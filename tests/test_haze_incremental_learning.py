"""Proof of cold-start growth: evaluate unseen recordings before adding them.

No title merging, no re-writing old checkpoints, no training/test leakage.
"""
from __future__ import annotations

import copy
import hashlib
import math
import struct
import wave
from pathlib import Path

import pytest

from hazewave.haze_audio_learning import AudioLearningError, bootstrap_owner_memory, listen_audio
from hazewave.haze_incremental_learning import probe_unseen, grow_early_memory


def _receipt(root: Path, folder: str, contents: bytes, bass: float):
    rel = f"{folder}/Repeated Generated Title.mp3"
    file = root / rel
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(contents)
    digest = hashlib.sha256(contents).hexdigest()
    asset_id = "PATH_SHA256_V1:" + hashlib.sha256(
        b"HAZE_ASSET_PATH_V1\0" + rel.encode()
    ).hexdigest()
    return {
        "schema": "HazeAudioListenReceipt/v1",
        "relative_path": rel,
        "asset_id": asset_id,
        "source_sha256": digest,
        "analyzer": "REAL_FFMPEG_WITH_EXISTING_REFERENCE_PROFILE",
        "acoustic_profile": {
            "schema": "ReferenceProfile/v1", "source_sha256": digest,
            "integrated_lufs": -13.0, "loudness_range_lu": 8.0,
            "true_peak_dbfs": -2.0, "crest_factor_ratio": 3.0,
            "low_energy_ratio": bass, "mid_energy_ratio": .7 - bass,
            "high_energy_ratio": .3, "stereo_correlation": .8,
            "stereo_side_energy_ratio": .10, "transient_density_per_second": .6,
            "section_energy_dbfs": [-15.0, -14.0, -13.5, -14.5],
        },
    }


def _five(root: Path):
    receipts = [
        _receipt(root, str(n), f"independent composition {n}".encode(), .1 * n)
        for n in range(1, 6)
    ]
    return receipts, bootstrap_owner_memory(
        receipts[:4], root=root, authorized_training=True
    )


def test_compare_an_unseen_audio_without_fitting_it_or_assigning_genre(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    receipts, parent = _five(root)
    old = copy.deepcopy(parent)
    report = probe_unseen(parent, receipts[4], root=root)
    assert report["schema"] == "HazeAcousticHoldoutProbe/v1"
    assert report["training_examples"] == 4
    assert report["query_sha256"] == receipts[4]["source_sha256"]
    assert report["nearest_training_sha256"] in {
        r["source_sha256"] for r in receipts[:4]
    }
    assert report["acoustic_distance"] >= 0
    assert report["source_unseen_by_sha256"] is True
    assert report["composition_independence_verified"] is False
    assert report["style_prediction"] is None
    assert report["generation_authorized"] is False
    assert parent == old


def test_no_leakage_from_identical_bytes_different_names(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    receipts, parent = _five(root)
    duplicate = copy.deepcopy(receipts[4])
    duplicate["source_sha256"] = receipts[0]["source_sha256"]
    duplicate["acoustic_profile"]["source_sha256"] = receipts[0]["source_sha256"]
    (root / duplicate["relative_path"]).write_bytes(
        (root / receipts[0]["relative_path"]).read_bytes()
    )
    with pytest.raises(AudioLearningError, match="HOLDOUT_SOURCE_ALREADY_TRAINED"):
        probe_unseen(parent, duplicate, root=root)
    assert (root / duplicate["relative_path"]).exists()


def test_add_new_audio_preserves_all_four_old_assets_and_checkpoint(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    receipts, parent = _five(root)
    original_parent = copy.deepcopy(parent)
    originals = {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*.mp3")
    }
    next_model = grow_early_memory(
        parent, receipts, root=root, authorized_training=True
    )
    assert next_model["schema"] == "HazeEarlyAudioLearning/v2"
    assert next_model["training_examples"] == 5
    assert next_model["previous_training_examples"] == 4
    assert next_model["new_training_examples"] == 1
    assert next_model["memory_revision"] == 2
    assert next_model["parent_checkpoint_sha256"] == hashlib.sha256(
        __import__("json").dumps(
            parent, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert len(next_model["learned_audio_prototypes"]) == 5
    assert {
        x["source_sha256"] for x in parent["learned_audio_prototypes"]
    }.issubset({
        x["source_sha256"] for x in next_model["learned_audio_prototypes"]
    })
    assert next_model["preupdate_holdout_probes"][0]["query_sha256"] == receipts[4]["source_sha256"]
    assert next_model["heldout_examples"] == 0
    assert next_model["style_labels_inferred"] is False
    assert next_model["generator_weights_updated"] is False
    assert next_model["automatic_delete_authorized"] is False
    assert original_parent == parent
    assert {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*.mp3")
    } == originals


def test_grow_rejects_missing_parent_receipt_and_unapproved_training(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    receipts, parent = _five(root)
    with pytest.raises(AudioLearningError, match="FEATURE_LEARNING_NOT_AUTHORIZED"):
        grow_early_memory(parent, receipts, root=root, authorized_training=False)
    with pytest.raises(AudioLearningError, match="PARENT_SOURCES_INCOMPLETE"):
        grow_early_memory(parent, receipts[1:], root=root, authorized_training=True)
    with pytest.raises(AudioLearningError, match="NO_NEW_AUDIO_EVIDENCE"):
        grow_early_memory(parent, receipts[:4], root=root, authorized_training=True)
    tampered = copy.deepcopy(parent)
    tampered["feature_mean"][0] += .25
    with pytest.raises(AudioLearningError, match="PARENT_CHECKPOINT_MISMATCH"):
        grow_early_memory(tampered, receipts, root=root, authorized_training=True)


def test_grow_can_continue_from_v2_without_overwriting_v1(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    receipts, parent = _five(root)
    second = grow_early_memory(parent, receipts, root=root, authorized_training=True)
    sixth = _receipt(root, "6", b"sixth distinct composition", .62)
    third = grow_early_memory(
        second, receipts + [sixth], root=root, authorized_training=True
    )
    assert third["memory_revision"] == 3
    assert third["training_examples"] == 6
    assert third["new_training_examples"] == 1
    assert second["training_examples"] == 5
    assert parent["training_examples"] == 4
    assert second["parent_checkpoint_sha256"] != third["parent_checkpoint_sha256"]


def test_real_waveform_out_of_sample_probe_end_to_end(tmp_path):
    root = tmp_path / "owned_corpus"
    root.mkdir()
    records = []
    for i in range(5):
        rel = f"composer-{i}/Repeated Title.wav"
        path = root / rel
        path.parent.mkdir(parents=True)
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            samples = b"".join(
                struct.pack("<hh", v, v)
                for k in range(48000)
                for v in [round(.18 * math.sin(2 * math.pi * (100 + i * 300) * k / 48000) * 32767)]
            )
            stream.writeframes(samples)
        records.append(listen_audio(root, rel, authorized=True))
    old = bootstrap_owner_memory(records[:4], root=root, authorized_training=True)
    report = probe_unseen(old, records[4], root=root)
    assert report["source_unseen_by_sha256"] is True
    updated = grow_early_memory(old, records, root=root, authorized_training=True)
    assert updated["training_examples"] == 5
    assert updated["generator_weights_updated"] is False
