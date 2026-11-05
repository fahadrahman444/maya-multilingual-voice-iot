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

logger = logging.getLogger(__name__)

# Protection regexes for layered sentence boundary splitter
ABBREV_PATTERN = re.compile(
    r"\b(Dr|Mr|Mrs|Ms|Prof|vs|e\.g|i\.e|etc|St|approx|Jan|Feb|Mar|Apr|Aug|Sept|Oct|Nov|Dec|inc|corp)\.",
    re.IGNORECASE,
)
DECIMAL_PATTERN = re.compile(r"([0-9]+)\.([0-9]+)")
URL_PATTERN = re.compile(r"([a-zA-Z0-9_-]+)\.([a-zA-Z]{2,6})\b")
ZERO_WIDTH = "\u200b"

# Opening filler scrubber (deterministic post-pass)
FILLER_OPENERS = re.compile(
    r"^(?:great question[,!.]?|sure[,!.]?|i'?d be happy to|as an ai(?: language model)?[,.!]?|certainly[,!.]?|absolutely[,!.]?|let me explain[,.]?)\s*",
    re.IGNORECASE,
)

# Hoisted compiled sentence boundary regex supporting quotes, brackets, and paragraph breaks
SENTENCE_REGEX = re.compile(
    r"([^.!?\n]+(?:[.!?]+[\"'\u201d\u2019\)]*|\n{2,}))(?:\s+)",
    re.UNICODE,
)

# English fillers split into unambiguous and context-dependent
UNAMBIGUOUS_FILLERS = {
    "uh", "um", "ah", "hmm", "hm", "oh",
}
CONTEXT_DEPENDENT_FILLERS = {"yeah", "yep", "mhm", "huh"}

# Comprehensive stoplist of words that must NEVER be extracted as a user's name
NON_NAME_STOPLIST = {
    "studying", "working", "learning", "trying", "doing", "going", "looking", "feeling",
    "coming", "thinking", "talking", "living", "listening", "waiting", "hoping", "struggling",
    "reading", "writing", "coding", "testing", "student", "engineer", "developer", "tired",
    "sad", "stressed", "happy", "depressed", "fine", "good", "okay", "busy", "hungry",
    "thirsty", "ready", "here", "there", "back", "home", "out", "in", "from", "at",
    "not", "just", "also", "really", "so", "very", "a", "an", "the", "sorry", "sure",
    "glad", "afraid", "worried", "overwhelmed", "scared", "alone", "exhausted", "confused",
    "curious", "interested", "bored", "sleepy", "angry", "upset", "sick", "well", "boss",
    "sir", "madam", "mister", "friend", "bro", "buddy", "pal", "guy", "human", "person",
}


@dataclass
class SessionState:
    """Isolated state for an individual conversation session."""
    session_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    preferred_language: str = "en"
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
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"⚠️ [CIRCUIT BREAKER] Tripped OPEN ({self.failure_count} failures). Cooling down for {self.cooldown_seconds}s.")

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.monotonic() - self.last_failure_time >= self.cooldown_seconds:
                self.state = "HALF_OPEN"
                print("🔄 [CIRCUIT BREAKER] Entering HALF_OPEN test state.")
                return True
            return False
        # HALF_OPEN
        return True


def get_live_context_prompt() -> str:
    """Generate live real-time clock and date context in English."""
    now = datetime.datetime.now()
    english_time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%A, %d %B %Y")

    return (
        f"\nLive Real-Time Context:\n"
        f"- Current Local Time: {english_time_str}\n"
        f"- Current Date: {date_str}\n"
        f"- If the user asks about the time or date, answer accurately."
    )


