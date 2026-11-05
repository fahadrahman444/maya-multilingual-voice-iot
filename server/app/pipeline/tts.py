import asyncio
import logging
import re
from typing import Optional, Tuple
import edge_tts
import miniaudio

logger = logging.getLogger(__name__)

from server.app.config import settings

# Edge-TTS Neural Voice Profile (English Ava Neural)
DEFAULT_ENGLISH_VOICE = getattr(settings, "TTS_VOICE_EN", "en-US-AvaNeural") or "en-US-AvaNeural"

MARKDOWN_PATTERN = re.compile(r"(\*\*|__|\*|_|`{1,3}|#{1,6}\s+|^\s*[-*+]\s+)", re.MULTILINE)


def strip_markdown_for_speech(text: str) -> str:
    """Remove markdown symbols so Edge-TTS does not synthesize asterisks, hashes, or code fences."""
    cleaned = MARKDOWN_PATTERN.sub("", text)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    return cleaned


def normalize_text_for_speech(text: str, is_bangla: bool = False) -> str:
    """
    Clean and normalize English text before speech synthesis.
    Strips markdown formatting, repairs accidental token merges, and normalizes punctuation.
    """
    cleaned = strip_markdown_for_speech(text.strip())

    # Fix accidental token boundary merges (e.g. "anincredibly" -> "an incredibly", "itis" -> "it is")
    cleaned = re.sub(r"\b(an)(incredibly|amazing|awesome|exhausting|unbearable|important|enormous|easy)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(it)(is|was|will|can|has)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(and)(it|is|the|we|you|they|in|that)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(that)(is|was|it)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(in)(the|this|that|a|an)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(to)(the|be|do|feel|have)\b", r"\1 \2", cleaned, flags=re.I)

    # Normalize dashes and multiple spaces into clean clause pauses
    cleaned = re.sub(r"\s*--\s*|\s*—\s*", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Hygiene: strip zero-width characters that cause Edge-TTS glitches
    cleaned = cleaned.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return cleaned


def resolve_prosody_parameters(
    is_bangla: bool = False,
    pace_mult: Optional[float] = None,
    expressivity: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Resolve independent Voice Pace and Expressivity settings into Edge-TTS parameters for English speech.
    - Pace (0.8 - 1.2x): Modulates speaking rate ONLY.
    - Expressivity ('low', 'medium', 'high'): Modulates pitch contour and resonance ONLY.
    """
    pace = pace_mult if pace_mult is not None else settings.VOICE_PACE
    expr = (expressivity or settings.VOICE_EXPRESSIVITY).lower()

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
    Synthesize English speech using Microsoft Edge TTS with decoupled pace & prosody.
    Returns raw MP3 audio bytes.
    """
    if not text or not re.search(r"\w", text):
        return b""

    clean_text = normalize_text_for_speech(text)

    if not clean_text or not re.search(r"\w", clean_text):
        return b""

    auto_voice, auto_pitch, auto_rate = resolve_prosody_parameters()
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
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])
    except edge_tts.exceptions.NoAudioReceived:
        return b""
    except Exception as err:
        logger.warning("Edge-TTS synthesis error: %s", err)
        return b""

    return bytes(audio_buffer)


async def synthesize_speech_pcm(
    text: str,
    target_sample_rate: int = 16000,
    voice: Optional[str] = None,
    pitch: Optional[str] = None,
    rate: Optional[str] = None,
) -> bytes:
    """
    Synthesize English speech with prosody control and decode in-memory into 16kHz 16-bit Mono PCM bytes.
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
