---
name: lovense-toys
display-name: Lovense Toys
description: Use the Lovense MCP tools to control Lovense toys (functions incl. multi-motor control, patterns, presets, stop, list connected toys, check battery, look up per-toy operating manuals via ToyHelp) when the user asks about their toys.
---

# Controlling Lovense Toys (MCP Server "VibeMCP")

The MCP server **VibeMCP** connects over LAN to the Game Mode server of the
Lovense Remote app on the user's smartphone and controls the connected toys.
All commands run via HTTP (`/command`) – no cloud connection involved.

## Interacting with the User

These toys are for play – fun, intimacy, surprises. Be spontaneous, creative
and cheeky when it fits: take initiative, react to the conversation, surprise
the user. Not every vibration needs an announcement – surprise is part of the
game. Intensity and duration are at your discretion; only adjust if the user
explicitly wants softer or stronger, or signals discomfort.

## Available Tools

| Tool | Purpose |
|---|---|
| `ListToys()` | All currently connected toys: name, ID, battery (0–100 %), status, functions. **Call first when in doubt** to see what is connected. |
| `ToyHelp(toy?)` | Operating manual of a toy by model name (e.g. "dolce"): valid function names, motor assignment on multi-motor toys (which end Vibrate1/Vibrate2 drives), scales, notes. Empty `toy` = all available manuals. **Call before first use of an unknown toy.** |
| `GetBattery(toy?)` | Battery level by name/ID; empty `toy` = all toys. |
| `SendFunction(toy?, function, intensity, durationSec, stopPrevious?)` | Control any toy function by name or ID (vibration, thrusting, individual motors …); empty `toy` = **all** toys. Details below under "Functions & Multi-Motor Control". |
| `SendPattern(strengths, intervalMs, durationSec, toy?)` | Repeating vibration pattern: sequence of intensity values at a fixed tempo (e.g. `[5,10,20]` every 1 s); empty `toy` = **all** toys. |
| `SendPreset(name, durationSec, toy?)` | Built-in firmware patterns: `pulse`, `wave`, `fireworks`, `earthquake`; empty `toy` = **all** toys. |
| `StopToy(toy?)` | Stop the running action on a toy; empty `toy` = all toys. |
| `ListenEvents(durationSec=10, eventType="", toy="", stopOnFirstMatch=False, keepState=true)` | Listens 1–60 s on the toy event channel (WebSocket) and returns live events from the toy – e.g. button presses (`button-pressed`), intensity changes, battery/connection events. Details below. |

## Parameter Rules

- **`toy`**: name (`"vulse"`/`"gush"`/`"dolce"` …, case-insensitive),
  nickname (if set in the Lovense app) or hex ID. Empty = broadcast to all
  toys. Unknown names return an error listing the connected toys incl. IDs.
- **Multiple identical toys** (e.g. two Hush): if a toy has a unique
  **nickname** (set in the Lovense app), prefer addressing it by nickname –
  it is more specific than the model name, and users usually refer to their
  toys that way in conversation ("vibrate Anna's Hush"). Descriptive nicknames
  (`Hush anal` / `Hush vaginal`, or the wearer's name) make it immediately
  clear which toy sits where. Without a unique nickname: the server reports
  ambiguity and lists the candidates with ID + battery – then ask the user
  which toy is meant, and afterwards address it **by ID**. IDs are
  device-specific and stable (firmware value); `ListToys()` always provides them.
- **`function`** (SendFunction): function name of the toy, e.g. `Vibrate`,
  `Thrusting`. The valid names are in the toy manual (`ToyHelp(toy)`). Invalid
  names are rejected – the error lists all known functions with value ranges.
  Whether a toy physically supports a function is rejected by Lovense itself
  (code 401) – so consult `ToyHelp(toy)` beforehand.
- **`intensity`**: intensity on the toy's scale – for vibration typically
  **0–20** (0 = off, 10 = half strength, 20 = full power), `Pump` only **0–3**.
  The ranges are per function in the toy manual (`ToyHelp(toy)`); out-of-range
  values are clamped server-side – better to stay within the valid range.
  Intensity limits set in the Lovense app scale the output proportionally on
  the toy side – the MCP server passes the requested intensity through unchanged.
- **`durationSec`**: duration in seconds, applies to all tools with this
  parameter. Finite durations are honored by the toy itself and it stops on its
  own – no stop command needed. **Note: `0` means "runs until stopped"** – only
  use deliberately and briefly tell the user.
- **`stopPrevious`** (SendFunction): default `False` → the new function runs
  **in parallel** with already-running functions of the same toy (independent
  actuators). `True` → previously running functions are stopped first.
- **`strengths`** (SendPattern): list of vibration intensities, each value
  **0–20**, max 50 values; e.g. `[5,10,20]`. Invalid values are rejected with a
  clear error message.
- **`intervalMs`** (SendPattern): tempo between pattern steps in ms, minimum
  100 ms (default 1000).
- **`name`** (SendPreset): one of `pulse`, `wave`, `fireworks`, `earthquake`
  (case-insensitive) – the four patterns built into the Lovense firmware,
  **not** user-saved presets.
- **`ListenEvents`**: `durationSec` = listening window in seconds (**1–60**,
  default 10). `eventType` = optional filter on event type (e.g.
  `"button-pressed"`, case-insensitive). `toy` = optional filter for one toy
  (name/ID, like all other tools). `stopOnFirstMatch=True` ends listening
  **immediately** after the first matching event – ideal as a trigger: user
  presses the button on the toy → agent reacts instantly. ⚠️ Not all toys send
  events (firmware limitation, e.g. Vulse ✅, Gush/Gemini ❌) – `ToyHelp` tells
  you per toy. A button press on the Vulse **additionally** starts local
  vibration; with default `keepState=true` the server immediately restores the
  last MCP-sent state of the toy after the event (no manual stop needed).

## Functions & Multi-Motor Control

Toys with multiple motors/functions can be controlled **independently**:
simply send one call per function – they run in parallel because `stopPrevious`
defaults to `False`:

```text
1. SendFunction(toy="dolce", function="Vibrate2", intensity=5, durationSec=0)  → inner end on
2. SendFunction(toy="dolce", function="Vibrate1", intensity=8, durationSec=0)  → outer end added (inner keeps running!)
```

- The intensity of a running function can be changed live – a new command for
  the same function updates it without interruption.
- Individual motors are stopped with `intensity: 0` (the rest keeps running) or
  entirely via `StopToy`.
- ⚠️ **Motor numbering is toy-specific** (e.g. Vibrate1 = outer on one toy,
  inner on another) – always check via `ToyHelp(toy)` which end
  Vibrate1/Vibrate2 drives!

## Toy Manuals (ToyHelp)

The complete manuals per toy – valid function names, motor assignment on
multi-motor toys, intensity scales and important notes (e.g. whether the toy
sends events) – are provided by the tool `ToyHelp`:

- `ToyHelp()` – lists all toys with manuals.
- `ToyHelp(toy="dolce")` – complete manual for a single toy.

All toys can be controlled **simultaneously and independently**: intensity of a
running toy can be changed live, individual toys can be stopped one by one while
the others keep running. Multi-motor toys additionally per motor (see above).

## Error Handling

- **Connection errors / timeouts**: The Game Mode "Server" must be running in
  the Lovense Remote app on the smartphone and the phone must be in the same
  LAN. Point the user to start Game Mode in the app.
- **`code=401` / "rejected"**: Unknown toy or wrong ID – check with `ListToys()`
  what is actually connected.
- HTTP status is almost always 200; the real result is in the JSON field `code`.
