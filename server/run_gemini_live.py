import asyncio
import io
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Set up project path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Set Windows Selector policy for SSL / AsyncIO stability
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
    try:
        if sys.stdin:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

from server.app.config import settings
from server.app.pipeline.safety import evaluate_crisis_guardrail

# Audio parameters
INPUT_SAMPLE_RATE = 16000    # Mic input to Gemini Live
OUTPUT_SAMPLE_RATE = 24000   # Audio returned by Gemini Live
CHUNK_SIZE = 1024            # ~64ms per frame
CHANNELS = 1
MODEL_ID = "gemini-3.8-live"

# ==========================================
# Simulated Physical IoT Appliance Relay Tool
# ==========================================
def control_appliance(appliance: str, state: str) -> str:
    """Switch physical smart home appliances (e.g. light, fan, lamp).
    Args:
        appliance: Name of appliance (e.g., 'light', 'fan', 'lamp').
        state: 'on' or 'off'.
    """
    state_upper = state.upper()
    appliance_clean = appliance.capitalize()
    color_symbol = "🟢" if state.lower() == "on" else "🔴"
    
    print("\n" + "=" * 54)
    print(f"⚡ [IOT RELAY ACTUATION] {color_symbol}")
    print(f"   Appliance : {appliance_clean}")
    print(f"   Pin State : GPIO 21 -> {state_upper}")
    print(f"   Status    : 5V Relay clicked successfully")
    print("=" * 54 + "\n")
    return f"{appliance_clean} has been switched {state.lower()}."


def trigger_head_gesture(gesture: str) -> str:
    """Animate physical tabletop robot 2-DOF neck servos."""
    gesture_clean = gesture.lower()
    print(f"🤖 [ROBOT GESTURE] Motion: {gesture_clean.upper()} on GPIO 13/14")
    return f"Robot performed gesture {gesture_clean}."


def set_facial_expression(expression: str) -> str:
    """Set animated eye expression on the 0.96 inch OLED."""
    expr_clean = expression.lower()
    show_robot_expression(expr_clean)
    return f"OLED eyes updated to {expr_clean}."


def show_robot_expression(expression: str):
    """Render simulated OLED eye expression and head posture."""
    eyes_art = {
        "happy":     "( ^  _  ^ )  [Happy / Speaking]",
        "listening": "( O  _  O )  [Listening Attentively]",
        "sleeping":  "( -  _  - )  [Idle Standby]",
        "curious":   "( O  _  o )  [Curious / Cocked]",
    }.get(expression, "( •  _  • )")
    print(f"\n👁️  OLED Face: {eyes_art}")


TOOL_FUNCTIONS = {
    "control_appliance": control_appliance,
}

SYSTEM_INSTRUCTION = """You are MAYA, an intelligent, empathetic, Siri-grade English voice companion and tabletop robot.

Core Behaviors:
1. Speak in warm, conversational, natural English.
2. ALWAYS provide a spoken voice answer in every single turn.
3. Keep spoken replies concise and direct (1-3 sentences) suitable for natural voice conversation.
4. You have access to the `control_appliance` tool to switch lights or fans on/off when the user explicitly asks.
5. When you execute an appliance tool, always speak a brief, friendly verbal confirmation (e.g., 'I have turned on the desk light for you.')."""


