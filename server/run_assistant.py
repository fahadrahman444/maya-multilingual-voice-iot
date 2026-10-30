import asyncio
import io
import os
import sys
import time
import wave
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

# Ensure UTF-8 I/O encoding on Windows consoles
if sys.platform == 'win32':
    try:
        if sys.stdin:
            sys.stdin.reconfigure(encoding='utf-8')
        if sys.stdout:
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr:
            sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import numpy as np
import sounddevice as sd
from server.app.pipeline.safety import evaluate_crisis_guardrail
from server.app.pipeline.brain import brain_engine
from server.app.pipeline.stt import stt_client
from server.app.pipeline.tts import synthesize_speech_pcm

SAMPLE_RATE = 16000
CHANNELS = 1


def play_pcm_audio(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE):
    """Play raw 16kHz 16-bit Mono PCM audio through the local speakers."""
    if not pcm_bytes:
        return
    audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
    sd.play(audio_array, samplerate=sample_rate)
    sd.wait()


def record_microphone_until_enter() -> bytes:
    """Record audio from the microphone until the user presses Enter."""
    print("\n🎤 [LISTENING...] Speak into your microphone now (Press Enter when done)...", end="", flush=True)
    recorded_chunks = []
    stop_recording = False

    def callback(indata, frames, time_info, status):
        if not stop_recording:
            recorded_chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback,
    )
    with stream:
        input()
        stop_recording = True

    if not recorded_chunks:
        return b""

    full_array = np.concatenate(recorded_chunks, axis=0)
    print(" [Done Recording]")
    return full_array.tobytes()


async def process_user_turn(user_text: str):
    """Process transcribed or typed user text through the AI safety & speech pipeline."""
    print(f"\n👤 You said: '{user_text}'")

    # 1. Crisis & Safety Interceptor
    t_start = time.perf_counter()
    safety_result = evaluate_crisis_guardrail(user_text)

    if safety_result.is_crisis:
        reply_text = safety_result.override_response
        print(f"🚨 [SAFETY PROTOCOL TRIGGERED] (Category: {safety_result.crisis_category})")
    else:
        # 2. Empathetic Brain Response
        reply_text = await brain_engine.generate_reply(user_text)

    t_brain = time.perf_counter() - t_start

    # 3. Speech Synthesis (Edge-TTS)
    t_tts_start = time.perf_counter()
    pcm_audio = await synthesize_speech_pcm(reply_text)
    t_tts = time.perf_counter() - t_tts_start

    print(f"\n🌸 MAYA: \"{reply_text}\"")
    print(f"⚡ Latency: Brain {t_brain*1000:.1f}ms | TTS {t_tts*1000:.1f}ms | Total {(t_brain+t_tts)*1000:.1f}ms")

    # 4. Speak Out Loud
    print("🔊 Speaking response through speakers...")
    play_pcm_audio(pcm_audio)


async def main():
    print("=" * 65)
    print("       MAYA: Multilingual Bangla AI Voice Assistant")
    print("=" * 65)
    print("1. [V] Voice Mode (Speak into your laptop microphone)")
    print("2. [T] Text Mode (Type in terminal, listen to spoken reply)")
    print("=" * 65)

    mode = input("Select mode (V for Voice / T for Text) [default: V]: ").strip().lower()
    if mode == "t":
        print("\n[TEXT MODE] Type your message in Bangla or English (or 'exit' to quit):")
        while True:
            try:
                user_msg = input("\nType message: ").strip()
                if user_msg.lower() in ["exit", "quit", "q"]:
                    print("বিদায়! ভালো থাকবেন।")
                    break
                if not user_msg:
                    continue
                await process_user_turn(user_msg)
            except (KeyboardInterrupt, EOFError):
                break
    else:
        print("\n[VOICE MODE] Press Enter to begin speaking, and Enter again to finish.")
        while True:
            try:
                input("\n👉 Press [ENTER] to start speaking (or Ctrl+C to quit)...")
                pcm_bytes = record_microphone_until_enter()

                if len(pcm_bytes) < (SAMPLE_RATE * 2 * 0.5):
                    print("⚠️ Audio too short. Please speak for at least 1 second.")
                    continue

                print("⏳ Transcribing Bangla speech via Groq Whisper...")
                t_stt_start = time.perf_counter()
                transcribed_text = await stt_client.transcribe_pcm(pcm_bytes)
                t_stt = time.perf_counter() - t_stt_start
                print(f"   Transcribed in {t_stt*1000:.1f}ms: '{transcribed_text}'")

                if not transcribed_text:
                    print("⚠️ Could not detect speech. Please try again.")
                    continue

                await process_user_turn(transcribed_text)
            except KeyboardInterrupt:
                print("\n\nবিদায়! ভালো থাকবেন।")
                break


if __name__ == "__main__":
    asyncio.run(main())
