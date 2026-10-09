"""Private holdout acoustic retrieval and lossless incremental checkpoint growth.

Train receipts remain authoritative and are revalidated against original bytes.
A holdout is SHA-distinct, NOT verified to be composition-independent; labels,
music quality and the generative producer are deliberately not inferred.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from hazewave.haze_catalog import (
    CatalogError, _checked_owned_audio, _root_path, _sha_file, write_private_receipt,
)
from hazewave.haze_audio_learning import (
    AudioLearningError, _FEATURES, _HEX, _dist, _features, bootstrap_owner_memory,
)


def _sha_obj(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _model_prototypes(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(model, dict)
        or model.get("schema") not in (
            "HazeEarlyAudioLearning/v1", "HazeEarlyAudioLearning/v2"
        )
        or model.get("model_kind") != "NON_NEURAL_ACOUSTIC_RETRIEVAL_FIT"
        or model.get("training_started") is not True
        or model.get("generator_weights_updated") is not False
        or model.get("automatic_delete_authorized") is not False
        or model.get("reaper_changes") != 0
        or model.get("feature_names") != [field for field, _ in _FEATURES] + [
            "section_energy_variability"
        ]):
        raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
    means = model.get("feature_mean")
    scales = model.get("feature_scales")
    features = len(_FEATURES) + 1
    if (not isinstance(means, list) or not isinstance(scales, list)
        or len(means) != features or len(scales) != features):
        raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
    if any(type(n) not in (int, float) or not math.isfinite(float(n))
           for n in means):
        raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
    if any(type(n) not in (int, float) or not math.isfinite(float(n))
           or float(n) < .05 for n in scales):
        raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
    prototypes = model.get("learned_audio_prototypes")
    if (not isinstance(prototypes, list)
        or not 2 <= len(prototypes) <= 64
        or model.get("training_examples") != len(prototypes)):
        raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
    seen_ids: set[str] = set()
    seen_shas: set[str] = set()
    for proto in prototypes:
        if not isinstance(proto, dict):
            raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
        rel = proto.get("relative_path")
        digest = proto.get("source_sha256")
        expected = ("PATH_SHA256_V1:" + sha256(
            b"HAZE_ASSET_PATH_V1\0" + rel.encode("utf-8")
        ).hexdigest()) if isinstance(rel, str) else None
        vec = proto.get("fitted_acoustic_vector")
        if (not isinstance(digest, str) or not _HEX.fullmatch(digest)
            or proto.get("asset_id") != expected or not isinstance(vec, list)
            or len(vec) != features or any(type(n) not in (int, float)
                or not math.isfinite(float(n)) for n in vec)
            or expected in seen_ids or digest in seen_shas):
            raise AudioLearningError("PARENT_CHECKPOINT_INVALID")
        seen_ids.add(expected)
        seen_shas.add(digest)
    return prototypes


def _verify_receipt(receipt: Mapping[str, Any], root: Path) -> tuple[float, ...]:
    if (not isinstance(receipt, dict)
        or receipt.get("schema") != "HazeAudioListenReceipt/v1"
        or receipt.get("analyzer") != "REAL_FFMPEG_WITH_EXISTING_REFERENCE_PROFILE"):
        raise AudioLearningError("LISTEN_RECEIPT_INVALID")
    rel = receipt.get("relative_path")
    digest = receipt.get("source_sha256")
    if not isinstance(rel, str) or not isinstance(digest, str) or not _HEX.fullmatch(digest):
        raise AudioLearningError("LISTEN_RECEIPT_INVALID")
    expected_id = "PATH_SHA256_V1:" + sha256(
        b"HAZE_ASSET_PATH_V1\0" + rel.encode("utf-8")
    ).hexdigest()
    if receipt.get("asset_id") != expected_id:
        raise AudioLearningError("LISTEN_RECEIPT_INVALID")
    p = receipt.get("acoustic_profile")
    if not isinstance(p, dict) or p.get("source_sha256") != digest:
        raise AudioLearningError("ACOUSTIC_SHA_MISMATCH")
    try:
        source = _checked_owned_audio(root, rel)
    except CatalogError as exc:
        raise AudioLearningError("HOLDOUT_UNOWNED_SOURCE") from exc
    if _sha_file(source) != digest:
        raise AudioLearningError("SOURCE_SHA_MISMATCH")
    return _features(p)


def probe_unseen(
    memory: Mapping[str, Any],
    receipt: Mapping[str, Any], *,
    root: Path | str,
) -> dict[str, Any]:
    """Compare an unseen SHA-distinct source against a FROZEN fitted model."""
    source = _root_path(root)
    prototypes = _model_prototypes(memory)
    digest = receipt.get("source_sha256") if isinstance(receipt, dict) else None
    if digest in {x["source_sha256"] for x in prototypes}:
        raise AudioLearningError("HOLDOUT_SOURCE_ALREADY_TRAINED")
    vector = _verify_receipt(receipt, source)
    means = memory["feature_mean"]
    scales = memory["feature_scales"]
    norm = tuple((v - m) / s for v, m, s in zip(vector, means, scales))
    close = sorted(
        (_dist(norm, p["fitted_acoustic_vector"]), p["source_sha256"])
        for p in prototypes
    )
    score, nearest = close[0]
    return {
        "schema": "HazeAcousticHoldoutProbe/v1",
        "training_examples": len(prototypes),
        "query_sha256": digest,
        "nearest_training_sha256": nearest,
        "acoustic_distance": round(score, 7),
        "source_unseen_by_sha256": True,
        "composition_independence_verified": False,
        "style_prediction": None,
        "quality_prediction": None,
        "generator_weights_updated": False,
        "generation_authorized": False,
        "no_model_fitting_on_probe": True,
        "reaper_changes": 0,
        "automatic_delete_authorized": False,
        "authority": "NONE",
    }


def grow_early_memory(
    memory: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]], *,
    root: Path | str, authorized_training: bool,
) -> dict[str, Any]:
    """Read-only verified replay + append one or more sources into NEW model.

    Never mutates old memory; caller must write to a new, exclusive path.
    Holdout probes are computed *before* refitting so no new source leaks.
    """
    if authorized_training is not True:
        raise AudioLearningError("FEATURE_LEARNING_NOT_AUTHORIZED")
    source_root = _root_path(root)
    existing = _model_prototypes(memory)
    if not isinstance(receipts, (list, tuple)) or not 2 <= len(receipts) <= 64:
        raise AudioLearningError("PARENT_SOURCES_INCOMPLETE")
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise AudioLearningError("LISTEN_RECEIPT_INVALID")
        key = (receipt.get("relative_path"), receipt.get("source_sha256"))
        if key in by_key:
            raise AudioLearningError("LISTEN_RECEIPT_DUPLICATE")
        by_key[key] = receipt
    prior = []
    for proto in existing:
        key = (proto["relative_path"], proto["source_sha256"])
        if key not in by_key:
            raise AudioLearningError("PARENT_SOURCES_INCOMPLETE")
        prior.append(by_key.pop(key))
    if not by_key:
        raise AudioLearningError("NO_NEW_AUDIO_EVIDENCE")
    replay = bootstrap_owner_memory(prior, root=source_root, authorized_training=True)
    # Parent metadata, fitted scaling and all asset prototypes must match an
    # independent replay from authenticated source recordings.
    for field in ("feature_mean", "feature_scales", "learned_audio_prototypes"):
        if replay[field] != memory[field]:
            raise AudioLearningError("PARENT_CHECKPOINT_MISMATCH")
    fresh = list(by_key.values())
    probes = [probe_unseen(memory, receipt, root=source_root) for receipt in fresh]
    trained = bootstrap_owner_memory(
        prior + fresh, root=source_root, authorized_training=True,
    )
    model = {**trained}
    model.update({
        "schema": "HazeEarlyAudioLearning/v2",
        "memory_revision": int(memory.get("memory_revision", 1)) + 1,
        "parent_checkpoint_sha256": _sha_obj(memory),
        "parent_checkpoint_schema": memory["schema"],
        "previous_training_examples": len(existing),
        "new_training_examples": len(fresh),
        "preupdate_holdout_probes": probes,
        "composition_independence_verified": False,
        "heldout_examples": 0,
        "evaluation_status": "PROBE_BEFORE_FIT_NOT_GENRE_ACCURACY",
        "style_labels_inferred": False,
        "automatic_delete_authorized": False,
        "generator_weights_updated": False,
        "producer_competence_proven": False,
        "prior_memory_unchanged": True,
    })
    return model


def _private_json(path: Path, root: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise AudioLearningError("PRIVATE_INPUT_SYMLINK_FORBIDDEN")
    file = path.expanduser().resolve(strict=True)
    if file.is_relative_to(root) or not file.is_file() or file.stat().st_size > 1000000:
        raise AudioLearningError("PRIVATE_INPUT_INVALID")
    for ancestor in (file.parent, *file.parent.parents):
        if ancestor.name == ".git" or (ancestor / ".git").exists():
            raise AudioLearningError("PRIVATE_INPUT_IN_GIT_REPOSITORY")
    result = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise AudioLearningError("PRIVATE_INPUT_INVALID")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.haze_incremental_learning")
    parser.add_argument("command", choices=("probe", "grow"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--receipt", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-private-corpus", action="store_true")
    parser.add_argument("--allow-feature-learning", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.allow_private_corpus:
            raise AudioLearningError("PRIVATE_CORPUS_NOT_AUTHORIZED")
        root = _root_path(args.root)
        parent = _private_json(args.prior, root)
        if not 1 <= len(args.receipt) <= 64:
            raise AudioLearningError("INPUT_COUNT_INVALID")
        all_receipts = [_private_json(path, root) for path in args.receipt]
        if args.command == "probe":
            if len(all_receipts) != 1:
                raise AudioLearningError("HOLDOUT_RECEIPT_COUNT_INVALID")
            result = probe_unseen(parent, all_receipts[0], root=root)
        else:
            result = grow_early_memory(
                parent, all_receipts, root=root,
                authorized_training=args.allow_feature_learning,
            )
        write_private_receipt(result, args.output, source_root=root)
    except (AudioLearningError, CatalogError, OSError, TypeError, ValueError,
            json.JSONDecodeError, OverflowError) as exc:
        print("HAZE_INCREMENTAL=BLOCKED:" + type(exc).__name__)
        return 20
    print("HAZE_INCREMENTAL=PRIVATE_RECEIPT_WRITTEN")
    print("RESULT_SCHEMA=" + result["schema"])
    print("GENERATOR_FINETUNE=NOT_STARTED")
    print("REAPER_PROJECT_CHANGED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
