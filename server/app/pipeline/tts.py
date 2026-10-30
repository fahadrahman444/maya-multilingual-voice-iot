import asyncio
from typing import Optional
import edge_tts
import miniaudio

from server.app.config import settings


async def synthesize_speech_mp3(text: str, voice: Optional[str] = None) -> bytes:
    """
    Synthesize natural Bangla speech using Microsoft Edge TTS.
    Returns raw MP3 audio bytes.
    """
    selected_voice = voice or settings.TTS_VOICE
    communicate = edge_tts.Communicate(text=text, voice=selected_voice)

    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])

    return bytes(audio_buffer)


async def synthesize_speech_pcm(
    text: str,
    target_sample_rate: int = 16000,
    voice: Optional[str] = None,
) -> bytes:
    """
    Synthesize Bangla speech and convert into raw 16kHz 16-bit Mono PCM bytes.
    Decoded in-memory using miniaudio with zero external ffmpeg dependencies.
    Directly compatible with ESP32 MAX98357A I2S DAC and local PCM playback.
    """
    mp3_bytes = await synthesize_speech_mp3(text, voice)
    if not mp3_bytes:
        return b""

    decoded = miniaudio.decode(
        mp3_bytes,
        nchannels=1,
        sample_rate=target_sample_rate,
        output_format=miniaudio.SampleFormat.SIGNED16,
    )
    return decoded.samples.tobytes()
