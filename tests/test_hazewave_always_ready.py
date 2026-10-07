from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMUX = ROOT / "scripts" / "hazewave_reflex_termux_control.sh"
REMOTE = ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh"
RUNTIME = ROOT / "src" / "hazewave" / "reflex_shadow_runtime.py"
POST_START = ROOT / "scripts" / "codespaces" / "start-always-ready.sh"
DEVCONTAINER = ROOT / ".devcontainer" / "devcontainer.json"
INSTALLER = ROOT / "scripts" / "install_hazewave_always_ready_termux.sh"


def test_termux_ready_is_lazy_wake_not_keepalive() -> None:
    text = TERMUX.read_text(encoding="utf-8")
    assert "ready)" in text
    assert "ensure_codespace_available" in text
    assert '"/user/codespaces/$CS/start"' in text
    assert "run_remote reconcile" in text
    assert "gh codespace create" not in text
    assert "while true" not in text
    assert "sleep infinity" not in text


def test_remote_reconcile_is_detached_locked_and_bounded() -> None:
    text = REMOTE.read_text(encoding="utf-8")
    assert "reconcile()" in text
    assert "flock -w 30" in text
    assert 'nohup "$PYTHON_BIN" -m hazewave.reflex_latency server' in text
    assert "RESTART_WINDOW_SECONDS=900" in text
    assert "RESTART_BUDGET=3" in text
    assert "REFLEX_HEALTHY_RUNTIME_UNTRACKED" in text
    assert "pkill" not in text
    assert "killall" not in text
    assert "provider_authority" in text
    assert '"NONE"' in text


def test_post_start_reconciles_desktop_and_reflex() -> None:
    text = POST_START.read_text(encoding="utf-8")
    assert 'bash "$DESKTOP"' in text
    assert 'bash "$REFLEX" reconcile' in text
    assert "HAZEWAVE_WORKSTATION_READY=PASS" in text
    assert "while true" not in text
    assert "sleep infinity" not in text


def test_devcontainer_uses_always_ready_post_start() -> None:
    config = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))
    assert config["postStartCommand"] == "bash scripts/codespaces/start-always-ready.sh"
    assert config["hostRequirements"] == {
        "cpus": 2,
        "memory": "8gb",
        "storage": "32gb",
    }


def test_termux_entrypoint_installer_is_idempotent_and_scoped() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "HAZEWAVE_ALWAYS_READY_V1_BEGIN" in text
    assert "HAZEWAVE_ALWAYS_READY_V1_END" in text
    assert "project-shells.sh" in text
    assert "hazewave-reflex ready" in text
    assert "doctor_anchor_not_unique" in text
    assert "cp -p" in text
    assert "bash -n" in text
    assert "ln -sfn" in text
    assert "global_controller_path_occupied" in text
    assert ".bashrc" not in text


def test_runtime_audit_follows_active_candidate_ref() -> None:
    termux = TERMUX.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert 'export HAZEWAVE_REFLEX_CANDIDATE_REF="refs/remotes/origin/$REF"' in termux
    assert 'CANDIDATE_REF = os.getenv("HAZEWAVE_REFLEX_CANDIDATE_REF"' in runtime
    assert "work/hazewave-always-ready-v1" in termux


def test_reconcile_exposes_doctor_audit_on_failure() -> None:
    remote = REMOTE.read_text(encoding="utf-8")
    needle = '"$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE"'
    assert needle in remote
    reconcile = remote.split("reconcile() {", 1)[1].split("smoke() {", 1)[0]
    assert needle + " >/dev/null" not in reconcile


def test_detached_runtime_does_not_inherit_reconcile_lock_fd() -> None:
    remote = REMOTE.read_text(encoding="utf-8")
    reconcile = remote.split("reconcile() {", 1)[1].split("smoke() {", 1)[0]
    assert 'exec 9>"$SERVICE_LOCK_FILE"' in reconcile
    assert "flock -w 30 9" in reconcile
    assert '9>&- >"$SERVICE_LOG_FILE" 2>&1 < /dev/null &' in reconcile
