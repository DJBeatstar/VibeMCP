# ToyAPI.py
# Shared Lovense Game Mode API helpers for the MCP server:
# - send_command():   generic POST /command wrapper (checks JSON "code", not HTTP status)
# - get_toys():       "GetToys" query -> parsed toy list (name, ID, battery, status, functions)
# - resolve_toy():    translates user input (name/ID) into the hex toy ID (live only;
#                     ambiguity guard for multiple identical toys)
# - check_function(): generic validation of function names + value ranges

import asyncio
import json
import sys
import time

import requests


def _log(msg):
    # stdout is reserved for the MCP stdio protocol -> only log to stderr!
    print(msg, file=sys.stderr)


# ------------------------
# State tracking (keepState for ListenEvents)
# ------------------------
# Game Mode has NO API to query the current toy setting -
# GetToys only returns battery/status/limits/functions.
# So the server remembers every successfully sent actuator command per toy
# here and can repeat it immediately when needed (ListenEvents keepState=True).
# After an MCP restart this memory is empty -> fallback = full stop of the toy.

_last_command_by_toy = {}      # toy_id (lowercase) -> last payload
_last_broadcast_payload = None  # last broadcast payload (toy="")


def _track_command(payload: dict):
    """Remembers successfully sent actuator commands per toy."""
    cmd = str(payload.get("command", ""))
    if cmd not in ("Function", "Pattern", "Preset"):
        return  # only track actuator commands, not queries like GetToys
    toy_key = str(payload.get("toy") or "").strip().lower()
    global _last_broadcast_payload
    if toy_key:
        _last_command_by_toy[toy_key] = payload
    else:
        _last_broadcast_payload = payload


def get_tracked_state(toy_id: str):
    """Last known actuator command for a toy (fallback: broadcast)."""
    key = str(toy_id or "").strip().lower()
    if key and key in _last_command_by_toy:
        return _last_command_by_toy[key]
    return _last_broadcast_payload


def _describe_payload(payload: dict) -> str:
    cmd = str(payload.get("command", ""))
    if cmd == "Function":
        return f"Function {payload.get('action', '?')}"
    if cmd == "Pattern":
        return f"Pattern (strengths {payload.get('strength', '?')})"
    if cmd == "Preset":
        return f"Preset '{payload.get('name', '?')}'"
    return cmd or "?"


