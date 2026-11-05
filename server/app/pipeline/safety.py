import re
from typing import Optional, NamedTuple
from server.app.config import settings


class SafetyCheckResult(NamedTuple):
    is_crisis: bool
    crisis_category: Optional[str] = None
    override_response: Optional[str] = None


# Regional Emergency & Crisis Helpline Interventions
CRISIS_RESPONSES = {
    "bd": (
        "I hear that you are going through a deeply painful and overwhelming time. "
        "Please know that you are not alone, and your life is truly valuable. "
        "Please reach out right now to a confidential crisis lifeline in Bangladesh: "
        "call Kaan Pete Roi at 01779-554391 or 01779-554392, or dial the National Mental Health Helpline at 16122, "
        "or call 999 for immediate emergency assistance. Compassionate support is available to help you right now."
    ),
    "us": (
        "I hear that you are going through a deeply painful and overwhelming time. "
        "Please know that you are not alone, and your life is truly valuable. "
        "Please reach out right now to a confidential crisis lifeline: "
        "call or text 988 (Suicide & Crisis Lifeline), or contact a local health professional or trusted loved one. "
        "Support is available 24/7."
    ),
    "uk": (
        "I hear that you are going through a deeply painful time. Please know you are not alone. "
        "Please reach out right now to Samaritans at 116 123, or call NHS 111 or 999 for immediate support."
    ),
    "global": (
        "I hear that you are going through a deeply painful time. Please know that you are not alone, and support is available. "
        "Please visit https://findahelpline.com to connect with free, confidential crisis support in your area, "
        "or contact your local emergency services right now."
    ),
}

# Deterministic patterns for suicide, severe self-harm, and extreme acute crisis
CRISIS_PATTERNS = [
    r"\bsuicide\b",
    r"\b(?:kill|killing)\s+myself\b",
    r"\b(?:want|wishing)\s+to\s+die\b",
    r"\b(?:end|ending)\s+(?:my\s+)?life\b",
    r"\b(?:take|taking)\s+my\s+(?:own\s+)?life\b",
    r"\b(?:hurt|hurting)\s+myself\b",
    r"\b(?:better\s+off\s+dead)\b",
    r"\b(?:no\s+reason\s+to\s+live)\b",
    r"\b(?:no\s+point\s+in\s+living)\b",
    r"\b(?:life\s+is\s+not\s+worth\s+living)\b",
    r"\bcan'?t\s+go\s+on\s+living\b",
    r"\bdon'?t\s+want\s+to\s+live\b",
    r"\beveryone\s+(?:would\s+be\s+)?better\s+off\s+without\s+me\b",
    # Legacy patterns caught as safety precaution (Bangla + Banglish)
    r"আত্মহত্যা",
    r"মরতে\s*চাই",
    r"বাঁচতে\s*চাই\s*না",
    r"\bmorte\s*chai\b",
    r"\bbaachte\s*chai\s*na\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]


def get_crisis_response(locale: Optional[str] = None) -> str:
    """Resolve localized crisis response based on configured or detected locale."""
    loc = (locale or getattr(settings, "LOCALE", "bd")).lower()
    return CRISIS_RESPONSES.get(loc, CRISIS_RESPONSES["bd"])


def evaluate_crisis_guardrail(text: str, locale: Optional[str] = None) -> SafetyCheckResult:
    """
    Zero-latency deterministic filter for self-harm and acute mental health crisis.
    Bypasses standard LLM generation to guarantee ethical crisis intervention with localized helplines.
    """
    if not text:
        return SafetyCheckResult(is_crisis=False)

    clean_text = text.strip()
    for pattern in COMPILED_PATTERNS:
        if pattern.search(clean_text):
            return SafetyCheckResult(
                is_crisis=True,
                crisis_category="suicide_or_self_harm",
                override_response=get_crisis_response(locale),
            )

    return SafetyCheckResult(is_crisis=False)
