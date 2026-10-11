#!/usr/bin/env python3
"""FYAHGRABBER offline CQT sidecar: visual only, no automatic note claims.

Requires explicit local installation of librosa, Pillow, NumPy and SoundFile.
Input is a bounded original WAV audio file. No network, upload, model download,
sample copying, or external executable. The caller alone owns its outputs.
"""
from __future__ import annotations

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import sys
import tempfile
import time
import wave

MAX_FILE_SIZE = 64 * 1024 * 1024
MAX_DURATION = 20.0
SR = 22050
HOP = 512
PITCH_LO, PITCH_HI = 36, 84


def assert_source(path: Path, offset: float, duration: float) -> tuple[str, float]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".wav":
        raise ValueError("ONLY_LOCAL_PCM_WAV_SUPPORTED")
    if not math.isfinite(offset) or not math.isfinite(duration):
        raise ValueError("INVALID_TIME")
    if offset < 0 or not 0 < duration <= MAX_DURATION:
        raise ValueError("OFFSET_OR_DURATION_OUT_OF_BOUNDS")
    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("SOURCE_FILE_TOO_LARGE")
    with wave.open(str(path), "rb") as h:
        frames, samplerate = h.getnframes(), h.getframerate()
        if h.getcomptype() != "NONE" or h.getsampwidth() != 2 or h.getnchannels() not in (1, 2):
            raise ValueError("PCM16_MONO_OR_STEREO_REQUIRED")
        total = frames / samplerate
    if offset + duration > total + 1e-4:
        raise ValueError("REQUESTED_ITEM_EXCEEDS_SOURCE")
    return sha256(path.read_bytes()).hexdigest(), total


def cqt_image(source: Path, offset: float, duration: float):
    import numpy as np
    import librosa
    from PIL import Image
    # Source decoding never invokes the system shell; soundfile handles PCM WAV.
    signal, rate = librosa.load(str(source), sr=SR, mono=True, offset=offset, duration=duration)
    if len(signal) == 0:
        raise ValueError("EMPTY_AUDIO_SEGMENT")
    magnitude = np.abs(librosa.cqt(
        signal, sr=rate, hop_length=HOP,
        fmin=librosa.midi_to_hz(PITCH_LO),
        n_bins=PITCH_HI-PITCH_LO+1, bins_per_octave=12,
    ))
    if not np.all(np.isfinite(magnitude)):
        raise ValueError("NONFINITE_CQT_VALUES")
    db = librosa.amplitude_to_db(magnitude, ref=np.max, top_db=75)
    width, height = 1100, PITCH_HI-PITCH_LO+1
    image = Image.new("RGB", (width, height))
    pixel = image.load()
    for col in range(width):
        position = min(db.shape[1]-1, int(col * db.shape[1] / width))
        for row in range(height):
            strength = max(0, min(1, float((db[height-1-row, position] + 75) / 75)))
            # Original, license-neutral blue/teal/orange spectral palette.
            red = round(8 + (strength ** 3) * 234)
            green = round(15 + (strength ** 1.5) * 162)
            blue = round(28 + (strength ** 0.9) * 148)
            pixel[col, row] = (red, green, blue)
    return image.resize((1100, height * 9), Image.Resampling.NEAREST), db.shape


def analyze(source: Path, offset: float, duration: float, png: Path, tsv: Path):
    if png.exists() and png.is_symlink():
        raise ValueError("PNG_SYMLINK_FORBIDDEN")
    if tsv.exists() and tsv.is_symlink():
        raise ValueError("TSV_SYMLINK_FORBIDDEN")
    if not png.parent.is_dir() or not tsv.parent.is_dir():
        raise ValueError("OUTPUT_PARENT_REQUIRED")
    start = time.perf_counter()
    source_hash, total = assert_source(source, offset, duration)
    img, shape = cqt_image(source, offset, duration)
    # Ensure the source did not change while decoding.
    if source_hash != sha256(source.read_bytes()).hexdigest():
        raise ValueError("SOURCE_MODIFIED_DURING_PROCESSING")
    png_tmp, tsv_tmp = None, None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", dir=png.parent, delete=False) as t:
            png_tmp = Path(t.name)
        img.save(png_tmp, "PNG")
        png_hash = sha256(png_tmp.read_bytes()).hexdigest()
        rows = [
            "FYAH_CQT_V1",
            "SOURCE_SHA256\t" + source_hash,
            "CQT_PNG_SHA256\t" + png_hash,
            f"OFFSET_SECONDS\t{offset:.6f}",
            f"DURATION_SECONDS\t{duration:.6f}",
            f"CQT_SHAPE\t{shape[0]}\t{shape[1]}",
            "PITCH_LOW\t36",
            "PITCH_HIGH\t84",
            "LICENSE\tORIGINAL_IMPLEMENTATION",
            "NOTES\tUNSUPPORTED_WITHOUT_EXPLICIT_MODEL",
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", encoding="utf-8",
                                         dir=tsv.parent, delete=False) as t:
            tsv_tmp = Path(t.name)
            t.write("\n".join(rows) + "\n")
            t.flush()
            os.fsync(t.fileno())
        # Atomic rename from temporary files in same directory.
        os.replace(png_tmp, png)
        os.replace(tsv_tmp, tsv)
    finally:
        if png_tmp and png_tmp.exists(): png_tmp.unlink()
        if tsv_tmp and tsv_tmp.exists(): tsv_tmp.unlink()
    return {
        "schema": "FyahGrabberCQTReceipt/v1",
        "status": "EXECUTED_LOCAL",
        "source_sha256": source_hash,
        "png_sha256": png_hash,
        "frames": shape[1], "pitches": shape[0],
        "cost_usd": 0,
        "elapsed_ms": round((time.perf_counter() - start)*1000, 2),
        "publication_attempted": False,
        "no_model_inference_claimed": True,
    }


def main() -> int:
    p = ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--offset", type=float, required=True)
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--png", type=Path, required=True)
    p.add_argument("--tsv", type=Path, required=True)
    args = p.parse_args()
    try:
        report = analyze(args.source, args.offset, args.duration, args.png, args.tsv)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, ImportError, wave.Error, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
