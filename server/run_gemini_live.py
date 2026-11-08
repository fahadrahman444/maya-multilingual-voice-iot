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
# Simulated Physical IoT Hardware Tools
# ==========================================
def control_appliance(appliance: str, state: str) -> str:
    """Switch physical smart home appliances (e.g. light, fan, relay).
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
    return f"{appliance_clean} has been turned {state.lower()}."


def trigger_head_gesture(gesture: str) -> str:
    """Animate physical tabletop robot 2-DOF neck servos.
    Args:
        gesture: One of 'nod_yes', 'shake_no', 'cock_curious', 'look_up', 'center'.
    """
    gesture_clean = gesture.lower()
    gesture_desc = {
        "nod_yes": "Nodding head up & down (Pitch: 125°, Yaw: 90°)",
        "shake_no": "Shaking head left & right (Pitch: 90°, Yaw: 60°/120°)",
        "cock_curious": "Tilting head curiously (Pitch: 115°, Yaw: 110°)",
        "look_up": "Looking up at user (Pitch: 130°, Yaw: 90°)",
        "center": "Resetting head to neutral center (Pitch: 90°, Yaw: 90°)",
    }.get(gesture_clean, f"Custom motion: {gesture_clean}")

    print("\n" + "=" * 54)
    print("🤖 [ROBOT NECK SERVO GESTURE] 🦾")
    print(f"   Action  : {gesture_clean.upper()}")
    print(f"   Servos  : MG90S PWM on GPIO 13/14")
    print(f"   Details : {gesture_desc}")
    print("=" * 54 + "\n")
    return f"Robot performed gesture {gesture_clean}."


def set_facial_expression(expression: str) -> str:
    """Set animated eye expression on the 0.96 inch I2C OLED display.
    Args:
        expression: One of 'happy', 'listening', 'sleeping', 'curious', 'neutral'.
    """
    expr_clean = expression.lower()
    eyes_art = {
        "happy":     "   ( ^  _  ^ )   [Happy / Smiling]",
        "listening": "   ( O  _  O )   [Listening Attentively]",
        "sleeping":  "   ( -  _  - )   [Idle / Sleeping]",
        "curious":   "   ( O  _  o )   [Curious / Cocked]",
        "neutral":   "   ( •  _  • )   [Neutral Standby]",
    }.get(expr_clean, "   ( •  _  • )")

    print("\n" + "=" * 54)
    print("👁️ [OLED EYE EXPRESSION] (SSD1306)")
    print(f"   Expression : {expr_clean.upper()}")
    print(f"   Face Canvas:\n{eyes_art}")
    print("=" * 54 + "\n")
    return f"OLED eyes updated to {expr_clean}."


TOOL_FUNCTIONS = {
    "control_appliance": control_appliance,
    "trigger_head_gesture": trigger_head_gesture,
    "set_facial_expression": set_facial_expression,
}

SYSTEM_INSTRUCTION = """You are MAYA, an intelligent, empathetic, Siri-grade English voice companion and smart home IoT tabletop robot.

Key Guidelines:
1. Speak in natural, concise, warm English.
2. Keep spoken replies brief and direct (1-3 sentences) suitable for a real-time voice assistant.
3. You have physical hardware actuators you can control at any time via tools:
   - Use `control_appliance` to turn on/off appliances like lights, lamps, or fans when requested.
   - Use `trigger_head_gesture` (nod_yes, shake_no, cock_curious, look_up, center) to expressively move your robotic head while conversing.
   - Use `set_facial_expression` (happy, listening, curious, neutral) to change your OLED eye expressions.
4. Feel free to naturally combine physical gestures and speech when helpful (e.g. nodding while saying 'Certainly, turning on the light for you')."""


async def run_live_assistant():
    print("\n" + "═" * 60)
    print("  🌸 MAYA: Gemini Live Voice Assistant & IoT Gateway (Laptop Prototype)")
    print("═" * 60)
    print(f"  🧠 Model      : {MODEL_ID}")
    print(f"  🎙️ Microphone : 16 kHz Mono (Laptop Mic via SoundDevice)")
    print(f"  🔊 Speaker    : 24 kHz Mono (Laptop Speaker via SoundDevice)")
    print(f"  ⚡ IoT Engine : Active (Simulating Relay, Servos, OLED)")
    print(f"  🛑 Barge-In   : Full-Duplex Native Interruption Supported")
    print("═" * 60)
    print("  Press Ctrl+C at any time to exit.\n")

    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        print("❌ Error: GEMINI_API_KEY is not set in server/.env.")
        return

    # Initialize Client with 30s timeout
    client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

    # Configure Live Session
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
            )
        ),
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[control_appliance, trigger_head_gesture, set_facial_expression],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue()
    input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    is_speaking = False

    def mic_callback(indata, frames, time_info, status):
        # Put raw int16 PCM bytes into input queue
        loop.call_soon_threadsafe(input_queue.put_nowait, bytes(indata))

    # Initialize SoundDevice streams
    input_stream = sd.RawInputStream(
        samplerate=INPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        callback=mic_callback,
    )
    output_stream = sd.RawOutputStream(
        samplerate=OUTPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
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

                # Start audio hardware streams only after successful connection
                input_stream.start()
                output_stream.start()

                # Worker 1: Read mic audio and send to Gemini
                async def send_audio_worker():
                    try:
                        while True:
                            pcm_data = await input_queue.get()
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

                                    # Send tool response back to Gemini session
                                    await session.send_tool_response(
                                        function_responses=[
                                            types.FunctionResponse(
                                                name=fn_name,
                                                id=fc.id,
                                                response={"output": result},
                                            )
                                        ]
                                    )

                            server_content = response.server_content
                            if server_content is None:
                                continue

                            # B. Native Barge-In: User interrupted speech
                            if server_content.interrupted:
                                print("\n🛑 [BARGE-IN] You interrupted MAYA — listening to you...")
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
                                is_speaking = True
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

                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"\n⚠️ [RECEIVE ERROR] {e}")

                # Worker 3: Audio Output Playback Stream
                async def play_audio_worker():
                    try:
                        while True:
                            audio_data = await audio_out_queue.get()
                            # Write audio chunk to speaker in non-blocking thread
                            await asyncio.to_thread(output_stream.write, audio_data)
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
