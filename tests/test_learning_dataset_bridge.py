from pathlib import Path
import json
import pytest

from hazewave.learning_dataset_bridge import (
    LearningBridgeError, export_synthetic_examples,
)

def _native():
    return {
        "schema":"HazewaveOwnedAutomaticNativeSynthesis/v1",
        "harness_authority":"HAZEWAVE_HARNESS",
        "behavioral_status":"EXHAUSTIVE_WITHIN_EXPLICIT_FINITE_DOMAIN",
        "domain":[-1000,1000],
        "inputs_checked":2001,
        "automatic_candidate_generation":True,
        "original_C_used_for_synthesis":False,
        "outside_domain_equivalence_proven":False,
        "production_approved":False,
        "oracle_elf_sha256":"a"*64,
    }

def _av():
    return {
        "schema":"HazewaveSyntheticAudioVideoFidelity/v1",
        "harness_authority":"HAZEWAVE_HARNESS",
        "source":"OWNED_SYNTHETIC_MEDIA",
        "actual_ffmpeg_executed":True,
        "audio_attenuation_detected_db":12.04,
        "identical_video_ssim":1.0,
        "altered_video_ssim":0.12,
        "owner_media_analyzed":False,
        "production_approved":False,
    }

def test_first_party_receipts_become_valid_alpaca_demo_not_train_authorization(tmp_path):
    native=tmp_path/"native.json"; av=tmp_path/"av.json"
    native.write_text(json.dumps(_native())); av.write_text(json.dumps(_av()))
    native.chmod(0o600); av.chmod(0o600)
    proof=export_synthetic_examples(native_receipt=native,av_receipt=av,output_root=tmp_path/"out")
    assert proof["source_type"]=="SOURCE_OWNED_SYNTHETIC_RECEIPTS_ONLY"
    assert proof["training_admitted"] is False
    assert proof["owner_dataset_grant"]=="NOT_PROVEN"
    assert proof["example_count"] >= 3
    data=json.loads((tmp_path/"out"/"hazewave_synthetic_research_demo.json").read_text())
    assert len(data)==proof["example_count"]
    assert all(set(x)=={"instruction","input","output"} for x in data)
    index=json.loads((tmp_path/"out"/"dataset_info.json").read_text())
    assert index["hazewave_synthetic_research_demo"]["formatting"]=="alpaca"
    assert index["hazewave_synthetic_research_demo"]["file_name"]=="hazewave_synthetic_research_demo.json"
    assert all(not p.stat().st_mode & 0o077 for p in (tmp_path/"out").iterdir())
    assert all("owner_media" not in json.dumps(x).lower() for x in data)

def test_untrusted_arbitrary_owner_media_receipt_is_rejected(tmp_path):
    n=_native(); a=_av()
    a["owner_media_analyzed"]=True
    paths=[tmp_path/"n.json",tmp_path/"a.json"]
    for p,r in zip(paths,(n,a)):
        p.write_text(json.dumps(r));p.chmod(0o600)
    with pytest.raises(LearningBridgeError,match="SYNTHETIC_ONLY"):
        export_synthetic_examples(native_receipt=paths[0],av_receipt=paths[1],
                                  output_root=tmp_path/"out")
    assert not (tmp_path/"out").exists()

def test_no_fake_pass_or_schema_self_attestation(tmp_path):
    n=_native(); a=_av(); n["inputs_checked"]=300
    paths=[tmp_path/"n.json",tmp_path/"a.json"]
    for p,r in zip(paths,(n,a)):
        p.write_text(json.dumps(r));p.chmod(0o600)
    with pytest.raises(LearningBridgeError,match="UNVERIFIED"):
        export_synthetic_examples(native_receipt=paths[0],av_receipt=paths[1],output_root=tmp_path/"out")
    assert not (tmp_path/"out").exists()
