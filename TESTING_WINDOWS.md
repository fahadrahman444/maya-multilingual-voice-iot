# Testing MAYA Voice Conversation on Windows

This guide explains how to test the **MAYA Voice Assistant** directly on your Windows laptop with full Siri-grade turn-taking, barge-in interruption, and telemetry monitoring.

---

## Method 1: One-Click Quick Launch (Recommended)

Batch launchers are provided that automatically verify dependencies, set environment policies, and start the interactive assistant.

1. Open **PowerShell** or **Command Prompt** and ensure you have the latest changes:
   ```cmd
   git pull origin main
   ```

2. Run the Windows launcher:
   * **From Project Root:** Double-click or execute `run_windows.bat` directly from the repository root.
   * **Or from the Server Folder:**
     ```cmd
     cd server
     run_windows.bat
     ```

---

## Method 2: Manual Step-by-Step Setup

If you prefer running commands manually via PowerShell or Command Prompt:

### 1. Activate Virtual Environment
If you already set up `venv` at the project root:
```powershell
# From project root (PowerShell):
.\venv\Scripts\Activate.ps1

# Or from project root (Command Prompt):
.\venv\Scripts\activate.bat
```
*(If script execution is blocked in PowerShell, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

If setting up for the first time:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
```

### 2. Verify `.env` Configuration
Ensure `server\.env` exists with your valid API keys:
```env
# Speech-to-Text (Groq Whisper Large V3) & Secondary Brain
GROQ_API_KEY=gsk_...

# Primary Empathetic Cognitive Brain (Gemini 3.5 Flash-Lite)
GEMINI_API_KEY=AIza...
```
*(If missing, copy `server\.env.example` to `server\.env` and paste your keys)*

### 3. Run the Voice Assistant
```powershell
python server/run_assistant.py
```

---

## How to Test the Voice Conversation

When the script starts:
```text
=================================================================
       MAYA: Multilingual AI Voice Assistant (Bangla & English)
       Mode: Siri-Grade Engine (Endpoint: 450ms, Barge-In: True)
=================================================================
1. [V] Hands-Free Voice Mode (Speak naturally, auto silence detection) [Default]
2. [T] Text Mode (Type in terminal, listen to spoken reply)
3. [M] Manual Push-to-Talk Mode (Press Enter to start/stop)
=================================================================
Select mode (V / T / M) [default: V]:
```

1. Press **`[ENTER]`** to choose **Hands-Free Voice Mode** (or type `T` for terminal text mode).
2. The terminal will activate continuous listening:
   ```text
   ✨ [HANDS-FREE VOICE MODE ACTIVATED]
      • Speak naturally in Bangla or English.
      • Siri-grade endpointing: ~450ms pause before assistant commits to answering.
      • Real-time barge-in: Speak while MAYA is talking to interrupt her immediately!
      • No keyboard input needed! (Press Ctrl+C anytime to exit)

   🎧 [LISTENING...] Speak naturally...
   ```
3. **Speak naturally in Bangla or English** into your microphone, for example:
   - *"Hello Maya, how are you today?"* (English casual turn)
   - *"হ্যালো মায়া, কেমন আছেন?"* (Bangla polite greeting)
   - *"ডেডলক কী এবং এর শর্তগুলো বলো"* (Bangla technical query)
   - *"It's Pizza Barg, not Pizza Berg"* (Terminology correction flywheel test)
   - *"আজকে আমার মনটা খুব খারাপ, বেঁচে থাকতে ইচ্ছে করছে না"* (Crisis safety guardrail test)
4. When you finish speaking and pause for **~450ms**, MAYA automatically stops listening, normalizes the Bengali Unicode transcript, streams the response chunk-by-chunk through the sentence boundary engine, and speaks aloud within **≤ 700ms**.
5. **Test Barge-In:** While MAYA is speaking through the speakers, speak aloud into your microphone. MAYA will cut playback within **< 50ms** and listen to you.

---

## Inspecting Telemetry & SLO Dashboard

MAYA records per-turn structured traces into a non-blocking JSONL sink with 50MB rotation.

View real-time SLO metrics, latency percentiles, and language breakdown:
```powershell
python -m server.app.dashboard
```

Example output:
```text
turns: 12
TTFA  p50=645.2 ms   p95=820.4 ms
fallback rate          0.00% (0/12)
silent truncation      0.00% (0/12)   <-- must be 0
crisis trigger rate    8.33% (1/12)
barge-in rate          8.33% (1/12)
language breakdown:
  • bn     : 6 turns (TTFA p50: 630.0 ms)
  • en     : 4 turns (TTFA p50: 660.5 ms)
  • mixed  : 2 turns (TTFA p50: 672.0 ms)
```

---

## Automated Test Suites

You can run automated test suites independently from the microphone:

```powershell
# 1. Run Comprehensive Regression Suite (19/19 Verified End-to-End Tests)
python server/tests/test_regression.py

# 2. Run Telemetry Sink & Memory Persistence Tests
pytest server/tests/test_telemetry.py server/tests/test_memory.py

# 3. Test Bilingual Speech Synthesis (TTS) & Transcription (STT)
python server/tests/test_speech.py
```
