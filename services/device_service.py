import json
import os
import re
import shutil
import subprocess


class WindowsDeviceService:
    """Read-only Windows device inventory. Pairing remains under Windows system consent UI."""
    def bluetooth_devices(self):
        command = "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Compress"
        try:
            output = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True, timeout=12)
            items = json.loads(output or "[]")
            if isinstance(items, dict): items = [items]
            return [{"name": x.get("FriendlyName") or "Unknown", "status": x.get("Status", "Unknown"), "id": x.get("InstanceId", "")} for x in items]
        except Exception as exc:
            return [{"name": "Windows Bluetooth inventory unavailable", "status": str(exc), "id": ""}]

    def bluetooth_phones(self):
        """Group Windows PnP profile endpoints into one card per paired phone."""
        groups = {}
        for item in self.bluetooth_devices():
            match = re.search(r"(?:DEV_|&0&)([0-9A-F]{12})", item["id"], re.IGNORECASE)
            if not match:
                continue
            mac = match.group(1).upper()
            group = groups.setdefault(mac, {"address": mac, "name": None, "status": "Unknown", "profiles": []})
            group["profiles"].append(item["name"])
            if item["status"] == "OK":
                group["status"] = "OK"
            if "BLUETOOTHDEVICE" in item["id"].upper():
                group["name"] = item["name"]
        phones = []
        for group in groups.values():
            if not group["name"]:
                continue
            group["profiles"] = sorted(set(group["profiles"]))
            group["audio_gateway_available"] = "Headset Audio Gateway Service" in group["profiles"]
            phones.append(group)
        return phones

    def usb_phones(self):
        command = "Get-PnpDevice -PresentOnly | Where-Object {$_.FriendlyName -match 'Android|iPhone|Phone|MTP'} | Select-Object FriendlyName,Status | ConvertTo-Json -Compress"
        try:
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True, timeout=12)
            data = json.loads(out or "[]")
            if isinstance(data, dict): data = [data]
            return [{"name": x.get("FriendlyName"), "status": x.get("Status")} for x in data]
        except Exception:
            return []

    @staticmethod
    def _adb_path():
        """Find adb without requiring a fixed Android SDK installation path."""
        project_adb = os.path.join(os.path.dirname(os.path.dirname(__file__)), "platform-tools", "adb.exe")
        candidates = [project_adb, shutil.which("adb")]
        for env in ("ANDROID_SDK_ROOT", "ANDROID_HOME", "LOCALAPPDATA"):
            root = os.environ.get(env)
            if root:
                candidates.append(os.path.join(root, "platform-tools", "adb.exe"))
        return next((path for path in candidates if path and os.path.isfile(path)), None)

    def adb_devices(self):
        adb = self._adb_path()
        if not adb:
            return {"available": False, "adb_path": None, "devices": [], "message": "adb was not found. Install Android Platform Tools or add adb to PATH."}
        try:
            output = subprocess.check_output([adb, "devices", "-l"], text=True, stderr=subprocess.STDOUT, timeout=15)
            rows = []
            for line in output.splitlines()[1:]:
                if not line.strip() or line.startswith("*") or line.startswith("List of devices"):
                    continue
                fields = line.split()
                if len(fields) >= 2:
                    details = {part.split(":", 1)[0]: part.split(":", 1)[1] for part in fields[2:] if ":" in part}
                    rows.append({"serial": fields[0], "state": fields[1], "model": details.get("model", "Unknown"), "transport": details.get("transport_id", "")})
            message = "ADB is connected." if rows else "No ADB devices detected. Unlock the phone and accept the RSA fingerprint prompt."
            return {"available": True, "adb_path": adb, "devices": rows, "message": message}
        except subprocess.CalledProcessError as exc:
            return {"available": True, "adb_path": adb, "devices": [], "message": exc.output.strip()}
        except Exception as exc:
            return {"available": True, "adb_path": adb, "devices": [], "message": str(exc)}

    def test_adb_connection(self):
        info = self.adb_devices()
        authorized = [d for d in info["devices"] if d["state"] == "device"]
        unauthorized = [d for d in info["devices"] if d["state"] == "unauthorized"]
        if authorized:
            info.update({"ok": True, "message": f"Connection test passed: {len(authorized)} authorized device(s)."})
        elif unauthorized:
            info.update({"ok": False, "message": "Phone is visible but not authorized. Accept the RSA debugging dialog on the phone, then refresh."})
        else:
            info.update({"ok": False})
        return info

