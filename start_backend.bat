@echo off
title TRADESWITHMK XAU INTEL BOT — Backend
color 0A

echo ============================================
echo  TRADESWITHMK XAU INTEL BOT
echo  Starting Python/FastAPI Backend
echo ============================================
echo.

cd /d "%~dp0backend"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [WARNING] .env not found — copying from .env.example
    copy .env.example .env
    echo [ACTION REQUIRED] Edit backend\.env with your API keys before trading!
    echo.
)

:: Create dirs
if not exist "logs"  mkdir logs
if not exist "data"  mkdir data

:: Install deps if needed
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo [INFO] Starting backend on http://127.0.0.1:8000
echo [INFO] API docs: http://127.0.0.1:8000/docs
echo [INFO] Press CTRL+C to stop
echo.

python main.py

pause
