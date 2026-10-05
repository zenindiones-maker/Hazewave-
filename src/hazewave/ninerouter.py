from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization

DEFAULT_ADMISSION_RECEIPT_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "free-admission.json"
)

PINNED_UPSTREAM_COMMIT = "a99cf57239ff778b61e434c2786009d5ed1c412c"
PINNED_ENDPOINT = "http://127.0.0.1:20128"
CATALOG_SOURCE = "https://opencode.ai/zen/v1/models"
MAX_RECEIPT_AGE = timedelta(hours=24)

_ALLOWED_CAPABILITIES = frozenset(
    {
        "reason.general",
        "reason.deep",
        "code.generate",
        "code.review",
    }
)
_ALLOWED_DATA_CLASSIFICATIONS = frozenset({"PUBLIC"})
_DEAD_FREE = frozenset({"deepseek-v4-flash-free"})


@dataclass(frozen=True)
class NineRouterAdmissionDecision:
    allowed: bool
    reason: str
    gateway: str = "9router"
    provider: str = "opencode"
    model_id: str | None = None
    zero_cost_verified: bool = False
    trust_lane: str = "REMOTE_PUBLIC_FREE"
    receipt_path: str | None = None
    schema: str = "Hazewave9RouterAdmissionDecision/v1"


def load_9router_admission_receipt(
    path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
) -> dict[str, Any] | None:
    target = Path(path).expanduser()
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _deny(reason: str, *, model_id: str | None) -> NineRouterAdmissionDecision:
    return NineRouterAdmissionDecision(
        allowed=False,
        reason=reason,
        model_id=model_id,
    )


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _looks_zero_cost_model(model_id: str) -> bool:
    if not model_id.startswith("oc/"):
        return False
    provider_model = model_id.removeprefix("oc/")
    if provider_model in _DEAD_FREE:
        return False
    return provider_model == "big-pickle" or provider_model.endswith("-free")


def evaluate_9router_admission(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
) -> NineRouterAdmissionDecision:
    model = str(model_id or "").strip()
    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)
    if receipt is None:
        return _deny("NINEROUTER_ADMISSION_RECEIPT_MISSING", model_id=model)

    try:
        validate_authorization(
            authorization,
            expected_task_id=authorization.task_id,
            expected_capability=authorization.capability_id,
        )
    except (PermissionError, ValueError):
        return _deny("HAZEWAVE_AUTHORIZATION_INVALID", model_id=model)

    if authorization.capability_id not in _ALLOWED_CAPABILITIES:
        return _deny("CAPABILITY_NOT_ALLOWED", model_id=model)

    classification = str(data_classification or "").strip().upper()
    if classification not in _ALLOWED_DATA_CLASSIFICATIONS:
        return _deny("DATA_CLASSIFICATION_NOT_ALLOWED", model_id=model)

    if not _looks_zero_cost_model(model):
        return _deny("MODEL_NOT_ZERO_COST_ELIGIBLE", model_id=model)

    if (
        receipt.get("schema") != "Hazewave9RouterFreeAdmissionReceipt/v1"
        or receipt.get("project_id") != PROJECT_ID
        or receipt.get("authority") != AUTHORITY
        or receipt.get("gateway") != "9router"
        or receipt.get("gateway_authority") != "NONE"
    ):
        return _deny("NINEROUTER_RECEIPT_AUTHORITY_INVALID", model_id=model)

    if (
        receipt.get("upstream_repository") != "decolua/9router"
        or receipt.get("upstream_commit") != PINNED_UPSTREAM_COMMIT
    ):
        return _deny("NINEROUTER_UPSTREAM_PIN_MISMATCH", model_id=model)

    if receipt.get("endpoint") != PINNED_ENDPOINT:
        return _deny("NINEROUTER_ENDPOINT_NOT_LOOPBACK_PINNED", model_id=model)

    if (
        receipt.get("provider") != "opencode"
        or receipt.get("provider_alias") != "oc"
        or receipt.get("catalog_source") != CATALOG_SOURCE
    ):
        return _deny("NINEROUTER_PROVIDER_RECEIPT_INVALID", model_id=model)

    policy = receipt.get("provider_policy")
    if not isinstance(policy, dict):
        return _deny("NINEROUTER_ZERO_COST_POLICY_MISSING", model_id=model)
    if (
        policy.get("has_free") is not True
        or policy.get("no_auth") is not True
        or policy.get("paid_fallback") != "FORBIDDEN"
        or policy.get("unknown_cost") != "DENY"
    ):
        return _deny("NINEROUTER_ZERO_COST_POLICY_INVALID", model_id=model)

    denylist = {str(item) for item in (policy.get("denylist") or [])}
    if model.removeprefix("oc/") in denylist:
        return _deny("MODEL_DENYLISTED", model_id=model)

    try:
        observed = _parse_time(str(receipt["observed_at"]))
        current = (
            _parse_time(now)
            if isinstance(now, str)
            else (now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc))
        )
    except (KeyError, TypeError, ValueError):
        return _deny("NINEROUTER_ADMISSION_RECEIPT_TIME_INVALID", model_id=model)

    if current < observed or current - observed > MAX_RECEIPT_AGE:
        return _deny("NINEROUTER_ADMISSION_RECEIPT_EXPIRED", model_id=model)

    discovered = {
        str(item) for item in (receipt.get("catalog_discovered_models") or [])
    }
    admitted = {
        str(item) for item in (receipt.get("execution_admitted_models") or [])
    }
    if model not in discovered:
        return _deny("MODEL_NOT_IN_PROVEN_CATALOG", model_id=model)
    if model not in admitted:
        return _deny("MODEL_NOT_EXECUTION_ADMITTED", model_id=model)

    probe = receipt.get("probe")
    if not isinstance(probe, dict):
        return _deny("NINEROUTER_PROBE_RECEIPT_MISSING", model_id=model)
    if probe.get("status") != "PASS" or probe.get("model") != model:
        return _deny("NINEROUTER_PROBE_NOT_BOUND_TO_MODEL", model_id=model)
    if probe.get("semantic_expected") != "HAZEWAVE_OK":
        return _deny("NINEROUTER_PROBE_SEMANTIC_PROOF_INVALID", model_id=model)
    if not str(probe.get("response_sha256") or "").strip():
        return _deny("NINEROUTER_PROBE_RESPONSE_PROOF_MISSING", model_id=model)

    attempts = probe.get("attempts")
    if not isinstance(attempts, list) or not any(
        isinstance(row, dict)
        and row.get("model") == model
        and row.get("status") == "semantic_pass"
        for row in attempts
    ):
        return _deny("NINEROUTER_SEMANTIC_PASS_MISSING", model_id=model)

    return NineRouterAdmissionDecision(
        allowed=True,
        reason="ALLOW",
        model_id=model,
        zero_cost_verified=True,
        receipt_path=str(Path(receipt_path).expanduser()),
    )
