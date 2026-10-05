from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable

from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization
from hazewave.provider_runtime import (
    ALLOWED_ZERO_CASH_COST_CLASSES,
    HazewaveProviderExecutionResult,
)

DEFAULT_PROVIDER_LEARNING_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "provider-learning-v1.json"
)
_PROVIDER_LEARNING_SCHEMA = "HazewaveProviderLearningState/v1"


@dataclass(frozen=True)
class ProviderRoute:
    provider: str
    model_id: str
    execution_profile: str
    capability_id: str
    cost_class: str
    task_family: str = "generic"
    complexity: str = "UNSPECIFIED"
    reasoning_budget: int = 0

    @property
    def legacy_route_key(self) -> str:
        return "|".join(
            (
                self.provider,
                self.model_id,
                self.execution_profile,
                self.capability_id,
            )
        )

    @property
    def route_key(self) -> str:
        return "|".join(
            (
                self.provider,
                self.model_id,
                self.execution_profile,
                self.capability_id,
                self.task_family,
                self.complexity,
                str(max(0, int(self.reasoning_budget))),
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


def _empty_state() -> dict[str, Any]:
    return {
        "schema": _PROVIDER_LEARNING_SCHEMA,
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "routes": {},
        "providers": {},
        "updated_at": None,
    }


def load_provider_learning(
    path: Path | str = DEFAULT_PROVIDER_LEARNING_PATH,
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
        or payload.get("schema") != _PROVIDER_LEARNING_SCHEMA
        or payload.get("project_id") != PROJECT_ID
        or payload.get("authority") != AUTHORITY
        or not isinstance(payload.get("routes"), dict)
    ):
        return _empty_state()
    payload.setdefault("providers", {})
    return payload


def _write_state(path: Path | str, payload: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    os.replace(tmp, target)
    target.chmod(0o600)


def _mutate(
    path: Path | str,
    fn: Callable[[dict[str, Any]], Any],
) -> Any:
    target = Path(path).expanduser()
    lock = target.with_suffix(target.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.chmod(0o700)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_provider_learning(target)
        result = fn(state)
        _write_state(target, state)
        return result
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _provider_row(
    state: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    providers = state.setdefault("providers", {})
    return providers.setdefault(
        provider,
        {
            "cooldown_kind": None,
            "cooldown_until": None,
            "last_failure": None,
        },
    )


def _route_row(
    state: dict[str, Any],
    route: ProviderRoute,
) -> dict[str, Any]:
    routes = state.setdefault("routes", {})
    if route.route_key not in routes and route.legacy_route_key in routes:
        migrated = dict(routes.pop(route.legacy_route_key))
        migrated["task_family"] = route.task_family
        migrated["complexity"] = route.complexity
        migrated["reasoning_budget"] = max(0, int(route.reasoning_budget))
        routes[route.route_key] = migrated
    row = routes.setdefault(
        route.route_key,
        {
            "provider": route.provider,
            "model_id": route.model_id,
            "execution_profile": route.execution_profile,
            "capability_id": route.capability_id,
            "cost_class": route.cost_class,
            "task_family": route.task_family,
            "complexity": route.complexity,
            "reasoning_budget": max(0, int(route.reasoning_budget)),
            "attempt_count": 0,
            "pass_count": 0,
            "semantic_failure_count": 0,
            "empty_count": 0,
            "token_budget_exhaustion_count": 0,
            "429_count": 0,
            "auth_or_eligibility_count": 0,
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
            "cooldown_kind": None,
            "cooldown_until": None,
        },
    )
    return row


def _ewma(previous: Any, observed: Any, alpha: float = 0.35) -> float | None:
    if not isinstance(observed, (int, float)) or observed < 0:
        return float(previous) if isinstance(previous, (int, float)) else None
    if not isinstance(previous, (int, float)) or previous < 0:
        return float(observed)
    return float(previous) * (1.0 - alpha) + float(observed) * alpha


def _cooldown_seconds(result: HazewaveProviderExecutionResult) -> int:
    if result.error_class == "RATE_LIMITED":
        return max(60, min(3600, int(result.retry_after_seconds or 60)))
    if result.error_class == "AUTH_OR_ELIGIBILITY_FAILURE":
        return 900
    if result.error_class in {"PROVIDER_SERVER_FAILURE", "PROVIDER_TIMEOUT"}:
        return 120
    if result.error_class in {
        "EMPTY_SEMANTIC_RESPONSE",
        "SEMANTIC_CONTRACT_FAILURE",
        "TOKEN_BUDGET_EXHAUSTED",
    }:
        return 180
    return 60


def record_provider_result(
    *,
    path: Path | str = DEFAULT_PROVIDER_LEARNING_PATH,
    route: ProviderRoute,
    result: HazewaveProviderExecutionResult,
    fallback_used: bool,
    now: str | datetime | None = None,
) -> None:
    current = _parse_time(now)

    def mutate(state: dict[str, Any]) -> None:
        row = _route_row(state, route)
        provider_row = _provider_row(state, route.provider)
        row["attempt_count"] = int(row.get("attempt_count") or 0) + 1
        if fallback_used:
            row["fallback_count"] = int(row.get("fallback_count") or 0) + 1
        row["latency_ms"] = _ewma(row.get("latency_ms"), result.latency_ms)
        if isinstance(result.prompt_tokens, int) and result.prompt_tokens >= 0:
            row["input_tokens"] = int(row.get("input_tokens") or 0) + result.prompt_tokens
        if isinstance(result.completion_tokens, int) and result.completion_tokens >= 0:
            row["output_tokens"] = int(row.get("output_tokens") or 0) + result.completion_tokens
        if isinstance(result.reasoning_tokens, int) and result.reasoning_tokens >= 0:
            row["reasoning_tokens"] = int(row.get("reasoning_tokens") or 0) + result.reasoning_tokens
        if isinstance(result.quality_score, (int, float)):
            bounded = max(0.0, min(1.0, float(result.quality_score)))
            row["quality_score"] = _ewma(row.get("quality_score"), bounded)

        if result.status == "PASS" and result.semantic_pass is True:
            row["pass_count"] = int(row.get("pass_count") or 0) + 1
            row["last_success"] = current.isoformat()
            row["cooldown_kind"] = None
            row["cooldown_until"] = None
        else:
            row["last_failure"] = current.isoformat()
            error = str(result.error_class or "SEMANTIC_FAILURE")
            if error == "EMPTY_SEMANTIC_RESPONSE":
                row["empty_count"] = int(row.get("empty_count") or 0) + 1
                row["semantic_failure_count"] = int(row.get("semantic_failure_count") or 0) + 1
            elif error == "TOKEN_BUDGET_EXHAUSTED":
                row["token_budget_exhaustion_count"] = int(row.get("token_budget_exhaustion_count") or 0) + 1
                row["semantic_failure_count"] = int(row.get("semantic_failure_count") or 0) + 1
            elif error == "RATE_LIMITED":
                row["429_count"] = int(row.get("429_count") or 0) + 1
            elif error == "AUTH_OR_ELIGIBILITY_FAILURE":
                row["auth_or_eligibility_count"] = int(row.get("auth_or_eligibility_count") or 0) + 1
            elif error == "PROVIDER_SERVER_FAILURE":
                row["5xx_count"] = int(row.get("5xx_count") or 0) + 1
            elif error == "PROVIDER_TIMEOUT":
                row["timeout_count"] = int(row.get("timeout_count") or 0) + 1
            else:
                row["semantic_failure_count"] = int(row.get("semantic_failure_count") or 0) + 1

            cooldown = _cooldown_seconds(result)
            row["cooldown_kind"] = error
            row["cooldown_until"] = (
                current + timedelta(seconds=cooldown)
            ).isoformat()
            if error in {
                "RATE_LIMITED",
                "AUTH_OR_ELIGIBILITY_FAILURE",
                "PROVIDER_SERVER_FAILURE",
                "PROVIDER_TIMEOUT",
            }:
                provider_row["cooldown_kind"] = error
                provider_row["cooldown_until"] = (
                    current + timedelta(seconds=cooldown)
                ).isoformat()
                provider_row["last_failure"] = current.isoformat()

        state["updated_at"] = current.isoformat()

    _mutate(path, mutate)


def _cooling(row: dict[str, Any], now: str | datetime | None) -> bool:
    until = row.get("cooldown_until")
    if not until:
        return False
    try:
        return _parse_time(str(until)) > _parse_time(now)
    except ValueError:
        return True


def _route_score(row: dict[str, Any]) -> float:
    attempts = max(0, int(row.get("attempt_count") or 0))
    if attempts <= 0:
        return 0.5
    passes = max(0, int(row.get("pass_count") or 0))
    semantic_failures = max(0, int(row.get("semantic_failure_count") or 0))
    success_probability = (passes + 2.0) / (attempts + 3.0)
    semantic_probability = (passes + 1.0) / (passes + semantic_failures + 2.0)
    quality = row.get("quality_score")
    quality_value = (
        max(0.0, min(1.0, float(quality)))
        if isinstance(quality, (int, float))
        else semantic_probability
    )
    tokens = (
        max(0, int(row.get("input_tokens") or 0))
        + max(0, int(row.get("output_tokens") or 0))
        + max(0, int(row.get("reasoning_tokens") or 0))
    )
    token_efficiency = 1.0 / (1.0 + ((tokens / max(1, passes)) / 2000.0))
    latency = row.get("latency_ms")
    latency_value = float(latency) if isinstance(latency, (int, float)) else 5000.0
    latency_efficiency = 1.0 / (1.0 + max(0.0, latency_value) / 3000.0)
    fallback_probability = min(
        1.0, max(0.0, int(row.get("fallback_count") or 0) / attempts)
    )
    return max(
        0.0,
        min(
            1.0,
            0.31 * quality_value
            + 0.27 * semantic_probability
            + 0.22 * success_probability
            + 0.08 * token_efficiency
            + 0.07 * latency_efficiency
            + 0.05 * (1.0 - fallback_probability),
        ),
    )


def rank_provider_routes(
    *,
    routes: list[ProviderRoute],
    state: dict[str, Any] | None = None,
    task_id: str,
    now: str | datetime | None = None,
) -> list[ProviderRoute]:
    learning = state if isinstance(state, dict) else _empty_state()
    unique: dict[str, ProviderRoute] = {}
    for route in routes:
        if route.cost_class not in ALLOWED_ZERO_CASH_COST_CLASSES:
            continue
        unique.setdefault(route.route_key, route)

    ranked: list[tuple[float, str, ProviderRoute]] = []
    rows = learning.get("routes")
    rows = rows if isinstance(rows, dict) else {}
    providers = learning.get("providers")
    providers = providers if isinstance(providers, dict) else {}
    for route in unique.values():
        provider_row = providers.get(route.provider)
        provider_row = provider_row if isinstance(provider_row, dict) else {}
        if provider_row and _cooling(provider_row, now):
            continue
        row = rows.get(route.route_key)
        if not isinstance(row, dict):
            row = rows.get(route.legacy_route_key)
        row = row if isinstance(row, dict) else {}
        if row and _cooling(row, now):
            continue
        score = _route_score(row)
        tie = sha256(
            f"{task_id}|{route.route_key}".encode("utf-8")
        ).hexdigest()
        ranked.append((-score, tie, route))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [route for _, _, route in ranked]


def execute_provider_routes(
    *,
    authorization: HazewaveAuthorization,
    routes: list[ProviderRoute],
    executor: Callable[[ProviderRoute], HazewaveProviderExecutionResult],
    learning_path: Path | str = DEFAULT_PROVIDER_LEARNING_PATH,
    max_attempts: int = 2,
    now: str | datetime | None = None,
) -> HazewaveProviderExecutionResult:
    validate_authorization(
        authorization,
        expected_task_id=authorization.task_id,
        expected_capability=authorization.capability_id,
    )
    if max_attempts < 1:
        raise ValueError("PROVIDER_MAX_ATTEMPTS_INVALID")

    visited: set[str] = set()
    last_result: HazewaveProviderExecutionResult | None = None
    attempts = 0
    for route in routes:
        if attempts >= max_attempts:
            break
        if route.route_key in visited:
            continue
        visited.add(route.route_key)
        if route.capability_id != authorization.capability_id:
            continue
        if route.cost_class not in ALLOWED_ZERO_CASH_COST_CLASSES:
            continue

        attempts += 1
        result = executor(route)
        if result.provider != route.provider or result.model_id != route.model_id:
            raise PermissionError("PROVIDER_EXECUTION_ROUTE_MISMATCH")
        if result.execution_profile != route.execution_profile:
            raise PermissionError("PROVIDER_EXECUTION_PROFILE_MISMATCH")
        record_provider_result(
            path=learning_path,
            route=route,
            result=result,
            fallback_used=attempts > 1,
            now=now,
        )
        last_result = result
        if result.status == "PASS" and result.semantic_pass is True:
            return result

    if last_result is not None:
        return last_result
    raise RuntimeError("NO_HARD_ELIGIBLE_PROVIDER_ROUTE")


def build_cross_provider_routes(
    *,
    authorization: HazewaveAuthorization,
    ninerouter_models: list[str],
    nvidia_receipt: dict[str, Any] | None,
    now: str | datetime | None = None,
    task_family: str = "generic",
    complexity: str | None = None,
    structured_output: bool = False,
) -> list[ProviderRoute]:
    from hazewave.nvidia import (
        DEFAULT_NVIDIA_MODEL,
        DEEP_REASONING,
        FAST_STRUCTURED,
        evaluate_nvidia_admission,
    )
    from hazewave.nvidia_optimization import (
        reasoning_budget_for_complexity,
        select_nvidia_execution_profile,
    )

    validate_authorization(
        authorization,
        expected_task_id=authorization.task_id,
        expected_capability=authorization.capability_id,
    )

    routes: list[ProviderRoute] = []
    for model in ninerouter_models:
        model_id = str(model or "").strip()
        if not model_id:
            continue
        routes.append(
            ProviderRoute(
                provider="9router",
                model_id=model_id,
                execution_profile="DEFAULT",
                capability_id=authorization.capability_id,
                cost_class="ZERO_COST_VERIFIED",
                task_family=task_family,
                complexity=str(complexity or "UNSPECIFIED"),
                reasoning_budget=0,
            )
        )

    if complexity is None:
        profile = (
            DEEP_REASONING
            if authorization.capability_id == "reason.deep"
            else FAST_STRUCTURED
        )
        reasoning_budget = 0
        route_complexity = "UNSPECIFIED"
    else:
        route_complexity = str(complexity).upper()
        profile = select_nvidia_execution_profile(
            capability_id=authorization.capability_id,
            complexity=route_complexity,
            structured_output=structured_output,
        )
        reasoning_budget = (
            0
            if profile in {FAST_STRUCTURED, "FAST_CODE"}
            else reasoning_budget_for_complexity(route_complexity)
        )
    if isinstance(nvidia_receipt, dict):
        decision = evaluate_nvidia_admission(
            authorization=authorization,
            model_id=DEFAULT_NVIDIA_MODEL,
            execution_profile=profile,
            receipt=nvidia_receipt,
            data_classification="PUBLIC",
            now=now,
        )
        if decision.allowed:
            routes.append(
                ProviderRoute(
                    provider="nvidia",
                    model_id=DEFAULT_NVIDIA_MODEL,
                    execution_profile=profile,
                    capability_id=authorization.capability_id,
                    cost_class=decision.cost_class,
                    task_family=task_family,
                    complexity=route_complexity,
                    reasoning_budget=reasoning_budget,
                )
            )
    return routes


def canonicalize_ninerouter_result(
    *,
    result: Any,
    capability_id: str,
    latency_ms: int,
    quality_score: float | None = None,
) -> HazewaveProviderExecutionResult:
    status = str(getattr(result, "status", "FAIL"))
    return HazewaveProviderExecutionResult(
        provider="9router",
        model_id=str(getattr(result, "model_id", "")),
        execution_profile="DEFAULT",
        capability_id=capability_id,
        status=status,
        content=str(getattr(result, "content", "")),
        finish_reason="stop" if status == "PASS" else None,
        prompt_tokens=getattr(result, "prompt_tokens", None),
        completion_tokens=getattr(result, "completion_tokens", None),
        reasoning_tokens=getattr(result, "reasoning_tokens", None),
        total_tokens=getattr(result, "total_tokens", None),
        latency_ms=max(0, int(latency_ms)),
        tool_calls=tuple(getattr(result, "tool_calls", ()) or ()),
        error_class=None if status == "PASS" else "NINEROUTER_EXECUTION_FAILURE",
        http_status=200 if status == "PASS" else None,
        retry_after_seconds=None,
        cost_class="ZERO_COST_VERIFIED",
        semantic_pass=status == "PASS",
        quality_score=quality_score,
        provider_gateway="9router",
    )
