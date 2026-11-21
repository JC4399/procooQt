@echo off
title Procoo Qt - Update
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "GIT_EXE=%~dp0git\cmd\git.exe"

echo.
echo   ========================================
echo     Procoo Qt - Update
echo   ========================================
echo.

rem ------------------------------------------------------------------
rem  1. Check portable Git
rem ------------------------------------------------------------------
echo [1/3] Checking portable Git...

if not exist "!GIT_EXE!" (
    echo   ERROR: Portable Git not found at "!GIT_EXE!".
    echo          Run install_procoo_qt.bat first.
    pause
    exit /b 1
)
echo   Portable Git ready.
echo.

rem ------------------------------------------------------------------
rem  2. Pull the latest changes
rem ------------------------------------------------------------------
echo [2/3] Pulling the latest changes from GitHub...

"!GIT_EXE!" pull --ff-only
if errorlevel 1 (
    echo   ERROR: git pull failed. Resolve the errors above and try again.
    pause
    exit /b 1
)
echo.

rem ------------------------------------------------------------------
rem  3. Sync project dependencies
rem ------------------------------------------------------------------
echo [3/3] Syncing project dependencies...

set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo   ERROR: uv not found. Run install_procoo_qt.bat first.
        pause
        exit /b 1
    )
)

"!UV!" sync --inexact
if errorlevel 1 (
    echo   ERROR: uv sync failed. Check the errors above.
    pause
    exit /b 1
)
echo.

echo   ========================================
echo     Update complete^^!
echo   ========================================
echo.
pause
