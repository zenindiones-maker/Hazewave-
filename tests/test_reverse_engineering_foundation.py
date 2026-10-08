from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from hazewave import cli
from hazewave.reverse_engineering import (
    ReverseEngineeringError,
    load_default_foundation,
)


ROOT = Path(__file__).resolve().parents[1]


def test_reverse_engineering_registry_is_zero_cost_evidence_first_and_domain_scoped() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")
    snapshot = foundation.snapshot()
    tools = {row["tool_id"]: row for row in snapshot["tools"]}

    assert snapshot["authority"] == "HAZEWAVE_HARNESS"
    assert snapshot["grants_execution_authority"] is False
    assert tools["rea"]["version"] == "4.1.0"
    assert tools["rea"]["source_repository"] == "morluto/rea"
    assert tools["rea"]["license_id"] == "MIT"
    assert tools["ghidra"]["version"] == "12.1.4"
    assert tools["ghidra"]["license_id"] == "Apache-2.0"
    assert tools["frida"]["version"] == "17.23.0"
    assert tools["rizin"]["version"] == "0.9.1"
    assert tools["renderdoc"]["version"] == "1.46"
    assert tools["spirv-tools"]["version"] == "2026.4"
    assert all(row["cost_class"] == "FREE_OPEN_SOURCE" for row in tools.values())
    assert all(row["grants_execution_authority"] is False for row in tools.values())


def test_haze_audio_plugin_investigation_uses_native_runtime_and_media_evidence() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    plan = foundation.plan(
        domain="HAZE",
        target_kind="audio_plugin",
        authorized=True,
        purpose="AUTHORIZED_FEATURE_STUDY",
    )

    assert plan["domain"] == "HAZE"
    assert plan["grants_execution_authority"] is False
    assert plan["tools"] == [
        "rea",
        "ghidra",
        "rizin",
        "frida",
        "ffmpeg",
        "mediainfo",
    ]
    assert plan["required_evidence"] == [
        "STATIC_INFERENCE",
        "MEASURED_BEHAVIOR",
        "RUNTIME_OBSERVATION",
        "REPRODUCED_BEHAVIOR",
    ]


def test_wave_shader_investigation_uses_frame_and_shader_tooling() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    plan = foundation.plan(
        domain="WAVE",
        target_kind="visual_shader",
        authorized=True,
        purpose="AUTHORIZED_FEATURE_STUDY",
    )

    assert plan["tools"] == [
        "rea",
        "renderdoc",
        "spirv-tools",
        "spirv-cross",
    ]
    assert plan["authority"] == "HAZEWAVE_HARNESS"


def test_bridge_is_translation_only_even_for_av_pipeline_investigation() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    plan = foundation.plan(
        domain="BRIDGE",
        target_kind="av_pipeline",
        authorized=True,
        purpose="INTEROPERABILITY",
    )

    assert plan["tools"] == ["rea", "ffmpeg", "mediainfo"]
    assert plan["domain_authority"] == "NONE"
    assert plan["grants_execution_authority"] is False


def test_reverse_engineering_fails_closed_without_target_authorization() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    with pytest.raises(
        ReverseEngineeringError,
        match="REVERSE_ENGINEERING_TARGET_AUTHORIZATION_REQUIRED",
    ):
        foundation.plan(
            domain="HAZE",
            target_kind="audio_plugin",
            authorized=False,
            purpose="AUTHORIZED_FEATURE_STUDY",
        )


@pytest.mark.parametrize(
    "purpose",
    [
        "UNAUTHORIZED_ACCESS",
        "CREDENTIAL_EXTRACTION",
        "DRM_BYPASS",
        "STEALTH_EVASION",
        "MALWARE_DEVELOPMENT",
        "EXFILTRATION",
    ],
)
def test_reverse_engineering_rejects_disallowed_purposes(purpose: str) -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    with pytest.raises(
        ReverseEngineeringError,
        match=f"REVERSE_ENGINEERING_PURPOSE_FORBIDDEN:{purpose}",
    ):
        foundation.plan(
            domain="WAVE",
            target_kind="web_visual",
            authorized=True,
            purpose=purpose,
        )


