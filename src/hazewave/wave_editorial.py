from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Final


ANIMATED_CARTOON: Final = "ANIMATED_CARTOON"


class WaveEditorialError(RuntimeError):
    pass


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class RationalRate:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            raise WaveEditorialError("WAVE_FRAME_RATE_INVALID")

    @property
    def value(self) -> float:
        return self.numerator / self.denominator

    def to_dict(self) -> dict[str, int]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True)
class ColorMetadata:
    primaries: str
    transfer: str
    matrix: str
    range: str
    bit_depth: int
    schema: str = "ColorMetadata/v1"

    def __post_init__(self) -> None:
        if self.bit_depth <= 0:
            raise WaveEditorialError("WAVE_COLOR_BIT_DEPTH_INVALID")

    @property
    def ambiguous(self) -> bool:
        unknown = {"", "unknown", "unspecified", "reserved", "n/a", "none"}
        return any(
            str(value).strip().casefold() in unknown
            for value in (
                self.primaries,
                self.transfer,
                self.matrix,
                self.range,
            )
        )

    def require_managed_transform(self) -> None:
        if self.ambiguous:
            raise WaveEditorialError("WAVE_COLOR_METADATA_AMBIGUOUS")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "primaries": self.primaries,
            "transfer": self.transfer,
            "matrix": self.matrix,
            "range": self.range,
            "bit_depth": self.bit_depth,
            "ambiguous": self.ambiguous,
        }


@dataclass(frozen=True)
class VideoStream:
    index: int
    codec_name: str
    width: int
    height: int
    pixel_format: str
    frame_rate: RationalRate
    duration_seconds: float
    color: ColorMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "codec_name": self.codec_name,
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format,
            "frame_rate": self.frame_rate.to_dict(),
            "duration_seconds": self.duration_seconds,
            "color": self.color.to_dict(),
        }


@dataclass(frozen=True)
class AudioStream:
    index: int
    codec_name: str
    sample_rate: int
    channels: int
    channel_layout: str
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "codec_name": self.codec_name,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class MediaManifest:
    source_path: str
    source_sha256: str
    container_format: str
    duration_seconds: float
    start_time_seconds: float
    bit_rate: int
    video_stream: VideoStream
    audio_streams: tuple[AudioStream, ...]
    private_media_policy: str = "LOCAL_BY_DEFAULT"
    schema: str = "MediaManifest/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "container_format": self.container_format,
            "duration_seconds": self.duration_seconds,
            "start_time_seconds": self.start_time_seconds,
            "bit_rate": self.bit_rate,
            "video_stream": self.video_stream.to_dict(),
            "audio_streams": [item.to_dict() for item in self.audio_streams],
            "private_media_policy": self.private_media_policy,
        }


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
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise WaveEditorialError("WAVE_FFPROBE_MISSING") from exc
    except subprocess.TimeoutExpired as exc:
        raise WaveEditorialError("WAVE_FFPROBE_TIMEOUT") from exc


def _parse_rate(value: object) -> RationalRate:
    raw = str(value or "").strip()
    if not raw or raw in {"0/0", "N/A"}:
        raise WaveEditorialError("WAVE_FRAME_RATE_INVALID")
    try:
        fraction = Fraction(raw)
    except (ValueError, ZeroDivisionError) as exc:
        raise WaveEditorialError("WAVE_FRAME_RATE_INVALID") from exc
    if fraction <= 0:
        raise WaveEditorialError("WAVE_FRAME_RATE_INVALID")
    return RationalRate(fraction.numerator, fraction.denominator)


def _float_field(payload: dict[str, Any], key: str, *, default: float | None = None) -> float:
    value = payload.get(key)
    if value in (None, "", "N/A"):
        if default is None:
            raise WaveEditorialError(f"WAVE_FFPROBE_FIELD_MISSING:{key}")
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WaveEditorialError(f"WAVE_FFPROBE_FIELD_INVALID:{key}") from exc
    return result


