"""Original Hazewave audio-to-note-map and MIDI baseline.

Bounded PCM16 WAV only, offline, CPU/std-lib only. This is NOT noteGRABBER2,
is NOT Spotify Basic Pitch, and cannot claim reliable polyphonic transcription.
"""
from __future__ import annotations

from array import array
from hashlib import sha256
from pathlib import Path
import argparse
import io
import json
import math
import os
import struct
import sys
import tempfile
import time
import wave

from hazewave.harness import HazewaveAuthorization, HazewaveTask, issue_authorization, route_task, validate_authorization
from hazewave.re_inspectors import inspect_file, run_inspection

CAPABILITY = "audio.sample_to_midi"
MAX_BYTES = 10 * 1024 * 1024
MAX_SECONDS = 20
WINDOW = 4096
HOP = 2048
MIN_HZ = 65.0
MAX_HZ = 1750.0


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _pcm_data(path: Path) -> tuple[list[float], int, str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_MUST_BE_REGULAR_FILE")
    length = path.stat().st_size
    if length == 0 or length > MAX_BYTES:
        raise ValueError("INPUT_SIZE_OUT_OF_BOUNDS")
    raw = path.read_bytes()
    if len(raw) != length:
        raise ValueError("INPUT_CHANGED_DURING_READ")
    try:
        with wave.open(io.BytesIO(raw), "rb") as wav:
            count = wav.getnframes()
            rate = wav.getframerate()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            comp = wav.getcomptype()
            if comp != "NONE" or width != 2 or channels not in (1, 2):
                raise ValueError("ONLY_PCM16_MONO_STEREO_SUPPORTED")
            if rate < 8000 or rate > 48000 or count == 0 or count > rate * MAX_SECONDS:
                raise ValueError("WAV_DURATION_OR_RATE_OUT_OF_BOUNDS")
            pcm = wav.readframes(count)
    except (wave.Error, EOFError, struct.error) as exc:
        raise ValueError("CORRUPT_OR_UNSUPPORTED_WAV") from exc
    if len(pcm) != count * channels * 2:
        raise ValueError("TRUNCATED_PCM_DATA")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    mono = []
    for i in range(0, len(samples), channels):
        mono.append(sum(samples[i:i + channels]) / (32768.0 * channels))
    return mono, rate, sha256(raw).hexdigest(), length


def _fft(samples: list[float]) -> list[complex]:
    """In-place radix-2 Cooley–Tukey; one original stdlib implementation."""
    n = len(samples)
    data = [complex(v) for v in samples]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            data[i], data[j] = data[j], data[i]
    step = 2
    while step <= n:
        theta = -2 * math.pi / step
        twiddle_root = complex(math.cos(theta), math.sin(theta))
        for start in range(0, n, step):
            w = complex(1.0)
            for k in range(start, start + step // 2):
                upper = data[k]
                lower = w * data[k + step // 2]
                data[k] = upper + lower
                data[k + step // 2] = upper - lower
                w *= twiddle_root
        step *= 2
    return data


def _frame_pitches(segment: list[float], rate: int) -> list[dict]:
    energy = sum(v * v for v in segment) / len(segment)
    if energy < 0.00004:
        return []
    window = [v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (WINDOW - 1)))
              for i, v in enumerate(segment)]
    spectrum = _fft(window)
    lo = max(2, math.ceil(MIN_HZ * WINDOW / rate))
    hi = min(WINDOW // 2 - 2, math.floor(MAX_HZ * WINDOW / rate))
    mags = [abs(z) for z in spectrum[:hi + 2]]
    maxmag = max(mags[lo:hi + 1], default=0.0)
    if maxmag < 0.001:
        return []
    found = []
    for k in range(lo, hi + 1):
        magnitude = mags[k]
        if magnitude < maxmag * 0.19 or magnitude <= mags[k - 1] or magnitude < mags[k + 1]:
            continue
        v1, v2, v3 = (math.log(max(mags[k + offset], 1e-10)) for offset in (-1, 0, 1))
        denom = v1 - 2 * v2 + v3
        fraction = 0 if abs(denom) < 1e-10 else max(-0.5, min(0.5, 0.5 * (v1 - v3) / denom))
        hz = (k + fraction) * rate / WINDOW
        if not MIN_HZ <= hz <= MAX_HZ:
            continue
        midi = round(69 + 12 * math.log2(hz / 440))
        if midi < 0 or midi > 127:
            continue
        found.append({"midi_note": midi, "frequency_hz": hz, "strength": magnitude / maxmag})
    found.sort(key=lambda x: x["strength"], reverse=True)
    selected = []
    for peak in found:
        if any(q["midi_note"] == peak["midi_note"] for q in selected):
            continue
        # Suppress integer harmonics of established stronger fundamentals.
        if any(peak["frequency_hz"] > q["frequency_hz"] and
               abs(peak["frequency_hz"] / q["frequency_hz"] -
                   round(peak["frequency_hz"] / q["frequency_hz"])) < 0.035
               for q in selected):
            continue
        selected.append(peak)
        if len(selected) >= 5:
            break
    return selected


def analyze_sample(file_path: str | Path) -> dict:
    """Heuristic acoustic note map. MIDI notes remain editable and unapproved."""
    path = Path(file_path)
    samples, rate, source_hash, length = _pcm_data(path)
    total = len(samples) / rate
    active: dict[int, list[int]] = {}
    strengths: dict[int, list[float]] = {}
    map_frames = []
    for frame_idx, start in enumerate(range(0, len(samples), HOP)):
        segment = samples[start:start + WINDOW]
        if len(segment) < WINDOW:
            segment = segment + [0.0] * (WINDOW - len(segment))
        pitch_candidates = _frame_pitches(segment, rate)
        names = sorted({p["midi_note"] for p in pitch_candidates})
        for p in pitch_candidates:
            pitch = p["midi_note"]
            active.setdefault(pitch, []).append(frame_idx)
            strengths.setdefault(pitch, []).append(p["strength"])
        map_frames.append({
            "time_seconds": round(start / rate, 4),
            "midi_notes": names,
        })
    events = []
    for midi, indexes in active.items():
        begin = prev = indexes[0]
        for index in indexes[1:] + [None]:
            if index is not None and index == prev + 1:
                prev = index
                continue
            start = begin * HOP / rate
            end = min(total, (prev * HOP + WINDOW) / rate)
            if end - start >= 0.075:
                events.append({
                    "midi_note": midi,
                    "note_name": "C C# D D# E F F# G G# A A# B".split()[midi % 12] +
                                 str(midi // 12 - 1),
                    "start_seconds": round(start, 4),
                    "end_seconds": round(end, 4),
                    "velocity": 90,
                    "confidence_relative": round(sum(strengths[midi]) / len(strengths[midi]), 3),
                })
            if index is not None:
                begin = index
            prev = index
    events.sort(key=lambda x: (x["start_seconds"], x["midi_note"]))
    return {
        "schema": "HazewaveSampleNoteMap/v1",
        "method": "bounded_windowed_fft_heuristic",
        "source": {
            "format": "WAV_PCM16", "sample_rate": rate,
            "duration_seconds": round(total, 4), "sha256": source_hash,
            "file_size": length,
        },
        "analysis": {"window_samples": WINDOW, "hop_samples": HOP,
                     "frequency_range_hz": [MIN_HZ, MAX_HZ],
                     "max_simultaneous_candidates": 5},
        "notes": events,
        "spectral_map": map_frames,
        "limitations": ["polyphonic_transcription_not_guaranteed",
                        "harmonic_overtones_or_transients_may_create_false_notes",
                        "manual_piano_roll_editing_required_for_professional_results",
                        "only_uncompressed_pcm16_wav_supported"],
    }


def _vlq(number: int) -> bytes:
    if number < 0 or number >= (1 << 28):
        raise ValueError("MIDI_DELTA_OUT_OF_BOUNDS")
    buffer = [number & 0x7f]
    number >>= 7
    while number:
        buffer.insert(0, 0x80 | (number & 0x7f))
        number >>= 7
    return bytes(buffer)


def _encode_midi(notes: list[dict]) -> bytes:
    # Format 0; tempo 120 BPM; PPQ 480 => 960 ticks / second.
    events = []
    for note in notes:
        midi = note["midi_note"]
        begin = round(note["start_seconds"] * 960)
        end = round(note["end_seconds"] * 960)
        if end <= begin:
            continue
        events.append((begin, 1, bytes((0x90, midi, note["velocity"]))))
        events.append((end, 0, bytes((0x80, midi, 0))))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    track = bytearray(b"\x00\xff\x51\x03\x07\xa1\x20")
    previous = 0
    for tick, _, payload in events:
        track.extend(_vlq(tick - previous))
        track.extend(payload)
        previous = tick
    track.extend(b"\x00\xff\x2f\x00")
    return (
        struct.pack(">4sIHHH", b"MThd", 6, 0, 1, 480)
        + struct.pack(">4sI", b"MTrk", len(track)) + track
    )


def transcribe_to_midi(
    file_path: str | Path, midi_output: str | Path, *,
    authorization: HazewaveAuthorization, task_id: str,
) -> dict:
    start = time.perf_counter()
    validate_authorization(
        authorization, expected_task_id=task_id, expected_capability=CAPABILITY,
    )
    if authorization.domain != "HAZE":
        raise PermissionError("HAZE_ONLY_CAPABILITY")
    again = issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Authorized local audio note mapping",
        requested_domain="HAZE", required_capability=CAPABILITY,
    )))
    if again.authorization_id != authorization.authorization_id:
        raise PermissionError("AUTHORIZATION_ID_MISMATCH")
    src, dest = Path(file_path), Path(midi_output)
    if dest.suffix.lower() != ".mid" or dest.exists() or dest.is_symlink():
        raise ValueError("MIDI_OUTPUT_MUST_BE_NEW_MID_FILE")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ValueError("MIDI_OUTPUT_DIRECTORY_INVALID")
    inspector_auth = issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Verify source WAV before any processing",
        required_capability="codec_stream_analyzer", requested_domain="HAZE",
    )))
    inspected = run_inspection(
        "codec_stream_analyzer", src,
        task_id=task_id, authorization=inspector_auth,
    )
    if inspected["result"].get("codec") != "PCM":
        raise ValueError("WAV_SOURCE_INSPECTION_FAILED")
    mapping = analyze_sample(src)
    if mapping["source"]["sha256"] != inspected["receipt"]["source_sha256"]:
        raise ValueError("SOURCE_CHANGED_AFTER_INSPECTION")
    midi_bytes = _encode_midi(mapping["notes"])
    if sha256(src.read_bytes()).hexdigest() != mapping["source"]["sha256"]:
        raise ValueError("SOURCE_CHANGED_BEFORE_EXPORT")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=dest.parent, prefix=".hazewave-midi-", delete=False
        ) as temp:
            tmp_path = Path(temp.name)
            temp.write(midi_bytes)
            temp.flush()
            os.fsync(temp.fileno())
        if dest.exists() or dest.is_symlink():
            raise ValueError("MIDI_OUTPUT_CHANGED_CONCURRENTLY")
        os.replace(tmp_path, dest)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
    receipt = {
        "schema": "HazewaveSampleToMidiExecutionReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "authorization_id": authorization.authorization_id,
        "task_id": task_id,
        "capability": CAPABILITY,
        "status": "EXECUTED_HAZE_LOCAL",
        "source_sha256": mapping["source"]["sha256"],
        "inspection_result_sha256": inspected["receipt"]["result_sha256"],
        "midi_sha256": sha256(midi_bytes).hexdigest(),
        "map_sha256": sha256(_canonical(mapping)).hexdigest(),
        "origin_kind": "ORIGINAL_STDLIB_IMPLEMENTATION",
        "cost_usd": 0,
        "publication_attempted": False,
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
    }
    return {"result": mapping, "receipt": receipt}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hazewave native WAV note map and editable MIDI (NOT noteGRABBER2)"
    )
    parser.add_argument("file_path")
    parser.add_argument("--out", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    try:
        authorization = issue_authorization(route_task(HazewaveTask(
            task_id=args.task_id, goal="Map approved local sample to MIDI",
            required_capability=CAPABILITY, requested_domain="HAZE",
        )))
        output = transcribe_to_midi(
            args.file_path, args.out, authorization=authorization,
            task_id=args.task_id,
        )
        data = json.dumps(output, sort_keys=True, indent=2) + "\n"
        if args.json_out:
            target = Path(args.json_out)
            if target.exists():
                raise ValueError("JSON_OUTPUT_EXISTS")
            target.write_text(data, encoding="utf-8")
        print(data)
        return 0
    except (ValueError, OSError, PermissionError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
