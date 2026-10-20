from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Final, Iterable


PYSCENEDETECT_EXPECTED_VERSION: Final = "0.7.1"
PYSCENEDETECT_LICENSE: Final = "BSD-3-Clause"


class SceneDetectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SceneDetectionResult:
    version: str
    detector: str
    scenes: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class SceneBoundary:
    scene_id: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    schema: str = "SceneBoundary/v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SceneDetectionReport:
    source_path: str
    source_sha256: str
    engine: str
    engine_version: str
    engine_license: str
    detector: str
    scene_count: int
    scenes: tuple[SceneBoundary, ...]
    analysis_only: bool = True
    split_performed: bool = False
    authority: str = "HAZEWAVE_HARNESS"
    domain: str = "WAVE"
    schema: str = "SceneDetectionReport/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["scenes"] = [scene.to_dict() for scene in self.scenes]
        return value


Backend = Callable[[Path], SceneDetectionResult]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pyscenedetect():
    try:
        import scenedetect
        from scenedetect import ContentDetector, detect
    except ImportError as exc:
        raise SceneDetectionError("SCENE_DETECT_RUNTIME_MISSING") from exc
    return scenedetect, ContentDetector, detect


def _runtime_backend(path: Path) -> SceneDetectionResult:
    scenedetect, ContentDetector, detect = _load_pyscenedetect()
    version = str(getattr(scenedetect, "__version__", "") or "").strip()
    if not version:
        raise SceneDetectionError("SCENE_DETECT_RUNTIME_VERSION_MISSING")

    try:
        raw_scenes = detect(str(path), ContentDetector())
    except Exception as exc:
        raise SceneDetectionError("SCENE_DETECT_EXECUTION_FAILED") from exc

    scenes: list[tuple[float, float]] = []
    for item in raw_scenes:
        try:
            start, end = item
            start_seconds = float(start.get_seconds())
            end_seconds = float(end.get_seconds())
        except (AttributeError, TypeError, ValueError) as exc:
            raise SceneDetectionError("SCENE_DETECT_RUNTIME_RESULT_MALFORMED") from exc
        scenes.append((start_seconds, end_seconds))

    return SceneDetectionResult(
        version=version,
        detector="ContentDetector",
        scenes=tuple(scenes),
    )


def _validate_scenes(
    raw: Iterable[tuple[float, float]],
) -> tuple[SceneBoundary, ...]:
    materialized = tuple(raw)
    if not materialized:
        raise SceneDetectionError("SCENE_DETECT_SCENES_EMPTY")

    result: list[SceneBoundary] = []
    previous_end: float | None = None
    for index, pair in enumerate(materialized, start=1):
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise SceneDetectionError("SCENE_DETECT_SCENES_INVALID")
        try:
            start = float(pair[0])
            end = float(pair[1])
        except (TypeError, ValueError) as exc:
            raise SceneDetectionError("SCENE_DETECT_SCENES_INVALID") from exc

        if start < 0 or end <= start:
            raise SceneDetectionError("SCENE_DETECT_SCENES_INVALID")
        if previous_end is not None and start < previous_end - 1e-9:
            raise SceneDetectionError("SCENE_DETECT_SCENES_INVALID")

        result.append(
            SceneBoundary(
                scene_id=f"scene-{index:04d}",
                start_seconds=start,
                end_seconds=end,
                duration_seconds=end - start,
            )
        )
        previous_end = end

    return tuple(result)


def detect_scenes(
    source: Path | str,
    *,
    backend: Backend | None = None,
    expected_version: str = PYSCENEDETECT_EXPECTED_VERSION,
) -> SceneDetectionReport:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise SceneDetectionError("SCENE_DETECT_SOURCE_NOT_FOUND")
    if path.stat().st_size <= 0:
        raise SceneDetectionError("SCENE_DETECT_SOURCE_EMPTY")

    execute = backend or _runtime_backend
    try:
        result = execute(path)
    except SceneDetectionError:
        raise
    except Exception as exc:
        raise SceneDetectionError("SCENE_DETECT_EXECUTION_FAILED") from exc

    if not isinstance(result, SceneDetectionResult):
        raise SceneDetectionError("SCENE_DETECT_RUNTIME_RESULT_MALFORMED")
    if result.version != expected_version:
        raise SceneDetectionError(
            f"SCENE_DETECT_VERSION_MISMATCH:{result.version}:{expected_version}"
        )
    if not str(result.detector or "").strip():
        raise SceneDetectionError("SCENE_DETECT_DETECTOR_IDENTITY_MISSING")

    scenes = _validate_scenes(result.scenes)

    return SceneDetectionReport(
        source_path=str(path),
        source_sha256=_sha256_file(path),
        engine="PySceneDetect",
        engine_version=result.version,
        engine_license=PYSCENEDETECT_LICENSE,
        detector=result.detector,
        scene_count=len(scenes),
        scenes=scenes,
    )
