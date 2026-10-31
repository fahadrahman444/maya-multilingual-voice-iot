# MAYA: Hardware & Software Component Specification

This document provides the complete hardware, pinout, server specifications, and software dependencies for **MAYA** (Alternative 2: ESP32-S3 Edge + FastAPI Gateway Server + Modular AI Pipeline).

---

## 1. Edge Hardware Bill of Materials (BOM)

| # | Component | Description & Role | Quantity | Est. Budget (BDT) |
|---|---|---|:---:|:---:|
| 1 | **ESP32-S3 N16R8** | Dual-core Xtensa LX7, 16MB Flash, 8MB Octal PSRAM. Manages $I^2S$ audio streaming, Wi-Fi WebSocket client, and GPIO relay control. | 1 | ৳800–1,000 |
| 2 | **INMP441 MEMS Microphone** | Omnidirectional digital microphone with $I^2S$ interface for crisp voice capture. | 1 | ৳200–330 |
| 3 | **MAX98357A I²S Amplifier** | 3.2W Class-D mono digital-to-analog amplifier breakout. Converts digital audio stream to speaker output. | 1 | ৳180–300 |
| 4 | **4 Ω, 3 W Speaker** | High-efficiency mini speaker for clear Bangla/English voice feedback. | 1 | ৳100–200 |
| 5 | **5 V 1-Channel Relay Module** | Optocoupled relay for switching smart home loads (lamp/fan). Active LOW/HIGH 3.3V logic compatible. | 1 | ৳80–150 |
| 6 | **Regulated 5 V, 3 A Power Supply** | Micro-USB / Type-C or DC power supply providing stable power to ESP32, amp, and relay. | 1 | ৳300–450 |
| 7 | **Prototyping Accessories** | Mini breadboard, tactile button (manual test/fallback), jumper wires (M-M, M-F). | 1 set | ৳150–250 |
| **Total** | | **Complete Hardware Prototype Budget** | | **৳1,810 – ৳2,680** |

---

## 2. ESP32-S3 Hardware Pinout Mapping

Below is the recommended GPIO allocation for the ESP32-S3 N16R8 to avoid strapping pins and internal PSRAM conflicts:

### A. INMP441 I²S Digital Microphone (Input)
| INMP441 Pin | ESP32-S3 GPIO | Function |
|---|---|---|
| **VDD** | 3.3V | Power (Do NOT connect to 5V) |
| **GND** | GND | Ground |
| **SD** (Serial Data) | GPIO 4 | $I^2S$ Data In (DIN) |
| **WS** (Word Select / L/R Clock) | GPIO 5 | $I^2S$ Left/Right Clock (LRCK) |
| **SCK** (Serial Clock) | GPIO 6 | $I^2S$ Bit Clock (BCLK) |
| **L/R** | GND | Left channel select (tied to GND) |

### B. MAX98357A I²S Class-D Amplifier (Output)
| MAX98357A Pin | ESP32-S3 GPIO / Power | Function |
|---|---|---|
| **VIN** | 5V (or VBUS) | 5V Power for full 3W output |
| **GND** | GND | Common Ground |
| **DIN** (Data In) | GPIO 7 | $I^2S$ Data Out (DOUT) |
| **BCLK** (Bit Clock) | GPIO 15 | $I^2S$ Bit Clock |
| **LRC** (Left/Right Clock) | GPIO 16 | $I^2S$ Word Select |
| **SD_MODE** | Unconnected / 100k to 3.3V | Defaults to mono $(L+R)/2$ |
| **GAIN** | GND | 9 dB default gain (or open for 12 dB) |

### C. Actuators & Controls
| Component Pin | ESP32-S3 GPIO | Function |
|---|---|---|
| **Relay Signal (IN)** | GPIO 10 | Digital output (Active LOW/HIGH) |
| **Relay VCC** | 5V | Relay coil power |
| **Relay GND** | GND | Common Ground |
| **Manual Fallback / Config Button (Optional)** | GPIO 11 | Internal pull-up to GND (Active LOW manual override) |
| **Status Indicator LED** | GPIO 12 | Visual feedback (Wake / Listening / Thinking / Speaking) |

---

## 3. Server Specifications & Modular Software Pipeline

### A. Server Environment
* **Platform:** Windows 10/11, macOS, Linux (Debian 12 / Ubuntu 22.04 LTS).
* **Runtime:** Python 3.10+ (tested on Python 3.10.11).
* **Architecture:** Hybrid Cloud-Accelerated Edge. STT and LLM run via high-speed cloud endpoints (~400ms), while VAD, Unicode normalization, telemetry, and audio I/O run locally on the device with minimal CPU (<2%) and low memory (<100MB).

### B. Core Python Pipeline Dependencies
* **FastAPI & Networking:** `fastapi`, `uvicorn[standard]`, `websockets`, `python-dotenv`, `pydantic-settings`
* **Speech-to-Text (STT):** `groq` (`whisper-large-v3` with dynamic vocabulary biasing & automatic language detection)
* **Voice Activity Detection & Endpointing:** `webrtcvad` (450ms Siri-grade endpointing with RMS energy thresholding)
* **Barge-In Acoustic Monitoring:** `sounddevice.RawStream` full-duplex simultaneous mic-read/speaker-write (<50ms playback cut)
* **Bangla Normalization Engine:** `bnunicodenormalizer` token-level normalizer + `unicodedata.normalize('NFC')`
* **Dual-Brain Cognitive Engine:**
  * Primary: `google-genai` (`gemini-3.5-flash-lite`)
  * Secondary: `groq` (`openai/gpt-oss-120b`)
  * Sliding-window circuit breaker with mid-stream failover
  * Hoisted sentence boundary regex with buffer-level decimal protection and 400ms timeout flush
* **Speech Synthesis (TTS) & Prosody:**
  * Engine: `edge-tts` (`bn-BD-NabanitaNeural` & `en-US-AvaNeural`)
  * Decoupled prosody parameters: Voice Pace (`0.8–1.2×`) and Expressivity (`low`, `medium`, `high`)
  * Dynamic phonetic lexicon (`apply_pronunciation_lexicon`) and ASCII-to-Bengali numeral conversion (`BANGLA_DIGITS`)
  * Markdown stripping (`strip_markdown_for_speech`) before audio synthesis
* **Tiered Memory Store:** Native atomic JSON store with contradiction resolution, audit history, and 800-character budget cap (`server/app/pipeline/memory.py`)
* **Continuous Correction Flywheel:** Thread-safe JSONL log (`server/data/correction_flywheel.jsonl`)
* **Zero-Blocking Telemetry:** `TurnTrace` queue with 50MB rolling file rotation (`server/data/traces.jsonl`) and real-time SLO dashboard (`server/app/dashboard.py`)
* **Crisis Safety Guardrail:** Deterministic regex & keyword engine routing to *Kaan Pete Roi* helpline (`server/app/pipeline/safety.py`)