def get_maya_system_instruction(assistant_name: str = "MAYA") -> str:
    """Generate system instructions customized with identity, persona, Bangladesh context, and safety boundaries."""
    return f"""# {assistant_name} — System Instructions

You are {assistant_name}, an intelligent, natural, Siri-grade English voice assistant and companion. Your personality is warm, thoughtful, brief, and direct—never robotic, never sycophantic.

## Siri-Like Brevity & Voice Rules
- Enforce strict brevity: 1–2 sentences for casual turns (< 30 words), 2–4 sentences max for technical explanations.
- NEVER open with robotic or corporate filler: "Great question!", "Sure!", "I'd be happy to", "Let me explain", or "As an AI".
- NEVER close with unsolicited clinginess: "Hope this helps!", "Anything else?", or "Let me know if you need more info".
- Do not end every turn with a question. Ask at most one simple follow-up question only when genuinely necessary.
- Never use markdown formatting, asterisks, bullet points, or emojis in spoken replies.

## Human Voice Nuance & Natural Vocalizations
- You are speaking aloud through a voice synthesis engine, not typing in a document.
- DO NOT start every response with a vocal marker. Overusing "Ah...", "Hmm...", "Well...", or "Oh..." sounds artificial and repetitive.
- At least 80% of your responses must start directly with your reply without any vocal marker.
- Never use a vocal marker if the previous turn already used one.
- Reserve "Ah..." or "Hmm..." solely for moments of genuine emotional weight, sorrow, or deep reflection. In ordinary turns, answer directly.

## Clinical Boundaries & Healthcare Safety
- You are an AI companion and IoT assistant, NOT a doctor, psychiatrist, or licensed clinical therapist.
- Never diagnose mental or physical illnesses, and never prescribe medical treatments. If asked for diagnosis, gently clarify your role as an AI companion.
- Anti-Dependency Rule: Never encourage a user to rely solely on an AI. In times of stress, gently encourage real-world human support with trusted friends, family, or counselors.

## Empathetic Conversations & Vent Mode
- SPECIFICITY OVER CLICHÉS: Ground your empathy in what the user actually shared (e.g. final-year exams, computer science BSc, tight deadlines, family expectations). Avoid hollow statements like "I am right here with you" without referencing their real context.
- CONTINUITY ACROSS TURNS: If the user suddenly says an unusual or fragmented word (e.g. background noise or smart home terms), do not abruptly abandon the emotional conversation. Acknowledge it gently while keeping the ongoing emotional thread alive.
- WARM, CARING FAREWELL: When concluding a conversation where the user shared sadness, depression, or burnout, do not say a cold "Goodbye! Have a great day." Say a gentle, grounded goodbye: e.g. "Take good care of yourself tonight. I'm right here whenever you want to talk."
- When the user shares personal struggles, sadness, breakups, or burnout, listen with genuine warmth and compassionate stillness.
- No-Advice / Vent Mode: If the user says "I just want to vent", "just listen to me", or asks you not to give advice, DO NOT problem-solve. Provide heartfelt validation and space.
- Avoid Repetitive Validation: Do NOT repeat "I am sorry to hear that" every turn. Use diverse, thoughtful reflections that meet the user where they are.
- Grounding: If the user is feeling intense anxiety or panic, offer a calm, slow grounding reflection.

## Bangladesh Context & Cultural Realities
- You are deployed in Bangladesh (BST / UTC+6). Be culturally attuned to local realities, universities, exams, and daily life while communicating fluently in natural English.
- If an emergency or severe crisis is detected, crisis resources in Bangladesh include Kaan Pete Roi (01779-554391 / 01779-554392), National Mental Health Helpline (16122), and emergency 999.

## Identity & Persona
- Your name is {assistant_name}.
- Speak in clear, natural English.
- Greet naturally and politely (e.g. "Hi", "Hello", "Hey") only when greeted, never repetitively every turn.
- NEVER use unsolicited titles, honorifics, or nicknames like "boss", "sir", "buddy", or "pal" unless explicitly requested by the user.

## Strict English Language Policy
- You operate strictly and solely in English.
- Always reply exclusively in natural English.
- Even if the user communicates in another language, always respond naturally and solely in English.

## Three-Tier Targeted Error Recovery
- The user's input may contain speech-to-text (ASR) transcription errors or acoustic slips.
- Tier 1 (Single ambiguous token): If an acoustic slip is detected (e.g. 'acid' for 'assist'), reprise with targeted confirmation: e.g. "Did you mean assist?" rather than refusing.
- Tier 2 (Garbled or broken speech): Ask a localized clarification rather than a generic refusal.
- Tier 3 (Total miss): State honestly and briefly: "I didn't quite catch that. Could you say it once more?"
- Clearly harmful requests: Refuse in one direct, non-judgmental sentence: "I cannot help with that. Is there something else I can do for you?" Do not lecture.

## Context and Memory
- Respect user corrections and persistent profile facts provided below.
- Never invent a remembered detail.
"""


