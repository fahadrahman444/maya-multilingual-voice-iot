import asyncio
import collections
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
import webrtcvad

from server.app.pipeline.safety import evaluate_crisis_guardrail
from server.app.pipeline.brain import brain_engine
from server.app.pipeline.stt import stt_client
from server.app.pipeline.tts import synthesize_speech_pcm

SAMPLE_RATE = 16000
CHANNELS = 1

# VAD parameters for comfortable conversational breathing room
VAD_AGGRESSIVENESS = 1  # 1: forgiving mode (avoids cutting off soft syllables/pauses)
FRAME_MS = 30  # WebRTC VAD supports 10, 20, or 30ms frames
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples
PRE_ROLL_FRAMES = 15  # ~450ms pre-speech buffer to prevent word clipping

# Generous silence threshold: ~1.65 seconds pause before MAYA assumes you finished talking
SILENCE_PAUSE_SECONDS = 1.65
SILENCE_FRAMES_THRESHOLD = int(SILENCE_PAUSE_SECONDS * 1000 / FRAME_MS)  # ~55 frames
MIN_SPEECH_FRAMES = 12  # ~360ms minimum speech length to filter tiny background clicks
MIN_RMS_THRESHOLD = 180.0  # Sensitive floor to catch soft whispers and sentence endings


def play_pcm_audio(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE):
    """Play raw 16kHz 16-bit Mono PCM audio through the local speakers."""
    if not pcm_bytes:
        return
    audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
    sd.play(audio_array, samplerate=sample_rate)
    sd.wait()


def record_continuous_vad() -> bytes:
    """Passively listen until speech is detected, record until natural silence pause, and return PCM audio."""
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    pre_roll = collections.deque(maxlen=PRE_ROLL_FRAMES)
    speech_chunks = []
    is_speaking = False
    consecutive_silence = 0

    print("\n🎧 [LISTENING...] Speak naturally (or Ctrl+C to quit)...", end="", flush=True)

    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=FRAME_SIZE) as stream:
        while True:
            frame, _ = stream.read(FRAME_SIZE)
            frame_bytes = bytes(frame)

            # Check RMS energy to ensure sufficient audio volume
            audio_array = np.frombuffer(frame_bytes, dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

            # Determine whether current 30ms chunk contains voice
            is_speech_frame = (rms >= MIN_RMS_THRESHOLD) and vad.is_speech(frame_bytes, SAMPLE_RATE)

            if not is_speaking:
                pre_roll.append(frame_bytes)
                if is_speech_frame:
                    is_speaking = True
                    consecutive_silence = 0
                    speech_chunks = list(pre_roll)
                    print("\n🎤 [HEARING YOU...] ", end="", flush=True)
            else:
                speech_chunks.append(frame_bytes)
                if not is_speech_frame:
                    consecutive_silence += 1
                    # Only finalize after the user has paused for ~1.65 full seconds
                    if consecutive_silence >= SILENCE_FRAMES_THRESHOLD:
                        if len(speech_chunks) >= MIN_SPEECH_FRAMES:
                            print("[Done]")
                            return b"".join(speech_chunks)
                        else:
                            # Too short to be actual speech (likely click or cough)
                            is_speaking = False
                            speech_chunks.clear()
                            consecutive_silence = 0
                            print("\r🎧 [LISTENING...] Speak naturally...", end="", flush=True)
                else:
                    # User resumed speaking; reset the silence counter
                    consecutive_silence = 0


def record_microphone_until_enter() -> bytes:
    """Record audio from the microphone until the user presses Enter (Manual Push-to-Talk)."""
    print("\n🎤 [MANUAL RECORDING...] Speak now (Press Enter when done)...", end="", flush=True)
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
    print("       MAYA: Multilingual AI Voice Assistant (Bangla & English)")
    print("=" * 65)
    print("1. [V] Hands-Free Voice Mode (Speak naturally, auto silence detection) [Default]")
    print("2. [T] Text Mode (Type in terminal, listen to spoken reply)")
    print("3. [M] Manual Push-to-Talk Mode (Press Enter to start/stop)")
    print("=" * 65)

    mode = input("Select mode (V / T / M) [default: V]: ").strip().lower()

    if mode == "t":
        print("\n[TEXT MODE] Type your message in Bangla or English (or 'exit' to quit):")
        while True:
            try:
                user_msg = input("\nType message: ").strip()
                if user_msg.lower() in ["exit", "quit", "q"]:
                    print("Goodbye! / বিদায়! ভালো থাকবেন।")
                    break
                if not user_msg:
                    continue
                await process_user_turn(user_msg)
            except (KeyboardInterrupt, EOFError):
                break

    elif mode == "m":
        print("\n[MANUAL PUSH-TO-TALK MODE]")
        while True:
            try:
                input("\n👉 Press [ENTER] to start speaking (or Ctrl+C to quit)...")
                pcm_bytes = record_microphone_until_enter()

                if len(pcm_bytes) < (SAMPLE_RATE * 2 * 0.5):
                    print("⚠️ Audio too short. Please speak for at least 1 second.")
                    continue

                print("⏳ Transcribing speech via Groq Whisper...")
                t_stt_start = time.perf_counter()
                transcribed_text = await stt_client.transcribe_pcm(pcm_bytes)
                t_stt = time.perf_counter() - t_stt_start
                print(f"   Transcribed in {t_stt*1000:.1f}ms: '{transcribed_text}'")

                if not transcribed_text:
                    print("⚠️ Could not detect speech. Please try again.")
                    continue

                await process_user_turn(transcribed_text)
            except KeyboardInterrupt:
                print("\n\nGoodbye! / বিদায়! ভালো থাকবেন।")
                break

    else:
        # Default: Continuous Hands-Free VAD with generous conversational pause tolerance
        print("\n✨ [HANDS-FREE VOICE MODE ACTIVATED]")
        print("   • Speak naturally in Bangla or English.")
        print("   • Pause tolerance: ~1.65 seconds (you can pause/think without being interrupted).")
        print("   • No keyboard input needed! (Press Ctrl+C anytime to exit)\n")

        while True:
            try:
                pcm_bytes = record_continuous_vad()

                if not pcm_bytes or len(pcm_bytes) < (SAMPLE_RATE * 2 * 0.4):
                    continue

                print("⏳ Transcribing speech via Groq Whisper...")
                t_stt_start = time.perf_counter()
                transcribed_text = await stt_client.transcribe_pcm(pcm_bytes)
                t_stt = time.perf_counter() - t_stt_start
                print(f"   Transcribed in {t_stt*1000:.1f}ms: '{transcribed_text}'")

                if not transcribed_text or not transcribed_text.strip():
                    continue

                await process_user_turn(transcribed_text)

            except KeyboardInterrupt:
                print("\n\nGoodbye! / বিদায়! ভালো থাকবেন।")
                break


if __name__ == "__main__":
    asyncio.run(main())
