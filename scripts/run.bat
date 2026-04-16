@echo off
REM =============================================================================
REM Spaceship Generator -- Windows launcher
REM
REM Usage:
REM   scripts\run.bat                    Launch web UI (default, port 5000)
REM   scripts\run.bat web [PORT]         Launch web UI on PORT
REM   scripts\run.bat cli  [ARGS ...]    Run CLI  -- e.g. cli --seed 42 --preview
REM   scripts\run.bat test [PYTEST ARGS] Run pytest
REM   scripts\run.bat list               List available palettes
REM   scripts\run.bat setup              Create .venv and install deps
REM   scripts\run.bat help               Show this help
REM
REM The .venv is auto-created on first run if missing.  Python 3.11+ on PATH.
REM Dependencies and entry-point are defined in pyproject.toml so this file
REM keeps working as the project evolves.
REM =============================================================================

setlocal
pushd "%~dp0\.."

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=web"

REM ---- dispatch help / setup before venv check ---------------------------------
if /i "%MODE%"=="help"   goto help
if /i "%MODE%"=="--help" goto help
if /i "%MODE%"=="-h"     goto help
if /i "%MODE%"=="/?"     goto help
if /i "%MODE%"=="setup"  goto setup

REM ---- auto-bootstrap on first run --------------------------------------------
if not exist "%PY%" (
    echo [run.bat] .venv not found -- bootstrapping...
    python -m venv "%VENV%" || goto fail_bootstrap
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install -e ".[dev]" || goto fail_bootstrap
    echo [run.bat] Bootstrap complete.
)

if /i "%MODE%"=="web"      goto web
if /i "%MODE%"=="cli"      goto cli
if /i "%MODE%"=="test"     goto test
if /i "%MODE%"=="list"     goto list
if /i "%MODE%"=="palettes" goto list

echo [run.bat] Unknown command: %MODE%
echo.
goto help

REM -----------------------------------------------------------------------------
:setup
echo [run.bat] Creating .venv and installing dependencies...
if not exist "%VENV%" (
    python -m venv "%VENV%" || goto fail_bootstrap
)
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -e ".[dev]" || goto fail_bootstrap
echo [run.bat] Setup complete.
goto end

REM -----------------------------------------------------------------------------
:web
set "PORT=%~2"
if "%PORT%"=="" set "PORT=5000"
echo [run.bat] Starting web UI at http://127.0.0.1:%PORT%/   (Ctrl-C to stop)
"%PY%" -m flask --app spaceship_generator.web.app run --host 127.0.0.1 --port %PORT%
goto end

REM -----------------------------------------------------------------------------
:cli
REM Strip the leading "cli" token, forward everything else.
for /f "tokens=1,*" %%a in ("%*") do set "REST=%%b"
"%PY%" -m spaceship_generator %REST%
set "REST="
goto end

REM -----------------------------------------------------------------------------
:test
for /f "tokens=1,*" %%a in ("%*") do set "REST=%%b"
"%PY%" -m pytest %REST%
set "REST="
goto end

REM -----------------------------------------------------------------------------
:list
"%PY%" -m spaceship_generator --list-palettes
goto end

REM -----------------------------------------------------------------------------
:fail_bootstrap
echo.
echo [run.bat] Bootstrap failed.  Is Python 3.11+ on PATH?
echo [run.bat] Try:  python --version
popd
endlocal
exit /b 1

REM -----------------------------------------------------------------------------
:help
echo.
echo Spaceship Generator launcher
echo ============================
echo   scripts\run.bat                    Launch web UI (default, port 5000)
echo   scripts\run.bat web [PORT]         Launch web UI on PORT
echo   scripts\run.bat cli  [ARGS ...]    Run CLI  (e.g. cli --seed 42 --palette ice_crystal --preview)
echo   scripts\run.bat test [PYTEST ARGS] Run pytest
echo   scripts\run.bat list               List available palettes
echo   scripts\run.bat setup              Create .venv and install deps
echo   scripts\run.bat help               Show this help
echo.
echo On first run the .venv is created and dependencies installed automatically.
echo.
goto end

REM -----------------------------------------------------------------------------
:end
popd
endlocal
