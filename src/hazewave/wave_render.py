from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping

from hazewave.video_qc import VideoQCError, analyze_video_qc
from hazewave.wave_editorial import MediaManifest, WaveEditorialTimeline


class WaveRenderError(RuntimeError):
    pass


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]

_RENDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class WaveRenderReceipt:
    timeline_id: str
    timeline_revision: int
    output_path: str
    output_sha256: str
    source_sha256: str
    ffmpeg_command_sha256: str
    video_qc: Mapping[str, object]
    render_backend: str = "FFmpeg"
    authority: str = "HAZEWAVE_HARNESS"
    domain: str = "WAVE"
    artistic_verdict: str = "NOT_ASSIGNED"
    schema: str = "WaveRenderReceipt/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["video_qc"] = dict(self.video_qc)
        return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_digest(args: list[str]) -> str:
    return sha256("\0".join(args).encode("utf-8")).hexdigest()


def _default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=900,
        )
    except FileNotFoundError as exc:
        raise WaveRenderError(f"WAVE_RENDER_TOOL_MISSING:{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WaveRenderError(f"WAVE_RENDER_TIMEOUT:{args[0]}") from exc


def _run_checked(
    runner: Runner,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(args)
    except WaveRenderError:
        raise
    except FileNotFoundError as exc:
        raise WaveRenderError(f"WAVE_RENDER_TOOL_MISSING:{args[0]}") from exc
    except Exception as exc:
        raise WaveRenderError("WAVE_RENDER_EXECUTION_FAILED") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500]
        raise WaveRenderError(
            f"WAVE_RENDER_FFMPEG_FAILED:{detail or 'NONZERO_EXIT'}"
        )
    return result


def _bound_manifest(
    source_sha256: str,
    manifests: Mapping[str, MediaManifest],
) -> MediaManifest:
    manifest = manifests.get(source_sha256)
    if not isinstance(manifest, MediaManifest):
        raise WaveRenderError("WAVE_RENDER_MANIFEST_NOT_BOUND")
    if manifest.source_sha256 != source_sha256:
        raise WaveRenderError("WAVE_RENDER_MANIFEST_HASH_MISMATCH")
    source = Path(manifest.source_path).expanduser().resolve()
    if not source.is_file():
        raise WaveRenderError("WAVE_RENDER_SOURCE_NOT_FOUND")
    if source.stat().st_size <= 0:
        raise WaveRenderError("WAVE_RENDER_SOURCE_EMPTY")
    if _sha256_file(source) != manifest.source_sha256:
        raise WaveRenderError("WAVE_RENDER_SOURCE_HASH_MISMATCH")
    return manifest


def _collect_clips(timeline: WaveEditorialTimeline):
    video_tracks = [track for track in timeline.tracks if track.kind == "VIDEO"]
    if len(video_tracks) != 1:
        raise WaveRenderError("WAVE_RENDER_SINGLE_VIDEO_TRACK_REQUIRED")
    clips = tuple(video_tracks[0].clips)
    if not clips:
        raise WaveRenderError("WAVE_RENDER_CLIP_REQUIRED")
    return clips


def _require_managed_color(manifest: MediaManifest) -> None:
    if manifest.video_stream.color.ambiguous:
        raise WaveRenderError("WAVE_RENDER_COLOR_METADATA_AMBIGUOUS")


def _build_filter_graph(
    timeline: WaveEditorialTimeline,
    manifest: MediaManifest,
) -> tuple[str, bool]:
    clips = _collect_clips(timeline)
    has_audio = bool(manifest.audio_streams)
    pieces: list[str] = []
    labels: list[str] = []

    for index, clip in enumerate(clips):
        start = float(clip.source_in_seconds)
        duration = float(clip.duration_seconds)
        pieces.append(
            f"[0:v:0]trim=start={start:.6f}:duration={duration:.6f},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        labels.append(f"[v{index}]")
        if has_audio:
            pieces.append(
                f"[0:a:0]atrim=start={start:.6f}:duration={duration:.6f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            labels.append(f"[a{index}]")

    if len(clips) == 1:
        pieces.append("[v0]null[vout]")
        if has_audio:
            pieces.append("[a0]anull[aout]")
    else:
        pieces.append(
            "".join(labels)
            + f"concat=n={len(clips)}:v=1:a={1 if has_audio else 0}"
            + ("[vout][aout]" if has_audio else "[vout]")
        )

    return ";".join(pieces), has_audio


def render_wave_timeline(
    timeline: WaveEditorialTimeline,
    *,
    manifests: Mapping[str, MediaManifest],
    output_root: Path | str,
    render_id: str,
    expected_revision: int,
    runner: Runner | None = None,
) -> WaveRenderReceipt:
    if expected_revision != timeline.revision:
        raise WaveRenderError("WAVE_RENDER_TIMELINE_STALE")
    if not _RENDER_ID_RE.fullmatch(str(render_id or "")):
        raise WaveRenderError("WAVE_RENDER_ID_INVALID")

    clips = _collect_clips(timeline)
    source_hashes = {clip.media_reference.source_sha256 for clip in clips}
    if len(source_hashes) != 1:
        raise WaveRenderError("WAVE_RENDER_MULTI_SOURCE_NOT_YET_SUPPORTED")
    source_sha256 = next(iter(source_hashes))
    manifest = _bound_manifest(source_sha256, manifests)
    _require_managed_color(manifest)

    expected_source_path = Path(manifest.source_path).expanduser().resolve()
    for clip in clips:
        if Path(clip.media_reference.source_path).expanduser().resolve() != expected_source_path:
            raise WaveRenderError("WAVE_RENDER_SOURCE_REFERENCE_MISMATCH")
        if (
            clip.source_in_seconds < 0
            or clip.duration_seconds <= 0
            or clip.source_in_seconds + clip.duration_seconds
            > manifest.duration_seconds + 1e-9
        ):
            raise WaveRenderError("WAVE_RENDER_CLIP_RANGE_INVALID")

    root = Path(output_root).expanduser().resolve()
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    output = artifacts / f"{render_id}.mp4"
    if output.exists():
        raise WaveRenderError("WAVE_RENDER_OUTPUT_ALREADY_EXISTS")

    graph, has_audio = _build_filter_graph(timeline, manifest)
    color = manifest.video_stream.color
    rate = manifest.video_stream.frame_rate

    args = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-i",
        str(expected_source_path),
        "-filter_complex",
        graph,
        "-map",
        "[vout]",
    ]
    if has_audio:
        args += ["-map", "[aout]"]

    args += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        f"{rate.numerator}/{rate.denominator}",
        "-color_primaries",
        color.primaries,
        "-color_trc",
        color.transfer,
        "-colorspace",
        color.matrix,
        "-color_range",
        color.range,
    ]
    if has_audio:
        audio = manifest.audio_streams[0]
        args += [
            "-c:a",
            "aac",
            "-ar",
            str(audio.sample_rate),
            "-ac",
            str(audio.channels),
        ]
    args += ["-movflags", "+faststart", str(output)]

    execute = runner or _default_runner
    _run_checked(execute, args)

    if not output.is_file():
        raise WaveRenderError("WAVE_RENDER_OUTPUT_MISSING")
    if output.stat().st_size <= 0:
        raise WaveRenderError("WAVE_RENDER_OUTPUT_EMPTY")

    try:
        qc = analyze_video_qc(output, runner=execute)
    except VideoQCError as exc:
        raise WaveRenderError(f"WAVE_RENDER_VIDEO_QC_FAILED:{exc}") from exc

    qc_payload = qc.to_dict()
    if qc_payload.get("schema") != "VideoQCReport/v1":
        raise WaveRenderError("WAVE_RENDER_VIDEO_QC_MALFORMED")
    if qc_payload.get("encode_integrity") != "PASS":
        raise WaveRenderError("WAVE_RENDER_ENCODE_INTEGRITY_FAILED")

    return WaveRenderReceipt(
        timeline_id=timeline.timeline_id,
        timeline_revision=timeline.revision,
        output_path=str(output),
        output_sha256=_sha256_file(output),
        source_sha256=source_sha256,
        ffmpeg_command_sha256=_command_digest(args),
        video_qc=qc_payload,
    )
