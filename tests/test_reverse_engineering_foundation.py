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

    tools = foundation._route(domain="HAZE", target_kind="audio_plugin")
    assert foundation.authority == "HAZEWAVE_HARNESS"
    assert tools == [
        "rea",
        "ghidra",
        "rizin",
        "frida",
        "ffmpeg",
        "mediainfo",
    ]
    assert foundation.snapshot()["evidence"]["allowed_claims"] == [
        "STATIC_INFERENCE",
        "MEASURED_BEHAVIOR",
        "RUNTIME_OBSERVATION",
        "REPRODUCED_BEHAVIOR",
    ]


def test_wave_shader_investigation_uses_frame_and_shader_tooling() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    tools = foundation._route(domain="WAVE", target_kind="visual_shader")
    assert tools == [
        "rea",
        "renderdoc",
        "spirv-tools",
        "spirv-cross",
    ]
    assert foundation.authority == "HAZEWAVE_HARNESS"


def test_bridge_is_translation_only_even_for_av_pipeline_investigation() -> None:
    foundation = load_default_foundation(ROOT / "config" / "reverse-engineering-foundation-v1.json")

    tools = foundation._route(domain="BRIDGE", target_kind="av_pipeline")
    assert tools == ["rea", "ffmpeg", "mediainfo"]
    assert foundation._policy["domain_authority"]["BRIDGE"] == "NONE"
    assert foundation.snapshot()["grants_execution_authority"] is False


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



def test_codespace_installer_bootstraps_pinned_user_local_node_for_rea() -> None:
    script = (
        ROOT / "scripts" / "codespaces" / "install-reverse-engineering-foundation.sh"
    ).read_text(encoding="utf-8")

    assert 'NODE_VERSION="24.11.0"' in script
    assert 'NODE_ASSET="node-v24.11.0-linux-x64.tar.xz"' in script
    assert 'NODE_SHA256="46da9a098973ab7ba4fca76945581ecb2eaf468de347173897044382f10e0a0a"' in script
    assert 'https://nodejs.org/dist/v24.11.0/' in script
    assert 'NODE_ROOT="$ROOT/node-$NODE_VERSION"' in script
    assert 'export PATH="$NODE_ROOT/bin:$PATH"' in script
    assert 'for cmd in curl sha256sum tar python3; do' in script
    assert 'for cmd in curl sha256sum tar python3 npm node; do' not in script
    assert 'npm install --prefix "$stage" --no-audit --no-fund "rea-agents@4.1.0"' in script
    assert '"node": {"version_output": node_version, "pin": "24.11.0"' in script

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

    with pytest.raises(SystemExit) as rejected:
        cli.main()
    assert rejected.value.code == 2
    assert "required" in capsys.readouterr().err


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


def test_codespace_installer_avoids_head_sigpipe_under_pipefail() -> None:
    script = (
        ROOT / "scripts" / "codespaces" / "install-reverse-engineering-foundation.sh"
    ).read_text(encoding="utf-8")

    assert "| head -n 1" not in script
    assert "sed -n '1p'" in script


def test_codespace_installer_provisions_isolated_hazewave_cli_runtime() -> None:
    script = (
        ROOT / "scripts" / "codespaces" / "install-reverse-engineering-foundation.sh"
    ).read_text(encoding="utf-8")

    assert 'SCRIPT_DIR=' in script
    assert 'REPO_ROOT=' in script
    assert 'CLI_VENV="$ROOT/hazewave-cli-venv"' in script
    assert '"$CLI_VENV/bin/python" -m pip install' in script
    assert '-e "$REPO_ROOT"' in script
    assert 'export HAZEWAVE_RE_PYTHON="$CLI_VENV/bin/python"' in script
    assert 'export HAZEWAVE_RE_REPO_ROOT="$REPO_ROOT"' in script
    assert 'cat >"$BIN_ROOT/hazewave-re-cli"' in script
    assert 'exec env PYTHONPATH="$HAZEWAVE_RE_REPO_ROOT/src' in script
    assert '"$HAZEWAVE_RE_PYTHON" -m hazewave.cli reverse-engineering' in script


def test_reverse_engineering_doctor_checks_governed_hazewave_cli_runtime() -> None:
    script = (
        ROOT / "scripts" / "codespaces" / "reverse-engineering-doctor.sh"
    ).read_text(encoding="utf-8")

    assert 'HAZEWAVE_RE_PYTHON' in script
    assert 'hazewave-re-cli' in script
    assert '"$HAZEWAVE_RE_PYTHON" -c "import httpx"' in script
