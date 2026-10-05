from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import os
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

    if receipt_schema == "Hazewave9RouterFreeAdmissionReceipt/v2":
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
        if not str(proof.get("response_sha256") or "").strip():
            return _deny("NINEROUTER_PROBE_RESPONSE_PROOF_MISSING", model_id=model)
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


def _receipt_ranked_models(
    receipt: dict[str, Any],
    *,
    capability_id: str = "reason.general",
) -> list[str]:
    admitted = [
        str(item)
        for item in (receipt.get("execution_admitted_models") or [])
        if isinstance(item, str)
    ]
    proofs = receipt.get("model_proofs")
    proofs = proofs if isinstance(proofs, dict) else {}

    ranked: list[tuple[tuple[int, int, str], str]] = []
    for model in admitted:
        proof = proofs.get(model)
        proof = proof if isinstance(proof, dict) else {}
        usage = proof.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        total_tokens = usage.get("total_tokens")
        latency_ms = proof.get("latency_ms")
        token_score = (
            int(total_tokens)
            if isinstance(total_tokens, int) and total_tokens >= 0
            else 1_000_000_000
        )
        latency_score = (
            int(latency_ms)
            if isinstance(latency_ms, (int, float)) and latency_ms >= 0
            else 1_000_000_000
        )
        reasoning_penalty = 0
        if capability_id == "reason.deep":
            reasoning_penalty = 0 if proof.get("reasoning_observed") is True else 1
        ranked.append(
            (
                (reasoning_penalty, token_score, latency_score, model),
                model,
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [model for _, model in ranked]


def build_9router_efficiency_status(
    *,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)

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

    return {
        **base,
        "receipt_schema": receipt.get("schema"),
        "fresh": fresh,
        "age_seconds": age_seconds,
        "catalog_model_count": len(receipt.get("catalog_discovered_models") or []),
        "admitted_model_count": len(receipt.get("execution_admitted_models") or []),
        "ranked_models": _receipt_ranked_models(receipt),
        "selection_policy": policy.get("selection", "EXACT_SINGLE_MODEL"),
        "rtk_enabled": policy.get("rtk_enabled", True),
        "headroom_enabled": policy.get("headroom_enabled", False),
        "combos_allowed": policy.get("combos_allowed", False),
        "stream": policy.get("stream", False),
    }


def rank_9router_models(
    *,
    authorization: HazewaveAuthorization,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_ADMISSION_RECEIPT_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
) -> list[str]:
    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)
    if receipt is None:
        return []

    ranked = _receipt_ranked_models(
        receipt,
        capability_id=authorization.capability_id,
    )
    allowed: list[str] = []
    for model in ranked:
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
    attempted_models: tuple[str, ...] = ()
    fallback_count: int = 0
    selection_mode: str = "exact"
    rtk_enabled: bool = True
    stream: bool = False


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
    transport: httpx.BaseTransport | None = None,
    max_fallbacks: int = 3,
) -> NineRouterExecutionResult:
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("NINEROUTER_PROMPT_REQUIRED")
    if max_tokens < 1 or max_tokens > 4096:
        raise ValueError("NINEROUTER_MAX_TOKENS_OUT_OF_RANGE")

    if max_fallbacks < 1 or max_fallbacks > 8:
        raise ValueError("NINEROUTER_MAX_FALLBACKS_OUT_OF_RANGE")

    if receipt is None:
        receipt = load_9router_admission_receipt(receipt_path)

    requested_model = str(model_id or "").strip()
    if requested_model == "auto":
        candidates = rank_9router_models(
            authorization=authorization,
            receipt=receipt,
            receipt_path=receipt_path,
            data_classification=data_classification,
            now=now,
        )[:max_fallbacks]
        if not candidates:
            raise NineRouterExecutionError("NINEROUTER_NO_ADMITTED_FREE_MODELS")
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

    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with httpx.Client(
            base_url=PINNED_ENDPOINT,
            timeout=timeout_seconds,
            transport=transport,
        ) as client:
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

                result: NineRouterExecutionResult | None = None
                last_error: NineRouterExecutionError | None = None
                attempted_models: list[str] = []
                for candidate_model in candidates:
                    attempted_models.append(candidate_model)
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "model": candidate_model,
                            "messages": [{"role": "user", "content": text}],
                            "max_tokens": max_tokens,
                            "stream": False,
                        },
                        headers={
                            "Accept": "application/json",
                            "User-Agent": "Hazewave/9router-governed-executor",
                        },
                    )
                    if response.status_code != 200:
                        error = NineRouterExecutionError(
                            f"NINEROUTER_COMPLETION_HTTP_{response.status_code}"
                        )
                        last_error = error
                        if requested_model == "auto" and response.status_code in {
                            429,
                            500,
                            502,
                            503,
                            504,
                        }:
                            continue
                        raise error
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        error = NineRouterExecutionError(
                            "NINEROUTER_COMPLETION_INVALID_JSON"
                        )
                        last_error = error
                        if requested_model == "auto":
                            continue
                        raise error from exc

                    content = str(
                        payload.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        or ""
                    ).strip()
                    if not content:
                        error = NineRouterExecutionError(
                            "NINEROUTER_COMPLETION_EMPTY"
                        )
                        last_error = error
                        if requested_model == "auto":
                            continue
                        raise error

                    usage = payload.get("usage")
                    usage = usage if isinstance(usage, dict) else {}

                    result = NineRouterExecutionResult(
                        status="PASS",
                        task_id=authorization.task_id,
                        authorization_id=authorization.authorization_id,
                        model_id=candidate_model,
                        content=content,
                        prompt_tokens=(
                            int(usage["prompt_tokens"])
                            if isinstance(usage.get("prompt_tokens"), int)
                            else None
                        ),
                        completion_tokens=(
                            int(usage["completion_tokens"])
                            if isinstance(usage.get("completion_tokens"), int)
                            else None
                        ),
                        total_tokens=(
                            int(usage["total_tokens"])
                            if isinstance(usage.get("total_tokens"), int)
                            else None
                        ),
                        attempted_models=tuple(attempted_models),
                        fallback_count=max(0, len(attempted_models) - 1),
                        selection_mode=("auto" if requested_model == "auto" else "exact"),
                        rtk_enabled=True,
                        stream=False,
                    )
                    break

                if result is None:
                    if last_error is not None:
                        raise last_error
                    raise NineRouterExecutionError(
                        "NINEROUTER_ALL_ADMITTED_FREE_MODELS_FAILED"
                    )
            finally:
                try:
                    _settings_request(
                        client,
                        "PATCH",
                        cli_token=token,
                        payload={
                            "requireApiKey": original_require_api_key,
                            "capacityAdapter": original_capacity_adapter,
                            "outboundProxyEnabled": original_outbound_proxy_enabled,
                            "rtkEnabled": original_rtk_enabled,
                            "headroomEnabled": original_headroom_enabled,
                        },
                    )
                except Exception as exc:  # fail closed if the global state cannot be restored
                    restore_error = exc

            if restore_error is not None:
                raise NineRouterExecutionError(
                    "NINEROUTER_SETTINGS_RESTORE_FAILED"
                ) from restore_error
            return result
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
