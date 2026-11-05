import io
import re
import wave
from typing import Optional, Tuple
from groq import AsyncGroq

from server.app.config import settings
from server.app.pipeline.memory import memory_store

# Domain-informed English conditioning prompt to guide Whisper STT accuracy
DEFAULT_ENGLISH_PROMPT = (
    "English conversation with MAYA, a smart voice assistant. "
    "Smart home IoT controls, device states, and queries: assist, deadlock, operating system, light, fan, switch on, turn off, schedule, timer, weather."
)

# Common meaningful English vocabulary sets to detect acoustic gibberish on short clips
COMMON_EN = {
    "i", "you", "he", "she", "it", "we", "they", "me", "my", "your",
    "hi", "hello", "what", "how", "is", "are", "am", "was", "were", "can", "could", "the", "a", "an", "maya",
    "light", "fan", "turn", "on", "off", "time", "date", "weather", "help", "who", "where", "why", "when",
    "hey", "yes", "no", "ok", "sure", "fine", "please", "thanks", "thank", "switch", "open", "close"
}


def looks_like_real_speech(text: str) -> bool:
    """Heuristic check: returns False if text appears to be acoustic nonsense/fragments."""
    words = [w.strip(",.?!") for w in text.lower().split() if w.strip(",.?!")]
    if not words:
        return False
    if len(words) == 1:
        return len(words[0]) >= 2 and words[0] in COMMON_EN
    meaningful_common = {w for w in COMMON_EN if len(w) > 1}
    has_meaningful = any(w in meaningful_common for w in words)
    short_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
    if short_ratio >= 0.50 and not has_meaningful:
        return False
    return True


# Deterministic phonetic correction map for frequent acoustic misrecognitions
PHONETIC_REPLACEMENTS = [
    (re.compile(r"\b(?:can\s+you\s+)?acid\s+(?:me\s+)?(?:with\s+)?something\b", re.I), "can you assist me with something"),
    (re.compile(r"\bacid\s+something\b", re.I), "assist something"),
    (re.compile(r"\bacid\s+me\b", re.I), "assist me"),
    (re.compile(r"\bcan\s+you\s+acid\b", re.I), "can you assist"),
    (re.compile(r"\bcould\s+you\s+acid\b", re.I), "could you assist"),
    (re.compile(r"\bplease\s+acid\b", re.I), "please assist"),
    (re.compile(r"\bacid\s+with\b", re.I), "assist with"),
]


def repair_transcript(text: str) -> Tuple[str, bool]:
    """
    Repair acoustic transcription errors and detect garbled / low-confidence text.
    Returns: (repaired_text, is_garbled)
    """
    if not text:
        return "", False

    cleaned = text.strip()

    # 1. Phonetic replacement
    for pattern, replacement in PHONETIC_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)

    # 2. Basic whitespace normalization
    cleaned = re.sub(r"\s+", " ", cleaned)

    # 3. Heuristic check for garbled speech fragments
    is_garbled = False
    if not looks_like_real_speech(cleaned):
        is_garbled = True
    else:
        words = cleaned.split()
        if len(words) >= 4:
            meaningful_common = {w for w in COMMON_EN if len(w) > 1}
            short_words = sum(1 for w in words if len(w.strip(",.?!")) <= 2)
            if (short_words / len(words)) >= 0.50 and not any(w.lower().strip(",.?!") in meaningful_common for w in words):
                is_garbled = True

    return cleaned, is_garbled


class WhisperSTT:
    """Ultra-fast Speech-to-Text client using Groq Cloud Whisper Large V3 locked to English."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self._client: Optional[AsyncGroq] = None
        if self.api_key and self.api_key != "your_groq_api_key_here":
            self._client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def _build_context_prompt(self, base_prompt: Optional[str] = None) -> str:
        """Compose conditioning prompt with active corrections from persistent memory."""
        prompt_parts = [base_prompt or DEFAULT_ENGLISH_PROMPT]

        # Dynamically append confirmed user corrections to bias STT accuracy
        corrections = memory_store.get_corrections()
        if corrections:
            correction_terms = list(corrections.values())
            prompt_parts.append("Confirmed terms: " + ", ".join(correction_terms))

        return " ".join(prompt_parts)

    async def transcribe_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        prompt: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> Tuple[str, bool]:
        """
        Transcribe raw 16kHz 16-bit Mono PCM audio to English text.
        Returns: (transcribed_and_repaired_text, is_garbled)
        """
        if not self._client:
            raise ValueError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in server/.env."
            )

        if not pcm_bytes:
            return "", False

        # Wrap raw PCM frames in standard WAV container in-memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        wav_buffer.seek(0)

        # Dispatch to Groq Cloud Whisper API (locked to English for ~150-250ms latency)
        kwargs = {
            "file": ("audio.wav", wav_buffer.read(), "audio/wav"),
            "model": "whisper-large-v3",
            "temperature": 0.0,
            "response_format": "text",
            "prompt": self._build_context_prompt(prompt),
            "language": language or "en",
        }

        raw_text = str(await self._client.audio.transcriptions.create(**kwargs)).strip()
        repaired_text, is_garbled = repair_transcript(raw_text)
        return repaired_text, is_garbled


stt_client = WhisperSTT()
