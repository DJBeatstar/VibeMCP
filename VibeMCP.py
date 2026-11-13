# VibeMCP.py - MCP server for controlling Lovense toys via Game Mode
from mcp.server.fastmcp import FastMCP
import json
import sys
import logging
import os
import re
import ToyAPI
logger = logging.getLogger('VibeMCP')

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stderr.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')



# Create an MCP server
mcp = FastMCP("VibeMCP")

directUrl = ""  # Direct IP connection to the local Game Mode (no DNS)

# ------------------------
# Utility Functions
# ------------------------

def validate_game_mode_ip(game_mode_ip) -> tuple:
    """Checks whether the Game Mode IP is valid (format + segments 0-255).

    Returns:
        tuple: (cleaned IP or None, status message)
    """
    if not game_mode_ip:
        return None, "❌ IP address cannot be empty"

    ip = game_mode_ip.strip()

    if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", ip):
        return None, "❌ Invalid IP format (e.g. 192.168.1.1)"

    for part in ip.split('.'):
        try:
            if not 0 <= int(part) <= 255:
                raise ValueError
        except ValueError:
            return None, "❌ Each IP segment must be between 0 and 255"

    return ip, f"✅ Valid IP: {ip}"

# ------------------------
# MCP -> Get from command line parameters
# ------------------------
def parse_args_from_argv() -> dict:
    args = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            args[key] = value
    return args

def get_mcp_config() -> dict:

    cli_args = parse_args_from_argv()

    config = {}
    config['game_mode_ip'] = cli_args.get("GAME_MODE_IP") or os.getenv("GAME_MODE_IP")
    config['game_mode_port'] = cli_args.get("GAME_MODE_PORT") or os.getenv("GAME_MODE_PORT")

    missing_keys = [k for k in ['game_mode_ip', 'game_mode_port'] if not config.get(k)]
    if missing_keys:
        raise ValueError(f"Required MCP configuration parameters are missing: {missing_keys}")

    ip, message = validate_game_mode_ip(config['game_mode_ip'])
    if not ip:
        raise ValueError(message)
    # Connect directly by IP (Game Mode runs locally). The lovense.club domain
    # from the original server is obsolete - see ToyAPI.py for certificate details.
    global directUrl
    directUrl = f"https://{ip}:{config['game_mode_port']}"
    return config





@mcp.tool()
def ListToys() -> dict:
    """Lists all toys currently connected to Game Mode.
    Returns per toy: name, ID, battery (0-100%), status and supported functions."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    try:
        toys = ToyAPI.get_toys(directUrl)
    except Exception as e:
        return {"success": False, "message": str(e)}

    if not toys:
        return {"success": True, "toys": [],
                "message": "No toys connected. Is the Game Mode server running in the Lovense Remote app?"}

    lines = []
    for t in toys:
        status = "connected" if t["status"] == "1" else f"Status={t['status']}"
        batt = f"{t['battery']}%" if t["battery"] is not None else "?"
        funcs = ", ".join(t["functions"]) or "unknown"
        nick = f" '{t['nickName']}'" if t.get("nickName") else ""
        lines.append(f"- {t['name']}{nick} (ID {t['id']}): battery {batt}, {status}, functions: {funcs}")
    return {"success": True, "toys": toys, "message": "\n".join(lines)}


@mcp.tool()
def GetBattery(toy: str = "") -> dict:
    """Returns the battery level (0-100%) of a toy by name or ID.
    With multiple identical toys (same name) always address by ID -
    the server reports ambiguity with candidate IDs. Empty 'toy' lists
    all connected toys."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    try:
        toys = ToyAPI.get_toys(directUrl)
    except Exception as e:
        return {"success": False, "message": str(e)}

    if toy.strip():
        toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
        if err:
            return {"success": False, "message": err}
        match = next((t for t in toys if t["id"] == toy_id), None)
        if not match:
            connected = ", ".join(t["name"] for t in toys) or "none"
            return {"success": False,
                    "message": f"'{toy}' is known but not currently connected. Connected: {connected}"}
        batt = match["battery"] if match["battery"] is not None else "unknown"
        return {"success": True, "toy": match["name"], "id": match["id"],
                "battery": match["battery"],
                "message": f"{match['name']}: battery {batt}%"}

    if not toys:
        return {"success": True, "batteries": {}, "message": "No toys connected."}
    lines = [f"- {t['name']}: {t['battery'] if t['battery'] is not None else '?'}%"
             for t in toys]
    return {"success": True,
            "batteries": {t["name"]: t["battery"] for t in toys},
            "message": "\n".join(lines)}


