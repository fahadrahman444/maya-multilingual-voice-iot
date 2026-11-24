# 🌸 MAYA: Siri-Grade Voice AI Companion & IoT Tabletop Robot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini Live](https://img.shields.io/badge/Google-Gemini%203.8%20Live-blue.svg)](https://ai.google.dev/)
[![Groq Whisper](https://img.shields.io/badge/Groq-Whisper%20Large%20V3-orange.svg)](https://groq.com/)
[![Edge-TTS](https://img.shields.io/badge/Microsoft%20Edge-TTS-blue.svg)](https://github.com/rany2/edge-tts)
[![Region](https://img.shields.io/badge/Region-Bangladesh%20(BST%20UTC%2B6)-green.svg)](https://en.wikipedia.org/wiki/Bangladesh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MAYA (মায়া)** is an emotionally intelligent voice assistant and physical tabletop robot proudly rooted in Bangladesh, engineered for natural low-latency conversational interaction, smart home IoT automation, and empathetic mental wellness support.

---

## 🗂️ Project Directory Structure

```text
MAYA/
├── run_gemini_live.bat          # 🚀 1-Click Launch: Gemini Live Native S2S Mode
├── run_cascaded.bat             # 🎙️ 1-Click Launch: Cascaded Whisper + Edge-TTS Mode
├── test_mic_record_play.py      # 🎤 Live audio calibration and VU recording test
├── run.bat                      # Backward-compatible launcher
└── maya-multilingual-voice-iot/
    ├── docs/                    # 📚 Project Documentation & Schematics
    │   ├── HARDWARE_CONNECTIONS.md             # Live hardware wiring tracker & verification log
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
    │   │   ├── pipeline/                           # Brain, STT, TTS, Memory, Safety, ESP32 Bridge
    │   │   ├── config.py                           # Central configuration & keys
    │   │   └── dashboard.py                        # Telemetry & SLO dashboard
    │   ├── data/                                   # User memory & turn traces
    │   ├── tests/                                  # Pipeline unit & regression test suite
    │   ├── run_gemini_live.py                      # Gemini Live Production Assistant Runner
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
* **Full-Duplex Turn Protection:** Smooth conversational turn shielding (comfort silence masking during speech) + 400ms acoustic echo hangover, eliminating self-interruption from speaker playback.
* **Acoustic Pre-Amplification:** +1.8× digital gain boost with dynamic noise-floor gating (110 RMS) calibrated for laptop internal microphones (Conexant ISST).
* **Live Visual Telemetry:** Real-time console ASCII VU meter (`🎤 [VOICE LIVE] |██████      |`) and live user speech transcription (`👤 You (hearing): ...`).
* **Simultaneous IoT Tools:** Controls appliances (5V relay), head gestures (MG90S servos), and OLED eye expressions concurrently while speaking.
* **Launch:**
  ```powershell
  .\run_gemini_live.bat
  ```

### 2. 🎙️ Cascaded Engine Mode (Whisper + Dual-Brain + Edge-TTS)
* **STT:** Groq Whisper Large V3 (`~150-250ms`) with dynamic gain normalization and hallucination suppression.
* **Cognitive Engine:** Gemini 3.5 Flash-Lite with automatic failover and persistent SQLite memory.
* **TTS:** Microsoft Edge-TTS (`en-US-AvaNeural` / `bn-BD-PradeepNeural`).
* **Launch:**
  ```powershell
  .\run_cascaded.bat
  ```

---

## 🇧🇩 Bangladeshi Regionalization & Core Capabilities

MAYA is deeply culturally attuned and regionally grounded in **Bangladesh**:
* **Language Fluency:** Seamlessly speaks standard Shuddho Bangla (বাংলা), Banglish, English, and Hindi. Employs language stickiness to stay in your preferred language.
* **Local Knowledge:** Converses fluently about Bangladeshi geography (Dhaka, Chittagong, Sylhet, Padma Bridge, Metro Rail), cultural festivals (Pohela Boishakh, Ekushey February, Eid), universities (UITS, DU, BUET), and national sports (*The Tigers*).
* **Time, Currency & Units:** Defaults to Bangladesh Standard Time (BST, UTC+6), Bangladeshi Taka (BDT / ৳), and Celsius (°C).
* **Live Weather Engine:** Instant live weather reports and temperature queries via integrated `wttr.in` parsing for Dhaka and nationwide cities.
* **Interactive Culinary Assistant:** Explains step-by-step recipes for Bangladeshi cuisine (Shorshe Ilish, Kacchi Biryani, Bhuna Khichuri, Dim Bhuna) and features **Pantry Cooking** (suggests meals using whatever 3–4 items you have in your fridge).
* **Empathetic Wellness & Crisis Triage:** Active listening, CBT-informed vent mode, panic grounding exercises, and zero-latency routing to verified Bangladeshi emergency lifelines:
  * **Emergency Services:** `999`
  * **Kaan Pete Roi (Emotional Support & Suicide Prevention):** `01779-554391` / `01779-554392`
  * **National Mental Health Helpline:** `16122`
  * **Women & Children Support:** `109`

---

## 🤖 Hardware & Physical Robot Overview

MAYA features an interactive physical tabletop robot edge node powered by the **ESP32-S3 (N16R8)**:
* **Audio Input:** INMP441 MEMS Omnidirectional Microphone ($I^2S$ on `IO4`, `IO5`, `IO6`) — verified and operational.
* **Audio Output:** MAX98357A 3.2W Class-D Amp + 4Ω 3W Speaker ($I^2S$ on `IO7`, `IO15`, `IO16`).
* **2-DOF Robotic Neck:** 2× MG90S metal-gear micro servos (Pan on `IO13` & Tilt on `IO14`).
* **Expressive OLED Eyes:** 0.96" I²C SSD1306 monochrome OLED (`IO8`, `IO9`).
* **Appliance Control:** 5V 1-Channel optocoupled relay module (`IO21`).
* **Hardware Bridge:** High-speed USB serial bridge with automatic graceful fallback to the laptop microphone and speakers when the microcontroller is unplugged.

For complete schematics, pin mappings, and star-grounding wiring instructions, refer to **[docs/architecture/ESP32_IoT_Hardware_Architecture.md](docs/architecture/ESP32_IoT_Hardware_Architecture.md)** and **[docs/HARDWARE_CONNECTIONS.md](docs/HARDWARE_CONNECTIONS.md)**.

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
