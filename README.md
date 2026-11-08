# 🌸 MAYA: Siri-Grade Voice AI Companion & IoT Tabletop Robot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini Live](https://img.shields.io/badge/Google-Gemini%203.8%20Live-blue.svg)](https://ai.google.dev/)
[![Groq Whisper](https://img.shields.io/badge/Groq-Whisper%20Large%20V3-orange.svg)](https://groq.com/)
[![Edge-TTS](https://img.shields.io/badge/Microsoft%20Edge-TTS-blue.svg)](https://github.com/rany2/edge-tts)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MAYA** is an emotionally intelligent voice assistant and physical tabletop robot engineered for natural, low-latency conversational interaction and smart home IoT automation.

---

## 🗂️ Project Directory Structure

```text
MAYA/
├── run_gemini_live.bat          # 🚀 1-Click Launch: Gemini Live Native S2S Mode
├── run_cascaded.bat             # 🎙️ 1-Click Launch: Cascaded Whisper + Edge-TTS Mode
├── run.bat                      # Backward-compatible launcher
└── maya-multilingual-voice-iot/
    ├── docs/                    # 📚 Project Documentation & Schematics
    │   ├── architecture/
    │   │   ├── ESP32_IoT_Hardware_Architecture.md  # Full pinouts, wiring & protocol
    │   │   ├── GeminiLive_Implementation_Plan.md   # Gemini Live integration design
    │   │   ├── Workflow.md                         # Turn-taking sequence workflows
    │   │   ├── WorkingProcess.md                   # Engineering process documentation
    │   │   ├── Component.md                        # Hardware BOM & pin assignments
    │   │   └── context.md                          # Multilingual & empathy context
    │   ├── proposal/
    │   │   ├── Proposal.md                         # Capstone thesis proposal
    │   │   ├── Proposal.pdf
    │   │   └── uits_logo.png
    │   └── testing/
    │       └── TESTING_WINDOWS.md                  # Windows audio calibration guide
    ├── firmware/                # ⚡ Microcontroller Firmware
    │   └── esp32_s3_robot/
    │       └── esp32_s3_robot.ino                  # Complete FreeRTOS ESP32-S3 sketch
    ├── server/                  # 🧠 Gateway Server & AI Engines
    │   ├── app/
    │   │   ├── pipeline/                           # Brain, STT, TTS, Memory, Safety
    │   │   ├── config.py                           # Central configuration & keys
    │   │   └── dashboard.py                        # Telemetry & SLO dashboard
    │   ├── data/                                   # User memory & turn traces
    │   ├── tests/                                  # Pipeline unit & integration tests
    │   ├── run_gemini_live.py                      # Gemini Live Laptop Prototype
    │   ├── run_assistant.py                        # Cascaded Engine Runner
    │   ├── requirements.txt
    │   └── .env
    ├── run_gemini_live.bat
    └── run_cascaded.bat
```

---

## ✨ Operating Modes

### 1. 🚀 Native Speech-to-Speech Mode (Gemini Live API)
* **Model:** Google Gemini 3.8 Live (`gemini-3.8-live`).
* **Latency:** Sub-400ms end-to-end voice loop.
* **Full-Duplex:** Speak and listen simultaneously with native server-side interruption.
* **Simultaneous IoT Tools:** Controls appliances (5V relay), head gestures (MG90S servos), and OLED eye expressions concurrently while speaking.
* **Launch:**
  ```powershell
  .\run_gemini_live.bat
  ```

### 2. 🎙️ Cascaded Engine Mode (Whisper + Dual-Brain + Edge-TTS)
* **STT:** Groq Whisper Large V3 (`~150-250ms`).
* **Cognitive Engine:** Gemini 3.5 Flash-Lite with automatic failover to Groq Qwen.
* **TTS:** Microsoft Edge-TTS (`en-US-AvaNeural` / `bn-BD-PradeepNeural`).
* **Launch:**
  ```powershell
  .\run_cascaded.bat
  ```

---

## 🤖 Hardware & Physical Robot Overview

MAYA features an interactive physical tabletop robot edge node powered by the **ESP32-S3 (N16R8)**:
* **Audio Input:** INMP441 MEMS Omnidirectional Microphone ($I^2S$).
* **Audio Output:** MAX98357A 3.2W Class-D Amp + 4Ω 3W Speaker ($I^2S$).
* **2-DOF Robotic Neck:** 2× MG90S metal-gear micro servos (Pan & Tilt).
* **Expressive OLED Eyes:** 0.96" I²C SSD1306 monochrome OLED.
* **Appliance Control:** 5V 1-Channel optocoupled relay module.

For complete schematics, pin mappings, and star-grounding wiring instructions, refer to **[docs/architecture/ESP32_IoT_Hardware_Architecture.md](docs/architecture/ESP32_IoT_Hardware_Architecture.md)**.

---

## 🚀 Quick Setup & Configuration

1. **Activate virtual environment:**
   ```powershell
   cd maya-multilingual-voice-iot
   .\venv\Scripts\Activate.ps1
   pip install -r server/requirements.txt
   ```

2. **Configure API Keys in `server/.env`:**
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Run Regression Tests:**
   ```powershell
   pytest server/tests
   ```
