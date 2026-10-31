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

# Enforce Windows Selector Event Loop policy to prevent Windows Proactor SSL transport crash on shutdown
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Ensure UTF-8 I/O encoding on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdin:
            sys.stdin.reconfigure(encoding="utf-8")
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import numpy as np
import sounddevice as sd
import webrtcvad

from server.app.config import settings
from server.app.pipeline.safety import evaluate_crisis_guardrail
from server.app.pipeline.brain import brain_engine
from server.app.pipeline.stt import stt_client
from server.app.pipeline.tts import synthesize_speech_pcm
from server.app.pipeline.telemetry import TurnTrace, emit_turn

SAMPLE_RATE = settings.SAMPLE_RATE
CHANNELS = settings.CHANNELS

# VAD parameters for Siri-Grade turn-taking
VAD_AGGRESSIVENESS = 1  # 1: forgiving mode
FRAME_MS = 30           # 30ms frames
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples
PRE_ROLL_FRAMES = 12    # ~360ms pre-speech buffer

# Siri-Grade Endpointing: ~450ms pause before assistant commits to answering
SILENCE_PAUSE_SECONDS = settings.VAD_ENDPOINT_MS / 1000.0  # 0.45s default
SILENCE_FRAMES_THRESHOLD = max(10, int(SILENCE_PAUSE_SECONDS * 1000 / FRAME_MS))
MIN_SPEECH_FRAMES = 10  # ~300ms minimum speech length
MIN_RMS_THRESHOLD = 180.0

# Higher threshold for barge-in to filter out speaker bleed-through
BARGE_IN_RMS_THRESHOLD = 420.0


