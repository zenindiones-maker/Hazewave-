from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from hazewave.colibri import (
    ColibriDecisionError,
    ColibriHardwareSnapshot,
    evaluate_colibri_admission,
    execute_colibri_system_one,
    load_colibri_policy,
    plan_colibri_model,
    require_confident_choice,
)
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task


ROOT = Path(__file__).resolve().parents[1]


def _authorization(capability: str = "decision.route"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="t-colibri",
                goal="Bounded local decision",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _hardware(
    *,
    ram_gb: float = 8.0,
    available_gb: float = 5.0,
    disk_gb: float = 20.0,
) -> ColibriHardwareSnapshot:
    gb = 1_000_000_000
    return ColibriHardwareSnapshot(
        ram_total_bytes=int(ram_gb * gb),
        ram_available_bytes=int(available_gb * gb),
        disk_free_bytes=int(disk_gb * gb),
        model_root="/tmp/models",
    )


def test_policy_validates_against_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/colibri-local-provider-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (ROOT / "config/colibri-local-provider-v1.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(config)
    assert (
        load_colibri_policy(
            ROOT / "config/colibri-local-provider-v1.json"
        )["provider_authority"]
        == "NONE"
    )


def test_current_8gb_lane_admits_laya_decisions_with_reserve() -> None:
    decision = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="INTERNAL_NON_SECRET",
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
    )
    assert decision.allowed is True
    assert decision.zero_cost_verified is True


def test_model_must_be_installed_and_revision_verified() -> None:
    decision = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="PUBLIC",
        hardware=_hardware(),
    )
    assert decision.allowed is False
    assert decision.reason == "MODEL_NOT_INSTALLED"

    decision = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="PUBLIC",
        model_installed=True,
        hardware=_hardware(),
    )
    assert decision.allowed is False
    assert decision.reason == "MODEL_REVISION_NOT_VERIFIED"


def test_credential_and_external_endpoint_fail_closed() -> None:
    denied = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="CREDENTIAL",
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
    )
    assert denied.reason == "DATA_CLASS_FORBIDDEN"

    denied = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="PUBLIC",
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
        base_url="http://10.0.0.5:28080",
    )
    assert denied.reason == "COLIBRI_ENDPOINT_NOT_LOOPBACK"


def test_english_only_is_enforced_for_current_colibri_decision_engine() -> None:
    denied = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="laya",
        data_classification="PUBLIC",
        state_language="pt-br",
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
    )
    assert denied.reason == "STATE_LANGUAGE_NOT_SUPPORTED"


def test_disabled_gliner_candidate_cannot_execute_yet() -> None:
    denied = evaluate_colibri_admission(
        authorization=_authorization(),
        model_id="gliner2.5-decide",
        data_classification="PUBLIC",
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
    )
    assert denied.reason == "MODEL_EXECUTION_NOT_ENABLED"


def test_resource_planner_preserves_workstation_reserve() -> None:
    plan = plan_colibri_model(model_id="laya", hardware=_hardware())
    assert plan["fits_before_download"] is True

    tight = plan_colibri_model(
        model_id="laya",
        hardware=_hardware(ram_gb=4.0, available_gb=3.5, disk_gb=20.0),
    )
    assert tight["fits_before_download"] is False


def test_system_one_executes_only_after_health_and_zero_cost_receipt() -> None:
    seen: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.method,
                str(request.url),
                request.headers.get("Authorization"),
            )
        )
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={"status": "ok", "scheduler": {"active": 0}},
            )
        if request.url.path == "/v1/systemone":
            return httpx.Response(
                200,
                json={
                    "id": "req_1",
                    "model": "laya",
                    "provider": "colibri",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "HAZE",
                            "probabilities": {
                                "HAZE": 0.93,
                                "WAVE": 0.04,
                                "BRIDGE": 0.03,
                            },
                            "confidence": 0.9,
                        }
                    },
                    "usage": {
                        "input_tokens": 42,
                        "output_tokens": 0,
                        "cost": 0,
                    },
                },
            )
        return httpx.Response(404)

    result = execute_colibri_system_one(
        authorization=_authorization(),
        model_id="laya",
        state={"task_kind": "audio_mix"},
        questions={
            "route": {
                "type": "choice",
                "instructions": "Which Hazewave domain handles this structured task?",
                "criteria": {
                    "HAZE": "audio work",
                    "WAVE": "visual work",
                    "BRIDGE": "cross-domain translation",
                },
            }
        },
        api_key="x" * 32,
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
        transport=httpx.MockTransport(handler),
    )

    assert require_confident_choice(result, "route") == "HAZE"
    assert len(result.request_sha256) == 64
    assert result.zero_cost_verified is True
    assert result.usage["cost"] == 0
    assert result.latency_ms >= 0
    assert seen[0][1].endswith("/health")
    assert seen[1][1].endswith("/v1/systemone")
    assert seen[0][2] == "Bearer " + ("x" * 32)


