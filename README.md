# Call Engine Desktop

Windows desktop prototype for a consent-based phone-call assistant. Run `py -m pip install -r requirements.txt` then `py app.py`.

## Runtime layout

The runtime keeps the same useful separation as a dedicated HFP/Linux bridge:

- `services/telephony.py`: Android/ADB call actions and state polling only.
- `services/audio_pipeline.py`: direct Windows HFP capture only.
- `services/runtime.py`: session lifecycle, health snapshot, and structured runtime events.
- `services/ai_engine.py`: the STT/LLM/TTS-facing conversation layer; it does not decide call state.

The desktop UI exposes call actions through the ADB adapter, plus Runtime Health so telephony and audio failures cannot be confused. The controls perform real Android actions when pressed; no automatic calls are made.

The Bluetooth page reads Windows paired Bluetooth devices. A discovered HFP endpoint is not treated as proof that Windows permits application capture; the Runtime Health view keeps that result as a separate, explicit media capability check.

The AI provider supports OpenAI-compatible endpoints. No API key is written to logs or persisted unless the operator explicitly supplies it for the running session.

## Android companion app (call audio capture)

`android/CallAudioCapture/` is a minimal Android app that captures call audio on the phone and streams raw PCM (16 kHz mono int16, 20 ms frames) to the PC over a TCP socket forwarded through ADB (`services/android_audio_stream.py`, port 19876).

### Install (MIUI/HyperOS)
ADB install is blocked unless Developer options are configured:
1. Settings → Additional settings → Developer options.
2. Enable: **USB debugging**, **Install via USB**, **USB debugging (Security settings)**.
3. Keep screen on; approve the install prompt on the phone.
4. `adb install -r android/.../app-debug.apk` (or use the GitHub Actions artifact).

### Run
1. Open the app → tap **Start capture** → grant **RECORD_AUDIO**.
2. On PC: `adb forward tcp:19876 tcp:19876` (handled automatically by `AndroidAudioStream.start`).
3. `AndroidAudioStream(adb_path).start(serial=...)` then `on_frame(cb)`.

### Known limitations on HyperOS/MIUI
- `MediaRecorder.AudioSource.VOICE_CALL` is **not available** on HyperOS (AudioRecord reports `STATE_UNINITIALIZED`); the app falls back to `VOICE_COMMUNICATION`. This captures the microphone path and (during a call) the remote party via the speakerphone/voice-comm routing, but true bidirectional `VOICE_CALL` duplex is **not** achievable on this device/OS. Treat capture as **outgoing/mic-dominant** unless verified during a real call.
- Foreground service uses `dataSync` type (Android 14 `microphone` FGS type requires `RECORD_AUDIO` + foreground-only permission state that HyperOS does not grant reliably).
- `INTERNET` permission is required even though the socket is loopback; MIUI returns `EPERM` otherwise.
- ADB install requires the three Developer options above; otherwise `INSTALL_FAILED_USER_RESTRICTED`.
- During an actual call, HyperOS may suspend background capture; keep the app in foreground and screen on.

### Duplex verification procedure
1. Start capture (app foreground).
2. Place/answer a real call (speakerphone recommended).
3. On PC, count frames and inspect RMS of each 20 ms frame:
   - Only near-zero RMS → capture not working (permission/FGS).
   - RMS changes with your voice only → mic-only (expected fallback).
   - RMS changes with remote voice too → duplex achieved.
4. Document the outcome in `docs/android_capture_test.md` (create if missing).
