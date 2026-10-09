"""Fail-closed acoustic semantics; these are deterministic tests, NOT real SLM trials."""
from __future__ import annotations

import pytest

from hazewave.haze_semantic_decision import (
    HazeEvidenceError, assess_gain_evidence, reconcile_gain_decision,
    evaluation_metrics,
)


def evidence(reference=-20.0, processed=-32.0, *, authorized=True,
             task="PRESERVE_REFERENCE_LEVEL", tolerance=1.0, uncertainty=0.05):
    return {
        "schema": "HazewaveGainComparisonEvidence/v1",
        "measurement_method": "FFMPEG_VOLUMEDETECT_MEAN_DBFS_PCM16",
        "reference_mean_dbfs": reference,
        "processed_mean_dbfs": processed,
        "attenuation_db": round(reference - processed, 3),
        "measurement_uncertainty_db": uncertainty,
        "reference_comparison_authorized": authorized,
        "task_spec": task,
        "maximum_permitted_change_db": tolerance,
        "source_sha256": "a"*64,
        "processed_sha256": "b"*64,
        "media_scope": "SYNTHETIC_1S_PCM16",
    }


def proposed(finding="ATTENUATION_DETECTED", action="REVIEW_GAIN_STAGE"):
    return {"finding": finding, "action": action,
            "evidence_keys": ["attenuation_db"], "requires_human_review": True}


def test_real_12db_loss_relative_to_authorized_reference_is_detected():
    result=assess_gain_evidence(evidence())
    assert result["measurement_authority"] == "DETERMINISTIC_FFMPEG"
    assert result["measured_change_db"] == pytest.approx(-12.0)
    assert result["technical_classification"] == "ATTENUATION_DETECTED"
    assert result["decision"] == "MEASURED_CHANGE_REQUIRES_REVIEW"
    assert result["professional_certification"] is False
    assert result["production_authorized"] is False


def test_task_definition_changes_defect_assessment_not_physical_measurement():
    result=assess_gain_evidence(evidence(task="MEASURE_ONLY"))
    assert result["measured_change_db"] == pytest.approx(-12.0)
    assert result["technical_classification"] == "ATTENUATION_MEASURED"
    assert result["decision"] == "ABSTAIN"
    assert result["reason"] == "DEFECT_CRITERION_NOT_AUTHORIZED"


@pytest.mark.parametrize("processed,classification", [
    (-20.0,"NO_ISSUE_DETECTED"),(-20.2,"NO_ISSUE_DETECTED"),
    (-32.0,"ATTENUATION_DETECTED"),(-26.0,"ATTENUATION_DETECTED"),
])
def test_loss_and_clean_controls(processed,classification):
    assert assess_gain_evidence(evidence(processed=processed))["technical_classification"] == classification


@pytest.mark.parametrize("ref,proc", [(-20,-17),(-20,-8)])
def test_gain_increase_cannot_be_disguised_as_no_issue(ref,proc):
    result=assess_gain_evidence(evidence(reference=ref,processed=proc))
    assert result["technical_classification"]=="GAIN_INCREASE_MEASURED"
    assert result["decision"]=="ABSTAIN"
    assert result["reason"]=="UNSUPPORTED_GAIN_INCREASE_CLASS"


@pytest.mark.parametrize("invalid", [
    {"attenuation_db": -12.0},
    {"reference_comparison_authorized": False},
    {"measurement_uncertainty_db": float("nan")},
    {"measurement_method": "LUFS"},
    {"source_sha256": "invalid"},
    {"processed_mean_dbfs": float("inf")},
    {"maximum_permitted_change_db": -2.0},
])
def test_bad_or_incomplete_evidence_cannot_result_in_automatic_pass(invalid):
    item=evidence()
    item.update(invalid)
    result=assess_gain_evidence(item)
    assert result["decision"]=="ABSTAIN"
    assert result["reason"] in {"MEASUREMENT_INCONSISTENT","REFERENCE_NOT_AUTHORIZED",
                                "INVALID_EVIDENCE"}


def test_ambiguous_threshold_abstains_not_manufacture_anomaly():
    result=assess_gain_evidence(evidence(processed=-21.0,uncertainty=0.05))
    assert result["decision"]=="ABSTAIN"
    assert result["reason"]=="THRESHOLD_AMBIGUOUS"


def test_semantic_mismatch_preserves_real_model_failure_even_if_guard_knows_fact():
    audit=reconcile_gain_decision(evidence(),proposed("NO_ISSUE_DETECTED","NO_ACTION"))
    assert audit["slm_only_grade"]=="FAIL"
    assert audit["haze_decision"]=="ABSTAIN"
    assert audit["abstention_reason"]=="MODEL_CONTRADICTS_MEASUREMENT"
    assert audit["deterministic_classification"]=="ATTENUATION_DETECTED"
    assert audit["hybrid_model_override"] is False


def test_correct_model_proposal_is_review_only_never_mastering_authorization():
    audit=reconcile_gain_decision(evidence(),proposed())
    assert audit["slm_only_grade"]=="PASS"
    assert audit["haze_decision"]=="REVIEW_ONLY"
    assert audit["professional_certification"] is False
    assert audit["hybrid_model_override"] is False


def test_schema_failure_and_unqualified_case_are_auditable_abstentions():
    invalid=reconcile_gain_decision(evidence(),{"finding":"ATTENUATION_DETECTED"})
    assert invalid["slm_only_grade"]=="FAIL"
    assert invalid["abstention_reason"]=="MODEL_SCHEMA_INVALID"
    clean=reconcile_gain_decision(evidence(processed=-20.0),
                   proposed("NO_ISSUE_DETECTED","NO_ACTION"))
    assert clean["haze_decision"]=="REVIEW_ONLY"
    increased=reconcile_gain_decision(evidence(processed=-16.0),
                                     proposed("NO_ISSUE_DETECTED","NO_ACTION"))
    assert increased["haze_decision"]=="ABSTAIN"


def test_metrics_keep_real_model_results_separate_from_test_doubles():
    with pytest.raises(HazeEvidenceError,match="UNATTESTED_MODEL_DATA"):
        evaluation_metrics([{"true":"ATTENUATION_DETECTED","pred":"ATTENUATION_DETECTED"}],
                           attestation="INJECTED_TEST_DOUBLE")
    results=evaluation_metrics([
      {"true":"ATTENUATION_DETECTED","pred":"NO_ISSUE_DETECTED"},
      {"true":"ATTENUATION_DETECTED","pred":"ATTENUATION_DETECTED"},
      {"true":"NO_ISSUE_DETECTED","pred":"NO_ISSUE_DETECTED"},
      {"true":"NO_ISSUE_DETECTED","pred":"ABSTAIN"},
    ],attestation="VERIFIED_MODEL_INFERENCE")
    assert results["sample_count"]==4
    assert results["accuracy"]==0.5
    assert results["false_negative_rate"]==0.5
    assert results["false_abstention_rate"]==0.25
    assert results["professional_certification"] is False

@pytest.mark.parametrize("malformed_finding", [[], {}, 42, None])
def test_malformed_model_field_can_never_crash_or_claim_pass(malformed_finding):
    bad=proposed()
    bad["finding"]=malformed_finding
    report=reconcile_gain_decision(evidence(),bad)
    assert report["haze_decision"]=="ABSTAIN"
    assert report["slm_only_grade"]=="FAIL"
    assert report["abstention_reason"]=="MODEL_SCHEMA_INVALID"
