@echo off
REM ============================================================
REM  VibeMCP - MCP server for Lovense toys (Game Mode)
REM
REM  One-time setup: run setup.cmd first.
REM  Then edit the two variables below if needed:
REM    GAME_MODE_IP   = IP of the phone running Game Mode
REM    GAME_MODE_PORT = port shown in the Lovense Remote app (default 30010)
REM ============================================================
set "GAME_MODE_IP=192.168.178.45"
set "GAME_MODE_PORT=30010"

"%~dp0venv\Scripts\python.exe" "%~dp0VibeMCP.py" GAME_MODE_IP=%GAME_MODE_IP% GAME_MODE_PORT=%GAME_MODE_PORT%
pause
