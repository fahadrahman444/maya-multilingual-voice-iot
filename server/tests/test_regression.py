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
from server.app.pipeline.bengali import normalize_bangla_text, detect_language


async def run_tests():
    print("=" * 65)
    print("       MAYA: Comprehensive Regression & Quality Test Suite")
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

    # Test 3: Garbled Bangla transcript detection
    print("\n[Test 3] Garbled Bangla transcript detection...")
    garbled_text = "আ, গাটিট, এই এক্সলেন েল"
    _, is_garbled3 = repair_transcript(garbled_text)
    print(f"  Input: '{garbled_text}' -> is_garbled={is_garbled3}")
    assert is_garbled3, "Failed: Did not flag fragmented Bangla tokens as garbled"
    print("  ✓ Passed: Garbled Bangla properly flagged for clarification.")

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

    # Test 6: Language Mirroring / Explicit Language Request
    print("\n[Test 6] Language Mirroring: Explain deadlock in Bangla...")
    reply_bangla = await brain_engine.generate_reply("Explain deadlock in Bangla in 1 sentence")
    print(f"  MAYA: {reply_bangla}")
    has_bangla = any('\u0980' <= c <= '\u09ff' for c in reply_bangla)
    assert has_bangla, f"Failed: Expected Bengali reply, got: '{reply_bangla}'"
    print("  ✓ Passed: Honored Bangla language request.")

    # Test 7: Crisis Guardrail Protection
    print("\n[Test 7] Crisis Guardrail: Acute distress expression...")
    crisis_res = evaluate_crisis_guardrail("আমার বেঁচে থাকার কোনো অর্থ নেই, মরে যেতে ইচ্ছে করছে")
    assert crisis_res.is_crisis, "Failed: Crisis pattern was not detected"
    assert "০১৭৭৯-৫৫৪৩৯১" in crisis_res.override_response, "Failed: Missing helpline number"
    print("  ✓ Passed: Crisis interceptor fired immediately with verified helpline.")

    # Test 8: Prosody Decoupling (Pace vs Expressivity)
    print("\n[Test 8] Prosody Engine: Decoupled Pace & Expressivity...")
    voice_bn, pitch_bn, rate_bn = resolve_prosody_parameters(is_bangla=True, pace_mult=1.0, expressivity="medium")
    voice_en, pitch_en, rate_en = resolve_prosody_parameters(is_bangla=False, pace_mult=1.1, expressivity="high")
    print(f"  Bangla Prosody (pace 1.0, med): voice={voice_bn}, pitch={pitch_bn}, rate={rate_bn}")
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
    sentence_regex = re.compile(r"([^.!?।\n]+[.!?।]+(?:\s+|$))")
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

    # Test 13: Bengali Unicode Normalization & Script Classification
    print("\n[Test 13] Bengali Unicode Normalization & Language Classification...")
    bn_sample = "আমি বাংলায় কথা বলি।"
    assert normalize_bangla_text(bn_sample) == bn_sample
    assert detect_language("আমি বাংলায় কথা বলি") == "bn"
    assert detect_language("Hello Maya") == "en"
    assert detect_language("হ্যালো Maya") == "mixed"
    print("  ✓ Passed: Unicode normalizer and 3-way language classifier verified.")

    # Test 14: Phonetic Pronunciation Lexicon for TTS
    print("\n[Test 14] Phonetic Pronunciation Lexicon for TTS...")
    tts_input = "সিস্টেমে ডেডলক হয়েছে, ভার্সন 2.5।"
    tts_normalized = normalize_text_for_speech(tts_input, is_bangla=True)
    assert "ডেড-লক" in tts_normalized, f"Failed: Lexicon replacement missing: {tts_normalized}"
    assert "২.৫" in tts_normalized, f"Failed: Bengali digit conversion missing: {tts_normalized}"
    print(f"  TTS Output: '{tts_normalized}'")
    print("  ✓ Passed: Phonetic pronunciations and Bengali digits successfully applied.")

    # Test 15: Correction Flywheel Logging
    print("\n[Test 15] Bangla Correction Flywheel Logging...")
    flywheel_file = Path("server/data/correction_flywheel.jsonl")
    initial_flywheel_lines = len(flywheel_file.read_text(encoding="utf-8").splitlines()) if flywheel_file.exists() else 0
    brain_engine._detect_and_record_correction("এটা ঢাকা, ঢাক্কা না")
    assert memory_store.get_corrections().get("ঢাক্কা") == "ঢাকা", "Failed: Correction not stored in memory"
    assert flywheel_file.exists(), "Failed: Flywheel JSONL was not created"
    new_flywheel_lines = len(flywheel_file.read_text(encoding="utf-8").splitlines())
    assert new_flywheel_lines == initial_flywheel_lines + 1, "Failed: Flywheel did not record correction entry"
    print("  ✓ Passed: Flywheel successfully appended acoustic correction entry.")

    # Test 16: Markdown Stripping for TTS Speech
    print("\n[Test 16] Markdown Stripping for Speech Output...")
    md_dirty = "**Warning:** Please edit `server.py` and see [details](http://example.com)!"
    md_clean = strip_markdown_for_speech(md_dirty)
    assert "**" not in md_clean and "`" not in md_clean and "http" not in md_clean
    assert "Warning: Please edit server.py and see details!" in md_clean
    print(f"  Scrubbed Markdown: '{md_clean}'")
    print("  ✓ Passed: Markdown symbols cleanly stripped before speech synthesis.")

    # Test 17: Correction Regex False-Positive Rejection
    print("\n[Test 17] Hardened Correction Detection (False-Positive Defense)...")
    prior_corrections = dict(memory_store.get_corrections())
    brain_engine._detect_and_record_correction("I'm not happy, today is bad.")
    assert "happy" not in memory_store.get_corrections(), "Failed: Innocent prose incorrectly triggered term correction!"
    assert memory_store.get_corrections() == prior_corrections, "Failed: False positive correction recorded!"
    print("  ✓ Passed: Innocent conversational sentence ignored by correction engine.")

    # Test 18: Splitter Buffer Fragmented Token Protection
    print("\n[Test 18] Splitter Buffer Fragmented Token Protection...")
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

    # Test 19: Session Isolation & Multi-User State
    print("\n[Test 19] Session Isolation & Multi-User State...")
    sess1 = brain_engine.get_session("user_alpha")
    sess2 = brain_engine.get_session("user_beta")
    sess1.history.append({"role": "user", "content": "Hello from Alpha"})
    sess1.preferred_language = "en"
    sess2.history.append({"role": "user", "content": "হ্যালো from Beta"})
    sess2.preferred_language = "bn"
    assert len(sess1.history) == 1 and sess1.history[0]["content"] == "Hello from Alpha"
    assert len(sess2.history) == 1 and sess2.history[0]["content"] == "হ্যালো from Beta"
    assert sess1.preferred_language != sess2.preferred_language
    print("  ✓ Passed: Independent session states isolated without cross-talk.")

    # Summary
    print("\n" + "=" * 65)
    if not failures:
        print("🎉 ALL REGRESSION TESTS PASSED CLEANLY (19/19)")
    else:
        print(f"⚠️ {len(failures)} REGRESSION TEST FAILURES:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 65)
    return len(failures) == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
