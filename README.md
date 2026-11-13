# VibeMCP

An MCP server for controlling Lovense toys via Game Mode — built for LM Studio.

VibeMCP connects your AI agent to your Lovense toys through the official Lovense Remote app's Game Mode API (Standard Solutions). The agent can list connected toys, check battery levels, control vibration and other functions per actuator, play patterns and presets, listen for live toy events — and read a built-in manual for each supported model.

> **Note:** VibeMCP is an independent hobby project and is not affiliated with or endorsed by Lovense. "Lovense" and the product names are trademarks of their respective owners. This project builds on the original Game Mode MCP server published by Lovense (see [Credits](#credits)).

## Features

- **ListToys** – all connected toys: name, ID, battery, status, supported functions
- **GetBattery** – battery level per toy (or all at once)
- **SendFunction** – control any function (Vibrate, Thrusting, Fingering, …), including independent multi-motor control via `Vibrate1`/`Vibrate2`, with parallel or sequential execution (`stopPrevious`)
- **StopToy** – stop a toy (or all toys)
- **SendPattern** – custom vibration patterns (up to 50 strength values, configurable interval and duration)
- **SendPreset** – built-in Lovense presets: pulse, wave, fireworks, earthquake
- **ListenEvents** – live event channel (button presses, strength changes, …), with filters, timeout mode (`stopOnFirstMatch`) and automatic state restore (`keepState`)
- **ToyHelp** – built-in operating manuals for supported models (function names, motor mapping, intensity scales, notes)

## Requirements

- Windows 10/11 (Linux/macOS: run the Python command manually — see [Manual start](#manual-start))
- Python 3.10+ on PATH
- The **Lovense Remote app** with Game Mode running on your phone
- At least one Lovense toy connected to Game Mode

## Quick Start

### 1. One-time setup

Double-click `setup.cmd` (or run it in a terminal). It creates the virtual environment and installs all dependencies:

```
[1/3] Creating virtual environment...
[2/3] Installing dependencies (requirements.txt)...
[3/3] Setup complete!
```

### 2. Configure IP & port

Open `run.cmd` and set the two variables at the top:

| Variable | What to enter | Where to find it |
|---|---|---|
| `GAME_MODE_IP` | The phone's IP address on your network | Phone settings → Wi-Fi, or the Lovense Remote app (Game Mode section) |
| `GAME_MODE_PORT` | The Game Mode port | Shown in the Lovense Remote app — default is **30010** |

### 3. Add to LM Studio

In LM Studio: **Settings → MCP Servers → Add**, then point it at this folder:

- **Command:** `<path-to-this-folder>\run.cmd`
- Example: `D:\AI\MCP_Server\VibeMCP\run.cmd`

LM Studio starts the server itself — no manual start needed. Restart LM Studio (or reload MCP) if the tools don't appear.

### 4. Test it

Ask your agent something like: *"List my connected toys"* or *"Vibrate the Hush at intensity 5 for 3 seconds."*

## Using multiple identical toys

Toy IDs are **device-individual** — every physical toy has its own unique ID (stored in firmware, stable). If you connect several toys of the same model, they all report the same name. To keep things unambiguous:

1. Give each toy a **descriptive nickname** in the Lovense Remote app (long-press the toy → rename), e.g.:
   - Multiple people playing: `Hush Anna`, `Hush Ben` — so it's clear which person wears which toy
   - One person, multiple toys: `Hush anal`, `Hush vaginal` — so it's clear where each one is
2. The agent will then prefer the nickname when addressing a specific toy; if two toys still can't be told apart, it will ask you and address them by ID from that point on.

## Manual start (without LM Studio)

```bat
venv\Scripts\python VibeMCP.py GAME_MODE_IP=192.168.178.45 GAME_MODE_PORT=30010
```

The server speaks MCP over stdio — it is meant to be started by an MCP client (like LM Studio), not used interactively.

## Project structure

```
VibeMCP/
├── VibeMCP.py      # MCP server: tools, config, argument handling
├── ToyAPI.py       # Game Mode API layer: commands, toy resolution, patterns, events
├── manuals.json    # Built-in toy manuals (ToyHelp) — add your toys here
├── requirements.txt
├── setup.cmd       # One-time setup (venv + dependencies)
└── run.cmd         # Start script for LM Studio (IP/port configured here)
```

## Adding a new toy to the manuals

`manuals.json` is read fresh on every `ToyHelp` call — no restart needed. Add an entry under `"toys"`:

```json
"mytoy": {
  "type": "what it is",
  "functions": {"Vibrate": "0-20, what it does"},
  "notes": ["anything the agent should know"]
}
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Game Mode not reachable` | Game Mode not running on the phone, wrong IP/port in `run.cmd`, or phone and PC on different networks (Wi-Fi vs. mobile data) |
| `HTTP 401` from a command | The toy rejected it — check function names via `ToyHelp`; some functions don't exist on every model |
| No events from `ListenEvents` | Some toys don't send events at all (firmware limitation, e.g. Gush). Vulse does. |
| Tools missing in LM Studio | Reload MCP servers / restart LM Studio; check that the command path points to `run.cmd` |

## Credits & license

- Built on the original **Lovense Game Mode MCP server** published by Lovense (developer.lovense.com) — thank you!
- API reference: [Lovense Standard Solutions](https://developer.lovense.com/docs/standard-solutions/standard-api.html)
- Developed with AI assistance: Qwen3.8 27B, running on LM Studio Bionic (AI Assisted Coding)

Licensed under the [MIT License](LICENSE). Copyright DJBeatstar.
