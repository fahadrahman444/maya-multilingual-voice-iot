import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

# Ensure UTF-8 I/O encoding on Windows consoles
if sys.platform == 'win32':
    try:
        if sys.stdout:
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr:
            sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from server.app.pipeline.tts import synthesize_speech_mp3, synthesize_speech_pcm
from server.app.pipeline.stt import stt_client
from server.app.config import settings


async def main():
    print("=" * 60)
    print("MAYA: Testing Step 2 - Bangla Speech Pipeline (STT & TTS)")
    print("=" * 60)

    test_sentence = "আসসালামু আলাইকুম, আমি মায়া। আপনার মানসিক প্রশান্তির সঙ্গী।"
    print(f"\n[1] Synthesizing Bangla speech via Edge-TTS:")
    print(f"    Text: '{test_sentence}'")
    print(f"    Voice: {settings.TTS_VOICE}")

    start_time = time.perf_counter()
    pcm_bytes = await synthesize_speech_pcm(test_sentence)
    tts_duration = time.perf_counter() - start_time

    audio_len_sec = len(pcm_bytes) / (16000 * 2)
    print(f"    -> Generated {len(pcm_bytes)} PCM bytes ({audio_len_sec:.2f} seconds of audio)")
    print(f"    -> Synthesis Latency: {tts_duration * 1000:.1f} ms")

    # Save audio file to test directory for inspection
    test_out_dir = Path(__file__).parent / "output"
    test_out_dir.mkdir(parents=True, exist_ok=True)
    out_mp3 = test_out_dir / "sample_bangla.mp3"
    mp3_bytes = await synthesize_speech_mp3(test_sentence)
    out_mp3.write_bytes(mp3_bytes)
    print(f"    -> Saved MP3 preview to: {out_mp3.relative_to(root_dir)}")

    print(f"\n[2] Testing Groq Whisper Speech-to-Text (STT):")
    if not stt_client.is_configured:
        print("    [!] GROQ_API_KEY is not configured yet in server/.env.")
        print("    -> TTS passed successfully with zero errors!")
        print("    -> To test transcription, add your free Groq API key to server/.env:")
        print("       GROQ_API_KEY=gsk_...")
    else:
        print("    -> Sending synthesized PCM audio to Groq Whisper Large V3...")
        start_stt = time.perf_counter()
        transcription = await stt_client.transcribe_pcm(pcm_bytes)
        stt_duration = time.perf_counter() - start_stt

        print(f"    -> Transcribed Bangla Text: '{transcription}'")
        print(f"    -> STT Latency: {stt_duration * 1000:.1f} ms")
        print(f"    -> Total Roundtrip Time: {(tts_duration + stt_duration) * 1000:.1f} ms")

    print("\n" + "=" * 60)
    print("Step 2 Core Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
