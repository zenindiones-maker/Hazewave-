"""Evidence-first, owner-authorized audiovisual reverse-engineering laboratory.

REA inspects *software*. HAZE/WAVE measurements are produced by the project's
existing purpose-built analyzers. No model downloads, arbitrary shell commands,
publication, stock mutations, or autonomous approval occur here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Callable, Mapping


class AVResearchError(RuntimeError):
    pass


KINDS: dict[str, tuple[str, str, str]] = {
    "AUDIO_QC": ("HAZE", "audio_asset", "research.audio.inspect"),
    "AUDIO_MUSIC": ("HAZE", "audio_asset", "research.audio.inspect"),
    "VIDEO_QC": ("WAVE", "video_asset", "research.visual.inspect"),
    "SCENE_DETECTION": ("WAVE", "video_asset", "research.visual.inspect"),
    "IMAGE_METRICS": ("WAVE", "image_asset", "research.visual.inspect"),
    "EDITORIAL_SCRIPT": ("WAVE", "editorial_script", "research.visual.inspect"),
}
_ALLOWED_CASE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{3,79}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_PRIVATE_FIELD_NAMES = frozenset({
    "source_path", "output_path", "input_path", "filepath", "filename",
    "local_path", "path", "original_text", "text", "narration", "transcript",
    "script", "media_path",
})


def research_specialist(kind: str) -> dict[str, str]:
    if kind not in KINDS:
        raise AVResearchError(f"RESEARCH_KIND_UNSUPPORTED:{kind}")
    domain, target_kind, capability = KINDS[kind]
    return {
        "domain": domain,
        "target_kind": target_kind,
        "capability": capability,
        "authority": "HAZEWAVE_HARNESS",
        "analyzer_authority": "NONE",
    }


def _private_metrics(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _private_metrics(item)
            for key, item in value.items()
            if key not in _PRIVATE_FIELD_NAMES
        }
    if isinstance(value, (list, tuple)):
        return [_private_metrics(item) for item in value]
    if isinstance(value, Path):
        raise AVResearchError("RESEARCH_PRIVATE_PATH_LEAK")
    if isinstance(value, float) and not math.isfinite(value):
        raise AVResearchError("RESEARCH_NUMERIC_NONFINITE")
    return value


def compose_research_evidence(
    *,
    kind: str,
    source_sha256: str,
    grant_evidence: Mapping[str, Any],
    measurements: Mapping[str, Any],
    case_id: str,
) -> dict[str, Any]:
    specialist = research_specialist(kind)
    if not _ALLOWED_CASE.fullmatch(case_id):
        raise AVResearchError("RESEARCH_CASE_ID_INVALID")
    if not _HEX.fullmatch(source_sha256):
        raise AVResearchError("RESEARCH_SOURCE_SHA_INVALID")
    if (
        grant_evidence.get("signature_verified") is not True
        or grant_evidence.get("target_sha256") != source_sha256
    ):
        raise AVResearchError("RESEARCH_GRANT_DIGEST_MISMATCH")
    if not isinstance(measurements, Mapping) or not measurements:
        raise AVResearchError("RESEARCH_MEASUREMENTS_REQUIRED")
    stripped = _private_metrics(measurements)
    if not stripped:
        raise AVResearchError("RESEARCH_MEASUREMENTS_REQUIRED")
    # Verify that even nested unsupported objects are serializable before storing.
    try:
        normalized = json.loads(json.dumps(stripped, allow_nan=False, sort_keys=True))
    except (ValueError, TypeError) as exc:
        raise AVResearchError("RESEARCH_MEASUREMENTS_NOT_JSON_SAFE") from exc

    return {
        "schema": "HazewaveAVResearchEvidence/v1",
        "case_id": case_id,
        "kind": kind,
        "domain": specialist["domain"],
        "source_sha256": source_sha256,
        "grant_id": grant_evidence.get("grant_id"),
        "signature_verified": True,
        "capability": specialist["capability"],
        "provider_authority": "NONE",
        "harness_authority": "HAZEWAVE_HARNESS",
        "state": "OBSERVATION_ONLY",
        "technical_measurements": normalized,
        "artistic_verdict": "NOT_ASSIGNED",
        "production_approved": False,
        "publication_authorized": False,
        "reconstruction_approved": False,
        "human_review_required": True,
        "private_media_policy": "LOCAL_ONLY",
        "limitations": [
            "Technical measurements do not recover original creative intent.",
            "No human judgment, reproduction fidelity, or production acceptance is implied.",
        ],
    }


def analyze_editorial_script(source: Path) -> dict[str, Any]:
    """Analyze a structured script without retaining words, dialogue or images."""
    try:
        if source.stat().st_size > 2 * 1024 * 1024:
            raise AVResearchError("RESEARCH_EDITORIAL_INPUT_TOO_LARGE")
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AVResearchError("RESEARCH_EDITORIAL_JSON_INVALID") from exc
    if not isinstance(data, dict) or data.get("schema") != "HazewaveEditorialReference/v1":
        raise AVResearchError("RESEARCH_EDITORIAL_SCHEMA_INVALID")
    segments = data.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 1000:
        raise AVResearchError("RESEARCH_EDITORIAL_SEGMENTS_INVALID")
    word_counts: list[int] = []
    paces: list[float] = []
    previous_end = 0.0
    overlaps = 0
    gaps = 0
    duration = 0.0
    seen: set[str] = set()
    repeating_4grams: set[tuple[str, ...]] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise AVResearchError("RESEARCH_EDITORIAL_SEGMENT_INVALID")
        identifier = segment.get("id")
        if not isinstance(identifier, str) or not _ALLOWED_CASE.fullmatch(identifier):
            raise AVResearchError("RESEARCH_EDITORIAL_SEGMENT_ID_INVALID")
        if identifier in seen:
            raise AVResearchError("RESEARCH_EDITORIAL_DUPLICATE_SEGMENT")
        seen.add(identifier)
        try:
            start = float(segment["start_seconds"])
            length = float(segment["duration_seconds"])
        except (ValueError, KeyError, TypeError) as exc:
            raise AVResearchError("RESEARCH_EDITORIAL_TIME_INVALID") from exc
        if not (math.isfinite(start) and math.isfinite(length)) or start < 0 or length <= 0:
            raise AVResearchError("RESEARCH_EDITORIAL_TIME_INVALID")
        if start < previous_end - 1e-9:
            overlaps += 1
        elif start > previous_end + 1e-9:
            gaps += 1
        previous_end = max(previous_end, start + length)
        duration = max(duration, start + length)
        text = segment.get("narration")
        if not isinstance(text, str) or len(text) > 100_000:
            raise AVResearchError("RESEARCH_EDITORIAL_TEXT_INVALID")
        words = re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", text, flags=re.UNICODE)
        lower = [w.casefold() for w in words]
        for i in range(max(0, len(lower) - 3)):
            phrase = tuple(lower[i:i + 4])
            if phrase in repeating_4grams:
                continue
            # Repetitions are only reliably identified within/between segments,
            # never assigned a creative verdict or treated as a plagiarism test.
            repeating_4grams.add(phrase)
        count = len(words)
        word_counts.append(count)
        paces.append(count * 60 / length)
    return {
        "schema": "HazewaveEditorialMeasurements/v1",
        "segment_count": len(segments),
        "word_count": sum(word_counts),
        "duration_seconds": round(duration, 6),
        "nominal_words_per_minute": round(sum(word_counts) * 60 / duration, 4),
        "max_words_per_minute": round(max(paces), 4),
        "overlapping_segment_count": overlaps,
        "gapped_segment_count": gaps,
        "timing_basis": "AUTHOR_SUPPLIED_ESTIMATE",
        "script_similarity": "NOT_MEASURED",
        "artistic_verdict": "NOT_ASSIGNED",
    }


def analyze_image_metrics(source: Path) -> dict[str, Any]:
    """Bounded Pillow-based image statistics, not a creative quality score."""
    try:
        import PIL
        from PIL import Image, ImageStat
    except ImportError as exc:
        raise AVResearchError("RESEARCH_PILLOW_NOT_INSTALLED") from exc
    try:
        Image.MAX_IMAGE_PIXELS = 50_000_000
        with Image.open(source) as picture:
            width, height = picture.size
            if width < 1 or height < 1 or width * height > 50_000_000:
                raise AVResearchError("RESEARCH_IMAGE_PIXEL_LIMIT")
            fmt = str(picture.format or "unknown")
            has_alpha = "A" in picture.getbands()
            small = picture.copy()
            small.thumbnail((512, 512))
            grayscale = small.convert("L")
            stats = ImageStat.Stat(grayscale)
            brightness, contrast = stats.mean[0], stats.stddev[0]
            entropy = grayscale.entropy()
    except AVResearchError:
        raise
    except Exception as exc:
        raise AVResearchError("RESEARCH_IMAGE_DECODE_FAILED") from exc
    return {
        "schema": "HazewaveImageMeasurements/v1",
        "engine": "Pillow",
        "engine_version": str(PIL.__version__),
        "width": width, "height": height, "format": fmt,
        "has_alpha": has_alpha,
        "preview_max_dimension": 512,
        "mean_luma_8bit": round(brightness, 4),
        "luma_stddev_8bit": round(contrast, 4),
        "luma_entropy_bits": round(entropy, 4),
        "sampling_note": "Bounded thumbnail; not full-resolution quality analysis.",
        "artistic_verdict": "NOT_ASSIGNED",
    }


def _source_digest(source: Path) -> str:
    h = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_safe(path: Path, kind: str) -> tuple[Path, str]:
    p = Path(path).expanduser()
    try:
        info = p.lstat()
    except OSError as exc:
        raise AVResearchError("RESEARCH_SOURCE_NOT_REGULAR") from exc
    if not stat.S_ISREG(info.st_mode) or p.is_symlink():
        raise AVResearchError("RESEARCH_SOURCE_NOT_REGULAR")
    if info.st_size < 1 or info.st_size > 4 * 1024**3:
        raise AVResearchError("RESEARCH_SOURCE_SIZE_BLOCKED")
    if kind == "EDITORIAL_SCRIPT" and info.st_size > 2 * 1024 * 1024:
        raise AVResearchError("RESEARCH_EDITORIAL_INPUT_TOO_LARGE")
    return p.resolve(strict=True), _source_digest(p)


def _run_measurement(kind: str, source: Path) -> dict[str, Any]:
    try:
        if kind == "EDITORIAL_SCRIPT":
            return analyze_editorial_script(source)
        if kind == "IMAGE_METRICS":
            return analyze_image_metrics(source)
        if kind == "AUDIO_QC":
            from hazewave.audio_qc import analyze_audio_qc
            return analyze_audio_qc(source).to_dict()
        if kind == "AUDIO_MUSIC":
            from hazewave.audio_analysis import analyze_professional_audio
            return analyze_professional_audio(source).to_dict()
        if kind == "VIDEO_QC":
            from hazewave.video_qc import analyze_video_qc
            return analyze_video_qc(source).to_dict()
        if kind == "SCENE_DETECTION":
            from hazewave.scene_detection import detect_scenes
            return detect_scenes(source).to_dict()
    except AVResearchError:
        raise
    except Exception as exc:
        raise AVResearchError(f"RESEARCH_ANALYZER_FAILED:{kind}:{type(exc).__name__}") from exc
    raise AVResearchError(f"RESEARCH_KIND_UNSUPPORTED:{kind}")


def _write_receipt(report: dict[str, Any], state_root: Path) -> None:
    if state_root.is_symlink():
        raise AVResearchError("RESEARCH_STATE_ROOT_SYMLINK")
    destination = state_root / "av-research" / "receipts"
    if destination.parent.is_symlink() or destination.is_symlink():
        raise AVResearchError("RESEARCH_STATE_PATH_SYMLINK")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.chmod(0o700)
    name = f"{report['case_id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    output = destination / name
    payload = (json.dumps(report, allow_nan=False, sort_keys=True, ensure_ascii=False) + "\n").encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def run_authorized_study(
    *,
    source: Path,
    kind: str,
    case_id: str,
    grant_file: Path | None,
    signature_file: Path | None,
    trusted_signers_file: Path | None = None,
    state_root: Path | None = None,
) -> dict[str, Any]:
    specialist = research_specialist(kind)
    # File identity is checked before any subprocess, decoder or analysis.
    target, digest = _source_safe(Path(source), kind)
    if grant_file is None or signature_file is None:
        raise AVResearchError("RESEARCH_SIGNED_GRANT_REQUIRED")
    if trusted_signers_file is None:
        trusted_signers_file = Path.home() / ".config" / "hazewave" / "reverse-engineering" / "allowed_signers"
    from hazewave.reverse_engineering import verify_research_grant, ReverseEngineeringError
    from hazewave.harness import HazewaveTask, route_task, issue_authorization
    try:
        grant = verify_research_grant(
            grant_file=Path(grant_file), signature_file=Path(signature_file),
            target_file=target, allowed_signers_file=Path(trusted_signers_file),
            domain=specialist["domain"], target_kind=specialist["target_kind"],
            purpose="AUTHORIZED_FEATURE_STUDY",
        )
    except ReverseEngineeringError as exc:
        raise AVResearchError(f"RESEARCH_AUTHORIZATION_BLOCKED:{exc}") from exc
    if grant["target_sha256"] != digest:
        raise AVResearchError("RESEARCH_GRANT_DIGEST_MISMATCH")
    if not _ALLOWED_CASE.fullmatch(case_id):
        raise AVResearchError("RESEARCH_CASE_ID_INVALID")
    task = HazewaveTask(
        task_id=case_id, goal=f"Authorized research: {kind} {digest}",
        required_capability=specialist["capability"],
        requested_domain=specialist["domain"],
    )
    route = route_task(task)
    auth = issue_authorization(route)
    measurements = _run_measurement(kind, target)
    if _source_digest(target) != digest:
        raise AVResearchError("RESEARCH_SOURCE_CHANGED_DURING_ANALYSIS")
    report = compose_research_evidence(
        kind=kind, source_sha256=digest, grant_evidence=grant,
        measurements=measurements, case_id=case_id,
    )
    report["harness_route"] = {
        "domain": route.selected_domain,
        "capability": route.selected_capability,
        "authorization_id": auth.authorization_id,
        "authority": auth.authority,
        "execution_authorized": False,
    }
    _write_receipt(report, state_root or Path.home() / ".local" / "state" / "hazewave")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.av_research_lab")
    parser.add_argument("--kind", choices=tuple(KINDS), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--grant-file", type=Path, required=True)
    parser.add_argument("--signature-file", type=Path, required=True)
    parser.add_argument("--state-root", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_authorized_study(
            source=args.source, kind=args.kind, case_id=args.case_id,
            grant_file=args.grant_file, signature_file=args.signature_file,
            state_root=args.state_root,
        )
    except (AVResearchError, ValueError, PermissionError, OSError) as exc:
        print(f"HAZEWAVE_AV_RESEARCH=BLOCKED:{exc}", file=sys.stderr)
        return 20
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False))
    print("HAZEWAVE_AV_RESEARCH=EVIDENCE_RECORDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
