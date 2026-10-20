from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.otio_adapter import (
    OTIOAdapterError,
    OTIOBackendResult,
    materialize_otio,
)
from hazewave.wave_editorial import (
    AudioStream,
    ColorMetadata,
    MediaManifest,
    RationalRate,
    VideoStream,
    WaveEditorialTimeline,
)


def _manifest(source: Path) -> MediaManifest:
    import hashlib

    return MediaManifest(
        source_path=str(source.resolve()),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        container_format="mov,mp4,m4a,3gp,3g2,mj2",
        duration_seconds=10.0,
        start_time_seconds=0.0,
        bit_rate=1_000_000,
        video_stream=VideoStream(
            index=0,
            codec_name="h264",
            width=1920,
            height=1080,
            pixel_format="yuv420p",
            frame_rate=RationalRate(30000, 1001),
            duration_seconds=10.0,
            color=ColorMetadata(
                primaries="bt709",
                transfer="bt709",
                matrix="bt709",
                range="tv",
                bit_depth=8,
            ),
        ),
        audio_streams=(
            AudioStream(
                index=1,
                codec_name="aac",
                sample_rate=48000,
                channels=2,
                channel_layout="stereo",
                duration_seconds=10.0,
            ),
        ),
    )


def test_otio_adapter_materializes_version_bound_interchange(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = _manifest(source)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )
    timeline = timeline.cut_clip(
        track_index=0,
        clip_index=0,
        timeline_seconds=4.0,
        expected_revision=0,
    )
    timeline = timeline.add_marker(
        name="Beat Drop",
        timeline_seconds=2.0,
        expected_revision=1,
    )
    captured: dict[str, object] = {}

    def backend(model: dict, output: Path) -> OTIOBackendResult:
        captured["model"] = model
        captured["output"] = output
        output.write_text('{"OTIO_SCHEMA":"Timeline.1"}\n', encoding="utf-8")
        return OTIOBackendResult(
            version="0.18.1",
            adapter="otio_json",
        )

    receipt = materialize_otio(
        timeline,
        output_root=tmp_path / "otio",
        artifact_id="timeline-001",
        expected_revision=2,
        backend=backend,
    )

    assert receipt.schema == "OTIOInterchangeReceipt/v1"
    assert receipt.otio_version == "0.18.1"
    assert receipt.adapter == "otio_json"
    assert receipt.timeline_id == "wave-001"
    assert receipt.timeline_revision == 2
    assert Path(receipt.output_path).is_file()
    assert len(receipt.output_sha256) == 64
    assert receipt.canonical_authority == "WAVE_MODEL"
    assert receipt.grants_authority is False

    model = captured["model"]
    assert isinstance(model, dict)
    assert model["name"] == "Fixture"
    assert model["tracks"][0]["kind"] == "VIDEO"
    assert len(model["tracks"][0]["clips"]) == 2
    assert model["markers"][0]["name"] == "Beat Drop"
    assert captured["output"] == (tmp_path / "otio" / "artifacts" / "timeline-001.otio").resolve()


def test_otio_adapter_rejects_stale_timeline(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=_manifest(source),
    )

    with pytest.raises(OTIOAdapterError, match="OTIO_TIMELINE_STALE"):
        materialize_otio(
            timeline,
            output_root=tmp_path / "otio",
            artifact_id="timeline-001",
            expected_revision=99,
            backend=lambda model, output: None,  # type: ignore[arg-type]
        )


def test_otio_adapter_rejects_path_traversal_artifact_id(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=_manifest(source),
    )

    with pytest.raises(OTIOAdapterError, match="OTIO_ARTIFACT_ID_INVALID"):
        materialize_otio(
            timeline,
            output_root=tmp_path / "otio",
            artifact_id="../escape",
            expected_revision=0,
            backend=lambda model, output: None,  # type: ignore[arg-type]
        )


def test_otio_adapter_rejects_wrong_runtime_version(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=_manifest(source),
    )

    def backend(model: dict, output: Path) -> OTIOBackendResult:
        output.write_text("{}\n", encoding="utf-8")
        return OTIOBackendResult(version="0.18.0", adapter="otio_json")

    with pytest.raises(OTIOAdapterError, match="OTIO_VERSION_MISMATCH"):
        materialize_otio(
            timeline,
            output_root=tmp_path / "otio",
            artifact_id="timeline-001",
            expected_revision=0,
            backend=backend,
        )


def test_otio_adapter_fails_closed_when_runtime_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=_manifest(source),
    )

    import hazewave.otio_adapter as module

    monkeypatch.setattr(
        module,
        "_load_otio",
        lambda: (_ for _ in ()).throw(OTIOAdapterError("OTIO_RUNTIME_MISSING")),
    )

    with pytest.raises(OTIOAdapterError, match="OTIO_RUNTIME_MISSING"):
        materialize_otio(
            timeline,
            output_root=tmp_path / "otio",
            artifact_id="timeline-001",
            expected_revision=0,
        )
