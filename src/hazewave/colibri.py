from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from time import monotonic
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization


GB = 1_000_000_000
DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "colibri-local-provider-v1.json"
)


class ColibriDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ColibriHardwareSnapshot:
    ram_total_bytes: int
    ram_available_bytes: int
    disk_free_bytes: int
    model_root: str
    schema: str = "HazewaveColibriHardwareSnapshot/v1"


@dataclass(frozen=True)
class ColibriAdmissionDecision:
    allowed: bool
    reason: str
    model_id: str
    capability_id: str
    trust_lane: str = "LOCAL_PRIVATE"
    provider: str = "colibri"
    provider_authority: str = "NONE"
    zero_cost_verified: bool = False
    schema: str = "HazewaveColibriAdmissionDecision/v1"


@dataclass(frozen=True)
class ColibriDecisionResult:
    model_id: str
    answers: dict[str, Any]
    request_sha256: str
    response_sha256: str
    latency_ms: float
    usage: dict[str, Any]
    health_ms: float | None = None
    system_one_ms: float | None = None
    engine_ms: float | None = None
    server_elapsed_ms: float | None = None
    queue_wait_ms: float | None = None
    provider: str = "colibri"
    provider_authority: str = "NONE"
    status: str = "PASS"
    zero_cost_verified: bool = True
    schema: str = "HazewaveColibriDecisionResult/v1"


