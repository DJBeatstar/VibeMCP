@echo off
rem ============================================================
rem  VibeMCP - Start script (Game Mode)
rem
rem  IP and port are stored in game_mode.txt in this folder.
rem  That file is created by the setup: run setup.cmd first.
rem ============================================================

setlocal EnableExtensions
cd /d "%~dp0"

if not exist "game_mode.txt" (
    echo ERROR: game_mode.txt was not found.
    echo Please run the setup first:  setup.cmd
    pause & exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in ("game_mode.txt") do set "%%A=%%B"

if not defined GAME_MODE_IP (
    echo ERROR: GAME_MODE_IP is missing from game_mode.txt.
    echo Please run the setup again:  setup.cmd
    pause & exit /b 1
)
if not defined GAME_MODE_PORT (
    echo ERROR: GAME_MODE_PORT is missing from game_mode.txt.
    echo Please run the setup again:  setup.cmd
    pause & exit /b 1
)

rem Determine the project folder automatically - do not change anything here
set "PROJECT_DIR=%~dp0"

"%PROJECT_DIR%venv\Scripts\python.exe" "%PROJECT_DIR%VibeMCP.py" GAME_MODE_IP=%GAME_MODE_IP% GAME_MODE_PORT=%GAME_MODE_PORT%
