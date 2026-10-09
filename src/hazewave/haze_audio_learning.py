"""Private, CPU-bounded listening and owner-approved style feature learning.

This is *not* a music generator, song reconstruction, automatic producer,
neural fine-tuning, or a grant to alter REAPER. Audio bytes remain local.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any, Mapping, Sequence

from hazewave.haze_catalog import (
    CatalogError, _bounded_pcm_decoder, _checked_owned_audio, _root_path,
    write_private_receipt,
)
from hazewave.reference_profile import ReferenceProfileError, build_reference_profile


class AudioLearningError(RuntimeError):
    pass


_HEX = re.compile(r"^[0-9a-f]{64}$")
# Fixed, documented physical-unit scaling; no held-out data enter fitting.
_FEATURES = (
    ("integrated_lufs", 12.0),
    ("loudness_range_lu", 12.0),
    ("true_peak_dbfs", 6.0),
    ("crest_factor_ratio", 8.0),
    ("low_energy_ratio", .35),
    ("mid_energy_ratio", .35),
    ("high_energy_ratio", .35),
    ("stereo_correlation", 1.0),
    ("stereo_side_energy_ratio", .4),
    ("transient_density_per_second", 3.0),
)
_TARGETS = ("integrated_lufs", "loudness_range_lu", "true_peak_dbfs",
            "low_energy_ratio", "mid_energy_ratio", "high_energy_ratio",
            "stereo_side_energy_ratio", "transient_density_per_second")


def listen_audio(
    root: Path | str, relative_path: str, *, authorized: bool,
) -> dict[str, Any]:
    """Really decode the *authorized private copy* with FFmpeg.

    The middle excerpt is limited to 30s for timbral/stereo features; full
    program is analyzed for loudness. No bytes of the source are modified.
    """
    if authorized is not True:
        raise AudioLearningError("PRIVATE_LISTEN_NOT_AUTHORIZED")
    try:
        source = _root_path(root)
        path = _checked_owned_audio(source, relative_path)
        before = path.stat()
        profile = build_reference_profile(
            path, authorized=True, pcm_decoder=_bounded_pcm_decoder,
            section_count=8,
        )
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino
        ):
            raise AudioLearningError("SOURCE_CHANGED_DURING_LISTEN")
    except (CatalogError, ReferenceProfileError) as exc:
        raise AudioLearningError(f"PRIVATE_LISTEN_FAILED:{exc}") from exc
    details = profile.to_dict()
    details.pop("source_path", None)
    return {
        "schema": "HazeAudioListenReceipt/v1",
        "source_sha256": profile.source_sha256,
        "asset_id": "PATH_SHA256_V1:" + sha256(
            b"HAZE_ASSET_PATH_V1\0" + relative_path.encode("utf-8")
        ).hexdigest(),
        "relative_path": relative_path,
        "acoustic_profile": details,
        "analyzer": "REAL_FFMPEG_WITH_EXISTING_REFERENCE_PROFILE",
        "spectral_scope": "MIDDLE_EXCERPT_MAX_30_SECONDS",
        "loudness_scope": "COMPLETE_SOURCE",
        "owner_genre": None,
        "training_started": False,
        "generator_weights_updated": False,
        "source_audio_exported": False,
        "original_modified": False,
        "reaper_changes": 0,
        "owner_review_required": True,
    }


def _features(profile: Mapping[str, Any]) -> tuple[float, ...]:
    if not isinstance(profile, dict) or profile.get("schema") != "ReferenceProfile/v1":
        raise AudioLearningError("ACOUSTIC_PROFILE_SCHEMA_INVALID")
    values = []
    for field, scale in _FEATURES:
        value = profile.get(field)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise AudioLearningError("FEATURE_INVALID")
        number = float(value)
        if not math.isfinite(number) or abs(number) > 1_000:
            raise AudioLearningError("FEATURE_INVALID")
        if field in ("low_energy_ratio", "mid_energy_ratio",
                     "high_energy_ratio", "stereo_side_energy_ratio") and not 0 <= number <= 1:
            raise AudioLearningError("FEATURE_INVALID")
        if field == "stereo_correlation" and not -1 <= number <= 1:
            raise AudioLearningError("FEATURE_INVALID")
        if field in ("loudness_range_lu", "crest_factor_ratio",
                     "transient_density_per_second") and number < 0:
            raise AudioLearningError("FEATURE_INVALID")
        values.append(number / scale)
    sections = profile.get("section_energy_dbfs")
    if not isinstance(sections, (list, tuple)) or not 2 <= len(sections) <= 128:
        raise AudioLearningError("FEATURE_INVALID")
    if any(type(v) not in (int, float) or not math.isfinite(float(v))
           or abs(float(v)) > 1000 for v in sections):
        raise AudioLearningError("FEATURE_INVALID")
    values.append(statistics.pstdev(float(v) for v in sections) / 12.)
    return tuple(values)


def _centroid(points: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(statistics.mean(x[i] for x in points)
                 for i in range(len(points[0])))


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((v - w) ** 2 for v, w in zip(a, b)))


def train_style_memory(
    curated: Mapping[str, Any], *, authorized_training: bool,
) -> dict[str, Any]:
    """Fit real numeric centroids to trusted audio measurements; hold out one
    distinct audio SHA per owner-defined style. Not neural audio fine-tuning.
    """
    if authorized_training is not True:
        raise AudioLearningError("FEATURE_LEARNING_NOT_AUTHORIZED")
    if not isinstance(curated, dict) or curated.get("schema") != "HazeCuratedStyleMemory/v1":
        raise AudioLearningError("CURATION_SCHEMA_INVALID")
    refs = curated.get("references")
    if not isinstance(refs, list) or not 6 <= len(refs) <= 5000:
        raise AudioLearningError("MULTI_STYLE_HOLDOUT_REQUIRED")
    if curated.get("reference_count") != len(refs):
        raise AudioLearningError("CURATION_COUNT_MISMATCH")

    grouped: dict[str, list[tuple[str, tuple[float, ...], dict[str, Any]]]] = defaultdict(list)
    seen_digests: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            raise AudioLearningError("CURATION_REFERENCE_INVALID")
        if ref.get("status") != "OWNER_REFERENCE_APPROVED_NOT_A_MODEL_TRAINING_GRANT":
            raise AudioLearningError("OWNER_REFERENCE_NOT_APPROVED")
        digest = ref.get("source_sha256")
        if not isinstance(digest, str) or not _HEX.fullmatch(digest):
            raise AudioLearningError("SOURCE_DIGEST_INVALID")
        profile = ref.get("acoustic_profile")
        if not isinstance(profile, dict) or profile.get("source_sha256") != digest:
            raise AudioLearningError("ACOUSTIC_SHA_MISMATCH")
        genre = ref.get("owner_genre")
        if not isinstance(genre, str) or not genre.strip() or len(genre) > 120:
            raise AudioLearningError("OWNER_STYLE_REQUIRED")
        genre = genre.strip()
        if digest in seen_digests:
            # Reject training leakage, without deleting or merging source
            # *assets*, which remain separate in the master catalog.
            raise AudioLearningError("INDEPENDENT_SOURCE_REQUIRED")
        seen_digests.add(digest)
        vector = _features(profile)
        grouped[genre].append((digest, vector, ref))
    if len(grouped) < 2 or any(len(group) < 3 for group in grouped.values()):
        raise AudioLearningError("MULTI_STYLE_HOLDOUT_REQUIRED")

    training: dict[str, list[tuple[str, tuple[float, ...], dict[str, Any]]]] = {}
    heldout: list[tuple[str, str, tuple[float, ...]]] = []
    for style, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: row[0])
        training[style] = ordered[:-1]
        heldout.append((style, ordered[-1][0], ordered[-1][1]))

    centers = {style: _centroid([row[1] for row in rows])
               for style, rows in training.items()}
    predictions = []
    for true_style, digest, vector in heldout:
        choices = sorted(
            ((style, _dist(vector, centroid)) for style, centroid in centers.items()),
            key=lambda entry: (entry[1], entry[0]),
        )
        predictions.append({
            "source_sha256": digest,
            "expected_owner_style": true_style,
            "predicted_style": choices[0][0],
            "match": choices[0][0] == true_style,
            "nearest_distance": round(choices[0][1], 6),
        })
    correct = sum(int(p["match"]) for p in predictions)
    trained_count = sum(map(len, training.values()))
    centers_output = []
    for style, rows in sorted(training.items()):
        acoustic_targets = {}
        for target in _TARGETS:
            acoustic_targets[target] = round(
                statistics.median(float(row[2]["acoustic_profile"][target])
                                  for row in rows), 5
            )
        centers_output.append({
            "owner_genre": style,
            "training_example_count": len(rows),
            "centroid_vector": [round(v, 7) for v in centers[style]],
            "observed_training_medians": acoustic_targets,
            "setpoints_are_descriptive_not_mastering_targets": True,
        })
    return {
        "schema": "HazeOwnerStyleLearning/v1",
        "model_kind": "NON_NEURAL_AUDIO_FEATURE_CENTROIDS",
        "model_features": [name for name, _ in _FEATURES] + ["section_energy_variability"],
        "source_asset_count": len(refs),
        "unique_sha256_count": len(seen_digests),
        "training_examples": trained_count,
        "heldout_examples": len(heldout),
        "heldout_accuracy": correct / len(heldout),
        "heldout_predictions": predictions,
        "holdout_protection": "BY_SHA256_ONLY_COMPOSITION_FAMILY_UNVERIFIED",
        "style_centroids": centers_output,
        "style_evidence": "EXPLORATORY_FEATURE_LEARNING_NEEDS_HUMAN_BLIND_EVALUATION",
        "name_based_deduplication": False,
        "automatic_delete_authorized": False,
        "training_started": True,
        "generator_weights_updated": False,
        "generative_training": "NOT_STARTED",
        "original_audio_modified": False,
        "private_audio_exported": False,
        "reaper_changes": 0,
        "producer_competence_proven": False,
        "human_approval_required_for_production": True,
        "authority": "NONE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.haze_audio_learning")
    parser.add_argument("command", choices=("listen", "learn"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--relative-path", type=str)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--allow-private-corpus", action="store_true")
    parser.add_argument("--allow-feature-learning", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "listen":
            if not args.relative_path:
                raise AudioLearningError("LISTEN_PATH_REQUIRED")
            result = listen_audio(
                args.root, args.relative_path,
                authorized=args.allow_private_corpus,
            )
        else:
            if args.input is None:
                raise AudioLearningError("CURATED_MEMORY_REQUIRED")
            if not args.allow_private_corpus:
                raise AudioLearningError("PRIVATE_CORPUS_NOT_AUTHORIZED")
            # Input must be private and outside the original media root.
            root = _root_path(args.root)
            source = args.input.expanduser().resolve(strict=True)
            if source.is_relative_to(root):
                raise AudioLearningError("CURATED_RECEIPT_INSIDE_MEDIA")
            for ancestor in (source.parent, *source.parent.parents):
                if (ancestor / ".git").exists() or ancestor.name == ".git":
                    raise AudioLearningError("CURATED_RECEIPT_INSIDE_REPOSITORY")
            curated = json.loads(source.read_text(encoding="utf-8"))
            result = train_style_memory(
                curated, authorized_training=args.allow_feature_learning,
            )
        write_private_receipt(result, args.output, source_root=args.root)
    except (AudioLearningError, CatalogError, ReferenceProfileError,
            OSError, ValueError, json.JSONDecodeError) as exc:
        # Do not spill private filenames to log.
        print(f"HAZE_AUDIO_LEARNING=BLOCKED:{type(exc).__name__}")
        return 20
    print("HAZE_AUDIO_LEARNING=PRIVATE_RECEIPT_WRITTEN")
    print(f"RESULT_SCHEMA={result['schema']}")
    print("GENERATOR_FINE_TUNING=NOT_STARTED")
    print("REAPER_PROJECT_CHANGED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