def load_colibri_policy(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_POLICY_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveColibriLocalProviderPolicy/v1":
        raise ValueError("COLIBRI_POLICY_SCHEMA_INVALID")
    if payload.get("project_id") != PROJECT_ID or payload.get("authority") != AUTHORITY:
        raise ValueError("COLIBRI_POLICY_AUTHORITY_INVALID")
    if payload.get("provider") != "colibri" or payload.get("provider_authority") != "NONE":
        raise ValueError("COLIBRI_PROVIDER_AUTHORITY_INVALID")
    runtime = payload.get("runtime_policy") or {}
    if runtime.get("paid_fallback") != "FORBIDDEN" or runtime.get("unknown_cost") != "DENY":
        raise ValueError("COLIBRI_ZERO_COST_POLICY_INVALID")
    if runtime.get("auto_install") is not False or runtime.get("auto_download") is not False:
        raise ValueError("COLIBRI_AUTONOMOUS_INSTALL_FORBIDDEN")
    transport = payload.get("transport") or {}
    if transport.get("loopback_only") is not True or transport.get("api_key_required") is not True:
        raise ValueError("COLIBRI_TRANSPORT_POLICY_INVALID")
    _validate_loopback_url(str(transport.get("base_url") or ""))
    return payload


def _validate_loopback_url(base_url: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise ValueError("COLIBRI_ENDPOINT_NOT_LOOPBACK_HTTP")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("COLIBRI_ENDPOINT_NOT_LOOPBACK_HTTP")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("COLIBRI_ENDPOINT_NOT_LOOPBACK_HTTP")
    return value


def _read_int(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text or text == "max":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _linux_available_memory() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def detect_colibri_hardware(
    model_root: str | Path = Path.home() / ".local" / "share" / "hazewave" / "models" / "colibri",
) -> ColibriHardwareSnapshot:
    root = Path(model_root).expanduser()
    probe_path = root if root.exists() else root.parent
    probe_path.mkdir(parents=True, exist_ok=True)

    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    physical_pages = int(os.sysconf("SC_PHYS_PAGES"))
    total = page_size * physical_pages
    available = _linux_available_memory()
    if available is None:
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        available = page_size * available_pages

    cgroup_max = _read_int(Path("/sys/fs/cgroup/memory.max"))
    cgroup_current = _read_int(Path("/sys/fs/cgroup/memory.current"))
    if cgroup_max is not None and cgroup_max > 0:
        total = min(total, cgroup_max)
        if cgroup_current is not None:
            available = min(available, max(0, cgroup_max - cgroup_current))

    disk = shutil.disk_usage(probe_path)
    return ColibriHardwareSnapshot(
        ram_total_bytes=max(0, int(total)),
        ram_available_bytes=max(0, int(available)),
        disk_free_bytes=max(0, int(disk.free)),
        model_root=str(root),
    )


def _model_entry(policy: Mapping[str, Any], model_id: str) -> dict[str, Any] | None:
    wanted = str(model_id or "").strip()
    for row in policy.get("models") or []:
        if isinstance(row, dict) and row.get("id") == wanted:
            return dict(row)
    return None


def _deny(reason: str, *, model_id: str, capability_id: str) -> ColibriAdmissionDecision:
    return ColibriAdmissionDecision(
        allowed=False,
        reason=reason,
        model_id=model_id,
        capability_id=capability_id,
    )


def evaluate_colibri_admission(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    data_classification: str,
    state_language: str = "en",
    execution_context: str = "DEVELOPMENT",
    model_installed: bool = False,
    model_revision_verified: bool = False,
    hardware: ColibriHardwareSnapshot | None = None,
    policy: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> ColibriAdmissionDecision:
    model = str(model_id or "").strip()
    capability = str(authorization.capability_id or "").strip()
    try:
        validate_authorization(
            authorization,
            expected_task_id=authorization.task_id,
            expected_capability=capability,
        )
    except (PermissionError, ValueError):
        return _deny("HAZEWAVE_AUTHORIZATION_INVALID", model_id=model, capability_id=capability)

    provider_policy = policy if policy is not None else load_colibri_policy()
    try:
        expected_url = _validate_loopback_url(
            str((provider_policy.get("transport") or {}).get("base_url") or "")
        )
        actual_url = _validate_loopback_url(base_url or expected_url)
    except ValueError:
        return _deny("COLIBRI_ENDPOINT_NOT_LOOPBACK", model_id=model, capability_id=capability)
    if actual_url != expected_url:
        return _deny("COLIBRI_ENDPOINT_NOT_PINNED", model_id=model, capability_id=capability)

    classification = str(data_classification or "").strip().upper()
    data_policy = provider_policy.get("data_policy") or {}
    if classification in {str(v).upper() for v in (data_policy.get("forbidden_classes") or [])}:
        return _deny("DATA_CLASS_FORBIDDEN", model_id=model, capability_id=capability)
    if classification not in {str(v).upper() for v in (data_policy.get("allowed_classes") or [])}:
        return _deny("DATA_CLASS_NOT_ALLOWED", model_id=model, capability_id=capability)

    entry = _model_entry(provider_policy, model)
    if entry is None:
        return _deny("MODEL_NOT_ALLOWLISTED", model_id=model, capability_id=capability)
    if entry.get("execution_enabled") is not True:
        return _deny("MODEL_EXECUTION_NOT_ENABLED", model_id=model, capability_id=capability)
    if capability not in {str(v) for v in (entry.get("allowed_capabilities") or [])}:
        return _deny("CAPABILITY_NOT_ALLOWED", model_id=model, capability_id=capability)

    language = str(state_language or "").strip().lower()
    if language not in {str(v).lower() for v in (entry.get("languages") or [])}:
        return _deny("STATE_LANGUAGE_NOT_SUPPORTED", model_id=model, capability_id=capability)

    context = str(execution_context or "").strip().upper()
    if context not in {"DEVELOPMENT", "PRODUCTION"}:
        return _deny("EXECUTION_CONTEXT_INVALID", model_id=model, capability_id=capability)
    if context == "PRODUCTION" and entry.get("production_allowed") is not True:
        return _deny("MODEL_LICENSE_NOT_PRODUCTION_ADMITTED", model_id=model, capability_id=capability)

    if not model_installed:
        return _deny("MODEL_NOT_INSTALLED", model_id=model, capability_id=capability)
    if not model_revision_verified:
        return _deny("MODEL_REVISION_NOT_VERIFIED", model_id=model, capability_id=capability)

    snapshot = hardware if hardware is not None else detect_colibri_hardware()
    resources = provider_policy.get("resource_policy") or {}
    reserve_ram = float(resources.get("reserve_system_ram_gb") or 0.0) * GB
    runtime_headroom = float(resources.get("runtime_headroom_ram_gb") or 0.0) * GB
    reserve_disk = float(resources.get("reserve_disk_gb") or 0.0) * GB
    model_ram = float(entry.get("ram_min_gb") or 0.0) * GB

    if snapshot.ram_total_bytes < model_ram + reserve_ram:
        return _deny("INSUFFICIENT_TOTAL_RAM_WITH_RESERVE", model_id=model, capability_id=capability)
    if snapshot.ram_available_bytes < model_ram + runtime_headroom:
        return _deny("INSUFFICIENT_AVAILABLE_RAM", model_id=model, capability_id=capability)
    if snapshot.disk_free_bytes < reserve_disk:
        return _deny("INSUFFICIENT_FREE_DISK_RESERVE", model_id=model, capability_id=capability)

    return ColibriAdmissionDecision(
        allowed=True,
        reason="ALLOW",
        model_id=model,
        capability_id=capability,
        zero_cost_verified=True,
    )


def plan_colibri_model(
    *,
    model_id: str,
    hardware: ColibriHardwareSnapshot,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_policy = policy if policy is not None else load_colibri_policy()
    entry = _model_entry(provider_policy, model_id)
    if entry is None:
        raise ValueError("COLIBRI_MODEL_NOT_ALLOWLISTED")
    resources = provider_policy.get("resource_policy") or {}
    reserve_ram = float(resources.get("reserve_system_ram_gb") or 0.0)
    reserve_disk = float(resources.get("reserve_disk_gb") or 0.0)
    required_total_ram = float(entry.get("ram_min_gb") or 0.0) + reserve_ram
    required_disk = float(entry.get("download_gb") or 0.0) + reserve_disk
    total_ram = hardware.ram_total_bytes / GB
    free_disk = hardware.disk_free_bytes / GB
    fits = total_ram >= required_total_ram and free_disk >= required_disk
    return {
        "schema": "HazewaveColibriModelPlan/v1",
        "model_id": model_id,
        "fits_before_download": fits,
        "ram_total_gb": round(total_ram, 3),
        "disk_free_gb": round(free_disk, 3),
        "required_total_ram_gb": required_total_ram,
        "required_free_disk_gb": required_disk,
        "execution_enabled": bool(entry.get("execution_enabled")),
        "recommended_current_tier": bool(entry.get("recommended_current_tier")),
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_questions(questions: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(questions, Mapping) or not questions or len(questions) > 16:
        raise ValueError("COLIBRI_SYSTEM_ONE_QUESTIONS_INVALID")
    normalized = {str(k): v for k, v in questions.items()}
    encoded = _canonical_json_bytes(normalized)
    if len(encoded) > 64_000:
        raise ValueError("COLIBRI_SYSTEM_ONE_QUESTIONS_TOO_LARGE")
    return normalized


def execute_colibri_system_one(
    *,
    authorization: HazewaveAuthorization,
    model_id: str,
    state: str | Mapping[str, Any],
    questions: Mapping[str, Any],
    api_key: str,
    data_classification: str = "INTERNAL_NON_SECRET",
    state_language: str = "en",
    execution_context: str = "DEVELOPMENT",
    model_installed: bool = False,
    model_revision_verified: bool = False,
    hardware: ColibriHardwareSnapshot | None = None,
    policy: dict[str, Any] | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> ColibriDecisionResult:
    secret = str(api_key or "")
    if len(secret) < 24:
        raise ColibriDecisionError("COLIBRI_API_KEY_REQUIRED")

    provider_policy = policy if policy is not None else load_colibri_policy()
    pinned_url = str((provider_policy.get("transport") or {}).get("base_url") or "").rstrip("/")
    selected_url = base_url or pinned_url
    admission = evaluate_colibri_admission(
        authorization=authorization,
        model_id=model_id,
        data_classification=data_classification,
        state_language=state_language,
        execution_context=execution_context,
        model_installed=model_installed,
        model_revision_verified=model_revision_verified,
        hardware=hardware,
        policy=provider_policy,
        base_url=selected_url,
    )
    if not admission.allowed:
        raise ColibriDecisionError(admission.reason)

    normalized_questions = _validate_questions(questions)
    if isinstance(state, str):
        normalized_state: str | dict[str, Any] = state.strip()
        if not normalized_state:
            raise ValueError("COLIBRI_SYSTEM_ONE_STATE_REQUIRED")
    elif isinstance(state, Mapping):
        normalized_state = dict(state)
    else:
        raise ValueError("COLIBRI_SYSTEM_ONE_STATE_INVALID")

    entry = _model_entry(provider_policy, model_id)
    if entry is None:
        raise ColibriDecisionError("MODEL_NOT_ALLOWLISTED")
    api_model = str(entry.get("api_model") or model_id)
    request_payload = {
        "model": api_model,
        "state": normalized_state,
        "questions": normalized_questions,
    }
    request_bytes = _canonical_json_bytes(request_payload)
    if len(request_bytes) > 256_000:
        raise ValueError("COLIBRI_SYSTEM_ONE_REQUEST_TOO_LARGE")

    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    client_kwargs: dict[str, Any] = {
        "base_url": _validate_loopback_url(selected_url),
        "timeout": timeout_seconds,
        "headers": headers,
    }
    if transport is not None:
        client_kwargs["transport"] = transport

    client_kwargs["trust_env"] = False
    started = monotonic()
    health_started = monotonic()
    health_ms: float | None = None
    system_one_ms: float | None = None
    try:
        with httpx.Client(**client_kwargs) as client:
            health = client.get("/health")
            health_ms = (monotonic() - health_started) * 1000.0
            if health.status_code != 200:
                raise ColibriDecisionError(f"COLIBRI_HEALTH_HTTP_{health.status_code}")
            if len(health.content) > 131_072:
                raise ColibriDecisionError("COLIBRI_HEALTH_RESPONSE_TOO_LARGE")
            try:
                health_payload = health.json()
            except ValueError as exc:
                raise ColibriDecisionError("COLIBRI_HEALTH_JSON_INVALID") from exc
            if not isinstance(health_payload, dict) or health_payload.get("status") != "ok":
                raise ColibriDecisionError("COLIBRI_HEALTH_NOT_OK")

            system_one_started = monotonic()
            response = client.post("/v1/systemone", json=request_payload)
            system_one_ms = (monotonic() - system_one_started) * 1000.0
    except ColibriDecisionError:
        raise
    except httpx.HTTPError as exc:
        raise ColibriDecisionError("COLIBRI_REQUEST_FAILED") from exc

    latency_ms = (monotonic() - started) * 1000.0
    if response.status_code != 200:
        raise ColibriDecisionError(f"COLIBRI_SYSTEM_ONE_HTTP_{response.status_code}")
    if len(response.content) > 1_048_576:
        raise ColibriDecisionError("COLIBRI_SYSTEM_ONE_RESPONSE_TOO_LARGE")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ColibriDecisionError("COLIBRI_SYSTEM_ONE_JSON_INVALID") from exc
    if not isinstance(payload, dict) or payload.get("provider") != "colibri":
        raise ColibriDecisionError("COLIBRI_RESPONSE_PROVIDER_INVALID")
    if payload.get("model") != api_model:
        raise ColibriDecisionError("COLIBRI_RESPONSE_MODEL_MISMATCH")
    answers = payload.get("answers")
    if not isinstance(answers, dict) or not answers:
        raise ColibriDecisionError("COLIBRI_RESPONSE_ANSWERS_INVALID")
    if set(answers) != set(normalized_questions):
        raise ColibriDecisionError("COLIBRI_RESPONSE_ANSWER_SET_MISMATCH")
    usage = payload.get("usage")
    if not isinstance(usage, dict) or usage.get("cost") != 0:
        raise ColibriDecisionError("COLIBRI_ZERO_COST_RECEIPT_MISSING")

    def _header_ms(name: str) -> float | None:
        raw = response.headers.get(name)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value >= 0.0 else None

    response_bytes = _canonical_json_bytes(payload)
    return ColibriDecisionResult(
        model_id=model_id,
        answers=dict(answers),
        request_sha256=sha256(request_bytes).hexdigest(),
        response_sha256=sha256(response_bytes).hexdigest(),
        latency_ms=latency_ms,
        usage=dict(usage),
        health_ms=health_ms,
        system_one_ms=system_one_ms,
        engine_ms=_header_ms("x-colibri-engine-ms"),
        server_elapsed_ms=_header_ms("x-colibri-elapsed-ms"),
        queue_wait_ms=_header_ms("x-colibri-queue-wait-ms"),
    )


def require_confident_choice(
    result: ColibriDecisionResult,
    question_id: str,
    *,
    min_confidence: float | None = None,
    policy: dict[str, Any] | None = None,
) -> str:
    provider_policy = policy if policy is not None else load_colibri_policy()
    default_threshold = float(
        (provider_policy.get("decision_policy") or {}).get("min_choice_probability") or 0.0
    )
    threshold = default_threshold if min_confidence is None else float(min_confidence)
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError("COLIBRI_CHOICE_PROBABILITY_THRESHOLD_INVALID")
    answer = result.answers.get(question_id)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ColibriDecisionError("COLIBRI_CHOICE_ANSWER_MISSING")
    choice = str(answer.get("choice") or "").strip()
    probabilities = answer.get("probabilities")
    if not choice or not isinstance(probabilities, dict):
        raise ColibriDecisionError("COLIBRI_CHOICE_ANSWER_INVALID")
    probability = probabilities.get(choice)
    if not isinstance(probability, (int, float)):
        raise ColibriDecisionError("COLIBRI_CHOICE_PROBABILITY_MISSING")
    if float(probability) < threshold:
        raise ColibriDecisionError("COLIBRI_CHOICE_PROBABILITY_BELOW_THRESHOLD")
    return choice
