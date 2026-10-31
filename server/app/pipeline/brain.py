import asyncio
import datetime
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, AsyncGenerator
from google import genai
from google.genai import types as genai_types
from groq import AsyncGroq
from server.app.config import settings
from server.app.pipeline.memory import memory_store
from server.app.pipeline.bengali import (
    normalize_bangla_text,
    detect_language,
    record_flywheel_correction,
)

logger = logging.getLogger(__name__)

BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

# Protection regexes for layered sentence boundary splitter
ABBREV_PATTERN = re.compile(
    r"\b(Dr|Mr|Mrs|Ms|Prof|vs|e\.g|i\.e|etc|St|approx|Jan|Feb|Mar|Apr|Aug|Sept|Oct|Nov|Dec|inc|corp)\.",
    re.IGNORECASE,
)
DECIMAL_PATTERN = re.compile(r"([0-9\u09e6-\u09ef]+)\.([0-9\u09e6-\u09ef]+)")
URL_PATTERN = re.compile(r"([a-zA-Z0-9_-]+)\.([a-zA-Z]{2,6})\b")
ZERO_WIDTH = "\u200b"

# Opening filler scrubber (deterministic post-pass)
FILLER_OPENERS = re.compile(
    r"^(?:great question[,!.]?|sure[,!.]?|i'?d be happy to|as an ai(?: language model)?[,.!]?|certainly[,!.]?|absolutely[,!.]?|let me explain[,.]?)\s*",
    re.IGNORECASE,
)

# Hoisted compiled sentence boundary regex supporting quotes, brackets, and paragraph breaks
SENTENCE_REGEX = re.compile(
    r"([^.!?।॥\n]+(?:[.!?।॥]+[\"'\u201d\u2019\)]*|\n{2,}))(?:\s+)",
    re.UNICODE,
)


@dataclass
class SessionState:
    """Isolated state for an individual conversation session."""
    session_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    preferred_language: Optional[str] = None
    warm_summary: str = ""
    last_active: float = field(default_factory=time.time)


def protect_abbreviations(text: str) -> str:
    """Protect decimals, abbreviations, URLs, and ellipses from premature sentence splitting."""
    t = DECIMAL_PATTERN.sub(lambda m: f"{m.group(1)}{ZERO_WIDTH}{m.group(2)}", text)
    t = ABBREV_PATTERN.sub(lambda m: m.group(0).replace(".", ZERO_WIDTH), t)
    t = URL_PATTERN.sub(lambda m: f"{m.group(1)}{ZERO_WIDTH}{m.group(2)}", t)
    t = re.sub(r"\.{2,}", lambda m: ZERO_WIDTH * len(m.group(0)), t)
    return t


def unprotect(text: str) -> str:
    """Restore protected dots back to periods."""
    return text.replace(ZERO_WIDTH, ".")


def scrub_sentence(text: str, is_first: bool = False) -> str:
    """Strip robotic opening filler and clean up conversational markers."""
    cleaned = text.strip()
    if is_first:
        cleaned = FILLER_OPENERS.sub("", cleaned).strip()
        if cleaned and cleaned[0].isascii() and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


