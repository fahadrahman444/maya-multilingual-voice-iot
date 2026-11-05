@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
call "venv\Scripts\activate.bat"
python server/run_assistant.py %*
