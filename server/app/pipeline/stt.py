import io
import re
import wave
from typing import Optional, Tuple
from groq import AsyncGroq

from server.app.config import settings
from server.app.pipeline.memory import memory_store
from server.app.pipeline.bengali import normalize_bangla_text

# Domain-informed bilingual conditioning prompt to guide Whisper STT accuracy
DEFAULT_MULTILINGUAL_PROMPT = (
    "Bangla and English conversation. Common words: assist, deadlock, operating system, "
    "mutual exclusion, hold and wait, no preemption, circular wait, Fahad, MAYA. "
    "হ্যালো মায়া, কেমন আছেন? কী সাহায্য করতে পারেন? আসসালামু আলাইকুম। "
    "Turn on the lights, switch off the fan."
)

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

    # 2. Bengali Unicode normalization pass
    cleaned = normalize_bangla_text(cleaned)

    # 3. Heuristic check for garbled speech fragments
    # Common pattern: fragmented isolated Bangla vowels or broken syllables like "আ, গাটিট, এই এক্সলেন েল"
    words = cleaned.split()
    is_garbled = False
    if len(words) >= 4:
        # Check if many words are single/two-character isolated fragments (e.g. >= 50%)
        short_words = sum(1 for w in words if len(w.strip(",.?!")) <= 2)
        if (short_words / len(words)) >= 0.50:
            is_garbled = True

    return cleaned, is_garbled


class WhisperSTT:
    """Ultra-fast Speech-to-Text client using Groq Cloud Whisper Large V3 with automatic language detection."""

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
        prompt_parts = [base_prompt or DEFAULT_MULTILINGUAL_PROMPT]

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
        language: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Transcribe raw 16kHz 16-bit Mono PCM audio to text (Bangla, English, or mixed).
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

        # Dispatch to Groq Cloud Whisper API
        kwargs = {
            "file": ("audio.wav", wav_buffer.read(), "audio/wav"),
            "model": "whisper-large-v3",
            "temperature": 0.0,
            "response_format": "text",
            "prompt": self._build_context_prompt(prompt),
        }
        if language:
            kwargs["language"] = language

        raw_text = str(await self._client.audio.transcriptions.create(**kwargs)).strip()
        repaired_text, is_garbled = repair_transcript(raw_text)
        return repaired_text, is_garbled


stt_client = WhisperSTT()
