from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.nvidia import (
    FAST_STRUCTURED,
    DEEP_REASONING,
    NvidiaNIMAdapter,
    NvidiaProviderError,
    evaluate_nvidia_admission,
    load_nvidia_api_key,
    normalize_nvidia_request,
    redact_nvidia_secrets,
)
from hazewave.provider_runtime import (
    FREE_DEVELOPMENT_ENDPOINT,
    HazewaveProviderExecutionResult,
)


MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def _authorization(capability: str = "reason.general"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="nvidia-provider-test",
                goal="prove NVIDIA provider behavior",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _admission(now: str = "2026-10-05T16:00:00+00:00") -> dict:
    return {
        "schema": "HazewaveNvidiaProviderAdmission/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider": "nvidia",
        "provider_authority": "NONE",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "cost_class": "FREE_DEVELOPMENT_ENDPOINT",
        "paid_fallback": "FORBIDDEN",
        "unknown_cost": "DENY",
        "development_endpoint_allowed": True,
        "known_billing_status": "NO_KNOWN_CHARGE_FOR_PROTOTYPE_FREE_ENDPOINT",
        "allowed_data_classes": ["PUBLIC"],
        "admitted_models": [MODEL],
        "profiles": ["FAST_STRUCTURED", "DEEP_REASONING"],
        "observed_at": "2026-10-05T12:00:00+00:00",
        "expires_at": "2026-10-12T12:00:00+00:00",
        "source_evidence": ["https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b"],
    }


def _write_secret(path: Path, value: str = "nvapi-unit-test-secret") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"NVIDIA_API_KEY={value}\n", encoding="utf-8")
    path.chmod(0o600)


def test_secret_loader_requires_private_file_and_never_returns_metadata(tmp_path: Path) -> None:
    path = tmp_path / "nvidia.env"
    _write_secret(path)
    assert load_nvidia_api_key(path) == "nvapi-unit-test-secret"

    path.chmod(0o644)
    with pytest.raises(NvidiaProviderError, match="NVIDIA_SECRET_PERMISSIONS_INVALID"):
        load_nvidia_api_key(path)


def test_redaction_removes_authorization_bearer_and_nvapi_tokens() -> None:
    raw = {
        "Authorization": "Bearer nvapi-super-secret",
        "nested": ["NVIDIA_API_KEY=nvapi-other-secret", "safe"],
    }
    redacted = redact_nvidia_secrets(raw)
    serialized = json.dumps(redacted)
    assert "nvapi-" not in serialized
    assert "Bearer " not in serialized
    assert "NVIDIA_API_KEY=" not in serialized
    assert "safe" in serialized


def test_admission_is_fail_closed_for_paid_unknown_stale_or_unadmitted() -> None:
    allowed = evaluate_nvidia_admission(
        authorization=_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        receipt=_admission(),
        data_classification="PUBLIC",
        now="2026-10-05T16:00:00+00:00",
    )
    assert allowed.allowed is True
    assert allowed.cost_class == FREE_DEVELOPMENT_ENDPOINT

    unknown = _admission()
    unknown["cost_class"] = "UNKNOWN"
    assert evaluate_nvidia_admission(
        authorization=_authorization(), model_id=MODEL,
        execution_profile=FAST_STRUCTURED, receipt=unknown,
        data_classification="PUBLIC", now="2026-10-05T16:00:00+00:00",
    ).allowed is False

    stale = _admission()
    assert evaluate_nvidia_admission(
        authorization=_authorization(), model_id=MODEL,
        execution_profile=FAST_STRUCTURED, receipt=stale,
        data_classification="PUBLIC", now="2026-10-13T16:00:00+00:00",
    ).reason == "NVIDIA_ADMISSION_EXPIRED"


def test_profile_normalization_fast_and_deep_use_distinct_thinking_budgets() -> None:
    fast = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "classify this"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="reason.general",
    )
    deep = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "analyze architecture"}],
        execution_profile=DEEP_REASONING,
        capability_id="reason.deep",
    )

    assert fast["stream"] is False
    assert fast["chat_template_kwargs"]["enable_thinking"] is False
    assert "reasoning_budget" not in fast
    assert fast["max_tokens"] < deep["max_tokens"]

    assert deep["chat_template_kwargs"]["enable_thinking"] is True
    assert deep["reasoning_budget"] > 0
    assert deep["reasoning_budget"] < deep["max_tokens"]


