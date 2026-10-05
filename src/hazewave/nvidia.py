from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Callable

import httpx

from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization
from hazewave.provider_runtime import (
    FREE_DEVELOPMENT_ENDPOINT,
    HazewaveProviderExecutionResult,
)
from hazewave.nvidia_optimization import (
    FAST_CODE,
    DEEP_MEDIUM,
    DEEP_HARD,
    DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
    acquire_nvidia_capacity,
    evaluate_model_lifecycle,
    release_nvidia_capacity,
    update_nvidia_concurrency,
)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
DEFAULT_NVIDIA_SECRET_PATH = (
    Path.home() / ".config" / "hazewave" / "secrets" / "nvidia.env"
)
DEFAULT_NVIDIA_ADMISSION_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "nvidia-provider-admission-v1.json"
)

FAST_STRUCTURED = "FAST_STRUCTURED"
# Legacy profile kept for durable receipt compatibility. New routing should use
# DEEP_MEDIUM/DEEP_HARD selected from task complexity instead.
DEEP_REASONING = "DEEP_REASONING"

_ALLOWED_CAPABILITIES = frozenset(
    {"reason.general", "reason.deep", "code.generate", "code.review"}
)
_PROFILE_CAPABILITIES = {
    FAST_STRUCTURED: frozenset(
        {"reason.general", "reason.deep", "code.generate", "code.review"}
    ),
    FAST_CODE: frozenset({"code.generate", "code.review"}),
    DEEP_MEDIUM: frozenset(
        {"reason.general", "reason.deep", "code.generate", "code.review"}
    ),
    DEEP_HARD: frozenset(
        {"reason.general", "reason.deep", "code.generate", "code.review"}
    ),
    DEEP_REASONING: frozenset(
        {"reason.deep", "reason.general", "code.generate", "code.review"}
    ),
}
_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    FAST_STRUCTURED: {
        "max_tokens": 1024,
        "enable_thinking": False,
    },
    FAST_CODE: {
        "max_tokens": 2048,
        "enable_thinking": False,
    },
    DEEP_MEDIUM: {
        "max_tokens": 4096,
        "enable_thinking": True,
        "reasoning_budget": 512,
    },
    DEEP_HARD: {
        "max_tokens": 8192,
        "enable_thinking": True,
        "reasoning_budget": 2048,
    },
    DEEP_REASONING: {
        "max_tokens": 4096,
        "enable_thinking": True,
        "reasoning_budget": 2048,
    },
}

_CAPABILITY_MAX_TOKENS = {
    "reason.general": 1024,
    "reason.deep": 4096,
    "code.generate": 1024,
    "code.review": 2048,
}

_NVAPI_RE = re.compile(r"nvapi-[A-Za-z0-9._~+\-/=]+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+[^\s\"']+", re.IGNORECASE)
_ENV_RE = re.compile(r"NVIDIA_API_KEY\s*=\s*[^\s\"']+", re.IGNORECASE)


class NvidiaProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class NvidiaAdmissionDecision:
    allowed: bool
    reason: str
    provider: str = "nvidia"
    model_id: str | None = None
    execution_profile: str | None = None
    cost_class: str = "UNKNOWN"
    provider_authority: str = "NONE"
    schema: str = "HazewaveNvidiaAdmissionDecision/v1"



@dataclass(frozen=True)
class GuidedJsonCanaryResult:
    status: str
    http_status: int | None
    schema_valid: bool
    error_class: str | None = None
    schema: str = "HazewaveNvidiaGuidedJsonCanaryResult/v1"

def _parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def redact_nvidia_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.casefold() in {"authorization", "nvidia_api_key", "api_key"}:
                cleaned[name] = "[REDACTED]"
            else:
                cleaned[name] = redact_nvidia_secrets(item)
        return cleaned
    if isinstance(value, list):
        return [redact_nvidia_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_nvidia_secrets(item) for item in value)
    if isinstance(value, str):
        text = _NVAPI_RE.sub("[REDACTED]", value)
        text = _BEARER_RE.sub("Bearer [REDACTED]", text)
        text = _ENV_RE.sub("[REDACTED]", text)
        return text
    return value