# ------------------------
# Toy manuals (manuals.json)
# ------------------------
MANUALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manuals.json")


def _load_manuals() -> dict:
    """Loads manuals.json fresh from disk - new entries without a server restart."""
    with open(MANUALS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("manuals.json must be a JSON object")
    return data


@mcp.tool()
def ToyHelp(toy: str = "") -> dict:
    """Returns the operating manual of a toy from manuals.json (no toy connection needed).

    toy = model name of the toy (e.g. 'hush', 'dolce' - size does not matter); an empty 'toy'
    lists all available manuals. ALWAYS call before first use of an unknown toy: it contains
    the valid function names, for multi-motor toys which motor number drives which end
    (e.g. Vibrate1/Vibrate2), the intensity scales and important notes (e.g. whether the
    toy sends events)."""
    try:
        data = _load_manuals()
    except Exception as e:
        return {"success": False, "message": f"manuals.json could not be loaded: {e}"}

    toys = data.get("toys") or {}
    general = data.get("general") or {}

    if not toy.strip():
        lines = [f"- {name}: {t.get('type', 'unknown type')}" for name, t in sorted(toys.items())]
        return {"success": True, "available_manuals": list(toys.keys()),
                "general": general,
                "message": "Available manuals:\n" + "\n".join(lines) +
                           "\nCall with ToyHelp(toy='<name>') to get the complete manual."}

    ref = toy.strip().lower()
    match_name = next((n for n in toys if n.lower() == ref), None)
    if not match_name:
        return {"success": False,
                "message": f"No manual for '{toy}'. Available: {', '.join(sorted(toys.keys()))}"}

    entry = toys[match_name]
    return {"success": True, "toy": match_name,
            "type": entry.get("type"), "functions": entry.get("functions", {}),
            "notes": entry.get("notes", []), "general": general,
            "message": f"Manual for {match_name}: {entry.get('type', '')}"}


@mcp.tool()
def SendFunction(toy: str = "", function: str = "Vibrate", intensity: int = 10,
                 durationSec: int = 2, stopPrevious: bool = False) -> dict:
    """Controls a function of a Lovense toy by name or ID (empty 'toy' = all toys).
    With multiple identical toys (same name) always address by ID - the server
    reports ambiguity with candidate IDs.

    function is the toy's function name - e.g. Vibrate, Thrusting, Fingering;
    for multi-motor toys also Vibrate1/Vibrate2 (valid functions and the motor
    mapping are in the ToyHelp manual). intensity is the level on the toy scale
    (typically 0-20, Pump 0-3); values outside the toy's range are clamped.
    durationSec in seconds; 0 = runs until StopToy is called, otherwise the
    firmware stops it by itself.

    Multiple actuators of the same toy can be controlled independently: simply
    send one separate call per function (e.g. Vibrate1 and Vibrate2). By default
    new functions run IN PARALLEL with already-running functions of the toy
    (stopPrevious=False). stopPrevious=True stops previously running functions
    of the same toy before starting the new one."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
    if err:
        return {"success": False, "message": err}

    canonical, lo, hi, ferr = ToyAPI.check_function(function)
    if ferr:
        return {"success": False, "message": ferr}

    requested = int(intensity)
    applied = max(lo, min(requested, hi))
    clamped = applied != requested

    try:
        ToyAPI.send_command(directUrl, {
            "command": "Function",
            "action": f"{canonical}:{applied}",
            "timeSec": max(0, int(durationSec)),
            "toy": toy_id,
            # stopPrevious=0: new function runs in parallel with already-running
            # functions of the same toy (independent actuators). Per the official
            # spec the API default is 1 (stops previous ones) - so we send it explicitly.
            "stopPrevious": 1 if stopPrevious else 0,
            "apiVer": 1,
        })
    except Exception as e:
        return {"success": False, "message": str(e)}

    target = toy if toy.strip() else "ALL toys"
    msg = f"{target}: {canonical} at intensity {applied}/{hi}"
    if clamped:
        msg += f" (requested: {requested}, clamped to toy range {lo}-{hi})"
    if int(durationSec) == 0:
        msg += " - runs until StopToy is called!"
    else:
        msg += f" for {int(durationSec)}s (stops by itself)"
    return {"success": True, "message": msg}


@mcp.tool()
def StopToy(toy: str = "") -> dict:
    """Stops the current action on a toy by name or ID.
    With multiple identical toys (same name) always address by ID - the server
    reports ambiguity with candidate IDs. Empty 'toy' stops all toys."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
    if err:
        return {"success": False, "message": err}

    try:
        ToyAPI.send_command(directUrl, {
            "command": "Function",
            "action": "Stop",
            "timeSec": 0,
            "toy": toy_id,
            "apiVer": 1,
        })
    except Exception as e:
        return {"success": False, "message": str(e)}

    target = toy if toy.strip() else "ALL toys"
    return {"success": True, "message": f"{target} stopped."}


@mcp.tool()
def SendPattern(strengths: list, intervalMs: int = 1000, durationSec: int = 5, toy: str = "") -> dict:
    """Plays a custom vibration pattern on a toy by name or ID
    (empty 'toy' = all toys; with multiple identical toys always use ID -
    the server reports ambiguity with candidate IDs).

    strengths is a list of values 0-20 (max. 50) that repeat at the interval
    intervalMs (milliseconds, min. 100) - e.g. [5,10,20] vibrates weak-medium-full
    in turn. durationSec in seconds; 0 = runs until StopToy is called, otherwise
    the firmware stops it by itself.

    IMPORTANT: patterns always affect ALL motors of the toy - per-motor patterns
    do not exist in the Lovense API (API limitation, assumed to apply to all toys).
    For per-motor effects: use SendFunction with Vibrate1/Vibrate2 (see ToyHelp
    for the mapping)."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
    if err:
        return {"success": False, "message": err}

    payload, err = ToyAPI.build_pattern_payload(toy_id, strengths, intervalMs, durationSec)
    if err:
        return {"success": False, "message": err}

    try:
        ToyAPI.send_command(directUrl, payload)
    except Exception as e:
        return {"success": False, "message": str(e)}

    target = toy if toy.strip() else "ALL toys"
    seq = ";".join(str(s) for s in strengths)
    msg = f"{target}: pattern [{seq}] repeating every {intervalMs} ms"
    if int(durationSec) == 0:
        msg += " - runs until StopToy is called!"
    else:
        msg += f" for {durationSec}s (stops by itself)"
    return {"success": True, "message": msg}


@mcp.tool()
def SendPreset(name: str, durationSec: int = 5, toy: str = "") -> dict:
    """Plays a built-in vibration pattern on a toy by name or ID
    (empty 'toy' = all toys; with multiple identical toys always use ID -
    the server reports ambiguity with candidate IDs).

    Available presets: pulse, wave, fireworks, earthquake.
    durationSec in seconds; 0 = runs until StopToy is called, otherwise
    the firmware stops it by itself."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
    if err:
        return {"success": False, "message": err}

    payload, err = ToyAPI.build_preset_payload(toy_id, name, durationSec)
    if err:
        return {"success": False, "message": err}

    try:
        ToyAPI.send_command(directUrl, payload)
    except Exception as e:
        return {"success": False, "message": str(e)}

    target = toy if toy.strip() else "ALL toys"
    msg = f"{target}: preset '{name}'"
    if int(durationSec) == 0:
        msg += " - runs until StopToy is called!"
    else:
        msg += f" for {durationSec}s (stops by itself)"
    return {"success": True, "message": msg}


@mcp.tool()
async def ListenEvents(durationSec: int = 10, eventType: str = "", toy: str = "",
                       stopOnFirstMatch: bool = False, keepState: bool = True) -> dict:
    """Listens on the toy events channel (WebSocket) and collects live events.

    Opens its own connection to Game Mode for durationSec seconds (1-60) and
    returns all events arriving there - e.g. button-down / button-up /
    button-pressed (button press on the toy), function-strength-changed,
    toy-status, battery-changed or toy-list. Each event gets a field 't' with
    the time in seconds since listening started.

    eventType: optional filter on the event type (e.g. "button-pressed").
    toy: optional filter by name or ID - only events of this toy (with multiple
    identical toys always use ID; the server reports ambiguity).
    stopOnFirstMatch=True: returns IMMEDIATELY after the first matching event
    (durationSec becomes a timeout) - ideal for trigger reactions, e.g. detect
    a button press and stop the toy right after.
    keepState (default true, only effective with stopOnFirstMatch=True): the server
    restores the last known state of the toy IMMEDIATELY after the detected event
    - without an agent round-trip (~1 s latency saved). Known state = the last
    command sent to this toy via MCP (it is re-sent, e.g. pattern from the start);
    unknown (e.g. after a server restart) -> fallback: full stop of the toy.
    keepState=false: the server does not change the toy itself - then call StopToy
    manually if needed.
    Note: not all toys send events (firmware limitation, e.g. Gush no; Vulse yes)."""
    if not directUrl:
        return {"success": False, "message": "Direct URL not initialized"}

    try:
        duration = int(durationSec)
    except (TypeError, ValueError):
        return {"success": False, "message": "durationSec must be an integer."}
    if duration < 1 or duration > ToyAPI.EVENTS_MAX_DURATION_SEC:
        return {"success": False,
                "message": f"durationSec must be between 1 and {ToyAPI.EVENTS_MAX_DURATION_SEC} seconds (given: {duration})."}

    toy_id = ""
    if toy.strip():
        toy_id, err = ToyAPI.resolve_toy(directUrl, toy)
        if err:
            return {"success": False, "message": err}

    # TLS port (30010) -> wss://, otherwise ws://. Game Mode speaks TLS on the
    # configured port - just like /command over https.
    if directUrl.startswith("https://"):
        ws_url = directUrl.replace("https://", "wss://") + ToyAPI.EVENTS_WS_PATH
    else:
        ws_url = directUrl.replace("http://", "ws://") + ToyAPI.EVENTS_WS_PATH
    try:
        result = await ToyAPI.listen_events(
            ws_url, duration, eventType.strip(), toy_id,
            stop_on_first_match=bool(stopOnFirstMatch),
            keep_state=bool(keepState), command_url=directUrl
        )
    except Exception as e:
        return {"success": False, "message": str(e)}

    events = result["events"]
    toys_seen = result["toys_seen"]

    if not events:
        msg = f"No events during {duration}s of listening."
        filters = []
        if eventType.strip():
            filters.append(f"type='{eventType.strip()}'")
        if toy_id:
            filters.append(f"toy={toy}")
        if filters:
            msg += " (filters: " + ", ".join(filters) + ")"
        return {"success": True, "events": [], "count": 0,
                "toysSeen": toys_seen, "message": msg}

    name_by_id = {}
    for t in toys_seen:
        if t.get("id"):
            name_by_id[str(t["id"]).lower()] = t.get("name") or str(t["id"])

    lines = []
    for ev in events[:20]:
        etype = ev.get("type", "?")
        extra = ""
        tid = str(ev.get("toyId", "")).lower()
        if tid:
            extra = f" [{name_by_id.get(tid, ev['toyId'])}]"
        data = ev.get("data")
        line = f"- {ev.get('t', 0):>5.1f}s: {etype}{extra}"
        if data is not None:
            line += " " + json.dumps(data, ensure_ascii=False)
        lines.append(line)
    msg = f"{len(events)} Events in {duration}s:\n" + "\n".join(lines)
    if len(events) > 20:
        msg += f"\n(... {len(events) - 20} more events in the 'events' field)"

    state_restored = result.get("stateRestored")
    if state_restored:
        if state_restored.get("error"):
            msg += f"\n⚠️ keepState error: {state_restored['error']}"
        else:
            msg += f"\n⚡ keepState: {state_restored.get('action', '')} (no manual stop needed)"

    return {"success": True, "events": events, "count": len(events),
            "toysSeen": toys_seen, "stateRestored": state_restored,
            "message": msg}


# Start the server
if __name__ == "__main__":
    get_mcp_config()
    mcp.run(transport="stdio")
