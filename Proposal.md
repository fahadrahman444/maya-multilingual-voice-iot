# Capstone Project Proposal

**Department of Computer Science and Engineering (CSE)**  
**University of Information Technology and Sciences (UITS)**

---

# Smart Bangla AI Voice Assistant & IoT Controller for Mental Wellness and Ambient Automation [MAYA]

### Capstone Project Proposal

**Supervisor:**  
Dr. Umma Khatuna Jannat  

**Submitted by:**

| Name | Student ID |
|---|---|
| Rion Ahmed | 0432320005101066 |
| Shafayat Hossain Shafin | 0432320005101088 |
| Zannatul Nayem | 0432320005101063 |
| Fahad Rahman | 0432320005101071 |

---

## 1. Introduction

Commercial voice assistants such as Apple Siri, Amazon Alexa, and Google Assistant have transformed human-computer interaction across the globe. However, these platforms predominantly cater to English and other high-resource Western languages, offering negligible or severely limited comprehension of spoken **Bangla**—the native language of over 250 million people worldwide. In Bangladesh, this linguistic divide disproportionately isolates the elderly, individuals with low digital literacy, and those residing in non-urban communities.

Simultaneously, contemporary society faces a rapidly escalating mental health crisis characterized by widespread loneliness, stress, and clinical depression. In Bangladesh, mental healthcare remains burdened by social stigma, an acute shortage of licensed counselors, and financial barriers. Many struggling individuals find it difficult to articulate their emotional pain to family members or seek professional psychological help until acute crisis points occur.

This project proposes **MAYA**, an affordable, low-latency, IoT-enabled intelligent voice assistant designed specifically for Bangla speakers. Beyond answering general queries and controlling home appliances, MAYA incorporates an **empathetic companion and depression-rescue engine**. Built on an Edge–Gateway hybrid architecture utilizing the ESP32-S3 microcontroller and a modular Python backend, MAYA provides non-judgmental active listening, emotional de-escalation, distress detection, and immediate referral to verified emergency crisis hotlines (such as *Kaan Pete Roi*), while simultaneously providing voice-driven smart-home appliance control.

---

## 2. Problem Statement

Most existing commercial voice systems fail in the context of everyday Bangladeshi life due to several fundamental shortcomings:
1. **Language & Dialect Gap:** Mainstream assistants fail to parse standard conversational Bangla, regional phonetics, and colloquial code-mixed speech ("Banglish").
2. **Lack of Emotional Intelligence:** Conventional voice assistants operate as cold transactional command parsers; they cannot recognize sadness, chronic loneliness, or severe emotional distress.
3. **Mental Health Stigma and Accessibility:** Seeking therapy in Bangladesh carries social stigma and high monetary costs. Accessible, non-judgmental first-line emotional support is practically non-existent.
4. **Hardware Cost & Complexity:** Implementing edge AI on expensive single-board computers (like full-size computers or Raspberry Pi 5) escalates product costs beyond what ordinary households can afford.
5. **Smart Home Inaccessibility:** Modern smart-home setups require complex proprietary applications in English, excluding non-technical and non-English-speaking users from ambient home control.

---

## 3. Objectives

### General Objective
To design, implement, and evaluate an affordable, IoT-based Bangla AI voice assistant (**MAYA**) that combines natural conversational capabilities in spoken Bangla, empathetic mental health support and depression de-escalation, and hands-free smart-home automation.

### Specific Objectives
1. **Edge Hardware Interface:** Develop low-latency $I^2S$ digital audio capture and playback firmware on an affordable **ESP32-S3 N16R8** microcontroller using the INMP441 MEMS microphone and MAX98357A Class-D amplifier.
2. **Modular Streaming Gateway:** Engineer a robust Python (FastAPI) WebSocket gateway to coordinate real-time bidirectional audio streaming between edge hardware and cloud AI microservices.
3. **Bangla Speech Pipeline:** Integrate and optimize low-latency Speech-to-Text (STT) and neural Text-to-Speech (TTS) models tailored for standard Bangladeshi Bangla (`bn-BD`).
4. **Empathetic Companion & Depression Rescue Engine:** Formulate Cognitive Behavioral Therapy (CBT)-inspired conversational logic and a deterministic safety triage layer that detects crisis keywords, delivers supportive de-escalation, and provides emergency hotline contacts.
5. **IoT Smart-Home Automation:** Implement native LLM tool/function calling to trigger physical relays for controlling household loads (e.g., lighting and fans).
6. **Empirical Evaluation:** Benchmark speech recognition Word Error Rate (WER), emotional classification accuracy, end-to-end response latency, and IoT command reliability across diverse Bangla speakers.