def load_nvidia_api_key(
    path: Path | str = DEFAULT_NVIDIA_SECRET_PATH,
) -> str:
    target = Path(path).expanduser()
    try:
        info = target.lstat()
    except OSError as exc:
        raise NvidiaProviderError("NVIDIA_SECRET_MISSING") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise NvidiaProviderError("NVIDIA_SECRET_FILE_TYPE_INVALID")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise NvidiaProviderError("NVIDIA_SECRET_PERMISSIONS_INVALID")
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise NvidiaProviderError("NVIDIA_SECRET_READ_FAILED") from exc
    values: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip()
        if normalized_key.startswith("export "):
            normalized_key = normalized_key[7:].strip()
        values[normalized_key] = value.strip().strip('"').strip("'")
    api_key = values.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise NvidiaProviderError("NVIDIA_API_KEY_MISSING")
    return api_key


def load_nvidia_admission(
    path: Path | str = DEFAULT_NVIDIA_ADMISSION_PATH,
) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NvidiaProviderError("NVIDIA_ADMISSION_RECEIPT_INVALID") from exc
    if not isinstance(payload, dict):
        raise NvidiaProviderError("NVIDIA_ADMISSION_RECEIPT_INVALID")
    return payload


def _deny(
    reason: str,
    *,
    model_id: str,
    execution_profile: str,
    cost_class: str = "UNKNOWN",
) -> NvidiaAdmissionDecision:
    return NvidiaAdmissionDecision(
        allowed=False,
        reason=reason,
        model_id=model_id,
        execution_profile=execution_profile,
        cost_class=cost_class,
    )


