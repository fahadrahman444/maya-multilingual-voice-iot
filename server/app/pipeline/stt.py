import io
import wave
from typing import Optional
from groq import AsyncGroq

from server.app.config import settings
from server.app.pipeline.memory import memory_store

# Bilingual conditioning prompt to guide Whisper towards accurate English, Bangla & Banglish speech
DEFAULT_MULTILINGUAL_PROMPT = (
    "Hello Maya, how are you? What time is it now? "
    "মায়া একটি বহুভাষিক বাংলা ও ইংরেজি এআই ভয়েস অ্যাসিস্ট্যান্ট। "
    "আসসালামু আলাইকুম মায়া, আপনি কেমন আছেন? এখন কয়টা বাজে তুমি কি বলতে পারবা? "
    "Turn on the lights, switch off the fan."
)


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

        # Dynamically append confirmed user corrections (e.g. Pizza Barg) to bias STT accuracy
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
    ) -> str:
        """
        Transcribe raw 16kHz 16-bit Mono PCM audio to text (Bangla, English, or mixed).
        When language is None, Whisper automatically detects the spoken language.
        """
        if not self._client:
            raise ValueError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in server/.env."
            )

        if not pcm_bytes:
            return ""

        # Wrap raw PCM frames in standard WAV container in-memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        wav_buffer.seek(0)

        # Dispatch to Groq Cloud Whisper API with automatic language detection and correction bias
        kwargs = {
            "file": ("audio.wav", wav_buffer.read(), "audio/wav"),
            "model": "whisper-large-v3",
            "temperature": 0.0,
            "response_format": "text",
            "prompt": self._build_context_prompt(prompt),
        }
        if language:
            kwargs["language"] = language

        response = await self._client.audio.transcriptions.create(**kwargs)
        return str(response).strip()


stt_client = WhisperSTT()
