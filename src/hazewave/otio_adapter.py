from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Callable, Mapping

from hazewave.wave_editorial import WaveEditorialTimeline


OTIO_EXPECTED_VERSION = "0.18.1"


class OTIOAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class OTIOBackendResult:
    version: str
    adapter: str


@dataclass(frozen=True)
class OTIOInterchangeReceipt:
    timeline_id: str
    timeline_revision: int
    output_path: str
    output_sha256: str
    otio_version: str
    adapter: str
    canonical_authority: str = "WAVE_MODEL"
    grants_authority: bool = False
    schema: str = "OTIOInterchangeReceipt/v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


Backend = Callable[[dict, Path], OTIOBackendResult]

_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_otio():
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise OTIOAdapterError("OTIO_RUNTIME_MISSING") from exc
    return otio


def _rt(otio, seconds: float):
    rate = 1000.0
    return otio.opentime.RationalTime(float(seconds) * rate, rate)


def _time_range(otio, start_seconds: float, duration_seconds: float):
    return otio.opentime.TimeRange(
        start_time=_rt(otio, start_seconds),
        duration=_rt(otio, duration_seconds),
    )


def _runtime_backend(model: dict, output: Path) -> OTIOBackendResult:
    otio = _load_otio()
    version = str(getattr(otio, "__version__", "") or "").strip()
    if not version:
        raise OTIOAdapterError("OTIO_RUNTIME_VERSION_MISSING")
    if version != OTIO_EXPECTED_VERSION:
        raise OTIOAdapterError(
            f"OTIO_VERSION_MISMATCH:{version}:{OTIO_EXPECTED_VERSION}"
        )

    try:
        timeline = otio.schema.Timeline(name=str(model["name"]))
        for track_payload in model["tracks"]:
            kind_value = str(track_payload.get("kind") or "")
            if kind_value == "VIDEO":
                kind = otio.schema.TrackKind.Video
            elif kind_value == "AUDIO":
                kind = otio.schema.TrackKind.Audio
            else:
                raise OTIOAdapterError("OTIO_TRACK_KIND_UNSUPPORTED")

            track = otio.schema.Track(kind=kind)
            for clip_payload in track_payload.get("clips", []):
                media_payload = clip_payload["media_reference"]
                available = float(media_payload["available_range_seconds"])
                media_reference = otio.schema.ExternalReference(
                    target_url=str(media_payload["source_path"]),
                    available_range=_time_range(otio, 0.0, available),
                )
                media_reference.metadata["hazewave_source_sha256"] = str(
                    media_payload["source_sha256"]
                )

                source_range = clip_payload["source_range"]
                clip = otio.schema.Clip(
                    name=str(clip_payload.get("name") or clip_payload["clip_id"]),
                    media_reference=media_reference,
                    source_range=_time_range(
                        otio,
                        float(source_range["start_seconds"]),
                        float(source_range["duration_seconds"]),
                    ),
                )
                clip.metadata["hazewave_clip_id"] = str(clip_payload["clip_id"])
                track.append(clip)
            timeline.tracks.append(track)

        for marker_payload in model.get("markers", []):
            marker = otio.schema.Marker(
                name=str(marker_payload["name"]),
                marked_range=_time_range(
                    otio,
                    float(marker_payload["timeline_seconds"]),
                    0.0,
                ),
            )
            timeline.markers.append(marker)

        timeline.metadata["hazewave_timeline_id"] = str(model["timeline_id"])
        timeline.metadata["hazewave_revision"] = int(model["revision"])
        timeline.metadata["hazewave_final_video_mode"] = str(
            model["final_video_mode"]
        )
        otio.adapters.write_to_file(
            timeline,
            str(output),
            adapter_name="otio_json",
        )
    except OTIOAdapterError:
        raise
    except Exception as exc:
        raise OTIOAdapterError("OTIO_MATERIALIZATION_FAILED") from exc

    return OTIOBackendResult(
        version=version,
        adapter="otio_json",
    )


def _interchange_model(timeline: WaveEditorialTimeline) -> dict:
    payload = timeline.to_dict()
    return {
        "timeline_id": payload["timeline_id"],
        "name": payload["name"],
        "revision": payload["revision"],
        "final_video_mode": payload["final_video_mode"],
        "tracks": payload["tracks"],
        "markers": payload["markers"],
    }


def materialize_otio(
    timeline: WaveEditorialTimeline,
    *,
    output_root: Path | str,
    artifact_id: str,
    expected_revision: int,
    backend: Backend | None = None,
) -> OTIOInterchangeReceipt:
    if expected_revision != timeline.revision:
        raise OTIOAdapterError("OTIO_TIMELINE_STALE")
    artifact = str(artifact_id or "")
    if not _ARTIFACT_ID_RE.fullmatch(artifact):
        raise OTIOAdapterError("OTIO_ARTIFACT_ID_INVALID")

    root = Path(output_root).expanduser().resolve()
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    output = (artifacts / f"{artifact}.otio").resolve()
    try:
        output.relative_to(artifacts.resolve())
    except ValueError as exc:
        raise OTIOAdapterError("OTIO_OUTPUT_OUTSIDE_ROOT") from exc
    if output.exists():
        raise OTIOAdapterError("OTIO_OUTPUT_ALREADY_EXISTS")

    execute = backend or _runtime_backend
    model = _interchange_model(timeline)
    try:
        result = execute(model, output)
    except OTIOAdapterError:
        raise
    except Exception as exc:
        raise OTIOAdapterError("OTIO_MATERIALIZATION_FAILED") from exc

    if not isinstance(result, OTIOBackendResult):
        raise OTIOAdapterError("OTIO_BACKEND_RESULT_MALFORMED")
    if result.version != OTIO_EXPECTED_VERSION:
        raise OTIOAdapterError(
            f"OTIO_VERSION_MISMATCH:{result.version}:{OTIO_EXPECTED_VERSION}"
        )
    if result.adapter != "otio_json":
        raise OTIOAdapterError("OTIO_ADAPTER_IDENTITY_MISMATCH")
    if not output.is_file():
        raise OTIOAdapterError("OTIO_OUTPUT_MISSING")
    if output.stat().st_size <= 0:
        raise OTIOAdapterError("OTIO_OUTPUT_EMPTY")

    return OTIOInterchangeReceipt(
        timeline_id=timeline.timeline_id,
        timeline_revision=timeline.revision,
        output_path=str(output),
        output_sha256=_sha256_file(output),
        otio_version=result.version,
        adapter=result.adapter,
    )
