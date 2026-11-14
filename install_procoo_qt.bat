@echo off
title Procoo Qt - Setup
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "REPO_URL=https://github.com/JC4399/procooQt.git"
set "MINIGIT_API=https://api.github.com/repos/git-for-windows/git/releases/latest"

rem ------------------------------------------------------------------
rem  Resolve the app folder (install in place when this script already
rem  lives inside a checkout).
rem ------------------------------------------------------------------
if exist "%~dp0.git" (
    set "APP_DIR=%~dp0"
) else (
    set "APP_DIR=%~dp0procooQt"
)
if "!APP_DIR:~-1!"=="\" set "APP_DIR=!APP_DIR:~0,-1!"
set "APP_DIR_DISPLAY=!APP_DIR!"
set "GIT_DIR=!APP_DIR!\git"
set "GIT_EXE=!GIT_DIR!\cmd\git.exe"
set "STAGE_DIR=%~dp0.git_stage"
set "STAGED=0"

echo.
echo   ========================================
echo     Procoo Qt - Setup
echo   ========================================
echo.

rem ------------------------------------------------------------------
rem  1. Ensure portable Git (MinGit) is available
rem ------------------------------------------------------------------
echo [1/6] Checking portable Git...

if exist "!GIT_EXE!" (
    echo   Portable Git already installed.
) else (
    echo   Downloading the latest MinGit release...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference='Stop';" ^
      "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
      "$rel=Invoke-RestMethod -UseBasicParsing '!MINIGIT_API!';" ^
      "$asset=$rel.assets | Where-Object { $_.name -match '^MinGit-[0-9.]+-64-bit\.zip$' } | Select-Object -First 1;" ^
      "if (-not $asset) { throw 'No MinGit 64-bit asset found in the latest release.' };" ^
      "Write-Host ('  Downloading ' + $asset.name);" ^
      "Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile '%~dp0.git_stage.zip';"
    if errorlevel 1 (
        echo   ERROR: Failed to download MinGit. Check your internet connection.
        pause
        exit /b 1
    )

    if exist "!STAGE_DIR!" rmdir /s /q "!STAGE_DIR!"
    echo   Extracting...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference='Stop';" ^
      "Expand-Archive -LiteralPath '%~dp0.git_stage.zip' -DestinationPath '!STAGE_DIR!' -Force;"
    del /q "%~dp0.git_stage.zip" >nul 2>nul

    if not exist "!STAGE_DIR!\cmd\git.exe" (
        echo   ERROR: MinGit extraction did not produce cmd\git.exe.
        pause
        exit /b 1
    )
    set "STAGED=1"
    set "GIT_EXE=!STAGE_DIR!\cmd\git.exe"
    echo   Portable Git ready.
)
echo.

rem ------------------------------------------------------------------
rem  2. Install the app from GitHub
rem ------------------------------------------------------------------
echo [2/6] Installing Procoo Qt from GitHub...

if exist "!APP_DIR!\.git" (
    echo   Existing checkout found -- skipping clone.
) else (
    if exist "!APP_DIR!" (
        dir /a /b "!APP_DIR!" 2>nul | findstr /r /c:"^." >nul
        if not errorlevel 1 (
            echo   ERROR: "!APP_DIR_DISPLAY!" already exists and is not empty.
            echo          Remove it and re-run this installer.
            pause
            exit /b 1
        )
    )
    echo   Cloning !REPO_URL! ...
    "!GIT_EXE!" clone "!REPO_URL!" "!APP_DIR!"
    if errorlevel 1 (
        echo   ERROR: git clone failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo   Repository cloned.
)
echo.

rem ------------------------------------------------------------------
rem  3. Place portable Git inside the app folder
rem ------------------------------------------------------------------
echo [3/6] Installing portable Git into the app folder...

if "!STAGED!"=="1" (
    if exist "!GIT_DIR!" rmdir /s /q "!GIT_DIR!"
    move "!STAGE_DIR!" "!GIT_DIR!" >nul
    if errorlevel 1 (
        echo   ERROR: Could not move portable Git into "!GIT_DIR!".
        pause
        exit /b 1
    )
    set "GIT_EXE=!GIT_DIR!\cmd\git.exe"
    echo   Portable Git installed.
) else (
    echo   Portable Git already in place -- skipped.
)
echo.

rem ------------------------------------------------------------------
rem  4. Check / install uv
rem ------------------------------------------------------------------
echo [4/6] Checking uv...

set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo   uv not found. Installing via standalone installer...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        if errorlevel 1 (
            echo   ERROR: Failed to install uv. Check your internet connection and try again.
            pause
            exit /b 1
        )
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
        set "PATH=%USERPROFILE%\.local\bin;!PATH!"
        echo   uv installed successfully.
    )
) else (
    echo   uv already installed:
    uv --version
)
echo.

rem ------------------------------------------------------------------
rem  5. Install Python and project dependencies
rem ------------------------------------------------------------------
echo [5/6] Installing Python 3.13 and project dependencies...

pushd "!APP_DIR!"
"!UV!" python install 3.13
if errorlevel 1 (
    echo   ERROR: Failed to install Python 3.13.
    popd
    pause
    exit /b 1
)
"!UV!" sync
if errorlevel 1 (
    echo   ERROR: uv sync failed. Check the errors above.
    popd
    pause
    exit /b 1
)
popd
echo.

rem ------------------------------------------------------------------
rem  6. Setup config and storage
rem ------------------------------------------------------------------
echo [6/6] Setting up config and storage...

if not exist "!APP_DIR!\config\config.yaml" (
    echo   Creating config.yaml from template...
    copy "!APP_DIR!\config\config_template.yaml" "!APP_DIR!\config\config.yaml" >nul
    echo   Remember to edit config\config.yaml with your LLM settings^^!
) else (
    echo   config.yaml already exists -- skipped.
)

if not exist "!APP_DIR!\storage" (
    mkdir "!APP_DIR!\storage"
    echo   Created storage directory.
) else (
    echo   storage directory already exists -- skipped.
)
echo.

echo   ========================================
echo     Setup complete^^!
echo     App folder: !APP_DIR_DISPLAY!
echo     Run start_procoo_qt.bat from that folder.
echo   ========================================
echo.
pause
