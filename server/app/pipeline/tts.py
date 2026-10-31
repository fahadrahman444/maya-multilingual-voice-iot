import asyncio
import re
from typing import Optional, Tuple
import edge_tts
import miniaudio

from server.app.config import settings
from server.app.pipeline.memory import memory_store
from server.app.pipeline.bengali import normalize_bangla_text, apply_pronunciation_lexicon

# Edge-TTS Neural Voice Profiles
DEFAULT_BANGLA_VOICE = settings.TTS_VOICE_BN  # bn-BD-NabanitaNeural
DEFAULT_ENGLISH_VOICE = settings.TTS_VOICE_EN  # en-US-AvaNeural

BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
MARKDOWN_PATTERN = re.compile(r"(\*\*|__|\*|_|`{1,3}|#{1,6}\s+|^\s*[-*+]\s+)", re.MULTILINE)


def strip_markdown_for_speech(text: str) -> str:
    """Remove markdown symbols so Edge-TTS does not synthesize asterisks, hashes, or code fences."""
    cleaned = MARKDOWN_PATTERN.sub("", text)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    return cleaned


def normalize_text_for_speech(text: str, is_bangla: bool) -> str:
    """
    Clean and normalize text before speech synthesis.
    Converts ASCII digits to Bengali digits in Bangla sentences to prevent phonetic glitches.
    Inserts clean micro-pause commas at conjunctions.
    Strips markdown formatting.
    """
    cleaned = strip_markdown_for_speech(text.strip())

    # Normalize Bengali Unicode, dynamic pronunciation corrections, and digits
    if is_bangla:
        cleaned = cleaned.translate(BANGLA_DIGITS)
        cleaned = normalize_bangla_text(cleaned)
        corrections = memory_store.get_corrections() if memory_store else None
        cleaned = apply_pronunciation_lexicon(cleaned, corrections)

    # Normalize dashes and multiple spaces into clean clause pauses
    cleaned = re.sub(r"\s*--\s*|\s*—\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def resolve_prosody_parameters(
    is_bangla: bool,
    pace_mult: Optional[float] = None,
    expressivity: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Resolve independent Voice Pace and Expressivity settings into Edge-TTS parameters.
    - Pace (0.8 - 1.2x): Modulates speaking rate ONLY.
    - Expressivity ('low', 'medium', 'high'): Modulates pitch contour and resonance ONLY.
    """
    pace = pace_mult if pace_mult is not None else settings.VOICE_PACE
    expr = (expressivity or settings.VOICE_EXPRESSIVITY).lower()

    if is_bangla:
        voice = DEFAULT_BANGLA_VOICE
        # Bangla natural melody is slightly gentler (~0.94x baseline)
        effective_pace = pace * 0.94
        rate_diff = int(round((effective_pace - 1.0) * 100))
        rate_str = f"{rate_diff:+d}%"

        # Expressivity pitch modulation
        if expr == "high":
            pitch_str = "-4Hz"
        elif expr == "low":
            pitch_str = "+0Hz"
        else:
            pitch_str = "-3Hz"  # Medium warm resonance
    else:
        voice = DEFAULT_ENGLISH_VOICE
        effective_pace = pace
        rate_diff = int(round((effective_pace - 1.0) * 100))
        rate_str = f"{rate_diff:+d}%"

        if expr == "high":
            pitch_str = "-3Hz"
        elif expr == "low":
            pitch_str = "+0Hz"
        else:
            pitch_str = "-2Hz"  # Modern smooth register

    return voice, pitch_str, rate_str


async def synthesize_speech_mp3(
    text: str,
    voice: Optional[str] = None,
    pitch: Optional[str] = None,
    rate: Optional[str] = None,
) -> bytes:
    """
    Synthesize speech using Microsoft Edge TTS with decoupled pace & prosody.
    Returns raw MP3 audio bytes.
    """
    has_bangla = any('\u0980' <= c <= '\u09ff' for c in text)
    clean_text = normalize_text_for_speech(text, is_bangla=has_bangla)

    auto_voice, auto_pitch, auto_rate = resolve_prosody_parameters(is_bangla=has_bangla)
    selected_voice = voice or auto_voice
    selected_pitch = pitch or auto_pitch
    selected_rate = rate or auto_rate

    communicate = edge_tts.Communicate(
        text=clean_text,
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
    Synthesize speech with prosody control and decode in-memory into 16kHz 16-bit Mono PCM bytes.
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
