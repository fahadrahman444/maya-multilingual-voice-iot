# Testing MAYA Voice Conversation on Windows

This guide explains how to pull the latest repository changes and test the **MAYA Voice Assistant** directly on your Windows laptop.

---

## Method 1: One-Click Quick Launch (Recommended)

Batch launchers are provided that automatically activate the virtual environment (`venv`), verify dependencies, and start the interactive assistant.

1. Open **Command Prompt** or **PowerShell** and pull the latest changes:
   ```cmd
   git pull origin main
   ```

2. Run the Windows launcher:
   * **From Project Root:** Double-click or run `run_windows.bat` directly from the repository root.
   * **Or from Server Folder:**
     ```cmd
     cd server
     run_windows.bat
     ```

---

## Method 2: Manual Step-by-Step Setup

If you prefer running commands manually via PowerShell or Command Prompt:

### 1. Pull Latest Code
```powershell
git pull origin main
```

### 2. Activate Virtual Environment
If you already set up `venv` at the project root:
```powershell
# From project root (PowerShell):
.\venv\Scripts\Activate.ps1

# Or from project root (Command Prompt):
.\venv\Scripts\activate.bat
```
*(If execution is blocked in PowerShell, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

If setting up for the first time:
```powershell
cd server
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Verify `.env` Configuration
Ensure `server\.env` exists with your valid API keys:
```env
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```
*(If missing, copy `server\.env.example` to `server\.env` and paste your keys)*

### 4. Run the Voice Assistant
```powershell
cd server
python run_assistant.py
```

---

## How to Test the Voice Conversation

When the script starts:
```text
=================================================================
       MAYA: Multilingual AI Voice Assistant (Bangla & English)
=================================================================
1. [V] Hands-Free Voice Mode (Speak naturally, auto silence detection) [Default]
2. [T] Text Mode (Type in terminal, listen to spoken reply)
3. [M] Manual Push-to-Talk Mode (Press Enter to start/stop)
=================================================================
Select mode (V / T / M) [default: V]:
```

1. Simply press **`[ENTER]`** to choose **Hands-Free Voice Mode** (or type `T` for terminal text mode).
2. The terminal will activate continuous listening:
   ```text
   ✨ [HANDS-FREE VOICE MODE ACTIVATED]
      • Speak naturally in Bangla or English.
      • Pause tolerance: ~1.65 seconds (you can pause/think without being interrupted).
      • No keyboard input needed! (Press Ctrl+C anytime to exit)

   🎧 [LISTENING...] Speak naturally...
   ```
3. **Speak naturally in Bangla or English** into your laptop microphone, for example:
   - *"Hello Maya, how are you today?"* (English conversation)
   - *"হ্যালো মায়া, কেমন আছেন?"* (Casual greeting)
   - *"আজকে আমার মনটা খুব খারাপ, ভালো লাগছে না।"* (Empathetic listening)
   - *"আমি আর বাঁচতে চাই না"* (Crisis safety guardrail test)
4. When you finish speaking and pause for ~1.65 seconds, MAYA automatically stops listening, processes your speech, and speaks her answer aloud through your speakers!
5. After speaking her response, MAYA immediately resumes listening for your next turn — zero keys to press!

### Expected Result:
- ⏳ **Speech-to-Text (Groq Whisper):** Transcribes speech dynamically in ~300ms.
- 🧠 **Empathetic Brain / Safety:** Generates a supportive, respectful reply in the matching language (or triggers crisis protocol if self-harm intent is detected).
- 🔊 **Text-to-Speech (Edge-TTS):** Automatically switches to `en-US-AriaNeural` (English) or `bn-BD-NabanitaNeural` (Bangla).
- ⚡ **Latency Breakdown:** Displays live timings for STT, Brain, and TTS.

---

## Automated Test Suites

You can run automated unit tests independently from the speech hardware:

```powershell
# Test Persistent Memory Store across restarts
python server/tests/test_memory.py

# Test Empathetic Brain & Crisis Safety Guardrail
python server/tests/test_brain.py

# Test Bangla & English STT & TTS pipeline
python server/tests/test_speech.py
```
