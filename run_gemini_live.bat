@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title MAYA - Gemini Live Voice Assistant
cd /d "%~dp0"
call ".\venv\Scripts\activate.bat"
python "server\run_gemini_live.py"
pause
