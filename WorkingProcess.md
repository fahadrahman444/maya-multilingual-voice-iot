# MAYA: Complete Step-by-Step Engineering Working Process

This document serves as the master engineering guide and operational roadmap for developing **MAYA (Siri-Grade English Voice AI Assistant & IoT Controller)**.

It follows a **Software-First & Voice-First Strategy**: building and thoroughly verifying the complete conversational speech, memory, telemetry, and safety pipeline directly on your computer before introducing smart-home relay controls and embedded ESP32-S3 hardware.

---

## 1. Project Development Roadmap

```mermaid
flowchart TD
    subgraph M1["MILESTONE 1: Pure Voice AI Assistant (COMPLETED & VERIFIED ✅)"]
        S1["Step 1: Environment & API Foundation ✅"] --> S2["Step 2: English Speech Pipeline (STT + TTS) ✅"]
        S2 --> S3["Step 3: Crisis Guardrail & Empathetic Dual-Brain ✅"]
        S3 --> S4["Step 4: Continuous Hands-Free VAD & Full-Duplex Barge-In ✅"]
        S4 --> S5["Step 5: Tiered Memory & Contradiction Resolution ✅"]
        S5 --> S6["Step 6: Decoupled Prosody & Telemetry Sink ✅"]
    end

    subgraph M2["MILESTONE 2: IoT & ESP32-S3 Hardware Integration (UPCOMING)"]
        S6 --> S7["Step 7: Smart Home Tool Calling (Relay Schema)"]
        S7 --> S8["Step 8: ESP32-S3 Firmware (I²S Audio & WebSocket Streaming)"]
        S8 --> S9["Step 9: On-Device Wake-Word (ESP-SR) & Physical Relay Wiring"]
        S9 --> S10["Step 10: Benchmark Profiling & Thesis Defense Deliverables"]
    end
```

---

## 2. Milestone 1: Pure Voice AI Assistant (Verified Status: ✅ Complete)

### Step 1: Environment, Configuration & Foundation (Completed ✅)
* Dependency specifications in `server/requirements.txt`.
* Environment configuration loader with validation in `server/app/config.py`.
* One-click Windows root launcher (`run_windows.bat`) and `WindowsSelectorEventLoopPolicy` setup to eliminate Windows SSL shutdown bugs.

### Step 2: English Speech Pipeline (STT & TTS) (Completed ✅)
* **STT:** Groq Whisper Large V3 locked to English (`language="en"`) with domain vocabulary conditioning in `server/app/pipeline/stt.py` (~150–250ms).
* **TTS:** Microsoft Edge-TTS with natural English neural voice (`en-US-AvaNeural`) in `server/app/pipeline/tts.py`.
* **Markdown Sanitizer:** `strip_markdown_for_speech` removes `**`, `*`, `` ` ``, `#` before audio synthesis.

### Step 3: Crisis Guardrail & Cognitive Dual-Brain (Completed ✅)
* **Safety:** Zero-latency deterministic regex detector for self-harm and acute crisis phrases in `server/app/pipeline/safety.py`. Routes directly to the `988` Suicide & Crisis Lifeline.
* **Dual-Brain:** Google Gemini 3.5 Flash-Lite primary with Groq (`qwen/qwen3.8-27b`) fallback.
* **Circuit Breaker:** Sliding-window error thresholding with 60-second cooldown and mid-stream failover.
* **Siri Brevity:** Enforces 1–2 sentence direct answers without conversational filler or clinginess.

### Step 4: Continuous Hands-Free VAD & Full-Duplex Barge-In (Completed ✅)
* **Pause Tolerance:** WebRTC VAD endpointing configured to a comfortable **1.65s** (`VAD_ENDPOINT_MS=1650`), allowing natural pauses without premature interruption.
* **Full-Duplex Barge-In Interruption:** Real-time microphone monitoring via `sounddevice.RawStream` interrupts speaker output within **< 50ms** when the user speaks.

### Step 5: Tiered Memory & Contradiction Resolution (Completed ✅)
* **Tiered Memory:** Hot (rolling 6 verbatim turns), Warm (background summarized context), and Cold (persistent disk store in `server/data/user_memory.json`).
* **Contradiction Resolver:** Automatically detects conflicting preferences/facts and preserves audit history.
* **Budget Cap:** Strict 800-character (~200 token) prompt budget cap prevents context bloat.
* **Multi-Session Isolation:** `SessionState` keyed by `session_id` guarantees multi-user concurrency without history contamination.

### Step 6: Decoupled Prosody & Telemetry Sink (Completed ✅)
* **Decoupled Prosody Engine:** Independent Pace (`0.8–1.2×`) and Expressivity (`low`, `medium`, `high`) controls in `server/app/pipeline/tts.py`.
* **Zero-Blocking Telemetry Sink:** Thread-safe `TurnTrace` queue with 50MB rolling file rotation (`server/data/traces.jsonl`).
* **SLO Dashboard:** Measures TTFA p50/p95 and fallback rates (`python -m server.app.dashboard`).

---

## 3. Automated Test Commands

```powershell
# 1. Comprehensive End-to-End Regression Test Suite (16/16 Verified Tests)
python server/tests/test_regression.py

# 2. Telemetry Sink & Persistent Memory Tests
pytest server/tests/test_telemetry.py server/tests/test_memory.py

# 3. English STT & TTS Pipeline Tests
python server/tests/test_speech.py

# 4. Cognitive Brain, Context & Crisis Safety Guardrail
python server/tests/test_brain.py
```
