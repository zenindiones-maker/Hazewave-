"""Tests for actual acoustic listening and explicit, held-out style-feature learning."""
from __future__ import annotations

import hashlib
import math
import shutil
import struct
import wave

import pytest

from hazewave.haze_audio_learning import AudioLearningError, listen_audio, train_style_memory


def _approved(genre: str, i: int, *, bass: float, sha: str | None = None):
    digest = sha or hashlib.sha256(f"{genre}-{i}".encode()).hexdigest()
    return {
        "relative_path": f"{genre}/Same Generated Title ({i}).wav",
        "source_sha256": digest,
        "owner_genre": genre,
        "reference_role": "MIX_REFERENCE",
        "status": "OWNER_REFERENCE_APPROVED_NOT_A_MODEL_TRAINING_GRANT",
        "acoustic_profile": {
            "schema": "ReferenceProfile/v1",
            "source_sha256": digest,
            "integrated_lufs": -14.0 + i * .1,
            "loudness_range_lu": 8.0,
            "true_peak_dbfs": -2.0,
            "crest_factor_ratio": 4.0,
            "low_energy_ratio": bass,
            "mid_energy_ratio": 0.6 - bass,
            "high_energy_ratio": 0.4,
            "stereo_correlation": 0.7,
            "stereo_side_energy_ratio": 0.12,
            "transient_density_per_second": 0.4,
            "section_energy_dbfs": [-15., -14., -13., -14.],
        },
    }


def _dataset():
    references = [
        _approved("bass-heavy", i, bass=.48 + i * .004)
        for i in range(4)
    ] + [
        _approved("mid-heavy", i, bass=.08 + i * .004)
        for i in range(4)
    ]
    return {
        "schema": "HazeCuratedStyleMemory/v1",
        "reference_count": len(references),
        "references": references,
    }


def test_style_learner_really_fits_independent_genres_and_holds_out_audio():
    records = _dataset()
    with pytest.raises(AudioLearningError, match="FEATURE_LEARNING_NOT_AUTHORIZED"):
        train_style_memory(records, authorized_training=False)
    model = train_style_memory(records, authorized_training=True)
    assert model["schema"] == "HazeOwnerStyleLearning/v1"
    assert model["training_examples"] == 6
    assert model["heldout_examples"] == 2
    assert model["heldout_accuracy"] == 1.0
    assert {c["owner_genre"] for c in model["style_centroids"]} == {
        "bass-heavy", "mid-heavy",
    }
    assert model["training_started"] is True
    assert model["model_kind"] == "NON_NEURAL_AUDIO_FEATURE_CENTROIDS"
    assert model["generator_weights_updated"] is False
    assert model["reaper_changes"] == 0
    assert model["automatic_delete_authorized"] is False
    assert model["producer_competence_proven"] is False


def test_style_learner_does_not_merge_identical_titles_or_duplicate_audio_bytes():
    dataset = _dataset()
    original_paths = [r["relative_path"] for r in dataset["references"]]
    assert len({path.rsplit("/", 1)[-1] for path in original_paths}) == 4
    result = train_style_memory(dataset, authorized_training=True)
    assert result["source_asset_count"] == 8
    assert result["name_based_deduplication"] is False
    assert [r["relative_path"] for r in dataset["references"]] == original_paths
    duplicate = _dataset()
    duplicate["references"][2]["source_sha256"] = duplicate["references"][0]["source_sha256"]
    duplicate["references"][2]["acoustic_profile"]["source_sha256"] = duplicate["references"][0]["source_sha256"]
    with pytest.raises(AudioLearningError, match="INDEPENDENT_SOURCE_REQUIRED"):
        train_style_memory(duplicate, authorized_training=True)


def test_style_learner_rejects_forged_acoustic_profile_and_insufficient_labels():
    dataset = _dataset()
    dataset["references"][0]["acoustic_profile"]["source_sha256"] = "0" * 64
    with pytest.raises(AudioLearningError, match="ACOUSTIC_SHA_MISMATCH"):
        train_style_memory(dataset, authorized_training=True)
    single = _dataset()
    single["references"] = single["references"][:4]
    with pytest.raises(AudioLearningError, match="MULTI_STYLE_HOLDOUT_REQUIRED"):
        train_style_memory(single, authorized_training=True)
    invalid = _dataset()
    invalid["references"][0]["acoustic_profile"]["integrated_lufs"] = float("nan")
    with pytest.raises(AudioLearningError, match="FEATURE_INVALID"):
        train_style_memory(invalid, authorized_training=True)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFMPEG_REQUIRED")
def test_real_waveform_listen_decodes_ffmpeg_and_never_alters_source(tmp_path):
    corpus = tmp_path / "owned_corpus"
    corpus.mkdir()
    song = corpus / "Aquaverno 004.wav"
    with wave.open(str(song), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        for i in range(48000):
            sample = int(0.14 * math.sin(2 * math.pi * 220 * i / 48000) * 32767)
            stream.writeframesraw(struct.pack("<hh", sample, sample))
    before = hashlib.sha256(song.read_bytes()).hexdigest()
    with pytest.raises(AudioLearningError, match="PRIVATE_LISTEN_NOT_AUTHORIZED"):
        listen_audio(corpus, "Aquaverno 004.wav", authorized=False)
    result = listen_audio(corpus, "Aquaverno 004.wav", authorized=True)
    assert result["schema"] == "HazeAudioListenReceipt/v1"
    assert result["acoustic_profile"]["schema"] == "ReferenceProfile/v1"
    assert result["source_sha256"] == before
    assert result["training_started"] is False
    assert result["original_modified"] is False
    assert hashlib.sha256(song.read_bytes()).hexdigest() == before
