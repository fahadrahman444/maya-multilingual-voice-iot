from typing import List, Dict, Optional
from groq import AsyncGroq
from server.app.config import settings

MAYA_SYSTEM_INSTRUCTION = """
You are "MAYA" (মায়া), an emotionally intelligent, empathetic Bengali voice assistant and mental wellness companion.

Core Guidelines:
1. Language & Persona:
   - Primary language: Standard spoken Bangla (বাংলা). You can also understand Banglish and English, but always respond primarily in warm, natural Bengali.
   - Always address the user with respectful Bengali honorifics ("আপনি", "আপনার"). Never use "তুমি" or "তুই".
   - Your tone is calm, soothing, validating, and compassionate (CBT-aligned active listening).

2. Speech-Friendly Brevity:
   - Your responses will be read aloud via Text-to-Speech (TTS).
   - Keep responses concise: 1 to 2 natural, clear sentences (under 40 words) so voice playback is immediate and not overwhelming.
   - Avoid long bullet points, asterisks, Markdown formatting, or tables in your spoken responses.

3. Emotional Support:
   - If the user expresses sadness, exhaustion, or loneliness, validate their feelings genuinely (e.g., "আমি বুঝতে পারছি আপনার সময়টা কঠিন যাচ্ছে...").
   - Offer gentle grounding encouragement (e.g., taking a calm breath, resting, or drinking water).
   - Never give formal medical diagnoses.
"""


class ConversationalBrain:
    """Cognitive conversation engine powered by Groq ultra-fast LLM with fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = "qwen/qwen3.8-27b"
        self._groq_client: Optional[AsyncGroq] = None
        self.history: List[Dict[str, str]] = []

        if self.api_key and self.api_key != "your_groq_api_key_here":
            self._groq_client = AsyncGroq(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        return self._groq_client is not None

    def reset_history(self):
        """Clear conversation history."""
        self.history.clear()

    async def generate_reply(self, user_text: str) -> str:
        """Generate empathetic spoken response using ultra-fast LLM (<500ms)."""
        if not self._groq_client:
            raise ValueError("GROQ_API_KEY is not configured in server/.env.")

        if not user_text.strip():
            return "আমি আপনার কথা স্পষ্ট শুনতে পাইনি, দয়া করে আবার বলবেন কি?"

        # Build message history for multi-turn context
        messages = [{"role": "system", "content": MAYA_SYSTEM_INSTRUCTION}]
        for turn in self.history[-6:]:  # Keep last 3 exchanges (6 turns)
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_text})

        response = await self._groq_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.6,
            max_tokens=150,
        )

        reply = response.choices[0].message.content.strip() if response.choices else "আমি বুঝতে পারছি। আপনি কেমন অনুভব করছেন?"

        # Update history
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})

        return reply


brain_engine = ConversationalBrain()