def play_pcm_audio(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE, allow_bargein: bool = True) -> bool:
    """
    Play raw 16kHz 16-bit Mono PCM audio through the local speakers.
    When allow_bargein is True and enabled in config, monitors microphone in real-time
    and cuts playback within < 50ms if user speaks.
    Returns: True if interrupted by user voice, False if played completely.
    """
    if not pcm_bytes:
        return False

    if not allow_bargein or not settings.BARGE_IN_ENABLED:
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()
        return False

    chunk_samples = 480  # 30ms
    chunk_bytes_len = chunk_samples * 2
    bargein_vad = webrtcvad.Vad(2)  # Moderate aggression for interrupt detection
    consecutive_user_speech = 0

    try:
        with sd.RawStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=chunk_samples) as stream:
            for offset in range(0, len(pcm_bytes), chunk_bytes_len):
                out_chunk = pcm_bytes[offset:offset + chunk_bytes_len]
                if len(out_chunk) < chunk_bytes_len:
                    out_chunk = out_chunk + b"\x00" * (chunk_bytes_len - len(out_chunk))

                # Simultaneous full-duplex mic read and speaker write
                in_chunk, _ = stream.read(chunk_samples)
                stream.write(out_chunk)

                # Measure incoming microphone energy
                audio_array = np.frombuffer(in_chunk, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

                if rms >= BARGE_IN_RMS_THRESHOLD and bargein_vad.is_speech(bytes(in_chunk), sample_rate):
                    consecutive_user_speech += 1
                    if consecutive_user_speech >= 3:  # ~90ms of sustained user speech
                        print("\n🛑 [BARGE-IN TRIGGERED] (User interrupted speech)")
                        return True
                else:
                    consecutive_user_speech = 0
    except Exception:
        # Fallback to standard blocking playback if duplex device is unavailable
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()

    return False


def record_continuous_vad() -> bytes:
    """Passively listen until speech is detected, record until crisp endpoint pause, and return PCM audio."""
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

            # Check RMS energy
            audio_array = np.frombuffer(frame_bytes, dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

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
                    if consecutive_silence >= SILENCE_FRAMES_THRESHOLD:
                        if len(speech_chunks) >= MIN_SPEECH_FRAMES:
                            print("[Done]")
                            return b"".join(speech_chunks)
                        else:
                            is_speaking = False
                            speech_chunks.clear()
                            consecutive_silence = 0
                            print("\r🎧 [LISTENING...] Speak naturally...", end="", flush=True)
                else:
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


async def process_user_turn(user_text: str, t_stt: float = 0.0) -> bool:
    """
    Process user text through the Siri-grade AI safety & pipelined streaming speech.
    Returns: True if interrupted via barge-in, False otherwise.
    """
    print(f"\n👤 You said: '{user_text}'")
    trace = TurnTrace()
    trace.record_user_input(user_text)
    if t_stt > 0:
        trace.stages["stt"] = round(t_stt, 1)
    trace.provider = brain_engine.provider

    try:
        # 1. Crisis & Safety Interceptor
        t_start = time.perf_counter()
        safety_result = evaluate_crisis_guardrail(user_text)

        if safety_result.is_crisis:
            trace.safety["crisis_triggered"] = True
            reply_text = safety_result.override_response or ""
            print(f"🚨 [SAFETY PROTOCOL TRIGGERED] (Category: {safety_result.crisis_category})")
            print(f"\n🌸 MAYA: \"{reply_text}\"")
            pcm_audio = await synthesize_speech_pcm(reply_text)
            trace.mark("first_audio")
            print("🔊 Speaking response through speakers...")
            play_pcm_audio(pcm_audio, allow_bargein=False)
            return False

        # 2. Pipelined Sentence-Streaming Brain + TTS
        print("\n🌸 MAYA: ", end="", flush=True)
        first_audio_ms = 0.0
        llm_ttft_ms = 0.0
        tts_first_ms = 0.0
        is_first_sentence = True
        barge_in_occurred = False

        async for sentence in brain_engine.generate_reply_sentences(user_text):
            s_clean = sentence.strip()
            if not s_clean:
                continue

            if is_first_sentence:
                llm_ttft_ms = (time.perf_counter() - t_start) * 1000
                trace.mark("llm_ttft")

            print(f"{s_clean} ", end="", flush=True)
            trace.observe_sentence(s_clean, terminated=True)

            # Synthesize audio for this sentence immediately
            t_synth_start = time.perf_counter()
            pcm_chunk = await synthesize_speech_pcm(s_clean)
            t_synth = (time.perf_counter() - t_synth_start) * 1000

            if is_first_sentence:
                tts_first_ms = t_synth
                first_audio_ms = (time.perf_counter() - t_start) * 1000
                trace.mark("first_audio")
                is_first_sentence = False

            if pcm_chunk:
                interrupted = play_pcm_audio(pcm_chunk, allow_bargein=True)
                if interrupted:
                    barge_in_occurred = True
                    trace.barge_in = True
                    break

        print()
        t_total = (time.perf_counter() - t_start) * 1000

        # Structured Siri-Grade Telemetry Logging
        endpoint_ms = settings.VAD_ENDPOINT_MS
        print(
            f"⚡ [TELEMETRY] Endpoint: {endpoint_ms}ms | ASR: {t_stt:.0f}ms | "
            f"LLM TTFT: {llm_ttft_ms:.0f}ms | TTS: {tts_first_ms:.0f}ms | "
            f"First Audio: {first_audio_ms:.0f}ms | BargeIn: {barge_in_occurred}"
        )
        return barge_in_occurred
    except Exception as exc:
        trace.errors.append(type(exc).__name__)
        raise
    finally:
        emit_turn(trace)


async def main():
    print("=" * 65)
    print("       MAYA: Multilingual AI Voice Assistant (Bangla & English)")
    print(f"       Mode: Siri-Grade Engine (Endpoint: {settings.VAD_ENDPOINT_MS}ms, Barge-In: {settings.BARGE_IN_ENABLED})")
    print("=" * 65)
    print("1. [V] Hands-Free Voice Mode (Speak naturally, auto silence detection) [Default]")
    print("2. [T] Text Mode (Type in terminal, listen to spoken reply)")
    print("3. [M] Manual Push-to-Talk Mode (Press Enter to start/stop)")
    print("=" * 65)

    try:
        mode = input("Select mode (V / T / M) [default: V]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

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
                transcribed_text, is_garbled = await stt_client.transcribe_pcm(pcm_bytes)
                t_stt = (time.perf_counter() - t_stt_start) * 1000
                print(f"   Transcribed in {t_stt:.1f}ms: '{transcribed_text}'")

                if not transcribed_text:
                    print("⚠️ Could not detect speech. Please try again.")
                    continue

                if is_garbled:
                    print("⚠️ [ASR TARGETED REPAIR] Flagged fragmented audio, asking for clarification...")
                    clarification = (
                        "আমি ঠিক বুঝতে পারিনি, আরেকবার একটু বুঝিয়ে বলবেন কি?"
                        if any('\u0980' <= c <= '\u09ff' for c in transcribed_text)
                        else "I didn't quite catch that. Could you say it once more?"
                    )
                    print(f"\n🌸 MAYA: \"{clarification}\"")
                    pcm = await synthesize_speech_pcm(clarification)
                    play_pcm_audio(pcm, allow_bargein=False)
                    continue

                await process_user_turn(transcribed_text, t_stt=t_stt)
            except KeyboardInterrupt:
                break

    else:
        # Default: Continuous Hands-Free VAD with Siri-Grade ~450ms endpointing
        print("\n✨ [SIRI-GRADE HANDS-FREE VOICE ACTIVATED]")
        print("   • Speak naturally in Bangla or English.")
        print(f"   • Crisp Endpointing: ~{settings.VAD_ENDPOINT_MS}ms pause.")
        print(f"   • Real-Time Barge-In: {'Enabled' if settings.BARGE_IN_ENABLED else 'Disabled'}")
        print("   • Press Ctrl+C anytime to exit.\n")

        while True:
            try:
                pcm_bytes = record_continuous_vad()

                if not pcm_bytes or len(pcm_bytes) < (SAMPLE_RATE * 2 * 0.3):
                    continue

                print("⏳ Transcribing speech via Groq Whisper...")
                t_stt_start = time.perf_counter()
                transcribed_text, is_garbled = await stt_client.transcribe_pcm(pcm_bytes)
                t_stt = (time.perf_counter() - t_stt_start) * 1000
                print(f"   Transcribed in {t_stt:.1f}ms: '{transcribed_text}'")

                if not transcribed_text or not transcribed_text.strip():
                    continue

                if is_garbled:
                    print("⚠️ [ASR TARGETED REPAIR] Flagged fragmented audio, asking for clarification...")
                    clarification = (
                        "আমি ঠিক বুঝতে পারিনি, আরেকবার একটু বুঝিয়ে বলবেন কি?"
                        if any('\u0980' <= c <= '\u09ff' for c in transcribed_text)
                        else "I didn't quite catch that. Could you say it once more?"
                    )
                    print(f"\n🌸 MAYA: \"{clarification}\"")
                    pcm = await synthesize_speech_pcm(clarification)
                    play_pcm_audio(pcm, allow_bargein=False)
                    continue

                await process_user_turn(transcribed_text, t_stt=t_stt)

            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    print("\nGoodbye! / বিদায়! ভালো থাকবেন।")
    sys.exit(0)
