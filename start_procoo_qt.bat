@echo off
title Procoo Qt - Launch
setlocal

cd /d "%~dp0"

echo.
echo   ========================================
echo     Procoo Qt - Launch
echo   ========================================
echo.

rem ------------------------------------------------------------------
rem  Launch Procoo Qt
rem ------------------------------------------------------------------
call .\.venv\Scripts\activate
python -m src.app
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Procoo Qt exited with an error (code %ERRORLEVEL%).
)

echo.
echo   ========================================
echo     Procoo Qt closed.
echo   ========================================
echo.
pause
