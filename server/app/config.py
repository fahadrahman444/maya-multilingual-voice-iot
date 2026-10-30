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
    """Central configuration for MAYA gateway server."""

    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Server Network
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    # Speech Synthesis (Edge TTS)
    TTS_VOICE: str = os.getenv("TTS_VOICE", "bn-BD-NabanitaNeural")

    # Audio & VAD Parameters
    SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
    CHANNELS: int = int(os.getenv("CHANNELS", "1"))
    VAD_SILENCE_SECONDS: float = float(os.getenv("VAD_SILENCE_SECONDS", "1.0"))

    def validate_keys(self) -> dict[str, bool]:
        """Check presence of required API keys."""
        return {
            "gemini": bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY != "your_gemini_api_key_here"),
            "groq": bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here"),
        }


settings = Settings()