async def run_live_assistant():
    print("\n" + "═" * 60)
    print("  🌸 MAYA: Gemini Live Voice Assistant (Laptop Prototype)")
    print("═" * 60)
    print(f"  🧠 Model      : {MODEL_ID}")
    print(f"  🎙️ Microphone : 16 kHz Mono (Laptop Mic via SoundDevice)")
    print(f"  🔊 Speaker    : 24 kHz Mono (Laptop Speaker via SoundDevice)")
    print(f"  ⚡ IoT Engine : 5V Appliance Relay Tool Active")
    print(f"  🛑 Barge-In   : Full-Duplex Native Interruption Supported")
    print("═" * 60)
    print("  Press Ctrl+C at any time to exit.\n")

    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        print("❌ Error: GEMINI_API_KEY is not set in server/.env.")
        return

    # Initialize Client with 30s timeout
    client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

    # Configure Live Session with AUDIO modality
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
            )
        ),
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[control_appliance],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue()
    input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    is_speaking = False

    def mic_callback(indata, frames, time_info, status):
        # Forward raw int16 PCM bytes to input queue
        loop.call_soon_threadsafe(input_queue.put_nowait, bytes(indata))

    # Initialize SoundDevice streams
    input_stream = sd.RawInputStream(
        samplerate=INPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        callback=mic_callback,
    )
    # Output stream with system-default buffer for glitch-free playback
    output_stream = sd.RawOutputStream(
        samplerate=OUTPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )

    # Retry loop for connection handshake
    MAX_ATTEMPTS = 3
    connected = False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"⏳ Connecting to Google Gemini Live API... (Attempt {attempt}/{MAX_ATTEMPTS})")
            async with client.aio.live.connect(model=MODEL_ID, config=config) as session:
                connected = True
                print("✅ [CONNECTED] Gemini Live is active! Start speaking naturally.\n")
                show_robot_expression("listening")

                # Start audio hardware streams only after successful connection
                input_stream.start()
                output_stream.start()

                # Worker 1: Read mic audio and send to Gemini
                async def send_audio_worker():
                    try:
                        while True:
                            pcm_data = await input_queue.get()
                            # Acoustic Echo Suppression:
                            # While MAYA is speaking, duck mic energy unless user speaks loudly (barge-in)
                            if is_speaking:
                                audio_arr = np.frombuffer(pcm_data, dtype=np.int16)
                                rms = float(np.sqrt(np.mean(np.square(audio_arr.astype(np.float32)))))
                                if rms < 1600.0:
                                    continue

                            await session.send_realtime_input(
                                audio={"data": pcm_data, "mime_type": "audio/pcm"}
                            )
                    except asyncio.CancelledError:
                        pass

                # Worker 2: Receive audio, transcripts, and tool calls from Gemini
                async def receive_audio_worker():
                    nonlocal is_speaking
                    try:
                        async for response in session.receive():
                            # A. Handle Tool Calls from Gemini
                            if response.tool_call and response.tool_call.function_calls:
                                tool_responses = []
                                for fc in response.tool_call.function_calls:
                                    fn_name = fc.name
                                    fn_args = fc.args or {}
                                    fn = TOOL_FUNCTIONS.get(fn_name)
                                    if fn:
                                        try:
                                            result = fn(**fn_args)
                                        except Exception as ex:
                                            result = f"Error executing {fn_name}: {ex}"
                                    else:
                                        result = f"Unknown tool: {fn_name}"

                                    tool_responses.append(
                                        types.FunctionResponse(
                                            name=fn_name,
                                            id=fc.id,
                                            response={"result": result},
                                        )
                                    )

                                await session.send_tool_response(function_responses=tool_responses)

                            server_content = response.server_content
                            if server_content is None:
                                continue

                            # B. Native Barge-In: User interrupted speech
                            if server_content.interrupted:
                                print("\n🛑 [BARGE-IN] You spoke — listening to you...")
                                show_robot_expression("curious")
                                # Flush outbound playback queue
                                while not audio_out_queue.empty():
                                    try:
                                        audio_out_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                is_speaking = False
                                continue

                            # C. Process generated audio chunks and text
                            if server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data:
                                        audio_out_queue.put_nowait(part.inline_data.data)
                                    if part.text:
                                        print(part.text, end="", flush=True)

                            # D. Process user speech transcription & Safety evaluation
                            if server_content.input_transcription:
                                user_text = server_content.input_transcription.text
                                if user_text:
                                    print(f"\n👤 You: {user_text.strip()}")
                                    try:
                                        guardrail_result = evaluate_crisis_guardrail(user_text)
                                        if getattr(guardrail_result, "is_crisis", False):
                                            print("\n🚨 [CRISIS GUARDRAIL ACTIVATED]")
                                            print("⚠️  High distress detected. Routing to emergency lifelines (988 / Kaan Pete Roi).")
                                            print(f"ℹ️  Lifeline response: {getattr(guardrail_result, 'override_response', '')}\n")
                                    except Exception:
                                        pass

                            # E. Print assistant speaking tag
                            if server_content.output_transcription:
                                asst_text = server_content.output_transcription.text
                                if asst_text:
                                    print(f"🤖 Maya: {asst_text.strip()}")

                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"\n⚠️ [RECEIVE ERROR] {e}")

                # Worker 3: Audio Output Playback Stream
                async def play_audio_worker():
                    nonlocal is_speaking
                    try:
                        while True:
                            audio_data = await audio_out_queue.get()
                            is_speaking = True
                            # Write raw PCM chunk directly to speaker
                            await asyncio.to_thread(output_stream.write, audio_data)
                            if audio_out_queue.empty():
                                await asyncio.sleep(0.12)
                                if audio_out_queue.empty():
                                    is_speaking = False
                    except asyncio.CancelledError:
                        pass

                # Run workers concurrently
                await asyncio.gather(
                    send_audio_worker(),
                    receive_audio_worker(),
                    play_audio_worker(),
                )
                break

        except KeyboardInterrupt:
            print("\n👋 Shutting down MAYA Gemini Live...")
            break
        except Exception as e:
            err_str = str(e).lower()
            if "timed out during opening handshake" in err_str and attempt < MAX_ATTEMPTS:
                print(f"⚠️ Handshake timed out (endpoint resetting). Retrying in 2.5s (Attempt {attempt+1}/{MAX_ATTEMPTS})...")
                await asyncio.sleep(2.5)
                continue
            else:
                print(f"\n❌ [ERROR] {e}")
                break
        finally:
            try:
                if input_stream.active:
                    input_stream.stop()
                input_stream.close()
            except Exception:
                pass
            try:
                if output_stream.active:
                    output_stream.stop()
                output_stream.close()
            except Exception:
                pass

    if connected:
        print("✅ Session ended. Audio streams released cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(run_live_assistant())
    except KeyboardInterrupt:
        print("\nSession ended.")
