import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import asyncio
import serial
import serial.tools.list_ports
import sounddevice as sd
import numpy as np

def find_esp32_port(default="COM8"):
    try:
        for p in serial.tools.list_ports.comports():
            if "303A" in p.hwid.upper():
                return p.device
            if any(k in p.description.upper() for k in ["CH340", "CP210", "CH343", "ESP32", "USB SERIAL"]):
                return p.device
    except Exception:
        pass
    return default

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.app.pipeline.stt import WhisperSTT
from server.app.pipeline.brain import ConversationalBrain
from server.app.pipeline.tts import synthesize_speech_pcm

SERIAL_PORT = os.getenv("ESP32_PORT", find_esp32_port("COM8"))
BAUD_RATE = 115200
SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 7.0


def record_turn_from_esp32(ser, duration=5.0):
    """Streams audio from INMP441 on ESP32 with real-time VU meter."""
    ser.reset_input_buffer()
    ser.write(b"R")

    pcm_chunks = []
    total_bytes = 0
    expected_bytes = int(SAMPLE_RATE * 2 * duration)
    start_time = time.time()

    print(f"\n🔴 [RECORDING NOW - SPEAK INTO INMP441 MIC!]")

    while (time.time() - start_time) < duration and total_bytes < expected_bytes:
        avail = ser.in_waiting
        if avail > 0:
            chunk = ser.read(min(avail, 2048))
            pcm_chunks.append(chunk)
            total_bytes += len(chunk)

            # Live VU feedback
            if len(chunk) >= 2:
                arr = np.frombuffer(chunk[: (len(chunk) // 2) * 2], dtype=np.int16)
                peak = int(np.max(np.abs(arr)))
                rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                bars = min(int(rms / 120), 16)
                bar_str = "█" * bars
                rem = max(0.0, duration - (time.time() - start_time))
                print(f"\r  ⏱️ {rem:3.1f}s | 🎤 |{bar_str:<16}| Peak: {peak:<5} RMS: {int(rms):<4}", end="", flush=True)
        else:
            time.sleep(0.01)

    ser.write(b"S")
    print("\n⏹️ [CAPTURE COMPLETE]")

    raw_pcm = b"".join(pcm_chunks)
    raw_pcm = raw_pcm.replace(b"\xAA\xBB\xCC\xDD", b"").replace(b"\xDD\xCC\xBB\xAA", b"")

    try:
        import wave
        wav_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "last_turn_esp32.wav"))
        with wave.open(wav_out, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(raw_pcm)
    except Exception:
        pass

    return raw_pcm


async def main():
    print("\n" + "═" * 65)
    print("  🌸 MAYA: LIVE VOICE CONVERSATION LOOP")
    print("  Powered by ESP32 INMP441 Mic + Groq Whisper + Gemini + Edge-TTS")
    print("═" * 65)

    print(f"📡 Connecting to ESP32 on {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        time.sleep(0.4)
        ser.reset_input_buffer()
        print(f"✅ Connected to ESP32 Hardware Audio Bridge ({SERIAL_PORT})!")
    except Exception as e:
        print(f"❌ Failed to connect to {SERIAL_PORT}: {e}")
        print("💡 Ensure Arduino Serial Monitor is closed so the port is free.")
        return

    stt = WhisperSTT()
    brain = ConversationalBrain()

    turn_count = 0

    print("\n" + "-" * 65)
    print("🎙️  Ready to chat with Maya!")
    print("   • Press [ENTER] to speak each turn (or type 'q' / 'exit' to quit).")
    print("   • Speak clearly near the INMP441 microphone.")
    print("-" * 65)

    try:
        while True:
            turn_count += 1
            prompt_text = f"\n👉 [Turn {turn_count}] Press [ENTER] to speak (or 'q' to quit): "
            user_input = input(prompt_text).strip().lower()

            if user_input in ["q", "quit", "exit"]:
                print("\n🌸 Maya: 'Goodbye! Let me know whenever you want to talk again!'")
                break

            # Record 5.5 seconds from ESP32 mic
            raw_pcm = record_turn_from_esp32(ser, duration=5.5)

            if len(raw_pcm) < 1600:
                print("⚠️ No audio data captured. Please check the mic connection.")
                continue

            samples_np = np.frombuffer(raw_pcm[: (len(raw_pcm) // 2) * 2], dtype=np.int16)
            peak = int(np.max(np.abs(samples_np)))

            if peak < 80:
                print("⚠️ Signal too quiet. Speak closer to the microphone!")
                continue

            # Transcribe with Whisper
            print("⏳ Transcribing speech with Groq Whisper...")
            t_stt_start = time.perf_counter()
            transcript, is_garbled = await stt.transcribe_pcm(raw_pcm, sample_rate=SAMPLE_RATE)
            t_stt = (time.perf_counter() - t_stt_start) * 1000

            if not transcript or not transcript.strip():
                print("❌ Maya didn't hear any words. Try speaking again.")
                continue

            print(f"⚡ ASR ({t_stt:.0f}ms) 👤 You: \"{transcript}\"")

            # Generate response with Gemini
            print("🧠 Maya is thinking...")
            full_reply = ""
            print("🌸 MAYA: ", end="", flush=True)

            async for sentence in brain.generate_reply_sentences(transcript):
                full_reply += sentence + " "
                print(f"{sentence} ", end="", flush=True)
            print()

            # Synthesize & Playback
            try:
                reply_pcm = await synthesize_speech_pcm(full_reply)
                if reply_pcm:
                    reply_arr = np.frombuffer(reply_pcm, dtype=np.int16)
                    sd.play(reply_arr, samplerate=24000)
                    sd.wait()
            except Exception as e:
                print(f"(Speaker playback: {e})")

    except KeyboardInterrupt:
        print("\n\nSession stopped by user.")
    finally:
        try:
            ser.write(b"S")
            ser.close()
        except Exception:
            pass
        print("Session ended. Have a wonderful day!\n")


if __name__ == "__main__":
    asyncio.run(main())
