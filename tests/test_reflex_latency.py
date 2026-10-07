from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import hazewave.reflex_latency as latency
import hazewave.reflex_shadow_runtime as shadow_runtime
from hazewave.reflex import load_reflex_policy, reflex_transport_timeout_seconds


ROOT = Path(__file__).resolve().parents[1]


def _report(
    *,
    profile: str,
    p50: float,
    p95: float,
    label: str = "HAZE",
    robust: bool = True,
    semantic_stable: bool | None = None,
    failures: int = 0,
    probabilities: dict[str, float] | None = None,
    runtime_fingerprint: dict | None = None,
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
        "all_semantically_stable": robust if semantic_stable is None else semantic_stable,
        "aggregate_probability_signature": probabilities
        or {"HAZE": 0.91, "WAVE": 0.05, "BRIDGE": 0.04},
        "runtime_fingerprint": runtime_fingerprint or latency._runtime_fingerprint(),
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


def test_exec_server_routes_explicit_engine_binary_through_coli_engine_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "source"
    c_root = source_root / "c"
    c_root.mkdir(parents=True)
    launcher = c_root / "coli"
    stock = c_root / "laya"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    stock.write_text("stock", encoding="utf-8")
    launcher.chmod(0o755)
    stock.chmod(0o755)

    derived = tmp_path / "derived" / "laya"
    derived.parent.mkdir()
    derived.write_text("derived-engine", encoding="utf-8")
    derived.chmod(0o755)

    model_root = tmp_path / "model"
    model_root.mkdir()
    secret_file = tmp_path / "secret"
    secret_file.write_text("ignored", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_execvpe(file: str, argv: list[str], env: dict[str, str]) -> None:
        captured["file"] = file
        captured["argv"] = argv
        captured["env"] = env
        raise RuntimeError("EXEC_CAPTURED")

    monkeypatch.setattr(latency, "_read_secret", lambda _path: "secret")
    monkeypatch.setattr(latency.os, "execvpe", fake_execvpe)

    with pytest.raises(RuntimeError, match="EXEC_CAPTURED"):
        latency.exec_server(
            source_root=source_root,
            model_root=model_root,
            secret_file=secret_file,
            port=28080,
            profile="baseline_2t",
            state_root=tmp_path / "state",
            engine_bin=derived,
        )

    argv = captured["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("--engine") + 1] == str(derived.resolve())
    env = captured["env"]
    assert isinstance(env, dict)
    assert "COLI_ENGINE" not in env

    stderr = capsys.readouterr().err
    assert f"REFLEX_LATENCY_ENGINE_BIN={derived.resolve()}" in stderr
    assert "REFLEX_LATENCY_ENGINE_SHA256=" in stderr


def test_latency_benchmark_observation_timeout_covers_live_route_transport_window() -> None:
    latency_policy = latency.load_latency_policy()
    reflex_policy = load_reflex_policy()
    route_profile = reflex_policy["profiles"]["decision.route"]

    assert latency_policy["benchmark"]["request_timeout_seconds"] >= (
        reflex_transport_timeout_seconds(route_profile)
    )


def test_question_scale_probe_uses_complete_live_permutation_prefixes() -> None:
    question = shadow_runtime._proof_question()

    probe = latency.question_scale_probe_questions(question)

    assert sorted(probe) == [1, 2, 3, 6]
    assert [len(probe[count]) for count in (1, 2, 3, 6)] == [1, 2, 3, 6]
    assert probe[6] == latency.complete_choice_permutations(
        question_id="route",
        question=question,
        max_rotations=6,
    )
    assert list(probe[3]) == list(probe[6])[:3]


def test_single_question_probe_is_valid_without_fake_ensemble_metrics() -> None:
    question = shadow_runtime._proof_question()
    questions = latency.question_scale_probe_questions(question)[1]
    qid = next(iter(questions))
    answers = {
        qid: {
            "choice": "BRIDGE",
            "probabilities": {"HAZE": 0.20, "WAVE": 0.30, "BRIDGE": 0.50},
            "confidence": 0.25,
        }
    }

    row = latency.ensemble_probe_diagnostics(questions, answers)

    assert row["mode"] == "SINGLE_DECISION"
    assert row["aggregate_winner"] == "BRIDGE"
    assert row["aggregate_probabilities"] == {
        "HAZE": 0.20,
        "WAVE": 0.30,
        "BRIDGE": 0.50,
    }
    assert row["winner_agreement"] is None
    assert row["normalized_jsd"] is None
    assert len(row["permutation_answers"]) == 1


def test_ensemble_probe_diagnostics_preserve_order_probabilities_and_aggregate() -> None:
    question = shadow_runtime._proof_question()
    questions = latency.question_scale_probe_questions(question)[6]
    answers = {}
    for index, qid in enumerate(questions):
        if index < 5:
            probs = {"HAZE": 0.08, "WAVE": 0.12, "BRIDGE": 0.80}
            choice = "BRIDGE"
        else:
            probs = {"HAZE": 0.08, "WAVE": 0.72, "BRIDGE": 0.20}
            choice = "WAVE"
        answers[qid] = {
            "choice": choice,
            "probabilities": probs,
            "confidence": (3 * probs[choice] - 1) / 2,
        }

    row = latency.ensemble_probe_diagnostics(questions, answers)

    assert row["aggregate_winner"] == "BRIDGE"
    assert row["winner_agreement"] == pytest.approx(5 / 6)
    assert len(row["permutation_answers"]) == 6
    assert row["permutation_answers"][0]["order"] == ["HAZE", "WAVE", "BRIDGE"]
    assert row["permutation_answers"][-1]["order"] == ["BRIDGE", "WAVE", "HAZE"]
    assert row["permutation_answers"][-1]["winner"] == "WAVE"
    assert row["permutation_answers"][-1]["probabilities"]["WAVE"] == pytest.approx(0.72)


def test_repeatability_summary_blocks_aggregate_winner_drift() -> None:
    rows = [
        {
            "aggregate_winner": "BRIDGE",
            "aggregate_probabilities": {"HAZE": 0.10, "WAVE": 0.35, "BRIDGE": 0.55},
        },
        {
            "aggregate_winner": "BRIDGE",
            "aggregate_probabilities": {"HAZE": 0.11, "WAVE": 0.34, "BRIDGE": 0.55},
        },
        {
            "aggregate_winner": "WAVE",
            "aggregate_probabilities": {"HAZE": 0.10, "WAVE": 0.46, "BRIDGE": 0.44},
        },
    ]

    summary = latency.summarize_ensemble_repeatability(rows)

    assert summary["repeat_count"] == 3
    assert summary["aggregate_winner_agreement"] == pytest.approx(2 / 3)
    assert summary["aggregate_winner_stable"] is False
    assert summary["max_aggregate_probability_delta"] == pytest.approx(0.12)


def test_latency_benchmark_uses_the_same_route_question_as_shadow_runtime() -> None:
    assert latency._proof_question() == shadow_runtime._proof_question()


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


def test_selector_rejects_probability_or_runtime_drift(tmp_path: Path) -> None:
    run = tmp_path / "run"
    state = tmp_path / "state"
    baseline_runtime = latency._runtime_fingerprint()
    _write_report(
        run,
        _report(
            profile="baseline_2t",
            p50=100.0,
            p95=120.0,
            runtime_fingerprint=baseline_runtime,
        ),
    )
    _write_report(
        run,
        _report(
            profile="close_2t",
            p50=70.0,
            p95=80.0,
            probabilities={"HAZE": 0.90, "WAVE": 0.06, "BRIDGE": 0.04},
            runtime_fingerprint=baseline_runtime,
        ),
    )
    drifted = dict(baseline_runtime)
    drifted["fingerprint_sha256"] = "f" * 64
    _write_report(
        run,
        _report(
            profile="spread_2t",
            p50=70.0,
            p95=80.0,
            runtime_fingerprint=drifted,
        ),
    )

    selected = latency.select_profile(run_dir=run, state_root=state)

    assert selected["profile"] == "baseline_2t"
    reasons = {
        row["profile"]: set(row["reasons"])
        for row in selected["rejected"]
    }
    assert "AGGREGATE_PROBABILITY_DRIFT" in reasons["close_2t"]
    assert "RUNTIME_FINGERPRINT_DRIFT" in reasons["spread_2t"]


def test_selector_can_optimize_slow_but_semantically_stable_shadow_baseline(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    state = tmp_path / "state"
    _write_report(
        run,
        _report(
            profile="baseline_2t",
            p50=13_400.0,
            p95=13_800.0,
            robust=False,
            semantic_stable=True,
        ),
    )
    _write_report(
        run,
        _report(
            profile="close_2t",
            p50=11_900.0,
            p95=12_200.0,
            robust=False,
            semantic_stable=True,
        ),
    )

    selected = latency.select_profile(run_dir=run, state_root=state)

    assert selected["profile"] == "close_2t"
    assert selected["grants_execution_authority"] is False
    assert selected["production_calibrated"] is False


def test_selector_refuses_non_robust_baseline(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_report(run, _report(profile="baseline_2t", p50=100.0, p95=120.0, robust=False))
    _write_report(run, _report(profile="single_1t", p50=90.0, p95=100.0))

    with pytest.raises(latency.ReflexLatencyError, match="BASELINE_NOT_ROBUST"):
        latency.select_profile(run_dir=run, state_root=tmp_path / "state")


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
                "runtime_fingerprint": latency._runtime_fingerprint(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(latency.ReflexLatencyError, match="POLICY_DRIFT"):
        latency.selected_profile(state_root=state)


def test_retire_stale_selection_archives_evidence_and_restores_safe_baseline(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    target = state / "latency" / "selected-profile.json"
    target.parent.mkdir(parents=True)
    stale = {
        "schema": "HazewaveReflexLatencySelection/v1",
        "policy_sha256": "0" * 64,
        "profile": "close_2t",
        "selection_sha256": "1" * 64,
        "runtime_fingerprint": latency._runtime_fingerprint(),
    }
    target.write_text(json.dumps(stale), encoding="utf-8")

    retired = latency.retire_stale_selection(state_root=state)

    assert retired["status"] == "STALE_SELECTION_RETIRED"
    assert retired["retired_profile"] == "close_2t"
    assert retired["retired_policy_sha256"] == "0" * 64
    assert retired["current_policy_sha256"] == latency.policy_digest(latency.load_latency_policy())
    assert target.exists() is False
    archive = Path(retired["archive_path"])
    assert archive.is_file()
    assert json.loads(archive.read_text(encoding="utf-8")) == stale
    assert latency.selected_profile(state_root=state) == "baseline_2t"
    assert retired["grants_execution_authority"] is False


def test_retire_selection_refuses_to_clear_current_valid_measurement(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    target = state / "latency" / "selected-profile.json"
    target.parent.mkdir(parents=True)
    policy = latency.load_latency_policy()
    current = {
        "schema": "HazewaveReflexLatencySelection/v1",
        "policy_sha256": latency.policy_digest(policy),
        "profile": "close_2t",
        "selection_sha256": "2" * 64,
        "runtime_fingerprint": latency._runtime_fingerprint(),
    }
    target.write_text(json.dumps(current), encoding="utf-8")

    with pytest.raises(latency.ReflexLatencyError, match="SELECTION_NOT_STALE"):
        latency.retire_stale_selection(state_root=state)

    assert json.loads(target.read_text(encoding="utf-8")) == current


def test_default_profile_is_baseline_without_measurement(tmp_path: Path) -> None:
    assert latency.selected_profile(state_root=tmp_path) == "baseline_2t"


def test_runtime_profile_falls_back_to_baseline_on_runtime_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    target = state / "latency" / "selected-profile.json"
    target.parent.mkdir(parents=True)
    current = latency._runtime_fingerprint()
    drifted = dict(current)
    drifted["fingerprint_sha256"] = "f" * 64
    policy = latency.load_latency_policy()
    target.write_text(
        json.dumps(
            {
                "schema": "HazewaveReflexLatencySelection/v1",
                "policy_sha256": latency.policy_digest(policy),
                "profile": "close_2t",
                "runtime_fingerprint": drifted,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(latency.ReflexLatencyError, match="RUNTIME_DRIFT"):
        latency.selected_profile(state_root=state, policy=policy)

    assert latency.runtime_profile(state_root=state, policy=policy) == "baseline_2t"


def test_runtime_profile_does_not_fallback_on_policy_drift(tmp_path: Path) -> None:
    state = tmp_path / "state"
    target = state / "latency" / "selected-profile.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "schema": "HazewaveReflexLatencySelection/v1",
                "policy_sha256": "0" * 64,
                "profile": "baseline_2t",
                "runtime_fingerprint": latency._runtime_fingerprint(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(latency.ReflexLatencyError, match="POLICY_DRIFT"):
        latency.runtime_profile(state_root=state)
