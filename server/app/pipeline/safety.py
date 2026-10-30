import re
from typing import Optional, NamedTuple


class SafetyCheckResult(NamedTuple):
    is_crisis: bool
    crisis_category: Optional[str] = None
    override_response: Optional[str] = None


# Verified Bangladeshi Crisis Helpline (Kaan Pete Roi / কান পেতে রই)
KAAN_PETE_ROI_RESPONSE_BN = (
    "আমি বুঝতে পারছি আপনার এই মুহূর্তটি অত্যন্ত কষ্টের ও একাকীত্বের। "
    "দয়া করে মনে রাখবেন, আপনি একা নন এবং আপনার জীবন অত্যন্ত মূল্যবান। "
    "অনুগ্রহ করে এখনই কান পেতে রই (Kaan Pete Roi) মানসিক স্বাস্থ্য হেল্পলাইনে কথা বলুন: "
    "০১৭৭৯-৫৫৪৩৯১ অথবা ০১৭৭৯-৫৫৪৩৯২। তারা সার্বক্ষণিক আপনার কথা শোনার জন্য পাশে আছেন।"
)

KAAN_PETE_ROI_RESPONSE_EN = (
    "I understand you are going through an overwhelming and painful time. "
    "Please know that you are not alone and your life is precious. "
    "Please reach out right now to the Kaan Pete Roi mental health helpline at: "
    "01779-554391 or 01779-554392. Caring listeners are available right now to support you."
)

# Deterministic patterns for suicide, severe self-harm, and extreme crisis
CRISIS_PATTERNS = [
    # Direct Bangla suicide & self-harm
    r"আত্মহত্যা",
    r"মরে\s*(যেতে|যাব|যাওয়ার|যাই)",
    r"মরতে\s*চাই",
    r"বাঁচতে\s*(চাই\s*না|ইচ্ছে\s*করছে\s*না|মন\s*চাইছে\s*না)",
    r"বেঁচে\s*থাকার\s*(কোনো|কোন)\s*(অর্থ|মানে|ইচ্ছা)\s*নেই",
    r"নিজেকে\s*শেষ\s*(করে|দিতে)",
    r"জীবন\s*শেষ\s*(করে|দিতে)",
    r"ফাঁসি\s*(দিব|দেবো|দিতে)",
    r"গলায়\s*দড়ি",
    r"বিষ\s*(খেয়ে|খাব|খেতে)",
    
    # Banglish transliterations
    r"\battahotta\b",
    r"\bmorte\s*chai\b",
    r"\bmore\s*jete\s*chai\b",
    r"\bbachte\s*chai\s*na\b",
    r"\bshesh\s*kore\s*debo\b",
    
    # English keywords
    r"\bsuicide\b",
    r"\bkill\s*myself\b",
    r"\bwant\s*to\s*die\b",
    r"\bend\s*my\s*life\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]


def evaluate_crisis_guardrail(text: str) -> SafetyCheckResult:
    """
    Zero-latency deterministic filter for self-harm and acute mental health crisis.
    Bypasses standard LLM generation to guarantee ethical suicide intervention in both Bangla and English.
    """
    if not text:
        return SafetyCheckResult(is_crisis=False)

    clean_text = text.strip()
    for pattern in COMPILED_PATTERNS:
        if pattern.search(clean_text):
            has_bangla = any('\u0980' <= c <= '\u09ff' for c in clean_text)
            response_text = KAAN_PETE_ROI_RESPONSE_BN if has_bangla else KAAN_PETE_ROI_RESPONSE_EN
            return SafetyCheckResult(
                is_crisis=True,
                crisis_category="suicide_or_self_harm",
                override_response=response_text,
            )

    return SafetyCheckResult(is_crisis=False)
