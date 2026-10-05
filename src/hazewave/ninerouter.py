from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

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
DEFAULT_EXECUTION_LOCK_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "execution.lock"
)
DEFAULT_ROUTE_HEALTH_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "route-health.json"
)

DEFAULT_9ROUTER_DATA_DIR = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "home"
    / ".9router"
)
CLI_TOKEN_SALT = "9r-cli-auth"

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

    receipt_schema = receipt.get("schema")
    if (
        receipt_schema not in {
            "Hazewave9RouterFreeAdmissionReceipt/v1",
            "Hazewave9RouterFreeAdmissionReceipt/v2",
            "Hazewave9RouterFreeAdmissionReceipt/v3",
        }
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

    if receipt_schema in {
        "Hazewave9RouterFreeAdmissionReceipt/v2",
        "Hazewave9RouterFreeAdmissionReceipt/v3",
    }:
        optimization_policy = receipt.get("optimization_policy")
        if not isinstance(optimization_policy, dict):
            return _deny("NINEROUTER_OPTIMIZATION_POLICY_MISSING", model_id=model)
        if (
            optimization_policy.get("stream") is not False
            or optimization_policy.get("rtk_enabled") is not True
            or optimization_policy.get("headroom_enabled") is not False
            or optimization_policy.get("combos_allowed") is not False
        ):
            return _deny("NINEROUTER_OPTIMIZATION_POLICY_INVALID", model_id=model)

        proofs = receipt.get("model_proofs")
        proof = proofs.get(model) if isinstance(proofs, dict) else None
        if not isinstance(proof, dict):
            return _deny("NINEROUTER_MODEL_PROOF_MISSING", model_id=model)
        if proof.get("status") != "semantic_pass":
            return _deny("NINEROUTER_SEMANTIC_PASS_MISSING", model_id=model)

        sample_count: int | None = None
        semantic_success_count: int | None = None
        benchmark_samples = proof.get("benchmark_samples")
        if isinstance(benchmark_samples, list) and benchmark_samples:
            sample_count = len(benchmark_samples)
            semantic_success_count = sum(
                1
                for row in benchmark_samples
                if isinstance(row, dict)
                and row.get("status") == "semantic_pass"
            )

        metrics = proof.get("metrics")
        if isinstance(metrics, dict):
            metric_samples = metrics.get("sample_count")
            metric_successes = metrics.get("semantic_success_count")
            if isinstance(metric_samples, int) and metric_samples >= 0:
                if sample_count is not None and metric_samples != sample_count:
                    return _deny(
                        "NINEROUTER_SEMANTIC_MAJORITY_PROOF_INCONSISTENT",
                        model_id=model,
                    )
                sample_count = metric_samples
            if isinstance(metric_successes, int) and metric_successes >= 0:
                if (
                    semantic_success_count is not None
                    and metric_successes != semantic_success_count
                ):
                    return _deny(
                        "NINEROUTER_SEMANTIC_MAJORITY_PROOF_INCONSISTENT",
                        model_id=model,
                    )
                semantic_success_count = metric_successes

        if (
            sample_count is not None
            and sample_count >= 3
            and (
                semantic_success_count is None
                or semantic_success_count < 2
            )
        ):
            return _deny(
                "NINEROUTER_SEMANTIC_MAJORITY_PROOF_MISSING",
                model_id=model,
            )

        if not str(proof.get("response_sha256") or "").strip():
            return _deny("NINEROUTER_PROBE_RESPONSE_PROOF_MISSING", model_id=model)

        if receipt_schema == "Hazewave9RouterFreeAdmissionReceipt/v3":
            lifecycle = receipt.get("model_lifecycle")
            lifecycle_row = (
                lifecycle.get(model) if isinstance(lifecycle, dict) else None
            )
            if not isinstance(lifecycle_row, dict):
                return _deny(
                    "NINEROUTER_ZERO_COST_VERIFICATION_MISSING",
                    model_id=model,
                )
            if (
                lifecycle_row.get("stage") != "ADMITTED"
                or lifecycle_row.get("zero_cost_verified") is not True
                or lifecycle_row.get("capacity_class")
                not in {"FREE_UNMETERED_OR_DYNAMIC", "FREE_QUOTA"}
            ):
                return _deny(
                    "NINEROUTER_ZERO_COST_VERIFICATION_MISSING",
                    model_id=model,
                )
    else:
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


def _empty_route_health() -> dict[str, Any]:
    return {
        "schema": "Hazewave9RouterRouteHealth/v1",
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "models": {},
    }


def load_9router_route_health(
    path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.is_file():
        return _empty_route_health()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_route_health()
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "Hazewave9RouterRouteHealth/v1"
        or payload.get("project_id") != PROJECT_ID
        or payload.get("authority") != AUTHORITY
        or not isinstance(payload.get("models"), dict)
    ):
        return _empty_route_health()
    return payload


def _write_route_health(
    store: dict[str, Any],
    path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    tmp.write_text(
        json.dumps(store, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    os.replace(tmp, target)
    target.chmod(0o600)


def _resolve_now(now: str | datetime | None) -> datetime:
    if isinstance(now, str):
        return _parse_time(now)
    if isinstance(now, datetime):
        value = now
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _record_route_health(
    *,
    model_id: str,
    status: str,
    transient_failure: bool,
    success: bool,
    path: Path | str,
    now: str | datetime | None,
    capability_id: str | None = None,
    latency_ms: int | None = None,
    total_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    retry_after_seconds: int | None = None,
) -> None:
    store = load_9router_route_health(path)
    models = store.setdefault("models", {})
    current = _resolve_now(now)
    existing = models.get(model_id)
    existing = existing if isinstance(existing, dict) else {}

    def ewma(previous: Any, observed: int | None) -> int | None:
        if observed is None or observed < 0:
            return previous if isinstance(previous, int) else None
        if not isinstance(previous, int) or previous < 0:
            return observed
        return int(round((previous * 0.65) + (observed * 0.35)))

    def update_row(
        current_row: dict[str, Any],
        *,
        apply_semantic_failure: bool,
    ) -> dict[str, Any]:
        row = dict(current_row)
        if success:
            row.update(
                {
                    "consecutive_transient_failures": 0,
                    "cooldown_until": None,
                    "retry_after_seconds": None,
                    "last_status": "PASS",
                    "attempt_count": int(row.get("attempt_count") or 0) + 1,
                    "success_count": int(row.get("success_count") or 0) + 1,
                    "failure_count": int(row.get("failure_count") or 0),
                    "ewma_latency_ms": ewma(
                        row.get("ewma_latency_ms"),
                        latency_ms,
                    ),
                    "ewma_total_tokens": ewma(
                        row.get("ewma_total_tokens"),
                        total_tokens,
                    ),
                    "last_reasoning_tokens": (
                        reasoning_tokens
                        if isinstance(reasoning_tokens, int)
                        else row.get("last_reasoning_tokens")
                    ),
                    "updated_at": current.isoformat(),
                }
            )
            return row

        if transient_failure:
            failures = int(row.get("consecutive_transient_failures") or 0) + 1
            exponential_seconds = min(900, 60 * (2 ** (failures - 1)))
            provider_seconds = (
                min(3600, retry_after_seconds)
                if isinstance(retry_after_seconds, int)
                and retry_after_seconds > 0
                else 0
            )
            cooldown_seconds = max(exponential_seconds, provider_seconds)
            row.update(
                {
                    "attempt_count": int(row.get("attempt_count") or 0) + 1,
                    "success_count": int(row.get("success_count") or 0),
                    "failure_count": int(row.get("failure_count") or 0) + 1,
                    "consecutive_transient_failures": failures,
                    "cooldown_until": (
                        current + timedelta(seconds=cooldown_seconds)
                    ).isoformat(),
                    "retry_after_seconds": (
                        provider_seconds if provider_seconds > 0 else None
                    ),
                    "last_status": status,
                    "last_failure_at": current.isoformat(),
                    "updated_at": current.isoformat(),
                }
            )
            return row

        if apply_semantic_failure:
            row.update(
                {
                    "attempt_count": int(row.get("attempt_count") or 0) + 1,
                    "success_count": int(row.get("success_count") or 0),
                    "failure_count": int(row.get("failure_count") or 0) + 1,
                    "last_status": status,
                    "last_failure_at": current.isoformat(),
                    "updated_at": current.isoformat(),
                }
            )
        return row

    # Global health tracks availability and successful runtime efficiency.
    # Semantic/content failures are capability-scoped so a model that is poor
    # at one task class does not contaminate every other capability.
    global_row = update_row(
        existing,
        apply_semantic_failure=False,
    )

    if capability_id:
        capabilities = global_row.get("capabilities")
        capabilities = (
            dict(capabilities) if isinstance(capabilities, dict) else {}
        )
        scoped_existing = capabilities.get(capability_id)
        scoped_existing = (
            scoped_existing if isinstance(scoped_existing, dict) else {}
        )
        capabilities[capability_id] = update_row(
            scoped_existing,
            apply_semantic_failure=True,
        )
        global_row["capabilities"] = capabilities

    models[model_id] = global_row
    _write_route_health(store, path)


def _model_in_active_cooldown(
    route_health: dict[str, Any],
    model_id: str,
    *,
    now: str | datetime | None,
) -> bool:
    models = route_health.get("models")
    models = models if isinstance(models, dict) else {}
    row = models.get(model_id)
    if not isinstance(row, dict):
        return False
    cooldown = row.get("cooldown_until")
    if not cooldown:
        return False
    try:
        return _parse_time(str(cooldown)) > _resolve_now(now)
    except ValueError:
        return False


def _proof_semantic_majority_valid(proof: dict[str, Any]) -> bool:
    benchmark_samples = proof.get("benchmark_samples")
    if isinstance(benchmark_samples, list) and len(benchmark_samples) >= 3:
        semantic_successes = sum(
            1
            for row in benchmark_samples
            if isinstance(row, dict)
            and row.get("status") == "semantic_pass"
        )
        if semantic_successes < 2:
            return False

    metrics = proof.get("metrics")
    if isinstance(metrics, dict):
        sample_count = metrics.get("sample_count")
        semantic_success_count = metrics.get("semantic_success_count")
        if (
            isinstance(sample_count, int)
            and sample_count >= 3
            and (
                not isinstance(semantic_success_count, int)
                or semantic_success_count < 2
            )
        ):
            return False
    return True


def _receipt_ranked_models(
    receipt: dict[str, Any],
    *,
    capability_id: str = "reason.general",
    route_health: dict[str, Any] | None = None,
    now: str | datetime | None = None,
) -> list[str]:
    admitted = [
        str(item)
        for item in (receipt.get("execution_admitted_models") or [])
        if isinstance(item, str)
    ]
    proofs = receipt.get("model_proofs")
    proofs = proofs if isinstance(proofs, dict) else {}
    health_models = (
        route_health.get("models")
        if isinstance(route_health, dict)
        else {}
    )
    health_models = health_models if isinstance(health_models, dict) else {}

    ranked: list[tuple[tuple[float, ...], str]] = []
    for model in admitted:
        proof = proofs.get(model)
        proof = proof if isinstance(proof, dict) else {}
        if not _proof_semantic_majority_valid(proof):
            continue
        metrics = proof.get("metrics")
        metrics = metrics if isinstance(metrics, dict) else {}
        usage = proof.get("usage")
        usage = usage if isinstance(usage, dict) else {}

        total_tokens = metrics.get("median_total_tokens")
        if not isinstance(total_tokens, int) or total_tokens < 0:
            total_tokens = usage.get("total_tokens")

        latency_ms = metrics.get("median_latency_ms")
        if not isinstance(latency_ms, (int, float)) or latency_ms < 0:
            latency_ms = proof.get("latency_ms")

        success_rate = metrics.get("semantic_success_rate")
        if not isinstance(success_rate, (int, float)):
            success_rate = 1.0
        success_rate = max(0.25, min(1.0, float(success_rate)))

        reasoning_tokens = metrics.get("median_reasoning_tokens")
        if not isinstance(reasoning_tokens, int):
            reasoning_tokens = usage.get("reasoning_tokens")
        reasoning_observed = (
            proof.get("reasoning_observed") is True
            or (
                isinstance(reasoning_tokens, int)
                and reasoning_tokens > 0
            )
        )

        global_health = health_models.get(model)
        global_health = (
            global_health if isinstance(global_health, dict) else {}
        )
        capabilities = global_health.get("capabilities")
        capabilities = capabilities if isinstance(capabilities, dict) else {}
        scoped_health = capabilities.get(capability_id)
        scoped_health = (
            scoped_health if isinstance(scoped_health, dict) else {}
        )
        health = (
            scoped_health
            if int(scoped_health.get("attempt_count") or 0) > 0
            else global_health
        )
        if int(health.get("success_count") or 0) > 0:
            live_tokens = health.get("ewma_total_tokens")
            live_latency = health.get("ewma_latency_ms")
            if isinstance(live_tokens, int) and live_tokens >= 0:
                total_tokens = live_tokens
            if isinstance(live_latency, int) and live_latency >= 0:
                latency_ms = live_latency
            live_reasoning = health.get("last_reasoning_tokens")
            if isinstance(live_reasoning, int) and live_reasoning > 0:
                reasoning_observed = True

        token_score = (
            float(total_tokens)
            if isinstance(total_tokens, int) and total_tokens >= 0
            else 1_000_000_000.0
        )
        latency_score = (
            float(latency_ms)
            if isinstance(latency_ms, (int, float)) and latency_ms >= 0
            else 1_000_000_000.0
        )
        balanced_score = (
            token_score * latency_score
        ) / (success_rate * success_rate)

        attempt_count = int(health.get("attempt_count") or 0)
        success_count = int(health.get("success_count") or 0)
        failure_count = int(health.get("failure_count") or 0)
        if attempt_count <= 0 and (success_count > 0 or failure_count > 0):
            attempt_count = success_count + failure_count

        reliability = 1.0
        if attempt_count > 0:
            observed_reliability = (
                (success_count + 2.0) / (attempt_count + 3.0)
            )
            failure_age_decay = 1.0
            last_failure_at = health.get("last_failure_at")
            if last_failure_at:
                try:
                    failure_age_hours = max(
                        0.0,
                        (
                            _resolve_now(now)
                            - _parse_time(str(last_failure_at))
                        ).total_seconds()
                        / 3600.0,
                    )
                    failure_age_decay = 2.0 ** (
                        -failure_age_hours / 6.0
                    )
                except ValueError:
                    failure_age_decay = 1.0

            if health.get("last_status") == "PASS":
                failure_age_decay = min(failure_age_decay, 0.35)

            reliability = 1.0 - (
                (1.0 - observed_reliability) * failure_age_decay
            )
            balanced_score = (
                balanced_score
                / max(0.25, reliability) ** 2
            )

        recent_failure_penalty = 1.0
        last_failure_at = health.get("last_failure_at")
        if last_failure_at and health.get("last_status") != "PASS":
            try:
                failure_age_hours = max(
                    0.0,
                    (
                        _resolve_now(now)
                        - _parse_time(str(last_failure_at))
                    ).total_seconds()
                    / 3600.0,
                )
                recent_failure_penalty = 1.0 + (
                    4.0 * (2.0 ** (-failure_age_hours / 2.0))
                )
            except ValueError:
                recent_failure_penalty = 2.0
            balanced_score *= recent_failure_penalty

        reasoning_penalty = 0.0
        if capability_id == "reason.deep":
            reasoning_penalty = 0.0 if reasoning_observed else 1.0

        ranked.append(
            (
                (
                    reasoning_penalty,
                    balanced_score,
                    latency_score,
                    token_score,
                    model,
                ),
                model,
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [model for _, model in ranked]


def build_9router_efficiency_status(
    *,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    route_health: dict[str, Any] | None = None,
    route_health_path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)
    if route_health is None:
        route_health = load_9router_route_health(route_health_path)

    base = {
        "schema": "Hazewave9RouterEfficiencyStatus/v1",
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "gateway": "9router",
        "gateway_authority": "NONE",
        "receipt_path": str(Path(receipt_path).expanduser()),
        "receipt_present": receipt is not None,
        "paid_fallback": "FORBIDDEN",
        "unknown_cost": "DENY",
    }
    if receipt is None:
        return {
            **base,
            "fresh": False,
            "catalog_model_count": 0,
            "admitted_model_count": 0,
            "ranked_models": [],
        }

    current = (
        _parse_time(now)
        if isinstance(now, str)
        else (
            now.astimezone(timezone.utc)
            if isinstance(now, datetime)
            else datetime.now(timezone.utc)
        )
    )
    try:
        observed = _parse_time(str(receipt["observed_at"]))
        fresh = current >= observed and current - observed <= MAX_RECEIPT_AGE
        age_seconds = max(0, int((current - observed).total_seconds()))
    except (KeyError, TypeError, ValueError):
        fresh = False
        age_seconds = None

    policy = receipt.get("optimization_policy")
    policy = policy if isinstance(policy, dict) else {}

    receipt_admitted = [
        str(item)
        for item in (receipt.get("execution_admitted_models") or [])
        if isinstance(item, str)
    ]
    proofs = receipt.get("model_proofs")
    proofs = proofs if isinstance(proofs, dict) else {}
    majority_invalid_models = [
        model
        for model in receipt_admitted
        if isinstance(proofs.get(model), dict)
        and not _proof_semantic_majority_valid(proofs[model])
    ]
    effective_ranked_models = _receipt_ranked_models(
        receipt,
        route_health=route_health,
        now=current,
    )

    health_models = route_health.get("models")
    health_models = health_models if isinstance(health_models, dict) else {}
    cooling_models = []
    for model, row in sorted(health_models.items()):
        if not isinstance(row, dict):
            continue
        if not _model_in_active_cooldown(route_health, model, now=current):
            continue
        cooling_models.append(
            {
                "model": model,
                "cooldown_until": row.get("cooldown_until"),
                "last_status": row.get("last_status"),
                "consecutive_transient_failures": int(
                    row.get("consecutive_transient_failures") or 0
                ),
            }
        )

    ranked_models_by_capability = {
        capability: _receipt_ranked_models(
            receipt,
            capability_id=capability,
            route_health=route_health,
            now=current,
        )
        for capability in (
            "reason.general",
            "reason.deep",
            "code.generate",
            "code.review",
        )
    }

    return {
        **base,
        "receipt_schema": receipt.get("schema"),
        "fresh": fresh,
        "age_seconds": age_seconds,
        "catalog_model_count": len(receipt.get("catalog_discovered_models") or []),
        "admitted_model_count": len(effective_ranked_models),
        "receipt_admitted_model_count": len(receipt_admitted),
        "effective_admitted_model_count": len(effective_ranked_models),
        "majority_invalid_models": majority_invalid_models,
        "ranked_models": effective_ranked_models,
        "ranked_models_by_capability": ranked_models_by_capability,
        "selection_policy": policy.get("selection", "EXACT_SINGLE_MODEL"),
        "rtk_enabled": policy.get("rtk_enabled", True),
        "headroom_enabled": policy.get("headroom_enabled", False),
        "combos_allowed": policy.get("combos_allowed", False),
        "stream": policy.get("stream", False),
        "cooling_model_count": len(cooling_models),
        "cooling_models": cooling_models,
    }


def rank_9router_models(
    *,
    authorization: HazewaveAuthorization,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    route_health: dict[str, Any] | None = None,
    route_health_path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
    context_profile: Any | None = None,
    capacity_state: dict[str, Any] | None = None,
) -> list[str]:
    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)
    if receipt is None:
        return []

    if route_health is None:
        route_health = load_9router_route_health(route_health_path)

    ranked = _receipt_ranked_models(
        receipt,
        capability_id=authorization.capability_id,
        route_health=route_health,
        now=now,
    )
    if context_profile is not None and capacity_state is not None:
        from hazewave.ninerouter_capacity import (
            contextual_cooldown_active,
            provider_circuit_active,
            quality_aware_model_score,
        )

        if provider_circuit_active(
            capacity_state,
            "opencode",
            now=now,
        ):
            return []

        ranked = sorted(
            ranked,
            key=lambda model: (
                -quality_aware_model_score(
                    capacity_state,
                    model,
                    context_profile,
                ),
                ranked.index(model),
            ),
        )

    allowed: list[str] = []
    for model in ranked:
        if _model_in_active_cooldown(
            route_health,
            model,
            now=now,
        ):
            continue
        if (
            context_profile is not None
            and capacity_state is not None
        ):
            from hazewave.ninerouter_capacity import contextual_cooldown_active
            if contextual_cooldown_active(
                capacity_state,
                model,
                context_profile,
                now=now,
            ):
                continue
        decision = evaluate_9router_admission(
            authorization=authorization,
            model_id=model,
            receipt=receipt,
            receipt_path=receipt_path,
            data_classification=data_classification,
            now=now,
        )
        if decision.allowed:
            allowed.append(model)
    return allowed


class NineRouterExecutionError(RuntimeError):
    """Raised when the governed 9Router execution boundary fails closed."""


@dataclass(frozen=True)
class NineRouterExecutionResult:
    status: str
    task_id: str
    authorization_id: str
    model_id: str
    content: str
    gateway: str = "9router"
    provider: str = "opencode"
    zero_cost_verified: bool = True
    schema: str = "Hazewave9RouterExecutionResult/v1"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    attempted_models: tuple[str, ...] = ()
    attempt_trace: tuple[dict[str, Any], ...] = ()
    fallback_count: int = 0
    selection_mode: str = "exact"
    rtk_enabled: bool = True
    stream: bool = False
    tool_calls: tuple[dict[str, Any], ...] = ()


def _opaque_session_hint(authorization: HazewaveAuthorization) -> str:
    digest = sha256(authorization.task_id.encode("utf-8")).hexdigest()[:32]
    return f"hz_{digest}"


def _derive_cli_token(data_dir: Path | str = DEFAULT_9ROUTER_DATA_DIR) -> str:
    root = Path(data_dir).expanduser()
    machine_file = root / "machine-id"
    secret_file = root / "auth" / "cli-secret"
    try:
        machine_id = machine_file.read_text(encoding="utf-8").strip()
        secret = secret_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise NineRouterExecutionError(
            "NINEROUTER_CLI_AUTH_MATERIAL_MISSING"
        ) from exc
    if not machine_id or not secret:
        raise NineRouterExecutionError("NINEROUTER_CLI_AUTH_MATERIAL_INVALID")
    return sha256(
        f"{machine_id}{CLI_TOKEN_SALT}{secret}".encode("utf-8")
    ).hexdigest()[:16]


def _disabled_capacity_adapters(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        str(key): {
            **(row if isinstance(row, dict) else {}),
            "enabled": False,
            "models": [],
        }
        for key, row in source.items()
    }


def _settings_request(
    client: httpx.Client,
    method: str,
    *,
    cli_token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(
        method,
        "/api/settings",
        headers={"x-9r-cli-token": cli_token},
        json=payload,
    )
    if response.status_code != 200:
        raise NineRouterExecutionError(
            f"NINEROUTER_SETTINGS_{method}_HTTP_{response.status_code}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise NineRouterExecutionError(
            "NINEROUTER_SETTINGS_RESPONSE_INVALID_JSON"
        ) from exc
    if not isinstance(body, dict):
        raise NineRouterExecutionError("NINEROUTER_SETTINGS_RESPONSE_INVALID")
    return body


def _validate_public_text_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("NINEROUTER_MESSAGES_REQUIRED")

    allowed_roles = {"system", "user", "assistant", "tool"}
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(messages):
        if not isinstance(raw, dict):
            raise ValueError(f"NINEROUTER_MESSAGES_INVALID_ITEM:{index}")
        role = str(raw.get("role") or "").strip()
        if role not in allowed_roles:
            raise ValueError(f"NINEROUTER_MESSAGES_INVALID_ROLE:{index}")

        message = dict(raw)
        content = message.get("content", "")
        if isinstance(content, str):
            pass
        elif isinstance(content, list):
            for part in content:
                if (
                    not isinstance(part, dict)
                    or part.get("type") not in {"text", "input_text"}
                    or not isinstance(part.get("text"), str)
                ):
                    raise ValueError(
                        f"NINEROUTER_MESSAGES_NON_TEXT_CONTENT:{index}"
                    )
        else:
            raise ValueError(f"NINEROUTER_MESSAGES_NON_TEXT_CONTENT:{index}")

        if role == "tool":
            if not str(message.get("tool_call_id") or "").strip():
                raise ValueError(
                    f"NINEROUTER_MESSAGES_TOOL_CALL_ID_REQUIRED:{index}"
                )
            if not isinstance(content, str):
                raise ValueError(
                    f"NINEROUTER_MESSAGES_TOOL_CONTENT_MUST_BE_TEXT:{index}"
                )

        tool_calls = message.get("tool_calls")
        if tool_calls is not None:
            if role != "assistant" or not isinstance(tool_calls, list):
                raise ValueError(
                    f"NINEROUTER_MESSAGES_TOOL_CALLS_INVALID:{index}"
                )
            for call in tool_calls:
                if not isinstance(call, dict):
                    raise ValueError(
                        f"NINEROUTER_MESSAGES_TOOL_CALLS_INVALID:{index}"
                    )

        normalized.append(message)
    return normalized


def _validate_tools(
    tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if tools is None:
        return None
    if not isinstance(tools, list) or not tools:
        raise ValueError("NINEROUTER_TOOLS_INVALID")
    if len(tools) > 128:
        raise ValueError("NINEROUTER_TOOLS_TOO_MANY")
    for item in tools:
        if not isinstance(item, dict):
            raise ValueError("NINEROUTER_TOOLS_INVALID")
    return [dict(item) for item in tools]


def _prepared_runtime_settings_safe(settings: dict[str, Any]) -> bool:
    if settings.get("requireApiKey") is not False:
        return False
    if any(
        settings.get(key) is True
        for key in ("cloudEnabled", "tunnelEnabled", "tailscaleEnabled")
    ):
        return False
    if settings.get("outboundProxyEnabled") is not False:
        return False
    if settings.get("rtkEnabled") is not True:
        return False
    if settings.get("headroomEnabled") is not False:
        return False

    adapters = settings.get("capacityAdapter")
    if adapters is None:
        return True
    if not isinstance(adapters, dict):
        return False
    for row in adapters.values():
        if not isinstance(row, dict):
            return False
        if row.get("enabled") is True:
            return False
        models = row.get("models")
        if models not in (None, []):
            return False
    return True


def _model_compatibility_from_receipt(
    receipt: dict[str, Any] | None,
    model_id: str,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        return {}
    lifecycle = receipt.get("model_lifecycle")
    row = lifecycle.get(model_id) if isinstance(lifecycle, dict) else None
    if not isinstance(row, dict):
        return {}
    compatibility = row.get("compatibility")
    return compatibility if isinstance(compatibility, dict) else {}


def execute_9router_messages(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
    max_tokens: int = 1024,
    timeout_seconds: float = 90.0,
    lock_path: Path | str = DEFAULT_EXECUTION_LOCK_PATH,
    cli_token: str | None = None,
    data_dir: Path | str = DEFAULT_9ROUTER_DATA_DIR,
    route_health_path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
    transport: httpx.BaseTransport | None = None,
    max_fallbacks: int = 3,
    prepared_runtime: bool = False,
    capacity_state_path: Path | str | None = None,
    task_family: str | None = None,
    reasoning_requirement: str | None = None,
    requested_reasoning_effort: str | None = None,
    requested_temperature: float | None = None,
) -> NineRouterExecutionResult:
    normalized_messages = _validate_public_text_messages(messages)
    normalized_tools = _validate_tools(tools)
    if max_tokens < 1 or max_tokens > 4096:
        raise ValueError("NINEROUTER_MAX_TOKENS_OUT_OF_RANGE")
    if max_fallbacks < 1 or max_fallbacks > 8:
        raise ValueError("NINEROUTER_MAX_FALLBACKS_OUT_OF_RANGE")
    if tool_choice is not None and not isinstance(tool_choice, (str, dict)):
        raise ValueError("NINEROUTER_TOOL_CHOICE_INVALID")

    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)

    profile = None
    capacity_state = None
    capacity_path = capacity_state_path
    if prepared_runtime:
        from hazewave.ninerouter_capacity import (
            DEFAULT_MAX_CAPACITY_STATE_PATH,
            build_task_context_profile,
            load_max_capacity_state,
        )

        if not isinstance(receipt, dict) or receipt.get("schema") != (
            "Hazewave9RouterFreeAdmissionReceipt/v3"
        ):
            raise NineRouterExecutionError(
                "NINEROUTER_PREPARED_RUNTIME_REQUIRES_V3_RECEIPT"
            )
        capacity_path = capacity_path or DEFAULT_MAX_CAPACITY_STATE_PATH
        profile = build_task_context_profile(
            capability_id=authorization.capability_id,
            messages=normalized_messages,
            tools=normalized_tools,
            task_family=task_family,
            reasoning_requirement=reasoning_requirement,
        )
        capacity_state = load_max_capacity_state(capacity_path)

    requested_model = str(model_id or "").strip()
    if requested_model == "auto":
        candidates = rank_9router_models(
            authorization=authorization,
            receipt=receipt,
            receipt_path=receipt_path,
            route_health_path=route_health_path,
            data_classification=data_classification,
            now=now,
            context_profile=profile,
            capacity_state=capacity_state,
        )[:max_fallbacks]
        if not candidates:
            raise NineRouterExecutionError(
                "NINEROUTER_NO_ADMITTED_FREE_MODELS"
            )
    else:
        decision = evaluate_9router_admission(
            authorization=authorization,
            model_id=requested_model,
            receipt=receipt,
            receipt_path=receipt_path,
            data_classification=data_classification,
            now=now,
        )
        if not decision.allowed:
            raise NineRouterExecutionError(decision.reason)
        candidates = [requested_model]

    token = cli_token or _derive_cli_token(data_dir)
    target_lock = Path(lock_path).expanduser()
    target_lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target_lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)

    def execute_candidates(client: httpx.Client) -> NineRouterExecutionResult:
        from hazewave.ninerouter_capacity import (
            acquire_capacity_lease,
            record_capacity_outcome,
            release_capacity_lease,
            safe_request_parameters,
        )

        result: NineRouterExecutionResult | None = None
        last_error: NineRouterExecutionError | None = None
        attempted_models: list[str] = []
        attempt_trace: list[dict[str, Any]] = []

        for candidate_model in candidates:
            attempted_models.append(candidate_model)
            fallback_used = len(attempted_models) > 1
            lease_id: str | None = None

            if prepared_runtime:
                assert profile is not None
                assert capacity_path is not None
                compatibility = _model_compatibility_from_receipt(
                    receipt,
                    candidate_model,
                )
                if not compatibility:
                    raise NineRouterExecutionError(
                        "NINEROUTER_MODEL_COMPATIBILITY_PROOF_MISSING"
                    )
                try:
                    lease_id = acquire_capacity_lease(
                        path=capacity_path,
                        provider="opencode",
                        model_id=candidate_model,
                        profile=profile,
                        now=now,
                        lease_ttl_seconds=max(
                            30,
                            int(timeout_seconds) + 30,
                        ),
                        wait_timeout_seconds=0,
                    )
                except RuntimeError as exc:
                    last_error = NineRouterExecutionError(str(exc))
                    if requested_model == "auto":
                        continue
                    raise last_error from exc

                request_body = safe_request_parameters(
                    model_id=candidate_model,
                    messages=normalized_messages,
                    profile=profile,
                    compatibility=compatibility,
                    requested_max_tokens=max_tokens,
                    tools=normalized_tools,
                    tool_choice=tool_choice,
                    requested_reasoning_effort=requested_reasoning_effort,
                    requested_temperature=requested_temperature,
                )
            else:
                request_body: dict[str, Any] = {
                    "model": candidate_model,
                    "messages": normalized_messages,
                    "max_tokens": max_tokens,
                    "stream": False,
                }
                if normalized_tools is not None:
                    request_body["tools"] = normalized_tools
                if tool_choice is not None:
                    request_body["tool_choice"] = tool_choice

            request_started = time.monotonic()
            try:
                try:
                    response = client.post(
                        "/v1/chat/completions",
                        json=request_body,
                        headers={
                            "Accept": "application/json",
                            "User-Agent": (
                                "Hazewave/9router-governed-executor"
                            ),
                            "x-session-id": _opaque_session_hint(
                                authorization
                            ),
                        },
                    )
                except httpx.TimeoutException as exc:
                    latency_ms = max(
                        0,
                        int(round(
                            (time.monotonic() - request_started) * 1000
                        )),
                    )
                    attempt_trace.append(
                        {
                            "model": candidate_model,
                            "status": "TIMEOUT",
                            "latency_ms": latency_ms,
                        }
                    )
                    _record_route_health(
                        model_id=candidate_model,
                        status="TIMEOUT",
                        transient_failure=True,
                        success=False,
                        path=route_health_path,
                        now=now,
                        capability_id=authorization.capability_id,
                    )
                    if prepared_runtime:
                        assert profile is not None
                        assert capacity_path is not None
                        record_capacity_outcome(
                            path=capacity_path,
                            provider="opencode",
                            model_id=candidate_model,
                            profile=profile,
                            status="TIMEOUT",
                            latency_ms=latency_ms,
                            fallback_used=fallback_used,
                            now=now,
                        )
                    error = NineRouterExecutionError(
                        "NINEROUTER_COMPLETION_TIMEOUT"
                    )
                    last_error = error
                    if requested_model == "auto":
                        continue
                    raise error from exc

                latency_ms = max(
                    0,
                    int(round(
                        (time.monotonic() - request_started) * 1000
                    )),
                )
                if response.status_code != 200:
                    status = f"HTTP_{response.status_code}"
                    attempt_trace.append(
                        {
                            "model": candidate_model,
                            "status": status,
                            "latency_ms": latency_ms,
                        }
                    )
                    transient = response.status_code in {
                        429,
                        500,
                        502,
                        503,
                        504,
                    }
                    retry_after_seconds = None
                    if response.status_code == 429:
                        retry_after_raw = response.headers.get("Retry-After")
                        try:
                            retry_after_seconds = int(
                                str(retry_after_raw).strip()
                            )
                        except (TypeError, ValueError):
                            retry_after_seconds = None
                    _record_route_health(
                        model_id=candidate_model,
                        status=status,
                        transient_failure=transient,
                        success=False,
                        path=route_health_path,
                        now=now,
                        capability_id=authorization.capability_id,
                        retry_after_seconds=retry_after_seconds,
                    )
                    if prepared_runtime:
                        assert profile is not None
                        assert capacity_path is not None
                        record_capacity_outcome(
                            path=capacity_path,
                            provider="opencode",
                            model_id=candidate_model,
                            profile=profile,
                            status=status,
                            latency_ms=latency_ms,
                            fallback_used=fallback_used,
                            retry_after_seconds=retry_after_seconds,
                            now=now,
                        )
                    error = NineRouterExecutionError(
                        f"NINEROUTER_COMPLETION_HTTP_{response.status_code}"
                    )
                    last_error = error
                    if requested_model == "auto" and transient:
                        continue
                    raise error

                try:
                    payload = response.json()
                except ValueError as exc:
                    attempt_trace.append(
                        {
                            "model": candidate_model,
                            "status": "INVALID_JSON",
                            "latency_ms": latency_ms,
                        }
                    )
                    _record_route_health(
                        model_id=candidate_model,
                        status="INVALID_JSON",
                        transient_failure=False,
                        success=False,
                        path=route_health_path,
                        now=now,
                        capability_id=authorization.capability_id,
                    )
                    if prepared_runtime:
                        assert profile is not None
                        assert capacity_path is not None
                        record_capacity_outcome(
                            path=capacity_path,
                            provider="opencode",
                            model_id=candidate_model,
                            profile=profile,
                            status="INVALID_JSON",
                            latency_ms=latency_ms,
                            fallback_used=fallback_used,
                            now=now,
                        )
                    error = NineRouterExecutionError(
                        "NINEROUTER_COMPLETION_INVALID_JSON"
                    )
                    last_error = error
                    if requested_model == "auto":
                        continue
                    raise error from exc

                choices = payload.get("choices")
                choices = choices if isinstance(choices, list) else []
                first_choice = (
                    choices[0]
                    if choices and isinstance(choices[0], dict)
                    else {}
                )
                message = first_choice.get("message")
                message = message if isinstance(message, dict) else {}
                content = str(message.get("content") or "").strip()
                raw_tool_calls = message.get("tool_calls")
                tool_calls = (
                    tuple(
                        dict(call)
                        for call in raw_tool_calls
                        if isinstance(call, dict)
                    )
                    if isinstance(raw_tool_calls, list)
                    else ()
                )
                if not content and not tool_calls:
                    attempt_trace.append(
                        {
                            "model": candidate_model,
                            "status": "EMPTY",
                            "latency_ms": latency_ms,
                        }
                    )
                    _record_route_health(
                        model_id=candidate_model,
                        status="EMPTY",
                        transient_failure=False,
                        success=False,
                        path=route_health_path,
                        now=now,
                        capability_id=authorization.capability_id,
                    )
                    if prepared_runtime:
                        assert profile is not None
                        assert capacity_path is not None
                        record_capacity_outcome(
                            path=capacity_path,
                            provider="opencode",
                            model_id=candidate_model,
                            profile=profile,
                            status="EMPTY",
                            latency_ms=latency_ms,
                            fallback_used=fallback_used,
                            now=now,
                        )
                    error = NineRouterExecutionError(
                        "NINEROUTER_COMPLETION_EMPTY"
                    )
                    last_error = error
                    if requested_model == "auto":
                        continue
                    raise error

                usage = payload.get("usage")
                usage = usage if isinstance(usage, dict) else {}
                details = usage.get("completion_tokens_details")
                details = details if isinstance(details, dict) else {}
                reasoning_tokens = usage.get("reasoning_tokens")
                if not isinstance(reasoning_tokens, int):
                    reasoning_tokens = details.get("reasoning_tokens")
                if not isinstance(reasoning_tokens, int):
                    reasoning_tokens = None
                prompt_tokens = (
                    int(usage["prompt_tokens"])
                    if isinstance(usage.get("prompt_tokens"), int)
                    else None
                )
                completion_tokens = (
                    int(usage["completion_tokens"])
                    if isinstance(usage.get("completion_tokens"), int)
                    else None
                )
                total_tokens = (
                    int(usage["total_tokens"])
                    if isinstance(usage.get("total_tokens"), int)
                    else None
                )

                attempt_trace.append(
                    {
                        "model": candidate_model,
                        "status": "PASS",
                        "latency_ms": latency_ms,
                        "total_tokens": total_tokens,
                        "reasoning_tokens": reasoning_tokens,
                    }
                )
                _record_route_health(
                    model_id=candidate_model,
                    status="PASS",
                    transient_failure=False,
                    success=True,
                    path=route_health_path,
                    now=now,
                    capability_id=authorization.capability_id,
                    latency_ms=latency_ms,
                    total_tokens=total_tokens,
                    reasoning_tokens=reasoning_tokens,
                )
                if prepared_runtime:
                    assert profile is not None
                    assert capacity_path is not None
                    record_capacity_outcome(
                        path=capacity_path,
                        provider="opencode",
                        model_id=candidate_model,
                        profile=profile,
                        status="PASS",
                        semantic_pass=None,
                        quality_score=None,
                        input_tokens=prompt_tokens,
                        output_tokens=completion_tokens,
                        reasoning_tokens=reasoning_tokens,
                        latency_ms=latency_ms,
                        fallback_used=fallback_used,
                        now=now,
                    )

                result = NineRouterExecutionResult(
                    status="PASS",
                    task_id=authorization.task_id,
                    authorization_id=authorization.authorization_id,
                    model_id=candidate_model,
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    reasoning_tokens=reasoning_tokens,
                    attempted_models=tuple(attempted_models),
                    attempt_trace=tuple(attempt_trace),
                    fallback_count=max(0, len(attempted_models) - 1),
                    selection_mode=(
                        "auto" if requested_model == "auto" else "exact"
                    ),
                    rtk_enabled=True,
                    stream=False,
                    tool_calls=tool_calls,
                )
                break
            finally:
                if prepared_runtime and lease_id is not None:
                    assert capacity_path is not None
                    release_capacity_lease(
                        path=capacity_path,
                        provider="opencode",
                        model_id=candidate_model,
                        lease_id=lease_id,
                    )

        if result is None:
            if last_error is not None:
                raise last_error
            raise NineRouterExecutionError(
                "NINEROUTER_ALL_ADMITTED_FREE_MODELS_FAILED"
            )
        return result

    try:
        with httpx.Client(
            base_url=PINNED_ENDPOINT,
            timeout=timeout_seconds,
            transport=transport,
        ) as client:
            if prepared_runtime:
                # Multiple prepared executions may share the settings lock,
                # while legacy executions require LOCK_EX before mutating
                # process-global 9Router settings. Holding LOCK_SH for the
                # whole provider call closes the check/use race without
                # serializing prepared requests.
                fcntl.flock(fd, fcntl.LOCK_SH)
                settings = _settings_request(
                    client,
                    "GET",
                    cli_token=token,
                )
                if not _prepared_runtime_settings_safe(settings):
                    raise NineRouterExecutionError(
                        "NINEROUTER_PREPARED_SETTINGS_UNSAFE"
                    )
                return execute_candidates(client)

            # Legacy lane keeps the existing whole-execution settings lock
            # and restore behavior for backwards compatibility.
            fcntl.flock(fd, fcntl.LOCK_EX)
            settings = _settings_request(
                client,
                "GET",
                cli_token=token,
            )
            if any(
                settings.get(key) is True
                for key in (
                    "cloudEnabled",
                    "tunnelEnabled",
                    "tailscaleEnabled",
                )
            ):
                raise NineRouterExecutionError(
                    "NINEROUTER_EXTERNAL_EXPOSURE_ENABLED"
                )

            original_require_api_key = settings.get("requireApiKey")
            original_capacity_adapter = settings.get("capacityAdapter")
            original_outbound_proxy_enabled = settings.get(
                "outboundProxyEnabled"
            )
            original_rtk_enabled = settings.get("rtkEnabled")
            original_headroom_enabled = settings.get("headroomEnabled")
            restore_error: Exception | None = None

            try:
                _settings_request(
                    client,
                    "PATCH",
                    cli_token=token,
                    payload={
                        "requireApiKey": False,
                        "capacityAdapter": _disabled_capacity_adapters(
                            original_capacity_adapter
                        ),
                        "outboundProxyEnabled": False,
                        "rtkEnabled": True,
                        "headroomEnabled": False,
                    },
                )
                result = execute_candidates(client)
            finally:
                try:
                    _settings_request(
                        client,
                        "PATCH",
                        cli_token=token,
                        payload={
                            "requireApiKey": original_require_api_key,
                            "capacityAdapter": original_capacity_adapter,
                            "outboundProxyEnabled": (
                                original_outbound_proxy_enabled
                            ),
                            "rtkEnabled": original_rtk_enabled,
                            "headroomEnabled": original_headroom_enabled,
                        },
                    )
                except Exception as exc:
                    restore_error = exc

            if restore_error is not None:
                raise NineRouterExecutionError(
                    "NINEROUTER_SETTINGS_RESTORE_FAILED"
                ) from restore_error
            return result
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(fd)

def execute_9router_text(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    prompt: str,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
    max_tokens: int = 1024,
    timeout_seconds: float = 90.0,
    lock_path: Path | str = DEFAULT_EXECUTION_LOCK_PATH,
    cli_token: str | None = None,
    data_dir: Path | str = DEFAULT_9ROUTER_DATA_DIR,
    route_health_path: Path | str = DEFAULT_ROUTE_HEALTH_PATH,
    transport: httpx.BaseTransport | None = None,
    max_fallbacks: int = 3,
) -> NineRouterExecutionResult:
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("NINEROUTER_PROMPT_REQUIRED")
    return execute_9router_messages(
        authorization=authorization,
        model_id=model_id,
        messages=[{"role": "user", "content": text}],
        receipt=receipt,
        receipt_path=receipt_path,
        data_classification=data_classification,
        now=now,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        lock_path=lock_path,
        cli_token=cli_token,
        data_dir=data_dir,
        route_health_path=route_health_path,
        transport=transport,
        max_fallbacks=max_fallbacks,
    )