class CircuitBreaker:
    """
    Prevents repeated doomed round-trips to an exhausted or failing provider.
    Transitions: CLOSED -> OPEN (on 3 failures / 429s) -> HALF_OPEN (after 60s cooldown).
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        now = time.monotonic()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.cooldown_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        # HALF_OPEN allows 1 probe
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                print(f"⚠️ [CIRCUIT BREAKER OPEN] Primary provider cooled down for {int(self.cooldown_seconds)}s.")
            self.state = "OPEN"


def get_live_context_prompt() -> str:
    """Generate live real-time clock and date context in both English and Bengali."""
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute

    # Natural Bengali time period
    if 4 <= hour < 6:
        period = "ভোর"
    elif 6 <= hour < 12:
        period = "সকাল"
    elif 12 <= hour < 15:
        period = "দুপুর"
    elif 15 <= hour < 18:
        period = "বিকেল"
    elif 18 <= hour < 20:
        period = "সন্ধ্যা"
    else:
        period = "রাত"

    hour_12 = 12 if hour % 12 == 0 else hour % 12
    hour_bn = str(hour_12).translate(BANGLA_DIGITS)
    minute_bn = str(minute).translate(BANGLA_DIGITS)

    bangla_time_str = f"{period} {hour_bn}টা {minute_bn} মিনিট"
    english_time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%A, %d %B %Y")

    return (
        f"\nLive Real-Time Context:\n"
        f"- Current Local Time (English): {english_time_str}\n"
        f"- Current Local Time (Bengali): {bangla_time_str}\n"
        f"- Current Date: {date_str}\n"
        f"- If the user asks about the time or date, answer accurately."
    )


def get_maya_system_instruction(assistant_name: str = "MAYA") -> str:
    """Generate system instructions customized with identity, persona, language policy, and ASR resilience."""
    lang_mode = settings.LANGUAGE_MODE

    if lang_mode == "always_bn":
        language_rule = "- Language Policy: Always reply exclusively in natural, respectful Bengali (বাংলা)."
    elif lang_mode == "always_en":
        language_rule = "- Language Policy: Always reply exclusively in natural English."
    else:
        language_rule = (
            "- Language Mirroring: Match the user's language, including Bangla and English, and code-switch naturally when the user does.\n"
            "  * If the user speaks English, reply in natural English.\n"
            "  * If the user speaks Bengali, reply in natural Bengali.\n"
            "  * If the user explicitly asks 'in Bangla' or 'in English', honor their request."
        )

    return f"""# {assistant_name} — System Instructions

You are {assistant_name}, an intelligent, natural, Siri-grade multilingual voice assistant. Your personality is warm, thoughtful, brief, and direct—never robotic, never sycophantic.

## Siri-Like Brevity & Voice Rules
- Enforce strict brevity: 1–2 sentences for casual turns (< 30 words), 2–4 sentences max for technical explanations.
- Answer the user's actual question immediately on the first word.
- NEVER open with conversational filler: "Great question!", "Sure!", "I'd be happy to", "Let me explain", or "As an AI".
- NEVER close with unsolicited clinginess: "Hope this helps!", "Anything else?", or "Let me know if you need more info".
- Do not end every turn with a question. Ask at most one simple follow-up question only when genuinely necessary.
- Never use markdown formatting, asterisks, bullet points, or emojis in spoken replies.

## Identity & Greetings
- Your current name is {assistant_name}.
- Follow the application's configured addressing preference (see persistent profile below).
- Natural Greeting & Salam Rules:
  * ONLY reply with "ওয়ালাইকুম আসসালাম" (Wa Alaikum Assalam) IF AND ONLY IF the user explicitly offered Salam ("আসসালামু আলাইকুম" / "Salam" / "Assalamu Alaikum") in their message.
  * If the user greeted with "Hi", "Hello", "Hey", or asks a question without giving Salam, do NOT say "ওয়ালাইকুম আসসালাম". Greet naturally or respond directly to their query.
  * If initiating an Islamic greeting yourself in Bengali, use "আসসালামু আলাইকুম" (never use non-Islamic greetings like "নমস্কার").
  * Do NOT attach a greeting to every message in an ongoing conversation. Answer questions directly without repeating greetings every turn.

## Three-Tier Targeted Error Recovery
- The user's input may contain speech-to-text (ASR) transcription errors or acoustic slips.
- Tier 1 (Single ambiguous token): If an acoustic slip is detected (e.g. 'acid' for 'assist'), reprise with targeted confirmation: e.g. "Did you mean assist?" rather than refusing.
- Tier 2 (Garbled or broken speech): Ask a localized clarification rather than a generic refusal.
- Tier 3 (Total miss): State honestly and briefly: "I didn't quite catch that. Could you say it once more?"
- Clearly harmful requests: Refuse in one direct, non-judgmental sentence: "I cannot help with that. Is there something else I can do for you?" Do not lecture.

## Language Policy
{language_rule}