---

## 4. Scope and Limitations

### In Scope
* Speech-to-text transcription in standard conversational Bangla and common mixed Bangla-English phrasing.
* Conversational reasoning across general topics (weather, time, explanations, daily conversations).
* Empathetic listening, sentiment analysis, and safety-screened suicide/depression crisis de-escalation.
* IoT appliance control through a 1-channel optocoupled relay module.
* Working physical prototype using the ESP32-S3, digital $I^2S$ audio hardware, and a local/cloud FastAPI companion server.

### Limitations & Out of Scope
* **Not a Medical Device:** MAYA serves as an empathetic companion and crisis triage tool; it does not diagnose psychiatric disorders or replace licensed clinical psychotherapy.
* **Network Requirement:** While edge appliance control operates locally, natural language understanding and neural speech synthesis require an active internet connection.
* **Regional Dialects:** The prototype targets standard spoken Bangla; highly diverged regional dialects (e.g., Chittagonian, Sylheti) are outside the primary training baseline.

---

## 5. System Architecture

MAYA adopts a **3-Tier Edge–Gateway–Cloud Hybrid Architecture** (Alternative 2) that decouples hardware I/O from heavy machine learning workloads:

```
┌────────────────────────────────────────────────────────┐
│                   TIER 1: EDGE NODE                    │
│                     (ESP32-S3)                         │
│  [INMP441 I²S Mic]  [MAX98357A Amp]  [5V Relay Module] │
│      [On-Chip ESP-SR Wake-Word & Manual Override]      │
└───────────────────────────┬────────────────────────────┘
                            │ Full-Duplex WebSocket
                            │ (Raw 16kHz PCM Audio & JSON)
                            ▼
┌────────────────────────────────────────────────────────┐
│                TIER 2: GATEWAY SERVER                  │
│                   (Python / FastAPI)                   │
│                                                        │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │ Audio Stream Buffer  │    │ Crisis Safety Engine │  │
│  └──────────────────────┘    └──────────────────────┘  │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │ Context & State Mem  │    │ IoT Tool Dispatcher  │  │
│  └──────────────────────┘    └──────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │ API Calls
                            ▼
┌────────────────────────────────────────────────────────┐
│                  TIER 3: CLOUD AI                      │
│                                                        │
│  • Bangla STT: Whisper / Google Cloud Speech           │
│  • LLM Engine: Google Gemini 2.0 / OpenAI API          │
│  • Bangla TTS: Neural Edge TTS (bn-BD Voices)          │
└────────────────────────────────────────────────────────┘
```

---

## 6. Key System Modules

| Module Name | Implementation Environment | Core Functionality |
|---|---|---|
| **Edge Audio & I/O Module** | ESP32-S3 (C++ / ESP-IDF) | Runs on-device ESP-SR WakeNet detection (*"Hey Maya"*), samples $I^2S$ audio at 16kHz, handles Wi-Fi socket streaming, outputs digital audio to amplifier, and actuates relay GPIOs. |
| **Gateway Router** | FastAPI / Python | Manages sessions, buffers incoming audio, executes VAD end-of-speech detection, controls turn-taking, and coordinates downstream AI services. |
| **Bangla Speech Pipeline** | Whisper & Edge-TTS | Converts spoken Bangla audio to text and synthesizes empathetic responses back into natural Bengali voice (`bn-BD`). |
| **Depression & Crisis Triage** | Python Regex & Classifier | Screens transcribed text for high-risk emotional markers. Enforces priority intervention protocols when self-harm is detected. |
| **Empathetic Reasoning Engine**| Gemini / GPT with Prompt Guard | Conducts conversational dialogue with warm, CBT-aligned active listening; invokes function calls for appliance commands. |
| **IoT Actuation Controller** | Python Gateway + ESP32 | Dispatches validated JSON hardware payloads (`{"cmd": "RELAY", "val": 0|1}`) to switch appliances. |

---

## 7. Hardware & Software Specifications

### A. Hardware Components
* **Microcontroller:** ESP32-S3 N16R8 (Xtensa 32-bit dual-core, 16 MB Flash, 8 MB PSRAM)
* **Audio Input:** INMP441 Omnidirectional MEMS digital microphone ($I^2S$)
* **Audio Output:** MAX98357A Mono Class-D audio amplifier ($I^2S$) + 4 Ω, 3 W speaker
* **Actuator:** 5 V 1-Channel optocoupled relay module
* **Controls & Power:** Voice command wake-up (ESP-SR) + tactile override button, breadboard, 5 V 3 A regulated power adapter

