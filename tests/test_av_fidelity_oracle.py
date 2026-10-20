"""Real synthetic audio/video fidelity controls: no fake metric-only PASS."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import pytest

from hazewave.av_fidelity_oracle import (
    AvFidelityError, analyze_synthetic_media,
    parse_audio_volumedetect, parse_ssim,
)

def test_parser_requires_real_loudness_summary():
    with pytest.raises(AvFidelityError):
        parse_audio_volumedetect("volumedetect available but no samples")
    observed = parse_audio_volumedetect("mean_volume: -18.2 dB\nmax_volume: -4.2 dB\n")
    assert observed["mean_volume_dbfs"] == -18.2
    assert observed["max_volume_dbfs"] == -4.2

def test_parser_requires_actual_ssim_all_not_cli_success():
    with pytest.raises(AvFidelityError):
        parse_ssim("SSIM filter available; result pending")
    assert parse_ssim("SSIM Y:0.993 U:1.000 V:1.000 All:0.9800 (17.1)") == 0.98

def test_real_ffmpeg_audio_video_oracle_correctly_rejects_altered_media(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    r=analyze_synthetic_media(private_root=tmp_path/"av-proof")
    assert r["harness_authority"]=="HAZEWAVE_HARNESS"
    assert r["actual_ffmpeg_executed"] is True
    assert r["synthetic_audio_verified"] is True
    assert r["audio_attenuation_detected_db"] >= 10
    assert r["synthetic_video_verified"] is True
    assert r["identical_video_ssim"] > 0.999
    assert r["altered_video_ssim"] < 0.99
    assert r["source"]=="OWNED_SYNTHETIC_MEDIA"
    assert r["owner_media_analyzed"] is False
    assert r["capability_plane_ready"] is False
    assert r["production_approved"] is False
    receipts=list((tmp_path/"av-proof").glob("av-receipt-*.json"))
    assert len(receipts)==1 and receipts[0].stat().st_mode & 0o077 == 0

def test_live_media_and_external_paths_have_no_ingress():
    import inspect
    import hazewave.av_fidelity_oracle as m
    sig=inspect.signature(m.analyze_synthetic_media)
    assert set(sig.parameters)=={"private_root","ffmpeg_bin"}
    src=inspect.getsource(m)
    assert "shell=True" not in src
    assert "fetch(" not in src
    assert "CODEC" not in src
