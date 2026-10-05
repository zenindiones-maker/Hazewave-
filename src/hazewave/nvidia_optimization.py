from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

TRIVIAL = "TRIVIAL"
SIMPLE = "SIMPLE"
MODERATE = "MODERATE"
HARD = "HARD"
VERY_HARD = "VERY_HARD"

FAST_STRUCTURED = "FAST_STRUCTURED"
FAST_CODE = "FAST_CODE"
DEEP_MEDIUM = "DEEP_MEDIUM"
DEEP_HARD = "DEEP_HARD"

REASONING_BUDGET_LADDER = (0, 512, 1024, 2048, 4096)

DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "nvidia"
    / "optimization-v2.json"
)
DEFAULT_NVIDIA_EVALUATION_ROOT = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "nvidia"
    / "evaluation"
)
DEFAULT_NVIDIA_PROOF_CAPACITY_STATE_PATH = (
    DEFAULT_NVIDIA_EVALUATION_ROOT / "runtime-proof-capacity-v2.json"
)
DEFAULT_NVIDIA_BENCHMARK_CAPACITY_STATE_PATH = (
    DEFAULT_NVIDIA_EVALUATION_ROOT / "cross-provider-benchmark-capacity-v2.json"
)
DEFAULT_NVIDIA_PROOF_LEARNING_PATH = (
    DEFAULT_NVIDIA_EVALUATION_ROOT / "runtime-proof-learning-v2.json"
)
DEFAULT_NVIDIA_BENCHMARK_LEARNING_PATH = (
    DEFAULT_NVIDIA_EVALUATION_ROOT / "cross-provider-benchmark-learning-v2.json"
)

_SCHEMA = "HazewaveNvidiaOptimizationState/v2"


@dataclass(frozen=True)
class TaskComplexitySignals:
    capability_id: str
    task_family: str
    estimated_context_tokens: int = 0
    constraint_count: int = 0
    dependent_reasoning_steps: int = 0
    tool_use_required: bool = False
    structured_output: bool = False
    code_complexity: int = 0
    evidence_items: int = 0
    historical_failure_count: int = 0


@dataclass(frozen=True)
class LifecycleDecision:
    allowed: bool
    reason: str
    model_id: str
    cost_class: str = "UNKNOWN"


