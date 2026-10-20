from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from hazewave.otio_adapter import OTIOInterchangeReceipt
from hazewave.scene_detection import SceneBoundary, SceneDetectionReport
from hazewave.video_qc import VideoQCReport
from hazewave.wave_editorial import (
    AudioStream,
    ColorMetadata,
    MediaManifest,
    RationalRate,
    VideoStream,
)
from hazewave.wave_live_proof import (
    WaveLiveProofError,
    WaveLiveProofRunner,
)
from hazewave.wave_render import WaveRenderReceipt


def _manifest(path: Path, *, duration: float = 6.0) -> MediaManifest:
    import hashlib

    return MediaManifest(
        source_path=str(path.resolve()),
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        container_format="mov,mp4,m4a,3gp,3g2,mj2",
        duration_seconds=duration,
        start_time_seconds=0.0,
        bit_rate=1_000_000,
        video_stream=VideoStream(
            index=0,
            codec_name="h264",
            width=640,
            height=360,
            pixel_format="yuv420p",
            frame_rate=RationalRate(24, 1),
            duration_seconds=duration,
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
                duration_seconds=duration,
            ),
        ),
    )


def _scene_report(path: Path, source_sha256: str) -> SceneDetectionReport:
    return SceneDetectionReport(
        source_path=str(path.resolve()),
        source_sha256=source_sha256,
        engine="PySceneDetect",
        engine_version="0.7.1",
        engine_license="BSD-3-Clause",
        detector="ContentDetector",
        scene_count=3,
        scenes=(
            SceneBoundary("scene-0001", 0.0, 2.0, 2.0),
            SceneBoundary("scene-0002", 2.0, 4.0, 2.0),
            SceneBoundary("scene-0003", 4.0, 6.0, 2.0),
        ),
    )


def _video_qc(path: Path, duration: float = 5.5) -> VideoQCReport:
    import hashlib

    return VideoQCReport(
        output_path=str(path.resolve()),
        output_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        container_format="mov,mp4,m4a,3gp,3g2,mj2",
        duration_seconds=duration,
        video_codec="h264",
        width=640,
        height=360,
        pixel_format="yuv420p",
        frame_rate_numerator=24,
        frame_rate_denominator=1,
        color_primaries="bt709",
        color_transfer="bt709",
        color_matrix="bt709",
        color_range="tv",
        bit_depth=8,
        audio_stream_count=1,
        av_duration_delta_seconds=0.0,
        encode_integrity="PASS",
        technical_flags=(),
    )


def test_wave_live_proof_orchestrates_real_editorial_sequence(tmp_path: Path) -> None:
    calls: list[str] = []

    def fixture_creator(proof_dir: Path) -> Path:
        calls.append("fixture")
        path = proof_dir / "fixture-source.mp4"
        path.write_bytes(b"fixture-source-video")
        return path

    def media_inspector(path: Path) -> MediaManifest:
        calls.append("inspect-source" if "fixture-source" in path.name else "inspect-output")
        return _manifest(path, duration=6.0 if "fixture-source" in path.name else 5.5)

    def scene_detector(path: Path) -> SceneDetectionReport:
        calls.append("scene-detect")
        manifest = _manifest(path)
        return _scene_report(path, manifest.source_sha256)

    def otio_materializer(timeline, *, output_root, artifact_id, expected_revision):
        calls.append("otio")
        assert expected_revision == 3
        output = Path(output_root) / "artifacts" / f"{artifact_id}.otio"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}\n", encoding="utf-8")
        return OTIOInterchangeReceipt(
            timeline_id=timeline.timeline_id,
            timeline_revision=timeline.revision,
            output_path=str(output.resolve()),
            output_sha256="a" * 64,
            otio_version="0.18.1",
            adapter="otio_json",
        )

    def renderer(timeline, *, manifests, output_root, render_id, expected_revision):
        calls.append("render")
        assert expected_revision == 3
        output = Path(output_root) / "artifacts" / f"{render_id}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"rendered-wave-proof")
        qc = _video_qc(output)
        return WaveRenderReceipt(
            timeline_id=timeline.timeline_id,
            timeline_revision=timeline.revision,
            output_path=str(output.resolve()),
            output_sha256=qc.output_sha256,
            source_sha256=next(iter(manifests)),
            ffmpeg_command_sha256="b" * 64,
            video_qc=qc.to_dict(),
        )

    runner = WaveLiveProofRunner(
        proof_root=tmp_path / "proofs",
        candidate_head="c" * 40,
        policy_digest="d" * 64,
        runtime_identity="codespace:fixture",
        fixture_creator=fixture_creator,
        media_inspector=media_inspector,
        scene_detector=scene_detector,
        otio_materializer=otio_materializer,
        renderer=renderer,
    )

    receipt = runner.run(proof_id="wave-001")

    assert receipt["schema"] == "WaveLiveProof/v1"
    assert receipt["status"] == "PASS"
    assert receipt["authority"] == "HAZEWAVE_HARNESS"
    assert receipt["portfolio_authority"] == "NONE"
    assert receipt["candidate_head"] == "c" * 40
    assert receipt["manifest"]["schema"] == "MediaManifest/v1"
    assert receipt["scene_detection"]["schema"] == "SceneDetectionReport/v1"
    assert receipt["scene_detection"]["scene_count"] == 3
    assert receipt["timeline"]["schema"] == "WaveEditorialTimeline/v1"
    assert receipt["timeline"]["revision"] == 3
    assert len(receipt["timeline"]["tracks"][0]["clips"]) == 2
    assert receipt["otio"]["schema"] == "OTIOInterchangeReceipt/v1"
    assert receipt["render"]["schema"] == "WaveRenderReceipt/v1"
    assert receipt["video_qc"]["schema"] == "VideoQCReport/v1"
    assert receipt["video_qc"]["encode_integrity"] == "PASS"
    assert receipt["output_manifest"]["schema"] == "MediaManifest/v1"
    assert receipt["human_review"] == "REQUIRED"
    assert Path(receipt["receipt_path"]).is_file()
    assert len(receipt["receipt_sha256"]) == 64
    assert calls == [
        "fixture",
        "inspect-source",
        "scene-detect",
        "otio",
        "render",
        "inspect-output",
    ]


