from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "schemas/project-profile-v2.schema.json",
    "schemas/haze-state-v1.schema.json",
    "schemas/wave-state-v1.schema.json",
    "schemas/hazewave-asset-manifest-v1.schema.json",
    "config/project-profile-v2.json",
    "docs/DOCUMENTATION_REGISTRY_V2.json",
    "docs/architecture/DOCUMENTATION_GOVERNANCE_V1.md",
    "docs/architecture/decisions/ADR-0001-haze-wave-domain-boundary.md",
    "docs/architecture/decisions/ADR-0002-hazewave-harness.md",
    "docs/architecture/decisions/ADR-0003-immutable-termux-runtime.md",
    "docs/reference/HAZE_WAVE_STATE_CONTRACTS_V1.md",
    "docs/runbooks/TERMUX_RUNTIME_V1.md",
    "examples/contracts/haze-state-v1.example.json",
    "examples/contracts/wave-state-v1.example.json",
    "examples/contracts/hazewave-asset-manifest-v1.example.json",
    "scripts/validate_repository_contracts.py",
)


def test_governance_v2_required_artifacts_exist() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    assert missing == []


def test_project_profile_v2_is_project_local_and_machine_readable() -> None:
    profile = json.loads(
        (ROOT / "config" / "project-profile-v2.json").read_text(encoding="utf-8")
    )

    assert profile["schema"] == "ProjectProfile/v2"
    assert profile["project_id"] == "HAZEWAVE"
    assert profile["status"] == "DEVELOPMENT_ACCEPTED"
    assert profile["architecture_authority"]["authority_id"] == "hazewave_harness"
    assert profile["portfolio_authority"] == "NONE"
    assert set(profile["domains"]) == {"HAZE", "WAVE", "BRIDGE"}
    assert profile["domains"]["HAZE"]["responsibility"] == "sound"
    assert profile["domains"]["WAVE"]["responsibility"] == "image"
    assert profile["runtime_model"]["state_namespace"] == "hazewave"
    assert profile["freshness_policy"]["material_change_requires_revalidation"] is True


def test_hazewave_governance_is_self_contained() -> None:
    profile = json.loads(
        (ROOT / "config" / "project-profile-v2.json").read_text(encoding="utf-8")
    )
    assert profile["portfolio_authority"] == "NONE"
    assert profile["runtime_model"]["state_namespace"] == "hazewave"
    assert profile["runtime_model"]["config_namespace"] == "hazewave"
    assert profile["runtime_model"]["deploy_namespace"] == "hazewave"


def test_documentation_registry_has_unique_existing_typed_entries() -> None:
    registry = json.loads(
        (ROOT / "docs" / "DOCUMENTATION_REGISTRY_V2.json").read_text(encoding="utf-8")
    )

    assert registry["schema"] == "HazewaveDocumentationRegistry/v2"
    ids = [entry["id"] for entry in registry["documents"]]
    assert len(ids) == len(set(ids))

    allowed_types = {
        "AGENT_CONTRACT",
        "PROJECT_PROFILE",
        "PROJECT_POLICY",
        "CANON",
        "ARCHITECTURE_DECISION",
        "ARCHITECTURE_POLICY",
        "EXPLANATION",
        "REFERENCE",
        "RUNBOOK",
        "PUBLISHING_STANDARD",
        "PROJECT_SPEC",
    }
    allowed_authority = {"NORMATIVE", "CANONICAL", "OPERATIONAL", "EXPLANATORY"}
    allowed_status = {"ACTIVE", "DEVELOPMENT", "SUPERSEDED"}

    for entry in registry["documents"]:
        assert entry["type"] in allowed_types
        assert entry["authority"] in allowed_authority
        assert entry["status"] in allowed_status
        assert (ROOT / entry["path"]).is_file(), entry["path"]


def test_agents_v2_is_operational_not_just_descriptive() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for required in (
        "## Authority",
        "## Source-of-truth precedence",
        "## Setup",
        "## Test and validation commands",
        "## Domain routing",
        "## Data classification",
        "## Write rules",
        "## Stop conditions",
        "## Handoff contract",
    ):
        assert required in agents


def test_termux_runtime_binds_project_profile_v2() -> None:
    installer = (
        ROOT / "scripts" / "install_hazewave_termux_runtime.sh"
    ).read_text(encoding="utf-8")
    control = (
        ROOT / "scripts" / "hazewave_termux_control.sh"
    ).read_text(encoding="utf-8")

    assert "config/project-profile-v2.json" in installer
    assert "config/project-profile-v2.json" in control
    assert "config/project-profile-v1.json" not in installer
    assert "config/project-profile-v1.json" not in control


def test_repository_contract_validator_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_repository_contracts.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "HAZEWAVE_REPOSITORY_CONTRACTS=PASS" in completed.stdout
