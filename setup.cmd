@echo off
REM ============================================================
REM  VibeMCP - one-time setup (run once, then use run.cmd)
REM  Creates a virtual environment and installs all dependencies.
REM ============================================================
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
if exist venv\goto :venv_done
python -m venv venv
:venv_done

echo [2/3] Installing dependencies (requirements.txt)...
"%~dp0venv\Scripts\pip.exe" install --upgrade pip >nul
"%~dp0venv\Scripts\pip.exe" install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Installing dependencies failed.
    pause
    exit /b 1
)

echo [3/3] Setup complete!
echo.
echo Next steps:
REM TODO: replace with the actual IP/port of your phone (see Lovense Remote app, Game Mode section)
echo   1. Open run.cmd and set GAME_MODE_IP / GAME_MODE_PORT
REM    (the port is shown in the Lovense Remote app - default 30010)
echo   2. Start Game Mode on your phone with a toy connected
echo   3. Add VibeMCP to LM Studio as an MCP server:
echo        command: %~dp0run.cmd
pause
