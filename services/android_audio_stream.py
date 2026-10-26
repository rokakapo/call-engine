"""Android-side duplex call audio capture over ADB.

The phone captures call audio (both directions) via AudioRecord(VOICE_CALL or
VOICE_COMMUNICATION) and streams raw PCM to the PC over a TCP socket forwarded
through ADB. This avoids the Windows HFP/WASAPI limitations entirely.

Requires the companion Android app (android/CallAudioCapture) installed on the
phone and running in capture mode.
"""
from __future__ import annotations

import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass


@dataclass
class AndroidAudioStatus:
    connected: bool = False
    serial: str = ""
    port: int = 19876
    sample_rate: int = 16000
    channels: int = 1
    frames_received: int = 0
    bytes_received: int = 0
    last_error: str | None = None
    running: bool = False


class AndroidAudioStream:
    def __init__(self, adb_path: str):
        self.adb = adb_path
        self.status = AndroidAudioStatus()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._frame_listeners: list = []

    def _adb(self, *args):
        return subprocess.run([self.adb, *args], capture_output=True, text=True)

    def start(self, serial: str, port: int = 19876, sample_rate: int = 16000):
        self.stop()
        self.status = AndroidAudioStatus(serial=serial, port=port, sample_rate=sample_rate, running=True)
        self._stop.clear()
        # Forward phone localhost:port -> PC localhost:port
        self._adb("-s", serial, "forward", f"tcp:{port}", f"tcp:{port}")
        self._thread = threading.Thread(target=self._run, name="android-audio", daemon=True)
        self._thread.start()
        return self.snapshot()

    def _run(self):
        serial = self.status.serial
        port = self.status.port
        sr = self.status.sample_rate
        bytes_per_frame = 2  # int16 mono
        frame_bytes = sr // 50 * bytes_per_frame  # 20 ms
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=10)
            sock.settimeout(2.0)
            self._sock = sock
            self.status.connected = True
            while not self._stop.is_set():
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                with self._lock:
                    self._buf.extend(data)
                    self.status.bytes_received += len(data)
                    while len(self._buf) >= frame_bytes:
                        frame = bytes(self._buf[:frame_bytes])
                        del self._buf[:frame_bytes]
                        self.status.frames_received += 1
                        for cb in list(self._frame_listeners):
                            try:
                                cb(frame, sr)
                            except Exception:
                                pass
        except Exception as exc:
            self.status.last_error = f"{type(exc).__name__}: {exc}"
        finally:
            self.status.connected = False
            self.status.running = False
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
            self._sock = None

    def on_frame(self, cb):
        self._frame_listeners.append(cb)

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self.status.running = False
        self.status.connected = False
        return self.snapshot()

    def snapshot(self):
        return asdict(self.status)
