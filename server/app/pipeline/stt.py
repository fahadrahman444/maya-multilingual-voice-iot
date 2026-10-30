import io
import wave
from typing import Optional
from groq import AsyncGroq

from server.app.config import settings


class WhisperSTT:
    """Ultra-fast Speech-to-Text client using Groq Cloud Whisper Large V3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self._client: Optional[AsyncGroq] = None
        if self.api_key and self.api_key != "your_groq_api_key_here":
            self._client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def transcribe_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        prompt: Optional[str] = None,
    ) -> str:
        """
        Transcribe raw 16kHz 16-bit Mono PCM audio to Bangla text.
        Returns cleaned Bengali text string.
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

        # Dispatch to Groq Cloud Whisper API (typically completes in 200-350ms)
        kwargs = {
            "file": ("audio.wav", wav_buffer.read(), "audio/wav"),
            "model": "whisper-large-v3",
            "language": "bn",
            "temperature": 0.0,
            "response_format": "text",
        }
        if prompt:
            kwargs["prompt"] = prompt

        response = await self._client.audio.transcriptions.create(**kwargs)
        return str(response).strip()


stt_client = WhisperSTT()
