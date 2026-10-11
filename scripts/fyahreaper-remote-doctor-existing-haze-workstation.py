#!/usr/bin/env python3
"""Read-only diagnosis of the *existing* FYAHREAPER stage on the approved Codespace.

No Python packages installed, no REAPER commands modifying the project, no
reaper.ini edits, no REAPER restart, and no token, media or settings disclosure.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

APPROVED_CODESPACE = "hazewave-zero-cost-4jxp45676rq6279xx"
PIN = "63219f44dd9363f83c087d7b1424e395347eb36e"
REPO = Path("/workspaces/Hazewave-")
ROOT = Path.home() / ".local/share/hazewave/fyahreaper-remote"
SOURCE = ROOT / f"source-{PIN}" / "apps/fyahreaper_remote"
REAPER_BIN = Path("/home/vscode/.local/opt/reaper/7.82/REAPER/reaper")


def has_web_interface(ini: str, port: int = 2307) -> bool:
    # Same structure as python-reapy 0.10.0's config writer: csurf_N=HTTP 0 PORT ...
    expr = re.compile(r"^\s*csurf_\d+\s*=\s*HTTP\s+\d+\s+" + re.escape(str(port)) + r"(?:\s|$)", re.I | re.M)
    return bool(expr.search(ini))


def validate_source(source: Path) -> None:
    if source.parents[1].name != "source-" + PIN:
        raise ValueError("SOURCE_NOT_EXPECTED_RELEASE")
    if any(x.is_symlink() for x in (source, *source.parents)):
        raise ValueError("SOURCE_SYMLINK")
    if not source.is_dir():
        raise ValueError("STAGED_SOURCE_MISSING")
    for name in ("reahub_server.py", "reaper_bridge.py", "requirements.txt"):
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError("STAGED_SOURCE_INCOMPLETE")


def is_healthy(output: str) -> bool:
    try:
        data = json.loads(output)
        return isinstance(data, dict) and data.get("reaper_connected") is True and bool(data.get("reaper_version"))
    except (ValueError, TypeError):
        return False


def capture(cmd: list[str], *, cwd: Path | None = None, timeout: int = 8) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_identity() -> tuple[str, str]:
    head = capture(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    state = capture(["git", "-C", str(REPO), "status", "--porcelain=v1"])
    if not head or not state or head.returncode or state.returncode:
        raise ValueError("GIT_CHECKOUT_NOT_READABLE")
    return head.stdout.strip(), state.stdout


def run() -> int:
    if os.environ.get("CODESPACE_NAME") not in (None, "", APPROVED_CODESPACE):
        print("BLOCKED:WRONG_CODESPACE")
        return 3
    if not REPO.exists() or not REAPER_BIN.is_file():
        print("BLOCKED:APPROVED_WORKSTATION_FILES_MISSING")
        return 3
    try:
        validate_source(SOURCE)
        before = git_identity()
    except ValueError as exc:
        print("BLOCKED:" + str(exc))
        return 3

    env_python = ROOT / ".venv/bin/python"
    print("FYAHREAPER_STAGE_SOURCE=VERIFIED:" + PIN)
    processes = capture(["pgrep", "-u", str(os.getuid()), "-x", "reaper"])
    process_count = len(processes.stdout.strip().splitlines()) if processes and processes.returncode == 0 else 0
    print("FYAHREAPER_EXISTING_REAPER_PROCESS=" + ("PRESENT" if process_count else "NOT_DETECTED"))

    resource = Path.home() / ".config/REAPER"
    ini = resource / "reaper.ini"
    kb = resource / "reaper-kb.ini"
    try:
        config_text = ini.read_text(encoding="utf-8", errors="replace") if ini.is_file() else ""
        kb_text = kb.read_text(encoding="utf-8", errors="replace") if kb.is_file() else ""
    except OSError:
        config_text = kb_text = ""
    print("FYAHREAPER_REAPY_WEB_INTERFACE_CONFIG=" + ("PRESENT" if has_web_interface(config_text) else "NOT_DETECTED"))
    print("FYAHREAPER_REAPY_ACTION_REGISTRATION=" + ("PRESENT" if "activate_reapy_server" in kb_text else "NOT_DETECTED"))

    if not env_python.is_file():
        print("FYAHREAPER_WORKSTATION_PYTHON=NOT_INSTALLED")
        print("FYAHREAPER_REAPY_LIVE_READ=NOT_TESTED")
        next_action = "CREATE_ISOLATED_VENV_AND_INSTALL_REQUIREMENTS"
    else:
        import_check = capture([str(env_python), "-c", "import reapy, fastapi, uvicorn, pydantic"], timeout=8)
        packages_ready = import_check is not None and import_check.returncode == 0
        print("FYAHREAPER_WORKSTATION_PYTHON=" + ("READY" if packages_ready else "MISSING_DEPENDENCIES"))
        if not packages_ready:
            print("FYAHREAPER_REAPY_LIVE_READ=NOT_TESTED")
            next_action = "INSTALL_REQUIREMENTS_IN_EXISTING_VENV"
        else:
            probe = capture([str(env_python), "-c", "import json; from reaper_bridge import ReaperBridge; print(json.dumps(ReaperBridge().health()))"], cwd=SOURCE, timeout=8)
            ready = probe is not None and probe.returncode == 0 and is_healthy(probe.stdout.strip().splitlines()[-1] if probe.stdout.strip() else "")
            print("FYAHREAPER_REAPY_LIVE_READ=" + ("PASS" if ready else "NOT_READY"))
            next_action = "READY_FOR_AUTHENTICATED_REAHUB_SMOKE" if ready else "REAPY_CONFIGURATION_REQUIRES_OWNER_CONTROLLED_REAPER_RESTART"

    after = git_identity()
    preserved = before == after
    print("FYAHREAPER_ORIGINAL_HEAD_WIP_UNCHANGED=" + ("PASS" if preserved else "FAIL"))
    print("FYAHREAPER_REAPER_SESSION_RESTARTED=NO")
    print("FYAHREAPER_NEXT_ACTION=" + next_action)
    return 0 if preserved else 7


if __name__ == "__main__":
    sys.exit(run())
