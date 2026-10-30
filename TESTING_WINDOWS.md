# Testing MAYA Voice Conversation on Windows

This guide explains how to pull the latest repository changes and test the **MAYA Voice Assistant** directly on your Windows laptop.

---

## Method 1: One-Click Quick Launch (Recommended)

A batch script is provided that automatically handles activating the virtual environment, checking dependencies, and launching the interactive assistant.

1. Open **Command Prompt** or **PowerShell** and pull the latest changes:
   ```cmd
   git pull origin main
   ```

2. Open the `server` folder:
   ```cmd
   cd server
   ```

3. Run the Windows launcher:
   ```cmd
   run_windows.bat
   ```
   *(Alternatively, you can navigate to `server` in Windows File Explorer and double-click `run_windows.bat`)*

---

## Method 2: Manual Step-by-Step Setup

If you prefer running commands manually via PowerShell or Command Prompt:

### 1. Pull Latest Code
```powershell
git pull origin main
cd server
```

### 2. Set Up Virtual Environment (First Time Only)
```powershell
# Create venv
python -m venv venv

# Activate venv
# On PowerShell:
.\venv\Scripts\Activate.ps1
# (If blocked by execution policy, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

# Or on Command Prompt (cmd.exe):
.\venv\Scripts\activate.bat

# Install dependencies (sounddevice on Windows bundles PortAudio automatically)
pip install -r requirements.txt
```

### 3. Verify `.env` Configuration
Ensure `server\.env` exists with your valid API keys:
```env
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```
*(If missing, copy `.env.example` to `.env` and paste your keys)*

### 4. Run the Voice Assistant
```powershell
python run_assistant.py
```

---

## How to Test the Voice Conversation

When the script starts:
```text
=================================================================
       MAYA: Multilingual Bangla AI Voice Assistant
=================================================================
1. [V] Voice Mode (Speak into your laptop microphone)
2. [T] Text Mode (Type in terminal, listen to spoken reply)
=================================================================
Select mode (V for Voice / T for Text) [default: V]:
```

1. Press **`[ENTER]`** to choose Voice Mode.
2. The terminal will display:
   ```text
   👉 Press [ENTER] to start speaking (or Ctrl+C to quit)...
   ```
   Press **`[ENTER]`**.
3. **Speak in Bangla** into your laptop microphone, for example:
   - *"হ্যালো মায়া, কেমন আছো?"* (Casual greeting)
   - *"আজকে আমার মনটা খুব খারাপ, ভালো লাগছে না।"* (Empathetic listening)
   - *"আমি আর বাঁচতে চাই না"* (Crisis safety guardrail test)
4. Press **`[ENTER]`** again when you finish speaking.

### Expected Result:
- ⏳ **Speech-to-Text (Groq Whisper):** Transcribes your Bangla speech in ~300ms.
- 🧠 **Empathetic Brain / Safety:** Generates a supportive, respectful Bengali reply (or triggers crisis protocol if self-harm intent is detected).
- 🔊 **Text-to-Speech (Edge-TTS):** Speaks the Bangla reply aloud through your laptop speakers.
- ⚡ **Latency Breakdown:** Displays live timings for STT, Brain, and TTS.

---

## Automated Test Suites

You can also run automated unit tests directly from the `server` folder:

```powershell
# Test Bangla STT & TTS pipeline
python tests/test_speech.py

# Test Empathetic Brain & Crisis Safety Guardrail
python tests/test_brain.py
```