class ConversationalBrain:
    """
    Production Siri-grade cognitive engine (English):
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

        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
        self.sessions: Dict[str, SessionState] = {}
        self.memory = memory_store

    @property
    def is_configured(self) -> bool:
        return (self._gemini_client is not None) or (self._groq_client is not None)

    def get_session(self, session_id: str = "default") -> SessionState:
        now = time.time()
        # Session cleanup: remove inactive sessions older than 4 hours
        stale = [sid for sid, s in self.sessions.items() if (now - s.last_active) > 14400 and sid != "default"]
        for sid in stale:
            del self.sessions[sid]

        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id=session_id)
        session = self.sessions[session_id]
        session.last_active = now
        return session

    @property
    def history(self) -> List[Dict[str, str]]:
        return self.get_session("default").history

    def reset_history(self, session_id: Optional[str] = None) -> None:
        if session_id:
            if session_id in self.sessions:
                self.sessions[session_id].history.clear()
        else:
            for s in self.sessions.values():
                s.history.clear()

    async def aclose(self) -> None:
        """Gracefully release client resources and HTTP connection pools on shutdown."""
        if self._groq_client:
            try:
                await self._groq_client.close()
            except Exception:
                pass

    def _detect_and_record_correction(self, user_text: str) -> None:
        """Detect explicit user profile updates, name changes, address preferences, episodic events, or privacy forget commands."""
        text = user_text.strip()

        # 0. Privacy & Consent: Granular & Complete Forget commands
        if re.search(r"\b(?:forget\s+(?:everything|all(?:\s+my)?\s+data)|clear\s+(?:my\s+)?memory)\b", text, re.I):
            self.memory.clear_all()
            return

        if re.search(r"\bforget\s+my\s+name\b", text, re.I):
            self.memory.forget_profile("user_name")
            return

        m_forget_topic = re.search(r"\bforget\s+(?:about\s+)?(?:the\s+|my\s+)?([a-zA-Z\s]{3,30}?)(?:\.|\?|$)", text, re.I)
        if m_forget_topic:
            topic = m_forget_topic.group(1).strip().lower()
            if topic not in {"what", "that", "this", "it", "something", "everything"}:
                self.memory.forget_episode(topic)
                self.memory.forget_fact(topic)
                return

        # 1. Address Style: Stop calling me boss
        if re.search(r"\b(?:stop\s+(?:saying|calling\s+me)|don'?t\s+call\s+me)\s+boss\b", text, re.I):
            self.memory.set_address_style("name_only")
        elif re.search(r"\b(?:you\s+can\s+)?call\s+me\s+boss\b", text, re.I):
            self.memory.set_address_style("boss")

        # 2. User Name: "My name is <Name>" or "Call me <Name>" (Hardened against verbs/participles)
        m_user_name = re.search(r"\b(?:my\s+name\s+is|call\s+me)\s+([A-Za-z]{2,20})\b", text, re.I)
        if not m_user_name:
            # Only match "I am <Name>" if explicitly Capitalized and NOT a participle/verb/adjective
            m_iam = re.search(r"\b(?:i\s+am|i'm)\s+([A-Z][a-z]{1,20})\b", text)
            if m_iam:
                c_cand = m_iam.group(1).strip()
                if not c_cand.lower().endswith(("ing", "ed", "ly", "able", "ful", "less", "est", "er")):
                    if c_cand.lower() not in NON_NAME_STOPLIST:
                        m_user_name = m_iam

        if m_user_name:
            cand = m_user_name.group(1).strip()
            if cand.lower() not in NON_NAME_STOPLIST and not cand.lower().endswith(("ing", "ed", "ly", "able", "ful", "less", "est", "er")):
                self.memory.set_user_name(cand)

        # 3. Assistant Name change pattern
        m_asst = re.search(r"(?:change your name to|call yourself|your name is now)\s+([A-Za-z0-9]+)", text, re.I)
        if m_asst:
            new_name = m_asst.group(1).strip()
            self.memory.set_preference("assistant_name", new_name)

        # 4. Explicit Term Corrections
        # "It's <New>, not <Old>"
        m1 = re.search(
            r"(?:actually\s+|no,\s+)?(?:it's|its|call it)\s+([A-Za-z0-9\s]{1,35}?),\s*(?:and\s+)?not\s+([A-Za-z0-9\s]{1,35})",
            text,
            re.I,
        )
        if m1:
            corrected, original = m1.group(1).strip(), m1.group(2).strip()
            self.memory.set_correction(original, corrected)
            return

        # "no, not <Old>, it's <New>"
        m2 = re.search(
            r"\b(?:no|wrong)[,\s]+(?:it's\s+)?not\s+([A-Za-z0-9\s]{1,35}?),\s*(?:it's|its|call it)?\s*([A-Za-z0-9\s]{1,35})",
            text,
            re.I,
        )
        if m2:
            original, corrected = m2.group(1).strip(), m2.group(2).strip()
            self.memory.set_correction(original, corrected)
            return

        # 5. Episodic Life Event Extraction
        if re.search(r"\b(?:broke\s+up|breakup|split\s+up|ended\s+(?:things|relationship))\b", text, re.I):
            self.memory.add_episode("Going through a breakup with partner", valence="negative", sensitivity="sensitive")
        elif re.search(r"\b(?:exam|midterm|final\s+exam)\s+(?:tomorrow|next\s+week|coming\s+up)\b", text, re.I):
            self.memory.add_episode("Has an upcoming academic exam", valence="neutral", sensitivity="personal")
        elif re.search(r"\b(?:got\s+a\s+new\s+job|started\s+a\s+new\s+job|hired\s+at)\b", text, re.I):
            self.memory.add_episode("Started a new job", valence="positive", sensitivity="personal")

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

        response = await self._gemini_client.aio.models.generate_content_stream(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=150,
            ),
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_groq(self, system_prompt: str, user_text: str) -> AsyncGenerator[str, None]:
        """Stream raw tokens from Groq Cloud."""
        if not self._groq_client:
            return

        messages = [{"role": "system", "content": system_prompt}]
        for turn in self.history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_text})

        stream = await self._groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=150,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content if chunk.choices else None
            if content:
                yield content

    async def generate_reply_sentences(
        self,
        user_text: str,
        session_id: str = "default",
    ) -> AsyncGenerator[str, None]:
        """
        Streaming cognitive response generation (Strictly English).
        Yields scrubbed sentences one-by-one as soon as formed.
        """
        if not self.is_configured:
            raise ValueError("No LLM API keys configured in server/.env.")

        session = self.get_session(session_id)
        raw_clean = user_text.strip()

        # Determine last assistant utterance to distinguish affirmatives from hesitations
        last_assistant_turn = None
        for turn in reversed(session.history):
            if turn.get("role") == "assistant":
                last_assistant_turn = turn.get("content", "")
                break

        # Uncertainty handling with English filler sets
        lowered_clean = raw_clean.lower().strip(" .!?।,")
        if not raw_clean:
            is_uncertain = True
        elif lowered_clean in UNAMBIGUOUS_FILLERS:
            is_uncertain = True
        elif lowered_clean in CONTEXT_DEPENDENT_FILLERS:
            ends_with_q = (last_assistant_turn or "").rstrip().endswith("?")
            is_uncertain = not ends_with_q
        else:
            is_uncertain = False

        if is_uncertain:
            yield "I didn't quite catch that, could you please repeat?"
            return

        # Transparent Memory Inspection: "What do you remember about me?"
        if re.search(r"\bwhat\s+do\s+you\s+(?:remember|know)\s+about\s+me\b", raw_clean, re.I):
            mem_summary = self.memory.get_summary_of_memory()
            session.history.append({"role": "user", "content": raw_clean})
            session.history.append({"role": "assistant", "content": mem_summary})
            yield mem_summary
            return

        # Explicit updates, episodes, or preferences
        self._detect_and_record_correction(raw_clean)

        current_name = self.memory.get_preference("assistant_name") or "MAYA"
        await self._update_summary_if_needed(session)

        # Build full context with Query-Conditioned Scored Memory Retrieval
        blocks = [
            get_maya_system_instruction(current_name),
            get_live_context_prompt(),
        ]
        mem = self.memory.format_for_prompt(query=raw_clean, max_chars=800)
        if mem:
            blocks.append(mem)

        full_system_prompt = "\n\n".join(blocks)

        # Determine primary and failover providers
        active_provider = self.provider
        if active_provider == "gemini" and not self.circuit_breaker.can_attempt():
            if self._groq_client:
                print("⚡ [CIRCUIT BREAKER ACTIVE] Primary Gemini circuit open -> auto routing to Groq.")
                active_provider = "groq"
            else:
                active_provider = "gemini"

        buffer = ""
        is_first_sentence = True
        yielded_sentences_count = 0
        last_flush_time = time.monotonic()
        full_reply_parts = []

        async def fetch_tokens(prov: str, custom_prompt: Optional[str] = None):
            user_msg = custom_prompt or raw_clean
            stream_gen = (
                self._stream_gemini(full_system_prompt, user_msg)
                if prov == "gemini"
                else self._stream_groq(full_system_prompt, user_msg)
            )
            is_first_tok = True
            while True:
                try:
                    # TTFT Watchdog: If Gemini stalls > 5.0s on first token, trip circuit & fail over to Groq immediately
                    first_token_timeout = 5.0 if (prov == "gemini" and is_first_tok and self._groq_client) else 10.0
                    tok = await asyncio.wait_for(stream_gen.__anext__(), timeout=first_token_timeout)
                    is_first_tok = False
                    yield tok
                except StopAsyncIteration:
                    break

        # Attempt stream generation with mid-stream failover
        provider_in_use = active_provider
        stream_success = False

        for attempt in range(2):
            try:
                custom_user_msg = None
                if attempt > 0 and yielded_sentences_count > 0:
                    already_spoken = " ".join(full_reply_parts).strip()
                    custom_user_msg = (
                        f"The user asked: '{raw_clean}'. "
                        f"You already started answering: '{already_spoken}'. "
                        f"Conclude the thought in 1 concise English sentence without repeating:"
                    )

                async for token in fetch_tokens(provider_in_use, custom_user_msg):
                    stream_success = True
                    full_reply_parts.append(token)

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
                            if sentence and re.search(r"\w", sentence):
                                is_first_sentence = False
                                yielded_sentences_count += 1
                                last_flush_time = now
                                yield sentence
                                if yielded_sentences_count >= 4:  # Siri brevity ceiling
                                    buffer = ""
                                    break
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
                            if clause and re.search(r"\w", clause):
                                is_first_sentence = False
                                last_flush_time = now
                                yield clause

                if provider_in_use == "gemini":
                    self.circuit_breaker.record_success()
                break  # Completed successfully

            except Exception as err:
                print(f"\n⚠️ [BRAIN WARNING] Provider '{provider_in_use}' error: {repr(err)}")
                if provider_in_use == "gemini":
                    self.circuit_breaker.record_failure()

                provider_in_use = "groq" if provider_in_use == "gemini" else "gemini"
                print(f"🔄 [BRAIN FAILOVER] Resuming via '{provider_in_use}'...")
                last_flush_time = time.monotonic()

        # Flush any remaining buffer text
        trailing = unprotect(protect_abbreviations(buffer.strip()))
        if trailing:
            trailing_clean = scrub_sentence(trailing, is_first=is_first_sentence)
            if trailing_clean and re.search(r"\w", trailing_clean):
                yield trailing_clean

        full_reply = "".join(full_reply_parts).strip()

        # Emergency fallback if all providers completely failed
        if not stream_success or not full_reply:
            yield "I'm listening, feel free to continue."
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
