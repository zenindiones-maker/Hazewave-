from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import json
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "freellmapi-provider-eligibility-v1.json"
)


@dataclass(frozen=True)
class MediaEgressGrant:
    grant_id: str
    task_id: str
    authorization_id: str
    asset_digest: str
    provider: str
    model_pattern: str
    purpose: str
    modality: str
    rights_basis: str
    expires_at: str


@dataclass(frozen=True)
class ProviderEligibilityDecision:
    allowed: bool
    reason: str
    provider: str
    model_id: str
    trust_lane: str
    zero_cost_verified: bool
    media_egress_grant_id: str | None = None


def load_provider_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveProviderEligibilityRegistry/v1":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_SCHEMA_INVALID")
    if payload.get("project_id") != "HAZEWAVE":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_PROJECT_INVALID")
    if payload.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_AUTHORITY_INVALID")
    if payload.get("provider_gateway") != "FREELLMAPI":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_GATEWAY_INVALID")
    if payload.get("paid_fallback") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_PAID_FALLBACK_INVALID")
    if payload.get("unknown_cost") != "DENY":
        raise ValueError("HAZEWAVE_PROVIDER_REGISTRY_UNKNOWN_COST_INVALID")
    return payload


def _provider_entry(registry: dict[str, Any], provider: str) -> dict[str, Any]:
    wanted = str(provider or "").strip().casefold()
    for entry in registry.get("providers") or []:
        if str(entry.get("provider") or "").strip().casefold() == wanted:
            return dict(entry)
    default = dict(registry.get("default_policy") or {})
    default["provider"] = wanted
    return default


def _matches(patterns: list[str], value: str) -> bool:
    candidate = str(value or "")
    return any(fnmatchcase(candidate, str(pattern)) for pattern in patterns)


def _parse_time(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _deny(
    *,
    reason: str,
    provider: str,
    model_id: str,
    trust_lane: str,
) -> ProviderEligibilityDecision:
    return ProviderEligibilityDecision(
        allowed=False,
        reason=reason,
        provider=provider,
        model_id=model_id,
        trust_lane=trust_lane,
        zero_cost_verified=False,
    )


def _grant_matches(
    grant: MediaEgressGrant,
    *,
    task_id: str | None,
    authorization_id: str | None,
    asset_digest: str | None,
    provider: str,
    model_id: str,
    modality: str,
) -> bool:
    return all(
        (
            bool(grant.grant_id.strip()),
            grant.task_id == str(task_id or ""),
            grant.authorization_id == str(authorization_id or ""),
            grant.asset_digest == str(asset_digest or ""),
            grant.provider.casefold() == provider.casefold(),
            _matches([grant.model_pattern], model_id),
            grant.modality == modality,
            bool(grant.purpose.strip()),
            bool(grant.rights_basis.strip()),
        )
    )


def evaluate_provider_eligibility(
    *,
    provider: str,
    model_id: str,
    capability_id: str,
    modality: str,
    data_classification: str,
    registry: dict[str, Any] | None = None,
    media_grant: MediaEgressGrant | None = None,
    task_id: str | None = None,
    authorization_id: str | None = None,
    asset_digest: str | None = None,
    endpoint_attested: bool = False,
    now: str | None = None,
) -> ProviderEligibilityDecision:
    policy_registry = registry if registry is not None else load_provider_registry()
    provider_name = str(provider or "").strip().casefold()
    model = str(model_id or "").strip()
    capability = str(capability_id or "").strip()
    modality_name = str(modality or "").strip()
    classification = str(data_classification or "").strip().upper()

    entry = _provider_entry(policy_registry, provider_name)
    trust_lane = str(entry.get("trust_lane") or "QUARANTINED")

    if classification == "CREDENTIAL":
        return _deny(
            reason="CREDENTIAL_EGRESS_FORBIDDEN",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if trust_lane == "QUARANTINED" and not entry.get("enabled", False):
        return _deny(
            reason="PROVIDER_QUARANTINED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if entry.get("enabled") is not True:
        return _deny(
            reason="PROVIDER_DISABLED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if entry.get("requires_endpoint_attestation") is True and not endpoint_attested:
        return _deny(
            reason="ENDPOINT_ATTESTATION_REQUIRED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if entry.get("monetary_policy") != "ZERO_COST_VERIFIED":
        return _deny(
            reason="ZERO_COST_NOT_VERIFIED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if entry.get("billing_overflow_policy") != "HARD_STOP":
        return _deny(
            reason="BILLING_OVERFLOW_NOT_FAIL_CLOSED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    allowed_classes = [str(v).upper() for v in entry.get("allowed_data_classes") or []]
    if classification not in allowed_classes:
        return _deny(
            reason="DATA_CLASS_NOT_ALLOWED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if modality_name not in (entry.get("allowed_modalities") or []):
        return _deny(
            reason="MODALITY_NOT_ALLOWED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if not _matches(list(entry.get("allowed_capabilities") or []), capability):
        return _deny(
            reason="CAPABILITY_NOT_ALLOWED",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    if not _matches(list(entry.get("model_patterns") or []), model):
        return _deny(
            reason="MODEL_NOT_ZERO_COST_ELIGIBLE",
            provider=provider_name,
            model_id=model,
            trust_lane=trust_lane,
        )

    grant_id: str | None = None
    if classification == "PRIVATE_MEDIA" and trust_lane != "LOCAL_PRIVATE":
        if media_grant is None:
            return _deny(
                reason="MEDIA_EGRESS_GRANT_REQUIRED",
                provider=provider_name,
                model_id=model,
                trust_lane=trust_lane,
            )
        if not _grant_matches(
            media_grant,
            task_id=task_id,
            authorization_id=authorization_id,
            asset_digest=asset_digest,
            provider=provider_name,
            model_id=model,
            modality=modality_name,
        ):
            return _deny(
                reason="MEDIA_EGRESS_GRANT_MISMATCH",
                provider=provider_name,
                model_id=model,
                trust_lane=trust_lane,
            )
        current = _parse_time(now) if now is not None else datetime.now(timezone.utc)
        if _parse_time(media_grant.expires_at) <= current:
            return _deny(
                reason="MEDIA_EGRESS_GRANT_EXPIRED",
                provider=provider_name,
                model_id=model,
                trust_lane=trust_lane,
            )
        grant_id = media_grant.grant_id

    return ProviderEligibilityDecision(
        allowed=True,
        reason="ALLOW",
        provider=provider_name,
        model_id=model,
        trust_lane=trust_lane,
        zero_cost_verified=True,
        media_egress_grant_id=grant_id,
    )
