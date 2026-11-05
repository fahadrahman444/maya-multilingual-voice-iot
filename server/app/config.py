import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Search for .env in server/ or project root
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
root_dir = server_dir.parent

env_paths = [server_dir / ".env", root_dir / ".env"]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()  # Default fallback


class Settings:
    """Central configuration for MAYA English voice gateway server."""

    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Language Policy - Strictly English
    LANGUAGE_MODE: str = os.getenv("LANGUAGE_MODE", "always_en").lower()

    # Regional Locale & Crisis Directory ("bd" | "us" | "uk" | "global")
    LOCALE: str = os.getenv("LOCALE", "bd").lower()

    # Cognitive Brain Provider ("gemini" for free unlimited tokens, "groq" for sub-second latency)
    BRAIN_PROVIDER: str = os.getenv("BRAIN_PROVIDER", "gemini").lower()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    # Server Network
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    # Voice Prosody & Turn-Taking Specifications
    VOICE_PACE: float = float(os.getenv("VOICE_PACE", "1.0"))             # 0.8 to 1.2 rate multiplier
    VOICE_EXPRESSIVITY: str = os.getenv("VOICE_EXPRESSIVITY", "medium")   # low | medium | high
    VAD_ENDPOINT_MS: int = int(os.getenv("VAD_ENDPOINT_MS", "1650"))      # 1.65s comfortable pause tolerance
    BARGE_IN_ENABLED: bool = os.getenv("BARGE_IN_ENABLED", "True").lower() in ("true", "1")

    # Speech Synthesis (Edge TTS) - English Voice Profile (Ava Neural)
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-AvaNeural")
    TTS_VOICE_EN: str = os.getenv("TTS_VOICE_EN", "en-US-AvaNeural")
    TTS_PITCH: str = os.getenv("TTS_PITCH", "-2Hz")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")

    # Audio & VAD Parameters
    SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
    CHANNELS: int = int(os.getenv("CHANNELS", "1"))
    VAD_SILENCE_SECONDS: float = float(os.getenv("VAD_SILENCE_SECONDS", "1.65"))

    def validate_keys(self) -> dict[str, bool]:
        """Check presence of required API keys."""
        return {
            "gemini": bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY != "your_gemini_api_key_here"),
            "groq": bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here"),
        }


settings = Settings()
