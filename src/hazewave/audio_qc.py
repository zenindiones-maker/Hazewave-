from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Final, Sequence


LOUDNESS_STANDARD: Final = "EBU_R128/ITU_R_BS.1770"
LOUDNESS_ENGINE: Final = "FFmpeg ebur128"
SAMPLE_STATS_ENGINE: Final = "FFmpeg astats"


class AudioQCError(RuntimeError):
    pass


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class AudioQCReport:
    source_path: str
    source_sha256: str
    codec_name: str
    sample_rate: int
    channels: int
    channel_layout: str
    duration_seconds: float
    integrated_lufs: float
    integrated_threshold_lufs: float
    loudness_range_lu: float
    true_peak_dbfs: float
    sample_peak_dbfs: float
    rms_dbfs: float
    dc_offset: float
    crest_factor_ratio: float
    clipping_detected: bool
    technical_flags: tuple[str, ...]
    momentary_max_lufs: float | None = None
    short_term_max_lufs: float | None = None
    loudness_timeseries_frames: int = 0
    delivery_profile: str | None = None
    artistic_verdict: str = "NOT_ASSIGNED"
    loudness_standard: str = LOUDNESS_STANDARD
    loudness_engine: str = LOUDNESS_ENGINE
    sample_stats_engine: str = SAMPLE_STATS_ENGINE
    schema: str = "AudioQCReport/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["technical_flags"] = list(self.technical_flags)
        return value


_NUMBER = r"([+-]?(?:\d+(?:\.\d+)?|\.\d+))"


def _require_match(pattern: str, text: str, *, code: str) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if match is None:
        raise AudioQCError(code)
    return match


def parse_ebur128_summary(text: str) -> dict[str, float]:
    if not isinstance(text, str) or not text.strip():
        raise AudioQCError("AUDIO_QC_EBUR128_MALFORMED")

    integrated = _require_match(
        rf"Integrated\s+loudness:\s*.*?I:\s*{_NUMBER}\s*LUFS\s*.*?Threshold:\s*{_NUMBER}\s*LUFS",
        text,
        code="AUDIO_QC_EBUR128_MALFORMED",
    )
    lra = _require_match(
        rf"Loudness\s+range:\s*.*?LRA:\s*{_NUMBER}\s*LU\b",
        text,
        code="AUDIO_QC_EBUR128_MALFORMED",
    )
    true_peak = _require_match(
        rf"True\s+peak:\s*.*?Peak:\s*{_NUMBER}\s*dBFS",
        text,
        code="AUDIO_QC_EBUR128_MALFORMED",
    )
    return {
        "integrated_lufs": float(integrated.group(1)),
        "integrated_threshold_lufs": float(integrated.group(2)),
        "loudness_range_lu": float(lra.group(1)),
        "true_peak_dbfs": float(true_peak.group(1)),
    }


