from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
from typing import Any, Iterable


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "freellmapi-provider-eligibility-v1.json"
)

DEFAULT_ACCOUNT_ATTESTATION_PATH = (
    Path.home()
    / ".config"
    / "hazewave"
    / "providers"
    / "freellmapi"
    / "account-attestations.json"
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
    account_attestation_ids: tuple[str, ...] = ()


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


def _empty_account_attestation_store() -> dict[str, Any]:
    return {
        "schema": "HazewaveProviderAccountAttestationStore/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider_gateway": "FREELLMAPI",
        "attestations": [],
    }


def load_account_attestations(path: str | Path | None = None) -> dict[str, Any]:
    store_path = Path(path).expanduser() if path is not None else DEFAULT_ACCOUNT_ATTESTATION_PATH
    if not store_path.is_file():
        return _empty_account_attestation_store()

    payload = json.loads(store_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveProviderAccountAttestationStore/v1":
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_SCHEMA_INVALID")
    if payload.get("project_id") != "HAZEWAVE":
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_PROJECT_INVALID")
    if payload.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_AUTHORITY_INVALID")
    if payload.get("provider_gateway") != "FREELLMAPI":
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_GATEWAY_INVALID")
    if not isinstance(payload.get("attestations"), list):
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_ROWS_INVALID")
    return payload


def write_account_attestation(
    *,
    provider: str,
    credential_id: int,
    expires_at: str,
    source_evidence: list[str],
    path: str | Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Persist one human-verified free-tier account attestation.

    This function never reads or writes the provider credential itself. The
    binding is to FreeLLMAPI's local, non-secret api_keys.id only.
    """

    provider_name = str(provider or "").strip().casefold()
    key_id = int(credential_id)
    if key_id <= 0:
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_CREDENTIAL_ID_INVALID")

    registry = load_provider_registry()
    entry = _provider_entry(registry, provider_name)
    if not (
        entry.get("enabled") is True
        and entry.get("monetary_policy") == "ZERO_COST_REQUIRES_ACCOUNT_HARD_CAP"
        and entry.get("billing_overflow_policy") == "ACCOUNT_ATTESTATION_REQUIRED"
    ):
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_PROVIDER_NOT_ACCOUNT_BOUND")

    evidence = [str(value).strip() for value in source_evidence if str(value).strip()]
    if not evidence:
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_EVIDENCE_REQUIRED")

    issued = _parse_time(now) if now is not None else datetime.now(timezone.utc)
    expires = _parse_time(expires_at)
    if expires <= issued:
        raise ValueError("HAZEWAVE_ACCOUNT_ATTESTATION_EXPIRY_INVALID")

    record = {
        "attestation_id": (
            f"{provider_name}-key-{key_id}-"
            f"{issued.strftime('%Y%m%dT%H%M%SZ')}"
        ),
        "provider": provider_name,
        "credential_id": key_id,
        "account_tier": "FREE",
        "paid_billing_enabled": False,
        "billing_overflow_policy": "HARD_STOP",
        "evidence_method": "HUMAN_VERIFIED_PROVIDER_ACCOUNT",
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "source_evidence": evidence,
    }

    store_path = Path(path).expanduser() if path is not None else DEFAULT_ACCOUNT_ATTESTATION_PATH
    store = load_account_attestations(store_path)
    rows = [
        dict(row)
        for row in (store.get("attestations") or [])
        if not (
            isinstance(row, dict)
            and str(row.get("provider") or "").strip().casefold() == provider_name
            and row.get("credential_id") == key_id
        )
    ]
    rows.append(record)
    store["attestations"] = sorted(
        rows,
        key=lambda row: (
            str(row.get("provider") or ""),
            int(row.get("credential_id") or 0),
        ),
    )

    store_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(store_path.parent, 0o700)
    temp_path = store_path.with_name(f".{store_path.name}.tmp.{os.getpid()}")
    temp_path.write_text(
        json.dumps(store, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temp_path, 0o600)
    temp_path.replace(store_path)
    os.chmod(store_path, 0o600)
    return record


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


def _account_attestation_ids(
    *,
    provider: str,
    credential_ids: Iterable[int] | None,
    attestations: dict[str, Any] | None,
    now: str | None,
) -> tuple[tuple[str, ...] | None, str | None]:
    ids = tuple(sorted({int(value) for value in (credential_ids or ()) if int(value) > 0}))
    if not ids:
        return None, "ACCOUNT_ATTESTATION_REQUIRED"

    store = attestations if attestations is not None else load_account_attestations()
    rows = [
        dict(row)
        for row in (store.get("attestations") or [])
        if isinstance(row, dict)
        and str(row.get("provider") or "").strip().casefold() == provider.casefold()
    ]
    by_credential = {
        int(row["credential_id"]): row
        for row in rows
        if isinstance(row.get("credential_id"), int)
    }

    matched = [by_credential[key_id] for key_id in ids if key_id in by_credential]
    if not matched:
        return None, "ACCOUNT_ATTESTATION_REQUIRED"
    if len(matched) != len(ids):
        return None, "ACCOUNT_ATTESTATION_INCOMPLETE"

    current = _parse_time(now) if now is not None else datetime.now(timezone.utc)
    attestation_ids: list[str] = []
    for row in matched:
        if str(row.get("account_tier") or "").upper() != "FREE":
            return None, "ACCOUNT_TIER_NOT_FREE"
        if row.get("paid_billing_enabled") is not False:
            return None, "PAID_BILLING_ENABLED"
        if row.get("billing_overflow_policy") != "HARD_STOP":
            return None, "ACCOUNT_ATTESTATION_NOT_FAIL_CLOSED"

        issued = _parse_time(str(row.get("issued_at") or ""))
        expires = _parse_time(str(row.get("expires_at") or ""))
        if issued > current:
            return None, "ACCOUNT_ATTESTATION_NOT_YET_VALID"
        if expires <= current:
            return None, "ACCOUNT_ATTESTATION_EXPIRED"

        attestation_id = str(row.get("attestation_id") or "").strip()
        if not attestation_id:
            return None, "ACCOUNT_ATTESTATION_INVALID"
        attestation_ids.append(attestation_id)

    return tuple(sorted(attestation_ids)), None


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
    credential_ids: Iterable[int] | None = None,
    attestations: dict[str, Any] | None = None,
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

    monetary_policy = str(entry.get("monetary_policy") or "")
    billing_policy = str(entry.get("billing_overflow_policy") or "")
    account_ids: tuple[str, ...] = ()

    if monetary_policy == "ZERO_COST_VERIFIED":
        if billing_policy != "HARD_STOP":
            return _deny(
                reason="BILLING_OVERFLOW_NOT_FAIL_CLOSED",
                provider=provider_name,
                model_id=model,
                trust_lane=trust_lane,
            )
    elif (
        monetary_policy == "ZERO_COST_REQUIRES_ACCOUNT_HARD_CAP"
        and billing_policy == "ACCOUNT_ATTESTATION_REQUIRED"
    ):
        resolved_ids, reason = _account_attestation_ids(
            provider=provider_name,
            credential_ids=credential_ids,
            attestations=attestations,
            now=now,
        )
        if reason is not None:
            return _deny(
                reason=reason,
                provider=provider_name,
                model_id=model,
                trust_lane=trust_lane,
            )
        account_ids = resolved_ids or ()
    else:
        return _deny(
            reason="ZERO_COST_NOT_VERIFIED",
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
        account_attestation_ids=account_ids,
    )
