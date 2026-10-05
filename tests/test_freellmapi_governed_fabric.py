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


def _private_media_registry() -> dict:
    return {
        "schema": "HazewaveProviderEligibilityRegistry/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider_gateway": "FREELLMAPI",
        "paid_fallback": "FORBIDDEN",
        "unknown_cost": "DENY",
        "default_policy": {
            "enabled": False,
            "trust_lane": "QUARANTINED",
            "monetary_policy": "UNKNOWN_COST",
            "billing_overflow_policy": "UNKNOWN",
            "allowed_data_classes": [],
        },
        "providers": [
            {
                "provider": "safe-media",
                "enabled": True,
                "trust_lane": "REMOTE_INTERNAL_SAFE",
                "monetary_policy": "ZERO_COST_VERIFIED",
                "billing_overflow_policy": "HARD_STOP",
                "allowed_data_classes": ["PUBLIC", "INTERNAL_NON_SECRET", "PRIVATE_MEDIA"],
                "allowed_modalities": ["vision"],
                "allowed_capabilities": ["visual.analyze"],
                "model_patterns": ["vision-*"],
                "terms_status": "TEST",
                "privacy_status": "TEST",
                "requires_endpoint_attestation": False,
                "last_reviewed_at": "2026-10-04",
                "source_evidence": ["test://policy"],
            }
        ],
    }


def test_unknown_provider_is_denied_before_egress() -> None:
    from hazewave.provider_policy import evaluate_provider_eligibility

    decision = evaluate_provider_eligibility(
        provider="not-reviewed",
        model_id="model",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
    )

    assert decision.allowed is False
    assert decision.reason == "PROVIDER_QUARANTINED"
    assert decision.zero_cost_verified is False


def test_non_verified_zero_cost_provider_is_denied() -> None:
    from hazewave.provider_policy import evaluate_provider_eligibility

    decision = evaluate_provider_eligibility(
        provider="google",
        model_id="gemini-2.5-flash",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
    )

    assert decision.allowed is False
    assert decision.reason == "PROVIDER_DISABLED"
    assert decision.zero_cost_verified is False


def test_credentials_are_always_denied_even_for_enabled_provider() -> None:
    from hazewave.provider_policy import evaluate_provider_eligibility

    decision = evaluate_provider_eligibility(
        provider="kilo",
        model_id="free-model",
        capability_id="reason.general",
        modality="text",
        data_classification="CREDENTIAL",
    )

    assert decision.allowed is False
    assert decision.reason == "CREDENTIAL_EGRESS_FORBIDDEN"


def test_public_keyless_route_is_allowed_when_capability_and_modality_match() -> None:
    from hazewave.provider_policy import evaluate_provider_eligibility

    decision = evaluate_provider_eligibility(
        provider="kilo",
        model_id="some-free-model",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
    )

    assert decision.allowed is True
    assert decision.reason == "ALLOW"
    assert decision.trust_lane == "REMOTE_PUBLIC_FREE"
    assert decision.zero_cost_verified is True


def test_model_pattern_prevents_paid_openrouter_model_from_becoming_eligible() -> None:
    from hazewave.provider_policy import evaluate_provider_eligibility

    paid = evaluate_provider_eligibility(
        provider="openrouter",
        model_id="anthropic/claude-sonnet",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
    )
    free = evaluate_provider_eligibility(
        provider="openrouter",
        model_id="meta-llama/llama-3.3-70b:free",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
    )

    assert paid.allowed is False
    assert paid.reason == "MODEL_NOT_ZERO_COST_ELIGIBLE"
    assert free.allowed is True


def test_remote_private_media_requires_exact_scoped_grant() -> None:
    from hazewave.provider_policy import MediaEgressGrant, evaluate_provider_eligibility

    registry = _private_media_registry()
    base = dict(
        provider="safe-media",
        model_id="vision-1",
        capability_id="visual.analyze",
        modality="vision",
        data_classification="PRIVATE_MEDIA",
        registry=registry,
        task_id="task-7",
        authorization_id="auth-7",
        asset_digest="sha256:asset-7",
    )

    missing = evaluate_provider_eligibility(**base)
    assert missing.allowed is False
    assert missing.reason == "MEDIA_EGRESS_GRANT_REQUIRED"

    wrong_asset = MediaEgressGrant(
        grant_id="grant-wrong",
        task_id="task-7",
        authorization_id="auth-7",
        asset_digest="sha256:other",
        provider="safe-media",
        model_pattern="vision-*",
        purpose="visual analysis",
        modality="vision",
        rights_basis="OWNER_AUTHORIZED",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    denied = evaluate_provider_eligibility(**base, media_grant=wrong_asset)
    assert denied.allowed is False
    assert denied.reason == "MEDIA_EGRESS_GRANT_MISMATCH"

    valid = MediaEgressGrant(
        grant_id="grant-7",
        task_id="task-7",
        authorization_id="auth-7",
        asset_digest="sha256:asset-7",
        provider="safe-media",
        model_pattern="vision-*",
        purpose="visual analysis",
        modality="vision",
        rights_basis="OWNER_AUTHORIZED",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    allowed = evaluate_provider_eligibility(**base, media_grant=valid)
    assert allowed.allowed is True
    assert allowed.media_egress_grant_id == "grant-7"


def test_expired_private_media_grant_is_denied() -> None:
    from hazewave.provider_policy import MediaEgressGrant, evaluate_provider_eligibility

    grant = MediaEgressGrant(
        grant_id="grant-expired",
        task_id="task-8",
        authorization_id="auth-8",
        asset_digest="sha256:asset-8",
        provider="safe-media",
        model_pattern="vision-*",
        purpose="visual analysis",
        modality="vision",
        rights_basis="OWNER_AUTHORIZED",
        expires_at="2020-01-01T00:00:00+00:00",
    )

    decision = evaluate_provider_eligibility(
        provider="safe-media",
        model_id="vision-1",
        capability_id="visual.analyze",
        modality="vision",
        data_classification="PRIVATE_MEDIA",
        registry=_private_media_registry(),
        task_id="task-8",
        authorization_id="auth-8",
        asset_digest="sha256:asset-8",
        media_grant=grant,
        now="2026-10-04T21:00:00-03:00",
    )

    assert decision.allowed is False
    assert decision.reason == "MEDIA_EGRESS_GRANT_EXPIRED"
