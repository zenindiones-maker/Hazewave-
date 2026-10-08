"""A single original ELF must be linked to Ghidra Evidence + black-box synthesis.

The Ghidra observation is not treated as a recovered source specification.
The synthetic contract is independently authored, and full-domain ELF checks
are separate from the Z3 mathematical proof.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil

import pytest

from hazewave.native_behavior_synthesis import SynthesisError, synthesize_owned_native_fixture


def test_joint_real_elf_sha_and_formal_contract_with_mocked_ghidra_boundary(tmp_path,monkeypatch):
    if not shutil.which("cc"):
        pytest.skip("no system C compiler")
    observed=[]
    def native_evidence(rea,oracle):
        digest=hashlib.sha256(Path(oracle).read_bytes()).hexdigest()
        observed.append(digest)
        return {
            "provider_id":"ghidra", "target_sha256":digest,
            "evidence_id":"ev_owned_test_fake",
            "operation":"analyze_function",
        }
    monkeypatch.setattr(
        "hazewave.native_behavior_qualification._ghidra_observation",
        native_evidence,
    )
    report=synthesize_owned_native_fixture(
        state_root=tmp_path/"proof",compiler="cc",
        rea_binary=Path("/not-a-real-tool"),require_formal=True,
    )
    assert report["ghidra_observed_exact_same_elf"] is True
    assert observed==[report["oracle_elf_sha256"]]
    assert report["ghidra_direct_observation"]["target_sha256"]==report["oracle_elf_sha256"]
    assert report["formal_contract"]["result"]=="UNSAT_NO_COUNTEREXAMPLE_WITHIN_SPEC"
    assert report["behavioral_status"]=="EXHAUSTIVE_WITHIN_EXPLICIT_FINITE_DOMAIN"
    assert report["ghidra_guided_synthesis_proven"] is False
    assert report["production_approved"] is False


def test_bad_ghidra_elf_identity_fails_closed_no_receipt(tmp_path,monkeypatch):
    if not shutil.which("cc"):
        pytest.skip("no system C compiler")
    def wrong_native(rea,oracle):
        return {"provider_id":"ghidra","target_sha256":"0"*64,
                "evidence_id":"ev_wrong","operation":"analyze_function"}
    monkeypatch.setattr(
        "hazewave.native_behavior_qualification._ghidra_observation",
        wrong_native,
    )
    with pytest.raises(SynthesisError,match="GHIDRA_ELF_IDENTITY_MISMATCH"):
        synthesize_owned_native_fixture(
            state_root=tmp_path/"failed",compiler="cc",
            rea_binary=Path("/fake"),require_formal=True,
        )
    assert not (tmp_path/"failed").exists()


def test_rea_optional_no_false_ghidra_attestation(tmp_path):
    if not shutil.which("cc"):
        pytest.skip("no system C compiler")
    report=synthesize_owned_native_fixture(
        state_root=tmp_path/"without-ghidra", compiler="cc",
        require_formal=False,
    )
    assert report["ghidra_observed_exact_same_elf"] is False
    assert report["ghidra_direct_observation"] is None
    assert report["formal_contract"] is None
    assert report["ghidra_guided_synthesis_proven"] is False
