from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from hazewave.av_research_lab import (
    AVResearchError,
    analyze_editorial_script,
    compose_research_evidence,
    run_authorized_study,
    research_specialist,
)

ROOT = Path(__file__).resolve().parents[1]


def _script_file(path: Path) -> Path:
    data = {
        "schema": "HazewaveEditorialReference/v1",
        "segments": [
            {"id": "intro", "start_seconds": 0, "duration_seconds": 12, "narration": "Vice City é o centro da nossa história."},
            {"id": "contexto", "start_seconds": 12, "duration_seconds": 10, "narration": "Agora vamos observar a montagem."},
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_editorial_analysis_measures_timing_word_density_and_no_raw_text(tmp_path: Path) -> None:
    out = analyze_editorial_script(_script_file(tmp_path / "script.json"))
    assert out["segment_count"] == 2
    assert out["duration_seconds"] == 22
    assert out["word_count"] == 14
    assert out["overlapping_segment_count"] == 0
    assert out["max_words_per_minute"] > 0
    assert out["artistic_verdict"] == "NOT_ASSIGNED"
    assert "Vice City" not in json.dumps(out, ensure_ascii=False)


def test_editorial_overlap_is_measured_not_silently_accepted(tmp_path: Path) -> None:
    path = _script_file(tmp_path / "script.json")
    x = json.loads(path.read_text())
    x["segments"][1]["start_seconds"] = 10
    path.write_text(json.dumps(x))
    out = analyze_editorial_script(path)
    assert out["overlapping_segment_count"] == 1


@pytest.mark.parametrize("kind,domain", [
    ("AUDIO_QC", "HAZE"),
    ("AUDIO_MUSIC", "HAZE"),
    ("VIDEO_QC", "WAVE"),
    ("SCENE_DETECTION", "WAVE"),
    ("IMAGE_METRICS", "WAVE"),
    ("EDITORIAL_SCRIPT", "WAVE"),
])
def test_specialist_routing_is_domain_explicit(kind: str, domain: str) -> None:
    assert research_specialist(kind)["domain"] == domain
    assert research_specialist(kind)["authority"] == "HAZEWAVE_HARNESS"


def test_unknown_research_mode_fails_closed() -> None:
    with pytest.raises(AVResearchError, match="RESEARCH_KIND_UNSUPPORTED"):
        research_specialist("ONE_AI_DOES_EVERYTHING")


def test_composer_rejects_wrong_digest_and_removes_media_paths(tmp_path: Path) -> None:
    path = _script_file(tmp_path / "script.json")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = compose_research_evidence(
        kind="EDITORIAL_SCRIPT",
        source_sha256=digest,
        grant_evidence={"signature_verified": True, "target_sha256": digest, "grant_id": "test-001"},
        measurements={"source_path": "/private/artist/speech.wav", "word_count": 14, "artistic_verdict": "NOT_ASSIGNED"},
        case_id="owned-case-0001",
    )
    raw = json.dumps(report)
    assert "/private/artist" not in raw
    assert report["state"] == "OBSERVATION_ONLY"
    assert report["production_approved"] is False
    assert report["provider_authority"] == "NONE"
    with pytest.raises(AVResearchError, match="RESEARCH_GRANT_DIGEST_MISMATCH"):
        compose_research_evidence(
            kind="EDITORIAL_SCRIPT", source_sha256=digest,
            grant_evidence={"signature_verified": True, "target_sha256": "a"*64, "grant_id": "test-001"},
            measurements={"word_count": 14}, case_id="owned-case-0001",
        )


def test_missing_signed_authorization_rejected_before_any_tool_run(tmp_path: Path) -> None:
    target = _script_file(tmp_path / "script.json")
    with pytest.raises(AVResearchError, match="RESEARCH_SIGNED_GRANT_REQUIRED"):
        run_authorized_study(
            source=target, kind="EDITORIAL_SCRIPT", case_id="owned-case-0001",
            grant_file=None, signature_file=None,
            state_root=tmp_path / "state",
        )
    assert not (tmp_path / "state").exists()


def test_symlinked_input_rejected_before_analysis(tmp_path: Path) -> None:
    actual = _script_file(tmp_path / "script.json")
    link = tmp_path / "alias.json"
    link.symlink_to(actual)
    with pytest.raises(AVResearchError, match="RESEARCH_SOURCE_NOT_REGULAR"):
        run_authorized_study(
            source=link, kind="EDITORIAL_SCRIPT", case_id="owned-case-0001",
            grant_file=tmp_path / "dummy.json", signature_file=tmp_path / "dummy.sig",
            state_root=tmp_path / "state",
        )


def test_signed_editorial_research_creates_private_evidence_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH signature tool unavailable")
    target = _script_file(tmp_path / "script.json")
    key = tmp_path / "owner_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    signers = tmp_path / "signers"
    signers.write_text("hazewave-owner " + key.with_suffix(".pub").read_text().strip() + "\n")
    signers.chmod(0o600)
    now = datetime.now(timezone.utc)
    grant = {
        "schema": "HazewaveReverseEngineeringTargetGrant/v1", "authority": "HAZEWAVE_HARNESS",
        "issuer": "hazewave-owner", "grant_id": "owned-editorial-fixture",
        "domain": "WAVE", "target_kind": "editorial_script", "purpose": "AUTHORIZED_FEATURE_STUDY",
        "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
    }
    grant_file = tmp_path / "grant.json"
    grant_file.write_text(json.dumps(grant))
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key),
                    "-n", "hazewave-research-grant", str(grant_file)], check=True,
                   stdout=subprocess.DEVNULL)
    grant_file.chmod(0o600)
    signature = tmp_path / "grant.json.sig"
    signature.chmod(0o600)
    result = run_authorized_study(
        source=target, kind="EDITORIAL_SCRIPT", case_id="editorial-fixture-01",
        grant_file=grant_file, signature_file=signature, trusted_signers_file=signers,
        state_root=tmp_path / "state",
    )
    assert result["state"] == "OBSERVATION_ONLY"
    assert result["harness_route"]["domain"] == "WAVE"
    receipts = list((tmp_path / "state" / "av-research" / "receipts").glob("*.json"))
    assert len(receipts) == 1
    assert receipts[0].stat().st_mode & 0o077 == 0
    assert json.loads(receipts[0].read_text())["source_sha256"] == grant["target_sha256"]
