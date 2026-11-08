# MAYA: Hardware & Software Component Specification

This document provides the complete hardware, pinout, robotic gesture mechanics, server specifications, and software dependencies for **MAYA** (Alternative 2: ESP32-S3 Tabletop Robot Edge + FastAPI Gateway Server + Modular AI Pipeline).

---

## 1. Edge Hardware Bill of Materials (BOM) & Cost Breakdown

| Component | Description & Role | Unit Price (BDT) |
|---|---|:---:|
| **ESP32-S3 (N16R8)** | Dual-core Xtensa LX7, 16MB Flash, 8MB Octal PSRAM. Audio I²S streaming, Wi-Fi WebSockets, PWM servo control, I²C display. | 1,250 Tk |
| **ESP32-S3 GPIO Terminal Expansion Board** | Screw-terminal breakout shield specifically for ESP32-S3, locking wire connections securely against servo vibration. | 395 Tk |
| **INMP441 MEMS Microphone Module** | Omnidirectional digital microphone with $I^2S$ interface for crisp voice capture. | 730 Tk |
| **MAX98357A I2S Amplifier Module** | 3.2W Class-D mono digital-to-analog amplifier breakout for speaker driving. | 450 Tk |
| **1-Channel 5V Relay Module** | Optocoupled relay for switching smart home appliance loads (lamp/fan). | 80 Tk |
| **MG90S Servo Motors (2x)** | Metal-gear micro servos for 2-DOF robotic neck mechanism (Pan & Tilt). | 418 Tk (209 × 2) |
| **I2C OLED Display (0.96")** | 128×64 monochrome OLED for animated facial expressions (blinking, smiling, confused). | 395 Tk |
| **5V, 3A Power Supply Module/Adapter** | Regulated DC power supply for ESP32, amp, servos, and relay. | 470 Tk |
| **Misc Parts** | Tactile button, status LED, 470µF–1000µF capacitor, mini breadboard & jumper wires. | 250 Tk |
| **Total Estimated Cost** | **Complete Hardware Prototype Total** | **4,238 Tk** |

> [!TIP]
> **Pinout Compatibility Check:** Standard ESP-WROOM-32 boards often use 30-pin or 38-pin headers, while **ESP32-S3 N16R8** dev boards commonly use **38-pin or 44-pin** layouts. Make sure the screw terminal adapter purchased matches the exact pin count and row-width of your specific ESP32-S3 N16R8 board.

---

## 2. ESP32-S3 Hardware Pinout Mapping

Below is the recommended GPIO allocation for the ESP32-S3 N16R8 to avoid strapping pins, internal Octal PSRAM (GPIO 33–37), and boot conflicts:

### A. INMP441 I²S Digital Microphone (Audio In)
| INMP441 Pin | ESP32-S3 GPIO | Function |
|---|---|---|
| **VDD** | 3.3V | Power (Do NOT connect to 5V) |
| **GND** | GND | Ground |
| **SD** (Serial Data) | GPIO 4 | $I^2S$ Data In (DIN) |
| **WS** (Word Select / L/R Clock) | GPIO 5 | $I^2S$ Left/Right Clock (LRCK) |
| **SCK** (Serial Clock) | GPIO 6 | $I^2S$ Bit Clock (BCLK) |
| **L/R** | GND | Left channel select (tied to GND) |

### B. MAX98357A I²S Class-D Amplifier (Audio Out)
| MAX98357A Pin | ESP32-S3 GPIO / Power | Function |
|---|---|---|
| **VIN** | 5V (or VBUS) | 5V Power for full 3W output |
| **GND** | GND | Common Ground |
| **DIN** (Data In) | GPIO 7 | $I^2S$ Data Out (DOUT) |
| **BCLK** (Bit Clock) | GPIO 15 | $I^2S$ Bit Clock |
| **LRC** (Left/Right Clock) | GPIO 16 | $I^2S$ Word Select |
| **SD_MODE** | Unconnected / 100k to 3.3V | Defaults to mono $(L+R)/2$ |
| **GAIN** | GND | 9 dB default gain (or open for 12 dB) |

### C. Robotic Neck Servos (Direct ESP32 GPIO PWM — No PCA9685 Needed)
> [!NOTE]
> For 1 to 2 micro servos (SG90 / MG90S), an external PCA9685 driver is **unnecessary**. The ESP32-S3 has 8 hardware LEDC PWM timers that generate smooth 50 Hz servo pulses directly. Power servos strictly from the 5V rail (with a 470µF–1000µF buffer capacitor across 5V/GND) to isolate inductive motor noise from the audio subsystem.

| Servo Pin | ESP32-S3 GPIO / Power | Function |
|---|---|---|
| **Pan Servo Signal (Yaw)** | GPIO 13 | Direct LEDC PWM (Left / Right head turn, 50 Hz) |
| **Tilt Servo Signal (Pitch)** | GPIO 14 | Direct LEDC PWM (Up / Down nod & curious tilt, 50 Hz) |
| **Servo VCC (+)** | 5V (External rail) | 5V Power (Direct from 5V 3A rail, not ESP 3.3V) |
| **Servo GND (-)** | GND | Common Ground |

### D. Facial OLED Display (I2C SSD1306)
| OLED Pin | ESP32-S3 GPIO / Power | Function |
|---|---|---|
| **VCC** | 3.3V (or 5V depending on module) | Logic & Panel Power |
| **GND** | GND | Common Ground |
| **SDA** | GPIO 8 | I2C Serial Data |
| **SCL** | GPIO 9 | I2C Serial Clock |

### E. Actuators & Controls
| Component Pin | ESP32-S3 GPIO | Function |
|---|---|---|
| **Relay Signal (IN)** | GPIO 10 | Digital output (Active LOW/HIGH) |
| **Relay VCC / GND** | 5V / GND | Coil power & common ground |
| **Manual Fallback / Config Button** | GPIO 11 | Internal pull-up to GND (Active LOW manual override) |
| **Status Indicator LED** | GPIO 12 | Visual status feedback (Wake / Thinking / Alert) |

---

## 3. Robot Gesture & Facial Expression Matrix

| Gesture / Reaction | Physical Motion | OLED Facial Expression | Trigger Event |
|---|---|---|---|
| **Perk Up & Greet** | Head lifts up slightly (`Tilt: 75°`) and turns to center | Eyes open wide, gentle blink | Wake word detected / greeting |
| **Attentive Listening** | Head tilts slightly forward (`Tilt: 60°`), subtle glance | Steady focused eyes (`O O`) | User speaking / VAD active |
| **Thinking / Processing** | Head tilts sideways 10°, slow pan oscillation | Shifting / thinking eyes (`~ ~` or wandering) | Awaiting LLM first token |
| **Agreement / "Yes"** | 2× rhythmic nodding (`Tilt: 60° -> 85° -> 60°`) | Smiling eyes (`^ ^`) | Successful IoT action / positive response |
| **Disagreement / "No"** | 2× left-right head shake (`Pan: 75° -> 105° -> 90°`) | Flat / squinting eyes (`- -`) | Command unrecognized / device error |
| **Curious Inquiry** | Head cocks sideways (`Tilt: 50°`, `Pan: 80°`) | Wide questioning eyes with raised brow | Asking user clarification (*"Ki bollen?"*) |
| **Sleep / Standby** | Head droops downward (`Tilt: 40°`) | Closed sleepy eyelids (`_ _`) | Inactive / timeout to idle |
| **Emergency / Crisis** | Head snaps upright, centered | Alert / concerned eyes (`! !`) + LED strobe | Crisis keyword / safety routing triggered |

---

## 4. Server Specifications & Modular Software Pipeline

### A. Server Environment
* **Platform:** Windows 10/11, macOS, Linux (Debian 12 / Ubuntu 22.04 LTS).
* **Runtime:** Python 3.10+ (tested on Python 3.10.11).
* **Architecture:** Hybrid Cloud-Accelerated Edge. STT and LLM run via high-speed cloud endpoints (~400ms), while VAD, Unicode normalization, telemetry, and audio I/O run locally on the device with minimal CPU (<2%) and low memory (<100MB).

### B. Core Python Pipeline Dependencies
* **FastAPI & Networking:** `fastapi`, `uvicorn[standard]`, `websockets`, `python-dotenv`, `pydantic-settings`
* **Speech-to-Text (STT):** `groq` (`whisper-large-v3` with dynamic vocabulary biasing & automatic language detection)
* **Voice Activity Detection & Endpointing:** `webrtcvad` (1.65s comfortable pause tolerance with RMS energy thresholding)
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
