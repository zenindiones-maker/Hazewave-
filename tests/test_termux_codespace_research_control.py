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
        "          printf '%s\\n' \"${FAKE_CODESPACE_STATE:-Shutdown}\" ;;\n"
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
    for token in ("--status", "--audit", "--start-existing",
                  "hazewave-zero-cost-4jxp45676rq6279xx",
                  "work/native-auto-synthesis-av-qa-v1",
                  "CODESPACE_STATE=Shutdown",
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
