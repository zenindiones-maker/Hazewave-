"""Executable HAZEWAVE_HARNESS-owned research fixture dispatcher.

Unlike the catalog, this module actually invokes pinned REA or Iris on one
first-party immutable fixture, validates original tool output, and persists a
non-promoting 0600 receipt. It does NOT authorize third-party targets, live
sites, agent registration, or production actions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from hazewave.harness import (
    HazewaveTask, route_task, issue_authorization, validate_authorization,
)


class ResearchExecutionError(RuntimeError):
    pass


_ADMITTED = {
    "rea_owned_js": "research.visual.inspect",
    "iris_owned_page": "web.visual_regression",
}
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{3,79}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def build_owned_harness_task(kind: str, task_id: str):
    if kind not in _ADMITTED:
        raise ResearchExecutionError("FIXTURE_ONLY_OPERATION_ADMITTED")
    if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
        raise ResearchExecutionError("TASK_ID_INVALID")
    task = HazewaveTask(
        task_id=task_id,
        goal="First-party fixture capability qualification only: " + kind,
        required_capability=_ADMITTED[kind],
        requested_domain="WAVE",
    )
    try:
        decision = route_task(task)
        auth = validate_authorization(
            issue_authorization(decision),
            expected_task_id=task_id,
            expected_capability=_ADMITTED[kind],
        )
    except (ValueError, PermissionError) as exc:
        raise ResearchExecutionError("HARNESS_ROUTE_REJECTED") from exc
    return task, auth


def _checked_worktree(workspace: Path, expected_sha: str | None) -> tuple[Path, str]:
    if expected_sha is None or not _HEX40.fullmatch(expected_sha):
        raise ResearchExecutionError("REVIEWED_SHA_REQUIRED")
    workspace = workspace.resolve(strict=True)
    try:
        head = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            text=True, capture_output=True, timeout=8, check=True,
        ).stdout.strip()
        if head != expected_sha:
            raise ResearchExecutionError("GIT_HEAD_MISMATCH")
        dirty = subprocess.run(
            ["git", "-C", str(workspace), "status", "--porcelain", "--untracked-files=normal"],
            text=True, capture_output=True, timeout=8, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ResearchExecutionError("GIT_IDENTITY_UNAVAILABLE") from exc
    if dirty:
        raise ResearchExecutionError("WORKTREE_NOT_CLEAN")
    for name in ("pyproject.toml", "tests/fixtures/iris-proof.html",
                 "tests/fixtures/rea6-javascript-owned/package.json"):
        path = workspace / name
        if path.is_symlink() or not path.is_file():
            raise ResearchExecutionError("OWNED_FIXTURE_MISSING")
    return workspace, head


def _command(binary: Path, arguments: list[str], *, timeout: int = 90) -> str:
    path = Path(binary).expanduser().resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ResearchExecutionError("TOOL_BINARY_UNAVAILABLE")
    # Inherit only the minimum execution environment. Do not inject GitHub,
    # package registry, SSH, Telegram, API keys or personal secrets.
    env = {key: os.environ[key] for key in
           ("HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "DISPLAY",
            "XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "FONTCONFIG_PATH")
           if key in os.environ}
    env["NO_COLOR"] = "1"
    try:
        response = subprocess.run(
            [str(path), *arguments], capture_output=True, text=True,
            check=False, timeout=timeout, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResearchExecutionError("TOOL_PROCESS_TIMEOUT_OR_FAILURE") from exc
    if response.returncode != 0:
        raise ResearchExecutionError("TOOL_PROCESS_NONZERO")
    if len(response.stdout) > 10 * 1024 * 1024:
        raise ResearchExecutionError("TOOL_OUTPUT_TOO_LARGE")
    return response.stdout


def _binary_sha(binary: Path) -> str:
    h = hashlib.sha256()
    with Path(binary).resolve(strict=True).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _save_result(report: dict[str, Any], *, state_root: Path, workspace: Path) -> Path:
    from os import O_CREAT, O_EXCL, O_WRONLY
    root = Path(state_root).expanduser()
    repo = workspace.resolve(strict=True)
    if root.resolve(strict=False).is_relative_to(repo):
        raise ResearchExecutionError("STATE_ROOT_INSIDE_WORKSPACE")
    for path in (root, root / "research", root / "research" / "receipts"):
        if path.is_symlink():
            raise ResearchExecutionError("STATE_ROOT_UNSAFE")
    folder = root / "research" / "receipts"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    filename = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                + "-" + report.get("kind", "unknown") + "-" + str(os.getpid()) + ".json")
    path = folder / filename
    blob = (json.dumps(report, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    flags = O_WRONLY | O_CREAT | O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(blob)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def execute_owned_fixture(
    *,
    kind: str,
    task_id: str,
    workspace: Path,
    expected_sha: str | None,
    state_root: Path,
    rea_binary: Path | None = None,
    iris_binary: Path | None = None,
    chrome_binary: Path | None = None,
) -> dict[str, Any]:
    task, auth = build_owned_harness_task(kind, task_id)
    workspace, observed_sha = _checked_worktree(workspace, expected_sha)
    since = time.monotonic()
    if kind == "rea_owned_js":
        from hazewave.rea6_provider_conformance import (
            fixture_tree_sha, validate_javascript_probe
        )
        if rea_binary is None:
            raise ResearchExecutionError("REA_BINARY_REQUIRED")
        version = _command(rea_binary, ["--version"], timeout=12)
        if not re.search(r"(?<![0-9])6\.0\.0(?![0-9])", version):
            raise ResearchExecutionError("REA_BINARY_VERSION_MISMATCH")
        fixture = workspace / "tests" / "fixtures" / "rea6-javascript-owned"
        before = fixture_tree_sha(fixture)
        raw = _command(rea_binary, [
            "analyze-javascript-application", str(fixture), "--json"
        ], timeout=90)
        after = fixture_tree_sha(fixture)
        if before != after:
            raise ResearchExecutionError("REA_FIXTURE_MUTATED")
        try:
            measurements = validate_javascript_probe(json.loads(raw), fixture_sha256=before)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ResearchExecutionError("REA_RESULT_NOT_VERIFIED") from exc
        installed_version = "6.0.0"
        tool_digest = _binary_sha(rea_binary)
    else:
        from hazewave.iris_capture import capture_owned_fixture
        if iris_binary is None or chrome_binary is None:
            raise ResearchExecutionError("IRIS_BROWSER_REQUIRED")
        version = _command(iris_binary, ["--version"], timeout=12)
        if not re.search(r"(?<![0-9])0\.4\.1(?![0-9])", version):
            raise ResearchExecutionError("IRIS_BINARY_VERSION_MISMATCH")
        fixture = workspace / "tests" / "fixtures" / "iris-proof.html"
        before = hashlib.sha256(fixture.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="hazewave-harness-iris-owned-") as dir:
            output = Path(dir) / "observed.png"
            try:
                measurements = capture_owned_fixture(
                    workspace=workspace, iris_binary=iris_binary,
                    chrome_binary=chrome_binary, output=output,
                )
            except Exception as exc:
                raise ResearchExecutionError("IRIS_CAPTURE_NOT_VERIFIED") from exc
        after = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if before != after:
            raise ResearchExecutionError("IRIS_FIXTURE_MUTATED")
        installed_version = "0.4.1"
        tool_digest = _binary_sha(iris_binary)

    report = {
        "schema": "HazewaveHarnessExecutedResearchFixture/v1",
        "kind": kind,
        "task_id": task.task_id,
        "capability": task.required_capability,
        "domain": "WAVE",
        "harness_authority": auth.authority,
        "harness_authorization_id": auth.authorization_id,
        "authorization_scope": "FIRST_PARTY_FIXTURE_BOOTSTRAP_ONLY",
        "state": "OBSERVATION_ONLY",
        "provider_tool_sha256": tool_digest,
        "provider_version": installed_version,
        "reviewed_repo_sha": observed_sha,
        "source_fixture_sha256": before,
        "elapsed_ms": round((time.monotonic() - since) * 1000, 1),
        "measurements": measurements,
        "host_environment_label": os.environ.get("CODESPACE_NAME") or "NO_CODESPACE_IDENTITY",
        "host_identity_verified": False,
        "owner_signed_external_target": False,
        "agent_mcp_session_connected": False,
        "capability_plane_measured_ready": False,
        "production_approved": False,
        "stock_health": "NOT_TESTED",
        "limitations": ["Fixture-only Harness-initiated execution; no owner target grant, "
                        "independent host attestation or production approval."],
    }
    receipt = _save_result(report, state_root=state_root, workspace=workspace)
    report["receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m hazewave.harness_research_execution")
    p.add_argument("--kind", choices=list(_ADMITTED), required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--state-root", type=Path, required=True)
    p.add_argument("--rea", type=Path)
    p.add_argument("--iris", type=Path)
    p.add_argument("--chrome", type=Path)
    args = p.parse_args(argv)
    try:
        result = execute_owned_fixture(
            kind=args.kind, task_id=args.task_id, workspace=args.workspace,
            expected_sha=args.expected_sha, state_root=args.state_root,
            rea_binary=args.rea, iris_binary=args.iris,
            chrome_binary=args.chrome
        )
        print(json.dumps(result, sort_keys=True))
        print("HAZEWAVE_HARNESS_OWNED_EXECUTION=PASS")
        print("HAZEWAVE_EXTERNAL_TARGET_AND_AGENT_CONNECTION=NOT_PROVEN")
        return 0
    except (ResearchExecutionError, OSError, ValueError) as exc:
        print(f"HAZEWAVE_HARNESS_OWNED_EXECUTION=BLOCKED:{str(exc)}", file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