def _int_field(payload: dict[str, Any], key: str, *, default: int | None = None) -> int:
    value = payload.get(key)
    if value in (None, "", "N/A"):
        if default is None:
            raise WaveEditorialError(f"WAVE_FFPROBE_FIELD_MISSING:{key}")
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WaveEditorialError(f"WAVE_FFPROBE_FIELD_INVALID:{key}") from exc
    return result


def inspect_media(
    source: Path | str,
    *,
    runner: Runner | None = None,
) -> MediaManifest:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise WaveEditorialError("WAVE_MEDIA_SOURCE_NOT_FOUND")
    execute = runner or _default_runner
    args = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = execute(args)
    except WaveEditorialError:
        raise
    except FileNotFoundError as exc:
        raise WaveEditorialError("WAVE_FFPROBE_MISSING") from exc
    except Exception as exc:
        raise WaveEditorialError("WAVE_FFPROBE_EXECUTION_FAILED") from exc
    if result.returncode != 0:
        raise WaveEditorialError("WAVE_FFPROBE_FAILED")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WaveEditorialError("WAVE_FFPROBE_MALFORMED") from exc
    if not isinstance(payload, dict):
        raise WaveEditorialError("WAVE_FFPROBE_MALFORMED")
    streams = payload.get("streams")
    format_payload = payload.get("format")
    if not isinstance(streams, list) or not isinstance(format_payload, dict):
        raise WaveEditorialError("WAVE_FFPROBE_MALFORMED")

    video_candidates = [
        item
        for item in streams
        if isinstance(item, dict) and item.get("codec_type") == "video"
    ]
    if not video_candidates:
        raise WaveEditorialError("WAVE_VIDEO_STREAM_REQUIRED")
    video_raw = video_candidates[0]

    duration = _float_field(format_payload, "duration")
    if duration < 0:
        raise WaveEditorialError("WAVE_MEDIA_DURATION_INVALID")
    video_duration = _float_field(video_raw, "duration", default=duration)
    bit_depth = _int_field(
        video_raw,
        "bits_per_raw_sample",
        default=_int_field(video_raw, "bits_per_sample", default=8),
    )
    color = ColorMetadata(
        primaries=str(video_raw.get("color_primaries") or "unknown"),
        transfer=str(video_raw.get("color_transfer") or "unknown"),
        matrix=str(video_raw.get("color_space") or "unknown"),
        range=str(video_raw.get("color_range") or "unknown"),
        bit_depth=bit_depth,
    )
    video = VideoStream(
        index=_int_field(video_raw, "index"),
        codec_name=str(video_raw.get("codec_name") or ""),
        width=_int_field(video_raw, "width"),
        height=_int_field(video_raw, "height"),
        pixel_format=str(video_raw.get("pix_fmt") or ""),
        frame_rate=_parse_rate(
            video_raw.get("avg_frame_rate") or video_raw.get("r_frame_rate")
        ),
        duration_seconds=video_duration,
        color=color,
    )
    if not video.codec_name or not video.pixel_format or video.width <= 0 or video.height <= 0:
        raise WaveEditorialError("WAVE_VIDEO_STREAM_MALFORMED")

    audio: list[AudioStream] = []
    for item in streams:
        if not isinstance(item, dict) or item.get("codec_type") != "audio":
            continue
        stream = AudioStream(
            index=_int_field(item, "index"),
            codec_name=str(item.get("codec_name") or ""),
            sample_rate=_int_field(item, "sample_rate"),
            channels=_int_field(item, "channels"),
            channel_layout=str(item.get("channel_layout") or ""),
            duration_seconds=_float_field(item, "duration", default=duration),
        )
        if not stream.codec_name or stream.sample_rate <= 0 or stream.channels <= 0:
            raise WaveEditorialError("WAVE_AUDIO_STREAM_MALFORMED")
        audio.append(stream)

    return MediaManifest(
        source_path=str(path),
        source_sha256=_sha256_file(path),
        container_format=str(format_payload.get("format_name") or ""),
        duration_seconds=duration,
        start_time_seconds=_float_field(format_payload, "start_time", default=0.0),
        bit_rate=_int_field(format_payload, "bit_rate", default=0),
        video_stream=video,
        audio_streams=tuple(audio),
    )


