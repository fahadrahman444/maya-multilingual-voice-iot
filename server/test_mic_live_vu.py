import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import serial
import serial.tools.list_ports
import numpy as np

def find_esp32_port(default="COM8"):
    try:
        for p in serial.tools.list_ports.comports():
            # 303A is Espressif USB VID
            if "303A" in p.hwid.upper():
                return p.device
            if any(k in p.description.upper() for k in ["CH340", "CP210", "CH343", "ESP32", "USB SERIAL"]):
                return p.device
    except Exception:
        pass
    return default

SERIAL_PORT = os.getenv("ESP32_PORT", find_esp32_port("COM8"))
BAUD_RATE = 115200

print("\n" + "=" * 60)
print("  🔍 MAYA INMP441 HARDWARE CONNECTION MONITOR")
print("=" * 60)
print(f"  Detected ESP32 port: {SERIAL_PORT}")
print("  Listening to INMP441 live stream...")
print("  Gently tap or speak near the mic to see live VU meter.\n")

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    time.sleep(0.3)
    ser.reset_input_buffer()
    ser.write(b"R")
except Exception as e:
    print(f"❌ Could not open {SERIAL_PORT}: {e}")
    exit(1)

try:
    while True:
        if ser.in_waiting >= 512:
            raw = ser.read(512)
            raw = raw.replace(b"\xAA\xBB\xCC\xDD", b"").replace(b"\xDD\xCC\xBB\xAA", b"")
            if len(raw) >= 2:
                arr = np.frombuffer(raw[: (len(raw) // 2) * 2], dtype=np.int16)
                peak = int(np.max(np.abs(arr)))
                rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                zeros_pct = float(np.sum(arr == 0) / len(arr) * 100)
                unique_vals = len(np.unique(arr))

                # Real acoustic sound has broad spectrum; floating pins have 60%+ zeros and static spikes
                if zeros_pct > 40 or unique_vals < 25:
                    if rms > 1000:
                        print(f"\r⚠️  [FAKE RMS: FLOATING WIRE STATIC] RMS: {int(rms):<5} ({zeros_pct:.0f}% zeros) | Check L/R->GND & SD->IO4", end="", flush=True)
                    else:
                        print(f"\r⚠️  [SILENT / DEAD LINE] Peak: 0     | RMS: 0     | Check 3V3, GND, SD(IO4), WS(IO5), SCK(IO6)...", end="", flush=True)
                else:
                    bars = min(int(rms / 100), 20)
                    bar_str = "█" * bars
                    print(f"\r✅ [REAL AUDIO DETECTED!] Peak: {peak:<5} | RMS: {int(rms):<4} | |{bar_str:<20}|", end="", flush=True)
        else:
            time.sleep(0.01)
except KeyboardInterrupt:
    pass
finally:
    try:
        ser.write(b"S")
        ser.close()
    except Exception:
        pass
    print("\n\nMonitor closed.")
