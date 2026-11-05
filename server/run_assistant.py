import asyncio
import collections
import io
import os
import re
import sys
import time
import wave
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

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
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
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

# Voice Endpointing: ~1.65s pause before assistant commits to answering
SILENCE_PAUSE_SECONDS = settings.VAD_ENDPOINT_MS / 1000.0  # 1.65s default
TRAILING_INCOMPLETE = re.compile(
    r"\b(?:and|but|or|because|so|then|it'?s|that|with|to|of|for|as|if|when|while|like|i\s+mean)\s*$",
    re.IGNORECASE,
)
SILENCE_FRAMES_THRESHOLD = max(10, int(SILENCE_PAUSE_SECONDS * 1000 / FRAME_MS))
MIN_SPEECH_FRAMES = 10  # ~300ms minimum speech length
MIN_RMS_THRESHOLD = 180.0

# Smart Barge-In RMS threshold (calibrated above laptop speaker echo)
BARGE_IN_RMS_THRESHOLD = float(getattr(settings, "BARGE_IN_RMS_THRESHOLD", 850.0))


def play_pcm_audio(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE, allow_bargein: bool = True) -> Tuple[bool, bytes]:
    """
    Play raw 16kHz 16-bit Mono PCM audio through the local speakers.
    When allow_bargein is True and enabled in config, monitors microphone in real-time
    and cuts playback within < 50ms if user speaks.
    Returns: (interrupted: bool, captured_audio: bytes)
    """
    if not pcm_bytes:
        return False, b""

    if not allow_bargein or not settings.BARGE_IN_ENABLED:
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()
        return False, b""

    chunk_samples = 480  # 30ms
    chunk_bytes_len = chunk_samples * 2
    bargein_vad = webrtcvad.Vad(2)  # Moderate-to-strict VAD for interrupt distinction
    consecutive_user_speech = 0
    recent_mic_frames = collections.deque(maxlen=10)  # ~300ms pre-roll to capture start of user interruption
    frame_index = 0

    try:
        with sd.RawStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=chunk_samples) as stream:
            for offset in range(0, len(pcm_bytes), chunk_bytes_len):
                out_chunk = pcm_bytes[offset:offset + chunk_bytes_len]
                if len(out_chunk) < chunk_bytes_len:
                    out_chunk = out_chunk + b"\x00" * (chunk_bytes_len - len(out_chunk))

                # Simultaneous full-duplex mic read and speaker write
                in_chunk, _ = stream.read(chunk_samples)
                stream.write(out_chunk)
                frame_index += 1

                in_bytes = bytes(in_chunk)
                recent_mic_frames.append(in_bytes)

                # Grace period: ignore first 6 frames (~180ms) to allow audio output stream to settle
                if frame_index < 6:
                    continue

                # Measure incoming microphone energy
                audio_array = np.frombuffer(in_chunk, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))

                # Require higher threshold + WebRTC VAD + 4 consecutive frames (~120ms sustained human voice)
                if rms >= BARGE_IN_RMS_THRESHOLD and bargein_vad.is_speech(in_bytes, sample_rate):
                    consecutive_user_speech += 1
                    if consecutive_user_speech >= 4:
                        print("\n🛑 [BARGE-IN TRIGGERED] (User interrupted speech)")
                        captured_audio = b"".join(recent_mic_frames)
                        return True, captured_audio
                else:
                    consecutive_user_speech = 0
    except Exception:
        # Fallback to standard blocking playback if duplex device is unavailable
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()

    return False, b""


def record_continuous_vad(
    is_continuation: bool = False,
    max_wait_seconds: Optional[float] = None,
    initial_audio: Optional[bytes] = None,
) -> bytes:
    """
    Passively listen until speech is detected, record until crisp endpoint pause, and return PCM audio.
    If initial_audio is provided (from a barge-in interruption), starts in speaking state immediately.
    """
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    pre_roll = collections.deque(maxlen=PRE_ROLL_FRAMES)
    speech_chunks = []
    is_speaking = False
    consecutive_silence = 0
    t_start = time.monotonic()

    if initial_audio and len(initial_audio) > 0:
        is_speaking = True
        speech_chunks.append(initial_audio)
        print("\n🎤 [HEARING YOU...] ", end="", flush=True)

    prompt_label = "🎧 [LISTENING...] Speak naturally (or Ctrl+C to quit)..." if not is_continuation else "⏳ [HOLDING...] (Waiting for you to finish your thought)..."
    if not is_speaking:
        print(f"\n{prompt_label}", end="", flush=True)

    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=FRAME_SIZE) as stream:
        while True:
            if is_continuation and not is_speaking and max_wait_seconds:
                if (time.monotonic() - t_start) >= max_wait_seconds:
                    return b""

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

                    # Respect full silence threshold (e.g. 1.65s) so user is never cut off mid-thought
                    adaptive_threshold = SILENCE_FRAMES_THRESHOLD

                    if consecutive_silence >= adaptive_threshold:
                        if len(speech_chunks) >= MIN_SPEECH_FRAMES:
                            print("[Done]")
                            return b"".join(speech_chunks)
                        else:
                            is_speaking = False
                            speech_chunks.clear()
                            consecutive_silence = 0
                            print(f"\r{prompt_label}", end="", flush=True)
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


