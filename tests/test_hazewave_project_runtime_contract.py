from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_profile_declares_haze_wave_and_bridge_with_project_local_authority() -> None:
    profile = json.loads(
        (ROOT / "config" / "project-profile-v2.json").read_text(encoding="utf-8")
    )

    assert profile["project_id"] == "HAZEWAVE"
    assert profile["architecture_authority"]["authority_id"] == "hazewave_harness"
    assert set(profile["domains"]) == {"HAZE", "WAVE", "BRIDGE"}
    assert profile["domains"]["HAZE"]["responsibility"] == "sound"
    assert profile["domains"]["WAVE"]["responsibility"] == "image"
    assert profile["portfolio_authority"] == "NONE"


def test_termux_runtime_is_project_namespaced_and_immutable() -> None:
    control = (ROOT / "scripts" / "hazewave_termux_control.sh").read_text(encoding="utf-8")
    installer = (
        ROOT / "scripts" / "install_hazewave_termux_runtime.sh"
    ).read_text(encoding="utf-8")

    combined = control + "\n" + installer

    assert ".local/share/hazewave/deploy" in combined
    assert ".local/state/hazewave" in combined
    assert ".config/hazewave" in combined
    assert "releases" in combined
    assert "current" in combined
    assert "config/project-profile-v2.json" in combined


def test_agents_contract_keeps_hazewave_project_local() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Hazewave Harness" in agents
    assert "HAZE" in agents
    assert "WAVE" in agents
    assert "portfolio layer has authority=NONE" in agents
    assert "External bots" in agents