def test_http_200_stop_nonempty_is_semantic_pass_and_accounts_tokens(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    _write_secret(secret)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": "HAZEWAVE_NVIDIA_OK"},
                }],
                "usage": {
                    "prompt_tokens": 29,
                    "completion_tokens": 9,
                    "total_tokens": 38,
                    "completion_tokens_details": {"reasoning_tokens": 3},
                },
            },
        )

    adapter = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_admission(),
        transport=httpx.MockTransport(handler),
    )
    result = adapter.execute(
        authorization=_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "Return the expected contract"}],
        semantic_validator=lambda content, tool_calls: content == "HAZEWAVE_NVIDIA_OK",
        now="2026-10-05T16:00:00+00:00",
    )

    assert isinstance(result, HazewaveProviderExecutionResult)
    assert result.status == "PASS"
    assert result.provider == "nvidia"
    assert result.model_id == MODEL
    assert result.finish_reason == "stop"
    assert result.prompt_tokens == 29
    assert result.completion_tokens == 9
    assert result.reasoning_tokens == 3
    assert result.total_tokens == 38
    assert result.cost_class == FREE_DEVELOPMENT_ENDPOINT
    assert seen["authorization"] == "Bearer nvapi-unit-test-secret"
    assert seen["body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert "nvapi-unit-test-secret" not in repr(result)


def test_finish_reason_length_is_never_pass_even_on_http_200(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    _write_secret(secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "length",
                    "message": {"content": ""},
                }],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 100,
                    "total_tokens": 120,
                },
            },
        )

    result = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_admission(),
        transport=httpx.MockTransport(handler),
    ).execute(
        authorization=_authorization("reason.deep"),
        model_id=MODEL,
        execution_profile=DEEP_REASONING,
        messages=[{"role": "user", "content": "deep reasoning"}],
        now="2026-10-05T16:00:00+00:00",
    )

    assert result.status == "PARTIAL"
    assert result.error_class == "TOKEN_BUDGET_EXHAUSTED"
    assert result.http_status == 200


def test_empty_stop_response_is_semantic_failure_not_pass(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    _write_secret(secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": ""}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 0, "total_tokens": 4},
            },
        )

    result = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_admission(),
        transport=httpx.MockTransport(handler),
    ).execute(
        authorization=_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "answer"}],
        now="2026-10-05T16:00:00+00:00",
    )

    assert result.status == "FAIL"
    assert result.error_class == "EMPTY_SEMANTIC_RESPONSE"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "AUTH_OR_ELIGIBILITY_FAILURE"),
        (403, "AUTH_OR_ELIGIBILITY_FAILURE"),
        (429, "RATE_LIMITED"),
        (500, "PROVIDER_SERVER_FAILURE"),
        (503, "PROVIDER_SERVER_FAILURE"),
    ],
)
def test_http_failures_are_causally_classified(
    tmp_path: Path,
    status_code: int,
    expected: str,
) -> None:
    secret = tmp_path / "nvidia.env"
    _write_secret(secret)

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "17"} if status_code == 429 else {}
        return httpx.Response(status_code, json={"error": {"message": "secretless"}}, headers=headers)

    result = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_admission(),
        transport=httpx.MockTransport(handler),
    ).execute(
        authorization=_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "hello"}],
        now="2026-10-05T16:00:00+00:00",
    )
    assert result.status == "FAIL"
    assert result.error_class == expected
    if status_code == 429:
        assert result.retry_after_seconds == 17


def test_timeout_is_provider_timeout_and_secret_never_enters_exception(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    _write_secret(secret)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("nvapi-unit-test-secret", request=request)

    result = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_admission(),
        transport=httpx.MockTransport(handler),
    ).execute(
        authorization=_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "hello"}],
        now="2026-10-05T16:00:00+00:00",
    )
    assert result.error_class == "PROVIDER_TIMEOUT"
    assert "nvapi-unit-test-secret" not in repr(result)


def test_model_compatibility_prevents_harness_from_sending_unproved_tools() -> None:
    with pytest.raises(NvidiaProviderError, match="NVIDIA_TOOL_CALLING_NOT_ADMITTED"):
        normalize_nvidia_request(
            model_id=MODEL,
            messages=[{"role": "user", "content": "use a tool"}],
            execution_profile=FAST_STRUCTURED,
            capability_id="code.review",
            tools=[{"type": "function", "function": {"name": "read_file"}}],
            compatibility={
                "tool_support": False,
                "response_format_support": False,
                "max_output_tokens": 4096,
                "temperature_supported": True,
                "top_p_supported": True,
                "reasoning_budget_supported": True,
            },
        )


def test_model_compatibility_caps_output_and_strips_unproved_sampling_params() -> None:
    payload = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "deep"}],
        execution_profile=DEEP_REASONING,
        capability_id="reason.deep",
        max_tokens=12000,
        temperature=0.7,
        top_p=0.8,
        compatibility={
            "tool_support": False,
            "response_format_support": False,
            "max_output_tokens": 4096,
            "temperature_supported": False,
            "top_p_supported": False,
            "reasoning_budget_supported": True,
        },
    )
    assert payload["max_tokens"] == 4096
    assert payload["reasoning_budget"] < 4096
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_secret_loader_accepts_export_prefix(tmp_path: Path) -> None:
    path = tmp_path / "nvidia.env"
    path.write_text(
        'export NVIDIA_API_KEY="nvapi-unit-test-secret"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)

    assert load_nvidia_api_key(path) == "nvapi-unit-test-secret"


def test_code_review_fast_profile_gets_review_budget() -> None:
    general = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "classify"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="reason.general",
    )
    review = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "review"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="code.review",
    )
    assert general["max_tokens"] == 1024
    assert review["max_tokens"] == 2048


def test_deep_profile_uses_tested_nvidia_4096_2048_budget_split() -> None:
    deep = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "analyze deeply"}],
        execution_profile=DEEP_REASONING,
        capability_id="reason.deep",
    )
    assert deep["max_tokens"] == 4096
    assert deep["reasoning_budget"] == 2048
