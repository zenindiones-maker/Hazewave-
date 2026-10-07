from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import hazewave.reflex_latency as latency


ROOT = Path(__file__).resolve().parents[1]


def _report(
    *,
    profile: str,
    p50: float,
    p95: float,
    label: str = "HAZE",
    robust: bool = True,
    failures: int = 0,
) -> dict:
    policy = latency.load_latency_policy()
    return {
        "schema": "HazewaveReflexLatencyProfileReport/v1",
        "status": "PASS" if failures == 0 else "FAIL",
        "profile": profile,
        "policy_sha256": latency.policy_digest(policy),
        "failed_requests": failures,
        "selected_labels": [label],
        "all_robust_eligible": robust,
        "latency": {
            "wall": {
                "count": 7,
                "min_ms": p50 - 5,
                "p50_ms": p50,
                "p95_ms": p95,
                "max_ms": p95,
            }
        },
    }


def _write_report(directory: Path, row: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{row['profile']}.json").write_text(
        json.dumps(row), encoding="utf-8"
    )


def test_latency_policy_validates_against_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/reflex-latency-v1.schema.json").read_text(encoding="utf-8")
    )
    policy = json.loads(
        (ROOT / "config/reflex-latency-v1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(policy)
    loaded = latency.load_latency_policy()
    assert loaded["activation_state"] == "MEASURE_BEFORE_ACTIVATE"
    assert loaded["provider_authority"] == "NONE"


def test_latency_profiles_only_expose_allowlisted_openmp_controls() -> None:
    policy = latency.load_latency_policy()
    allowed = set(policy["safety"]["allowed_environment_keys"])
    for name in policy["profiles"]:
        env = latency.profile_environment(name, policy=policy)
        assert set(env) <= allowed
        assert env.get("OMP_WAIT_POLICY", "").lower() != "active"
        if "OMP_NUM_THREADS" in env:
            assert int(env["OMP_NUM_THREADS"]) in {1, 2}


def test_selector_picks_material_p50_gain_without_p95_or_output_regression(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    state = tmp_path / "state"
    _write_report(run, _report(profile="baseline_2t", p50=100.0, p95=120.0))
    _write_report(run, _report(profile="close_2t", p50=89.0, p95=121.0))

    selected = latency.select_profile(run_dir=run, state_root=state)

    assert selected["status"] == "MEASURED_PROFILE_SELECTED"
    assert selected["profile"] == "close_2t"
    assert selected["selected_p50_ms"] == 89.0
    assert latency.selected_profile(state_root=state) == "close_2t"
    assert selected["provider_authority"] == "NONE"
    assert selected["grants_execution_authority"] is False


def test_selector_retains_baseline_when_gain_is_too_small(tmp_path: Path) -> None:
    run = tmp_path / "run"
    state = tmp_path / "state"
    _write_report(run, _report(profile="baseline_2t", p50=100.0, p95=120.0))
    _write_report(run, _report(profile="close_2t", p50=97.0, p95=116.0))

    selected = latency.select_profile(run_dir=run, state_root=state)

    assert selected["status"] == "BASELINE_RETAINED"
    assert selected["profile"] == "baseline_2t"


def test_selector_rejects_label_or_robustness_drift(tmp_path: Path) -> None:
    run = tmp_path / "run"
    state = tmp_path / "state"
    _write_report(run, _report(profile="baseline_2t", p50=100.0, p95=120.0))
    _write_report(
        run,
        _report(profile="spread_2t", p50=70.0, p95=75.0, label="WAVE"),
    )
    _write_report(
        run,
        _report(profile="close_2t", p50=72.0, p95=78.0, robust=False),
    )

    selected = latency.select_profile(run_dir=run, state_root=state)

    assert selected["profile"] == "baseline_2t"
    reasons = {
        row["profile"]: set(row["reasons"])
        for row in selected["rejected"]
    }
    assert "SELECTED_LABEL_DRIFT" in reasons["spread_2t"]
    assert "ROBUST_ELIGIBILITY_FAILED" in reasons["close_2t"]


def test_selected_profile_fails_closed_on_policy_drift(tmp_path: Path) -> None:
    state = tmp_path / "state"
    target = state / "latency" / "selected-profile.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "schema": "HazewaveReflexLatencySelection/v1",
                "policy_sha256": "0" * 64,
                "profile": "single_1t",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(latency.ReflexLatencyError, match="POLICY_DRIFT"):
        latency.selected_profile(state_root=state)


def test_default_profile_is_baseline_without_measurement(tmp_path: Path) -> None:
    assert latency.selected_profile(state_root=tmp_path) == "baseline_2t"
