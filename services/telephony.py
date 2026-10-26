"""Telephony adapter boundary.

This keeps Android/ADB call control separate from media transport, mirroring the
runtime design used by dedicated HFP call bridges. Audio may be unavailable while
call control remains healthy, and the UI must report that distinction.
"""
import re
import subprocess
from dataclasses import dataclass, asdict

from services.device_service import WindowsDeviceService


@dataclass
class TelephonyStatus:
    transport: str = "adb"
    connected: bool = False
    state: str = "unknown"
    selected_device: str = ""
    last_error: str | None = None


class AdbTelephonyAdapter:
    def __init__(self, devices: WindowsDeviceService, logger):
        self._devices, self._logger = devices, logger
        self.status = TelephonyStatus()

    def _run(self, *args: str, timeout: int = 15) -> str:
        adb = self._devices._adb_path()
        if not adb:
            raise RuntimeError("ADB is not available")
        return subprocess.check_output([adb, *args], text=True, stderr=subprocess.STDOUT, timeout=timeout)

    def refresh(self):
        devices = self._devices.test_adb_connection().get("devices", [])
        active = next((item for item in devices if item["state"] == "device"), None)
        self.status.connected = active is not None
        self.status.selected_device = active["serial"] if active else ""
        self.status.last_error = None
        if not active:
            self.status.state = "disconnected"
            return asdict(self.status)
        try:
            output = self._run("-s", active["serial"], "shell", "dumpsys", "telephony.registry")
            match = re.search(r"mCallState\s*=\s*(\d)", output)
            self.status.state = {"0": "idle", "1": "ringing", "2": "active"}.get(match.group(1) if match else "", "unknown")
        except Exception as exc:
            self.status.state, self.status.last_error = "unknown", str(exc)
        return asdict(self.status)

    def dial(self, number: str):
        clean = re.sub(r"[^\d+]", "", number)
        if len(clean.replace("+", "")) < 3:
            raise ValueError("A valid phone number is required")
        current = self.refresh()
        if not current["connected"]:
            raise RuntimeError("No authorized Android device is connected through ADB")
        self._run("-s", current["selected_device"], "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean}")
        self._logger.info("ADB dial requested for %s", clean)
        return self.refresh()

    def answer(self):
        current = self.refresh()
        if not current["connected"]:
            raise RuntimeError("No authorized Android device is connected through ADB")
        self._run("-s", current["selected_device"], "shell", "input", "keyevent", "5")
        self._logger.info("ADB answer requested")
        return self.refresh()

    def hangup(self):
        current = self.refresh()
        if not current["connected"]:
            raise RuntimeError("No authorized Android device is connected through ADB")
        self._run("-s", current["selected_device"], "shell", "input", "keyevent", "6")
        self._logger.info("ADB hangup requested")
        return self.refresh()
