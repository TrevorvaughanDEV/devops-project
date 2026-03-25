@echo off
REM DevOps Monitor - Local Development Start Script
REM Usage: start_dev.bat

echo.
echo ========================================
echo DevOps Monitor - Development Server
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

echo [OK] Python is installed

REM Check if virtual environment exists
if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo [INFO] Installing dependencies...
pip install -r requirements.txt

REM Run Flask app
echo.
echo ========================================
echo [OK] Starting Flask Development Server
echo ========================================
echo.
echo Visit: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py
