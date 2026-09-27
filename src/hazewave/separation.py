from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "htdemucs"


class SeparationError(RuntimeError):
    """Raised when neural stem separation cannot complete safely."""


@dataclass(frozen=True)
class SeparationResult:
    source: Path
    instrumental: Path
    vocals: Path | None
    model: str


def _check_runtime() -> None:
    if importlib.util.find_spec("demucs") is None:
        raise SeparationError(
            'Demucs is not installed. Run: pip install -e ".[separation]"'
        )

    if shutil.which("ffmpeg") is None:
        raise SeparationError(
            "FFmpeg was not found in PATH. Install FFmpeg before separating audio."
        )


def _run_demucs(source: Path, work_dir: Path, model: str) -> None:
    command = [
        sys.executable,
        "-m",
        "demucs.separate",
        "-n",
        model,
        "--two-stems",
        "vocals",
        "-o",
        str(work_dir),
        str(source),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        details = process.stderr.strip() or process.stdout.strip()
        raise SeparationError(
            f"Demucs failed with exit code {process.returncode}: {details}"
        )


def _find_single_stem(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if len(matches) != 1:
        raise SeparationError(
            f"Expected exactly one {filename!r} stem, found {len(matches)}."
        )
    return matches[0]


def _export_stem(source: Path, destination: Path, output_format: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "wav":
        shutil.copy2(source, destination)
        return

    if output_format != "mp3":
        raise SeparationError(f"Unsupported output format: {output_format}")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "320k",
        str(destination),
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise SeparationError(
            f"FFmpeg export failed: {process.stderr.strip() or process.stdout.strip()}"
        )


def separate_track(
    source: str | Path,
    *,
    output_dir: str | Path = "output",
    model: str = DEFAULT_MODEL,
    instrumental_only: bool = False,
    output_format: str = "wav",
) -> SeparationResult:
    """Separate one audio file into vocals and instrumental stems using Demucs."""

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise SeparationError(f"Input audio file does not exist: {source_path}")

    if output_format not in {"wav", "mp3"}:
        raise SeparationError("output_format must be 'wav' or 'mp3'")

    _check_runtime()

    output_root = Path(output_dir).expanduser().resolve()
    track_dir = output_root / source_path.stem
    extension = f".{output_format}"

    with tempfile.TemporaryDirectory(prefix="hazewave-demucs-") as temp:
        work_dir = Path(temp)
        _run_demucs(source_path, work_dir, model)

        vocal_stem = _find_single_stem(work_dir, "vocals.wav")
        instrumental_stem = _find_single_stem(work_dir, "no_vocals.wav")

        instrumental_output = track_dir / f"instrumental{extension}"
        _export_stem(instrumental_stem, instrumental_output, output_format)

        vocal_output: Path | None = None
        if not instrumental_only:
            vocal_output = track_dir / f"vocals{extension}"
            _export_stem(vocal_stem, vocal_output, output_format)

    return SeparationResult(
        source=source_path,
        instrumental=instrumental_output,
        vocals=vocal_output,
        model=model,
    )
