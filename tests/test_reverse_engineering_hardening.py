from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from hazewave.reverse_engineering import ReverseEngineeringError, load_default_foundation, verify_research_grant


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def signed_case(tmp_path: Path) -> dict:
    if not shutil.which("ssh-keygen"):
        pytest.skip("openssh-client is required for signature verification")
    private = tmp_path / "owner_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private)], check=True)
    public = private.with_suffix(".pub").read_text().strip()
    signers = tmp_path / "allowed_signers"
    signers.write_text("hazewave-owner " + public + "\n")
    signers.chmod(0o600)
    target = tmp_path / "target.so"
    target.write_bytes(b"fixture-only-public-target")
    now = datetime.now(timezone.utc)
    grant = {
        "schema": "HazewaveReverseEngineeringTargetGrant/v1",
        "authority": "HAZEWAVE_HARNESS",
        "issuer": "hazewave-owner",
        "grant_id": "unit-fixture-01",
        "domain": "HAZE",
        "target_kind": "audio_plugin",
        "purpose": "AUTHORIZED_FEATURE_STUDY",
        "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=20)).isoformat(),
    }
    grant_path = tmp_path / "grant.json"
    grant_path.write_text(json.dumps(grant, sort_keys=True, separators=(",", ":")) + "\n")
    signature = tmp_path / "grant.json.sig"
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(private), "-n", "hazewave-research-grant", str(grant_path)], check=True, stdout=subprocess.DEVNULL)
    # OpenSSH writes the signature to <file>.sig
    assert signature.is_file()
    grant_path.chmod(0o600)
    signature.chmod(0o600)
    return {"target": target, "grant": grant_path, "signature": signature, "signers": signers, "content": grant}


def _verify(f: dict, **overrides: object) -> dict:
    args = {
        "grant_file": f["grant"], "signature_file": f["signature"],
        "target_file": f["target"], "allowed_signers_file": f["signers"],
        "domain": "HAZE", "target_kind": "audio_plugin",
        "purpose": "AUTHORIZED_FEATURE_STUDY",
    }
    args.update(overrides)
    return verify_research_grant(**args)


def test_valid_owner_signed_grant_binds_target_scope_and_expiry(signed_case: dict) -> None:
    evidence = _verify(signed_case)
    assert evidence["target_sha256"] == signed_case["content"]["target_sha256"]
    assert evidence["issuer"] == "hazewave-owner"
    assert evidence["signature_verified"] is True


def test_tampered_grant_fails_closed(signed_case: dict) -> None:
    grant = signed_case["grant"]
    obj = json.loads(grant.read_text())
    obj["purpose"] = "PERFORMANCE_STUDY"
    grant.write_text(json.dumps(obj))
    with pytest.raises(ReverseEngineeringError):
        _verify(signed_case)


def test_target_digest_mismatch_fails_closed(signed_case: dict) -> None:
    signed_case["target"].write_bytes(b"another-asset")
    with pytest.raises(ReverseEngineeringError, match="TARGET_DIGEST_MISMATCH"):
        _verify(signed_case)


def test_wrong_scope_fails_closed(signed_case: dict) -> None:
    with pytest.raises(ReverseEngineeringError, match="GRANT_SCOPE_MISMATCH"):
        _verify(signed_case, domain="WAVE")


def test_expired_grant_fails_closed(signed_case: dict) -> None:
    future = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(ReverseEngineeringError, match="GRANT_TIME_INVALID"):
        _verify(signed_case, now=future)


def test_weak_trust_file_permissions_fail_closed(signed_case: dict) -> None:
    signed_case["signers"].chmod(0o644)
    with pytest.raises(ReverseEngineeringError, match="SIGNER_TRUST_FILE_UNSAFE"):
        _verify(signed_case)


def test_unauthenticated_bool_cannot_authorize_research() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")
    with pytest.raises((TypeError, ReverseEngineeringError)):
        foundation.plan(domain="HAZE", target_kind="audio_plugin",
                        purpose="AUTHORIZED_FEATURE_STUDY", authorized=True)


def test_doctor_does_not_ignore_rea_doctor_failure() -> None:
    script = (ROOT / "scripts/codespaces/reverse-engineering-doctor.sh").read_text()
    assert '[[ "$doctor_rc" -eq 0 ]] || fail "REA_DOCTOR_FAILED' in script
    assert 'HAZEWAVE_RE_DOCTOR=PASS' in script


def test_installer_only_claims_installed_not_runtime_ready() -> None:
    script = (ROOT / "scripts/codespaces/install-reverse-engineering-foundation.sh").read_text()
    assert 'HAZEWAVE_RE_INSTALL=PASS' in script
    assert 'HAZEWAVE_RE_RUNTIME_READY=PASS' not in script
    assert '"$REA_BIN" doctor --json' in script
    assert "RE_DOCTOR_NONZERO" in script


def test_signed_grant_is_required_for_actual_harness_plan(signed_case: dict) -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")
    plan = foundation.plan(
        domain="HAZE",
        target_kind="audio_plugin",
        purpose="AUTHORIZED_FEATURE_STUDY",
        target_file=signed_case["target"],
        grant_file=signed_case["grant"],
        signature_file=signed_case["signature"],
        trusted_signers_file=signed_case["signers"],
    )
    assert plan["authorized_target"] is True
    assert plan["authorization_evidence"]["signature_verified"] is True
    assert plan["tools"] == ["rea", "ghidra", "rizin", "frida", "ffmpeg", "mediainfo"]
    assert plan["grants_execution_authority"] is False
    assert plan["production_approved"] is False


def test_untrusted_signing_key_is_rejected(signed_case: dict, tmp_path: Path) -> None:
    another_key = tmp_path / "another"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(another_key)], check=True)
    signed_case["signers"].write_text("hazewave-owner " + another_key.with_suffix(".pub").read_text().strip() + "\n")
    with pytest.raises(ReverseEngineeringError, match="GRANT_SIGNATURE_INVALID"):
        _verify(signed_case)


def test_symlink_to_target_is_rejected(signed_case: dict, tmp_path: Path) -> None:
    alias = tmp_path / "alias.so"
    alias.symlink_to(signed_case["target"])
    with pytest.raises(ReverseEngineeringError, match="TARGET_FILE_UNSAFE"):
        _verify(signed_case, target_file=alias)


def test_deep_probe_does_not_promote_nonempty_json_to_runtime_proven() -> None:
    script = (ROOT / "scripts/codespaces/reverse-engineering-doctor.sh").read_text()
    assert 'len(raw) < 64' not in script
    assert "REA6_SOURCE_OWNED_FIXTURE" in script
    assert "rea function" in script
    assert "main --provider ghidra --json" in script
    assert "-m hazewave.rea6_integration verify-evidence" in script
    assert "RE_DEEP_EVIDENCE_NOT_VERIFIED" in script
    assert "len(raw) < 64" not in script