@dataclass(frozen=True)
class MediaReference:
    source_path: str
    source_sha256: str
    available_range_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ExternalReference/v1",
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "available_range_seconds": self.available_range_seconds,
        }


@dataclass(frozen=True)
class WaveClip:
    clip_id: str
    name: str
    media_reference: MediaReference
    source_in_seconds: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if not self.clip_id.strip():
            raise WaveEditorialError("WAVE_CLIP_ID_REQUIRED")
        if self.source_in_seconds < 0 or self.duration_seconds <= 0:
            raise WaveEditorialError("WAVE_CLIP_RANGE_INVALID")
        if (
            self.source_in_seconds + self.duration_seconds
            > self.media_reference.available_range_seconds + 1e-9
        ):
            raise WaveEditorialError("WAVE_CLIP_RANGE_OUTSIDE_MEDIA")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "Clip/v1",
            "clip_id": self.clip_id,
            "name": self.name,
            "media_reference": self.media_reference.to_dict(),
            "source_range": {
                "start_seconds": self.source_in_seconds,
                "duration_seconds": self.duration_seconds,
            },
            "source_in_seconds": self.source_in_seconds,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class WaveTrack:
    kind: str
    clips: tuple[WaveClip, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "Track/v1",
            "kind": self.kind,
            "clips": [clip.to_dict() for clip in self.clips],
        }


@dataclass(frozen=True)
class WaveMarker:
    name: str
    timeline_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "Marker/v1",
            "name": self.name,
            "timeline_seconds": self.timeline_seconds,
        }


