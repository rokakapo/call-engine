import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""Quick RMS verification for AndroidAudioStream during a real call.

Usage:
  python scripts/verify_android_capture.py [serial]
"""
import math
import struct
import time

from services.android_audio_stream import AndroidAudioStream

ADB = r"D:\x1\call-engine\platform-tools\adb.exe"
SERIAL = sys.argv[1] if len(sys.argv) > 1 else "a6858t65jvmbsokn"
DURATION = 5.0

rms_values = []


def on_frame(frame, sr):
    n = len(frame) // 2
    samples = struct.unpack(f"<{n}h", frame)
    rms = math.sqrt(sum(s * s for s in samples) / max(n, 1))
    rms_values.append(rms)


def main():
    s = AndroidAudioStream(ADB)
    s.on_frame(on_frame)
    snap = s.start(serial=SERIAL)
    print("connected:", snap["connected"])
    time.sleep(DURATION)
    s.stop()
    if not rms_values:
        print("NO FRAMES RECEIVED")
        return
    print(f"frames={len(rms_values)}")
    print(f"rms min={min(rms_values):.1f} max={max(rms_values):.1f} avg={sum(rms_values)/len(rms_values):.1f}")
    nonzero = [r for r in rms_values if r > 50]
    print(f"non-silent frames: {len(nonzero)}/{len(rms_values)}")


if __name__ == "__main__":
    main()