def send_command(url: str, payload: dict) -> dict:
    """POSTs a command to {url}/command and returns the parsed JSON.

    The HTTP status is almost always 200; the real result is in the JSON field
    "code" (200 = accepted, 401 = rejected). Raises RuntimeError on connection
    problems or when the server reports an error code.
    """
    command_url = f"{url}/command"
    # verify=False: direct IP connection (no lovense.club DNS); the certificate
    # is issued for *.lovense.club. Local network only - OK.
    response = requests.post(command_url, json=payload, verify=False, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from {command_url}: {response.text[:200]}")

    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(f"No JSON response from {command_url}: {response.text[:200]}")

    code = result.get("code", 200)
    label = payload.get("command") or payload.get("action") or "?"
    _log(f"✅ /command {label} -> code={code}")
    if code != 200:
        raise RuntimeError(
            f"Game Mode rejected the command (code={code}): {result.get('message', result)}"
        )
    _track_command(payload)
    return result


def get_toys(url: str) -> list:
    """Queries the connected toys via the "GetToys" command.

    Returns a list of dicts with normalized fields:
      id, name (lowercase), nickName, status ("1" = connected),
      battery (0-100 or None), version, functions (list), strengths (dict)

    Note: "strengths" are the intensity LIMITS configured in the app, in
    percent - NOT the current vibration level!
    """
    result = send_command(url, {"command": "GetToys", "apiVer": 1})

    raw = (result.get("data") or {}).get("toys")
    if not raw:
        return []

    # data.toys is a JSON STRING inside the JSON response -> parse twice.
    toys_obj = json.loads(raw) if isinstance(raw, str) else raw

    toys = []
    for toy_id, info in toys_obj.items():
        functions = info.get("shortFunctionNames") or []
        if isinstance(functions, str):
            try:
                functions = json.loads(functions)
            except ValueError:
                functions = [f.strip() for f in functions.split(",") if f.strip()]

        settings = info.get("settings") or {}
        strengths = settings.get("strengths") or {}
        if isinstance(strengths, str):
            try:
                strengths = json.loads(strengths)
            except ValueError:
                strengths = {}

        battery_raw = str(info.get("battery", ""))
        toys.append({
            "id": toy_id,
            "name": (info.get("name") or "").lower(),
            "nickName": info.get("nickName") or "",
            "status": str(info.get("status", "")),
            "battery": int(battery_raw) if battery_raw.lstrip("-").isdigit() else None,
            "version": info.get("version") or "",
            "functions": functions,
            "strengths": strengths,
        })
    return toys


# Generic function whitelist + value ranges per the official Lovense spec:
# Vibration/Rotation/Fingering/Suction/Thrusting 0-20, Pump/Air 0-3.
# Vibrate1/Vibrate2 are the multi-motor channels (e.g. Dolce, Edge). They apply
# generically to all toys here: whether a toy physically supports them is in
# manuals.json (ToyHelp); otherwise Lovense itself rejects it (code 401).
DEFAULT_FUNCTIONS = {
    "Vibrate": (0, 20),
    "Vibrate1": (0, 20),
    "Vibrate2": (0, 20),
    "Rotate": (0, 20),
    "Pump": (0, 3),
    "Thrusting": (0, 20),
    "Fingering": (0, 20),
    "Suction": (0, 20),
}


def resolve_toy(url: str, name_or_id: str):
    """Translates user input into the hex toy ID for /command.

    Accepts "" (all toys), a full hex ID or a name/nickname (case-insensitive).
    The source is ALWAYS the live GetToys query - there is no local registry:
    only connected toys are addressable, and their IDs come from GetToys live.

    IMPORTANT: toy IDs are DEVICE-INDIVIDUAL (stored in firmware, stable) -
    multiple devices of the same model have different IDs. An ID is therefore
    always unambiguous. A name/nickname is only accepted when exactly ONE
    connected device matches it; with several candidates this function returns
    an ambiguity error message with the candidate list (IDs + battery), so the
    agent can ask the user which device was meant.

    Returns (toy_id_or_empty, error_message_or_None).
    """
    ref = (name_or_id or "").strip()
    if not ref:
        return "", None  # empty = broadcast to all toys

    try:
        live_toys = get_toys(url)
    except Exception as e:
        _log(f"⚠️ Live GetToys query failed: {e}")
        if len(ref) >= 4 and all(c in "0123456789abcdefABCDEF" for c in ref):
            # Looks like a toy ID -> pass through; the command would fail at
            # Lovense anyway with a clear message.
            return ref, None
        return "", f"Game Mode not reachable ({e}) - cannot resolve toy '{ref}'."

    ref_l = ref.lower()

    # 1) ID match: always unambiguous (IDs are device-individual).
    for t in live_toys:
        if ref_l == str(t["id"]).lower():
            return t["id"], None

    # 2) name/nickname: collect all candidates.
    candidates = []
    for t in live_toys:
        name_hit = ref_l == str(t["name"]).lower()
        nick_hit = bool(t.get("nickName")) and ref_l == str(t["nickName"]).lower()
        if name_hit or nick_hit:
            candidates.append(t)

    if len(candidates) == 1:
        return candidates[0]["id"], None

    if len(candidates) > 1:
        parts = []
        for t in candidates:
            label = str(t["name"])
            if t.get("nickName"):
                label += f" (nickname '{t['nickName']}')"
            batt = f", battery {t['battery']}%" if t.get("battery") is not None else ""
            parts.append(f"{label} ID {t['id']}{batt}")
        err = (
            f"Ambiguous: '{ref}' matches {len(candidates)} connected devices: "
            + "; ".join(parts)
            + ". Please ask the user which device was meant, then address it by ID."
        )
        return "", err

    connected = ", ".join(f"{t['name']} (ID {t['id']})" for t in live_toys) or "none"
    err = f"Unknown toy '{ref}'. Currently connected: {connected}."
    if not live_toys:
        err += " (Is Game Mode active on the phone?)"
    return "", err


def check_function(function_name: str):
    """Validates a function name generically against DEFAULT_FUNCTIONS.

    Returns (canonical_function_name, min, max, error_message_or_None).
    Toy-specific validity (e.g. whether a toy physically has Vibrate1/Vibrate2)
    is checked by Lovense itself - the agent should consult ToyHelp beforehand.
    """
    fn = (function_name or "").strip()
    if not fn:
        return "", 0, 20, "function must not be empty."

    for name, (lo, hi) in DEFAULT_FUNCTIONS.items():
        if name.lower() == fn.lower():
            return name, lo, hi, None

    available = ", ".join(f"{n} [{lo}-{hi}]" for n, (lo, hi) in DEFAULT_FUNCTIONS.items())
    return "", 0, 20, (
        f"'{fn}' is not a known Lovense function. Known functions: {available}. "
        f"Call ToyHelp for toy-specific details."
    )


# ------------------------
# Pattern & Preset (pattern commands)
# ------------------------

PRESET_NAMES = ("pulse", "wave", "fireworks", "earthquake")
PATTERN_MAX_STRENGTHS = 50


def _validate_duration(duration_sec):
    """Checks timeSec per the official spec: 0 = endless, otherwise > 1.

    Returns (value_or_None, error_message_or_None).
    """
    try:
        value = float(duration_sec)
    except (TypeError, ValueError):
        return None, "durationSec must be a number."
    if value < 0 or (0 < value <= 1):
        return None, (
            "durationSec: 0 = endless (until StopToy), otherwise the value must be greater than 1 second."
        )
    # Whole-number values stay int (clean JSON), otherwise float
    if value == int(value):
        return int(value), None
    return value, None


def build_pattern_payload(toy_id: str, strengths, interval_ms, duration_sec):
    """Validates the parameters and builds the /command payload for the Pattern command.

    Official spec (Standard API, "Pattern Request", apiVer always 2):
      rule     = "V:1;F:v;S:<ms>#"
                 V:1 static; F: functions (v=vibrate, r=rotate, p=pump,
                 t=thrusting, f=fingering, s=suction, d=depth, o=oscillate);
                 S: interval in ms (> 100). Here always vibration only (F:v).
      strength = semicolon-separated values, max. 50, vibration scale 0-20
      timeSec  = 0 = endless, otherwise > 1; the firmware stops by itself
      toy      = optional, empty/missing = all toys

    Returns (payload_or_None, error_message_or_None).
    """
    if not isinstance(strengths, (list, tuple)) or len(strengths) == 0:
        return None, "strengths must be a list with at least one value."
    if len(strengths) > PATTERN_MAX_STRENGTHS:
        return None, f"At most {PATTERN_MAX_STRENGTHS} values allowed (given: {len(strengths)})."

    values = []
    for i, s in enumerate(strengths):
        try:
            v = int(s)
        except (TypeError, ValueError):
            return None, f"strengths[{i}] is not an integer: {s!r}"
        if not 0 <= v <= 20:
            return None, f"strengths[{i}] = {v} is outside the range 0-20."
        values.append(v)

    try:
        interval_ms = int(interval_ms)
    except (TypeError, ValueError):
        return None, "intervalMs must be a number."
    if interval_ms < 100:
        return None, f"intervalMs must be at least 100 ms (given: {interval_ms})."

    duration, err = _validate_duration(duration_sec)
    if err:
        return None, err

    payload = {
        "command": "Pattern",
        "rule": f"V:1;F:v;S:{interval_ms}#",
        "strength": ";".join(str(v) for v in values),
        "timeSec": duration,
        "toy": toy_id,
        "apiVer": 2,
    }
    return payload, None


def build_preset_payload(toy_id: str, name: str, duration_sec):
    """Validates the parameters and builds the /command payload for the Preset command.

    Official spec (Standard API, "Preset Request", apiVer always 1): four built-in
    patterns of the Lovense Remote app - pulse, wave, fireworks, earthquake.
    timeSec: 0 = endless, otherwise > 1; toy optional (empty = all).

    Returns (payload_or_None, error_message_or_None).
    """
    preset = (name or "").strip().lower()
    if preset not in PRESET_NAMES:
        return None, f"Unknown preset '{name}'. Available: {', '.join(PRESET_NAMES)}."

    duration, err = _validate_duration(duration_sec)
    if err:
        return None, err

    payload = {
        "command": "Preset",
        "name": preset,
        "timeSec": duration,
        "toy": toy_id,
        "apiVer": 1,
    }
    return payload, None


# ------------------------
# Toy Events API (WebSocket event channel)
# ------------------------
#
# Official spec: developer.lovense.com/docs/standard-solutions/toy-events-api.html
# Connection setup:
#   1. Open a WebSocket to ws://<IP>:<PORT>/v1 (same IP/port as Game Mode)
#   2. Send {"type":"access","data":{"appName":...}} -> response "access-granted"
#   3. KEEP THE CHANNEL ALIVE: send {"type":"ping"} every 3 seconds, otherwise the
#      server drops the inactive connection after ~20 s (source: official demo
#      ToyEventsAPI_Demo.html, "Step 3: Maintain Connection")
#
# Known event types (live-verified on a Vulse):
#   access-granted, toy-list, pong (keep-alive response), button-down,
#   button-up, button-pressed, function-strength-changed
# Note: the physical button on the Vulse switches the vibration strength locally -
# every press generates button-* AND function-strength-changed events.
# Not all toys send events (e.g. Gush does not; firmware limitation).

EVENTS_WS_PATH = "/v1"
EVENTS_PING_INTERVAL_SEC = 3.0
EVENTS_MAX_DURATION_SEC = 60


async def listen_events(ws_url: str, duration_sec: float,
                        event_type_filter: str = "", toy_id_filter: str = "",
                        stop_on_first_match: bool = False,
                        keep_state: bool = True, command_url: str = "") -> dict:
    """Listens on the toy events channel and collects all events in the time window.

    keep_state (only effective with stop_on_first_match=True): restores the last
    known state of the toy IMMEDIATELY after the first matching event - without an
    agent round-trip. Known state = the last command sent to this toy via MCP (it is
    re-sent, e.g. pattern from the start); unknown -> fallback: full stop of the toy.
    command_url is the Game Mode base URL (http/https) for the restore command.

    Opens its own WebSocket connection (stateless - fresh per call), performs the
    access handshake, keeps the connection alive with 3s pings and collects all
    incoming events until the end of the window. "pong" is discarded as protocol
    noise; every event gets a field "t" (seconds since listening started).

    Filters: event_type_filter = exact event type (case-insensitive),
             toy_id_filter     = only events with this toy ID.
    stop_on_first_match=True ends listening immediately after the first matching
    event - durationSec then serves as the timeout window (trigger).

    Returns {"events": [...], "toys_seen": [{name,id,battery}, ...]}.
    toys_seen comes from the initial "toy-list" event. Raises RuntimeError on
    connection problems or a missing websockets package.
    """
    try:
        import websockets  # lazy import: without the package the HTTP tools should keep working
    except ImportError as e:
        raise RuntimeError(
            "The 'websockets' package is missing from the venv. Run: pip install websockets"
        ) from e

    etf = (event_type_filter or "").strip().lower()
    tidf = (toy_id_filter or "").strip().lower()

    events: list = []
    toys_seen: list = []
    state_restored = None
    t0 = time.time()
    stop = asyncio.Event()

    async def pinger(ws) -> None:
        # keep-alive: without pings the Game Mode server disconnects after ~20 s.
        while not stop.is_set():
            await asyncio.sleep(EVENTS_PING_INTERVAL_SEC)
            if stop.is_set():
                break
            try:
                await ws.send(json.dumps({"type": "ping"}))
            except Exception:
                return

    # TLS support: wss:// URLs (Game Mode TLS port 30010) need an SSL context
    # without certificate checking - Game Mode uses a *.lovense.club certificate,
    # just like the /command path with verify=False.
    ssl_kwargs = {}
    if ws_url.startswith("wss://"):
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_kwargs["ssl"] = ctx

    try:
        async with websockets.connect(ws_url, open_timeout=10, **ssl_kwargs) as ws:
            await ws.send(json.dumps(
                {"type": "access", "data": {"appName": "LM-Studio-MCP"}}
            ))
            pinger_task = asyncio.create_task(pinger(ws))
            deadline = t0 + duration_sec
            try:
                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=deadline - time.time()
                        )
                    except asyncio.TimeoutError:
                        break
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue  # not JSON -> ignore
                    mtype = str(msg.get("type", ""))
                    if mtype == "pong":
                        continue  # keep-alive response, not a real event
                    if mtype == "toy-list":
                        for t in msg.get("toyList") or []:
                            toys_seen.append({
                                "name": t.get("name"),
                                "id": t.get("id"),
                                "battery": t.get("battery"),
                            })
                    if etf and mtype.lower() != etf:
                        continue
                    tid = str(msg.get("toyId", "")).lower()
                    if tidf and tid != tidf:
                        continue
                    entry = dict(msg)
                    entry["t"] = round(time.time() - t0, 1)
                    events.append(entry)
                    if stop_on_first_match:
                        # keepState: restore the last known state of this toy
                        # IMMEDIATELY - without an agent round-trip that would
                        # otherwise cost ~1 s latency until the StopToy call.
                        if keep_state and command_url:
                            tid = str(msg.get("toyId") or "").strip().lower()
                            state = get_tracked_state(tid)
                            try:
                                if state is not None:
                                    # Rewrite the broadcast payload for this specific toy
                                    # so that only it is reset.
                                    if tid and not str(state.get("toy") or "").strip():
                                        state = dict(state)
                                        state["toy"] = msg.get("toyId")
                                    await asyncio.to_thread(send_command, command_url, state)
                                    state_restored = {
                                        "toyId": msg.get("toyId"),
                                        "action": f"last state restored: {_describe_payload(state)}",
                                    }
                                else:
                                    # Unknown state (e.g. after an MCP restart):
                                    # safe fallback = full stop of this toy.
                                    stop_payload = {
                                        "command": "Function", "action": "Stop",
                                        "timeSec": 0, "apiVer": 1,
                                    }
                                    if tid:
                                        stop_payload["toy"] = msg.get("toyId")
                                    await asyncio.to_thread(send_command, command_url, stop_payload)
                                    state_restored = {
                                        "toyId": msg.get("toyId"),
                                        "action": "no known state -> toy fully stopped",
                                    }
                            except Exception as e:
                                state_restored = {"toyId": msg.get("toyId"), "error": str(e)}
                        break
            finally:
                stop.set()
                pinger_task.cancel()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"WebSocket problem: {e}") from e

    return {"events": events, "toys_seen": toys_seen,
            "stateRestored": state_restored}
