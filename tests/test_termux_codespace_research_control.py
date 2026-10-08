"""Regression suite for a safe Termux -> existing Hazewave Codespace controller."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "termux" / "hazewave-research-codespace-control.sh"


def _fake_gh(tmp_path: Path) -> dict[str, str]:
    binary = tmp_path / "gh"
    binary.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  auth) exit 0 ;;\n"
        "  api)\n"
        "    case \"$*\" in\n"
        "      *'/start'*) printf '{\"state\":\"Available\"}\\n' ;;\n"
        "      *'user/codespaces/hazewave-zero-cost-4jxp45676rq6279xx'*)\n"
        "          case \"$*\" in\n"
        "            *'.name'*) printf '%s\\n' \"${FAKE_CODESPACE_NAME:-hazewave-zero-cost-4jxp45676rq6279xx}\" ;;\n"
        "            *'.repository.full_name'*) printf '%s\\n' \"${FAKE_CODESPACE_REPO:-zenindiones-maker/Hazewave-}\" ;;\n"
        "            *) printf '%s\\n' \"${FAKE_CODESPACE_STATE:-Shutdown}\" ;;\n"
        "          esac ;;\n"
        "      *'git/ref/heads/work/provider-python-distribution-qualification-v1'*)\n"
        "          printf '%s\\n' 'f94b9aadd8ead34ed7c0157b645d8295e7fd07dd' ;;\n"
        "      *'git/ref/heads/work/research-codespace-identity-authenticated-v1'*)\n"
        "          printf '%s\\n' 'f94b9aadd8ead34ed7c0157b645d8295e7fd07dd' ;;\n"
        "      *'git/ref/heads/work/native-auto-synthesis-av-qa-v1'*)\n"
        "          printf '%s\\n' 'f94b9aadd8ead34ed7c0157b645d8295e7fd07dd' ;;\n"
        "      *) exit 44 ;;\n"
        "    esac ;;\n"
        "  codespace) echo 'FAKE_SSH_CALLED' >> \"${FAKE_MARKER_FILE:-/dev/null}\" ;;\n"
        "  *) exit 45 ;;\n"
        "esac\n"
    )
    binary.chmod(0o700)
    return {**os.environ, "PATH": f"{tmp_path}:{os.environ.get('PATH', '/usr/bin')}",
            "HOME": str(tmp_path), "FAKE_CODESPACE_STATE": "Shutdown"}


def test_script_syntax_and_explicit_existing_host_only() -> None:
    assert SCRIPT.is_file()
    data = SCRIPT.read_text()
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
    for token in ("--status", "--inventory", "--audit", "--start-existing",
                  "hazewave-zero-cost-4jxp45676rq6279xx",
                  "work/native-auto-synthesis-av-qa-v1",
                  'echo "CODESPACE_STATE=$state"',
                  "HAZEWAVE_FREE_COMPUTE_VERIFIED",
                  "CODESPACE_SHUTDOWN_START_REQUIRED",
                  "git -C \"$BASE\" worktree add --detach",
                  "HAZEWAVE_RESEARCH_AUDIT=INCOMPLETE",
                  "HAZEWAVE_RESEARCH_AUDIT=PASS"):
        assert token in data
    for forbidden in ("gh codespace create", "git reset --hard", "git push --force",
                      "gh codespace rebuild", "sudo ", "pkg install", "git -C \"$BASE\" checkout"):
        assert forbidden not in data


def test_shutdown_status_reports_without_waking(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    proc = subprocess.run(["bash", str(SCRIPT), "--status"], env=env, text=True,
                          capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "CODESPACE_STATE=Shutdown" in proc.stdout
    assert "CODESPACE_AUTO_START=FORBIDDEN" in proc.stdout


def test_shutdown_audit_is_fail_closed_before_ssh(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--audit"], env=env, text=True,
                          capture_output=True, timeout=15)
    assert proc.returncode == 20
    assert "CODESPACE_SHUTDOWN_START_REQUIRED" in proc.stderr
    assert not marker.exists()


def test_start_existing_requires_explicit_free_compute_verification(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    proc = subprocess.run(["bash", str(SCRIPT), "--start-existing"], env=env,
                          text=True, capture_output=True, timeout=15)
    assert proc.returncode == 20
    assert "FREE_COMPUTE_NOT_VERIFIED" in proc.stderr
    assert "CODESPACE_START_ATTEMPTED" not in proc.stdout


def test_start_existing_only_with_explicit_gate(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["HAZEWAVE_FREE_COMPUTE_VERIFIED"] = "YES"
    proc = subprocess.run(["bash", str(SCRIPT), "--start-existing"], env=env,
                          text=True, capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "CODESPACE_START_ATTEMPTED=EXISTING_ONLY" in proc.stdout
    assert "CODESPACE_NEW_MACHINE=FORBIDDEN" in proc.stdout


def test_available_host_inventory_does_not_need_paid_execution_override(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--inventory"], env=env,
                          text=True, capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "CODESPACE_STATE=Available" in proc.stdout
    assert marker.exists()


def test_heavy_research_audit_requires_verified_budget_even_if_host_is_running(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--audit"], env=env,
                          text=True, capture_output=True, timeout=15)
    assert proc.returncode == 20
    assert "FREE_COMPUTE_NOT_VERIFIED" in proc.stderr
    assert not marker.exists()


def test_authenticated_identity_rejects_wrong_repository_before_ssh(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["FAKE_CODESPACE_REPO"] = "unrelated/other"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--inventory"], env=env,
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 20
    assert "CODESPACE_CONTROL_PLANE_IDENTITY_MISMATCH" in proc.stderr
    assert not marker.exists()


def test_remote_session_guard_accepts_unset_name_only_in_codespace() -> None:
    data = SCRIPT.read_text()
    platform = next(line for line in data.splitlines()
                    if '[[ "${CODESPACES:-}" == "true" ]] ||' in line)
    named = next(line for line in data.splitlines()
                 if '[[ -z "${CODESPACE_NAME:-}" || "${CODESPACE_NAME}" == "$CS" ]]' in line)
    code = 'CS="hazewave-zero-cost-4jxp45676rq6279xx"\n' + platform + "\n" + named + "\necho REMOTE_GUARD=PASS\n"
    for name, platform, accepted in [
        (None, "true", True),
        ("hazewave-zero-cost-4jxp45676rq6279xx", "true", True),
        ("other-host", "true", False),
        (None, "false", False),
    ]:
        env = {**os.environ, "CODESPACES": platform}
        env.pop("CODESPACE_NAME", None)
        if name is not None:
            env["CODESPACE_NAME"] = name
        proc = subprocess.run(["bash", "-c", code], env=env,
                              capture_output=True, text=True, timeout=5)
        assert (proc.returncode == 0) is accepted
        if accepted:
            assert "REMOTE_GUARD=PASS" in proc.stdout


def test_downstream_guards_require_codespaces_context() -> None:
    for rel in (
        "scripts/codespaces/native-behavior-rea6-probe.sh",
        "scripts/codespaces/research-closed-loop-qualification.sh",
        "scripts/codespaces/harness-live-research-bridge.sh",
    ):
        script = (ROOT / rel).read_text()
        assert '[[ "${CODESPACES:-}" == "true" ]]' in script
        assert '[[ -z "${CODESPACE_NAME:-}" ||' in script
        assert subprocess.run(["bash", "-n", str(ROOT / rel)],
                              capture_output=True).returncode == 0

def test_exact_reviewed_followup_ref_is_allowed_without_new_machine(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["HAZEWAVE_RESEARCH_REF"] = "work/research-codespace-identity-authenticated-v1"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--inventory"], env=env,
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "REVIEWED_REF=work/research-codespace-identity-authenticated-v1" in proc.stdout
    assert marker.exists()


def test_unreviewed_ref_is_rejected_before_ssh(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["HAZEWAVE_RESEARCH_REF"] = "untrusted/branch"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--inventory"], env=env,
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 20
    assert "UNREVIEWED_RESEARCH_REF" in proc.stderr
    assert not marker.exists()


def test_inventory_receipt_discloses_local_fetch_worktree_and_log_writes() -> None:
    text = SCRIPT.read_text()
    assert "READ_ONLY_HOST_INVENTORY" not in text
    assert "NON_DESTRUCTIVE_HOST_INVENTORY_WITH_LOCAL_WORKTREE_AND_LOG_WRITES" in text
    assert 'git -C "$BASE" worktree add --detach' in text
    assert 'mkdir -p "$LOG"' in text
    assert subprocess.run(["bash", "-n", str(SCRIPT)],
                          capture_output=True).returncode == 0


def test_pinned_python_provider_branch_accepted_before_ssh(tmp_path: Path) -> None:
    env = _fake_gh(tmp_path)
    env["FAKE_CODESPACE_STATE"] = "Available"
    env["HAZEWAVE_RESEARCH_REF"] = "work/provider-python-distribution-qualification-v1"
    env["HAZEWAVE_RESEARCH_EXPECTED_SHA"] = "f94b9aadd8ead34ed7c0157b645d8295e7fd07dd"
    marker = tmp_path / "ssh.marker"
    env["FAKE_MARKER_FILE"] = str(marker)
    proc = subprocess.run(["bash", str(SCRIPT), "--inventory"], env=env,
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "REVIEWED_REF=work/provider-python-distribution-qualification-v1" in proc.stdout
    assert marker.exists()
