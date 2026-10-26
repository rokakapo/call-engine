"""WASAPI dual-direction audio capture test for Windows HFP endpoints."""
from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundcard as sc


@dataclass
class StreamResult:
    label: str
    device_name: str
    device_id: str
    ok: bool
    error: str | None = None
    duration_s: float = 0.0
    frames: int = 0
    samplerate: int = 0
    rms: float = 0.0
    peak: float = 0.0
    active_frame_ratio: float = 0.0
    clipping: int = 0


def _metrics(data, samplerate, frame_ms=20):
    if data.size == 0:
        return {"rms": 0.0, "peak": 0.0, "active_frame_ratio": 0.0, "clipping": 0}
    mono = data.reshape(-1).astype(np.float64)
    rms = float(np.sqrt(np.mean(mono * mono)))
    peak = float(np.max(np.abs(mono)))
    frame = max(1, int(samplerate * frame_ms / 1000))
    nframes = len(mono) // frame
    active = 0
    thr = 0.005
    for i in range(nframes):
        chunk = mono[i * frame:(i + 1) * frame]
        frms = float(np.sqrt(np.mean(chunk * chunk)))
        if frms >= thr:
            active += 1
    ratio = (active / nframes) if nframes else 0.0
    clip = int(np.sum(np.abs(mono) >= 0.99))
    return {"rms": rms, "peak": peak, "active_frame_ratio": ratio, "clipping": clip}


def record_stream(mic_obj, label, duration, samplerate):
    res = StreamResult(label=label, device_name=mic_obj.name, device_id=str(mic_obj.id),
                       ok=False, samplerate=samplerate)
    chunks = []
    t0 = time.time()
    err = None
    chunk_frames = max(1, samplerate // 10)
    try:
        with mic_obj.recorder(samplerate=samplerate, channels=1) as rec:
            while time.time() - t0 < duration:
                chunk = rec.record(numframes=chunk_frames)
                if chunk is not None and len(chunk):
                    chunks.append(np.asarray(chunk))
        res.ok = True
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    res.error = err
    res.duration_s = round(time.time() - t0, 3)
    if chunks:
        data = np.concatenate(chunks, axis=0)
    else:
        data = np.zeros((0, 1), dtype=np.float32)
    res.frames = int(data.shape[0])
    m = _metrics(data, samplerate)
    res.rms = m["rms"]
    res.peak = m["peak"]
    res.active_frame_ratio = m["active_frame_ratio"]
    res.clipping = m["clipping"]
    return res

def run_test(duration, filt, samplerate, out_path):
    speakers = [s for s in sc.all_speakers() if filt.lower() in s.name.lower()]
    mics = [m for m in sc.all_microphones() if filt.lower() in m.name.lower()]
    loopback_mics = []
    for spk in speakers:
        try:
            loopback_mics.append((spk, sc.get_microphone(spk.id, include_loopback=True)))
        except Exception as exc:
            loopback_mics.append((spk, exc))
    print("=== WASAPI HFP device discovery ===")
    print("filter:", filt)
    print("render endpoints (speakers):")
    for s in speakers:
        print(f"  - {s.name}  [{s.id}]")
    print("capture endpoints (mics):")
    for m in mics:
        print(f"  - {m.name}  [{m.id}]")
    if not speakers and not mics:
        print("No HFP endpoints matched. Pair/connect the phone first, or change --filter.")
    results = []
    threads = []
    barrier = threading.Barrier(len(loopback_mics) + len(mics) + 1) if (loopback_mics or mics) else None

    def worker(mic_obj, label):
        if barrier:
            barrier.wait()
        r = record_stream(mic_obj, label, duration, samplerate)
        results.append(r)

    for spk, lb in loopback_mics:
        if isinstance(lb, Exception):
            results.append(StreamResult(label="incoming(loopback)", device_name=spk.name,
                                       device_id=str(spk.id), ok=False, error=repr(lb),
                                       samplerate=samplerate))
            continue
        t = threading.Thread(target=worker, args=(lb, f"incoming(loopback):{spk.name}"), daemon=True)
        threads.append(t)
    for m in mics:
        t = threading.Thread(target=worker, args=(m, f"outgoing(mic):{m.name}"), daemon=True)
        threads.append(t)

    t0 = time.time()
    for t in threads:
        t.start()
    if barrier:
        barrier.wait()
    for t in threads:
        t.join(timeout=duration + 10)
    wall = round(time.time() - t0, 3)

    incoming = [r for r in results if r.label.startswith("incoming")]
    outgoing = [r for r in results if r.label.startswith("outgoing")]
    all_ok = all(r.ok for r in results) and bool(results)
    both_active = (any(r.ok and r.active_frame_ratio > 0 for r in incoming) and
                   any(r.ok and r.active_frame_ratio > 0 for r in outgoing))
    if not results:
        verdict = "NO_DEVICES: no HFP endpoints found"
    elif not all_ok:
        verdict = "FAIL: at least one stream could not be opened (driver/permission/exclusive mode)"
    elif both_active:
        verdict = "PASS: both directions captured live audio simultaneously"
    else:
        verdict = ("PARTIAL: streams opened and captured data, but no voice activity detected on at "
                   "least one side. Keep a real call active and have both parties speak, then rerun.")

    report = {"filter": filt, "duration_requested_s": duration, "wall_time_s": wall,
              "samplerate": samplerate, "render_endpoints": [s.name for s in speakers],
              "capture_endpoints": [m.name for m in mics],
              "streams": [asdict(r) for r in results], "verdict": verdict}

    print("\n=== RESULTS ===")
    for r in results:
        print(f"[{'OK ' if r.ok else 'ERR'}] {r.label}")
        print(f"      frames={r.frames} rms={r.rms:.5f} peak={r.peak:.5f} active={r.active_frame_ratio:.2%} dur={r.duration_s}s")
        if r.error:
            print(f"      error={r.error}")
    print("\nVERDICT:", verdict)

    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("report written:", out_path)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=8.0)
    ap.add_argument("--filter", default="Hands-Free")
    ap.add_argument("--samplerate", type=int, default=16000)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out = Path(args.out) if args.out else None
    run_test(args.duration, args.filter, args.samplerate, out)


if __name__ == "__main__":
    main()
