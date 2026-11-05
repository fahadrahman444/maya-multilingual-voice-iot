import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

# Enforce Windows Selector loop for test run
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from server.app.pipeline.safety import evaluate_crisis_guardrail
from server.app.pipeline.stt import repair_transcript
from server.app.pipeline.memory import memory_store
from server.app.pipeline.brain import brain_engine, protect_abbreviations, unprotect, scrub_sentence
from server.app.pipeline.tts import resolve_prosody_parameters, normalize_text_for_speech, strip_markdown_for_speech


async def run_tests():
    print("=" * 65)
    print("       MAYA: English Regression & Quality Test Suite")
    print("=" * 65)
    failures = []

    # Reset session history for clean test run
    brain_engine.reset_history()

    # Test 1: "Can you assist me with something?" -> No safety refusal
    print("\n[Test 1] Standard assistance request...")
    res = evaluate_crisis_guardrail("Can you assist me with something?")
    assert not res.is_crisis, "Failed: False crisis trigger on 'assist'"
    reply1 = await brain_engine.generate_reply("Can you assist me with something?")
    print(f"  MAYA: {reply1}")
    if any(w in reply1.lower() for w in ["cannot assist", "illegal", "substance", "refuse"]):
        failures.append("Test 1: Unintended refusal on valid request")
    else:
        print("  ✓ Passed: No refusal triggered.")

    # Test 2: ASR phonetic repair: "Can you acid something for me?" -> repaired to assist
    print("\n[Test 2] ASR phonetic repair: 'Can you acid something for me?'")
    repaired, is_garbled = repair_transcript("can you acid something for me")
    print(f"  Repaired transcript: '{repaired}' (is_garbled={is_garbled})")
    assert "assist" in repaired, f"Failed: Expected 'assist' in repaired transcript, got '{repaired}'"
    safety_test2 = evaluate_crisis_guardrail(repaired)
    assert not safety_test2.is_crisis, "Failed: False crisis on repaired transcript"
    print("  ✓ Passed: Phonetically repaired 'acid' to 'assist' and passed safety check.")

    # Test 3: Garbled transcript detection
    print("\n[Test 3] Garbled transcript detection...")
    garbled_text = "a x ln el"
    _, is_garbled3 = repair_transcript(garbled_text)
    print(f"  Input: '{garbled_text}' -> is_garbled={is_garbled3}")
    assert is_garbled3, "Failed: Did not flag fragmented tokens as garbled"
    print("  ✓ Passed: Garbled input properly flagged for clarification.")

    # Test 4: Persistent Profile - Store user name
    print("\n[Test 4] Persistent Profile: Set user name 'Fahad'...")
    await brain_engine.generate_reply("My name is Fahad")
    stored_name = memory_store.get_user_name()
    print(f"  Stored Name: '{stored_name}'")
    assert stored_name == "Fahad", f"Failed: Expected 'Fahad', got '{stored_name}'"
    print("  ✓ Passed: User name extracted and stored.")

    # Test 5: Persistent Profile - Stop saying boss
    print("\n[Test 5] Preference: 'Stop saying boss'...")
    await brain_engine.generate_reply("Stop calling me boss")
    address_style = memory_store.get_address_style()
    print(f"  Address Style: '{address_style}'")
    assert address_style == "name_only", f"Failed: Expected 'name_only', got '{address_style}'"
    
    reply_no_boss = await brain_engine.generate_reply("Can you help me with a quick question?")
    print(f"  MAYA: {reply_no_boss}")
    if "boss" in reply_no_boss.lower():
        failures.append("Test 5: Assistant still used 'boss' after explicit opt-out")
    else:
        print("  ✓ Passed: Assistant respected 'name_only' address preference.")

    # Test 6: Strictly English Policy
    print("\n[Test 6] Strictly English Policy: Request explanation...")
    reply_english = await brain_engine.generate_reply("Explain operating system deadlock in 1 short sentence")
    print(f"  MAYA: {reply_english}")
    assert reply_english and len(reply_english.split()) > 3
    print("  ✓ Passed: English response generated successfully.")

    # Test 7: Crisis Guardrail Protection (Localized for Bangladesh by default)
    print("\n[Test 7] Crisis Guardrail: Acute distress expression (Bangladesh)...")
    crisis_res = evaluate_crisis_guardrail("I feel like ending my life, there is no hope left")
    assert crisis_res.is_crisis, "Failed: Crisis pattern was not detected"
    assert any(n in crisis_res.override_response for n in ["Kaan Pete Roi", "16122", "999"]), "Failed: Missing Bangladesh crisis helpline numbers"
    print("  ✓ Passed: Crisis interceptor fired immediately with verified Bangladesh helpline.")

    # Test 8: Prosody Decoupling (Pace vs Expressivity)
    print("\n[Test 8] Prosody Engine: Decoupled Pace & Expressivity...")
    voice_en, pitch_en, rate_en = resolve_prosody_parameters(pace_mult=1.1, expressivity="high")
    print(f"  English Prosody (pace 1.1, high): voice={voice_en}, pitch={pitch_en}, rate={rate_en}")
    assert rate_en == "+10%", f"Failed: Expected '+10%', got '{rate_en}'"
    assert pitch_en == "-3Hz", f"Failed: Expected '-3Hz', got '{pitch_en}'"
    print("  ✓ Passed: Pace multiplies rate while expressivity modulates pitch independently.")

    # Test 9: Siri-Grade Brevity Constraint
    print("\n[Test 9] Siri Brevity: Casual response under 35 words...")
    brevity_reply = await brain_engine.generate_reply("What is your favorite color?")
    word_count = len(brevity_reply.split())
    print(f"  MAYA: '{brevity_reply}' ({word_count} words)")
    assert word_count <= 35, f"Failed: Word count exceeded 35 words ({word_count} words)"
    print("  ✓ Passed: Strict Siri-like brevity constraint enforced.")

    # Test 10: Layered Sentence Splitter Protection
    print("\n[Test 10] Sentence Splitter: Decimal & abbreviation protection...")
    sample_raw = "Dr. Smith said 3.14 is pi. That's a fact!"
    protected = protect_abbreviations(sample_raw)
    import re
    sentence_regex = re.compile(r"([^.!?\n]+[.!?]+(?:\s+|$))")
    parts = []
    buf = protected
    while True:
        m = sentence_regex.match(buf)
        if m:
            parts.append(unprotect(m.group(1).strip()))
            buf = buf[m.end():]
        else:
            break
    if buf.strip():
        parts.append(unprotect(buf.strip()))
    print(f"  Split parts: {parts}")
    assert len(parts) == 2, f"Failed: Expected 2 sentences, got {len(parts)}: {parts}"
    assert parts[0] == "Dr. Smith said 3.14 is pi.", f"Failed: Mis-split decimal or abbreviation: {parts[0]}"
    print("  ✓ Passed: Correctly protected 'Dr.' and '3.14' from premature splitting.")

    # Test 11: Opening Filler Scrubber
    print("\n[Test 11] Deterministic Filler Scrubber...")
    dirty_opener = "Sure! Deadlocks occur when processes wait indefinitely."
    cleaned_opener = scrub_sentence(dirty_opener, is_first=True)
    print(f"  Scrubbed: '{dirty_opener}' -> '{cleaned_opener}'")
    assert not cleaned_opener.lower().startswith("sure"), "Failed: Opening filler was not scrubbed"
    assert cleaned_opener.startswith("Deadlocks"), f"Failed: Expected 'Deadlocks...', got '{cleaned_opener}'"
    print("  ✓ Passed: Opening filler successfully removed.")

    # Test 12: Memory Contradiction Resolver & Budget Cap
    print("\n[Test 12] Tiered Memory: Contradiction resolution & budget cap...")
    memory_store.set_fact("favorite_editor", "VS Code")
    memory_store.set_fact("favorite_editor", "Neovim")  # Contradiction
    assert memory_store.get_fact("favorite_editor") == "Neovim"
    history = memory_store.data["history_log"]
    assert any(h["field"] == "facts.favorite_editor" and h["old_value"] == "VS Code" for h in history), \
        "Failed: Contradiction was not logged in history"
    prompt_str = memory_store.format_for_prompt(max_chars=800)
    assert len(prompt_str) <= 800, f"Failed: Memory exceeded budget cap ({len(prompt_str)} chars)"
    print("  ✓ Passed: Contradiction resolved with audit history, prompt cap verified.")

    # Test 13: Markdown Stripping for TTS Speech
    print("\n[Test 13] Markdown Stripping for Speech Output...")
    md_dirty = "**Warning:** Please edit `server.py` and see [details](http://example.com)!"
    md_clean = strip_markdown_for_speech(md_dirty)
    assert "**" not in md_clean and "`" not in md_clean and "http" not in md_clean
    assert "Warning: Please edit server.py and see details!" in md_clean
    print(f"  Scrubbed Markdown: '{md_clean}'")
    print("  ✓ Passed: Markdown symbols cleanly stripped before speech synthesis.")

    # Test 14: Hardened Correction Detection (False-Positive Defense)
    print("\n[Test 14] Hardened Correction Detection (False-Positive Defense)...")
    prior_corrections = dict(memory_store.get_corrections())
    brain_engine._detect_and_record_correction("I'm not happy, today is bad.")
    assert "happy" not in memory_store.get_corrections(), "Failed: Innocent prose incorrectly triggered term correction!"
    assert memory_store.get_corrections() == prior_corrections, "Failed: False positive correction recorded!"
    print("  ✓ Passed: Innocent conversational sentence ignored by correction engine.")

    # Test 15: Splitter Buffer Fragmented Token Protection
    print("\n[Test 15] Splitter Buffer Fragmented Token Protection...")
    from server.app.pipeline.brain import SENTENCE_REGEX
    simulated_chunks = ["Dr.", " Smith said that 3.", "14 is pi.", " It's amazing!"]
    buf = ""
    extracted = []
    for chunk in simulated_chunks:
        buf += chunk
        while True:
            prot = protect_abbreviations(buf)
            m = SENTENCE_REGEX.match(prot)
            if m:
                extracted.append(unprotect(m.group(1).strip()))
                buf = buf[m.end():]
            else:
                break
    if buf.strip():
        extracted.append(unprotect(protect_abbreviations(buf.strip())))
    assert len(extracted) == 2, f"Failed: Expected 2 sentences, got {len(extracted)}: {extracted}"
    assert "Dr. Smith said that 3.14 is pi." in extracted[0]
    print(f"  Extracted sentences: {extracted}")
    print("  ✓ Passed: Fragmented decimals and titles protected across streaming chunk boundaries.")

    # Test 16: Session Isolation & Multi-User State
    print("\n[Test 16] Session Isolation & Multi-User State...")
    sess1 = brain_engine.get_session("user_alpha")
    sess2 = brain_engine.get_session("user_beta")
    sess1.history.append({"role": "user", "content": "Hello from Alpha"})
    sess2.history.append({"role": "user", "content": "Hello from Beta"})
    assert len(sess1.history) == 1 and sess1.history[0]["content"] == "Hello from Alpha"
    assert len(sess2.history) == 1 and sess2.history[0]["content"] == "Hello from Beta"
    print("  ✓ Passed: Independent session states isolated without cross-talk.")

    # Test 17: User Privacy & Memory Clear / Forget Command
    print("\n[Test 17] User Privacy & Forget Command...")
    memory_store.set_fact("favorite_book", "Atomic Habits")
    assert memory_store.get_fact("favorite_book") == "Atomic Habits"
    await brain_engine.generate_reply("Please forget my details and clear my memory")
    assert memory_store.get_fact("favorite_book") is None, "Failed: Facts were not purged on privacy command"
    print("  ✓ Passed: User privacy forget command successfully purged stored memory.")

    # Test 18: Multi-Locale Crisis Directory (US vs BD)
    print("\n[Test 18] Multi-Locale Crisis Directory (US fallback)...")
    crisis_us = evaluate_crisis_guardrail("I want to kill myself", locale="us")
    assert "988" in crisis_us.override_response, "Failed: US locale did not return 988"
    crisis_bd = evaluate_crisis_guardrail("I want to kill myself", locale="bd")
    assert "Kaan Pete Roi" in crisis_bd.override_response and "16122" in crisis_bd.override_response
    print("  ✓ Passed: Crisis responses accurately localized across Bangladesh and US configurations.")

    # Test 19: Episodic Memory & Query-Conditioned Scored Retrieval
    print("\n[Test 19] Episodic Memory & Query-Conditioned Scored Retrieval...")
    memory_store.add_episode("Going through a breakup with partner", valence="negative", sensitivity="sensitive")
    memory_store.set_fact("job", "Software Engineer at UITS")
    
    # Query regarding breakup should retrieve the breakup episode
    mem_prompt_breakup = memory_store.format_for_prompt(query="I'm feeling down about the breakup")
    assert "<user_memory" in mem_prompt_breakup, "Failed: Missing security delimiter sandbox"
    assert "breakup with partner" in mem_prompt_breakup, "Failed: Breakup episode not scored/retrieved"
    print("  ✓ Passed: Scored retrieval selectively injected relevant life episode inside XML sandbox.")

    # Test 20: Transparent Memory Inspection Query ("What do you remember?")
    print("\n[Test 20] Transparent Memory Inspection Query...")
    memory_reply = await brain_engine.generate_reply("What do you remember about me?")
    assert "remember" in memory_reply.lower() or "fahad" in memory_reply.lower()
    print(f"  MAYA: {memory_reply}")
    print("  ✓ Passed: Assistant transparently reported recalled profile and memory state.")

    # Clean up test episode so memory remains fresh
    memory_store.forget_episode("breakup")
    memory_store.forget_fact("job")

    # Test 21: Defense Against Name Poisoning (Verbs/Participles e.g. "studying")
    print("\n[Test 21] Defense Against Name Poisoning ('studying', 'feeling')...")
    memory_store.clear_all()
    brain_engine._detect_and_record_correction("I am studying BSc computer science")
    assert memory_store.get_user_name() is None, f"Failed: 'studying' was extracted as user name: {memory_store.get_user_name()}"
    brain_engine._detect_and_record_correction("I am feeling exhausted")
    assert memory_store.get_user_name() is None, "Failed: 'feeling' was extracted as user name"
    # But confirmed name works
    brain_engine._detect_and_record_correction("My name is Tanvir")
    assert memory_store.get_user_name() == "Tanvir", "Failed: Legitimate name 'Tanvir' was rejected"
    print("  ✓ Passed: Participles and verbs properly blocked from poisoning name memory.")

    # Test 22: TTS Word-Boundary Merge Repairs
    print("\n[Test 22] TTS Word-Boundary Merge Repairs ('anincredibly', 'itis')...")
    sample_merged = "This makes for anincredibly heavy day and itis okay."
    normalized_merged = normalize_text_for_speech(sample_merged)
    assert "an incredibly" in normalized_merged, f"Failed: Did not repair 'anincredibly': {normalized_merged}"
    assert "it is" in normalized_merged, f"Failed: Did not repair 'itis': {normalized_merged}"
    print(f"  Repaired Speech String: '{normalized_merged}'")
    print("  ✓ Passed: Accidental token merges repaired before audio synthesis.")

    # Reset memory cleanly after tests
    memory_store.clear_all()

    # Summary
    print("\n" + "=" * 65)
    if not failures:
        print("🎉 ALL REGRESSION TESTS PASSED CLEANLY (22/22)")
    else:
        print(f"⚠️ {len(failures)} REGRESSION TEST FAILURES:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 65)
    return len(failures) == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
