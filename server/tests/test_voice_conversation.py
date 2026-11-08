import asyncio
import os
import sys
from pathlib import Path

# Set up project paths
test_dir = Path(__file__).resolve().parent
server_dir = test_dir.parent
root_dir = server_dir.parent

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

# Enforce Windows Selector event loop
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import pytest
from server.app.pipeline.safety import evaluate_crisis_guardrail
from server.app.pipeline.stt import repair_transcript
from server.app.pipeline.tts import (
    normalize_text_for_speech,
    strip_markdown_for_speech,
    resolve_prosody_parameters,
    synthesize_speech_pcm,
)
from server.app.pipeline.brain import brain_engine
from server.run_gemini_live import (
    control_appliance,
    trigger_head_gesture,
    set_facial_expression,
)


def test_crisis_guardrail_emergency_detection():
    """Ensure suicidal ideation and acute distress trigger safety overrides."""
    crisis_queries = [
        "I want to kill myself",
        "Thinking about suicide tonight",
        "I feel like ending my life",
        "There is no reason to live anymore",
    ]
    for q in crisis_queries:
        res = evaluate_crisis_guardrail(q)
        assert res.is_crisis is True, f"Failed to detect crisis in: {q}"
        assert res.override_response is not None
        assert "lifeline" in res.override_response.lower() or "support" in res.override_response.lower()


def test_crisis_guardrail_safe_queries():
    """Ensure normal conversational and technical requests are NOT falsely blocked."""
    safe_queries = [
        "Can you assist me with scheduling my day?",
        "Explain operating system deadlocks.",
        "What is the weather like right now?",
        "Turn on the reading light please.",
        "Hello Maya, how are you feeling today?",
    ]
    for q in safe_queries:
        res = evaluate_crisis_guardrail(q)
        assert res.is_crisis is False, f"False positive crisis on safe query: {q}"


def test_transcript_repair_engine():
    """Verify phonetic and acoustic repair heuristics."""
    repaired, is_garbled = repair_transcript("can you acid something for me")
    assert "assist" in repaired.lower()
    assert is_garbled is False

    repaired_deadlock, _ = repair_transcript("explain operating system dad lock")
    assert "deadlock" in repaired_deadlock.lower()


def test_speech_normalization_and_markdown_stripping():
    """Verify markdown tags and token boundary glitches are cleaned before TTS."""
    markdown_text = "**Bold** statement with `inline code` and # Header"
    cleaned = strip_markdown_for_speech(markdown_text)
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "#" not in cleaned

    glitched_text = "itis anincredibly good day."
    normalized = normalize_text_for_speech(glitched_text)
    assert "it is" in normalized.lower()
    assert "an incredibly" in normalized.lower()


def test_prosody_parameter_resolution():
    """Verify pace and expressivity configurations map cleanly."""
    voice, pitch, rate = resolve_prosody_parameters(pace_mult=1.1, expressivity="high")
    assert "Ava" in voice
    assert pitch == "-3Hz"
    assert rate == "+10%"


def test_gemini_live_iot_tool_actuation():
    """Verify physical robot simulated tools execute and return valid responses."""
    # 1. Appliance Relay
    relay_on = control_appliance("light", "on")
    assert "Light" in relay_on and "on" in relay_on

    relay_off = control_appliance("fan", "off")
    assert "Fan" in relay_off and "off" in relay_off

    # 2. Neck Servo Gestures
    servo_nod = trigger_head_gesture("nod_yes")
    assert "nod_yes" in servo_nod

    servo_cock = trigger_head_gesture("cock_curious")
    assert "cock_curious" in servo_cock

    # 3. Facial OLED Expressions
    oled_happy = set_facial_expression("happy")
    assert "happy" in oled_happy

    oled_listen = set_facial_expression("listening")
    assert "listening" in oled_listen


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


def test_voice_tts_synthesis_pipeline():
    """Verify that Edge-TTS synthesizes raw PCM audio for playback."""
    async def _run():
        pcm_bytes = await synthesize_speech_pcm("Voice test.")
        assert len(pcm_bytes) > 0, "TTS generated 0 bytes"
        # 16-bit Mono PCM should have an even number of bytes
        assert len(pcm_bytes) % 2 == 0

    _run_async(_run())


def test_voice_conversation_brain_reply():
    """Verify cognitive brain generates coherent, natural replies for voice conversations."""
    async def _run():
        user_prompt = "Hello Maya, tell me one interesting fact about space."
        reply = await brain_engine.generate_reply(user_prompt)
        assert reply is not None
        assert len(reply.strip()) > 10, "Brain reply too short or empty"
        # Ensure reply does not contain robotic filler or refusals
        assert not any(err in reply.lower() for err in ["circuit breaker open", "refuse to assist"])

    _run_async(_run())


def test_streaming_sentence_splitter_pipeline():
    """Verify that sentence streaming generates chunked, clean speech outputs."""
    async def _run():
        chunks = []
        async for sentence in brain_engine.generate_reply_sentences("What is artificial intelligence?"):
            assert len(sentence.strip()) > 0
            # Ensure markdown is stripped
            assert "**" not in sentence
            chunks.append(sentence)

        assert len(chunks) >= 1, "Sentence generator produced zero chunks"

    _run_async(_run())