## Context and Memory
- Respect user corrections and persistent profile facts provided below.
- Never invent a remembered detail.
"""


class ConversationalBrain:
    """
    Production Siri-grade cognitive engine:
    - Layered sentence splitter with abbreviation/decimal protections and 400ms timeout flush.
    - Circuit breaker protecting against exhausted or failing primary LLM.
    - Seamless mid-stream failover if primary terminates unexpectedly.
    - Post-pass filler and length scrubbers.
    - Tiered memory (Hot, Warm, Cold) with 200-token budget cap and contradiction resolution.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        self.provider = (provider or settings.BRAIN_PROVIDER).lower()
        self.gemini_key = gemini_api_key or settings.GEMINI_API_KEY
        self.groq_key = groq_api_key or settings.GROQ_API_KEY

        self._gemini_client: Optional[genai.Client] = None
        self._groq_client: Optional[AsyncGroq] = None

        if self.gemini_key and self.gemini_key != "your_gemini_api_key_here":
            try:
                self._gemini_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                print(f"⚠️ [BRAIN WARNING] Failed to initialize Gemini client: {e}")

        if self.groq_key and self.groq_key != "your_groq_api_key_here":
            try:
                self._groq_client = AsyncGroq(api_key=self.groq_key)
            except Exception as e:
                print(f"⚠️ [BRAIN WARNING] Failed to initialize Groq client: {e}")

        self._sessions: Dict[str, SessionState] = {}
        self.memory = memory_store               # Cold Tier: persistent facts & profile
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

    @property
    def is_configured(self) -> bool:
        return (self._gemini_client is not None) or (self._groq_client is not None)

    def get_session(self, session_id: str = "default") -> SessionState:
        """Retrieve or initialize isolated state for a given session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                warm_summary=self.memory.get_warm_summary() or "",
            )
        session = self._sessions[session_id]
        session.last_active = time.time()
        return session

    @property
    def history(self) -> List[Dict[str, str]]:
        """Active history for default session (backward-compatible view)."""
        return self.get_session("default").history

    @property
    def preferred_language(self) -> Optional[str]:
        return self.get_session("default").preferred_language

    @preferred_language.setter
    def preferred_language(self, lang: Optional[str]):
        self.get_session("default").preferred_language = lang

    def reset_history(self, session_id: Optional[str] = None):
        """Clear session conversation history and warm summary for a specific session (or all)."""
        if session_id:
            if session_id in self._sessions:
                self._sessions[session_id].history.clear()
                self._sessions[session_id].warm_summary = ""
                self._sessions[session_id].preferred_language = None
        else:
            self._sessions.clear()
            self.memory.set_warm_summary("")

    async def aclose(self) -> None:
        """Gracefully release client resources and HTTP connection pools on shutdown."""
        if self._groq_client:
            try:
                await self._groq_client.close()
            except Exception:
                pass

    def _detect_and_record_correction(self, user_text: str) -> None:
        """Detect explicit user profile updates, name changes, or address style preferences."""
        text = normalize_bangla_text(user_text.strip())

        # 1. Address Style: Stop calling me boss
        if re.search(r"\b(?:stop\s+(?:saying|calling\s+me)|don'?t\s+call\s+me)\s+boss\b", text, re.I) or \
           re.search(r"\b(?:বস\s+(?:বলবা\s+না|বলবে\s+না|ডেকো\s+না))\b", text):
            self.memory.set_address_style("name_only")

        # Re-enable boss
        elif re.search(r"\b(?:you\s+can\s+)?call\s+me\s+boss\b", text, re.I) or \
             re.search(r"\b(?:আমাকে\s+বস\s+(?:বলতে\s+পারো|ডাকতে\s+পারো))\b", text):
            self.memory.set_address_style("boss")

        # 2. User Name: "My name is <Name>" or "Call me <Name>" or Bangla "আমার নাম <নাম>"
        m_user_name = re.search(r"\b(?:my\s+name\s+is|call\s+me|i\s+am)\s+([A-Za-z\u0980-\u09ff]{2,20})\b", text, re.I) or \
                      re.search(r"(?:আমার\s+নাম|আমাকে\s+ডেকো)\s+([A-Za-z\u0980-\u09ff]{2,20})", text)
        if m_user_name:
            cand = m_user_name.group(1).strip()
            if cand.lower() not in {"boss", "a", "an", "the", "hungry", "tired", "happy", "fine"}:
                self.memory.set_user_name(cand)

        # 3. Assistant Name change pattern
        m_asst = re.search(r"(?:change your name to|call yourself|your name is now)\s+([A-Za-z0-9\u0980-\u09ff]+)", text, re.I)
        if m_asst:
            new_name = m_asst.group(1).strip()
            self.memory.set_preference("assistant_name", new_name)

        # 4. Explicit Term Corrections: English & Bangla
        # "It's <New>, not <Old>"
        m1 = re.search(
            r"(?:actually\s+|no,\s+)?(?:it's|its|call it)\s+([A-Za-z0-9\u0980-\u09ff\s]{1,35}?),\s*(?:and\s+)?not\s+([A-Za-z0-9\u0980-\u09ff\s]{1,35})",
            text,
            re.I,
        )
        if m1:
            corrected, original = m1.group(1).strip(), m1.group(2).strip()
            self.memory.set_correction(original, corrected)
            record_flywheel_correction(original, corrected, text)
            return

        # "no, not <Old>, it's <New>" (requires explicit correction prefix to avoid matching "I'm not happy, today is bad")
        m2 = re.search(
            r"\b(?:no|wrong)[,\s]+(?:it's\s+)?not\s+([A-Za-z0-9\u0980-\u09ff\s]{1,35}?),\s*(?:it's|its|call it)?\s*([A-Za-z0-9\u0980-\u09ff\s]{1,35})",
            text,
            re.I,
        )
        if m2:
            original, corrected = m2.group(1).strip(), m2.group(2).strip()
            self.memory.set_correction(original, corrected)
            record_flywheel_correction(original, corrected, text)
            return

        # Bangla: "এটা <নতুন>, <পুরাতন> না"
        m3 = re.search(
            r"(?:এটা|ওটা|নামটা)\s+([A-Za-z0-9\u0980-\u09ff\s]{1,35}?),\s*([A-Za-z0-9\u0980-\u09ff\s]{1,35}?)\s+(?:না|নয়)",
            text,
        )
        if m3:
            corrected, original = m3.group(1).strip(), m3.group(2).strip()
            self.memory.set_correction(original, corrected)
            record_flywheel_correction(original, corrected, text)
            return

        # Bangla: "না, <পুরাতন> না, <নতুন>"
        m4 = re.search(
            r"(?:না|ভুল)[,\s]+([A-Za-z0-9\u0980-\u09ff\s]{1,35}?)\s+(?:না|নয়),\s*([A-Za-z0-9\u0980-\u09ff\s]{1,35})",
            text,
        )
        if m4:
            original, corrected = m4.group(1).strip(), m4.group(2).strip()
            self.memory.set_correction(original, corrected)
            record_flywheel_correction(original, corrected, text)

    async def _update_summary_if_needed(self, session: SessionState) -> None:
        """Update Warm Tier summary every 8 turns to keep context compact."""
        if len(session.history) < 8:
            return

        turns_to_summarize = session.history[:-6]
        convo_text = "\n".join(f"{t['role'].capitalize()}: {t['content']}" for t in turns_to_summarize)
        current_warm = session.warm_summary or self.memory.get_warm_summary()

        prompt = (
            "Summarize the key ongoing facts and discussion topics from this conversation into "
            "2 concise bullet points under 40 words:\n\n"
            f"{convo_text}"
        )
        if current_warm:
            prompt = f"Previous Context:\n{current_warm}\n\nRecent History:\n{convo_text}\n\nUpdate into 2 concise bullets:"

        # Attempt summarization via Gemini (free tokens) - do NOT trip voice circuit breaker on background failure
        if self._gemini_client and self.circuit_breaker.can_attempt():
            try:
                res = await self._gemini_client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction="You are a concise conversation context summarizer.",
                        max_output_tokens=75,
                        temperature=0.3,
                    ),
                )
                if res and res.text:
                    session.warm_summary = res.text.strip()
                    self.memory.set_warm_summary(res.text.strip())
                    return
            except Exception as e:
                logger.debug("Background Gemini context summarization skipped: %s", e)

        # Fallback to Groq for background summarization
        if self._groq_client:
            try:
                res = await self._groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a concise conversation context summarizer."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=75,
                    temperature=0.3,
                )
                if res and res.choices and res.choices[0].message.content:
                    summary_text = res.choices[0].message.content.strip()
                    session.warm_summary = summary_text
                    self.memory.set_warm_summary(summary_text)
            except Exception as e:
                logger.debug("Background Groq context summarization skipped: %s", e)

    async def _stream_gemini(self, system_prompt: str, user_text: str) -> AsyncGenerator[str, None]:
        """Stream raw tokens from Google Gemini."""
        if not self._gemini_client:
            return

        contents = []
        for turn in self.history[-6:]:
            role = "model" if turn.get("role") == "assistant" else "user"
            content = turn.get("content", "").strip()
            if content:
                contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=content)]))
        contents.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_text)]))

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.6,
            max_output_tokens=150,
        )

        response = await self._gemini_client.aio.models.generate_content_stream(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_groq(self, system_prompt: str, user_text: str) -> AsyncGenerator[str, None]:
        """Stream raw tokens from Groq."""
        if not self._groq_client:
            return

        messages = [{"role": "system", "content": system_prompt}]
        for turn in self.history[-6:]:
            if turn.get("content", "").strip():
                messages.append({"role": turn["role"], "content": turn["content"].strip()})
        messages.append({"role": "user", "content": user_text})

        response = await self._groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=150,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else ""
            if delta:
                yield delta

    async def generate_reply_sentences(
        self, user_text: str, session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        """
        Layered sentence-boundary streaming generator with:
        - Session isolation keyed by session_id.
        - Buffer-level abbreviation, decimal, URL, and double-danda protection.
        - Per-token streaming timeout (8.0s) with seamless mid-stream failover.
        - 400ms timeout flush to prevent speech stalling.
        - Circuit breaker skipping downed primary.
        - Deterministic post-pass filler scrubbing with zero-drop preservation.
        """
        if not self.is_configured:
            raise ValueError("No LLM API keys configured in server/.env.")

        session = self.get_session(session_id)
        raw_clean = normalize_bangla_text(user_text.strip())

        # Uncertainty handling
        filler_words = {"uh", "um", "ah", "hmm", "hm", "oh", "হুম", "উঁ", "আহ", "ওহ", "ইয়ে"}
        is_uncertain = (not raw_clean) or (len(raw_clean) <= 2 and raw_clean.lower() in filler_words)

        if is_uncertain:
            if session.preferred_language == "bn":
                yield "আমি স্পষ্ট শুনতে পাইনি, আরেকবার বলবেন কি?"
            else:
                yield "I didn't quite catch that, could you please repeat?"
            return

        # Track language
        has_bangla = any('\u0980' <= c <= '\u09ff' for c in raw_clean)
        session.preferred_language = "bn" if has_bangla else "en"

        # Check for profile updates or explicit corrections
        self._detect_and_record_correction(raw_clean)

        current_name = self.memory.get_preference("assistant_name") or "MAYA"
        await self._update_summary_if_needed(session)

        # Build full context
        blocks = [
            get_maya_system_instruction(current_name),
            get_live_context_prompt(),
        ]
        mem = self.memory.format_for_prompt(max_chars=800)
        if mem:
            blocks.append(mem)

        warm_summary = session.warm_summary or self.memory.get_warm_summary()
        if warm_summary:
            blocks.append(f"\nPrior Context Summary:\n{warm_summary}\n")

        full_system_prompt = "\n".join(blocks)

        # Decide initial provider based on circuit breaker
        primary = self.provider
        if primary == "gemini" and not self.circuit_breaker.can_attempt():
            active_provider = "groq"
        else:
            active_provider = primary

        buffer = ""
        full_reply_parts: List[str] = []
        yielded_sentences_count = 0
        last_flush_time = time.monotonic()
        is_first_sentence = True

        async def fetch_tokens(prov: str, custom_prompt: Optional[str] = None):
            user_msg = custom_prompt or raw_clean
            stream_gen = (
                self._stream_gemini(full_system_prompt, user_msg)
                if prov == "gemini"
                else self._stream_groq(full_system_prompt, user_msg)
            )
            while True:
                try:
                    tok = await asyncio.wait_for(stream_gen.__anext__(), timeout=8.0)
                    yield tok
                except StopAsyncIteration:
                    break

        # Attempt stream generation with mid-stream failover
        provider_in_use = active_provider
        stream_success = False

        for attempt in range(2):
            try:
                # If failover mid-stream, prompt fallback to continue gracefully
                custom_user_msg = None
                if attempt > 0 and yielded_sentences_count > 0:
                    already_spoken = " ".join(full_reply_parts).strip()
                    custom_user_msg = (
                        f"The user asked: '{raw_clean}'. "
                        f"You already started answering: '{already_spoken}'. "
                        f"Conclude the thought in 1 concise sentence without repeating:"
                    )

                async for token in fetch_tokens(provider_in_use, custom_user_msg):
                    stream_success = True
                    full_reply_parts.append(token)

                    # Accumulate raw tokens directly into buffer
                    buffer += token
                    now = time.monotonic()

                    # 1. Standard sentence boundary match on protected buffer
                    while True:
                        protected_buffer = protect_abbreviations(buffer)
                        match = SENTENCE_REGEX.match(protected_buffer)
                        if match:
                            raw_sentence = unprotect(match.group(1).strip())
                            buffer = buffer[match.end():]
                            sentence = scrub_sentence(raw_sentence, is_first=is_first_sentence)
                            if sentence:
                                is_first_sentence = False
                                yielded_sentences_count += 1
                                last_flush_time = now
                                yield sentence
                                if yielded_sentences_count >= 4:  # Siri brevity ceiling
                                    buffer = ""
                                    break
                            # If sentence was completely scrubbed (e.g. pure opening filler "Sure!"),
                            # is_first_sentence stays True so the next sentence is properly scrubbed
                        else:
                            break

                    if yielded_sentences_count >= 4:
                        break

                    # 2. Timeout Flush: if no boundary for >400ms and buffer is substantial
                    if (now - last_flush_time >= 0.40 and len(buffer) >= 28) or len(buffer) >= 180:
                        protected_buffer = protect_abbreviations(buffer)
                        clause_match = re.search(r"^(.*?[\,\;\:\—\-])\s+(.*)$", protected_buffer, re.DOTALL)
                        if clause_match:
                            clause_raw = unprotect(clause_match.group(1).strip())
                            buffer = buffer[clause_match.end(1):].lstrip()
                            clause = scrub_sentence(clause_raw, is_first=is_first_sentence)
                            if clause:
                                is_first_sentence = False
                                yielded_sentences_count += 1
                                last_flush_time = now
                                yield clause

                if provider_in_use == "gemini":
                    self.circuit_breaker.record_success()
                break  # Completed successfully

            except Exception as err:
                print(f"\n⚠️ [BRAIN WARNING] Provider '{provider_in_use}' error: {err}")
                if provider_in_use == "gemini":
                    self.circuit_breaker.record_failure()

                # Switch to secondary provider
                provider_in_use = "groq" if provider_in_use == "gemini" else "gemini"
                print(f"🔄 [BRAIN FAILOVER] Resuming via '{provider_in_use}'...")
                last_flush_time = time.monotonic()

        # Flush any remaining buffer text
        trailing = unprotect(protect_abbreviations(buffer.strip()))
        if trailing and yielded_sentences_count < 4:
            trailing_clean = scrub_sentence(trailing, is_first=is_first_sentence)
            if trailing_clean:
                yield trailing_clean

        full_reply = "".join(full_reply_parts).strip()

        # Emergency fallback if all providers completely failed
        if not stream_success or not full_reply:
            fallback_line = (
                "আমি শুনছি, বলুন আপনি কী ভাবছেন?" if session.preferred_language == "bn"
                else "I'm listening, feel free to continue."
            )
            yield fallback_line
            return

        # Update Session history
        session.history.append({"role": "user", "content": raw_clean})
        session.history.append({"role": "assistant", "content": full_reply})

    async def generate_reply(self, user_text: str, session_id: str = "default") -> str:
        """Convenience method returning complete combined response."""
        sentences = []
        async for s in self.generate_reply_sentences(user_text, session_id=session_id):
            sentences.append(s)
        return " ".join(sentences).strip()


brain_engine = ConversationalBrain()
