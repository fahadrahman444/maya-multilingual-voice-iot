# MAYA: Smart Bangla AI Voice Assistant & IoT Controller

**MAYA** is an IoT-based, emotionally intelligent voice assistant built for standard spoken Bangla and English. It bridges two vital domains:
1. **Mental Wellness & Empathetic Companion:** Active listening, sentiment-aware conversation, depression de-escalation, and crisis hotline referral.
2. **Smart Home Automation:** Natural voice-controlled actuation of physical home appliances via relays and IoT protocols.

---

## 1. Core Architecture (Alternative 2: Edge + Gateway Pipeline)

To achieve low latency, high Bangla accuracy, and safe mental health guardrails on accessible hardware, MAYA uses an **Edge–Gateway–Cloud Hybrid Architecture**:

```
[User speaks: "Hey Maya" / "মায়া"]
         │
         ▼
[ESP32-S3 Edge Node] ──(Wi-Fi WebSocket / Raw PCM)──► [FastAPI Gateway Server]
 (INMP441 Mic + MAX98357A Amp)                                │
 (1-Ch Relay + On-Chip Wake-Word)                              ├─► 1. Voice Activity Detection (VAD)
                                                               ├─► 2. Bangla STT (Whisper API)
                                                               ├─► 3. Emotion & Crisis Safety Engine
                                                               ├─► 4. Empathetic LLM (Gemini / GPT)
                                                               ├─► 5. Tool Dispatch (Relay GPIO Command)
                                                               └─► 6. Bangla Neural TTS (Edge TTS)
         ▲                                                             │
         │                                                             │
         └────────(WebSocket: Audio stream + Relay JSON)───────────────┘
```

* **The ESP32-S3 Edge Node:** Functions as the sensory endpoint and physical actuator. It captures audio from the INMP441 microphone over $I^2S$, drives the MAX98357A amplifier and speaker, and directly triggers the 5V relay module.
* **The FastAPI Gateway Server:** Runs on a PC or cloud server. It orchestrates real-time audio ingestion, speech transcription, emotion screening, LLM reasoning with tool calling, and speech synthesis.

---

## 2. The Three System Pillars

### Pillar A: Conversational General Intelligence (Bangla & English)
* Capable of natural, open-domain conversations in standard spoken Bangla, mixed Bangla-English (Banglish), and pure English.
* Capable of everyday queries: weather, general knowledge, time, storytelling, and advice.
* Retains conversational context across multi-turn interactions.

### Pillar B: Empathetic Companion & Depression Rescue
Mental health challenges and loneliness are often stigmatized or unaddressed. MAYA acts as a non-judgmental, warm presence:
* **Sentiment & Mood Screening:** Detects emotional tone (sadness, loneliness, anxiety, distress) from acoustic pauses and spoken text.
* **Empathetic Dialogue (CBT-inspired):** Offers comforting, validating, non-clinical supportive feedback using respectful Bangla honorifics (e.g., *"আমি বুঝতে পারছি আপনার সময়টা কঠিন যাচ্ছে..."*).
* **Crisis De-escalation & Safety Triage:** Contains a deterministic safety filter. If self-harm, suicidal thoughts, or extreme crisis keywords are detected:
  1. The assistant responds with calming de-escalation language.
  2. The assistant explicitly offers verified Bangladeshi mental health emergency contacts (e.g., **Kaan Pete Roi / কান পেতে রই**, National Mental Health Helpline).

### Pillar C: Smart Home Appliance Automation
* Supports intent-based tool calling.
* When the user issues an automation command (e.g., *"আলোটা জ্বালিয়ে দাও"* / *"Turn on the light"* or *"আমি ঘুমাতে যাচ্ছি, লাইট বন্ধ করো"* / *"I am going to sleep, turn off the light"*):
  1. The LLM extracts the action via structured function calling.
  2. The FastAPI server dispatches a lightweight JSON event to the ESP32: `{"action": "relay", "state": 0 | 1}`.
  3. The ESP32 switches the relay GPIO pin immediately.
  4. The assistant speaks back an empathetic spoken confirmation.

---

## 3. Hardware & Peripherals Overview

All physical edge tasks are executed on affordable, off-the-shelf components:
* **Controller:** ESP32-S3 N16R8 (16MB Flash, 8MB PSRAM, Wi-Fi 4 + BLE 5).
* **Audio Input:** INMP441 digital MEMS omnidirectional microphone ($I^2S$).
* **Audio Output:** MAX98357A Class-D amplifier breakout + 4 Ω, 3 W speaker ($I^2S$).
* **Appliance Control:** 5 V 1-Channel optocoupled relay module.
* **Interaction:** Hands-free Voice Command Wake-Up (ESP-SR WakeNet detecting *"Hey Maya"* / *"মায়া"*) with server-side VAD and software half-duplex mic muting during speaker playback. (Tactile button on breadboard retained as optional manual override).

For exact wiring pinouts and component specifications, refer to [Component.md](file:///home/fahad/Desktop/MAYA/Component.md).

---

## 4. Software Stack

| Component | Technology / Library | Role |
|---|---|---|
| **Edge Firmware** | C++ / Arduino Framework / ESP-IDF | $I^2S$ audio driver, ESP-SR WakeNet (Wake-Word), Wi-Fi WebSocket client, GPIO control |
| **Gateway Server** | Python 3.10+, FastAPI, Uvicorn | Full-duplex WebSocket router and pipeline coordinator |
| **Voice Activity Detection** | Silero-VAD / WebRTC VAD | Real-time speech boundary and end-of-speech (EOS) detection |
| **Speech-to-Text (STT)**| Groq Whisper API / Faster-Whisper | Low-latency, accurate Bangla speech transcription |
| **Cognitive Engine** | Google Gemini 2.0 Flash / OpenAI API | Empathetic reasoning, context memory, and IoT tool calling |
| **Crisis Filter** | Python Regex + Sentiment Classifier | Zero-latency emergency safety interceptor |
| **Text-to-Speech (TTS)**| Microsoft Edge TTS (`bn-BD-PradeepNeural` / `bn-BD-NabanitaNeural`) | High-fidelity, natural Bangla voice generation |

---

## 5. Development Roadmap

1. **Hardware Validation:** Wire INMP441, MAX98357A, speaker, and relay to ESP32-S3. Verify $I^2S$ audio loopback and relay switching.
2. **WebSocket Client/Server Bridge:** Implement the ESP32 streaming client and the FastAPI WebSocket server for bidirectional audio chunks.
3. **Bangla Speech Pipeline:** Connect Whisper STT and Edge TTS to the streaming server.
4. **Empathetic & Crisis Intelligence:** Build prompt templates, emotion classification layers, and crisis safety triage rules.
5. **IoT Tool Calling Integration:** Implement function schemas so the LLM controls the physical relay.
6. **Testing & Evaluation:** Collect benchmark data (WER, response latency, emotion accuracy) for the Capstone thesis defense.
