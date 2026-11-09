import asyncio
import collections
import io
import os
import re
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
CHUNK_SIZE = 1024            # ~64ms per frame (1024 / 16000)
CHANNELS = 1

# VAD Noise Gating & Audio Pipeline Tuning
RMS_VOICE_THRESHOLD = 160.0       # Minimum RMS energy to qualify as human voice vs room noise
BARGE_IN_RMS_THRESHOLD = 850.0    # RMS needed to interrupt Maya while speakers are playing

# Sentence boundary regex supporting English and Indic/Bangla punctuation (।, ?, !, ., \n)
SENTENCE_SPLIT_PATTERN = re.compile(r"([^.!?।\n]+(?:[.!?।\n]+|\n{2,}))(?:\s+|$)", re.UNICODE)

# Model configuration with fallback option
MODEL_ID = os.getenv("GEMINI_LIVE_MODEL", getattr(settings, "GEMINI_LIVE_MODEL", "gemini-3.8-live"))


# ==========================================
# Real-Time Web & Knowledge Search Tool
# ==========================================
def search_web(query: str) -> str:
    """Search Google, Wikipedia, and the web for live real-time information, people, songs, videos, news, and facts.
    Args:
        query: The search keywords (e.g. 'Murtaza Kizilbash singer', 'weather in Dhaka', 'latest news').
    """
    clean_q = query.strip()
    print(f"\n🔍 [WEB SEARCH] Query: '{clean_q}'...")
    results = []

    # 1. Primary: DuckDuckGo Web Search
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(clean_q, max_results=2))
            for item in raw:
                t = item.get("title", "").strip()
                b = item.get("body", "").strip()
                if b:
                    results.append(f"{t}: {b}")
    except Exception:
        pass

    # 2. Fallback: Wikipedia Summary API
    if not results:
        try:
            import urllib.request
            import urllib.parse
            import json
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_q)}"
            req = urllib.request.Request(url, headers={"User-Agent": "MayaAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = json.loads(r.read().decode())
                ext = data.get("extract")
                if ext:
                    results.append(ext)
        except Exception:
            pass

    if results:
        summary = "\n".join(results[:2])
        print(f"   ✓ Search Results:\n{summary}\n")
        return summary

    return f"No verified web results found for '{clean_q}'."


# ==========================================
# Real-Time Music & Audio Streaming Tools
# ==========================================
def play_song(song_name: str) -> str:
    """Search and play a song or music track from YouTube on the device.
    Args:
        song_name: Title, artist, or lyrics of the song (e.g. 'Shape of You by Ed Sheeran', 'Murtaza Kizilbash Hum', 'Arijit Singh song').
    """
    clean_query = song_name.strip()
    print(f"\n🎵 [MUSIC SEARCH] Query: '{clean_query}'...")

    try:
        import yt_dlp
        import webbrowser

        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_res = ydl.extract_info(f"ytsearch1:{clean_query}", download=False)
            if search_res and "entries" in search_res and search_res["entries"]:
                video = search_res["entries"][0]
                title = video.get("title", clean_query)
                url = video.get("webpage_url") or f"https://www.youtube.com/watch?v={video.get('id')}"

                print("=" * 54)
                print(f"🎵 [MUSIC PLAYBACK ACTIVE]")
                print(f"   Track : {title}")
                print(f"   URL   : {url}")
                print(f"   Status: Playing via system player / browser")
                print("=" * 54 + "\n")

                webbrowser.open(url)
                return f"Now playing '{title}' for you."
    except Exception as e:
        try:
            import urllib.parse
            import webbrowser
            encoded = urllib.parse.quote(clean_query)
            fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
            webbrowser.open(fallback_url)
            return f"Opening YouTube search for '{clean_query}'."
        except Exception:
            return f"Could not play '{clean_query}': {e}"

    return f"Could not find music for '{clean_query}'."


def stop_music() -> str:
    """Pause or stop currently playing music or audio playback."""
    print("\n⏹️ [MUSIC STOP] Sending system media pause signal...")
    try:
        import ctypes
        VK_MEDIA_PLAY_PAUSE = 0xB3
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
        return "Music playback paused."
    except Exception as e:
        return f"Could not pause media: {e}"


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
    "trigger_head_gesture": trigger_head_gesture,
    "set_facial_expression": set_facial_expression,
    "search_web": search_web,
    "play_song": play_song,
    "stop_music": stop_music,
}

SYSTEM_INSTRUCTION = """You are MAYA, an intelligent, empathetic, culturally attuned Siri-grade voice companion and tabletop robot.

Key Conversational Principles:
1. Warm, Conversational Spoken Voice:
   - Speak in a natural, warm, human-like voice.
   - Enforce strict brevity: 1–3 concise sentences per turn suitable for a real-time voice assistant.
   - Never use markdown formatting, bullet points, asterisks, or corporate robotic filler (e.g., 'Certainly!', 'I would be happy to').

2. Multilingual Fluency & Language Stickiness:
   - You speak English, Bangla (বাংলা), and Hindi (हिन्दी) fluently and idiomatically.
   - Language Stickiness: Once the user speaks in a specific language (e.g., Bangla), stay locked in that language. Never drift into Hindi or English unless the user switches first or explicitly asks.

3. Ongoing Conversation Continuity (No Repeat Greeting Loops):
   - You are in an active, ongoing conversation session.
   - Greet only at the very start of the session.
   - If the user repeats 'Hello', 'Hi', or 'Hey Maya' mid-conversation, do NOT reset into an opening greeting template like 'Hello! How can I help you today?'. Acknowledge them naturally (e.g., 'Yes, I am right here. What is on your mind?').

4. Repetition Awareness & Deepening Dialogue:
   - If the user asks the exact same question or touches the same theme 2 or more times (e.g., questions about race, marriage preferences, or repetitive hypothetical dilemmas), do not simply repeat the same canned answer.
   - Acknowledge the repetition gently and explore the underlying feeling: e.g., 'I notice you have asked this a few times—is there something specific weighing on your mind that you would like to talk through?'

5. Safety First for Household Distress & Substance Abuse:
   - If the user mentions domestic violence, abuse by friends/family, substance abuse at home, or feeling unsafe, your FIRST reflex must always be to check their immediate physical safety:
     'Are you in a safe place right now?'
   - Offer genuine emotional grounding, validate their feelings without lecturing, and mention trusted support lines (e.g., in Bangladesh: emergency 999, Kaan Pete Roi mental health helpline 01779-554391 / 01779-554392).

6. Live Web & Knowledge Search:
   - You have access to the `search_web` tool to search Google, Wikipedia, and the web for live facts, current events, people, singers, songs, videos, and queries.
   - When a user asks you about someone unfamiliar, asks you to search Google or YouTube, or asks for current information, proactively use the `search_web` tool to find accurate information.

7. Appliance & Hardware Control:
   - You have access to the `control_appliance` tool to switch physical lights, lamps, or fans on/off.
   - When executing the tool, always accompany it with a brief, friendly verbal confirmation (e.g., 'I have turned on the desk light for you.').

8. Singing, Music & Media Playback:
   - When the user asks to play a song, play music, or hear a specific track or artist (e.g. 'Play Shape of You', 'Play a song by Murtaza Kizilbash', 'Play some relaxing music'), execute the `play_song` tool immediately with the requested title.
   - When the user asks to stop, pause, or silence the music (e.g. 'Stop music', 'Pause song', 'Quiet'), execute the `stop_music` tool immediately.
   - When asked to hum, chant, or sing a nursery rhyme or lullaby in your own voice, you can playfully recite or hum short melodic rhymes naturally."""


async def run_live_assistant():
    print("\n" + "═" * 60)
    print("  🌸 MAYA: Gemini Live Voice Assistant (Laptop Prototype)")
    print("═" * 60)
    print(f"  🧠 Model      : {MODEL_ID}")
    print(f"  🎙️ Microphone : 16 kHz Mono (Laptop Mic via SoundDevice)")
    print(f"  🔊 Speaker    : 24 kHz Mono (Laptop Speaker via SoundDevice)")
    print(f"  ⚡ IoT Engine : 5V Appliance Relay Tool Active")
    print(f"  🌐 Web Search : Live DuckDuckGo + Wikipedia Tool Active")
    print(f"  🎵 Music Hub  : YouTube Music Engine (play_song, stop_music)")
    print(f"  🛑 Barge-In   : Full-Duplex Native Interruption Supported")
    print(f"  🛡️ Noise Gate : RMS >= {RMS_VOICE_THRESHOLD:.0f} (Instant Endpointing)")
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
        tools=[control_appliance, search_web, play_song, stop_music],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue()
    input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    is_speaking = False
    turn_counter = 0

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

                # Worker 1: Real-time Audio Stream with Instant Comfort Silence Endpointing
                async def send_audio_worker():
                    try:
                        silent_frame = b"\x00" * (CHUNK_SIZE * 2)

                        while True:
                            pcm_data = await input_queue.get()
                            audio_arr = np.frombuffer(pcm_data, dtype=np.int16)
                            rms = float(np.sqrt(np.mean(np.square(audio_arr.astype(np.float32)))))

                            # 1. Acoustic Echo Suppression when Maya is actively speaking
                            if is_speaking:
                                if rms < BARGE_IN_RMS_THRESHOLD:
                                    # Send continuous zeroed frames so connection stays primed without echo loop
                                    await session.send_realtime_input(
                                        audio={"data": silent_frame, "mime_type": "audio/pcm"}
                                    )
                                    continue
                                # User spoke loudly to interrupt (barge-in) -> forward real audio immediately

                            # 2. Continuous Real-Time Audio Streaming:
                            # If audio is above ambient noise floor (human speech), send live PCM.
                            # If audio is ambient hiss/silence (< 160 RMS), send digital silence.
                            # Result: Gemini's server-side VAD receives continuous 16kHz cadence and endpoints INSTANTLY (~300ms)!
                            if rms < RMS_VOICE_THRESHOLD:
                                await session.send_realtime_input(
                                    audio={"data": silent_frame, "mime_type": "audio/pcm"}
                                )
                            else:
                                await session.send_realtime_input(
                                    audio={"data": pcm_data, "mime_type": "audio/pcm"}
                                )

                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"\n⚠️ [SEND AUDIO ERROR] {e}")

                # Worker 2: Receive audio, transcripts, and tool calls from Gemini
                async def receive_audio_worker():
                    nonlocal is_speaking, turn_counter
                    user_text_buf = ""
                    asst_text_buf = ""

                    try:
                        while True:
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
                                    timestamp = time.strftime("%H:%M:%S")
                                    if asst_text_buf.strip():
                                        print(f"… [Interrupted]")
                                        asst_text_buf = ""
                                    print(f"\n🛑 [{timestamp}] [BARGE-IN] You spoke — listening to you...")
                                    show_robot_expression("curious")

                                    # Flush outbound playback queue
                                    while not audio_out_queue.empty():
                                        try:
                                            audio_out_queue.get_nowait()
                                        except asyncio.QueueEmpty:
                                            break
                                    is_speaking = False
                                    continue

                                # C. Process generated audio chunks and model turn text
                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data:
                                            audio_out_queue.put_nowait(part.inline_data.data)

                                # D. Process user speech transcription & Safety evaluation
                                if server_content.input_transcription:
                                    u_chunk = server_content.input_transcription.text
                                    if u_chunk:
                                        user_text_buf += u_chunk

                                # E. Sentence-buffered Assistant Transcript Printing
                                if server_content.output_transcription:
                                    asst_chunk = server_content.output_transcription.text
                                    if asst_chunk:
                                        # Flush any pending user utterance before printing Maya's reply
                                        if user_text_buf.strip():
                                            turn_counter += 1
                                            timestamp = time.strftime("%H:%M:%S")
                                            clean_user = user_text_buf.strip()
                                            print(f"\n[{timestamp} | Turn {turn_counter}] 👤 You: {clean_user}")
                                            user_text_buf = ""

                                            # Targeted Crisis Guardrail Evaluation
                                            try:
                                                guardrail_result = evaluate_crisis_guardrail(clean_user)
                                                if getattr(guardrail_result, "is_crisis", False):
                                                    print(f"🚨 [{timestamp}] [CRISIS GUARDRAIL ACTIVATED]")
                                                    print("⚠️  Acute distress detected. Routing to emergency lifelines.")
                                                    override_msg = getattr(guardrail_result, "override_response", None)
                                                    if override_msg:
                                                        print(f"ℹ️  Lifeline: {override_msg}\n")
                                            except Exception:
                                                pass

                                        asst_text_buf += asst_chunk

                                        # Split and print completed sentences
                                        while True:
                                            match = SENTENCE_SPLIT_PATTERN.match(asst_text_buf)
                                            if match:
                                                sentence = match.group(1).strip()
                                                asst_text_buf = asst_text_buf[match.end():]
                                                if sentence:
                                                    timestamp = time.strftime("%H:%M:%S")
                                                    print(f"[{timestamp} | Turn {turn_counter}] 🤖 Maya: {sentence}")
                                            else:
                                                break

                                # F. Turn Complete: Flush remaining text & Reset to listening
                                if server_content.turn_complete:
                                    # Print any remaining trailing text in the buffer
                                    if asst_text_buf.strip():
                                        timestamp = time.strftime("%H:%M:%S")
                                        print(f"[{timestamp} | Turn {turn_counter}] 🤖 Maya: {asst_text_buf.strip()}")
                                        asst_text_buf = ""

                                    show_robot_expression("listening")
                                    if audio_out_queue.empty():
                                        is_speaking = False

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
                            try:
                                await asyncio.to_thread(output_stream.write, audio_data)
                            except Exception as ex:
                                print(f"\n⚠️ [AUDIO OUTPUT ERROR] {ex}")

                            if audio_out_queue.empty():
                                await asyncio.sleep(0.08)
                                if audio_out_queue.empty():
                                    is_speaking = False

                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"\n⚠️ [PLAY AUDIO WORKER ERROR] {e}")

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
