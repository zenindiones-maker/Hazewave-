"""Exact-source, deletion integrity and failure-mode regressions (no network)."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path
import pytest
from hazewave.source_truth_guard import (
    SourceTruthError, load_deletion_policy, validate_active_references,
    verify_bound_receipt, verify_checkout, detect_protected_reintroductions,
    validate_deletion_history, validate_restoration_exception, verify_remote_ref
)

ROOT=Path(__file__).resolve().parents[1]
DELETED="docs/architecture/decisions/ADR-0006-reverse-engineering-lab.md"
SUCCESSOR="docs/architecture/decisions/ADR-0007-reverse-engineering-lab.md"
REMOVAL="8624e219882f11d39cd2c8cb893e984c3fcc86f5"


def git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],capture_output=True,
                          text=True,check=True).stdout.strip()


def fixture_repo(tmp_path):
    root=tmp_path/"repo"; root.mkdir()
    git(root,"init","-q")
    git(root,"config","user.name","Governance Fixture")
    git(root,"config","user.email","test@example.invalid")
    (root/"AGENTS.md").write_text("## Authority\n## Source-of-truth precedence\n")
    git(root,"add",".");git(root,"commit","-qm","fixture")
    return root


def fixture_policy():
    return {"schema":"HazewaveSourceOfTruthDeletions/v1",
            "project_id":"HAZEWAVE","authority":"HAZEWAVE_HARNESS",
            "protected_deletions":[{
             "path":DELETED,"deletion_commit":REMOVAL,
             "reason":"Retired duplicate ADR-0006 identifier",
             "successor":SUCCESSOR,"review_owner":"zenindiones-maker"}]}


def test_registry_and_root_agents_reference_existing_policy_without_losing_headings():
    p=load_deletion_policy(ROOT/"config/source-of-truth-deletions-v1.json")
    assert p["protected_deletions"]==fixture_policy()["protected_deletions"]
    assert p["authority"]=="HAZEWAVE_HARNESS"
    assert not (ROOT/DELETED).exists()
    assert (ROOT/SUCCESSOR).is_file()
    agent=(ROOT/"AGENTS.md").read_text()
    assert "docs/governance/source-of-truth.md" in agent
    assert "## Authority" in agent and "## Handoff contract" in agent
    reg=json.loads((ROOT/"docs/DOCUMENTATION_REGISTRY_V2.json").read_text())
    assert any(v["path"]=="docs/governance/source-of-truth.md"
               and v["authority"]=="NORMATIVE" and v["status"]=="ACTIVE"
               for v in reg["documents"])


def test_deletion_commit_real_and_ancestor_not_just_path_missing():
    assert validate_deletion_history(ROOT,fixture_policy())["verified_tombstones"]==1


def test_checkout_sha_tree_and_uncommitted_wip_cannot_be_overwritten(tmp_path):
    root=fixture_repo(tmp_path)
    sha=git(root,"rev-parse","HEAD")
    tree=git(root,"rev-parse","HEAD^{tree}")
    assert verify_checkout(root,expected_commit=sha,
                           expected_tree=tree)["wip_preserved"]=="PASS_CLEAN_NO_MUTATION"
    with pytest.raises(SourceTruthError,match="STALE_COMMIT"):
        verify_checkout(root,expected_commit="0"*40,expected_tree=tree)
    with pytest.raises(SourceTruthError,match="TREE_MISMATCH"):
        verify_checkout(root,expected_commit=sha,expected_tree="1"*40)
    (root/"WIP").write_text("preserve me")
    with pytest.raises(SourceTruthError,match="WIP_PRESENT"):
        verify_checkout(root,expected_commit=sha,expected_tree=tree)
    assert (root/"WIP").read_text()=="preserve me"
    git(root,"add","WIP")
    with pytest.raises(SourceTruthError,match="WIP_PRESENT"):
        verify_checkout(root,expected_commit=sha,expected_tree=tree)


def test_active_missing_references_denied_and_explicit_historical_citations_allowed(tmp_path):
    tick=chr(96)
    (tmp_path/"AGENTS.md").write_text("Use "+tick+"config/phantom.json"+tick+" now\n"+
                                     "HISTORICAL_ONLY "+tick+"docs/archived.md"+tick+"\n")
    with pytest.raises(SourceTruthError,match="ACTIVE_REFERENCE_MISSING"):
        validate_active_references(tmp_path,{"AGENTS.md"},require_registry=False)
    (tmp_path/"AGENTS.md").write_text("HISTORICAL_ONLY "+tick+"docs/archived.md"+tick+"\n")
    assert validate_active_references(tmp_path,{"AGENTS.md"},
                                     require_registry=False)["active_refs_checked"]==0


def test_tombstone_blocks_reintroduction_without_authenticated_exception():
    p=fixture_policy()
    with pytest.raises(SourceTruthError,match="PROTECTED_FILE_RESURRECTION"):
        detect_protected_reintroductions({DELETED,SUCCESSOR,"AGENTS.md"},p,
                                         commit="a"*40,tree="b"*40)
    assert detect_protected_reintroductions({SUCCESSOR,"AGENTS.md"},p,
                                             commit="a"*40,tree="b"*40)["reintroductions"]==0
    with pytest.raises(SourceTruthError):
        detect_protected_reintroductions({DELETED,SUCCESSOR,"AGENTS.md"},p,
           commit="a"*40,tree="b"*40,
           exceptions=[{"schema":"HazewaveDeletionException/v1","path":DELETED,
                        "approved":True}],github_reviews=[])


def test_exception_binds_exact_sha_tree_owner_approval_tests_and_reason():
    request={"schema":"HazewaveDeletionException/v1","path":DELETED,
        "deletion_commit":REMOVAL,"candidate_commit":"a"*40,"candidate_tree":"b"*40,
        "reason":"Functional change after verified successor and historical security review",
        "successor_comparison":"ADR-0007 lacks the accepted new property; migration required",
        "security_review":"Security and architecture reviewed with scope-limited tests",
        "regression_tests":["tests/test_source_truth_guard.py"],
        "owner":"zenindiones-maker"}
    reviews=[{"user":{"login":"zenindiones-maker"},"state":"APPROVED",
              "commit_id":"a"*40,"submitted_at":"2026-10-08T23:00:00Z"}]
    assert validate_restoration_exception(request,protected=fixture_policy()["protected_deletions"][0],
         commit="a"*40,tree="b"*40,tracked_files={"tests/test_source_truth_guard.py"},
         github_reviews=reviews)["approved"] is True
    with pytest.raises(SourceTruthError,match="RESTORATION_REVIEW_REQUIRED"):
        validate_restoration_exception(request,protected=fixture_policy()["protected_deletions"][0],
         commit="a"*40,tree="b"*40,tracked_files={"tests/test_source_truth_guard.py"},
         github_reviews=[])
    with pytest.raises(SourceTruthError,match="RESTORATION_REVIEW_REQUIRED"):
        validate_restoration_exception(request,protected=fixture_policy()["protected_deletions"][0],
         commit="a"*40,tree="b"*40,tracked_files={"tests/test_source_truth_guard.py"},
         github_reviews=[{**reviews[0],"commit_id":"c"*40}])
    with pytest.raises(SourceTruthError,match="RESTORATION_SCOPE_INVALID"):
        validate_restoration_exception({**request,"candidate_tree":"c"*40},
          protected=fixture_policy()["protected_deletions"][0],
          commit="a"*40,tree="b"*40,tracked_files={"tests/test_source_truth_guard.py"},
          github_reviews=reviews)


def test_receipts_from_obsolete_ref_sha_tree_or_changed_bytes_fail(tmp_path):
    payload={"schema":"HazewaveBoundEvidence/v1","authority":"HAZEWAVE_HARNESS",
      "repository":"zenindiones-maker/Hazewave-","source_ref":"work/current",
      "source_commit":"a"*40,"source_tree":"b"*40,"production_approved":False}
    path=tmp_path/"proof.json"
    path.write_text(json.dumps(payload,sort_keys=True))
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert verify_bound_receipt(path,expected_digest=digest,
      ref="work/current",commit="a"*40,tree="b"*40)["provenance"]=="EXACT_COMMIT_AND_TREE"
    for ref,sha,tree,hash_,error in [
        ("work/old","a"*40,"b"*40,digest,"STALE_BRANCH_EVIDENCE"),
        ("work/current","c"*40,"b"*40,digest,"RECEIPT_COMMIT_MISMATCH"),
        ("work/current","a"*40,"c"*40,digest,"RECEIPT_TREE_MISMATCH"),
        ("work/current","a"*40,"b"*40,"d"*64,"RECEIPT_HASH_MISMATCH")]:
        with pytest.raises(SourceTruthError,match=error):
            verify_bound_receipt(path,expected_digest=hash_,ref=ref,commit=sha,tree=tree)
    path.write_text(path.read_text()+"tampered")
    with pytest.raises(SourceTruthError,match="RECEIPT_HASH_MISMATCH"):
        verify_bound_receipt(path,expected_digest=digest,
          ref="work/current",commit="a"*40,tree="b"*40)


def test_remote_branch_and_commit_tree_are_independently_checked():
    remote={"ref":"refs/heads/work/current","object":{"sha":"a"*40}}
    commit={"sha":"a"*40,"tree":{"sha":"b"*40}}
    assert verify_remote_ref(remote,commit,expected_ref="work/current",
            expected_commit="a"*40,expected_tree="b"*40)["remote_attested"]
    with pytest.raises(SourceTruthError,match="STALE_REMOTE_REF"):
        verify_remote_ref({**remote,"object":{"sha":"c"*40}},commit,
         expected_ref="work/current",expected_commit="a"*40,expected_tree="b"*40)
    with pytest.raises(SourceTruthError,match="REMOTE_TREE_MISMATCH"):
        verify_remote_ref(remote,{**commit,"tree":{"sha":"c"*40}},
         expected_ref="work/current",expected_commit="a"*40,expected_tree="b"*40)


def test_existing_agents_directory_scope_refs_are_valid_not_missing(tmp_path):
    tick=chr(96)
    (tmp_path/"AGENTS.md").write_text(
        "## Path expectations\nRead "+tick+"docs/wave/"+tick+" and "+
        tick+"src/hazewave/"+tick+" as directory scopes.\n")
    paths={"AGENTS.md","docs/wave/LIVING_RESONANCE.md","src/hazewave/harness.py"}
    assert validate_active_references(tmp_path,paths,
        require_registry=False)["active_refs_checked"]==2
    with pytest.raises(SourceTruthError,match="ACTIVE_REFERENCE_MISSING"):
        validate_active_references(tmp_path,
            {"AGENTS.md","src/hazewave/harness.py"},require_registry=False)
