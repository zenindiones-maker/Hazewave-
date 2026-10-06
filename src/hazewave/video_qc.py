from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping


class VideoQCError(RuntimeError):
    pass


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class VideoQCReport:
    output_path: str
    output_sha256: str
    container_format: str
    duration_seconds: float
    video_codec: str
    width: int
    height: int
    pixel_format: str
    frame_rate_numerator: int
    frame_rate_denominator: int
    color_primaries: str
    color_transfer: str
    color_matrix: str
    color_range: str
    bit_depth: int
    audio_stream_count: int
    av_duration_delta_seconds: float
    encode_integrity: str
    technical_flags: tuple[str, ...]
    reference_quality: Mapping[str, object] | None = None
    artistic_verdict: str = "NOT_ASSIGNED"
    schema: str = "VideoQCReport/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["technical_flags"] = list(self.technical_flags)
        if self.reference_quality is not None:
            value["reference_quality"] = dict(self.reference_quality)
        return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise VideoQCError(f"VIDEO_QC_TOOL_MISSING:{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoQCError(f"VIDEO_QC_COMMAND_TIMEOUT:{args[0]}") from exc


def _run_checked(
    runner: Runner,
    args: list[str],
    *,
    code: str,
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(args)
    except VideoQCError:
        raise
    except FileNotFoundError as exc:
        raise VideoQCError(f"VIDEO_QC_TOOL_MISSING:{args[0]}") from exc
    except Exception as exc:
        raise VideoQCError(f"{code}:RUNNER_ERROR") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500]
        raise VideoQCError(f"{code}:{detail or 'NONZERO_EXIT'}")
    return result


def _float_value(value: object, *, code: str, default: float | None = None) -> float:
    if value in (None, "", "N/A"):
        if default is None:
            raise VideoQCError(code)
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise VideoQCError(code) from exc
    if result < 0:
        raise VideoQCError(code)
    return result


def _int_value(value: object, *, code: str, default: int | None = None) -> int:
    if value in (None, "", "N/A"):
        if default is None:
            raise VideoQCError(code)
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise VideoQCError(code) from exc
    if result < 0:
        raise VideoQCError(code)
    return result


def _parse_rate(value: object) -> tuple[int, int]:
    raw = str(value or "").strip()
    if not raw or raw in {"0/0", "N/A"}:
        raise VideoQCError("VIDEO_QC_FRAME_RATE_INVALID")
    try:
        rate = Fraction(raw)
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoQCError("VIDEO_QC_FRAME_RATE_INVALID") from exc
    if rate <= 0:
        raise VideoQCError("VIDEO_QC_FRAME_RATE_INVALID")
    return rate.numerator, rate.denominator


_UNKNOWN_COLOR = {"", "unknown", "unspecified", "reserved", "n/a", "none"}


def _is_ambiguous_color(*values: object) -> bool:
    return any(str(value or "").strip().casefold() in _UNKNOWN_COLOR for value in values)


def parse_reference_quality_metrics(text: str) -> dict[str, object]:
    if not isinstance(text, str):
        raise VideoQCError("VIDEO_QC_REFERENCE_METRICS_MISSING")

    result: dict[str, object] = {
        "schema": "ReferenceVideoQualityReport/v1",
        "vmaf": None,
        "ssim": None,
        "psnr_db": None,
        "interpretation": "TECHNICAL_FIDELITY_ONLY",
        "artistic_verdict": "NOT_ASSIGNED",
    }

    vmaf = re.search(
        r"VMAF\s+score:\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))",
        text,
        flags=re.IGNORECASE,
    )
    ssim = re.search(
        r"SSIM\b.*?\bAll:\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))",
        text,
        flags=re.IGNORECASE,
    )
    psnr = re.search(
        r"PSNR\b.*?\baverage:\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))",
        text,
        flags=re.IGNORECASE,
    )

    if vmaf is not None:
        result["vmaf"] = float(vmaf.group(1))
    if ssim is not None:
        result["ssim"] = float(ssim.group(1))
    if psnr is not None:
        result["psnr_db"] = float(psnr.group(1))

    if result["vmaf"] is None and result["ssim"] is None and result["psnr_db"] is None:
        raise VideoQCError("VIDEO_QC_REFERENCE_METRICS_MISSING")
    return result


def _probe(
    path: Path,
    *,
    runner: Runner,
) -> dict[str, object]:
    result = _run_checked(
        runner,
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        code="VIDEO_QC_FFPROBE_FAILED",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoQCError("VIDEO_QC_FFPROBE_MALFORMED") from exc
    if not isinstance(payload, dict):
        raise VideoQCError("VIDEO_QC_FFPROBE_MALFORMED")
    streams = payload.get("streams")
    format_payload = payload.get("format")
    if not isinstance(streams, list) or not isinstance(format_payload, dict):
        raise VideoQCError("VIDEO_QC_FFPROBE_MALFORMED")
    return payload


def _reference_metrics(
    output: Path,
    reference: Path,
    *,
    runner: Runner,
) -> dict[str, object]:
    if not reference.is_file():
        raise VideoQCError("VIDEO_QC_REFERENCE_NOT_FOUND")
    result = _run_checked(
        runner,
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "info",
            "-i",
            str(output),
            "-i",
            str(reference),
            "-lavfi",
            "[0:v][1:v]libvmaf;[0:v][1:v]ssim;[0:v][1:v]psnr",
            "-f",
            "null",
            "-",
        ],
        code="VIDEO_QC_REFERENCE_METRICS_FAILED",
    )
    return parse_reference_quality_metrics((result.stderr or "") + "\n" + (result.stdout or ""))


def analyze_video_qc(
    output: Path | str,
    *,
    runner: Runner | None = None,
    av_duration_tolerance_seconds: float = 0.1,
    reference: Path | str | None = None,
) -> VideoQCReport:
    path = Path(output).expanduser().resolve()
    if not path.is_file():
        raise VideoQCError("VIDEO_QC_OUTPUT_NOT_FOUND")
    if path.stat().st_size <= 0:
        raise VideoQCError("VIDEO_QC_OUTPUT_EMPTY")
    if av_duration_tolerance_seconds < 0:
        raise VideoQCError("VIDEO_QC_AV_TOLERANCE_INVALID")

    execute = runner or _default_runner
    payload = _probe(path, runner=execute)
    streams = payload["streams"]
    format_payload = payload["format"]
    assert isinstance(streams, list)
    assert isinstance(format_payload, dict)

    videos = [
        item
        for item in streams
        if isinstance(item, dict) and item.get("codec_type") == "video"
    ]
    if not videos:
        raise VideoQCError("VIDEO_QC_VIDEO_STREAM_REQUIRED")
    video = videos[0]

    width = _int_value(video.get("width"), code="VIDEO_QC_VIDEO_STREAM_MALFORMED")
    height = _int_value(video.get("height"), code="VIDEO_QC_VIDEO_STREAM_MALFORMED")
    if width <= 0 or height <= 0:
        raise VideoQCError("VIDEO_QC_VIDEO_STREAM_MALFORMED")

    video_codec = str(video.get("codec_name") or "").strip()
    pixel_format = str(video.get("pix_fmt") or "").strip()
    if not video_codec or not pixel_format:
        raise VideoQCError("VIDEO_QC_VIDEO_STREAM_MALFORMED")

    fr_num, fr_den = _parse_rate(
        video.get("avg_frame_rate") or video.get("r_frame_rate")
    )

    format_duration = _float_value(
        format_payload.get("duration"),
        code="VIDEO_QC_DURATION_INVALID",
    )
    video_duration = _float_value(
        video.get("duration"),
        code="VIDEO_QC_DURATION_INVALID",
        default=format_duration,
    )

    audios = [
        item
        for item in streams
        if isinstance(item, dict) and item.get("codec_type") == "audio"
    ]
    audio_durations = [
        _float_value(
            item.get("duration"),
            code="VIDEO_QC_AUDIO_STREAM_MALFORMED",
            default=format_duration,
        )
        for item in audios
    ]
    if audio_durations:
        av_delta = max(abs(video_duration - duration) for duration in audio_durations)
    else:
        av_delta = 0.0

    color_primaries = str(video.get("color_primaries") or "unknown")
    color_transfer = str(video.get("color_transfer") or "unknown")
    color_matrix = str(video.get("color_space") or "unknown")
    color_range = str(video.get("color_range") or "unknown")
    bit_depth = _int_value(
        video.get("bits_per_raw_sample"),
        code="VIDEO_QC_BIT_DEPTH_INVALID",
        default=_int_value(
            video.get("bits_per_sample"),
            code="VIDEO_QC_BIT_DEPTH_INVALID",
            default=8,
        ),
    )
    if bit_depth <= 0:
        raise VideoQCError("VIDEO_QC_BIT_DEPTH_INVALID")

    flags: list[str] = []
    if av_delta > av_duration_tolerance_seconds:
        flags.append("AV_DURATION_MISMATCH")
    if _is_ambiguous_color(
        color_primaries,
        color_transfer,
        color_matrix,
        color_range,
    ):
        flags.append("COLOR_METADATA_AMBIGUOUS")

    reference_quality: dict[str, object] | None = None
    if reference is not None:
        reference_quality = _reference_metrics(
            path,
            Path(reference).expanduser().resolve(),
            runner=execute,
        )

    return VideoQCReport(
        output_path=str(path),
        output_sha256=_sha256_file(path),
        container_format=str(format_payload.get("format_name") or ""),
        duration_seconds=format_duration,
        video_codec=video_codec,
        width=width,
        height=height,
        pixel_format=pixel_format,
        frame_rate_numerator=fr_num,
        frame_rate_denominator=fr_den,
        color_primaries=color_primaries,
        color_transfer=color_transfer,
        color_matrix=color_matrix,
        color_range=color_range,
        bit_depth=bit_depth,
        audio_stream_count=len(audios),
        av_duration_delta_seconds=av_delta,
        encode_integrity="PASS",
        technical_flags=tuple(flags),
        reference_quality=reference_quality,
    )