async def process_user_turn(user_text: str, t_stt: float = 0.0) -> Tuple[bool, bytes]:
    """
    Process user text through the Siri-grade AI safety & pipelined streaming speech.
    Returns: (interrupted: bool, captured_audio: bytes)
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
            return False, b""

        # 2. Pipelined Sentence-Streaming Brain + TTS
        print("\n🌸 MAYA: ", end="", flush=True)
        first_audio_ms = 0.0
        llm_ttft_ms = 0.0
        tts_first_ms = 0.0
        is_first_sentence = True
        barge_in_occurred = False
        barge_in_audio = b""

        async for sentence in brain_engine.generate_reply_sentences(user_text):
            s_clean = sentence.strip()
            if not s_clean or not re.search(r"\w", s_clean):
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
                interrupted, captured = play_pcm_audio(pcm_chunk, allow_bargein=True)
                if interrupted:
                    barge_in_occurred = True
                    barge_in_audio = captured
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
        return barge_in_occurred, barge_in_audio
    except Exception as exc:
        trace.errors.append(type(exc).__name__)
        raise
    finally:
        emit_turn(trace)


async def main():
    print("=" * 65)
    print("       MAYA: Siri-Grade English AI Voice Assistant")
    print(f"       Mode: Hands-Free Voice Engine (Endpoint: {settings.VAD_ENDPOINT_MS}ms, Barge-In: {settings.BARGE_IN_ENABLED})")
    print("=" * 65)

    mode = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().strip().lstrip("-")
        if arg in ("v", "voice", "handsfree", "hands-free"):
            mode = "v"
        elif arg in ("t", "text"):
            mode = "t"
        elif arg in ("m", "push", "manual", "ptt"):
            mode = "m"

    if not mode:
        print("1. [V] Hands-Free Voice Mode (Speak naturally, auto silence detection) [Default]")
        print("2. [T] Text Mode (Type in terminal, listen to spoken reply)")
        print("3. [M] Manual Push-to-Talk Mode (Press Enter to start/stop)")
        print("=" * 65)
        try:
            mode = input("Select mode (V / T / M) [default: V]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

    if mode == "t":
        print("\n[TEXT MODE] Type your message in English (or 'exit' to quit):")
        while True:
            try:
                user_msg = input("\nType message: ").strip()
                if user_msg.lower() in ["exit", "quit", "q"]:
                    print("Goodbye! Have a great day.")
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
                transcribed_text, is_garbled = await stt_client.transcribe_pcm(pcm_bytes, language="en")
                t_stt = (time.perf_counter() - t_stt_start) * 1000
                print(f"   Transcribed in {t_stt:.1f}ms: '{transcribed_text}'")

                if not transcribed_text:
                    print("⚠️ Could not detect speech. Please try again.")
                    continue

                if is_garbled:
                    print("⚠️ [ASR TARGETED REPAIR] Flagged fragmented/gibberish audio, asking for clarification...")
                    clarification = "I didn't quite catch that. Could you say it once more?"
                    print(f"\n🌸 MAYA: \"{clarification}\"")
                    pcm = await synthesize_speech_pcm(clarification)
                    play_pcm_audio(pcm, allow_bargein=False)
                    continue

                await process_user_turn(transcribed_text, t_stt=t_stt)
            except KeyboardInterrupt:
                break

    else:
        # Default: Continuous Hands-Free VAD with 1.65s comfortable pause tolerance
        print("\n✨ [HANDS-FREE VOICE ACTIVATED]")
        print("   • Speak naturally in English.")
        print(f"   • Pause Tolerance: ~{settings.VAD_ENDPOINT_MS / 1000.0:.2f}s pause (you can pause/think without being interrupted).")
        print(f"   • Real-Time Barge-In: {'Enabled' if settings.BARGE_IN_ENABLED else 'Disabled'}")
        print("   • Press Ctrl+C anytime to exit.\n")

        barge_audio = b""
        while True:
            try:
                pcm_bytes = record_continuous_vad(initial_audio=barge_audio)
                barge_audio = b""

                if not pcm_bytes or len(pcm_bytes) < (SAMPLE_RATE * 2 * 0.3):
                    continue

                print("⏳ Transcribing speech via Groq Whisper...")
                t_stt_start = time.perf_counter()
                transcribed_text, is_garbled = await stt_client.transcribe_pcm(pcm_bytes, language="en")
                t_stt = (time.perf_counter() - t_stt_start) * 1000
                print(f"   Transcribed in {t_stt:.1f}ms: '{transcribed_text}'")

                if not transcribed_text or not transcribed_text.strip():
                    continue

                # Semantic Continuation: If transcript ends on an incomplete connector, don't cut off!
                if TRAILING_INCOMPLETE.search(transcribed_text.strip()):
                    print(" ⏳ [MID-THOUGHT PAUSE DETECTED] Holding for continuation...")
                    more_pcm = record_continuous_vad(is_continuation=True, max_wait_seconds=2.5)
                    if more_pcm and len(more_pcm) >= (SAMPLE_RATE * 2 * 0.3):
                        more_text, _ = await stt_client.transcribe_pcm(more_pcm, language="en")
                        if more_text and more_text.strip():
                            transcribed_text = f"{transcribed_text.strip()} {more_text.strip()}"
                            print(f"   Stitched transcript: '{transcribed_text}'")

                if is_garbled:
                    print("⚠️ [ASR TARGETED REPAIR] Flagged fragmented/gibberish audio, asking for clarification...")
                    clarification = "I didn't quite catch that. Could you say it once more?"
                    print(f"\n🌸 MAYA: \"{clarification}\"")
                    pcm = await synthesize_speech_pcm(clarification)
                    play_pcm_audio(pcm, allow_bargein=False)
                    continue

                _, barge_audio = await process_user_turn(transcribed_text, t_stt=t_stt)

            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    print("\nGoodbye! Have a great day.")
    sys.exit(0)
