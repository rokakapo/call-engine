from dataclasses import asdict, dataclass
from threading import Lock
import time
import audioop

import sounddevice as sd
import webrtcvad


@dataclass
class AudioPipelineStatus:
    echo_cancellation: bool = False
    vad_enabled: bool = True
    capture_source: str = "Not attached"
    output_sink: str = "Not attached"
    sample_rate: int = 8000
    monitoring: bool = False
    speech_frames: int = 0
    total_frames: int = 0
    rms: float = 0.0
    last_voice_at: float | None = None


class AudioPipeline:
    """Real Windows endpoint capture with 20 ms WebRTC VAD frames.

    It deliberately contains no call-control logic. The selected HFP endpoints are
    ordinary Windows capture/render devices and must be active for a live call.
    """
    def __init__(self):
        self.status = AudioPipelineStatus()
        self._stream = None
        self._lock = Lock()
        self._vad = webrtcvad.Vad(2)

    @staticmethod
    def hfp_endpoints():
        devices = sd.query_devices()
        pairs = {}
        for index, device in enumerate(devices):
            name = device["name"]
            if "Hands-Free HF Audio" not in name:
                continue
            # Windows puts the remote device name between the final parentheses.
            label = name.rsplit("(", 1)[-1].rstrip(")").strip() if "(" in name else name
            pair = pairs.setdefault(label, {"name": label, "input": None, "output": None, "sample_rate": int(device["default_samplerate"])})
            entry = {"index": index, "name": name, "channels": device["max_input_channels"] or device["max_output_channels"]}
            if device["max_input_channels"]:
                pair["input"] = entry
            if device["max_output_channels"]:
                pair["output"] = entry
        return list(pairs.values())

    def attach_hfp(self, device_name: str):
        self.stop_monitor()
        matches = [pair for pair in self.hfp_endpoints() if device_name.lower() in pair["name"].lower()]
        if not matches:
            raise ValueError("No Windows Hands-Free HF Audio endpoint is available for this phone")
        pair = matches[0]
        if not pair["input"] or not pair["output"]:
            raise ValueError("The phone needs both HFP input and output endpoints")
        self.status.capture_source = pair["input"]["name"]
        self.status.output_sink = pair["output"]["name"]
        self.status.sample_rate = pair["sample_rate"]
        self.status.echo_cancellation = False  # Hardware/driver AEC capability has not been negotiated.
        return self.snapshot()

    def start_monitor(self):
        if self.status.capture_source == "Not attached":
            raise ValueError("Choose an HFP audio gateway before starting monitoring")
        self.stop_monitor()
        endpoints = self.hfp_endpoints()
        source = next((pair["input"] for pair in endpoints if pair["input"] and pair["input"]["name"] == self.status.capture_source), None)
        if not source:
            raise ValueError("The selected HFP input endpoint is no longer available")
        samplerate = self.status.sample_rate
        if samplerate not in (8000, 16000, 32000, 48000):
            raise ValueError(f"Unsupported VAD sample rate: {samplerate}")
        blocksize = samplerate // 50  # fixed 20 ms frame, accepted by WebRTC VAD

        def on_audio(indata, frames, time_info, status):
            data = bytes(indata)
            try:
                voiced = self._vad.is_speech(data, samplerate)
            except Exception:
                voiced = False
            level = audioop.rms(data, 2) / 32768.0
            with self._lock:
                self.status.total_frames += 1
                self.status.rms = level
                if voiced:
                    self.status.speech_frames += 1
                    self.status.last_voice_at = time.time()

        try:
            self._stream = sd.RawInputStream(device=source["index"], samplerate=samplerate, channels=1, dtype="int16", blocksize=blocksize, callback=on_audio)
            self._stream.start()
        except sd.PortAudioError as exc:
            self._stream = None
            raise ValueError(
                "Windows HFP driver rejected direct application access to this phone audio endpoint. "
                "This endpoint is visible but protected/unavailable to the current Windows audio API; retrying the same call state will not fix it."
            ) from exc
        self.status.monitoring = True
        return self.snapshot()

    def stop_monitor(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.status.monitoring = False
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            return asdict(self.status)
