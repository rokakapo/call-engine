"""Runtime coordinator: telephony, audio transport, and AI remain independent."""
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread
import time

import audioop
import webrtcvad

from services.audio_pipeline import AudioPipeline
from services.telephony import AdbTelephonyAdapter
try:
    from services.android_audio_stream import AndroidAudioStream
except Exception:
    AndroidAudioStream = None


@dataclass
class RuntimeState:
    call_state: str = "unknown"
    media_transport: str = "none"
    media_state: str = "stopped"
    session_id: str | None = None
    failure: str | None = None


class CallRuntime:
    def __init__(self, telephony: AdbTelephonyAdapter, hfp: AudioPipeline, logger, android_audio=None):
        self.telephony, self.hfp, self.logger = telephony, hfp, logger
        self.android = android_audio
        self.state, self._events = RuntimeState(), deque(maxlen=100)
        self._hfp_waiter = None
        self._hfp_arm_cancel = Event()
        self._android_waiter = None
        self._android_arm_cancel = Event()
        self._android_vad = webrtcvad.Vad(2)
        self._android_lock = Lock()
        self._android_total = 0
        self._android_speech = 0
        self._android_rms = 0.0
        self._android_last_voice = None
        if self.android is not None:
            self.android.on_frame(self._on_android_frame)

    def _on_android_frame(self, frame, sr):
        try:
            voiced = self._android_vad.is_speech(frame, sr)
        except Exception:
            voiced = False
        level = audioop.rms(frame, 2) / 32768.0
        with self._android_lock:
            self._android_total += 1
            self._android_rms = level
            if voiced:
                self._android_speech += 1
                self._android_last_voice = time.time()

    def _android_snapshot(self):
        snap = self.android.snapshot() if self.android is not None else {}
        with self._android_lock:
            return {
                "stream": snap,
                "total_frames": self._android_total,
                "speech_frames": self._android_speech,
                "rms": self._android_rms,
                "last_voice_at": self._android_last_voice,
            }

    def _event(self, kind: str, detail: str):
        event = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "detail": detail}
        self._events.appendleft(event)
        self.logger.info("runtime %s: %s", kind, detail)

    def health(self):
        hfp_pairs = self.hfp.hfp_endpoints()
        telephony = self.telephony.refresh()
        if telephony["state"] != self.state.call_state:
            self.state.call_state = telephony["state"]
            self._event("call_state_changed", telephony["state"])
        out = {
            "telephony": telephony,
            "hfp": {"pairs": hfp_pairs, "direct_capture_probe": "not_run",
                    "note": "Windows HFP endpoint presence does not prove user-mode capture access."},
            "runtime": asdict(self.state),
            "events": list(self._events),
        }
        if self.android is not None:
            out["android"] = self._android_snapshot()
        return out

    def start_android(self):
        if self.android is None:
            raise RuntimeError("Android audio stream not configured")
        serial = self.telephony.refresh()["selected_device"]
        if not serial:
            raise RuntimeError("No authorized Android device is connected through ADB")
        with self._android_lock:
            self._android_total = 0
            self._android_speech = 0
            self._android_rms = 0.0
            self._android_last_voice = None
        snap = self.android.start(serial=serial)
        self.state.media_transport, self.state.media_state = "android-audio-stream", "monitoring"
        self.state.session_id = f"android-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state.failure = None
        self._event("android_monitor_started", str(snap.get("connected")))
        return {**snap, "android_vad": self._android_snapshot()}

    def arm_android_for_active_call(self, timeout_seconds: int = 60):
        if self.android is None:
            raise RuntimeError("Android audio stream not configured")
        if self._android_waiter and self._android_waiter.is_alive():
            raise RuntimeError("Android audio is already armed and waiting for an active call")
        self._android_arm_cancel.clear()
        self.state.media_transport, self.state.media_state = "android-audio-stream", "waiting-for-active-call"
        self.state.session_id = f"android-arm-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state.failure = None
        self._event("android_armed", f"waiting up to {timeout_seconds}s for an active call")

        def wait_for_call():
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline and not self._android_arm_cancel.is_set():
                try:
                    state = self.telephony.refresh()["state"]
                    if state == "active":
                        self._event("android_active_call_detected", "")
                        self.start_android()
                        return
                except Exception as exc:
                    self.state.failure = str(exc)
                    self.state.media_state = "failed"
                    self._event("android_arm_failed", str(exc))
                    return
                time.sleep(1)
            if self._android_arm_cancel.is_set():
                self._event("android_arm_cancelled", "operator request")
            else:
                self.state.media_state, self.state.media_transport = "stopped", "none"
                self._event("android_arm_timeout", "no active call within %ss" % timeout_seconds)

        self._android_waiter = Thread(target=wait_for_call, name="android-active-call-waiter", daemon=True)
        self._android_waiter.start()
        return asdict(self.state)

    def start_hfp(self, device_name: str):
        try:
            self.hfp.attach_hfp(device_name)
            capture = self.hfp.start_monitor()
        except Exception as exc:
            call_state = self.telephony.refresh()["state"]
            self.state.failure = str(exc)
            self.state.media_state = "failed"
            self._event("hfp_monitor_failed", f"call_state={call_state}; {exc}")
            raise RuntimeError(
                f"Direct HFP capture was rejected while the ADB call state was '{call_state}'. "
                "Keep a real call connected until this test completes; if it is rejected again while state is 'active', "
                "this Windows Bluetooth driver does not expose application capture."
            ) from exc
        self.state.media_transport, self.state.media_state = "windows-hfp-direct", "monitoring"
        self.state.session_id = f"media-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state.failure = None
        self._event("hfp_monitor_started", capture["capture_source"])
        return capture

    def arm_hfp_for_active_call(self, device_name: str, timeout_seconds: int = 60):
        if self._hfp_waiter and self._hfp_waiter.is_alive():
            raise RuntimeError("HFP is already armed and waiting for an active call")
        self._hfp_arm_cancel.clear()
        self.state.media_transport, self.state.media_state = "windows-hfp-direct", "waiting-for-active-call"
        self.state.session_id = f"hfp-arm-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state.failure = None
        self._event("hfp_armed", f"waiting up to {timeout_seconds}s for an active call")

        def wait_for_call():
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline and not self._hfp_arm_cancel.is_set():
                try:
                    state = self.telephony.refresh()["state"]
                    if state == "active":
                        self._event("hfp_active_call_detected", device_name)
                        self.start_hfp(device_name)
                        return
                except Exception as exc:
                    self.state.failure = str(exc)
                    self.state.media_state = "failed"
                    self._event("hfp_arm_failed", str(exc))
                    return
                time.sleep(1)
            if self._hfp_arm_cancel.is_set():
                self._event("hfp_arm_cancelled", "operator request")
            else:
                self.state.media_state, self.state.media_transport = "stopped", "none"
                self._event("hfp_arm_timeout", "no active call within 60 seconds")

        self._hfp_waiter = Thread(target=wait_for_call, name="hfp-active-call-waiter", daemon=True)
        self._hfp_waiter.start()
        return asdict(self.state)

    def stop_media(self):
        self._hfp_arm_cancel.set()
        self._android_arm_cancel.set()
        if self.hfp.status.monitoring:
            capture = self.hfp.stop_monitor()
        else:
            capture = self.hfp.snapshot()
        if self.android is not None and self.android.status.running:
            self.android.stop()
        self.state.media_state, self.state.media_transport = "stopped", "none"
        self._event("media_stopped", "operator request")
        return capture

    def dial(self, number: str):
        result = self.telephony.dial(number)
        self._event("dial_requested", number)
        return result

    def answer(self):
        result = self.telephony.answer()
        self._event("answer_requested", result["selected_device"])
        return result

    def hangup(self):
        result = self.telephony.hangup()
        self.stop_media()
        self._event("hangup_requested", result["selected_device"])
        return result