def test_policy_never_claims_original_source_recovery() -> None:
    policy = json.loads(
        (ROOT / "config" / "reverse-engineering-foundation-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert "ORIGINAL_SOURCE_RECOVERED" not in policy["evidence"]["allowed_claims"]
    assert policy["evidence"]["source_recovery_claim"] == "FORBIDDEN"


def test_codespace_installer_pins_rea_ghidra_frida_and_rizin_without_hopper() -> None:
    script = (
        ROOT / "scripts" / "codespaces" / "install-reverse-engineering-foundation.sh"
    ).read_text(encoding="utf-8")

    assert "rea-agents@4.1.0" in script
    assert "ghidra_12.1.4_PUBLIC_20260921.zip" in script
    assert "ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db" in script
    assert "frida==17.23.0" in script
    assert "frida-tools==14.11.0" in script
    assert "rizin-v0.9.1-static-x86_64.tar.xz" in script
    assert "9102249a9f0b6319c5334a2e5cf8d9cc3f2035e1d3def027c41f6a90f647e8cf" in script
    assert "REA_ANALYSIS_PROVIDER=ghidra" in script
    assert "GHIDRA_INSTALL_DIR=" in script
    assert "hopper" not in script.casefold()
    assert "chmod 600" in script
    assert "reverse-engineering-install-receipt.json" in script


def test_specialist_charter_machine_policy_adopts_reverse_engineering_domains() -> None:
    specialists = json.loads(
        (ROOT / "config" / "creative-specialists-v1.json").read_text(encoding="utf-8")
    )

    assert "audio_reverse_engineering" in specialists["domains"]["HAZE"]["includes"]
    assert "visual_reverse_engineering" in specialists["domains"]["WAVE"]["includes"]
    policy = specialists["reverse_engineering"]
    assert policy["required"] is True
    assert policy["policy_ref"] == "config/reverse-engineering-foundation-v1.json"
    assert policy["tool_authority"] == "NONE"
    assert policy["authorized_targets_only"] is True
    assert policy["runtime_mutation_authority"] is False


def test_hazewave_cli_exposes_authorized_reverse_engineering_plan(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hazewave",
            "reverse-engineering",
            "plan",
            "--domain",
            "HAZE",
            "--target-kind",
            "audio_plugin",
            "--purpose",
            "AUTHORIZED_FEATURE_STUDY",
            "--authorized",
        ],
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "HazewaveReverseEngineeringPlan/v1"
    assert payload["domain"] == "HAZE"
    assert payload["authorized_target"] is True
    assert payload["grants_execution_authority"] is False


def test_daily_intelligence_tracks_reverse_engineering_upstreams() -> None:
    registry = json.loads(
        (ROOT / "config" / "daily-intelligence-sources-v1.json").read_text(
            encoding="utf-8"
        )
    )
    sources = {row["source_id"]: row for row in registry["sources"]}

    expected = {
        "rea-upstream": {"HAZE", "WAVE"},
        "ghidra-upstream": {"HAZE", "WAVE"},
        "rizin-upstream": {"HAZE", "WAVE"},
        "frida-upstream": {"HAZE", "WAVE"},
        "mediainfo-upstream": {"HAZE", "WAVE"},
        "renderdoc-upstream": {"WAVE"},
        "spirv-tools-upstream": {"WAVE"},
        "spirv-cross-upstream": {"WAVE"},
    }
    for source_id, domains in expected.items():
        assert source_id in sources
        assert set(sources[source_id]["domains"]) == domains
        assert sources[source_id]["tier"] == "A_AUTHORITATIVE"
        assert sources[source_id]["data_classification"] == "PUBLIC"