def test_wave_live_proof_requires_multiple_detected_scenes(tmp_path: Path) -> None:
    def fixture_creator(proof_dir: Path) -> Path:
        path = proof_dir / "fixture-source.mp4"
        path.write_bytes(b"fixture")
        return path

    manifest_holder: dict[str, MediaManifest] = {}

    def media_inspector(path: Path) -> MediaManifest:
        manifest = _manifest(path)
        manifest_holder["value"] = manifest
        return manifest

    def scene_detector(path: Path) -> SceneDetectionReport:
        manifest = manifest_holder["value"]
        return SceneDetectionReport(
            source_path=str(path.resolve()),
            source_sha256=manifest.source_sha256,
            engine="PySceneDetect",
            engine_version="0.7.1",
            engine_license="BSD-3-Clause",
            detector="ContentDetector",
            scene_count=1,
            scenes=(SceneBoundary("scene-0001", 0.0, 6.0, 6.0),),
        )

    runner = WaveLiveProofRunner(
        proof_root=tmp_path / "proofs",
        candidate_head="c" * 40,
        policy_digest="d" * 64,
        runtime_identity="codespace:fixture",
        fixture_creator=fixture_creator,
        media_inspector=media_inspector,
        scene_detector=scene_detector,
        otio_materializer=lambda *args, **kwargs: None,
        renderer=lambda *args, **kwargs: None,
    )

    with pytest.raises(WaveLiveProofError, match="WAVE_LIVE_SCENE_PROOF_INSUFFICIENT"):
        runner.run(proof_id="wave-one-scene")


def test_wave_live_proof_rejects_duplicate_proof_directory(tmp_path: Path) -> None:
    root = tmp_path / "proofs"
    (root / "wave-001").mkdir(parents=True)

    runner = WaveLiveProofRunner(
        proof_root=root,
        candidate_head="c" * 40,
        policy_digest="d" * 64,
        runtime_identity="codespace:fixture",
    )

    with pytest.raises(WaveLiveProofError, match="WAVE_LIVE_PROOF_ALREADY_EXISTS"):
        runner.run(proof_id="wave-001")


def test_wave_live_proof_requires_exact_candidate_and_policy_digests(tmp_path: Path) -> None:
    with pytest.raises(WaveLiveProofError, match="WAVE_LIVE_CANDIDATE_HEAD_INVALID"):
        WaveLiveProofRunner(
            proof_root=tmp_path,
            candidate_head="not-a-sha",
            policy_digest="d" * 64,
            runtime_identity="codespace:fixture",
        )

    with pytest.raises(WaveLiveProofError, match="WAVE_LIVE_POLICY_DIGEST_INVALID"):
        WaveLiveProofRunner(
            proof_root=tmp_path,
            candidate_head="c" * 40,
            policy_digest="bad",
            runtime_identity="codespace:fixture",
        )
