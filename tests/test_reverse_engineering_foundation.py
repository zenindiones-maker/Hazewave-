from __future__ import annotations

import json
from pathlib import Path

import pytest

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
