@echo off
REM YouTube to MP4 Downloader Launcher
REM This batch file launches the MP4.py Python script with automatic venv setup

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

REM Check if venv folder exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
)

REM Activate the virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install requirements
echo Installing required packages...
pip install -q --upgrade pip
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install requirements
    pause
    exit /b 1
)
echo Packages installed successfully

REM Run the MP4.py script
echo.
echo Starting YouTube to MP4 Downloader...
echo.
python MP4.py

REM Deactivate venv
call venv\Scripts\deactivate.bat

exit /b %errorlevel%
