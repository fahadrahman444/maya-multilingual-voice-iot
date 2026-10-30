@echo off
chcp 65001 >nul
echo ========================================================
echo        MAYA Voice Assistant - Windows Launcher
echo ========================================================
cd /d "%~dp0"

IF NOT EXIST "venv" (
    echo [INFO] Virtual environment not found. Creating 'venv'...
    python -m venv venv
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment. Ensure Python 3.10+ is installed and on your PATH.
        pause
        exit /b %ERRORLEVEL%
    )
    echo [INFO] Installing required packages...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b %ERRORLEVEL%
    )
) ELSE (
    call venv\Scripts\activate.bat
)

IF NOT EXIST ".env" (
    echo [WARNING] .env file not found in server directory!
    IF EXIST ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
        echo [ACTION REQUIRED] Please edit server\.env and add your GROQ_API_KEY and GEMINI_API_KEY.
        pause
        exit /b 1
    )
)

echo.
echo [INFO] Starting MAYA Voice Assistant...
python run_assistant.py
pause
