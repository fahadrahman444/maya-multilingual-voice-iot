@echo off
title "MAYA - Gemini Live Voice Assistant and IoT Prototype"
cd /d "%~dp0"

echo ========================================================
echo  🌸 Launching MAYA: Gemini Live Voice Assistant (Laptop)
echo ========================================================
echo.

set PYTHONPATH=%~dp0

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0server\run_gemini_live.py"
) else (
    python "%~dp0server\run_gemini_live.py"
)

pause
