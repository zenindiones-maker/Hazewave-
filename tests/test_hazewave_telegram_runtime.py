from __future__ import annotations

import json
from pathlib import Path

import pytest

from hazewave.telegram_gateway import pairing_decision, runtime_status_payload

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "src/hazewave/telegram_gateway.py",
    "scripts/configure_hazewave_telegram.sh",
    "scripts/hazewave_telegram_control.sh",
    "scripts/install_hazewave_telegram_persistence.sh",
    "docs/architecture/decisions/ADR-0004-hazewave-telegram-runtime-isolation.md",
    "docs/runbooks/TELEGRAM_RUNTIME_V1.md",
)


def test_hazewave_telegram_runtime_artifacts_exist() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    assert missing == []


def test_pairing_requires_exact_local_code_then_binds_one_user() -> None:
    wrong = pairing_decision(
        configured_user_id=None,
        pairing_code="ABC12345",
        sender_user_id=101,
        text="/pair WRONG",
    )
    assert wrong.authorized is False
    assert wrong.pair_user_id is None

    paired = pairing_decision(
        configured_user_id=None,
        pairing_code="ABC12345",
        sender_user_id=101,
        text="/pair ABC12345",
    )
    assert paired.authorized is True
    assert paired.pair_user_id == 101

    owner = pairing_decision(
        configured_user_id=101,
        pairing_code="ABC12345",
        sender_user_id=101,
        text="/status",
    )
    assert owner.authorized is True
    assert owner.pair_user_id is None

    stranger = pairing_decision(
        configured_user_id=101,
        pairing_code="ABC12345",
        sender_user_id=202,
        text="/status",
    )
    assert stranger.authorized is False
    assert stranger.pair_user_id is None


@pytest.mark.parametrize("empty", ["", "   ", "/pair", "/pair    "])
def test_pairing_rejects_missing_code(empty: str) -> None:
    decision = pairing_decision(
        configured_user_id=None,
        pairing_code="ABC12345",
        sender_user_id=101,
        text=empty,
    )
    assert decision.authorized is False
    assert decision.pair_user_id is None


def test_runtime_status_is_exact_release_bound() -> None:
    sha = "a" * 40
    payload = runtime_status_payload(sha)
    assert payload["project_id"] == "HAZEWAVE"
    assert payload["authority"] == "HAZEWAVE_HARNESS"
    assert payload["runtime_sha"] == sha
    assert payload["telegram_bot_username"] == "HazewaveAgentBot"
    assert payload["portfolio_authority"] == "NONE"


def test_termux_telegram_scripts_are_hazewave_namespaced_and_immutable() -> None:
    configure = (ROOT / "scripts" / "configure_hazewave_telegram.sh").read_text(encoding="utf-8")
    control = (ROOT / "scripts" / "hazewave_telegram_control.sh").read_text(encoding="utf-8")
    installer = (ROOT / "scripts" / "install_hazewave_telegram_persistence.sh").read_text(encoding="utf-8")
    combined = "\n".join((configure, control, installer))

    assert ".config/hazewave/telegram" in combined
    assert ".local/state/hazewave/telegram" in combined
    assert ".local/share/hazewave/deploy/current" in combined
    assert "HazewaveAgentBot" in configure
    assert "read -r -s" in configure

    # Runtime control must execute from the immutable current release, not a
    # mutable developer checkout and not mutate Git to reconcile deployment.
    assert "Hazewave-dev" not in combined
    assert "git merge" not in control
    assert "git checkout" not in control
    assert "git pull" not in control


def test_telegram_token_is_never_a_repository_config_value() -> None:
    profile = json.loads(
        (ROOT / "config" / "project-profile-v2.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(profile)
    assert "TELEGRAM_BOT_TOKEN" not in serialized
    assert "bot-token" not in serialized


def test_documentation_registry_registers_telegram_runtime_docs() -> None:
    registry = json.loads(
        (ROOT / "docs" / "DOCUMENTATION_REGISTRY_V2.json").read_text(encoding="utf-8")
    )
    by_id = {item["id"]: item for item in registry["documents"]}

    assert by_id["adr-0004-hazewave-telegram-runtime"]["path"] == (
        "docs/architecture/decisions/ADR-0004-hazewave-telegram-runtime-isolation.md"
    )
    assert by_id["telegram-runtime-runbook-v1"]["path"] == "docs/runbooks/TELEGRAM_RUNTIME_V1.md"


def test_ci_validates_all_hazewave_telegram_shell_scripts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for script in (
        "scripts/configure_hazewave_telegram.sh",
        "scripts/hazewave_telegram_control.sh",
        "scripts/install_hazewave_telegram_persistence.sh",
    ):
        assert f"bash -n {script}" in workflow
