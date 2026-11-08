@echo off
title MAYA - Cascaded Voice Assistant (Groq Whisper + Edge-TTS)
cd /d "%~dp0"

echo ========================================================
echo  🌸 Launching MAYA: Cascaded Voice Assistant (Groq+TTS)
echo ========================================================
echo.

set PYTHONPATH=%cd%

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "server\run_assistant.py" %*
) else (
    python "server\run_assistant.py" %*
)

pause
