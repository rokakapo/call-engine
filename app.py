from pathlib import Path
import webview
from services.ai_engine import AiConversationEngine
from services.audio_pipeline import AudioPipeline
from services.android_audio_stream import AndroidAudioStream
from services.call_controller import CallController
from services.device_service import WindowsDeviceService
from services.logging_service import configure_logging
from services.runtime import CallRuntime
from services.telephony import AdbTelephonyAdapter

logger = configure_logging()
ai, audio, devices, calls = AiConversationEngine(), AudioPipeline(), WindowsDeviceService(), CallController(logger)
telephony = AdbTelephonyAdapter(devices, logger)
android_audio = AndroidAudioStream(devices._adb_path() if hasattr(devices, "_adb_path") else r"D:\x1\call-engine\platform-tools\adb.exe")
runtime = CallRuntime(telephony, audio, logger, android_audio=android_audio)

class Api:
    def get_devices(self): return {"bluetooth": devices.bluetooth_phones(), "usb": devices.usb_phones()}
    def get_runtime_health(self): return runtime.health()
    def get_audio_status(self): return audio.snapshot()
    def get_adb_devices(self): return devices.adb_devices()
    def test_adb_connection(self): return devices.test_adb_connection()
    def get_status(self): return {"call": calls.snapshot(), "audio": audio.status.__dict__}
    def save_provider(self, config):
        try: ai.set_config(config); return {"ok": True}
        except ValueError as exc: return {"ok": False, "message": str(exc)}
    def test_provider(self): return ai.test_connection()
    def fetch_models(self):
        try: return {"ok": True, "models": ai.fetch_models()}
        except Exception as exc: return {"ok": False, "message": str(exc), "models": []}
    def dial(self, number):
        try: return {"ok": True, "call": runtime.dial(number)}
        except (ValueError, RuntimeError) as exc: return {"ok": False, "message": str(exc)}
    def connect_demo(self):
        try: return {"ok": True, "call": calls.connect()}
        except ValueError as exc: return {"ok": False, "message": str(exc)}
    def answer(self):
        try: return {"ok": True, "call": runtime.answer()}
        except RuntimeError as exc: return {"ok": False, "message": str(exc)}
    def hangup(self):
        try: return {"ok": True, "call": runtime.hangup()}
        except RuntimeError as exc: return {"ok": False, "message": str(exc)}
    def hfp_endpoints(self): return audio.hfp_endpoints()
    def arm_hfp_monitor(self, name):
        try: return {"ok": True, "runtime": runtime.arm_hfp_for_active_call(name)}
        except Exception as exc: return {"ok": False, "message": str(exc)}
    def start_android_monitor(self):
        try: return {"ok": True, "runtime": runtime.start_android()}
        except Exception as exc: return {"ok": False, "message": str(exc)}
    def arm_android_monitor(self):
        try: return {"ok": True, "runtime": runtime.arm_android_for_active_call()}
        except Exception as exc: return {"ok": False, "message": str(exc)}
    def get_android_status(self): return runtime.health().get("android", {}) if hasattr(runtime, "health") else {}
    def stop_hfp_monitor(self): return {"ok": True, "audio": runtime.stop_media()}
    def process_transcript(self, text):
        try: return {"ok": True, "reply": ai.reply(text)}
        except Exception as exc: logger.exception("AI reply failed"); return {"ok": False, "message": str(exc)}

if __name__ == "__main__":
    page = (Path(__file__).parent / "static" / "index.html").as_uri()
    webview.create_window("Call Engine", page, js_api=Api(), width=1320, height=840, min_size=(960, 650))
    webview.start(debug=True)
