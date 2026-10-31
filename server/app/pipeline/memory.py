import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from server.app.pipeline.bengali import normalize_bangla_text

DEFAULT_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_MEMORY_FILE = DEFAULT_MEMORY_DIR / "user_memory.json"

# Prompt injection blocklist for memory updates
INJECTION_PATTERN = re.compile(
    r"(?:ignore\s+previous\s+instructions|system\s*:|assistant\s*:|prompt\s*injection|you\s+must\s+obey)",
    re.IGNORECASE,
)


def sanitize_memory_string(text: str, max_len: int = 256) -> str:
    """Sanitize learned facts and preferences to prevent prompt injection."""
    cleaned = INJECTION_PATTERN.sub("", text).strip()
    cleaned = re.sub(r"[\r\n]+", " ", cleaned)
    return cleaned[:max_len].strip()


class PersistentMemoryStore:
    """
    Production-grade tiered memory store supporting:
    - Structured schema with timestamps, confidence, and contradiction tracking.
    - Automatic migration from legacy schema.
    - Prompt injection defenses.
    - Strict 200-token prompt injection budget cap.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or DEFAULT_MEMORY_FILE
        self.data: Dict[str, Any] = {
            "profile": {},
            "facts": {},
            "corrections": {},
            "warm_summary": "",
            "history_log": [],
        }
        self.load()

    def _migrate_legacy_data(self, loaded: Dict[str, Any]) -> None:
        """Migrate legacy flat key-value store to structured schema seamlessly."""
        now = int(time.time())

        # Migrate profile preferences
        legacy_prefs = loaded.get("profile") or loaded.get("preferences", {})
        if isinstance(legacy_prefs, dict):
            for k, v in legacy_prefs.items():
                if isinstance(v, dict) and "value" in v:
                    self.data["profile"][k] = v
                else:
                    self.data["profile"][k] = {
                        "value": str(v).strip(),
                        "updated_at": now,
                        "confidence": 1.0,
                    }

        # Migrate facts
        legacy_facts = loaded.get("facts", {})
        if isinstance(legacy_facts, dict):
            for k, v in legacy_facts.items():
                if isinstance(v, dict) and "value" in v:
                    self.data["facts"][k] = v
                else:
                    self.data["facts"][k] = {
                        "value": str(v).strip(),
                        "updated_at": now,
                        "confidence": 0.9,
                    }

        # Migrate corrections
        legacy_corr = loaded.get("corrections", {})
        if isinstance(legacy_corr, dict):
            for k, v in legacy_corr.items():
                if isinstance(v, dict) and "value" in v:
                    self.data["corrections"][k] = v
                else:
                    self.data["corrections"][k] = {
                        "value": str(v).strip(),
                        "updated_at": now,
                    }

        self.data["warm_summary"] = loaded.get("warm_summary", "")
        self.data["history_log"] = loaded.get("history_log", [])

    def load(self) -> Dict[str, Any]:
        """Load stored memory from disk, handling legacy formats gracefully."""
        if not self.file_path.exists():
            return self.data

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._migrate_legacy_data(loaded)
        except Exception as e:
            print(f"⚠️ [MEMORY WARNING] Could not read memory file ({e}), using fresh store.")

        return self.data

    def save(self) -> None:
        """Persist memory to disk atomically using temporary file swap."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.file_path)
        except Exception as e:
            print(f"⚠️ [MEMORY ERROR] Failed to save persistent memory: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def set_user_name(self, name: str) -> None:
        """Store or update user's confirmed name."""
        self.set_preference("user_name", name.strip())

    def get_user_name(self) -> Optional[str]:
        """Retrieve user's confirmed name."""
        return self.get_preference("user_name")

    def set_address_style(self, style: str) -> None:
        """Store addressing style ('boss' or 'name_only')."""
        self.set_preference("address_style", style.strip())

    def get_address_style(self) -> str:
        """Retrieve addressing style (defaults to 'boss')."""
        return self.get_preference("address_style") or "boss"

    def set_preference(self, key: str, value: str) -> None:
        """Set a profile preference with contradiction resolution and change logging."""
        k = normalize_bangla_text(sanitize_memory_string(key, max_len=64))
        v = normalize_bangla_text(sanitize_memory_string(value, max_len=128))
        if not k or not v:
            return

        now = int(time.time())
        old_entry = self.data["profile"].get(k)
        if old_entry and old_entry.get("value") != v:
            # Contradiction resolver: Log previous value into history
            self.data["history_log"].append({
                "field": f"profile.{k}",
                "old_value": old_entry.get("value"),
                "new_value": v,
                "timestamp": now,
            })

        self.data["profile"][k] = {
            "value": v,
            "updated_at": now,
            "confidence": 1.0,
        }
        self.save()

    def get_preference(self, key: str) -> Optional[str]:
        """Retrieve preference value."""
        entry = self.data["profile"].get(normalize_bangla_text(key.strip()))
        if isinstance(entry, dict):
            return entry.get("value")
        return str(entry) if entry else None

    def set_fact(self, key: str, value: str, confidence: float = 0.9) -> None:
        """Store or update a user fact with contradiction resolution."""
        k = normalize_bangla_text(sanitize_memory_string(key, max_len=64))
        v = normalize_bangla_text(sanitize_memory_string(value, max_len=256))
        if not k or not v:
            return

        now = int(time.time())
        old_fact = self.data["facts"].get(k)
        if old_fact and old_fact.get("value") != v:
            self.data["history_log"].append({
                "field": f"facts.{k}",
                "old_value": old_fact.get("value"),
                "new_value": v,
                "timestamp": now,
            })

        self.data["facts"][k] = {
            "value": v,
            "updated_at": now,
            "confidence": confidence,
        }
        self.save()

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve fact value."""
        entry = self.data["facts"].get(normalize_bangla_text(key.strip()))
        if isinstance(entry, dict):
            return entry.get("value")
        return str(entry) if entry else None

    def set_correction(self, term: str, corrected_spelling: str) -> None:
        """Store verified proper noun spelling correction."""
        t = normalize_bangla_text(sanitize_memory_string(term, max_len=64))
        c = normalize_bangla_text(sanitize_memory_string(corrected_spelling, max_len=64))
        if not t or not c:
            return

        self.data["corrections"][t] = {
            "value": c,
            "updated_at": int(time.time()),
        }
        self.save()

    def get_corrections(self) -> Dict[str, str]:
        """Return dict of {term: corrected_spelling}."""
        res = {}
        for k, v in self.data["corrections"].items():
            if isinstance(v, dict):
                res[k] = v.get("value", k)
            else:
                res[k] = str(v)
        return res

    def set_warm_summary(self, summary: str) -> None:
        """Store warm tier rolling conversation summary."""
        self.data["warm_summary"] = sanitize_memory_string(summary, max_len=500)
        self.save()

    def get_warm_summary(self) -> str:
        """Retrieve warm tier rolling summary."""
        return self.data.get("warm_summary", "")

    def format_for_prompt(self, max_chars: int = 800) -> str:
        """
        Format persistent profile and cold facts with a strict ~200-token (~800 char) budget cap.
        Prioritizes user name, address style, and confirmed entity corrections.
        """
        lines: List[str] = []
        user_name = self.get_user_name()
        address_style = self.get_address_style()

        if user_name:
            lines.append(f"  • User Name: {user_name}")

        if address_style == "name_only":
            if user_name:
                lines.append(f"  • Addressing Preference: NEVER call user 'boss'; use '{user_name}' or speak respectfully without 'boss'.")
            else:
                lines.append("  • Addressing Preference: NEVER call user 'boss'; speak politely without using 'boss'.")
        else:
            lines.append("  • Addressing Preference: You may address the user as 'boss' when appropriate.")

        # Prioritize confirmed proper noun entity corrections (prevents repeated misspellings)
        corrections = self.get_corrections()
        if corrections:
            lines.append("Confirmed Entity Corrections:")
            for orig, corr in list(corrections.items())[:4]:
                lines.append(f"  • Use '{corr}' (confirmed for '{orig}')")

        # Sort facts by recency
        if self.data["facts"]:
            sorted_facts = sorted(
                self.data["facts"].items(),
                key=lambda item: item[1].get("updated_at", 0) if isinstance(item[1], dict) else 0,
                reverse=True,
            )
            fact_lines = []
            for k, v in sorted_facts[:4]:
                val = v.get("value") if isinstance(v, dict) else str(v)
                fact_lines.append(f"  • {k}: {val}")
            if fact_lines:
                lines.append("User Background Facts:")
                lines.extend(fact_lines)

        if not lines:
            return ""

        # Enforce budget cap
        output = "\nPersistent Memory Across Restarts:\n" + "\n".join(lines) + "\n"
        if len(output) > max_chars:
            output = output[:max_chars].rsplit("\n", 1)[0] + "\n"
        return output


memory_store = PersistentMemoryStore()
