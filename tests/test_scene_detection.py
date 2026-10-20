from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.scene_detection import (
    SceneDetectionError,
    SceneDetectionResult,
    detect_scenes,
)


def test_scene_detection_report_is_version_bound_and_non_destructive(tmp_path: Path) -> None:
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"video-fixture")
    calls: list[Path] = []

    def backend(path: Path) -> SceneDetectionResult:
        calls.append(path)
        return SceneDetectionResult(
            version="0.7.1",
            detector="ContentDetector",
            scenes=(
                (0.0, 2.5),
                (2.5, 7.0),
                (7.0, 10.0),
            ),
        )

    report = detect_scenes(source, backend=backend)

    assert report.schema == "SceneDetectionReport/v1"
    assert report.source_path == str(source.resolve())
    assert len(report.source_sha256) == 64
    assert report.engine == "PySceneDetect"
    assert report.engine_version == "0.7.1"
    assert report.detector == "ContentDetector"
    assert report.scene_count == 3
    assert report.scenes[0].scene_id == "scene-0001"
    assert report.scenes[0].start_seconds == pytest.approx(0.0)
    assert report.scenes[0].end_seconds == pytest.approx(2.5)
    assert report.scenes[-1].duration_seconds == pytest.approx(3.0)
    assert report.analysis_only is True
    assert report.split_performed is False
    assert calls == [source.resolve()]


def test_scene_detection_rejects_wrong_runtime_version(tmp_path: Path) -> None:
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"video-fixture")

    def backend(path: Path) -> SceneDetectionResult:
        return SceneDetectionResult(
            version="0.7.0",
            detector="ContentDetector",
            scenes=((0.0, 1.0),),
        )

    with pytest.raises(SceneDetectionError, match="SCENE_DETECT_VERSION_MISMATCH"):
        detect_scenes(source, backend=backend)


def test_scene_detection_rejects_overlapping_or_non_monotonic_scenes(tmp_path: Path) -> None:
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"video-fixture")

    def backend(path: Path) -> SceneDetectionResult:
        return SceneDetectionResult(
            version="0.7.1",
            detector="ContentDetector",
            scenes=((0.0, 3.0), (2.5, 5.0)),
        )

    with pytest.raises(SceneDetectionError, match="SCENE_DETECT_SCENES_INVALID"):
        detect_scenes(source, backend=backend)


def test_scene_detection_requires_at_least_one_scene(tmp_path: Path) -> None:
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"video-fixture")

    def backend(path: Path) -> SceneDetectionResult:
        return SceneDetectionResult(
            version="0.7.1",
            detector="ContentDetector",
            scenes=(),
        )

    with pytest.raises(SceneDetectionError, match="SCENE_DETECT_SCENES_EMPTY"):
        detect_scenes(source, backend=backend)


def test_scene_detection_fails_closed_when_runtime_module_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"video-fixture")

    import hazewave.scene_detection as module

    monkeypatch.setattr(
        module,
        "_load_pyscenedetect",
        lambda: (_ for _ in ()).throw(
            SceneDetectionError("SCENE_DETECT_RUNTIME_MISSING")
        ),
    )

    with pytest.raises(SceneDetectionError, match="SCENE_DETECT_RUNTIME_MISSING"):
        detect_scenes(source)


def test_scene_detection_rejects_source_outside_local_filesystem(tmp_path: Path) -> None:
    with pytest.raises(SceneDetectionError, match="SCENE_DETECT_SOURCE_NOT_FOUND"):
        detect_scenes(tmp_path / "missing.mp4", backend=lambda path: None)  # type: ignore[arg-type]