def classify_task_complexity(signals: TaskComplexitySignals) -> str:
    score = 0
    context = max(0, int(signals.estimated_context_tokens))
    if context > 4000:
        score += 1
    if context > 16000:
        score += 2
    if context > 64000:
        score += 2

    score += min(4, max(0, int(signals.constraint_count)) // 3)
    score += min(4, max(0, int(signals.dependent_reasoning_steps)) // 2)
    score += 1 if signals.tool_use_required else 0
    score += min(3, max(0, int(signals.code_complexity)) // 2)
    score += min(3, max(0, int(signals.evidence_items)) // 5)
    score += min(3, max(0, int(signals.historical_failure_count)))

    # Structured output can reduce search space for already-complex work, but
    # should not erase real constraints/steps on a small reasoning task.
    if signals.structured_output and score >= 4:
        score -= 1

    if score <= 1:
        return TRIVIAL
    if score <= 3:
        return SIMPLE
    if score <= 6:
        return MODERATE
    if score <= 10:
        return HARD
    return VERY_HARD


def select_nvidia_execution_profile(
    *,
    capability_id: str,
    complexity: str,
    structured_output: bool,
) -> str:
    level = str(complexity).upper()
    if capability_id == "code.generate" and level in {
        TRIVIAL,
        SIMPLE,
        MODERATE,
    }:
        return FAST_CODE
    if capability_id == "code.review" and level in {TRIVIAL, SIMPLE}:
        return FAST_CODE
    if capability_id == "code.review" and level == MODERATE:
        return DEEP_MEDIUM
    if structured_output and level in {TRIVIAL, SIMPLE, MODERATE}:
        return FAST_STRUCTURED
    if level in {TRIVIAL, SIMPLE}:
        return FAST_STRUCTURED
    if level == MODERATE:
        return DEEP_MEDIUM
    return DEEP_HARD


def reasoning_budget_for_complexity(complexity: str) -> int:
    mapping = {
        TRIVIAL: 0,
        SIMPLE: 0,
        MODERATE: 512,
        HARD: 1024,
        VERY_HARD: 2048,
    }
    try:
        return mapping[str(complexity).upper()]
    except KeyError as exc:
        raise ValueError("NVIDIA_COMPLEXITY_INVALID") from exc


def next_reasoning_budget(
    *,
    current_budget: int,
    error_class: str | None,
    may_benefit_from_more_reasoning: bool,
) -> int:
    current = max(0, int(current_budget))
    if error_class in {
        "RATE_LIMITED",
        "AUTH_OR_ELIGIBILITY_FAILURE",
        "PROVIDER_SERVER_FAILURE",
        "PROVIDER_TIMEOUT",
    }:
        return current
    if error_class not in {
        "TOKEN_BUDGET_EXHAUSTED",
        "SEMANTIC_CONTRACT_FAILURE",
    }:
        return current
    if not may_benefit_from_more_reasoning:
        return current
    ladder = list(REASONING_BUDGET_LADDER)
    for value in ladder:
        if value > current:
            return value
    return current


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
        "schema": _SCHEMA,
        "authority": "HAZEWAVE_HARNESS",
        "provider": "nvidia",
        "concurrency": {
            "limit": 1,
            "success_streak": 0,
            "cooldown_kind": None,
            "cooldown_until": None,
            "active_leases": {},
        },
        "models": {},
        "updated_at": None,
    }


def load_nvidia_optimization_state(
    path: Path | str = DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
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
        or payload.get("schema") != _SCHEMA
        or payload.get("authority") != "HAZEWAVE_HARNESS"
        or payload.get("provider") != "nvidia"
        or not isinstance(payload.get("concurrency"), dict)
    ):
        return _empty_state()
    payload.setdefault("models", {})
    payload["concurrency"].setdefault("active_leases", {})
    return payload


def _write_private(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.chmod(0o600)
    os.replace(temp, path)
    path.chmod(0o600)


def update_nvidia_concurrency(
    *,
    path: Path | str = DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
    model_id: str,
    outcome: str,
    latency_ms: int,
    retry_after_seconds: int | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    target = Path(path).expanduser()
    lock = target.with_suffix(target.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.chmod(0o700)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_nvidia_optimization_state(target)
        concurrency = state["concurrency"]
        limit = max(1, int(concurrency.get("limit") or 1))
        status = str(outcome).upper()
        current = _parse_time(now)

        if status == "PASS":
            streak = int(concurrency.get("success_streak") or 0) + 1
            if streak >= 4:
                limit = min(16, limit + 1)
                streak = 0
            concurrency["success_streak"] = streak
            concurrency["cooldown_kind"] = None
            concurrency["cooldown_until"] = None
        elif status == "RATE_LIMITED":
            limit = max(1, limit // 2)
            concurrency["success_streak"] = 0
            delay = max(60, min(3600, int(retry_after_seconds or 60)))
            concurrency["cooldown_kind"] = "RATE_LIMITED"
            concurrency["cooldown_until"] = (
                current + timedelta(seconds=delay)
            ).isoformat()
        elif status in {"PROVIDER_SERVER_FAILURE", "PROVIDER_TIMEOUT"}:
            limit = max(1, limit // 2)
            concurrency["success_streak"] = 0
            concurrency["cooldown_kind"] = status
            concurrency["cooldown_until"] = (
                current + timedelta(seconds=120)
            ).isoformat()
        elif status == "AUTH_OR_ELIGIBILITY_FAILURE":
            concurrency["success_streak"] = 0
            concurrency["cooldown_kind"] = status
            concurrency["cooldown_until"] = (
                current + timedelta(seconds=900)
            ).isoformat()

        concurrency["limit"] = limit
        model = state.setdefault("models", {}).setdefault(
            str(model_id),
            {"last_outcome": None, "last_latency_ms": None},
        )
        model["last_outcome"] = status
        model["last_latency_ms"] = max(0, int(latency_ms))
        state["updated_at"] = current.isoformat()
        _write_private(target, state)
        return state
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def evaluate_model_lifecycle(
    receipt: dict[str, Any],
    model_id: str,
) -> LifecycleDecision:
    lifecycle = receipt.get("model_lifecycle")
    rows = lifecycle if isinstance(lifecycle, dict) else {}
    row = rows.get(model_id)
    if not isinstance(row, dict):
        return LifecycleDecision(False, "NVIDIA_MODEL_LIFECYCLE_MISSING", model_id)
    cost_class = str(row.get("cost_class") or "UNKNOWN")
    if cost_class != "FREE_DEVELOPMENT_ENDPOINT":
        return LifecycleDecision(
            False, "NVIDIA_MODEL_COST_NOT_ADMITTED", model_id, cost_class
        )
    if row.get("free_endpoint_available") is not True:
        return LifecycleDecision(
            False, "NVIDIA_FREE_ENDPOINT_UNAVAILABLE", model_id, cost_class
        )
    if row.get("stage") != "ADMITTED":
        return LifecycleDecision(
            False, "NVIDIA_MODEL_NOT_ADMITTED", model_id, cost_class
        )
    return LifecycleDecision(True, "ALLOW", model_id, cost_class)


def acquire_nvidia_capacity(
    *,
    path: Path | str = DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
    model_id: str,
    now: str | datetime | None = None,
    lease_ttl_seconds: int = 120,
) -> str:
    target = Path(path).expanduser()
    lock = target.with_suffix(target.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.chmod(0o700)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_nvidia_optimization_state(target)
        concurrency = state["concurrency"]
        current = _parse_time(now)
        until = concurrency.get("cooldown_until")
        if until:
            try:
                if _parse_time(str(until)) > current:
                    raise RuntimeError("NVIDIA_CAPACITY_COOLDOWN")
            except ValueError:
                raise RuntimeError("NVIDIA_CAPACITY_COOLDOWN")

        active = concurrency.setdefault("active_leases", {})
        expired = []
        for lease_id, row in active.items():
            if not isinstance(row, dict):
                expired.append(lease_id)
                continue
            try:
                expires = _parse_time(str(row.get("expires_at")))
            except ValueError:
                expired.append(lease_id)
                continue
            if expires <= current:
                expired.append(lease_id)
        for lease_id in expired:
            active.pop(lease_id, None)

        limit = max(1, int(concurrency.get("limit") or 1))
        if len(active) >= limit:
            raise RuntimeError("NVIDIA_CAPACITY_BUSY")

        ttl = max(1, int(lease_ttl_seconds))
        raw = f"{model_id}|{current.isoformat()}|{os.getpid()}|{len(active)}"
        lease_id = sha256(raw.encode("utf-8")).hexdigest()[:24]
        active[lease_id] = {
            "model_id": str(model_id),
            "acquired_at": current.isoformat(),
            "expires_at": (current + timedelta(seconds=ttl)).isoformat(),
        }
        state["updated_at"] = current.isoformat()
        _write_private(target, state)
        return lease_id
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def release_nvidia_capacity(
    *,
    path: Path | str = DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
    lease_id: str,
) -> None:
    target = Path(path).expanduser()
    lock = target.with_suffix(target.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.chmod(0o700)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = load_nvidia_optimization_state(target)
        state["concurrency"].setdefault("active_leases", {}).pop(
            str(lease_id), None
        )
        _write_private(target, state)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
