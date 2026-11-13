# VibeMCP

An MCP server for **LM Studio** that controls Lovense toys over your local network – no cloud involved. The connection runs through the **Game Mode "Server"** of the Lovense Remote app on your smartphone:

```text
LM Studio (AI agent)  ←MCP/stdio→  VibeMCP.py   ←HTTP(S)/LAN→  Game-Mode server (smartphone)  ←Bluetooth→  toys
```

> Built using the public Lovense developer documentation; compatible with Lovense devices. Not affiliated with or endorsed by Lovense.

## Requirements

- **Python 3.10 or newer** (Windows, Linux or macOS)
- The **Lovense Remote app** on your smartphone with *Game Mode → Server* enabled
- Smartphone and PC on the **same LAN**
- The **IP address of the smartphone** in the LAN (shown in the Lovense app under Game Mode)

## Installation (Windows)

### 1. Clone the repository

```bat
git clone https://github.com/DJBeatstar/VibeMCP.git
cd VibeMCP
```

### 2. Run the setup

Double-click **`setup.cmd`** (or run `cmd /c setup.cmd` in a console). The script:

1. checks that Python 3.10 or newer is installed,
2. creates the virtual environment (`venv`) – skipped if it already exists,
3. installs the dependencies from `requirements.txt`,
4. asks for the **IP address and port** of the Game Mode (Enter keeps the previous/default value) and writes them to `game_mode.txt`.

At the end the setup offers to start the server directly – otherwise simply run **`run.cmd`** afterwards.

### 3. Configure LM Studio

In LM Studio's MCP settings, create a new server:

- **Name:** e.g. `VibeMCP`
- **Command:** full path to `run.cmd`, e.g. `C:\path\to\VibeMCP\run.cmd`

No extra arguments needed – the script reads IP and port from `game_mode.txt`. Then connect the server; the tools (`ListToys`, `SendFunction`, …) should appear in the MCP tool list.

> **Linux/macOS:** Instead of `run.cmd`, simply enter the equivalent command, e.g.
> `venv/bin/python VibeMCP.py GAME_MODE_IP=<ip> GAME_MODE_PORT=30010`.

### 4 (optional). Install the skill for the AI agent

The [`SKILL.md`](SKILL.md) file in the repository root teaches the agent how to use the tools correctly (parameter rules, multi-motor control, addressing multiple identical toys, event handling). The tools work without the skill – but the skill makes the agent significantly more reliable.

Installation: install via the skill management in LM Studio/Bionic.

## Available Tools

| Tool | Purpose |
|---|---|
| `ListToys()` | All connected toys: name, ID, battery, status, functions |
| `ToyHelp(toy?)` | Operating manual of a toy (function names, motor assignment, scales) |
| `GetBattery(toy?)` | Battery level of one or all toys |
| `SendFunction(...)` | Control a function: vibration, thrusting, individual motors – also in parallel & changeable live |
| `SendPattern(...)` | Repeating vibration pattern (sequence + tempo) |
| `SendPreset(name, ...)` | Firmware patterns: `pulse`, `wave`, `fireworks`, `earthquake` |
| `StopToy(toy?)` | Stop the running action |
| `ListenEvents(...)` | Listen for live events from a toy (e.g. button press as trigger) |

Details and parameter rules: [`SKILL.md`](SKILL.md).

## Multiple identical toys

If you own several identical toys (e.g. two Hush), it is best to assign **descriptive nicknames** directly in the Lovense app – e.g. `Hush anal` / `Hush vaginal`, or, with multiple people, the name of the wearer (`Hush Anna`). The agent recognizes the nicknames automatically and can then address each toy individually without asking; this keeps it clear at all times which toy is where and whose it is.

Without a nickname, the agent asks when there is ambiguity and addresses the toy by ID – that works reliably as well (the IDs are provided by `ListToys()`).

## Adding new toys / extending manuals

The single data source is `manuals.json`: simply add a new toy object following the same pattern (type, functions with effect + scale, notes).
Toy-specific safety notes (if ever needed) belong in the `notes` of the respective toy object – not in SKILL.md. The server reloads the file from disk on every `ToyHelp()` call – **no restart** required. Toy IDs do not belong there: they are device-specific firmware values and are delivered live by `ListToys()`.

## Troubleshooting

| Symptom | Cause / solution |
|---|---|
| `run.cmd` reports "ERROR: game_mode.txt was not found." | Setup has not been run yet – start `setup.cmd` |
| Server does not start: "Required MCP configuration parameters are missing" | `GAME_MODE_IP`/`GAME_MODE_PORT` missing or malformed in `game_mode.txt` (format: `KEY=VALUE`) – re-run `setup.cmd` |
| Connection errors / timeouts on tool calls | Is the Game Mode "Server" not running in the app? Smartphone on the same LAN? IP address correct (it can change!)? |
| `code=401` / "rejected" | Unknown toy or wrong ID – check with `ListToys()` what is connected |

## Project structure

```text
VibeMCP/
├── VibeMCP.py            # MCP server (tools)
├── ToyAPI.py             # HTTP connection to the Game-Mode server
├── manuals.json          # Single data source: manuals for ToyHelp()
├── requirements.txt      # Python dependencies
├── setup.cmd             # One-time setup: venv, packages, IP/port prompt
├── game_mode.txt         # Configuration (IP/port), created by setup.cmd
├── run.cmd               # Start script (reads IP/port from game_mode.txt)
└── SKILL.md              # Skill file for AI agents
```

## License

This project is licensed under the MIT License – see [LICENSE](LICENSE).

## Developers

- **DJBeatstar**
- Qwen3.8 27B, running on LM Studio Bionic (AI Assisted Coding)
