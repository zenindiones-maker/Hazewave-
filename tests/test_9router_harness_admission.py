from __future__ import annotations

import json
from pathlib import Path

import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    DEFAULT_ADMISSION_RECEIPT_PATH,
    evaluate_9router_admission,
    load_9router_admission_receipt,
)


def _authorization(capability: str = "reason.general"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="nine-route-001",
                goal="Use a proven free reasoning route",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _receipt(*, observed_at: str = "2026-10-05T11:45:00+00:00") -> dict:
    model = "oc/mimo-v2.6-flash-free"
    return {
        "schema": "Hazewave9RouterFreeAdmissionReceipt/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "gateway": "9router",
        "gateway_authority": "NONE",
        "upstream_repository": "decolua/9router",
        "upstream_commit": "a99cf57239ff778b61e434c2786009d5ed1c412c",
        "endpoint": "http://127.0.0.1:20128",
        "provider": "opencode",
        "provider_alias": "oc",
        "provider_policy": {
            "has_free": True,
            "no_auth": True,
            "paid_fallback": "FORBIDDEN",
            "unknown_cost": "DENY",
            "catalog_rule": "id.endswith(-free) OR id==big-pickle",
            "denylist": ["deepseek-v4-flash-free"],
        },
        "catalog_source": "https://opencode.ai/zen/v1/models",
        "catalog_sha256": "catalog-proof",
        "catalog_discovered_models": [model, "oc/space-bunny-free"],
        "execution_admitted_models": [model],
        "probe": {
            "model": model,
            "max_tokens": 128,
            "max_attempts": 3,
            "attempts": [{"model": model, "status": "semantic_pass"}],
            "semantic_expected": "HAZEWAVE_OK",
            "response_sha256": "response-proof",
            "status": "PASS",
        },
        "observed_at": observed_at,
    }


def test_missing_receipt_fails_closed(tmp_path: Path) -> None:
    loaded = load_9router_admission_receipt(tmp_path / "missing.json")
    decision = evaluate_9router_admission(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        receipt=loaded,
        data_classification="PUBLIC",
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == "NINEROUTER_ADMISSION_RECEIPT_MISSING"


def test_exact_semantic_pass_model_is_admitted_for_public_reasoning() -> None:
    decision = evaluate_9router_admission(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        receipt=_receipt(),
        data_classification="PUBLIC",
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is True
    assert decision.reason == "ALLOW"
    assert decision.gateway == "9router"
    assert decision.provider == "opencode"
    assert decision.model_id == "oc/mimo-v2.6-flash-free"
    assert decision.zero_cost_verified is True


def test_catalog_only_model_is_not_execution_admitted() -> None:
    decision = evaluate_9router_admission(
        authorization=_authorization(),
        model_id="oc/space-bunny-free",
        receipt=_receipt(),
        data_classification="PUBLIC",
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == "MODEL_NOT_EXECUTION_ADMITTED"


@pytest.mark.parametrize(
    ("capability", "classification", "reason"),
    [
        ("audio.generate", "PUBLIC", "CAPABILITY_NOT_ALLOWED"),
        ("reason.general", "INTERNAL_NON_SECRET", "DATA_CLASSIFICATION_NOT_ALLOWED"),
        ("reason.general", "PRIVATE_MEDIA", "DATA_CLASSIFICATION_NOT_ALLOWED"),
    ],
)
def test_9router_free_lane_is_text_public_only(
    capability: str,
    classification: str,
    reason: str,
) -> None:
    decision = evaluate_9router_admission(
        authorization=_authorization(capability),
        model_id="oc/mimo-v2.6-flash-free",
        receipt=_receipt(),
        data_classification=classification,
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == reason


def test_stale_receipt_fails_closed() -> None:
    decision = evaluate_9router_admission(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        receipt=_receipt(observed_at="2026-10-03T00:00:00+00:00"),
        data_classification="PUBLIC",
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == "NINEROUTER_ADMISSION_RECEIPT_EXPIRED"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update({"gateway_authority": "9ROUTER"}),
        lambda r: r.update({"endpoint": "http://0.0.0.0:20128"}),
        lambda r: r["provider_policy"].update({"paid_fallback": "ALLOWED"}),
        lambda r: r["provider_policy"].update({"unknown_cost": "ALLOW"}),
        lambda r: r["probe"].update({"status": "FAIL"}),
    ],
)
def test_receipt_policy_tampering_fails_closed(mutation) -> None:
    receipt = _receipt()
    mutation(receipt)

    decision = evaluate_9router_admission(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        receipt=receipt,
        data_classification="PUBLIC",
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False


def test_default_receipt_path_is_project_scoped_local_state() -> None:
    assert str(DEFAULT_ADMISSION_RECEIPT_PATH).endswith(
        ".local/state/hazewave/providers/9router/free-admission.json"
    )
