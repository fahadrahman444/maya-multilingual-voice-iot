import os
import sys
import time
import threading
import serial
import serial.tools.list_ports
from typing import Optional

def find_esp32_port(default: str = "COM8") -> str:
    """Auto-detect active ESP32 COM port by VID/PID or driver description."""
    try:
        for p in serial.tools.list_ports.comports():
            if "303A" in p.hwid.upper():
                return p.device
            if any(k in p.description.upper() for k in ["CH340", "CP210", "CH343", "ESP32", "USB SERIAL"]):
                return p.device
    except Exception:
        pass
    return default

class ESP32HardwareBridge:
    """
    High-Speed USB Serial Bridge between Maya's AI Core (Gemini Live)
    and the physical ESP32-S3 IoT tabletop robot.
    """
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = os.getenv("ESP32_PORT", port or find_esp32_port("COM8"))
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self._running: bool = False
        self._reader_thread: Optional[threading.Thread] = None
        self._audio_queue = None
        self._loop = None

    def connect(self, retries: int = 3, retry_delay: float = 1.0) -> bool:
        """Attempt connection to ESP32 on specified COM port with automatic retries."""
        for attempt in range(1, retries + 1):
            try:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
                time.sleep(0.3)
                self.ser.reset_input_buffer()
                self.is_connected = True
                print(f"✅ [ESP32 HARDWARE BRIDGE] Connected to robot on {self.port}!")
                return True
            except Exception as e:
                if attempt < retries:
                    time.sleep(retry_delay)
                else:
                    print(f"ℹ️ [ESP32 HARDWARE BRIDGE] {self.port} unavailable ({e}). Using laptop mic.")
                    self.is_connected = False
                    return False
        return False

    def start_audio_stream(self, queue, loop):
        """Start streaming 16kHz PCM audio from INMP441 directly into asyncio Queue."""
        if not self.is_connected or not self.ser:
            return

        self._audio_queue = queue
        self._loop = loop
        self._running = True

        # Send command 'R' to tell ESP32 to start streaming audio
        try:
            self.ser.write(b"R")
        except Exception:
            pass

        def _read_worker():
            # Read 512-byte frames (256 samples @ 16kHz = 16ms) with stream alignment
            frame_size = 512
            buffer = bytearray()
            sync_marker = b"\xAA\xBB\xCC\xDD"

            while self._running:
                try:
                    if self.ser and self.ser.in_waiting > 0:
                        chunk = self.ser.read(self.ser.in_waiting)
                        if chunk:
                            buffer.extend(chunk)
                            if sync_marker in buffer:
                                buffer = bytearray(bytes(buffer).replace(sync_marker, b""))

                            while len(buffer) >= frame_size:
                                frame = bytes(buffer[:frame_size])
                                del buffer[:frame_size]
                                self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, frame)
                    else:
                        time.sleep(0.002)
                except Exception:
                    break

        self._reader_thread = threading.Thread(target=_read_worker, daemon=True)
        self._reader_thread.start()
        print("🎤 [ESP32 HARDWARE BRIDGE] INMP441 I2S Audio Stream Active (16 kHz Mono).")

    def stop_audio_stream(self):
        """Pause audio streaming from ESP32."""
        self._running = False
        if self.is_connected and self.ser:
            try:
                self.ser.write(b"S")
            except Exception:
                pass

    def control_relay(self, state: bool):
        """Actuate physical 5V Relay on GPIO 21."""
        if self.is_connected and self.ser:
            try:
                self.ser.write(b"1" if state else b"0")
                status = "ON (HIGH)" if state else "OFF (LOW)"
                print(f"⚡ [HARDWARE RELAY] Pin GPIO 21 -> {status}")
            except Exception as e:
                print(f"⚠️ [HARDWARE RELAY] Write error: {e}")

    def trigger_gesture(self, gesture: str):
        """Actuate physical 2-DOF MG90S Servos on GPIO 13/14."""
        if self.is_connected and self.ser:
            try:
                g = gesture.lower()
                cmd = b"h" if ("happy" in g or "nod" in g) else (b"c" if ("curious" in g or "tilt" in g) else b"s")
                self.ser.write(cmd)
                print(f"🤖 [HARDWARE SERVOS] Motion command sent: {g}")
            except Exception as e:
                print(f"⚠️ [HARDWARE SERVOS] Write error: {e}")

    def set_expression(self, expression: str):
        """Update animated OLED eyes on SSD1306 (I2C GPIO 8/9)."""
        if self.is_connected and self.ser:
            try:
                e = expression.lower()
                cmd = b"h" if "happy" in e else (b"c" if "curious" in e else (b"l" if "listen" in e else b"h"))
                self.ser.write(cmd)
                print(f"👁️ [HARDWARE OLED] Face updated: {e}")
            except Exception as e:
                print(f"⚠️ [HARDWARE OLED] Write error: {e}")

    def close(self):
        """Clean shutdown of serial link."""
        self.stop_audio_stream()
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.is_connected = False
        print("🔌 [ESP32 HARDWARE BRIDGE] Connection closed safely.")

# Global singleton instance
esp32_bridge = ESP32HardwareBridge()
