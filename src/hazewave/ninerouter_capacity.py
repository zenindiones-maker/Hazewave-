from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable
from uuid import uuid4

from hazewave.harness import AUTHORITY, PROJECT_ID


DEFAULT_MAX_CAPACITY_STATE_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "max-capacity-state.json"
)
DEFAULT_RESULT_CACHE_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "9router"
    / "result-cache.json"
)

MAX_CAPACITY_STATE_SCHEMA = "Hazewave9RouterMaxCapacityState/v1"
RESULT_CACHE_SCHEMA = "Hazewave9RouterResultCache/v1"

FREE_CAPACITY_CLASSES = frozenset(
    {
        "FREE_UNMETERED_OR_DYNAMIC",
        "FREE_QUOTA",
    }
)
FORBIDDEN_PERMANENT_ZERO_COST_CLASSES = frozenset(
    {
        "PROMOTIONAL_CREDIT",
        "PAID",
        "UNKNOWN",
    }
)

_OUTCOME_CLASS = {
    "PASS": "HEALTHY",
    "EMPTY": "MODEL_QUALITY_COOLDOWN",
    "SEMANTIC_FAIL": "MODEL_QUALITY_COOLDOWN",
    "HTTP_403": "PROVIDER_AUTH_ELIGIBILITY_FAILURE",
    "HTTP_429": "PROVIDER_RATE_LIMIT_COOLDOWN",
    "TIMEOUT": "PROVIDER_SERVER_FAILURE",
}
_PROVIDER = "opencode"


@dataclass(frozen=True)
class TaskContextProfile:
    capability_id: str
    task_family: str
    context_size_bucket: str
    tool_use_requirement: bool
    reasoning_requirement: str
    estimated_context_tokens: int

    @property
    def segment_key(self) -> str:
        tool_lane = "TOOLS" if self.tool_use_requirement else "NO_TOOLS"
        return "|".join(
            (
                self.capability_id,
                self.task_family,
                self.context_size_bucket,
                tool_lane,
                self.reasoning_requirement,
            )
        )


def _parse_time(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: str | datetime | None) -> str:
    return _parse_time(value).isoformat()


