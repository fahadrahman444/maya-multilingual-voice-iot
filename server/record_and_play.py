import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import wave
import serial
import serial.tools.list_ports
import sounddevice as sd
import numpy as np


def find_esp32_port(default="COM8"):
    try:
        for p in serial.tools.list_ports.comports():
            if "303A" in p.hwid.upper():
                return p.device
            if any(k in p.description.upper() for k in ["CH340", "CP210", "CH343", "ESP32", "USB SERIAL"]):
                return p.device
    except Exception:
        pass
    return default


def main():
    print("\n" + "=" * 60)
    print("  🎙️ MAYA ESP32 INMP441 MIC -> LAPTOP PLAYBACK TEST")
    print("=" * 60)

    port = os.getenv("ESP32_PORT", find_esp32_port("COM8"))
    baud = 115200
    sample_rate = 16000
    record_seconds = 5.0
    wav_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "esp32_recording.wav"))

    print(f"📡 Connecting to ESP32 on {port}...")
    try:
        ser = serial.Serial(port, baud, timeout=1.0)
        time.sleep(0.3)
        ser.reset_input_buffer()
        print(f"✅ Connected to ESP32 on {port}!")
    except Exception as e:
        print(f"❌ Failed to connect to {port}: {e}")
        print("💡 Tip: Close any other monitor or terminal that might have the COM port open.")
        return

    print("\nGet ready to speak into the INMP441 microphone!")
    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", flush=True)
        time.sleep(1)

    print("\n🔴 [RECORDING FOR 5 SECONDS - SPEAK NOW!]")
    ser.write(b"R")

    total_bytes_needed = int(sample_rate * 2 * record_seconds)  # 16-bit = 2 bytes per sample
    raw_buffer = bytearray()
    start_time = time.time()

    try:
        while time.time() - start_time < record_seconds:
            remaining_time = max(0.0, record_seconds - (time.time() - start_time))
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                chunk = chunk.replace(b"\xAA\xBB\xCC\xDD", b"").replace(b"\xDD\xCC\xBB\xAA", b"")
                raw_buffer.extend(chunk)

                # Show live audio energy
                if len(chunk) >= 2:
                    recent = np.frombuffer(chunk[: (len(chunk) // 2) * 2], dtype=np.int16)
                    peak = int(np.max(np.abs(recent)))
                    rms = float(np.sqrt(np.mean(recent.astype(np.float32) ** 2)))
                    bars = min(int(rms / 100), 15)
                    bar_str = "█" * bars
                    print(f"\r  ⏱️ {remaining_time:4.1f}s left | Peak: {peak:<5} | RMS: {int(rms):<4} | |{bar_str:<15}|", end="", flush=True)
            time.sleep(0.01)
    finally:
        ser.write(b"S")
        ser.close()

    print("\n\n⏹️ Recording complete!")

    if len(raw_buffer) < 2:
        print("❌ No audio data received from ESP32.")
        return

    # Trim to even number of bytes for 16-bit PCM
    valid_len = (len(raw_buffer) // 2) * 2
    audio_data = np.frombuffer(raw_buffer[:valid_len], dtype=np.int16)

    max_peak = int(np.max(np.abs(audio_data)))
    avg_rms = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))
    zeros_pct = float(np.sum(audio_data == 0) / len(audio_data) * 100)
    unique_vals = len(np.unique(audio_data))

    print(f"📊 Summary:")
    print(f"   • Total Samples: {len(audio_data)} ({len(audio_data)/sample_rate:.1f} seconds)")
    print(f"   • Peak Amplitude: {max_peak}")
    print(f"   • Average RMS: {int(avg_rms)}")
    print(f"   • Zero Samples: {zeros_pct:.1f}%")

    if zeros_pct > 40 or unique_vals < 30:
        print("\n⚠️  WARNING: High RMS is FALSE STATIC NOISE caused by a loose/floating wire.")
        print(f"   {zeros_pct:.0f}% of the recording is empty zeros with electrical glitch spikes.")
        print("   Key check: Ensure INMP441 'L/R' pin is firmly wired to 'GND' and 'SD' is in GPIO 4.")
    else:
        print("\n✅ Real acoustic voice audio detected!")

    # Save to WAV file
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

    print(f"💾 Saved recording to: {wav_path}")

    # Playback through laptop speakers
    print("\n🔊 PLAYING BACK ON LAPTOP SPEAKERS NOW...")
    try:
        sd.play(audio_data, samplerate=sample_rate)
        sd.wait()
        print("✅ Playback finished!")
    except Exception as e:
        print(f"❌ Playback error: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
