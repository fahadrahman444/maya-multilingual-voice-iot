import asyncio
from typing import Optional
import edge_tts
import miniaudio

from server.app.config import settings

# Permanent Soft / Alluring Female Voice Profile
DEFAULT_BANGLA_VOICE = settings.TTS_VOICE_BN  # bn-BD-NabanitaNeural
DEFAULT_ENGLISH_VOICE = settings.TTS_VOICE_EN  # en-US-AvaNeural (silky, expressive, modern female)

# Soft & Alluring Acoustic Modulation (slightly lowered pitch, gentle slowed pace)
DEFAULT_BANGLA_PITCH = settings.TTS_PITCH      # -3Hz (warm, velvety resonance)
DEFAULT_ENGLISH_PITCH = "-2Hz"                 # -2Hz (smooth, intimate register)
DEFAULT_RATE = settings.TTS_RATE               # -5% (relaxed, gentle breathing room)


def detect_voice_for_text(text: str) -> tuple[str, str]:
    """
    Detect language and return the optimal neural voice and pitch.
    Returns: (voice_name, pitch)
    """
    has_bangla = any('\u0980' <= char <= '\u09ff' for char in text)
    if has_bangla:
        return DEFAULT_BANGLA_VOICE, DEFAULT_BANGLA_PITCH
    return DEFAULT_ENGLISH_VOICE, DEFAULT_ENGLISH_PITCH


async def synthesize_speech_mp3(
    text: str,
    voice: Optional[str] = None,
    pitch: Optional[str] = None,
    rate: Optional[str] = None,
) -> bytes:
    """
    Synthesize speech using Microsoft Edge TTS with the Soft / Alluring Female acoustic profile.
    Returns raw MP3 audio bytes.
    """
    auto_voice, auto_pitch = detect_voice_for_text(text)
    selected_voice = voice or auto_voice
    selected_pitch = pitch or auto_pitch
    selected_rate = rate or DEFAULT_RATE

    communicate = edge_tts.Communicate(
        text=text,
        voice=selected_voice,
        pitch=selected_pitch,
        rate=selected_rate,
    )

    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])

    return bytes(audio_buffer)


async def synthesize_speech_pcm(
    text: str,
    target_sample_rate: int = 16000,
    voice: Optional[str] = None,
    pitch: Optional[str] = None,
    rate: Optional[str] = None,
) -> bytes:
    """
    Synthesize soft/alluring speech (Bangla or English) and convert into raw 16kHz 16-bit Mono PCM bytes.
    Decoded in-memory using miniaudio with zero external ffmpeg dependencies.
    """
    mp3_bytes = await synthesize_speech_mp3(text, voice=voice, pitch=pitch, rate=rate)
    if not mp3_bytes:
        return b""

    decoded = miniaudio.decode(
        mp3_bytes,
        nchannels=1,
        sample_rate=target_sample_rate,
        output_format=miniaudio.SampleFormat.SIGNED16,
    )
    return decoded.samples.tobytes()