def estimate_context_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int:
    serialized = json.dumps(
        {"messages": messages, "tools": tools or []},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return max(1, int(math.ceil(len(serialized) / 4.0)))


def _context_bucket(estimated_tokens: int) -> str:
    if estimated_tokens <= 2_048:
        return "TINY"
    if estimated_tokens <= 8_192:
        return "SMALL"
    if estimated_tokens <= 32_768:
        return "MEDIUM"
    if estimated_tokens <= 131_072:
        return "LARGE"
    return "XLARGE"


def build_task_context_profile(
    *,
    capability_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    task_family: str | None = None,
    reasoning_requirement: str | None = None,
) -> TaskContextProfile:
    estimated_tokens = estimate_context_tokens(messages, tools)
    requires_tools = bool(tools)
    if not requires_tools:
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "tool" or message.get("tool_calls"):
                requires_tools = True
                break

    requirement = str(
        reasoning_requirement
        or ("DEEP" if capability_id == "reason.deep" else "STANDARD")
    ).strip().upper()
    family = str(task_family or f"{capability_id}.default").strip()
    if not family:
        family = f"{capability_id}.default"

    return TaskContextProfile(
        capability_id=str(capability_id),
        task_family=family,
        context_size_bucket=_context_bucket(estimated_tokens),
        tool_use_requirement=requires_tools,
        reasoning_requirement=requirement,
        estimated_context_tokens=estimated_tokens,
    )


def classify_outcome(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in _OUTCOME_CLASS:
        return _OUTCOME_CLASS[normalized]
    if normalized.startswith("HTTP_5") and len(normalized) == 8:
        return "PROVIDER_SERVER_FAILURE"
    return "MODEL_QUALITY_COOLDOWN"


def _empty_state() -> dict[str, Any]:
    return {
        "schema": MAX_CAPACITY_STATE_SCHEMA,
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "providers": {},
        "models": {},
        "cache": {
            "CACHE_HIT": 0,
            "CACHE_MISS": 0,
            "CACHE_INVALIDATED": 0,
            "provider_calls_avoided": 0,
        },
        "updated_at": None,
    }


def load_max_capacity_state(
    path: Path | str = DEFAULT_MAX_CAPACITY_STATE_PATH,
) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.is_file():
        return _empty_state()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != MAX_CAPACITY_STATE_SCHEMA
        or payload.get("project_id") != PROJECT_ID
        or payload.get("authority") != AUTHORITY
        or not isinstance(payload.get("providers"), dict)
        or not isinstance(payload.get("models"), dict)
    ):
        return _empty_state()
    payload.setdefault("cache", {})
    payload["cache"].setdefault("CACHE_HIT", 0)
    payload["cache"].setdefault("CACHE_MISS", 0)
    payload["cache"].setdefault("CACHE_INVALIDATED", 0)
    payload["cache"].setdefault("provider_calls_avoided", 0)
    return payload


def _write_json_private(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    os.replace(tmp, path)
    path.chmod(0o600)


def _mutate_state(
    path: Path | str,
    mutator: Callable[[dict[str, Any]], Any],
) -> Any:
    target = Path(path).expanduser()
    lock_path = target.with_suffix(target.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.chmod(0o700)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_max_capacity_state(target)
        result = mutator(state)
        _write_json_private(target, state)
        return result
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _provider_state(state: dict[str, Any], provider: str) -> dict[str, Any]:
    providers = state.setdefault("providers", {})
    row = providers.setdefault(provider, {})
    row.setdefault(
        "concurrency",
        {
            "limit": 1,
            "max_limit": 16,
            "healthy_streak": 0,
            "active_leases": {},
        },
    )
    row.setdefault(
        "circuit",
        {
            "state": "CLOSED",
            "kind": None,
            "cooldown_until": None,
            "last_failure": None,
        },
    )
    return row


def _model_state(state: dict[str, Any], model_id: str) -> dict[str, Any]:
    models = state.setdefault("models", {})
    row = models.setdefault(model_id, {})
    row.setdefault("segments", {})
    row.setdefault(
        "concurrency",
        {
            "limit": 1,
            "max_limit": 8,
            "healthy_streak": 0,
            "active_leases": {},
        },
    )
    row.setdefault(
        "circuit",
        {
            "state": "CLOSED",
            "kind": None,
            "cooldown_until": None,
            "last_failure": None,
        },
    )
    return row


def _segment_state(
    model: dict[str, Any],
    profile: TaskContextProfile,
) -> dict[str, Any]:
    segments = model.setdefault("segments", {})
    row = segments.setdefault(
        profile.segment_key,
        {
            "profile": asdict(profile),
            "attempt_count": 0,
            "pass_count": 0,
            "semantic_evaluation_count": 0,
            "semantic_pass_count": 0,
            "empty_count": 0,
            "429_count": 0,
            "403_count": 0,
            "5xx_count": 0,
            "timeout_count": 0,
            "fallback_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "latency_ms": None,
            "quality_score": None,
            "last_success": None,
            "last_failure": None,
            "cooldown": {
                "state": "CLOSED",
                "kind": None,
                "until": None,
            },
        },
    )
    return row


def _ewma(previous: Any, observed: float | int | None, alpha: float = 0.35) -> float | None:
    if not isinstance(observed, (int, float)) or observed < 0:
        return float(previous) if isinstance(previous, (int, float)) else None
    if not isinstance(previous, (int, float)) or previous < 0:
        return float(observed)
    return (float(previous) * (1.0 - alpha)) + (float(observed) * alpha)


def _open_circuit(
    row: dict[str, Any],
    *,
    kind: str,
    current: datetime,
    cooldown_seconds: int,
) -> None:
    row["circuit"] = {
        "state": "OPEN",
        "kind": kind,
        "cooldown_until": (
            current + timedelta(seconds=max(1, cooldown_seconds))
        ).isoformat(),
        "last_failure": current.isoformat(),
    }


def _close_circuit(row: dict[str, Any]) -> None:
    row["circuit"] = {
        "state": "CLOSED",
        "kind": None,
        "cooldown_until": None,
        "last_failure": row.get("circuit", {}).get("last_failure"),
    }


def _aimd_success(concurrency: dict[str, Any]) -> None:
    limit = max(1, int(concurrency.get("limit") or 1))
    maximum = max(limit, int(concurrency.get("max_limit") or limit))
    streak = int(concurrency.get("healthy_streak") or 0) + 1
    if streak >= limit:
        concurrency["limit"] = min(maximum, limit + 1)
        concurrency["healthy_streak"] = 0
    else:
        concurrency["healthy_streak"] = streak


def _aimd_congestion(concurrency: dict[str, Any]) -> None:
    limit = max(1, int(concurrency.get("limit") or 1))
    concurrency["limit"] = max(1, limit // 2)
    concurrency["healthy_streak"] = 0


def record_capacity_outcome(
    *,
    path: Path | str = DEFAULT_MAX_CAPACITY_STATE_PATH,
    provider: str,
    model_id: str,
    profile: TaskContextProfile,
    status: str,
    semantic_pass: bool | None = None,
    quality_score: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    latency_ms: int | None = None,
    fallback_used: bool = False,
    retry_after_seconds: int | None = None,
    now: str | datetime | None = None,
) -> None:
    normalized = str(status or "").strip().upper()
    outcome_class = classify_outcome(normalized)
    current = _parse_time(now)

    def mutate(state: dict[str, Any]) -> None:
        provider_row = _provider_state(state, provider)
        model_row = _model_state(state, model_id)
        segment = _segment_state(model_row, profile)

        segment["attempt_count"] = int(segment.get("attempt_count") or 0) + 1
        if fallback_used:
            segment["fallback_count"] = int(segment.get("fallback_count") or 0) + 1

        if isinstance(input_tokens, int) and input_tokens >= 0:
            segment["input_tokens"] = int(segment.get("input_tokens") or 0) + input_tokens
        if isinstance(output_tokens, int) and output_tokens >= 0:
            segment["output_tokens"] = int(segment.get("output_tokens") or 0) + output_tokens
        if isinstance(reasoning_tokens, int) and reasoning_tokens >= 0:
            segment["reasoning_tokens"] = (
                int(segment.get("reasoning_tokens") or 0) + reasoning_tokens
            )
        segment["latency_ms"] = _ewma(segment.get("latency_ms"), latency_ms)

        if semantic_pass is not None:
            segment["semantic_evaluation_count"] = (
                int(segment.get("semantic_evaluation_count") or 0) + 1
            )
            if semantic_pass:
                segment["semantic_pass_count"] = (
                    int(segment.get("semantic_pass_count") or 0) + 1
                )
        if isinstance(quality_score, (int, float)):
            bounded_quality = max(0.0, min(1.0, float(quality_score)))
            segment["quality_score"] = _ewma(
                segment.get("quality_score"),
                bounded_quality,
            )

        if normalized == "PASS":
            segment["pass_count"] = int(segment.get("pass_count") or 0) + 1
            segment["last_success"] = current.isoformat()
            segment["cooldown"] = {
                "state": "CLOSED",
                "kind": None,
                "until": None,
            }
            _close_circuit(model_row)
            provider_circuit = provider_row.get("circuit", {})
            if provider_circuit.get("state") != "OPEN":
                _close_circuit(provider_row)
            _aimd_success(provider_row["concurrency"])
            _aimd_success(model_row["concurrency"])
        else:
            segment["last_failure"] = current.isoformat()
            if normalized == "EMPTY":
                segment["empty_count"] = int(segment.get("empty_count") or 0) + 1
            elif normalized == "HTTP_429":
                segment["429_count"] = int(segment.get("429_count") or 0) + 1
            elif normalized == "HTTP_403":
                segment["403_count"] = int(segment.get("403_count") or 0) + 1
            elif normalized.startswith("HTTP_5"):
                segment["5xx_count"] = int(segment.get("5xx_count") or 0) + 1
            elif normalized == "TIMEOUT":
                segment["timeout_count"] = int(segment.get("timeout_count") or 0) + 1

            cooldown_seconds = 60
            if outcome_class == "PROVIDER_RATE_LIMIT_COOLDOWN":
                cooldown_seconds = max(
                    60,
                    min(3600, int(retry_after_seconds or 0)),
                )
                _aimd_congestion(provider_row["concurrency"])
                _aimd_congestion(model_row["concurrency"])
                _open_circuit(
                    model_row,
                    kind=outcome_class,
                    current=current,
                    cooldown_seconds=cooldown_seconds,
                )
            elif outcome_class == "PROVIDER_AUTH_ELIGIBILITY_FAILURE":
                cooldown_seconds = 900
                _open_circuit(
                    provider_row,
                    kind=outcome_class,
                    current=current,
                    cooldown_seconds=cooldown_seconds,
                )
                _open_circuit(
                    model_row,
                    kind=outcome_class,
                    current=current,
                    cooldown_seconds=cooldown_seconds,
                )
            elif outcome_class == "PROVIDER_SERVER_FAILURE":
                cooldown_seconds = 120
                _aimd_congestion(model_row["concurrency"])
                _open_circuit(
                    model_row,
                    kind=outcome_class,
                    current=current,
                    cooldown_seconds=cooldown_seconds,
                )
            else:
                quality_failures = (
                    int(segment.get("empty_count") or 0)
                    + (
                        int(segment.get("semantic_evaluation_count") or 0)
                        - int(segment.get("semantic_pass_count") or 0)
                    )
                )
                cooldown_seconds = 300 if quality_failures >= 2 else 60
                segment["cooldown"] = {
                    "state": "OPEN",
                    "kind": outcome_class,
                    "until": (
                        current + timedelta(seconds=cooldown_seconds)
                    ).isoformat(),
                }
                _open_circuit(
                    model_row,
                    kind=outcome_class,
                    current=current,
                    cooldown_seconds=cooldown_seconds,
                )

        state["updated_at"] = current.isoformat()

    _mutate_state(path, mutate)


def _circuit_active(
    circuit: dict[str, Any] | None,
    current: datetime,
) -> bool:
    if not isinstance(circuit, dict) or circuit.get("state") != "OPEN":
        return False
    until = circuit.get("cooldown_until") or circuit.get("until")
    if not until:
        return True
    try:
        return _parse_time(str(until)) > current
    except ValueError:
        return True


def contextual_cooldown_active(
    state: dict[str, Any],
    model_id: str,
    profile: TaskContextProfile,
    *,
    now: str | datetime | None = None,
) -> bool:
    current = _parse_time(now)
    model = state.get("models", {}).get(model_id, {})
    if not isinstance(model, dict):
        return False
    if _circuit_active(model.get("circuit"), current):
        return True
    segment = model.get("segments", {}).get(profile.segment_key, {})
    if not isinstance(segment, dict):
        return False
    return _circuit_active(segment.get("cooldown"), current)


def provider_circuit_active(
    state: dict[str, Any],
    provider: str,
    *,
    now: str | datetime | None = None,
) -> bool:
    current = _parse_time(now)
    row = state.get("providers", {}).get(provider, {})
    return isinstance(row, dict) and _circuit_active(row.get("circuit"), current)


def quality_aware_model_score(
    state: dict[str, Any],
    model_id: str,
    profile: TaskContextProfile,
) -> float:
    model = state.get("models", {}).get(model_id, {})
    if not isinstance(model, dict):
        return 0.5
    segment = model.get("segments", {}).get(profile.segment_key, {})
    if not isinstance(segment, dict) or int(segment.get("attempt_count") or 0) <= 0:
        return 0.5

    attempts = max(1, int(segment.get("attempt_count") or 0))
    passes = max(0, int(segment.get("pass_count") or 0))
    semantic_evaluations = max(
        0,
        int(segment.get("semantic_evaluation_count") or 0),
    )
    semantic_passes = max(0, int(segment.get("semantic_pass_count") or 0))

    success_probability = (passes + 2.0) / (attempts + 3.0)
    semantic_probability = (
        (semantic_passes + 1.0) / (semantic_evaluations + 2.0)
        if semantic_evaluations > 0
        else 0.5
    )
    observed_quality = segment.get("quality_score")
    quality = (
        max(0.0, min(1.0, float(observed_quality)))
        if isinstance(observed_quality, (int, float))
        else semantic_probability
    )

    total_tokens = max(
        0,
        int(segment.get("input_tokens") or 0)
        + int(segment.get("output_tokens") or 0)
        + int(segment.get("reasoning_tokens") or 0),
    )
    tokens_per_success = total_tokens / max(1, passes)
    token_efficiency = 1.0 / (1.0 + (tokens_per_success / 2000.0))

    latency = segment.get("latency_ms")
    latency_value = float(latency) if isinstance(latency, (int, float)) else 5000.0
    latency_efficiency = 1.0 / (1.0 + (max(0.0, latency_value) / 3000.0))

    fallback_probability = min(
        1.0,
        max(0.0, int(segment.get("fallback_count") or 0) / attempts),
    )
    circuit = model.get("circuit")
    health = 0.0 if isinstance(circuit, dict) and circuit.get("state") == "OPEN" else 1.0

    score = (
        (0.32 * quality)
        + (0.25 * semantic_probability)
        + (0.20 * success_probability)
        + (0.08 * token_efficiency)
        + (0.07 * latency_efficiency)
        + (0.05 * (1.0 - fallback_probability))
        + (0.03 * health)
    )

    if attempts < 3:
        score += 0.03 * (3 - attempts) / 3.0
    return max(0.0, min(1.0, score))


def _cleanup_expired_leases(concurrency: dict[str, Any], current: datetime) -> None:
    leases = concurrency.get("active_leases")
    leases = leases if isinstance(leases, dict) else {}
    live: dict[str, Any] = {}
    for lease_id, row in leases.items():
        if not isinstance(row, dict):
            continue
        expires_at = row.get("expires_at")
        try:
            if expires_at and _parse_time(str(expires_at)) > current:
                live[str(lease_id)] = row
        except ValueError:
            continue
    concurrency["active_leases"] = live


def acquire_capacity_lease(
    *,
    path: Path | str = DEFAULT_MAX_CAPACITY_STATE_PATH,
    provider: str,
    model_id: str,
    profile: TaskContextProfile,
    now: str | datetime | None = None,
    lease_ttl_seconds: int = 180,
    wait_timeout_seconds: float = 30.0,
) -> str:
    fixed_now = _parse_time(now) if now is not None else None
    deadline = time.monotonic() + max(0.0, float(wait_timeout_seconds))

    while True:
        current = fixed_now or datetime.now(timezone.utc)
        lease_id = f"lease-{uuid4().hex}"

        def try_acquire(state: dict[str, Any]) -> str | None:
            provider_row = _provider_state(state, provider)
            model_row = _model_state(state, model_id)
            segment = _segment_state(model_row, profile)

            if _circuit_active(provider_row.get("circuit"), current):
                raise RuntimeError("NINEROUTER_PROVIDER_CIRCUIT_OPEN")
            if _circuit_active(model_row.get("circuit"), current):
                raise RuntimeError("NINEROUTER_MODEL_CIRCUIT_OPEN")
            if _circuit_active(segment.get("cooldown"), current):
                raise RuntimeError("NINEROUTER_CONTEXT_SEGMENT_COOLDOWN")

            provider_concurrency = provider_row["concurrency"]
            model_concurrency = model_row["concurrency"]
            _cleanup_expired_leases(provider_concurrency, current)
            _cleanup_expired_leases(model_concurrency, current)

            provider_limit = max(1, int(provider_concurrency.get("limit") or 1))
            model_limit = max(1, int(model_concurrency.get("limit") or 1))
            provider_active = len(provider_concurrency["active_leases"])
            model_active = len(model_concurrency["active_leases"])
            if provider_active >= provider_limit or model_active >= model_limit:
                return None

            expires_at = (
                current + timedelta(seconds=max(1, lease_ttl_seconds))
            ).isoformat()
            lease = {
                "model_id": model_id,
                "segment_key": profile.segment_key,
                "acquired_at": current.isoformat(),
                "expires_at": expires_at,
            }
            provider_concurrency["active_leases"][lease_id] = lease
            model_concurrency["active_leases"][lease_id] = lease
            state["updated_at"] = current.isoformat()
            return lease_id

        acquired = _mutate_state(path, try_acquire)
        if acquired is not None:
            return str(acquired)
        if time.monotonic() >= deadline:
            raise RuntimeError("NINEROUTER_CAPACITY_BUSY")
        time.sleep(0.05)


def release_capacity_lease(
    *,
    path: Path | str = DEFAULT_MAX_CAPACITY_STATE_PATH,
    provider: str,
    model_id: str,
    lease_id: str,
) -> None:
    def mutate(state: dict[str, Any]) -> None:
        provider_row = _provider_state(state, provider)
        model_row = _model_state(state, model_id)
        provider_row["concurrency"].setdefault("active_leases", {}).pop(
            lease_id,
            None,
        )
        model_row["concurrency"].setdefault("active_leases", {}).pop(
            lease_id,
            None,
        )

    _mutate_state(path, mutate)


def safe_request_parameters(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    profile: TaskContextProfile,
    compatibility: dict[str, Any] | None,
    requested_max_tokens: int,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    requested_reasoning_effort: str | None = None,
    requested_temperature: float | None = None,
) -> dict[str, Any]:
    contract = compatibility if isinstance(compatibility, dict) else {}
    if contract.get("hazewave_chat_execution_compatible") is False:
        raise ValueError("NINEROUTER_MODEL_CHAT_EXECUTION_INCOMPATIBLE")
    if profile.tool_use_requirement and contract.get("tool_support") is False:
        raise ValueError("NINEROUTER_MODEL_TOOL_USE_INCOMPATIBLE")

    ceiling = contract.get("max_output_tokens")
    if not isinstance(ceiling, int) or ceiling < 1:
        ceiling = 4096
    max_tokens = min(max(1, int(requested_max_tokens)), ceiling)

    payload: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }

    if tools:
        if contract.get("tool_support") is not False:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

    allowed_reasoning = contract.get("reasoning_effort_values")
    if (
        requested_reasoning_effort
        and isinstance(allowed_reasoning, list)
        and requested_reasoning_effort in allowed_reasoning
    ):
        payload["reasoning_effort"] = requested_reasoning_effort

    if requested_temperature is not None and contract.get("temperature_supported") is True:
        payload["temperature"] = float(requested_temperature)

    return payload


def verify_zero_cost_catalog(
    catalog_models: list[str],
    verified_registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lifecycle: dict[str, dict[str, Any]] = {}
    for model in sorted({str(item) for item in catalog_models if str(item).strip()}):
        registry_row = verified_registry.get(model)
        capacity_class = (
            str(registry_row.get("capacity_class"))
            if isinstance(registry_row, dict)
            else "UNKNOWN"
        )
        verified = capacity_class in FREE_CAPACITY_CLASSES
        lifecycle[model] = {
            "stage": "ZERO_COST_VERIFIED" if verified else "DISCOVERED",
            "capacity_class": capacity_class,
            "zero_cost_verified": verified,
        }
    return lifecycle


def _empty_cache() -> dict[str, Any]:
    return {
        "schema": RESULT_CACHE_SCHEMA,
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "entries": {},
        "metrics": {
            "CACHE_HIT": 0,
            "CACHE_MISS": 0,
            "CACHE_INVALIDATED": 0,
            "provider_calls_avoided": 0,
        },
    }


def _load_cache(path: Path | str) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.is_file():
        return _empty_cache()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_cache()
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != RESULT_CACHE_SCHEMA
        or payload.get("project_id") != PROJECT_ID
        or payload.get("authority") != AUTHORITY
        or not isinstance(payload.get("entries"), dict)
    ):
        return _empty_cache()
    payload.setdefault("metrics", {})
    for key in (
        "CACHE_HIT",
        "CACHE_MISS",
        "CACHE_INVALIDATED",
        "provider_calls_avoided",
    ):
        payload["metrics"].setdefault(key, 0)
    return payload


def _cache_key(
    *,
    semantic_hash: str,
    profile: TaskContextProfile,
    context_revision: str,
    policy_revision: str,
    dependency_revision: str,
) -> str:
    payload = {
        "semantic_hash": semantic_hash,
        "segment_key": profile.segment_key,
        "context_revision": context_revision,
        "policy_revision": policy_revision,
        "dependency_revision": dependency_revision,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def cache_store(
    *,
    path: Path | str = DEFAULT_RESULT_CACHE_PATH,
    semantic_hash: str,
    profile: TaskContextProfile,
    context_revision: str,
    policy_revision: str,
    dependency_revision: str,
    payload: dict[str, Any],
    now: str | datetime | None = None,
) -> str:
    if profile.tool_use_requirement:
        raise ValueError("CACHE_TOOL_USE_FORBIDDEN")
    for value, error in (
        (semantic_hash, "CACHE_SEMANTIC_HASH_REQUIRED"),
        (context_revision, "CACHE_CONTEXT_REVISION_REQUIRED"),
        (policy_revision, "CACHE_POLICY_REVISION_REQUIRED"),
        (dependency_revision, "CACHE_DEPENDENCY_REVISION_REQUIRED"),
    ):
        if not str(value or "").strip():
            raise ValueError(error)

    target = Path(path).expanduser()
    key = _cache_key(
        semantic_hash=semantic_hash,
        profile=profile,
        context_revision=context_revision,
        policy_revision=policy_revision,
        dependency_revision=dependency_revision,
    )
    cache = _load_cache(target)
    cache["entries"][key] = {
        "semantic_hash": semantic_hash,
        "segment_key": profile.segment_key,
        "context_revision": context_revision,
        "policy_revision": policy_revision,
        "dependency_revision": dependency_revision,
        "created_at": _iso(now),
        "payload": dict(payload),
    }
    _write_json_private(target, cache)
    return key


def cache_lookup(
    *,
    path: Path | str = DEFAULT_RESULT_CACHE_PATH,
    semantic_hash: str,
    profile: TaskContextProfile,
    context_revision: str,
    policy_revision: str,
    dependency_revision: str,
    now: str | datetime | None = None,
    max_age_seconds: int = 86_400,
) -> dict[str, Any] | None:
    target = Path(path).expanduser()
    cache = _load_cache(target)
    current = _parse_time(now)
    key = _cache_key(
        semantic_hash=semantic_hash,
        profile=profile,
        context_revision=context_revision,
        policy_revision=policy_revision,
        dependency_revision=dependency_revision,
    )
    row = cache["entries"].get(key)
    if isinstance(row, dict):
        try:
            created_at = _parse_time(str(row.get("created_at")))
            fresh = current >= created_at and (
                current - created_at
            ).total_seconds() <= max_age_seconds
        except (TypeError, ValueError):
            fresh = False
        if fresh:
            cache["metrics"]["CACHE_HIT"] += 1
            cache["metrics"]["provider_calls_avoided"] += 1
            _write_json_private(target, cache)
            return {"key": key, **row}
        cache["entries"].pop(key, None)
        cache["metrics"]["CACHE_INVALIDATED"] += 1

    invalidated = 0
    for old_key, old_row in list(cache["entries"].items()):
        if not isinstance(old_row, dict):
            continue
        if (
            old_row.get("semantic_hash") == semantic_hash
            and old_row.get("segment_key") == profile.segment_key
            and (
                old_row.get("context_revision") != context_revision
                or old_row.get("policy_revision") != policy_revision
                or old_row.get("dependency_revision") != dependency_revision
            )
        ):
            cache["entries"].pop(old_key, None)
            invalidated += 1
    cache["metrics"]["CACHE_INVALIDATED"] += invalidated
    cache["metrics"]["CACHE_MISS"] += 1
    _write_json_private(target, cache)
    return None


def compute_rtk_ab_metrics(
    rtk_off: dict[str, Any],
    rtk_on: dict[str, Any],
) -> dict[str, float | bool]:
    if rtk_off.get("task_id") != rtk_on.get("task_id"):
        raise ValueError("RTK_AB_TASK_MISMATCH")
    if rtk_off.get("model_id") != rtk_on.get("model_id"):
        raise ValueError("RTK_AB_MODEL_MISMATCH")
    if rtk_off.get("rtk_enabled") is not False:
        raise ValueError("RTK_AB_OFF_SAMPLE_INVALID")
    if rtk_on.get("rtk_enabled") is not True:
        raise ValueError("RTK_AB_ON_SAMPLE_INVALID")

    off_input = rtk_off.get("input_tokens")
    on_input = rtk_on.get("input_tokens")
    if not isinstance(off_input, int) or off_input <= 0:
        raise ValueError("RTK_AB_PROVIDER_INPUT_TOKENS_REQUIRED")
    if not isinstance(on_input, int) or on_input < 0:
        raise ValueError("RTK_AB_PROVIDER_INPUT_TOKENS_REQUIRED")

    off_quality = rtk_off.get("quality_score")
    on_quality = rtk_on.get("quality_score")
    if not isinstance(off_quality, (int, float)) or not isinstance(
        on_quality, (int, float)
    ):
        raise ValueError("RTK_AB_QUALITY_EVIDENCE_REQUIRED")

    off_latency = rtk_off.get("latency_ms")
    on_latency = rtk_on.get("latency_ms")
    if not isinstance(off_latency, (int, float)) or not isinstance(
        on_latency, (int, float)
    ):
        raise ValueError("RTK_AB_LATENCY_EVIDENCE_REQUIRED")

    return {
        "RTK_REAL_TOKEN_REDUCTION": (off_input - on_input) / off_input,
        "RTK_QUALITY_DELTA": float(on_quality) - float(off_quality),
        "RTK_LATENCY_DELTA": float(on_latency) - float(off_latency),
        "RTK_SEMANTIC_NONREGRESSION": (
            rtk_off.get("semantic_pass") is True
            and rtk_on.get("semantic_pass") is True
        ),
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    bounded = max(0.0, min(1.0, fraction))
    if bounded == 0.5:
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[mid])
        return float((ordered[mid - 1] + ordered[mid]) / 2.0)
    rank = max(
        1,
        min(len(ordered), int(math.ceil(bounded * len(ordered)))),
    )
    return float(ordered[rank - 1])


def summarize_capacity_benchmark(
    rows: list[dict[str, Any]],
    *,
    elapsed_seconds: float,
    concurrency: int,
) -> dict[str, float | int]:
    total = len(rows)
    if total <= 0:
        raise ValueError("CAPACITY_BENCHMARK_ROWS_REQUIRED")
    if elapsed_seconds <= 0:
        raise ValueError("CAPACITY_BENCHMARK_ELAPSED_INVALID")

    successful = [
        row
        for row in rows
        if row.get("status") in {"PASS", "CACHE_HIT"}
    ]
    semantic_successful = [
        row for row in rows if row.get("semantic_pass") is True
    ]
    latencies = [
        float(row["latency_ms"])
        for row in successful
        if isinstance(row.get("latency_ms"), (int, float))
        and row.get("status") != "CACHE_HIT"
    ]
    total_tokens = sum(
        max(0, int(row.get("total_tokens") or 0))
        for row in successful
    )
    fallback_count = sum(
        max(0, int(row.get("fallback_count") or 0))
        for row in rows
    )
    count_429 = sum(
        1
        for row in rows
        if row.get("http_status") == 429 or row.get("status") == "HTTP_429"
    )
    count_empty = sum(1 for row in rows if row.get("status") == "EMPTY")
    cache_hits = sum(1 for row in rows if row.get("cache_hit") is True)

    return {
        "SUSTAINABLE_CONCURRENCY": int(concurrency),
        "USEFUL_TASKS_PER_MINUTE": (
            len(successful) * 60.0 / float(elapsed_seconds)
        ),
        "SUCCESS_RATE": len(successful) / total,
        "SEMANTIC_SUCCESS_RATE": len(semantic_successful) / total,
        "P50_LATENCY": _percentile(latencies, 0.50),
        "P95_LATENCY": _percentile(latencies, 0.95),
        "TOKENS_PER_SUCCESSFUL_TASK": (
            total_tokens / max(1, len(successful))
        ),
        "FALLBACK_AMPLIFICATION": fallback_count / max(1, len(successful)),
        "429_RATE": count_429 / total,
        "EMPTY_RATE": count_empty / total,
        "CACHE_HIT_RATE": cache_hits / total,
    }