### B. Software Tools & Libraries
* **Embedded Development:** ESP-IDF / Arduino IDE, ESP-SR (WakeNet), FreeRTOS, ArduinoJson, WebSocketsClient
* **Backend Gateway:** Python 3.10+, FastAPI, Uvicorn, WebSockets, Asyncio, Silero-VAD
* **AI & NLP:** OpenAI Whisper / Groq API, Google Gemini API, Microsoft Edge-TTS (`edge-tts`)
* **Audio Processing:** NumPy, SciPy, PyDub

---

## 8. Methodology and Project Timeline

The project follows an iterative, staged engineering approach over a 12-week schedule:

| Weeks | Phase | Tasks & Deliverables |
|:---:|---|---|
| **1–2** | **Literature & Design** | Finalize architecture, assemble BOM, establish evaluation criteria, design API schemas. |
| **3–4** | **Hardware Audio Validation** | Wire ESP32-S3 to INMP441 and MAX98357A. Verify bidirectional $I^2S$ capture and playback. |
| **5–6** | **Gateway & Speech Pipeline** | Implement FastAPI WebSocket server. Integrate Bangla STT (Whisper) and Bangla TTS (Edge-TTS). |
| **7–8** | **Empathetic AI & Crisis Engine**| Develop CBT empathetic system prompts, emotion classification layer, and crisis hotline safety triggers. |
| **9–10** | **IoT Integration & Actuation** | Implement LLM tool calling and relay switching. Run integration tests on end-to-end user loops. |
| **11** | **Evaluation & Benchmarking** | Measure WER, sentiment classification accuracy, IoT success rate, and latency with multiple speakers. |
| **12** | **Final Report & Defense** | Compile thesis document, prepare demonstration rig, and conduct Capstone presentation. |

---

## 9. Testing and Evaluation Metrics

The system will be quantitatively evaluated using four primary benchmarks:

| Evaluation Metric | Target Benchmark | Verification Method |
|---|:---:|---|
| **STT Word Error Rate (WER)** | $\le 18\%$ | Tested against a recorded benchmark set of 100 common Bangla commands & emotional expressions. |
| **Crisis Detection Recall** | $\ge 95\%$ | Tested against standard suicidal and high-distress trigger phrase datasets to ensure zero critical misses. |
| **IoT Command Success Rate** | $\ge 95\%$ | Ratio of successfully executed relay toggles over 100 spoken smart-home commands. |
| **End-to-End Latency** | $\le 2.5\text{ seconds}$ | Time measured from speech completion (VAD silence trigger) to the initial audio byte played through the speaker. |
| **User Empathy Rating** | $\ge 4.2 / 5.0$ | Subjective Likert-scale feedback evaluated by test participants assessing conversational warmth and comfort. |

---

## 10. Risks, Ethics, and Mitigation Strategies

1. **Mental Health Safety:**
   * *Risk:* Erroneous advice or failure to recognize acute suicide risk.
   * *Mitigation:* Hardcoded deterministic keyword guardrails override the LLM whenever crisis phrases are uttered, immediately providing registered emergency contacts (**Kaan Pete Roi: 01779-554391**).
2. **Acoustic Feedback & Echo:**
   * *Risk:* The microphone re-capturing the assistant’s voice.
   * *Mitigation:* Firmware-level half-duplex audio management: software-muting the microphone during active speaker playback and utilizing server-side VAD filtering.
3. **Network Latency:**
   * *Risk:* Cloud API roundtrips causing noticeable conversational lag.
   * *Mitigation:* Utilizing high-throughput streaming WebSockets and ultra-fast inference APIs (Groq Whisper & Gemini Flash).
4. **Data Privacy:**
   * *Risk:* Accidental recording of private home conversations.
   * *Mitigation:* No audio is streamed over Wi-Fi during passive listening. Audio transmission is strictly activated upon local, on-device wake-word detection (*"Hey Maya"* / *"মায়া"*).

---

## 11. Expected Outcomes

* A fully functional physical prototype of **MAYA** built with the ESP32-S3 and breadboard peripherals.
* A low-latency conversational AI pipeline capable of empathetic dialogue in natural spoken Bangla.
* A robust safety triage mechanism providing active depression and emotional crisis de-escalation.
* Voice-controlled physical relay actuation for domestic smart-home loads.
* Comprehensive thesis report, dataset benchmarks, and reproducible open-source documentation.

---

## 12. Conclusion

**MAYA** bridges a critical intersection between embedded IoT systems, applied artificial intelligence, and public mental wellness in Bangladesh. By combining affordable microcontroller hardware with state-of-the-art conversational and empathetic speech intelligence, this project demonstrates that low-cost, high-impact technology can bring accessible voice automation and compassionate support to millions of native Bangla speakers.
