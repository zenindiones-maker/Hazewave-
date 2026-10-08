from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from hazewave.harness_research_execution import (
    ResearchExecutionError, build_owned_harness_task, execute_owned_fixture,
)

ROOT = Path(__file__).resolve().parents[1]


def test_owned_rea_and_iris_task_binding_is_real_harness_authorization() -> None:
    for kind, cap in (("rea_owned_js", "research.visual.inspect"),
                      ("iris_owned_page", "web.visual_regression")):
        task, auth = build_owned_harness_task(kind, "owner-fixture-001")
        assert task.required_capability == cap
        assert task.requested_domain == "WAVE"
        assert auth.authority == "HAZEWAVE_HARNESS"
        assert auth.capability_id == cap


@pytest.mark.parametrize("kind", [
    "rea_arbitrary_file", "iris_live_site", "rea_native_untrusted",
    "iris_metadata_ip", "frida_attach", "haze_owner_voice",
])
def test_user_target_is_never_implicitly_admitted(kind: str) -> None:
    with pytest.raises(ResearchExecutionError, match="FIXTURE_ONLY"):
        build_owned_harness_task(kind, "owner-fixture-002")


@pytest.mark.parametrize("task_id", ["", "unsafe/../task", "spaced id", "a" * 129])
def test_research_task_id_must_be_bounded(task_id: str) -> None:
    with pytest.raises(ResearchExecutionError, match="TASK_ID_INVALID"):
        build_owned_harness_task("rea_owned_js", task_id)


def test_requires_exact_git_sha_and_immaculate_worktree_before_process(tmp_path: Path) -> None:
    with pytest.raises(ResearchExecutionError, match="REVIEWED_SHA_REQUIRED"):
        execute_owned_fixture(
            kind="rea_owned_js", task_id="owner-fixture-003",
            workspace=ROOT, expected_sha=None,
            state_root=tmp_path, rea_binary=Path("/unused"),
        )
    assert not list(tmp_path.rglob("*"))


def test_wrong_sha_blocks_before_tool_invocation(tmp_path: Path) -> None:
    with pytest.raises(ResearchExecutionError, match="GIT_HEAD_MISMATCH"):
        execute_owned_fixture(
            kind="rea_owned_js", task_id="owner-fixture-003",
            workspace=ROOT, expected_sha="0" * 40,
            state_root=tmp_path, rea_binary=Path("/unused"),
        )
    assert not list(tmp_path.rglob("*"))


def test_existing_script_adapters_are_called_not_replaced_with_fake_receipts() -> None:
    import inspect
    import hazewave.harness_research_execution as op
    code = inspect.getsource(op)
    assert "validate_javascript_probe" in code
    assert "capture_owned_fixture" in code
    assert "subprocess.run" in code
    assert "route_task" in code
    assert "issue_authorization" in code
    assert "validate_authorization" in code
    assert "OBSERVATION_ONLY" in code
    assert "production_approved" in code


def test_proof_execution_does_not_accept_arbitrary_urls_or_shell_commands() -> None:
    import inspect
    import hazewave.harness_research_execution as op
    code = inspect.getsource(op)
    assert "shell=True" not in code
    assert "curl | sh" not in code
    assert "gh codespace create" not in code
    assert "codex mcp add" not in code


def test_private_receipt_can_only_be_written_outside_git(tmp_path: Path) -> None:
    from hazewave.harness_research_execution import _save_result
    report = {"status": "OBSERVATION_ONLY", "production_approved": False}
    with pytest.raises(ResearchExecutionError, match="STATE_ROOT_INSIDE_WORKSPACE"):
        _save_result(report, state_root=ROOT / "tests" / "receipts", workspace=ROOT)
    file = _save_result(report, state_root=tmp_path / "private", workspace=ROOT)
    assert file.is_file()
    assert file.stat().st_mode & 0o077 == 0
    assert json.loads(file.read_text())["production_approved"] is False


def test_executed_rea_iris_subprocesses_strip_connected_secrets(monkeypatch):
    from hazewave.harness_research_execution import _tool_environment
    monkeypatch.setenv("GITHUB_TOKEN", "PRIVATE_TOKEN_MUST_NOT_TRAVEL")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SECRET")
    monkeypatch.setenv("OPENAI_API_KEY", "SECRET")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = _tool_environment()
    assert env["PATH"] == "/usr/bin"
    assert "GITHUB_TOKEN" not in env
    assert "TELEGRAM_BOT_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env


def test_iris_fixture_subprocess_supports_explicit_restricted_environment():
    import inspect
    from hazewave.iris_capture import capture_owned_fixture
    parameters = inspect.signature(capture_owned_fixture).parameters
    assert "process_env" in parameters
    import hazewave.harness_research_execution as module
    src = inspect.getsource(module)
    assert "process_env=_tool_environment()" in src
