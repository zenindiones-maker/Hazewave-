from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "freellmapi-provider-eligibility-v1.json"
SCHEMA_PATH = ROOT / "schemas" / "freellmapi-provider-eligibility-v1.schema.json"
DOC_REGISTRY_PATH = ROOT / "docs" / "DOCUMENTATION_REGISTRY_V2.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_governed_free_fabric_contract_files_are_registered() -> None:
    assert SCHEMA_PATH.is_file()
    assert REGISTRY_PATH.is_file()

    docs = _load(DOC_REGISTRY_PATH)["documents"]
    by_id = {entry["id"]: entry for entry in docs}

    assert by_id["adr-0006-governed-zero-cost-provider-fabric"]["status"] == "ACTIVE"
    assert (
        by_id["adr-0006-governed-zero-cost-provider-fabric"]["path"]
        == "docs/architecture/decisions/ADR-0006-governed-zero-cost-provider-fabric.md"
    )


def test_provider_eligibility_registry_validates_against_schema() -> None:
    schema = _load(SCHEMA_PATH)
    registry = _load(REGISTRY_PATH)

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(registry)

    assert registry["schema"] == "HazewaveProviderEligibilityRegistry/v1"
    assert registry["project_id"] == "HAZEWAVE"
    assert registry["authority"] == "HAZEWAVE_HARNESS"
    assert registry["provider_gateway"] == "FREELLMAPI"
    assert registry["paid_fallback"] == "FORBIDDEN"
    assert registry["unknown_cost"] == "DENY"


def test_registry_is_fail_closed_for_credentials_and_unknown_providers() -> None:
    registry = _load(REGISTRY_PATH)

    assert registry["default_policy"]["trust_lane"] == "QUARANTINED"
    assert registry["default_policy"]["enabled"] is False
    assert registry["default_policy"]["monetary_policy"] == "UNKNOWN_COST"

    providers = registry["providers"]
    assert providers

    for entry in providers:
        assert "CREDENTIAL" not in entry["allowed_data_classes"]
        if entry["monetary_policy"] != "ZERO_COST_VERIFIED":
            assert entry["enabled"] is False
        if entry["trust_lane"] == "QUARANTINED":
            assert entry["enabled"] is False


@pytest.mark.parametrize(
    "provider",
    ["kilo", "pollinations", "ovh", "aihorde"],
)
def test_registry_contains_reviewed_keyless_public_free_routes(provider: str) -> None:
    registry = _load(REGISTRY_PATH)
    by_provider = {entry["provider"]: entry for entry in registry["providers"]}

    entry = by_provider[provider]
    assert entry["enabled"] is True
    assert entry["trust_lane"] == "REMOTE_PUBLIC_FREE"
    assert entry["monetary_policy"] == "ZERO_COST_VERIFIED"
    assert entry["billing_overflow_policy"] == "HARD_STOP"
    assert entry["allowed_data_classes"] == ["PUBLIC"]


def test_registry_does_not_treat_generic_custom_endpoint_as_private_safe() -> None:
    registry = _load(REGISTRY_PATH)
    by_provider = {entry["provider"]: entry for entry in registry["providers"]}

    custom = by_provider["custom"]
    assert custom["trust_lane"] == "QUARANTINED"
    assert custom["enabled"] is False
    assert custom["requires_endpoint_attestation"] is True
