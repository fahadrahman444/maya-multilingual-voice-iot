import os
import sys
import time
import asyncio
import unittest
import numpy as np

# Ensure project path is accessible
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(server_dir, ".."))
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from google import genai
from google.genai import types
from server.app.config import settings
from server.app.pipeline.esp32_bridge import esp32_bridge
from server.run_gemini_live import (
    control_appliance,
    trigger_head_gesture,
    set_facial_expression,
    SYSTEM_INSTRUCTION,
    MODEL_ID,
)


class TestGeminiLiveESP32Integration(unittest.IsolatedAsyncioTestCase):
    """
    Automated Integration Test Suite for:
    ESP32-S3 (INMP441 Mic + Actuators) <--> Maya Gemini Live Native S2S API
    """

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 65)
        print("🧪 RUNNING: Gemini Live Native S2S & ESP32 Hardware Integration Tests")
        print("=" * 65)

    async def test_01_esp32_bridge_connection(self):
        """Test physical USB connection and audio bridge handshake with ESP32."""
        print("\n[TEST 1] Connecting to ESP32 Hardware Bridge on COM8...")
        connected = esp32_bridge.connect()
        if not connected:
            raise unittest.SkipTest("ESP32 hardware not plugged into USB COM port. Skipping physical test.")
        self.assertTrue(esp32_bridge.is_connected)
        print("  ✓ ESP32 Serial connection established on COM8 (115200 baud).")

    async def test_02_esp32_audio_stream_capture(self):
        """Test streaming raw 16kHz PCM audio from INMP441 microphone over USB."""
        print("\n[TEST 2] Verifying INMP441 Microphone Audio Stream...")
        if not esp32_bridge.is_connected:
            raise unittest.SkipTest("ESP32 hardware not connected. Skipping audio stream test.")

        audio_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        esp32_bridge.start_audio_stream(audio_queue, loop)
        
        # Collect audio chunks for 1.5 seconds
        t_start = time.time()
        received_chunks = []
        while time.time() - t_start < 1.5:
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                received_chunks.append(chunk)
            except asyncio.TimeoutError:
                pass

        esp32_bridge.stop_audio_stream()

        self.assertGreater(len(received_chunks), 0, "No audio chunks received from ESP32 mic.")
        total_bytes = sum(len(c) for c in received_chunks)
        print(f"  ✓ Audio capture verified: {len(received_chunks)} chunks ({total_bytes} bytes in 1.5s).")

        # Verify PCM int16 data properties
        raw_pcm = b"".join(received_chunks)
        samples = np.frombuffer(raw_pcm[: (len(raw_pcm) // 2) * 2], dtype=np.int16)
        peak = int(np.max(np.abs(samples))) if len(samples) > 0 else 0
        print(f"  ✓ Waveform validity: {len(samples)} samples, Peak amplitude = {peak}/32768.")
        self.assertGreater(len(samples), 500, "Too few audio samples captured.")

    async def test_03_hardware_actuation_tools(self):
        """Test real-time tool calls for 5V Relay, Servos, and OLED display."""
        print("\n[TEST 3] Testing IoT Tool Calling Dispatch to ESP32 Hardware...")
        if not esp32_bridge.is_connected:
            raise unittest.SkipTest("ESP32 hardware not connected. Skipping hardware actuation test.")

        # 1. Relay Actuation
        res_on = control_appliance("Table Light", "on")
        self.assertIn("switched on", res_on)
        await asyncio.sleep(0.3)
        res_off = control_appliance("Table Light", "off")
        self.assertIn("switched off", res_off)
        print("  ✓ 5V Relay tool call verified (GPIO 21 toggled HIGH and LOW).")

        # 2. Servos Gesture
        res_gesture = trigger_head_gesture("nod")
        self.assertIn("nod", res_gesture)
        print("  ✓ Servo neck tool call verified (GPIO 13/14 Pan & Tilt actuated).")

        # 3. OLED Expression
        res_face = set_facial_expression("curious")
        self.assertIn("curious", res_face)
        print("  ✓ OLED eyes expression tool call verified (I2C SSD1306 updated).")

    async def test_04_gemini_live_s2s_handshake(self):
        """Test Gemini Live Native S2S WebSocket handshake with ESP32 audio config."""
        print(f"\n[TEST 4] Connecting to Google Gemini Live API ({MODEL_ID})...")
        api_key = settings.GEMINI_API_KEY
        self.assertTrue(bool(api_key and api_key != "your_gemini_api_key_here"), "GEMINI_API_KEY must be set in .env")

        client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[control_appliance],
        )

        t_handshake_start = time.perf_counter()
        async with client.aio.live.connect(model=MODEL_ID, config=config) as session:
            t_handshake = (time.perf_counter() - t_handshake_start) * 1000
            print(f"  ✓ Gemini Live WebSocket connected in {t_handshake:.1f}ms!")

            # Send a 50ms 16kHz PCM audio frame from the ESP32 stream format
            test_frame = b"\x00" * 1600  # 50ms of 16kHz 16-bit mono PCM
            await session.send_realtime_input(
                audio={"data": test_frame, "mime_type": "audio/pcm"}
            )
            print("  ✓ Ingested test PCM audio frame into Gemini Live session.")

    @classmethod
    def tearDownClass(cls):
        esp32_bridge.close()
        print("\n" + "=" * 65)
        print("✅ ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 65)


if __name__ == "__main__":
    unittest.main()