def parse_ebur128_timeseries(text: str) -> dict[str, float | int]:
    if not isinstance(text, str) or not text.strip():
        raise AudioQCError("AUDIO_QC_EBUR128_TIMESERIES_MALFORMED")

    momentary: list[float] = []
    short_term: list[float] = []
    pattern = re.compile(
        rf"\bM:\s*{_NUMBER}\s+S:\s*{_NUMBER}\s+I:",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        m_value = float(match.group(1))
        s_value = float(match.group(2))
        momentary.append(m_value)
        short_term.append(s_value)

    if not momentary or len(momentary) != len(short_term):
        raise AudioQCError("AUDIO_QC_EBUR128_TIMESERIES_MALFORMED")

    return {
        "momentary_max_lufs": max(momentary),
        "short_term_max_lufs": max(short_term),
        "frame_count": len(momentary),
    }


def _last_metric(text: str, label_pattern: str, *, code: str) -> float:
    matches = re.findall(
        rf"{label_pattern}:\s*{_NUMBER}",
        text,
        flags=re.IGNORECASE,
    )
    if not matches:
        raise AudioQCError(code)
    value = matches[-1]
    if isinstance(value, tuple):
        value = value[-1]
    return float(value)


def parse_astats_summary(text: str) -> dict[str, float]:
    if not isinstance(text, str) or "Overall" not in text:
        raise AudioQCError("AUDIO_QC_ASTATS_MALFORMED")

    overall = text[text.rfind("Overall") :]
    return {
        "dc_offset": _last_metric(
            overall,
            r"DC\s+offset",
            code="AUDIO_QC_ASTATS_MALFORMED",
        ),
        "sample_peak_dbfs": _last_metric(
            overall,
            r"Peak\s+level\s+dB",
            code="AUDIO_QC_ASTATS_MALFORMED",
        ),
        "rms_dbfs": _last_metric(
            overall,
            r"RMS\s+level\s+dB",
            code="AUDIO_QC_ASTATS_MALFORMED",
        ),
        "crest_factor_ratio": _last_metric(
            overall,
            r"Crest\s+factor",
            code="AUDIO_QC_ASTATS_MALFORMED",
        ),
    }


def _default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise AudioQCError(f"AUDIO_QC_TOOL_MISSING:{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioQCError(f"AUDIO_QC_COMMAND_TIMEOUT:{args[0]}") from exc


def _run_checked(
    runner: Runner,
    args: list[str],
    *,
    code: str,
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(args)
    except AudioQCError:
        raise
    except FileNotFoundError as exc:
        raise AudioQCError(f"AUDIO_QC_TOOL_MISSING:{args[0]}") from exc
    except Exception as exc:
        raise AudioQCError(f"{code}:RUNNER_ERROR") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500]
        raise AudioQCError(f"{code}:{detail or 'NONZERO_EXIT'}")
    return result


def _probe_audio(
    source: Path,
    *,
    runner: Runner,
) -> dict[str, object]:
    result = _run_checked(
        runner,
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,channel_layout:format=duration",
            "-of",
            "json",
            str(source),
        ],
        code="AUDIO_QC_FFPROBE_FAILED",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AudioQCError("AUDIO_QC_FFPROBE_MALFORMED") from exc

    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list) or not streams:
        raise AudioQCError("AUDIO_QC_NO_AUDIO_STREAM")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise AudioQCError("AUDIO_QC_FFPROBE_MALFORMED")

    format_info = payload.get("format")
    if not isinstance(format_info, dict):
        raise AudioQCError("AUDIO_QC_FFPROBE_MALFORMED")
    try:
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        duration_seconds = float(format_info["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AudioQCError("AUDIO_QC_FFPROBE_MALFORMED") from exc

    if sample_rate <= 0 or channels <= 0 or duration_seconds < 0:
        raise AudioQCError("AUDIO_QC_FFPROBE_MALFORMED")

    return {
        "codec_name": str(stream.get("codec_name") or ""),
        "sample_rate": sample_rate,
        "channels": channels,
        "channel_layout": str(stream.get("channel_layout") or ""),
        "duration_seconds": duration_seconds,
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_audio_qc(
    source: Path | str,
    *,
    runner: Runner | None = None,
    delivery_profile: str | None = None,
) -> AudioQCReport:
    path = Path(source)
    if not path.is_file():
        raise AudioQCError("AUDIO_QC_SOURCE_NOT_FOUND")
    if delivery_profile is not None and not str(delivery_profile).strip():
        raise AudioQCError("AUDIO_QC_DELIVERY_PROFILE_INVALID")

    execute = runner or _default_runner
    probe = _probe_audio(path, runner=execute)

    ebur = _run_checked(
        execute,
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "info",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-filter_complex",
            "ebur128=peak=true:framelog=info",
            "-f",
            "null",
            "-",
        ],
        code="AUDIO_QC_EBUR128_FAILED",
    )
    astats = _run_checked(
        execute,
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "info",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "astats=metadata=0:reset=0",
            "-f",
            "null",
            "-",
        ],
        code="AUDIO_QC_ASTATS_FAILED",
    )

    loudness = parse_ebur128_summary(ebur.stderr)
    loudness_timeseries = parse_ebur128_timeseries(ebur.stderr)
    samples = parse_astats_summary(astats.stderr)

    clipping = (
        loudness["true_peak_dbfs"] >= 0.0
        or samples["sample_peak_dbfs"] >= 0.0
    )
    flags: list[str] = []
    if clipping:
        flags.append("CLIPPING_OR_OVERS_DETECTED")
    if abs(samples["dc_offset"]) >= 0.01:
        flags.append("MATERIAL_DC_OFFSET")

    return AudioQCReport(
        source_path=str(path.resolve()),
        source_sha256=_sha256_file(path),
        codec_name=str(probe["codec_name"]),
        sample_rate=int(probe["sample_rate"]),
        channels=int(probe["channels"]),
        channel_layout=str(probe["channel_layout"]),
        duration_seconds=float(probe["duration_seconds"]),
        integrated_lufs=loudness["integrated_lufs"],
        integrated_threshold_lufs=loudness["integrated_threshold_lufs"],
        loudness_range_lu=loudness["loudness_range_lu"],
        true_peak_dbfs=loudness["true_peak_dbfs"],
        sample_peak_dbfs=samples["sample_peak_dbfs"],
        rms_dbfs=samples["rms_dbfs"],
        dc_offset=samples["dc_offset"],
        crest_factor_ratio=samples["crest_factor_ratio"],
        clipping_detected=clipping,
        technical_flags=tuple(flags),
        momentary_max_lufs=float(loudness_timeseries["momentary_max_lufs"]),
        short_term_max_lufs=float(loudness_timeseries["short_term_max_lufs"]),
        loudness_timeseries_frames=int(loudness_timeseries["frame_count"]),
        delivery_profile=delivery_profile,
    )


def _print_report(report: AudioQCReport) -> None:
    print(json.dumps(report.to_dict(), sort_keys=True, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.audio_qc")
    parser.add_argument("source", type=Path)
    parser.add_argument("--delivery-profile")
    args = parser.parse_args(argv)

    try:
        report = analyze_audio_qc(
            args.source,
            delivery_profile=args.delivery_profile,
        )
    except AudioQCError as exc:
        print(f"AUDIO_QC=FAIL:{exc}")
        return 20

    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
