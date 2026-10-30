import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_MEMORY_FILE = DEFAULT_MEMORY_DIR / "user_memory.json"


class PersistentMemoryStore:
    """
    Lightweight, persistent memory store for user-approved facts, preferences,
    and verified corrections across assistant restarts.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or DEFAULT_MEMORY_FILE
        self.data: Dict[str, Any] = {
            "facts": {},
            "preferences": {},
            "corrections": {},
        }
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load stored memory from disk, handling missing or corrupt files gracefully."""
        if not self.file_path.exists():
            return self.data

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.data["facts"] = loaded.get("facts", {})
                    self.data["preferences"] = loaded.get("preferences", {})
                    self.data["corrections"] = loaded.get("corrections", {})
        except Exception as e:
            # Fall back to empty structure on corrupt read
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

    def set_fact(self, key: str, value: str) -> None:
        """Store or update a user-approved fact."""
        self.data["facts"][key.strip()] = value.strip()
        self.save()

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve a stored fact."""
        return self.data["facts"].get(key.strip())

    def set_preference(self, key: str, value: str) -> None:
        """Store or update a user preference."""
        self.data["preferences"][key.strip()] = value.strip()
        self.save()

    def get_preference(self, key: str) -> Optional[str]:
        """Retrieve a user preference."""
        return self.data["preferences"].get(key.strip())

    def set_correction(self, term: str, corrected_spelling: str) -> None:
        """
        Store an explicitly confirmed spelling or term correction.
        Example: set_correction("Pizza Berg", "Pizza Barg")
        """
        self.data["corrections"][term.strip()] = corrected_spelling.strip()
        self.save()

    def get_corrections(self) -> Dict[str, str]:
        """Return all tracked corrections."""
        return dict(self.data["corrections"])

    def clear(self) -> None:
        """Reset memory store to empty."""
        self.data = {
            "facts": {},
            "preferences": {},
            "corrections": {},
        }
        self.save()

    def format_for_prompt(self) -> str:
        """Format persistent facts and corrections for system prompt injection."""
        lines = []

        if self.data["facts"]:
            lines.append("User Facts & Background:")
            for k, v in self.data["facts"].items():
                lines.append(f"  • {k}: {v}")

        if self.data["preferences"]:
            lines.append("User Preferences:")
            for k, v in self.data["preferences"].items():
                lines.append(f"  • {k}: {v}")

        if self.data["corrections"]:
            lines.append("Verified Proper Nouns & Entity Corrections:")
            for orig, corr in self.data["corrections"].items():
                lines.append(f"  • Use '{corr}' (confirmed spelling for '{orig}')")

        if not lines:
            return ""

        return "\nPersistent Memory Across Restarts:\n" + "\n".join(lines) + "\n"


memory_store = PersistentMemoryStore()