def test_system_one_refuses_nonzero_cost_receipt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "model": "laya",
                "provider": "colibri",
                "answers": {
                    "q": {
                        "type": "choice",
                        "choice": "a",
                        "confidence": 0.9,
                    }
                },
                "usage": {"cost": 0.01},
            },
        )

    with pytest.raises(
        ColibriDecisionError,
        match="COLIBRI_ZERO_COST_RECEIPT_MISSING",
    ):
        execute_colibri_system_one(
            authorization=_authorization("decision.gate"),
            model_id="laya",
            state="safe structured state",
            questions={
                "q": {
                    "type": "choice",
                    "instructions": "gate",
                    "criteria": {"a": "allow", "b": "deny"},
                }
            },
            api_key="y" * 32,
            model_installed=True,
            model_revision_verified=True,
            hardware=_hardware(),
            transport=httpx.MockTransport(handler),
        )


def test_low_choice_probability_never_becomes_automatic_pass() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "model": "laya",
                "provider": "colibri",
                "answers": {
                    "q": {
                        "type": "choice",
                        "choice": "allow",
                        "probabilities": {"allow": 0.75, "deny": 0.25},
                        "confidence": 0.5,
                    }
                },
                "usage": {"cost": 0},
            },
        )

    result = execute_colibri_system_one(
        authorization=_authorization("decision.gate"),
        model_id="laya",
        state="structured state",
        questions={
            "q": {
                "type": "choice",
                "instructions": "gate",
                "criteria": {
                    "allow": "allowed lane",
                    "deny": "denied lane",
                },
            }
        },
        api_key="z" * 32,
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ColibriDecisionError,
        match="COLIBRI_CHOICE_PROBABILITY_BELOW_THRESHOLD",
    ):
        require_confident_choice(result, "q")



def test_choice_threshold_uses_peak_probability_not_system_one_concentration() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "model": "laya",
                "provider": "colibri",
                "answers": {
                    "q": {
                        "type": "choice",
                        "choice": "a",
                        "probabilities": {"a": 0.85, "b": 0.15},
                        "confidence": 0.70,
                    }
                },
                "usage": {"cost": 0},
            },
        )

    result = execute_colibri_system_one(
        authorization=_authorization("decision.route"),
        model_id="laya",
        state="bounded state",
        questions={
            "q": {
                "type": "choice",
                "instructions": "route",
                "criteria": {"a": "first", "b": "second"},
            }
        },
        api_key="p" * 32,
        model_installed=True,
        model_revision_verified=True,
        hardware=_hardware(),
        transport=httpx.MockTransport(handler),
    )

    assert require_confident_choice(result, "q") == "a"


def test_system_one_rejects_missing_or_extra_answers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "model": "laya",
                "provider": "colibri",
                "answers": {
                    "unexpected": {
                        "type": "choice",
                        "choice": "a",
                        "probabilities": {"a": 0.9, "b": 0.1},
                        "confidence": 0.8,
                    }
                },
                "usage": {"cost": 0},
            },
        )

    with pytest.raises(
        ColibriDecisionError,
        match="COLIBRI_RESPONSE_ANSWER_SET_MISMATCH",
    ):
        execute_colibri_system_one(
            authorization=_authorization("decision.route"),
            model_id="laya",
            state="bounded state",
            questions={
                "q": {
                    "type": "choice",
                    "instructions": "route",
                    "criteria": {"a": "first", "b": "second"},
                }
            },
            api_key="m" * 32,
            model_installed=True,
            model_revision_verified=True,
            hardware=_hardware(),
            transport=httpx.MockTransport(handler),
        )
