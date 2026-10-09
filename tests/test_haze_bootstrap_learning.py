"""V1 cold-start learning from authentic private listening receipts.

Every source stays independent, regardless of repeated generated filenames.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import copy

import pytest

from hazewave.haze_audio_learning import (
    AudioLearningError, bootstrap_owner_memory,
)


def _receipts(root: Path):
    samples = [
        ("folder A/Repetido.mp3", b"different original mix: A", .12),
        ("folder B/Repetido.mp3", b"different original mix: B", .20),
        ("folder C/Track 1.mp3", b"different original mix: C", .27),
        ("folder D/Track 2.mp3", b"different original mix: D", .49),
    ]
    results = []
    originals = {}
    for name, contents, bass in samples:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        originals[path] = contents
        digest = sha256(contents).hexdigest()
        results.append({
            "schema": "HazeAudioListenReceipt/v1",
            "relative_path": name,
            "source_sha256": digest,
            "asset_id": "PATH_SHA256_V1:" + sha256(
                b"HAZE_ASSET_PATH_V1\0" + name.encode()
            ).hexdigest(),
            "analyzer": "REAL_FFMPEG_WITH_EXISTING_REFERENCE_PROFILE",
            "acoustic_profile": {
                "schema": "ReferenceProfile/v1",
                "source_sha256": digest,
                "integrated_lufs": -13.0 - bass,
                "loudness_range_lu": 8.0,
                "true_peak_dbfs": -2.0,
                "crest_factor_ratio": 4.0,
                "low_energy_ratio": bass,
                "mid_energy_ratio": .6 - bass,
                "high_energy_ratio": .4,
                "stereo_correlation": .7,
                "stereo_side_energy_ratio": .12,
                "transient_density_per_second": .4,
                "section_energy_dbfs": [-15.0, -13.5, -14.1],
            },
        })
    return results, originals


def test_bootstrap_really_fits_weights_and_keeps_every_original(tmp_path):
    root = tmp_path / "private_corpus"
    root.mkdir()
    receipts, originals = _receipts(root)
    before = copy.deepcopy(receipts)
    with pytest.raises(AudioLearningError, match="FEATURE_LEARNING_NOT_AUTHORIZED"):
        bootstrap_owner_memory(receipts, root=root, authorized_training=False)
    model = bootstrap_owner_memory(receipts, root=root, authorized_training=True)
    assert model["schema"] == "HazeEarlyAudioLearning/v1"
    assert model["model_kind"] == "NON_NEURAL_ACOUSTIC_RETRIEVAL_FIT"
    assert model["training_started"] is True
    assert model["training_examples"] == 4
    assert model["independent_source_count"] == 4
    assert model["heldout_examples"] == 0
    assert model["style_labels_inferred"] is False
    assert model["generator_weights_updated"] is False
    assert model["producer_competence_proven"] is False
    assert model["name_based_deduplication"] is False
    assert model["automatic_delete_authorized"] is False
    assert len(model["feature_mean"]) == len(model["feature_scales"]) == 11
    assert len(model["learned_audio_prototypes"]) == 4
    assert {p["source_sha256"] for p in model["learned_audio_prototypes"]} == {
        x["source_sha256"] for x in receipts
    }
    assert receipts == before
    assert all(p.read_bytes() == content for p, content in originals.items())
    assert model["nearest_acoustic_neighbours"]
    assert all(row["source_sha256"] != row["neighbour_sha256"]
               for row in model["nearest_acoustic_neighbours"])


def test_bootstrap_learns_different_weights_when_audio_features_change(tmp_path):
    root = tmp_path / "private_corpus"
    root.mkdir()
    receipts, _ = _receipts(root)
    original = bootstrap_owner_memory(receipts, root=root, authorized_training=True)
    changed = copy.deepcopy(receipts)
    changed[-1]["acoustic_profile"]["low_energy_ratio"] = .8
    changed[-1]["acoustic_profile"]["mid_energy_ratio"] = .05
    updated = bootstrap_owner_memory(changed, root=root, authorized_training=True)
    assert original["feature_mean"] != updated["feature_mean"]


def test_bootstrap_fail_closed_on_changed_original_and_forged_receipt(tmp_path):
    root = tmp_path / "private_corpus"
    root.mkdir()
    receipts, _ = _receipts(root)
    corrupted = copy.deepcopy(receipts)
    corrupted[0]["source_sha256"] = "0" * 64
    with pytest.raises(AudioLearningError, match="ACOUSTIC_SHA_MISMATCH"):
        bootstrap_owner_memory(corrupted, root=root, authorized_training=True)
    song = root / receipts[0]["relative_path"]
    song.write_bytes(b"content modified on disk")
    with pytest.raises(AudioLearningError, match="SOURCE_SHA_MISMATCH"):
        bootstrap_owner_memory(receipts, root=root, authorized_training=True)


def test_bootstrap_rejects_duplicate_bytes_without_deleting_or_moving_files(tmp_path):
    root = tmp_path / "private_corpus"
    root.mkdir()
    receipts, _ = _receipts(root)
    src = root / receipts[0]["relative_path"]
    dest = root / receipts[1]["relative_path"]
    dest.write_bytes(src.read_bytes())
    duplicate = copy.deepcopy(receipts)
    duplicate[1]["source_sha256"] = duplicate[0]["source_sha256"]
    duplicate[1]["acoustic_profile"]["source_sha256"] = duplicate[0]["source_sha256"]
    with pytest.raises(AudioLearningError, match="INDEPENDENT_SOURCE_REQUIRED"):
        bootstrap_owner_memory(duplicate, root=root, authorized_training=True)
    assert src.is_file() and dest.is_file()
    assert src.read_bytes() == dest.read_bytes()


def test_bootstrap_blocks_path_traversal_and_insufficient_evidence(tmp_path):
    root = tmp_path / "private_corpus"
    root.mkdir()
    receipts, _ = _receipts(root)
    with pytest.raises(AudioLearningError, match="BOOTSTRAP_INSUFFICIENT_SOURCES"):
        bootstrap_owner_memory(receipts[:1], root=root, authorized_training=True)
    tampered = copy.deepcopy(receipts)
    tampered[0]["relative_path"] = "../other.mp3"
    with pytest.raises(AudioLearningError, match="BOOTSTRAP_UNOWNED_SOURCE"):
        bootstrap_owner_memory(tampered, root=root, authorized_training=True)
