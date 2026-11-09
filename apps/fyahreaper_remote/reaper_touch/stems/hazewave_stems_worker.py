#!/usr/bin/env python3
"""Hazewave offline stem worker (Demucs). Invoked by the ReaScript; no GUI.

Clean-room Hazewave tool — talks only via a job JSON + status JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

STEM_SETS = {
    # model -> ordered (filename_stem, display_pt, rrggbb)
    "htdemucs_6s": [
        ("drums", "Bateria", "2E86DE"),
        ("bass", "Baixo", "27AE60"),
        ("guitar", "Guitarra", "7D8A2E"),
        ("piano", "Teclado", "8E44AD"),
        ("other", "Outros", "7F8C8D"),
        ("vocals", "Vocais", "00BCD4"),
    ],
    "htdemucs": [
        ("drums", "Bateria", "2E86DE"),
        ("bass", "Baixo", "27AE60"),
        ("other", "Outros", "7F8C8D"),
        ("vocals", "Vocais", "00BCD4"),
    ],
    "htdemucs_ft": [
        ("drums", "Bateria", "2E86DE"),
        ("bass", "Baixo", "27AE60"),
        ("other", "Outros", "7F8C8D"),
        ("vocals", "Vocais", "00BCD4"),
    ],
}


def _write_status(path: Path, **fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = {"updated_at": time.time(), **fields}
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _run_demucs(source: Path, out_root: Path, model: str, two_stems: str | None, device: str) -> Path:
    import demucs.separate  # noqa: F401 — ensure importable
    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "-n",
        model,
        "-d",
        device,
        "--float32",
        "-o",
        str(out_root),
        str(source),
    ]
    if two_stems:
        i = cmd.index("-o")
        cmd[i:i] = ["--two-stems", two_stems]
    import subprocess

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"demucs exit {proc.returncode}: {detail[-2000:]}")
    # demucs writes out_root/<model>/<trackname>/*.wav
    track_dirs = [d for d in (out_root / model).glob("*") if d.is_dir()]
    if len(track_dirs) != 1:
        # fall back: any new dir
        track_dirs = [d for d in out_root.rglob("*") if d.is_dir() and any(d.glob("*.wav"))]
    if not track_dirs:
        raise RuntimeError("demucs produced no stem folder")
    return track_dirs[0]


def process_job(job: dict, status_path: Path) -> None:
    model = job.get("model") or "htdemucs_6s"
    if model not in STEM_SETS and not job.get("two_stems"):
        raise ValueError(f"unsupported model: {model}")
    two_stems = job.get("two_stems")  # e.g. "vocals" for 2-stem
    device = job.get("device") or "cpu"
    inputs = job.get("inputs") or []
    if not inputs:
        raise ValueError("no inputs")

    results = []
    n = len(inputs)
    for idx, item in enumerate(inputs):
        src = Path(item["path"])
        out_dir = Path(item["out_dir"])
        name = item.get("name") or src.stem
        pos = float(item.get("position", 0.0))
        track_idx = int(item.get("track_idx", 0))
        _write_status(
            status_path,
            state="running",
            progress=int(100 * idx / n),
            message=f"Separando {idx + 1}/{n}: {name}",
            current=name,
            results=results,
        )
        if not src.is_file():
            raise FileNotFoundError(f"missing input: {src}")
        out_dir.mkdir(parents=True, exist_ok=True)
        work = out_dir / "_demucs_work"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)
        stem_dir = _run_demucs(src, work, model, two_stems, device)

        if two_stems:
            # vocals + no_vocals (or other target)
            mapping = [
                (f"{two_stems}.wav", "Vocais" if two_stems == "vocals" else two_stems.title(), "00BCD4"),
                (f"no_{two_stems}.wav", "Instrumental", "7F8C8D"),
            ]
        else:
            mapping = [(f"{fn}.wav", label, color) for fn, label, color in STEM_SETS[model]]

        stems = []
        for fname, label, color in mapping:
            found = stem_dir / fname
            if not found.is_file():
                # case-insensitive search
                matches = list(stem_dir.glob("*.wav")) + list(stem_dir.glob("*.flac"))
                found = next((m for m in matches if m.stem.lower() == Path(fname).stem.lower()), None)
            if found is None or not found.is_file():
                raise RuntimeError(f"stem missing: {fname} in {stem_dir}")
            dest = out_dir / f"{name}__{label}.wav"
            shutil.copy2(found, dest)
            stems.append({"path": str(dest), "label": label, "color": color})
        shutil.rmtree(work, ignore_errors=True)
        results.append(
            {
                "name": name,
                "position": pos,
                "track_idx": track_idx,
                "source_path": str(src),
                "stems": stems,
            }
        )
        _write_status(
            status_path,
            state="running",
            progress=int(100 * (idx + 1) / n),
            message=f"Concluído {idx + 1}/{n}: {name}",
            current=name,
            results=results,
        )

    _write_status(
        status_path,
        state="done",
        progress=100,
        message="Stems prontos",
        results=results,
        model=model,
        two_stems=two_stems,
    )
    tsv = status_path.with_name("import.tsv")
    with tsv.open("w", encoding="utf-8") as fh:
        for r in results:
            for s in r["stems"]:
                fh.write(
                    f"{s['path']}\t{s['label']}\t{s['color']}\t{float(r.get('position') or 0):.9f}\t{int(r.get('track_idx') or 0)}\n"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description="Hazewave Demucs stem worker")
    ap.add_argument("--job", required=True, help="path to job.json")
    args = ap.parse_args()
    job_path = Path(args.job)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    status_path = Path(job.get("status_path") or (job_path.parent / "status.json"))
    try:
        _write_status(status_path, state="starting", progress=0, message="Iniciando Demucs…")
        process_job(job, status_path)
        return 0
    except Exception as exc:
        _write_status(
            status_path,
            state="error",
            progress=0,
            message=str(exc),
            error="".join(traceback.format_exception(exc)),
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
