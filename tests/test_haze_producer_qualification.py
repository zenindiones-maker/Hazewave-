"""Real FFmpeg audio QC regression; no REAPER runtime or model performance is simulated."""
from __future__ import annotations
import hashlib
import math
import shutil
import struct
import wave
from pathlib import Path
import pytest

from hazewave.haze_producer_qualification import (
    ProducerQualificationError, evaluate_producer_render_pair,
    admit_candidate_tool_surface,
)

def synth(path:Path, *, dc:float, hz:float=440., amp:float=.21, duration:float=3.0):
    """Owned, 48 kHz PCM16 stereo source; original and corrected share signal."""
    sr=48000
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr)
        out=bytearray()
        for i in range(int(sr*duration)):
            v=max(-.999,min(.999,amp*math.sin(2*math.pi*hz*i/sr)+dc))
            item=int(round(32767*v))
            out.extend(struct.pack("<hh",item,item))
        w.writeframes(out)
    return hashlib.sha256(path.read_bytes()).hexdigest()

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="REAL_FFMPEG_REQUIRED")
def test_real_audio_qc_qualifies_measured_dc_correction_but_not_reaper_expertise(tmp_path):
    root=tmp_path/"controlled";root.mkdir()
    before=root/"original.wav";after=root/"correction.wav"
    bh=synth(before,dc=.07);ah=synth(after,dc=0.)
    result=evaluate_producer_render_pair(
        fixture_root=root,reference=before,candidate=after,
        reference_sha256=bh,candidate_sha256=ah,
        intent="REMOVE_DC_OFFSET")
    assert result["measurement_engine"]=="FFMPEG_EBUR128_AND_ASTATS"
    assert result["technical_result"]=="TARGETED_QC_IMPROVEMENT"
    assert result["before"]["dc_offset"]>0.05
    assert abs(result["after"]["dc_offset"])<0.005
    assert result["before"]["sha256"]==bh
    assert result["after"]["sha256"]==ah
    assert result["music_quality_judgement"]=="HUMAN_LISTENING_NOT_PERFORMED"
    assert result["reaper_runtime_proven"] is False
    assert result["mix_master_competence_proven"] is False
    assert result["production_approved"] is False
    assert result["action_executed"] is False
    assert result["human_review_required"] is True

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="REAL_FFMPEG_REQUIRED")
def test_bad_processing_stays_not_qualified(tmp_path):
    root=tmp_path/"controlled";root.mkdir()
    before=root/"original.wav";after=root/"bad.wav"
    bh=synth(before,dc=.07);ah=synth(after,dc=.07,amp=.82)
    result=evaluate_producer_render_pair(
        fixture_root=root,reference=before,candidate=after,
        reference_sha256=bh,candidate_sha256=ah,intent="REMOVE_DC_OFFSET")
    assert result["technical_result"]=="REJECTED_BY_QC"
    assert "DC_OFFSET_NOT_CORRECTED" in result["qc_failures"]
    assert result["production_approved"] is False

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="REAL_FFMPEG_REQUIRED")
def test_same_material_and_unowned_paths_denied(tmp_path):
    root=tmp_path/"owned";root.mkdir()
    original=root/"original.wav"
    sha=synth(original,dc=.07)
    with pytest.raises(ProducerQualificationError,match="DISTINCT_RENDER_REQUIRED"):
        evaluate_producer_render_pair(
            fixture_root=root,reference=original,candidate=original,
            reference_sha256=sha,candidate_sha256=sha,intent="REMOVE_DC_OFFSET")
    external=tmp_path/"outside.wav"
    eh=synth(external,dc=0.)
    with pytest.raises(ProducerQualificationError,match="UNOWNED_RENDER_PATH"):
        evaluate_producer_render_pair(
            fixture_root=root,reference=original,candidate=external,
            reference_sha256=sha,candidate_sha256=eh,intent="REMOVE_DC_OFFSET")
    synth(root/"other.wav",dc=0.)
    with pytest.raises(ProducerQualificationError,match="AUDIO_DIGEST_MISMATCH"):
        evaluate_producer_render_pair(
            fixture_root=root,reference=original,candidate=(root/"other.wav"),
            reference_sha256=sha,candidate_sha256="f"*64,intent="REMOVE_DC_OFFSET")

def test_unverified_external_agents_cannot_gain_harness_execution_authority():
    checked=admit_candidate_tool_surface(
        candidate_id="xdarkzx-reapermcp",
        requested_operations=("session.inspect","fx.inventory"))
    assert checked["decision"]=="CATALOG_ONLY"
    assert checked["allowed_runtime_operations"]==[]
    assert checked["can_mutate_reaper"] is False
    assert checked["can_start_server"] is False
    assert checked["authority"]=="HAZEWAVE_HARNESS"
    with pytest.raises(ProducerQualificationError,match="CANDIDATE_OPERATION_FORBIDDEN"):
        admit_candidate_tool_surface(candidate_id="xdarkzx-reapermcp",
                                    requested_operations=("fx.add",))
    with pytest.raises(ProducerQualificationError,match="CANDIDATE_NOT_REVIEWED"):
        admit_candidate_tool_surface(candidate_id="made-up-provider",
                                    requested_operations=("session.inspect",))
    with pytest.raises(ProducerQualificationError,match="CANDIDATE_OPERATION_FORBIDDEN"):
        admit_candidate_tool_surface(candidate_id="xdarkzx-reapermcp",
                                    requested_operations=("shell.exec",))
    with pytest.raises(ProducerQualificationError,match="CANDIDATE_SHA_REQUIRED"):
        admit_candidate_tool_surface(candidate_id="xdarkzx-reapermcp",
                                    requested_operations=("session.inspect",),
                                    expected_upstream_sha256="not-a-commit")

def test_candidate_inventory_is_not_model_authority_and_has_no_paid_fallback():
    from hazewave.haze_producer_qualification import candidate_inventory
    entries=candidate_inventory()
    assert len(entries)>=4
    assert any(row["kind"]=="GENERATIVE_MUSIC_ENGINE" for row in entries)
    assert sum(row["kind"]=="REAPER_MCP_AGENT" for row in entries)>=2
    assert all(row["admission"]=="DISCOVERY_ONLY" for row in entries)
    assert all(row["production_approved"] is False for row in entries)
    assert all(row["paid_fallback_permitted"] is False for row in entries)
