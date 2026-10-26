# Android capture — real-call duplex verification

Fill in after running the procedure in README.md → "Duplex verification procedure".

## Device / OS
- Device:
- Android / HyperOS version:
- ADB serial: a6858t65jvmbsokn

## Test conditions
- Date:
- Call type (outgoing/incoming):
- Speakerphone: yes/no
- App foreground during call: yes/no

## Measurements (run verify_android_capture.py during the call)
- Frames received (3s window):
- Min RMS:
- Max RMS:
- RMS changed with my voice: yes/no
- RMS changed with remote voice: yes/no

## Outcome
- [ ] Not working (near-zero RMS)
- [ ] Mic-only (RMS changes with my voice only)  ← expected fallback
- [ ] Duplex (RMS changes with both voices)

## Notes
