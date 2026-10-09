"""Fail-closed source truth and historical deletion preflight for Hazewave Harness.

No authority is created: authoritative routing/policy stays in Hazewave Harness,
the accepted ProjectProfile and existing AGENTS.md. This module verifies the
reviewed Git object, active references, intentional deletions and provenance.
It never writes checkout state, restores files or promotes production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any, Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen

from hazewave.harness import AUTHORITY

REPOSITORY = "zenindiones-maker/Hazewave-"
_ROOT = Path(__file__).resolve().parents[2]
POLICY = _ROOT / "config/source-of-truth-deletions-v1.json"
_SHA40 = re.compile(r"^[a-f0-9]{40}$")
_SHA64 = re.compile(r"^[a-f0-9]{64}$")
_PATH = re.compile(r"^(?:config|docs|src|schemas|skills|scripts|tests|canon|apps|examples|\.github)/[a-zA-Z0-9_.\-/]+$")
_AGENT_REF = re.compile(r"\x60((?:config|docs|src|schemas|skills|scripts|tests|canon|apps|examples|\.github)/[A-Za-z0-9_.\-/]+)\x60")


class SourceTruthError(ValueError):
    """A typed deny reason; no arbitrary source text is used as authority."""


def _path_ok(value: Any) -> bool:
    if not isinstance(value, str) or not _PATH.fullmatch(value):
        return False
    p = PurePosixPath(value)
    return len(value) <= 220 and ".." not in p.parts and not value.endswith("/") and "//" not in value


def _sha(value: Any, length: int = 40) -> bool:
    return isinstance(value, str) and bool((_SHA40 if length == 40 else _SHA64).fullmatch(value))


def _git(root: Path, *args: str, allow_failure: bool = False) -> str:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True,
            text=True, check=False, timeout=12, env=env
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceTruthError("GIT_INTEGRITY_UNAVAILABLE") from exc
    if completed.returncode and not allow_failure:
        raise SourceTruthError("GIT_INTEGRITY_UNAVAILABLE")
    return completed.stdout.strip() if completed.returncode == 0 else ""


def load_deletion_policy(path: Path = POLICY) -> dict[str, Any]:
    try:
        if path.is_symlink() or path.stat().st_size > 32768:
            raise SourceTruthError("DELETION_POLICY_INVALID")
        payload = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise SourceTruthError("DELETION_POLICY_INVALID") from exc
    if (type(payload) is not dict
            or payload.get("schema") != "HazewaveSourceOfTruthDeletions/v1"
            or payload.get("project_id") != "HAZEWAVE"
            or payload.get("authority") != AUTHORITY
            or set(payload) != {"schema", "project_id", "authority", "protected_deletions"}):
        raise SourceTruthError("DELETION_POLICY_INVALID")
    items = payload["protected_deletions"]
    if not isinstance(items, list) or not items or len(items) > 128:
        raise SourceTruthError("DELETION_POLICY_INVALID")
    seen: set[str] = set()
    for item in items:
        if (type(item) is not dict
                or set(item) != {"path", "deletion_commit", "reason", "successor", "review_owner"}
                or not _path_ok(item.get("path"))
                or not _sha(item.get("deletion_commit"))
                or not _path_ok(item.get("successor"))
                or item["path"] == item["successor"]
                or not isinstance(item.get("reason"), str)
                or not 12 <= len(item["reason"]) <= 500
                or item.get("review_owner") != "zenindiones-maker"
                or item["path"] in seen):
            raise SourceTruthError("DELETION_POLICY_INVALID")
        seen.add(item["path"])
    return payload


def tracked_tree_paths(root: Path) -> set[str]:
    # Exact Git object tree; never scan a historical branch or arbitrary FS.
    raw = _git(root, "ls-tree", "-r", "--name-only", "HEAD")
    return set(raw.splitlines())


def verify_checkout(root: Path, *, expected_commit: str, expected_tree: str) -> dict[str, str]:
    root = root.resolve()
    if (not _sha(expected_commit) or not _sha(expected_tree)
            or _git(root, "rev-parse", "--show-toplevel") != str(root)):
        raise SourceTruthError("REPOSITORY_IDENTITY_INVALID")
    sha = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    if sha != expected_commit:
        raise SourceTruthError("STALE_COMMIT")
    if tree != expected_tree:
        raise SourceTruthError("TREE_MISMATCH")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise SourceTruthError("WIP_PRESENT")
    return {
        "commit_sha": sha, "tree_sha": tree,
        "wip_preserved": "PASS_CLEAN_NO_MUTATION",
        "authority": AUTHORITY,
    }


def validate_deletion_history(root: Path, policy: Mapping[str, Any]) -> dict[str, int]:
    count = 0
    for item in policy.get("protected_deletions", []):
        deletion_commit = item["deletion_commit"]
        if _git(root, "merge-base", "--is-ancestor", deletion_commit, "HEAD",
                allow_failure=True) != "":
            # merge-base --is-ancestor prints no output when it succeeds:
            # check the deletion object exists plus actual diff below.
            pass
        # Ensure deletion commit object is present in THIS candidate's lineage.
        # rev-list HEAD contains all parents, not any unrelated branch history.
        if not _git(root, "rev-list", "HEAD", "--max-count=10000").splitlines().__contains__(deletion_commit):
            raise SourceTruthError("DELETION_COMMIT_NOT_IN_LINEAGE")
        diff = _git(root, "diff-tree", "--no-commit-id", "--name-status", "-r",
                    "--no-renames", deletion_commit)
        if ("D\t" + item["path"]) not in diff.splitlines():
            raise SourceTruthError("DELETION_HISTORY_NOT_PROVEN")
        count += 1
    return {"verified_tombstones": count}


def validate_active_references(root: Path, tracked_files: set[str],
                               *, require_registry: bool = True) -> dict[str, int]:
    agent_file = root / "AGENTS.md"
    if "AGENTS.md" not in tracked_files or not agent_file.is_file():
        raise SourceTruthError("AGENT_CONTRACT_MISSING")
    active_refs: set[str] = set()
    for line in agent_file.read_text(encoding="utf-8").splitlines():
        if "HISTORICAL_ONLY" in line:
            continue
        active_refs.update(_AGENT_REF.findall(line))
    if require_registry:
        mandatory = {"docs/governance/source-of-truth.md",
                     "docs/DOCUMENTATION_REGISTRY_V2.json",
                     "config/project-profile-v2.json",
                     "config/source-of-truth-deletions-v1.json"}
        if not mandatory.issubset(tracked_files):
            raise SourceTruthError("GOVERNANCE_ARTIFACT_MISSING")
        if "docs/governance/source-of-truth.md" not in agent_file.read_text(encoding="utf-8"):
            raise SourceTruthError("AGENT_SOURCE_TRUTH_REFERENCE_MISSING")
        try:
            registry = json.loads((root / "docs/DOCUMENTATION_REGISTRY_V2.json").read_text())
            profile = json.loads((root / "config/project-profile-v2.json").read_text())
        except (OSError, ValueError) as exc:
            raise SourceTruthError("ACTIVE_REFERENCE_REGISTRY_INVALID") from exc
        for item in registry.get("documents", []):
            if item.get("status") == "ACTIVE":
                active_refs.add(item.get("path"))
        for item in profile.get("architecture_authority", {}).get("normative_refs", []):
            active_refs.add(item.get("path"))
        active_refs.update(mandatory)
    checked = 0
    for ref in active_refs:
        if not isinstance(ref, str) or not _path_ok(ref) and ref != "AGENTS.md":
            raise SourceTruthError("ACTIVE_REFERENCE_INVALID")
        # Backticked references to a directory are allowed if that prefix exists.
        if ref not in tracked_files and not any(x.startswith(ref.rstrip("/") + "/") for x in tracked_files):
            raise SourceTruthError(f"ACTIVE_REFERENCE_MISSING:{ref}")
        checked += 1
    return {"active_refs_checked": checked}


def validate_restoration_exception(
    request: Mapping[str, Any], *, protected: Mapping[str, Any],
    commit: str, tree: str, tracked_files: set[str],
    github_reviews: list[dict[str, Any]]
) -> dict[str, Any]:
    fields = {
        "schema", "path", "deletion_commit", "candidate_commit", "candidate_tree",
        "reason", "successor_comparison", "security_review", "regression_tests", "owner"
    }
    if (not isinstance(request, Mapping)
            or set(request) != fields
            or request.get("schema") != "HazewaveDeletionException/v1"
            or request.get("path") != protected["path"]
            or request.get("deletion_commit") != protected["deletion_commit"]
            or request.get("candidate_commit") != commit
            or request.get("candidate_tree") != tree
            or request.get("owner") != protected["review_owner"]
            or any(not isinstance(request.get(x), str)
                   or not 28 <= len(request[x]) <= 1200
                   for x in ("reason", "successor_comparison", "security_review"))
            or not isinstance(request.get("regression_tests"), list)
            or not 1 <= len(request["regression_tests"]) <= 20
            or any(not isinstance(t, str) or not t.startswith("tests/test_")
                   or t not in tracked_files for t in request["regression_tests"])):
        raise SourceTruthError("RESTORATION_SCOPE_INVALID")
    # Only GitHub's fetched PR review objects may enter github_reviews.
    # An approval field in the authored request file is NEVER evidence.
    if not any(
        type(rv) is dict and rv.get("state") == "APPROVED"
        and rv.get("commit_id") == commit
        and isinstance(rv.get("user"), dict)
        and rv["user"].get("login") == protected["review_owner"]
        and isinstance(rv.get("submitted_at"), str)
        for rv in github_reviews
    ):
        raise SourceTruthError("RESTORATION_REVIEW_REQUIRED")
    return {"approved": True, "review_binding": "LIVE_GITHUB_OWNER_REVIEW_EXACT_SHA"}


def detect_protected_reintroductions(
    tracked_files: set[str], policy: Mapping[str, Any], *,
    commit: str, tree: str, exceptions: list[dict[str, Any]] | None = None,
    github_reviews: list[dict[str, Any]] | None = None
) -> dict[str, int]:
    if not _sha(commit) or not _sha(tree):
        raise SourceTruthError("CANDIDATE_IDENTITY_INVALID")
    requests = exceptions or []
    reintroduced = 0
    for item in policy["protected_deletions"]:
        if item["successor"] not in tracked_files:
            raise SourceTruthError("PROTECTED_SUCCESSOR_MISSING")
        if item["path"] not in tracked_files:
            continue
        reintroduced += 1
        matches = [x for x in requests if isinstance(x, dict) and x.get("path") == item["path"]]
        if len(matches) != 1:
            raise SourceTruthError("PROTECTED_FILE_RESURRECTION")
        validate_restoration_exception(
            matches[0], protected=item, commit=commit, tree=tree,
            tracked_files=tracked_files, github_reviews=github_reviews or [])
    return {"reintroductions": reintroduced}


def verify_bound_receipt(
    file_path: Path, *, expected_digest: str, ref: str, commit: str, tree: str
) -> dict[str, str]:
    if not _sha(expected_digest, 64) or not _sha(commit) or not _sha(tree):
        raise SourceTruthError("RECEIPT_BINDING_INVALID")
    try:
        if file_path.is_symlink() or not stat.S_ISREG(file_path.stat().st_mode):
            raise SourceTruthError("RECEIPT_FILE_INVALID")
        raw = file_path.read_bytes()
    except OSError as exc:
        raise SourceTruthError("RECEIPT_UNAVAILABLE") from exc
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected_digest:
        raise SourceTruthError("RECEIPT_HASH_MISMATCH")
    try:
        item = json.loads(raw)
    except ValueError as exc:
        raise SourceTruthError("RECEIPT_JSON_INVALID") from exc
    if (not isinstance(item, dict) or item.get("schema") != "HazewaveBoundEvidence/v1"
            or item.get("authority") != AUTHORITY or item.get("repository") != REPOSITORY
            or item.get("production_approved") is not False):
        raise SourceTruthError("RECEIPT_POLICY_INVALID")
    if item.get("source_ref") != ref:
        raise SourceTruthError("STALE_BRANCH_EVIDENCE")
    if item.get("source_commit") != commit:
        raise SourceTruthError("RECEIPT_COMMIT_MISMATCH")
    if item.get("source_tree") != tree:
        raise SourceTruthError("RECEIPT_TREE_MISMATCH")
    return {"provenance": "EXACT_COMMIT_AND_TREE", "sha256": expected_digest}


def verify_remote_ref(
    branch: Mapping[str, Any], commit_obj: Mapping[str, Any], *,
    expected_ref: str, expected_commit: str, expected_tree: str
) -> dict[str, Any]:
    if (branch.get("ref") != "refs/heads/" + expected_ref
            or not isinstance(branch.get("object"), dict)
            or branch["object"].get("sha") != expected_commit):
        raise SourceTruthError("STALE_REMOTE_REF")
    if (commit_obj.get("sha") != expected_commit
            or not isinstance(commit_obj.get("tree"), dict)
            or commit_obj["tree"].get("sha") != expected_tree):
        raise SourceTruthError("REMOTE_TREE_MISMATCH")
    return {"remote_attested": True}


def _github_api(endpoint: str, token: str) -> Any:
    if not token or not endpoint.startswith("/repos/" + REPOSITORY + "/"):
        raise SourceTruthError("GITHUB_TRUST_CONTEXT_MISSING")
    request = Request(
        "https://api.github.com" + endpoint,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urlopen(request, timeout=12) as answer:
            raw = answer.read(196609)
        if len(raw) > 196608:
            raise SourceTruthError("GITHUB_RESPONSE_TOO_LARGE")
        return json.loads(raw)
    except (OSError, ValueError) as exc:
        raise SourceTruthError("GITHUB_ATTESTATION_UNAVAILABLE") from exc


def _restore_requests(root: Path) -> list[dict[str, Any]]:
    directory = root / "docs/governance/restoration-exceptions"
    if not directory.exists():
        return []
    if directory.is_symlink():
        raise SourceTruthError("EXCEPTION_DIRECTORY_UNSAFE")
    requests: list[dict[str, Any]] = []
    for file in sorted(directory.iterdir()):
        if file.is_symlink() or file.suffix != ".json" or file.stat().st_size > 8192:
            raise SourceTruthError("EXCEPTION_FILE_UNSAFE")
        try:
            value = json.loads(file.read_bytes())
        except (OSError, ValueError) as exc:
            raise SourceTruthError("EXCEPTION_FILE_INVALID") from exc
        if not isinstance(value, dict):
            raise SourceTruthError("EXCEPTION_FILE_INVALID")
        requests.append(value)
    return requests


def _main_github(root: Path) -> dict[str, Any]:
    event_file, token = os.environ.get("GITHUB_EVENT_PATH"), os.environ.get("GITHUB_TOKEN")
    if (not event_file or not token or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
            or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY):
        raise SourceTruthError("GITHUB_TRUST_CONTEXT_MISSING")
    try:
        raw = Path(event_file).read_bytes()
        if len(raw) > 196608:
            raise SourceTruthError("GITHUB_EVENT_OVERSIZE")
        event = json.loads(raw)
    except (ValueError, OSError) as exc:
        raise SourceTruthError("GITHUB_EVENT_INVALID") from exc
    obj = event.get("pull_request") or {}
    head = obj.get("head") or {}
    base = obj.get("base") or {}
    head_repo = (head.get("repo") or {}).get("full_name")
    if (head_repo != REPOSITORY
            or not isinstance(obj.get("number"), int) or obj["number"] < 1
            or not _sha(head.get("sha")) or not _sha(base.get("sha"))
            or not isinstance(head.get("ref"), str)
            or not head["ref"].startswith("work/")
            or not re.fullmatch(r"work/[A-Za-z0-9_./-]{3,120}", head["ref"])
            or ".." in head["ref"]):
        raise SourceTruthError("UNAUTHORIZED_MISSION_LINEAGE")
    # No GitHub fork credentials or side effects; this is a same-repo candidate.
    expected_commit = head["sha"]
    if _git(root, "rev-parse", "HEAD") != expected_commit:
        raise SourceTruthError("STALE_COMMIT")
    expected_tree = _git(root, "rev-parse", "HEAD^{tree}")
    proof = verify_checkout(root, expected_commit=expected_commit,
                            expected_tree=expected_tree)
    # Resolve current ref and Git tree from authenticated GitHub APIs rather than
    # trusting a branch name or a stale locally cached checkout.
    remote_branch = _github_api(
        "/repos/" + REPOSITORY + "/git/ref/heads/" + quote(head["ref"], safe=""), token)
    remote_commit = _github_api(
        "/repos/" + REPOSITORY + "/git/commits/" + expected_commit, token)
    verify_remote_ref(remote_branch, remote_commit, expected_ref=head["ref"],
                      expected_commit=expected_commit, expected_tree=expected_tree)
    if not _git(root, "merge-base", base["sha"], expected_commit):
        raise SourceTruthError("MISSION_ANCESTRY_UNVERIFIED")
    policy = load_deletion_policy(root / "config/source-of-truth-deletions-v1.json")
    paths = tracked_tree_paths(root)
    history = validate_deletion_history(root, policy)
    refs = validate_active_references(root, paths)
    exceptions = _restore_requests(root)
    protected_present = any(x["path"] in paths for x in policy["protected_deletions"])
    reviews = []
    if protected_present:
        reviews = _github_api(
            "/repos/" + REPOSITORY + "/pulls/" + str(obj["number"]) + "/reviews?per_page=100", token)
        if not isinstance(reviews, list):
            raise SourceTruthError("RESTORATION_REVIEW_UNAVAILABLE")
    deletions = detect_protected_reintroductions(
        paths, policy, commit=expected_commit, tree=expected_tree,
        exceptions=exceptions, github_reviews=reviews)
    return {
        "SOURCE_OF_TRUTH": "VERIFIED",
        "AUTHORIZED_REF": head["ref"],
        "REMOTE_HEAD": expected_commit,
        "REVIEWED_TREE": expected_tree,
        "WIP_PRESERVED": proof["wip_preserved"],
        "PROTECTED_DELETION_CHECK": "PASS",
        "STALE_ACTIVE_REFERENCE_CHECK": "PASS",
        "verified_tombstones": history["verified_tombstones"],
        "active_refs_checked": refs["active_refs_checked"],
        "restorations": deletions["reintroductions"],
        "PRODUCTION_APPROVED": False,
        "authority": AUTHORITY,
    }


def verify_repository_static(root: Path) -> dict[str, Any]:
    """Existing Harness validator entrypoint: no network, no Git write, no claim of remote proof."""
    policy = load_deletion_policy(root / "config/source-of-truth-deletions-v1.json")
    paths = tracked_tree_paths(root)
    refs = validate_active_references(root, paths)
    hist = validate_deletion_history(root, policy)
    sha, tree = _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")
    deleted = detect_protected_reintroductions(paths, policy, commit=sha, tree=tree)
    return {
        "STATIC_GOVERNANCE": "PASS",
        "active_refs_checked": refs["active_refs_checked"],
        "verified_tombstones": hist["verified_tombstones"],
        "protected_reintroductions": deleted["reintroductions"],
        "REMOTE_ATTESTATION": "NOT_RUN",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--github-pr", action="store_true")
    opts.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=_ROOT)
    args = parser.parse_args(argv)
    try:
        result = _main_github(args.root) if args.github_pr else verify_repository_static(args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (SourceTruthError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, SourceTruthError) else "SOURCE_TRUTH_SCHEMA_INVALID"
        if not re.fullmatch(r"[A-Z0-9_]{3,128}(?::[A-Za-z0-9_./-]+)?", reason):
            reason = "SOURCE_TRUTH_VALIDATION_FAILED"
        print("HAZEWAVE_SOURCE_TRUTH=BLOCKED:" + reason, file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
