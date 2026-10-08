"""Governed Specialist Intelligence V2: routing abstention and repeated evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from hazewave.harness import HazewaveTask, issue_authorization, route_task
from hazewave.slm_specialist_governance import (
    SpecialistGovernanceError, load_specialist_registry, select_specialist,
    evaluate_reliability,
)

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "slm-specialist-registry-v2.json"


def auth(capability="reason.general", domain="HAZE"):
    return issue_authorization(route_task(HazewaveTask(
        task_id="v2-governed-diagnostic-001", goal="Public synthetic diagnostics only",
        required_capability=capability, requested_domain=domain
    )))


def test_registry_has_real_specialists_without_inventing_model_qualification():
    registry = load_specialist_registry(REGISTRY)
    assert registry["authority"] == "HAZEWAVE_HARNESS"
    ids = [x["id"] for x in registry["specialists"]]
    assert ids == ["HAZE_AUDIO_QC", "WAVE_VISUAL_QC", "RE_NATIVE_ANALYSIS"]
    haze, wave, native = registry["specialists"]
    assert haze["model_id"] == "oc/mimo-v2.6-flash-free"
    assert haze["model_classification"] == "UNVERIFIED_ROUTER_ALIAS_LARGE_FAMILY_RISK"
    assert haze["qualification"] == "AVAILABLE"
    assert wave["model_id"] is None
    assert native["model_id"] is None
    for item in registry["specialists"]:
        assert item["production_approved"] is False
        assert item["professional"] is False
        assert item["authority"] == "NONE"


def test_haze_evaluation_proposal_is_not_executable_authority():
    r = select_specialist(auth(), domain="HAZE", requested_workflow="audio.qc",
                          risk="LOW", data_classification="PUBLIC",
                          require_small_model=False)
    assert r["decision"] == "EVALUATION_CANDIDATE"
    assert r["specialist_id"] == "HAZE_AUDIO_QC"
    assert r["model_id"] == "oc/mimo-v2.6-flash-free"
    assert r["execution_authorized"] is False
    assert r["reference_only"] is True
    assert r["production_approved"] is False
    assert r["reason"] == "LIVE_ADMISSION_AND_COMPETENCE_NOT_PROVEN"


def test_wrong_domains_high_risk_private_inputs_and_nonexistent_tools_abstain():
    for opts in (
        dict(domain="WAVE", requested_workflow="audio.qc", risk="LOW", data_classification="PUBLIC"),
        dict(domain="HAZE", requested_workflow="audio.qc", risk="HIGH", data_classification="PUBLIC"),
        dict(domain="HAZE", requested_workflow="audio.qc", risk="LOW", data_classification="PRIVATE"),
        dict(domain="HAZE", requested_workflow="audio.master", risk="LOW", data_classification="PUBLIC"),
    ):
        result = select_specialist(auth(), **opts)
        assert result["decision"] == "ABSTAIN"
        assert result["model_id"] is None
        assert result["execution_authorized"] is False


def test_wave_and_native_gates_abstain_until_real_model_execution():
    for domain, workflow in (("WAVE", "visual.qc"), ("WAVE", "reverse.native.inspect")):
        grant = auth(domain=domain)
        r = select_specialist(grant, domain=domain, requested_workflow=workflow,
                              risk="LOW", data_classification="PUBLIC")
        assert r["decision"] == "ABSTAIN"
        assert r["execution_authorized"] is False


def report(trial_id, receipt_sha="a"*64, case_id="synthetic-gain-12db", grade="PASS"):
    return {
        "schema": "HazewaveSLMAudioSpecialistBenchmark/v1",
        "reviewed_source_sha": "b"*40, "source_evidence_digest_sha256": receipt_sha,
        "model_id": "oc/mimo-v2.6-flash-free",
        "trial_id": trial_id, "case_id": case_id,
        "specialist": {
            "grade": grade, "model_id": "oc/mimo-v2.6-flash-free",
            "total_tokens": 25, "elapsed_ms": 100.0
        },
        "baseline": {
            "grade": "FAIL", "model_id": "oc/mimo-v2.6-flash-free",
            "total_tokens": 29, "elapsed_ms": 120.0
        },
        "model_improvement_proven": False,
        "agent_tool_execution_proven": False,
        "production_approved": False,
    }


def test_three_winning_repeats_on_single_case_do_not_prove_professionalism():
    r = evaluate_reliability([report("trial0001"), report("trial0002"), report("trial0003")])
    assert r["status"] == "INSUFFICIENT_CASE_DIVERSITY"
    assert r["pass_at_1"] == 1.0
    assert r["observed_pass_all_trials"] is True
    assert r["distinct_case_count"] == 1
    assert r["attempt_count"] == 3
    assert r["baseline_pass_at_1"] == 0.0
    assert r["measured_total_tokens"] == 162
    assert r["professional"] is False
    assert r["route_promotion_allowed"] is False
    assert r["independently_attested"] is False


def test_duplicates_and_conflicting_model_claims_fail_closed():
    duplicate = [report("trial0001"), report("trial0001"), report("trial0003")]
    with pytest.raises(SpecialistGovernanceError, match="TRIAL_REPLAY"):
        evaluate_reliability(duplicate)
    bad = report("trial0002")
    bad["baseline"]["model_id"] = "oc/another-free"
    with pytest.raises(SpecialistGovernanceError, match="MODEL_COHORT_MISMATCH"):
        evaluate_reliability([report("trial0001"), bad, report("trial0003")])


def test_multiple_cases_still_need_trusted_runtime_attestation_for_promotion():
    r = evaluate_reliability([
        report("trial0001", case_id="synthetic-gain-12db", receipt_sha="a"*64),
        report("trial0002", case_id="synthetic-gain-6db", receipt_sha="c"*64),
        report("trial0003", case_id="synthetic-silence", receipt_sha="d"*64),
    ])
    assert r["distinct_case_count"] == 3
    assert r["status"] == "OBSERVED_UNATTESTED_NOT_PROFESSIONAL"
    assert r["professional"] is False
    assert r["route_promotion_allowed"] is False


def test_fake_professional_claim_or_invalid_grade_is_rejected():
    forged = report("trial0001")
    forged["production_approved"] = True
    with pytest.raises(SpecialistGovernanceError, match="UNAUTHORIZED_PROMOTION_CLAIM"):
        evaluate_reliability([forged, report("trial0002"), report("trial0003")])
    corrupt = report("trial0001")
    corrupt["specialist"]["grade"] = "SUPERIOR"
    with pytest.raises(SpecialistGovernanceError, match="INVALID_GRADE"):
        evaluate_reliability([corrupt, report("trial0002"), report("trial0003")])


def test_empty_or_short_benchmark_remains_unqualified():
    with pytest.raises(SpecialistGovernanceError, match="TRIAL_COUNT_INSUFFICIENT"):
        evaluate_reliability([])
    with pytest.raises(SpecialistGovernanceError, match="TRIAL_COUNT_INSUFFICIENT"):
        evaluate_reliability([report("trial0001")])


def test_pass_at_k_and_pass_power_k_group_repeats_by_distinct_cases():
    # Each of three independent cases is evaluated with three isolated trials.
    # A: all 3 pass, B: only one pass, C: none pass.
    batch = []
    cases = [
        ("case-alpha", "a"*64, ["PASS","PASS","PASS"]),
        ("case-bravo", "c"*64, ["FAIL","FAIL","PASS"]),
        ("case-charlie", "d"*64, ["FAIL","FAIL","FAIL"]),
    ]
    for i, (case, digest, grades) in enumerate(cases):
        for j, grade in enumerate(grades):
            batch.append(report(f"trial{i:02d}repeat{j:02d}", case_id=case,
                                receipt_sha=digest, grade=grade))
    result = evaluate_reliability(batch)
    assert result["attempt_count"] == 9
    assert result["repeat_count_per_case"] == 3
    assert result["pass_at_k"] == pytest.approx(2/3)
    assert result["pass_power_k"] == pytest.approx(1/3)
    assert result["pass_at_1"] == pytest.approx(4/9)
    assert result["professional"] is False
    assert result["route_promotion_allowed"] is False


def test_incomplete_repetitions_cannot_claim_pass_power_k():
    data = [
        report("trial0001", case_id="case-alpha", receipt_sha="a"*64),
        report("trial0002", case_id="case-bravo", receipt_sha="b"*64),
        report("trial0003", case_id="case-charlie", receipt_sha="c"*64),
    ]
    result = evaluate_reliability(data)
    assert result["pass_at_k"] is None
    assert result["pass_power_k"] is None
    assert result["repeat_count_per_case"] is None


def test_slm_first_abstains_from_unverified_large_family_alias():
    result = select_specialist(
        auth(), domain="HAZE", requested_workflow="audio.qc",
        risk="LOW", data_classification="PUBLIC"
    )
    assert result["decision"] == "ABSTAIN"
    assert result["reason"] == "SLM_SIZE_AND_ROUTER_ALIAS_NOT_VERIFIED"
    assert result["model_id"] is None
    assert result["execution_authorized"] is False


def test_registry_provenance_does_not_equate_router_alias_to_xiaomi_checkpoint():
    row = load_specialist_registry(REGISTRY)["specialists"][0]
    assert row["reference_role"] == "EXPERIMENTAL_UNVERIFIED_SIZE_NOT_SLM"
    assert row["upstream_family"]["official_model_url"] == (
        "https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL"
    )
    assert row["upstream_family"]["reported_total_parameters"] == 309_000_000_000
    assert row["upstream_family"]["reported_active_parameters"] == 15_000_000_000
    assert row["upstream_family"]["exact_router_alias_mapping_verified"] is False
    assert row["production_approved"] is False
