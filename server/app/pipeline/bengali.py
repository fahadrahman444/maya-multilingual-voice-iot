"""Bengali language processing, Unicode normalization, and pronunciation utilities."""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try importing bnunicodenormalizer; fallback cleanly if unavailable
try:
    from bnunicodenormalizer import Normalizer as _BnNormalizer
    _bn_norm: Optional[_BnNormalizer] = _BnNormalizer()
except Exception as e:
    logger.warning("bnunicodenormalizer not available: %s", e)
    _bn_norm = None

_SERVER_ROOT = Path(__file__).resolve().parent.parent.parent
_FLYWHEEL_PATH = _SERVER_ROOT / "data" / "correction_flywheel.jsonl"
_FLYWHEEL_LOCK = threading.Lock()

# Curated pronunciation adjustments for Edge-TTS Bengali voice
DEFAULT_PRONUNCIATION_LEXICON: dict[str, str] = {
    # Tech terms in Bengali phonetic transliteration that TTS mispronounces
    "ডেডলক": "ডেড-লক",
    "রিসেট": "রি-সেট",
    "লগইন": "লগ-ইন",
    "লগআউট": "লগ-আউট",
    "সফটওয়্যার": "সফট-ওয়্যার",
    "হার্ডওয়্যার": "হার্ড-ওয়্যার",
    "অ্যালগরিদম": "অ্যালগোরিদম",
}


def normalize_bangla_text(text: str) -> str:
    """
    Standardize Bengali Unicode characters to eliminate multi-byte encoding mismatches.
    Applies Unicode NFC normalization followed by token-level bnunicodenormalizer.
    Preserves all whitespace, newlines, and punctuation.
    """
    if not text:
        return ""

    # Step 1: Standard NFC Unicode canonical composition
    text = unicodedata.normalize("NFC", text)

    # If text has no Bengali code points, skip word-level normalizer
    if not any("\u0980" <= c <= "\u09ff" for c in text):
        return text

    if _bn_norm is None:
        return text

    # Split preserving whitespace tokens
    parts = re.split(r"(\s+)", text)
    normalized_parts = []
    for part in parts:
        if not part or part.isspace():
            normalized_parts.append(part)
            continue
        # Only normalize tokens with Bengali chars and without ASCII alphanumeric characters
        # to prevent bnunicodenormalizer from stripping English words, code, or ASCII numbers
        if not any("\u0980" <= c <= "\u09ff" for c in part) or re.search(r"[a-zA-Z0-9]", part):
            normalized_parts.append(part)
            continue
        try:
            res = _bn_norm(part)
            norm_val = res.get("normalized") if isinstance(res, dict) else None
            normalized_parts.append(norm_val if norm_val else part)
        except Exception:
            normalized_parts.append(part)

    return "".join(normalized_parts)


def detect_language(text: str) -> str:
    """
    Classify text language into 'bn', 'en', 'mixed', or 'unknown'.
    """
    if not text or not text.strip():
        return "unknown"

    has_bn = any("\u0980" <= c <= "\u09ff" for c in text)
    has_en = any("a" <= c.lower() <= "z" for c in text)

    if has_bn and has_en:
        return "mixed"
    if has_bn:
        return "bn"
    if has_en:
        return "en"
    return "unknown"


def apply_pronunciation_lexicon(
    text: str, custom_lexicon: Optional[dict[str, str]] = None
) -> str:
    """
    Apply phonetic corrections for Edge-TTS speech synthesis.
    Merges custom dynamic corrections with DEFAULT_PRONUNCIATION_LEXICON.
    """
    if not text:
        return ""

    lexicon = dict(DEFAULT_PRONUNCIATION_LEXICON)
    if custom_lexicon:
        lexicon.update(custom_lexicon)

    result = text
    for word, phonetic in lexicon.items():
        if word in result:
            result = result.replace(word, phonetic)

    return result


def record_flywheel_correction(
    original: str, corrected: str, user_text: str = ""
) -> None:
    """
    Append an acoustic or term correction to the flywheel log for continual retraining.
    Zero-blocking file append protected with a process-level thread lock.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "original": normalize_bangla_text(original.strip()),
        "corrected": normalize_bangla_text(corrected.strip()),
        "user_text": normalize_bangla_text(user_text.strip()),
    }
    try:
        _FLYWHEEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _FLYWHEEL_LOCK:
            with open(_FLYWHEEL_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Failed to record flywheel correction: %s", e)