def evaluate_nvidia_admission(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    execution_profile: str,
    receipt: dict[str, Any] | None = None,
    receipt_path: Path | str = DEFAULT_NVIDIA_ADMISSION_PATH,
    data_classification: str = "PUBLIC",
    now: str | datetime | None = None,
) -> NvidiaAdmissionDecision:
    model = str(model_id or "").strip()
    profile = str(execution_profile or "").strip().upper()
    if receipt is None:
        receipt = load_nvidia_admission(receipt_path)
    try:
        validate_authorization(
            authorization,
            expected_task_id=authorization.task_id,
            expected_capability=authorization.capability_id,
        )
    except (PermissionError, ValueError):
        return _deny(
            "HAZEWAVE_AUTHORIZATION_INVALID",
            model_id=model,
            execution_profile=profile,
        )

    if authorization.capability_id not in _ALLOWED_CAPABILITIES:
        return _deny(
            "NVIDIA_CAPABILITY_NOT_ALLOWED",
            model_id=model,
            execution_profile=profile,
        )
    if profile not in _PROFILE_CAPABILITIES:
        return _deny(
            "NVIDIA_EXECUTION_PROFILE_INVALID",
            model_id=model,
            execution_profile=profile,
        )
    if authorization.capability_id not in _PROFILE_CAPABILITIES[profile]:
        return _deny(
            "NVIDIA_PROFILE_CAPABILITY_MISMATCH",
            model_id=model,
            execution_profile=profile,
        )

    if not isinstance(receipt, dict):
        return _deny(
            "NVIDIA_ADMISSION_RECEIPT_MISSING",
            model_id=model,
            execution_profile=profile,
        )
    cost_class = str(receipt.get("cost_class") or "UNKNOWN")
    if (
        receipt.get("schema") != "HazewaveNvidiaProviderAdmission/v1"
        or receipt.get("project_id") != PROJECT_ID
        or receipt.get("authority") != AUTHORITY
        or receipt.get("provider") != "nvidia"
        or receipt.get("provider_authority") != "NONE"
    ):
        return _deny(
            "NVIDIA_ADMISSION_AUTHORITY_INVALID",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if receipt.get("base_url") != NVIDIA_BASE_URL:
        return _deny(
            "NVIDIA_BASE_URL_NOT_PINNED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if (
        cost_class != FREE_DEVELOPMENT_ENDPOINT
        or receipt.get("paid_fallback") != "FORBIDDEN"
        or receipt.get("unknown_cost") != "DENY"
        or receipt.get("development_endpoint_allowed") is not True
        or receipt.get("known_billing_status")
        != "NO_KNOWN_CHARGE_FOR_PROTOTYPE_FREE_ENDPOINT"
    ):
        return _deny(
            "NVIDIA_COST_POLICY_NOT_ADMITTED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )

    classification = str(data_classification or "").strip().upper()
    allowed_classes = {
        str(value).upper()
        for value in (receipt.get("allowed_data_classes") or [])
    }
    if classification not in allowed_classes:
        return _deny(
            "NVIDIA_DATA_CLASSIFICATION_NOT_ALLOWED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )

    if model not in {
        str(value) for value in (receipt.get("admitted_models") or [])
    }:
        return _deny(
            "NVIDIA_MODEL_NOT_ADMITTED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if isinstance(receipt.get("model_lifecycle"), dict):
        lifecycle_decision = evaluate_model_lifecycle(receipt, model)
        if not lifecycle_decision.allowed:
            return _deny(
                lifecycle_decision.reason,
                model_id=model,
                execution_profile=profile,
                cost_class=cost_class,
            )
    if profile not in {
        str(value) for value in (receipt.get("profiles") or [])
    }:
        return _deny(
            "NVIDIA_PROFILE_NOT_ADMITTED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )

    try:
        current = _parse_time(now or datetime.now(timezone.utc))
        observed = _parse_time(str(receipt["observed_at"]))
        expires = _parse_time(str(receipt["expires_at"]))
    except (KeyError, TypeError, ValueError):
        return _deny(
            "NVIDIA_ADMISSION_TIME_INVALID",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if current < observed:
        return _deny(
            "NVIDIA_ADMISSION_TIME_INVALID",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if current > expires:
        return _deny(
            "NVIDIA_ADMISSION_EXPIRED",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )
    if not [
        value
        for value in (receipt.get("source_evidence") or [])
        if str(value).strip()
    ]:
        return _deny(
            "NVIDIA_ADMISSION_EVIDENCE_MISSING",
            model_id=model,
            execution_profile=profile,
            cost_class=cost_class,
        )

    return NvidiaAdmissionDecision(
        allowed=True,
        reason="ALLOW",
        model_id=model,
        execution_profile=profile,
        cost_class=cost_class,
    )


def normalize_nvidia_request(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    execution_profile: str,
    capability_id: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    sampling_policy: str = "PROVIDER_DEFAULT",
    seed: int | None = None,
    reasoning_budget: int | None = None,
    enable_thinking_override: bool | None = None,
    compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = str(execution_profile).upper()
    if profile not in _PROFILE_DEFAULTS:
        raise NvidiaProviderError("NVIDIA_EXECUTION_PROFILE_INVALID")
    if capability_id not in _PROFILE_CAPABILITIES[profile]:
        raise NvidiaProviderError("NVIDIA_PROFILE_CAPABILITY_MISMATCH")
    if not isinstance(messages, list) or not messages:
        raise NvidiaProviderError("NVIDIA_MESSAGES_REQUIRED")

    defaults = _PROFILE_DEFAULTS[profile]
    contract = compatibility if isinstance(compatibility, dict) else {}
    ceiling = contract.get("max_output_tokens")
    if not isinstance(ceiling, int) or ceiling < 1:
        ceiling = 16384
    capability_default = int(
        _CAPABILITY_MAX_TOKENS.get(capability_id, defaults["max_tokens"])
    )
    limit = min(
        int(max_tokens if max_tokens is not None else capability_default),
        ceiling,
    )
    if limit < 1 or limit > 16384:
        raise NvidiaProviderError("NVIDIA_MAX_TOKENS_OUT_OF_RANGE")
    if tools and contract.get("tool_support") is False:
        raise NvidiaProviderError("NVIDIA_TOOL_CALLING_NOT_ADMITTED")
    if response_format is not None and contract.get("response_format_support") is False:
        raise NvidiaProviderError("NVIDIA_RESPONSE_FORMAT_NOT_ADMITTED")

    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [dict(message) for message in messages],
        "max_tokens": limit,
        "stream": False,
        "chat_template_kwargs": {
            "enable_thinking": (
                bool(enable_thinking_override)
                if enable_thinking_override is not None
                else bool(defaults["enable_thinking"])
            )
        },
    }
    policy = str(sampling_policy or "PROVIDER_DEFAULT").upper()
    temperature_supported = contract.get("temperature_supported") is not False
    top_p_supported = contract.get("top_p_supported") is not False
    if policy == "DETERMINISTIC_STRUCTURED":
        if temperature_supported:
            payload["temperature"] = 0.0
    elif policy == "CREATIVE":
        if temperature_supported:
            payload["temperature"] = float(
                temperature if temperature is not None else 0.7
            )
    elif policy == "TOP_P_EXPERIMENT":
        if top_p_supported:
            payload["top_p"] = float(top_p if top_p is not None else 0.95)
    elif policy != "PROVIDER_DEFAULT":
        raise NvidiaProviderError("NVIDIA_SAMPLING_POLICY_INVALID")

    if "temperature" in payload and "top_p" in payload:
        raise NvidiaProviderError(
            "NVIDIA_SAMPLING_PARAMETERS_MUTUALLY_EXCLUSIVE"
        )

    if seed is not None:
        if contract.get("seed_supported") is False:
            raise NvidiaProviderError("NVIDIA_SEED_NOT_ADMITTED")
        seed_value = int(seed)
        if seed_value < 0 or seed_value > 18446744073709552000:
            raise NvidiaProviderError("NVIDIA_SEED_OUT_OF_RANGE")
        payload["seed"] = seed_value

    thinking_enabled = bool(
        payload["chat_template_kwargs"]["enable_thinking"]
    )
    if (
        thinking_enabled
        and contract.get("reasoning_budget_supported") is not False
    ):
        budget = int(
            reasoning_budget
            if reasoning_budget is not None
            else defaults.get("reasoning_budget", 0)
        )
        if budget < 0 or budget > 32768:
            raise NvidiaProviderError("NVIDIA_REASONING_BUDGET_OUT_OF_RANGE")
        if budget >= limit:
            budget = max(1, limit - 1)
        payload["reasoning_budget"] = budget
    if tools:
        payload["tools"] = [dict(tool) for tool in tools]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    if response_format is not None:
        payload["response_format"] = dict(response_format)
    return payload


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _error_result(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    execution_profile: str,
    error_class: str,
    latency_ms: int,
    http_status: int | None,
    retry_after_seconds: int | None,
    finish_reason: str | None = None,
    status: str = "FAIL",
    content: str = "",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    total_tokens: int | None = None,
) -> HazewaveProviderExecutionResult:
    return HazewaveProviderExecutionResult(
        provider="nvidia",
        model_id=model_id,
        execution_profile=execution_profile,
        capability_id=authorization.capability_id,
        status=status,
        content=content,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        tool_calls=(),
        error_class=error_class,
        http_status=http_status,
        retry_after_seconds=retry_after_seconds,
        cost_class=FREE_DEVELOPMENT_ENDPOINT,
        semantic_pass=False,
    )


def probe_hosted_guided_json(
    *,
    secret_path: Path | str = DEFAULT_NVIDIA_SECRET_PATH,
    model_id: str = DEFAULT_NVIDIA_MODEL,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 30.0,
) -> GuidedJsonCanaryResult:
    api_key = load_nvidia_api_key(secret_path)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    body = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": "Return JSON with ok=true.",
            }
        ],
        "max_tokens": 64,
        "stream": False,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
        "guided_json": schema,
    }
    try:
        with httpx.Client(
            base_url=NVIDIA_BASE_URL,
            timeout=float(timeout_seconds),
            transport=transport,
        ) as client:
            response = client.post(
                "/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Hazewave/NVIDIA-guided-json-canary",
                },
            )
    except httpx.TimeoutException:
        return GuidedJsonCanaryResult(
            "FAILED", None, False, "PROVIDER_TIMEOUT"
        )
    except httpx.HTTPError:
        return GuidedJsonCanaryResult(
            "FAILED", None, False, "PROVIDER_TRANSPORT_FAILURE"
        )

    if response.status_code in {400, 404, 422}:
        return GuidedJsonCanaryResult(
            "UNSUPPORTED",
            response.status_code,
            False,
            "GUIDED_JSON_UNSUPPORTED",
        )
    if response.status_code != 200:
        return GuidedJsonCanaryResult(
            "FAILED",
            response.status_code,
            False,
            "PROVIDER_HTTP_FAILURE",
        )
    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        decoded = json.loads(str(content))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return GuidedJsonCanaryResult(
            "FAILED", 200, False, "GUIDED_JSON_INVALID_RESPONSE"
        )
    valid = (
        isinstance(decoded, dict)
        and decoded.get("ok") is True
        and set(decoded) == {"ok"}
    )
    return GuidedJsonCanaryResult(
        "SUPPORTED" if valid else "FAILED",
        200,
        valid,
        None if valid else "GUIDED_JSON_SCHEMA_MISMATCH",
    )


class NvidiaNIMAdapter:
    def __init__(
        self,
        *,
        secret_path: Path | str = DEFAULT_NVIDIA_SECRET_PATH,
        receipt: dict[str, Any] | None = None,
        receipt_path: Path | str = DEFAULT_NVIDIA_ADMISSION_PATH,
        base_url: str = NVIDIA_BASE_URL,
        timeout_seconds: float = 90.0,
        transport: httpx.BaseTransport | None = None,
        max_connections: int = 8,
        max_keepalive_connections: int = 4,
        optimization_state_path: Path | str | None = None,
    ) -> None:
        if base_url.rstrip("/") != NVIDIA_BASE_URL:
            raise NvidiaProviderError("NVIDIA_BASE_URL_NOT_PINNED")
        self.secret_path = Path(secret_path).expanduser()
        self.receipt = receipt
        self.receipt_path = Path(receipt_path)
        self.timeout_seconds = float(timeout_seconds)
        self.transport = transport
        self.optimization_state_path = (
            Path(optimization_state_path).expanduser()
            if optimization_state_path is not None
            else None
        )
        self._client = httpx.Client(
            base_url=NVIDIA_BASE_URL,
            timeout=self.timeout_seconds,
            transport=self.transport,
            limits=httpx.Limits(
                max_connections=max(1, int(max_connections)),
                max_keepalive_connections=max(
                    1, min(int(max_keepalive_connections), int(max_connections))
                ),
                keepalive_expiry=30.0,
            ),
        )

    @property
    def client_identity(self) -> int:
        return id(self._client)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NvidiaNIMAdapter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def execute(
        self,
        *,
        authorization: HazewaveAuthorization,
        model_id: str,
        execution_profile: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        data_classification: str = "PUBLIC",
        semantic_validator: Callable[[str, tuple[dict[str, Any], ...]], bool] | None = None,
        now: str | datetime | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        sampling_policy: str = "PROVIDER_DEFAULT",
        seed: int | None = None,
        reasoning_budget: int | None = None,
        enable_thinking_override: bool | None = None,
        request_timeout_seconds: float | None = None,
    ) -> HazewaveProviderExecutionResult:
        decision = evaluate_nvidia_admission(
            authorization=authorization,
            model_id=model_id,
            execution_profile=execution_profile,
            receipt=self.receipt,
            receipt_path=self.receipt_path,
            data_classification=data_classification,
            now=now,
        )
        if not decision.allowed:
            raise NvidiaProviderError(decision.reason)

        api_key = load_nvidia_api_key(self.secret_path)
        admission = self.receipt if isinstance(self.receipt, dict) else load_nvidia_admission(self.receipt_path)
        contracts = admission.get("model_contracts")
        model_contract = contracts.get(model_id) if isinstance(contracts, dict) else None
        compatibility = model_contract if isinstance(model_contract, dict) else {}
        request_body = normalize_nvidia_request(
            model_id=model_id,
            messages=messages,
            execution_profile=execution_profile,
            capability_id=authorization.capability_id,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            sampling_policy=sampling_policy,
            seed=seed,
            reasoning_budget=reasoning_budget,
            enable_thinking_override=enable_thinking_override,
            compatibility=compatibility,
        )
        lease_id: str | None = None
        if self.optimization_state_path is not None:
            try:
                lease_id = acquire_nvidia_capacity(
                    path=self.optimization_state_path,
                    model_id=model_id,
                    now=now,
                    lease_ttl_seconds=max(30, int(self.timeout_seconds) + 30),
                )
            except RuntimeError as exc:
                error_class = (
                    "PROVIDER_CAPACITY_COOLDOWN"
                    if "COOLDOWN" in str(exc)
                    else "PROVIDER_CAPACITY_BUSY"
                )
                return _error_result(
                    authorization=authorization,
                    model_id=model_id,
                    execution_profile=execution_profile,
                    error_class=error_class,
                    latency_ms=0,
                    http_status=None,
                    retry_after_seconds=None,
                )

        started = time.monotonic()
        try:
            try:
                response = self._client.post(
                    "/chat/completions",
                    json=request_body,
                    timeout=(
                        float(request_timeout_seconds)
                        if request_timeout_seconds is not None
                        else self.timeout_seconds
                    ),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": "Hazewave/NVIDIA-NIM-governed-adapter",
                    },
                )
            finally:
                if lease_id is not None and self.optimization_state_path is not None:
                    release_nvidia_capacity(
                        path=self.optimization_state_path,
                        lease_id=lease_id,
                    )
        except httpx.TimeoutException:
            latency_ms = max(
                0, int(round((time.monotonic() - started) * 1000))
            )
            if self.optimization_state_path is not None:
                update_nvidia_concurrency(
                    path=self.optimization_state_path,
                    model_id=model_id,
                    outcome="PROVIDER_TIMEOUT",
                    latency_ms=latency_ms,
                    now=now,
                )
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="PROVIDER_TIMEOUT",
                latency_ms=latency_ms,
                http_status=None,
                retry_after_seconds=None,
            )
        except httpx.HTTPError:
            latency_ms = max(
                0, int(round((time.monotonic() - started) * 1000))
            )
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="PROVIDER_TRANSPORT_FAILURE",
                latency_ms=latency_ms,
                http_status=None,
                retry_after_seconds=None,
            )

        latency_ms = max(
            0, int(round((time.monotonic() - started) * 1000))
        )
        if response.status_code != 200:
            if response.status_code in {401, 403}:
                error_class = "AUTH_OR_ELIGIBILITY_FAILURE"
            elif response.status_code == 429:
                error_class = "RATE_LIMITED"
            elif 500 <= response.status_code <= 599:
                error_class = "PROVIDER_SERVER_FAILURE"
            else:
                error_class = "PROVIDER_HTTP_FAILURE"
            retry_after = _retry_after_seconds(response)
            if self.optimization_state_path is not None and error_class in {
                "AUTH_OR_ELIGIBILITY_FAILURE",
                "RATE_LIMITED",
                "PROVIDER_SERVER_FAILURE",
            }:
                update_nvidia_concurrency(
                    path=self.optimization_state_path,
                    model_id=model_id,
                    outcome=error_class,
                    retry_after_seconds=retry_after,
                    latency_ms=latency_ms,
                    now=now,
                )
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class=error_class,
                latency_ms=latency_ms,
                http_status=response.status_code,
                retry_after_seconds=retry_after,
            )

        try:
            payload = response.json()
        except ValueError:
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="INVALID_RESPONSE_SCHEMA",
                latency_ms=latency_ms,
                http_status=200,
                retry_after_seconds=None,
            )
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="INVALID_RESPONSE_SCHEMA",
                latency_ms=latency_ms,
                http_status=200,
                retry_after_seconds=None,
            )
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message")
        message = message if isinstance(message, dict) else {}
        finish_reason = (
            str(choice.get("finish_reason"))
            if choice.get("finish_reason") is not None
            else None
        )
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
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        reasoning_tokens = usage.get("reasoning_tokens")
        if not isinstance(reasoning_tokens, int):
            reasoning_tokens = details.get("reasoning_tokens")
        if not isinstance(reasoning_tokens, int):
            reasoning_tokens = None

        def usage_int(key: str) -> int | None:
            value = usage.get(key)
            return int(value) if isinstance(value, int) else None

        prompt_tokens = usage_int("prompt_tokens")
        completion_tokens = usage_int("completion_tokens")
        total_tokens = usage_int("total_tokens")

        if finish_reason == "length":
            return HazewaveProviderExecutionResult(
                provider="nvidia",
                model_id=model_id,
                execution_profile=execution_profile,
                capability_id=authorization.capability_id,
                status="PARTIAL",
                content=content,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                error_class="TOKEN_BUDGET_EXHAUSTED",
                http_status=200,
                retry_after_seconds=None,
                cost_class=FREE_DEVELOPMENT_ENDPOINT,
                semantic_pass=False,
            )
        if finish_reason not in {"stop", "tool_calls"}:
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="UNACCEPTABLE_FINISH_REASON",
                latency_ms=latency_ms,
                http_status=200,
                retry_after_seconds=None,
                finish_reason=finish_reason,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=total_tokens,
            )
        if not content and not tool_calls:
            return _error_result(
                authorization=authorization,
                model_id=model_id,
                execution_profile=execution_profile,
                error_class="EMPTY_SEMANTIC_RESPONSE",
                latency_ms=latency_ms,
                http_status=200,
                retry_after_seconds=None,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=total_tokens,
            )
        if semantic_validator is not None:
            try:
                valid = bool(semantic_validator(content, tool_calls))
            except Exception:
                valid = False
            if not valid:
                return _error_result(
                    authorization=authorization,
                    model_id=model_id,
                    execution_profile=execution_profile,
                    error_class="SEMANTIC_CONTRACT_FAILURE",
                    latency_ms=latency_ms,
                    http_status=200,
                    retry_after_seconds=None,
                    finish_reason=finish_reason,
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                )

        if (
            self.optimization_state_path is not None
            and semantic_validator is not None
        ):
            update_nvidia_concurrency(
                path=self.optimization_state_path,
                model_id=model_id,
                outcome="PASS",
                latency_ms=latency_ms,
                now=now,
            )
        return HazewaveProviderExecutionResult(
            provider="nvidia",
            model_id=model_id,
            execution_profile=execution_profile,
            capability_id=authorization.capability_id,
            status="PASS",
            content=content,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            error_class=None,
            http_status=200,
            retry_after_seconds=None,
            cost_class=FREE_DEVELOPMENT_ENDPOINT,
            semantic_pass=(
                True if semantic_validator is not None else None
            ),
        )
