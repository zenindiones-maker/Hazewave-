from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "scripts" / "hazewave_freellmapi_control.sh"
PERSISTENCE = ROOT / "scripts" / "install_hazewave_freellmapi_persistence.sh"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_dead(pid: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)


def _read_pid(path: Path) -> int:
    return int(path.read_text(encoding="utf-8").strip())


def test_control_recovers_orphaned_lock_instead_of_staying_busy(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "control.lock").mkdir()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "FREELLMAPI_STATE_ROOT": str(state),
            "FREELLMAPI_CONFIG_ROOT": str(tmp_path / "config"),
            "FREELLMAPI_PROVIDER_ROOT": str(tmp_path / "provider"),
        }
    )

    result = subprocess.run(
        ["bash", str(CONTROL), "start"],
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 75, result.stderr
    assert "HAZEWAVE_FREELLMAPI_CONTROL=BUSY" not in result.stderr
    assert not (state / "control.lock").exists()


def test_boot_recovers_after_supervisor_sigkill_with_stale_pid_and_lock(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    deploy = tmp_path / "deploy"
    release = deploy / "releases" / "test-release"
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    home.mkdir(parents=True)

    fake_control = scripts / "hazewave_freellmapi_control.sh"
    fake_control.write_text(
        """#!/usr/bin/env bash
set -eu
case "${1:-status}" in
  status) exit 0 ;;
  restart) exit 0 ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    fake_control.chmod(0o700)
    (deploy / "current").symlink_to(release, target_is_directory=True)

    env = os.environ.copy()
    env.update({"HOME": str(home), "HAZEWAVE_DEPLOY_ROOT": str(deploy)})

    subprocess.run(
        ["bash", str(PERSISTENCE)],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )

    state = home / ".local" / "state" / "hazewave" / "providers" / "freellmapi"
    pid_file = state / "supervisor.pid"
    lock_dir = state / "supervisor.lock"
    boot = home / ".termux" / "boot" / "hazewave-freellmapi.sh"

    old_pid = _read_pid(pid_file)
    assert _pid_alive(old_pid)
    assert lock_dir.is_dir()

    new_pid: int | None = None
    try:
        os.kill(old_pid, signal.SIGKILL)
        _wait_dead(old_pid)

        assert lock_dir.is_dir(), "SIGKILL must reproduce a stale supervisor lock"

        subprocess.run(
            ["bash", str(boot)],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
            check=True,
        )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                candidate = _read_pid(pid_file)
            except (FileNotFoundError, ValueError):
                candidate = old_pid
            if candidate != old_pid and _pid_alive(candidate):
                new_pid = candidate
                break
            time.sleep(0.1)

        assert new_pid is not None, "boot did not replace the killed supervisor"
        assert lock_dir.is_dir()
    finally:
        for pid in {old_pid, new_pid}:
            if pid is not None and _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