@dataclass(frozen=True)
class WaveEditorialTimeline:
    timeline_id: str
    name: str
    tracks: tuple[WaveTrack, ...]
    markers: tuple[WaveMarker, ...] = ()
    revision: int = 0
    final_video_mode: str = ANIMATED_CARTOON
    schema: str = "WaveEditorialTimeline/v1"

    def __post_init__(self) -> None:
        if not self.timeline_id.strip() or not self.name.strip():
            raise WaveEditorialError("WAVE_TIMELINE_IDENTITY_REQUIRED")
        if self.revision < 0:
            raise WaveEditorialError("WAVE_TIMELINE_REVISION_INVALID")
        if self.final_video_mode != ANIMATED_CARTOON:
            raise WaveEditorialError("WAVE_FINAL_VIDEO_MODE_POLICY")
        if not self.tracks:
            raise WaveEditorialError("WAVE_TIMELINE_TRACK_REQUIRED")

    @classmethod
    def create(
        cls,
        *,
        timeline_id: str,
        name: str,
        manifest: MediaManifest,
        final_video_mode: str = ANIMATED_CARTOON,
    ) -> "WaveEditorialTimeline":
        if final_video_mode != ANIMATED_CARTOON:
            raise WaveEditorialError("WAVE_FINAL_VIDEO_MODE_POLICY")
        ref = MediaReference(
            source_path=manifest.source_path,
            source_sha256=manifest.source_sha256,
            available_range_seconds=manifest.duration_seconds,
        )
        clip = WaveClip(
            clip_id=f"{timeline_id}-clip-0001",
            name=Path(manifest.source_path).name,
            media_reference=ref,
            source_in_seconds=0.0,
            duration_seconds=manifest.duration_seconds,
        )
        return cls(
            timeline_id=timeline_id,
            name=name,
            tracks=(WaveTrack(kind="VIDEO", clips=(clip,)),),
            final_video_mode=final_video_mode,
        )

    def _require_revision(self, expected_revision: int) -> None:
        if expected_revision != self.revision:
            raise WaveEditorialError("WAVE_TIMELINE_STALE")

    def _track_clip(self, track_index: int, clip_index: int) -> tuple[WaveTrack, WaveClip]:
        try:
            track = self.tracks[track_index]
            clip = track.clips[clip_index]
        except IndexError as exc:
            raise WaveEditorialError("WAVE_TIMELINE_INDEX_INVALID") from exc
        return track, clip

    def _replace_track(
        self,
        track_index: int,
        track: WaveTrack,
    ) -> tuple[WaveTrack, ...]:
        tracks = list(self.tracks)
        tracks[track_index] = track
        return tuple(tracks)

    def cut_clip(
        self,
        *,
        track_index: int,
        clip_index: int,
        timeline_seconds: float,
        expected_revision: int,
    ) -> "WaveEditorialTimeline":
        self._require_revision(expected_revision)
        track, clip = self._track_clip(track_index, clip_index)
        if timeline_seconds <= 0 or timeline_seconds >= clip.duration_seconds:
            raise WaveEditorialError("WAVE_CUT_POSITION_INVALID")
        first = replace(
            clip,
            clip_id=f"{clip.clip_id}-a",
            duration_seconds=float(timeline_seconds),
        )
        second = replace(
            clip,
            clip_id=f"{clip.clip_id}-b",
            source_in_seconds=clip.source_in_seconds + float(timeline_seconds),
            duration_seconds=clip.duration_seconds - float(timeline_seconds),
        )
        clips = list(track.clips)
        clips[clip_index : clip_index + 1] = [first, second]
        new_track = replace(track, clips=tuple(clips))
        return replace(
            self,
            tracks=self._replace_track(track_index, new_track),
            revision=self.revision + 1,
        )

    def trim_clip(
        self,
        *,
        track_index: int,
        clip_index: int,
        new_in_seconds: float,
        new_out_seconds: float,
        expected_revision: int,
    ) -> "WaveEditorialTimeline":
        self._require_revision(expected_revision)
        track, clip = self._track_clip(track_index, clip_index)
        start = float(new_in_seconds)
        end = float(new_out_seconds)
        if start < 0 or end <= start:
            raise WaveEditorialError("WAVE_TRIM_RANGE_INVALID")
        if end > clip.media_reference.available_range_seconds + 1e-9:
            raise WaveEditorialError("WAVE_TRIM_RANGE_OUTSIDE_MEDIA")
        new_clip = replace(
            clip,
            source_in_seconds=start,
            duration_seconds=end - start,
        )
        clips = list(track.clips)
        clips[clip_index] = new_clip
        new_track = replace(track, clips=tuple(clips))
        return replace(
            self,
            tracks=self._replace_track(track_index, new_track),
            revision=self.revision + 1,
        )

    def add_marker(
        self,
        *,
        name: str,
        timeline_seconds: float,
        expected_revision: int,
    ) -> "WaveEditorialTimeline":
        self._require_revision(expected_revision)
        if not name.strip() or timeline_seconds < 0:
            raise WaveEditorialError("WAVE_MARKER_INVALID")
        marker = WaveMarker(name=name.strip(), timeline_seconds=float(timeline_seconds))
        return replace(
            self,
            markers=self.markers + (marker,),
            revision=self.revision + 1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "timeline_id": self.timeline_id,
            "name": self.name,
            "revision": self.revision,
            "final_video_mode": self.final_video_mode,
            "tracks": [track.to_dict() for track in self.tracks],
            "markers": [marker.to_dict() for marker in self.markers],
            "otio_compatibility": {
                "concepts": [
                    "Timeline",
                    "Track",
                    "Clip",
                    "ExternalReference",
                    "TimeRange",
                    "Marker",
                    "Transition",
                ],
                "target_release_baseline": "0.18.1",
                "runtime_adapter": "NOT_PROVEN",
            },
        }
