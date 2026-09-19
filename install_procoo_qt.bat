@echo off
title Procoo Qt - Setup
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo   ========================================
echo     Procoo Qt - Setup
echo   ========================================
echo.

rem ------------------------------------------------------------------
rem  1. Check / install uv
rem ------------------------------------------------------------------
echo [1/4] Checking uv...

where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo   uv not found. Installing via standalone installer...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %ERRORLEVEL% neq 0 (
        echo   ERROR: Failed to install uv. Check your internet connection and try again.
        pause
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    echo   uv installed successfully.
) else (
    echo   uv already installed:
    uv --version
)
echo.

rem ------------------------------------------------------------------
rem  2. Ensure a suitable Python is available
rem ------------------------------------------------------------------
echo [2/4] Ensuring Python 3.13+ is available...
uv python install 3.13
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Failed to install Python 3.13.
    pause
    exit /b 1
)
echo   Python ready.
echo.

rem ------------------------------------------------------------------
rem  3. Install project dependencies
rem ------------------------------------------------------------------
echo [3/4] Installing project dependencies...
uv sync
if %ERRORLEVEL% neq 0 (
    echo   ERROR: uv sync failed. Check the errors above.
    pause
    exit /b 1
)
echo.

rem ------------------------------------------------------------------
rem  4. Setup config and storage
rem ------------------------------------------------------------------
echo [4/4] Setting up config and storage...

if not exist "config\config.yaml" (
    echo   Creating config.yaml from template...
    copy "config\config_template.yaml" "config\config.yaml" >nul
    echo   Remember to edit config\config.yaml with your LLM settings!
) else (
    echo   config.yaml already exists -- skipped.
)

if not exist "storage" (
    mkdir storage
    echo   Created storage directory.
) else (
    echo   storage directory already exists -- skipped.
)

echo.
echo   ========================================
echo     Setup complete! Run start_procoo_qt.bat
echo   ========================================
echo.
pause
