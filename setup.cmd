@echo off
rem ============================================================
rem  VibeMCP - Setup (one-time, double-click)
rem
rem  Creates the Python environment, installs the dependencies
rem  and asks for the Game Mode IP/port. Afterwards: run.cmd.
rem ============================================================

setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   VibeMCP - Setup
echo ============================================================
echo.

rem ---------- 1) Check Python (3.10 or newer) ----------
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD goto :no_python

set "PYOK="
%PYCMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PYOK=yes"
if not defined PYOK goto :py_too_old

echo [1/4] Python found: %PYCMD%

rem ---------- 2) Create virtual environment ----------
if exist "venv\Scripts\python.exe" (
    echo [2/4] Virtual environment already exists - skipped.
) else (
    echo [2/4] Creating virtual environment ...
    %PYCMD% -m venv venv || goto :error_venv
)

rem ---------- 3) Install dependencies ----------
echo [3/4] Installing Python packages (may take a moment) ...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error_pip

rem ---------- 4) Ask for IP and port ----------
echo.
echo [4/4] Now the connection to your phone:
echo       The IP address and port are shown in the Lovense app under Game Mode.
echo       Important: use the SSL Port from the app (not the plain port).
echo.

rem Load existing values as suggestions (if present)
set "GM_IP_DEFAULT="
set "GM_PORT_DEFAULT="
if exist "game_mode.txt" (
    for /f "usebackq tokens=1,* delims==" %%A in ("game_mode.txt") do (
        if /i "%%A"=="GAME_MODE_IP" set "GM_IP_DEFAULT=%%B"
        if /i "%%A"=="GAME_MODE_PORT" set "GM_PORT_DEFAULT=%%B"
    )
)

if defined GM_IP_DEFAULT (
    set "IP_HINT=[current: %GM_IP_DEFAULT% - Enter = keep]"
) else (
    set "IP_HINT=[e.g. 192.168.178.x - shown in the Lovense app]"
)
set /p GAME_MODE_IP="Phone IP address %IP_HINT%: "
if "%GAME_MODE_IP%"=="" if defined GM_IP_DEFAULT set "GAME_MODE_IP=%GM_IP_DEFAULT%"
if "%GAME_MODE_IP%"=="" goto :no_ip

if defined GM_PORT_DEFAULT (
    set "PORT_HINT=[current: %GM_PORT_DEFAULT% - Enter = keep]"
) else (
    set "PORT_HINT=[default: 30010 - Enter = 30010]"
)
set /p GAME_MODE_PORT="SSL Port (from the app) %PORT_HINT%: "
if "%GAME_MODE_PORT%"=="" if defined GM_PORT_DEFAULT set "GAME_MODE_PORT=%GM_PORT_DEFAULT%"
if "%GAME_MODE_PORT%"=="" set "GAME_MODE_PORT=30010"

> "game_mode.txt" echo GAME_MODE_IP=%GAME_MODE_IP%
>> "game_mode.txt" echo GAME_MODE_PORT=%GAME_MODE_PORT%

echo.
echo ============================================================
echo   Done! IP and port are now stored in game_mode.txt.
echo   Start the server with:  run.cmd
echo ============================================================
echo.
set /p START_NOW="Start the server right now? [y/N]: "
if /i "%START_NOW%"=="y" goto :start_server
if /i "%START_NOW%"=="yes" goto :start_server
pause & exit /b 0

:start_server
echo.
call run.cmd
exit /b 0

:no_ip
echo.
echo ERROR: The IP address is required.
echo Please run the setup again and take the IP from the Lovense app.
pause & exit /b 1

:error_venv
echo.
echo ERROR: Creating the venv failed.
echo Tip: Close other windows working in this folder and try again.
pause & exit /b 1

:error_pip
echo.
echo ERROR: Installing the packages failed (is the internet connection up?).
echo You can simply run the setup again - already installed parts are skipped.
pause & exit /b 1

:no_python
echo.
echo ERROR: Python was not found on this system.
echo Please install Python 3.10 or newer (https://www.python.org) and run the setup again.
pause & exit /b 1

:py_too_old
echo.
echo ERROR: The installed Python is older than version 3.10.
echo Please install a newer version (https://www.python.org) and run the setup again.
pause & exit /b 1
