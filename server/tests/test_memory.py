import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

# Ensure UTF-8 I/O encoding on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from server.app.pipeline.memory import PersistentMemoryStore


def test_persistent_memory_across_restarts():
    print("=" * 65)
    print("MAYA: Testing Persistent Memory Store Across Restarts")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test_memory.json"

        # Session 1: Store facts, preferences, and corrections
        print("\n[1] Session 1: Adding facts, preferences, and corrections...")
        store1 = PersistentMemoryStore(file_path=test_file)
        store1.set_fact("User Name", "Tanvir")
        store1.set_preference("Preferred Language", "English")
        store1.set_correction("Pizza Berg", "Pizza Barg")
        store1.set_correction("পিজা বার্গ", "পিজ্জা বার্গ")

        prompt_view = store1.format_for_prompt()
        print("    -> Prompt view generated:")
        for line in prompt_view.strip().split("\n"):
            print(f"       {line}")

        # Simulate process termination / restart (instantiating fresh store pointing to same disk file)
        print("\n[2] Simulating process termination & restart...")
        del store1

        # Session 2: Read memory from disk
        store2 = PersistentMemoryStore(file_path=test_file)
        print("    -> Session 2 loaded memory from disk successfully.")

        # Assertions
        assert store2.get_fact("User Name") == "Tanvir", "Fact 'User Name' mismatch!"
        assert store2.get_preference("Preferred Language") == "English", "Preference mismatch!"
        assert store2.get_corrections().get("Pizza Berg") == "Pizza Barg", "Correction 'Pizza Barg' mismatch!"
        assert store2.get_corrections().get("পিজা বার্গ") == "পিজ্জা বার্গ", "Bangla correction mismatch!"

        # Session 2: Update existing fact
        print("\n[3] Session 2: Updating an existing fact...")
        store2.set_fact("Favorite Drink", "Black Coffee")
        assert store2.get_fact("Favorite Drink") == "Black Coffee"

        # Session 3: Verify update persisted across another restart
        del store2
        store3 = PersistentMemoryStore(file_path=test_file)
        assert store3.get_fact("Favorite Drink") == "Black Coffee"
        print("    -> Session 3 verified updated fact was persisted.")

        # Session 4: Test Episodic Memory & Query-Conditioned Retrieval
        print("\n[4] Session 4: Testing Episodic Memory & Query-Conditioned Scored Retrieval...")
        store3.add_episode("User broke up with long-term partner", valence="negative", sensitivity="sensitive")
        store3.add_episode("User has a software engineering exam next week", valence="neutral", sensitivity="personal")

        # Query about breakup -> should retrieve breakup episode
        prompt_breakup = store3.format_for_prompt(query="I am feeling so sad about the breakup")
        assert "<user_memory" in prompt_breakup, "Failed: Missing XML security sandbox"
        assert "broke up with long-term partner" in prompt_breakup, "Failed: Breakup episode not recalled on relevant query"
        print("    -> Successfully retrieved breakup episode on relevant query.")

        # Query about exam -> should retrieve exam episode
        prompt_exam = store3.format_for_prompt(query="I need to study for my exam")
        assert "software engineering exam" in prompt_exam, "Failed: Exam episode not recalled on exam query"
        print("    -> Successfully retrieved exam episode on relevant query.")

        # Session 5: Granular Forget & Memory Inspection
        print("\n[5] Session 5: Testing Granular Forget & Transparent Summary...")
        summary = store3.get_summary_of_memory()
        assert "broke up" in summary or "exam" in summary
        print(f"    -> Summary: {summary}")

        # Forget breakup episode specifically
        removed = store3.forget_episode("breakup")
        assert removed == 1, "Failed: Expected 1 episode removed"
        prompt_after_forget = store3.format_for_prompt(query="breakup")
        assert "broke up with long-term partner" not in prompt_after_forget, "Failed: Breakup still present after granular forget"
        print("    -> Successfully verified granular forget of specific episode.")

    print("\n" + "=" * 65)
    print("Persistent Memory Unit Test Passed Completely (100%)!")
    print("=" * 65)


if __name__ == "__main__":
    test_persistent_memory_across_restarts()
