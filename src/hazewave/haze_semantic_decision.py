"""Typed HAZE acoustic reasoning boundary.

A physical measurement, its task-specific defect verdict, and a fallible
model proposal are separate. The model never becomes measurement authority.
This scope is limited to FFmpeg volumedetect of comparable PCM16 signals.
It does NOT certify perceived loudness, tone, music quality, mixing or mastering.
"""
from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any, Mapping

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FINDINGS = {"ATTENUATION_DETECTED", "NO_ISSUE_DETECTED",
             "SILENCE_DETECTED", "CLIPPING_DETECTED"}
_ACTIONS = {"REVIEW_GAIN_STAGE", "NO_ACTION",
            "RESTORE_SIGNAL_PATH", "REDUCE_GAIN_OR_LIMIT"}

class HazeEvidenceError(ValueError):
    """Typed denial of unsupported benchmark provenance."""


def _abstain(reason: str, measured_change_db: float | None = None) -> dict[str, Any]:
    return {
        "schema": "HazewaveGainSemanticAssessment/v1",
        "measurement_authority": "DETERMINISTIC_FFMPEG",
        "decision": "ABSTAIN",
        "reason": reason,
        "technical_classification": "UNQUALIFIED",
        "measured_change_db": measured_change_db,
        "professional_certification": False,
        "production_authorized": False,
    }


def _number(x: Any) -> bool:
    return type(x) in (float, int) and math.isfinite(x)


def assess_gain_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Treat 'attenuation' as a measured relation, 'defect' as a task judgement.

    The requested task must explicitly require preserving reference level.
    FFmpeg mean_volume is dBFS, not a BS.1770 LUFS or a listening assessment.
    An uncertainty band prevents a boundary from being decided on rounded data.
    """
    if not isinstance(evidence, Mapping):
        return _abstain("INVALID_EVIDENCE")
    mandatory = ("reference_mean_dbfs", "processed_mean_dbfs",
                 "attenuation_db", "measurement_uncertainty_db",
                 "maximum_permitted_change_db")
    if (evidence.get("schema") != "HazewaveGainComparisonEvidence/v1"
        or evidence.get("measurement_method") != "FFMPEG_VOLUMEDETECT_MEAN_DBFS_PCM16"
        or evidence.get("media_scope") != "SYNTHETIC_1S_PCM16"
        or any(not _number(evidence.get(k)) for k in mandatory)
        or not all(isinstance(evidence.get(x), str) and
                   _SHA256.fullmatch(evidence[x]) for x in
                   ("source_sha256", "processed_sha256"))
        or evidence.get("source_sha256") == evidence.get("processed_sha256")):
        return _abstain("INVALID_EVIDENCE")
    ref, processed, observed, uncertainty, tolerance = (
        float(evidence[k]) for k in mandatory
    )
    if (uncertainty < 0 or uncertainty > 1.0 or tolerance < 0
        or tolerance > 80 or ref > 0 or processed > 0):
        return _abstain("INVALID_EVIDENCE")
    delta = round(ref - processed, 3)
    # The reported difference must agree with the two actual measured levels;
    # an arbitrary positive number alone is never sufficient evidence.
    if abs(delta - observed) > max(0.01, uncertainty):
        return _abstain("MEASUREMENT_INCONSISTENT", round(-delta, 3))
    change = round(processed - ref, 3)
    if evidence.get("reference_comparison_authorized") is not True:
        return _abstain("REFERENCE_NOT_AUTHORIZED", change)
    if evidence.get("task_spec") != "PRESERVE_REFERENCE_LEVEL":
        out = _abstain("DEFECT_CRITERION_NOT_AUTHORIZED", change)
        out["technical_classification"] = (
            "ATTENUATION_MEASURED" if change < -uncertainty else
            "GAIN_INCREASE_MEASURED" if change > uncertainty else
            "NEGLIGIBLE_LEVEL_CHANGE")
        return out

    # If a tolerance boundary is within the measurement uncertainty, abstain.
    if abs(abs(change) - tolerance) <= uncertainty:
        return _abstain("THRESHOLD_AMBIGUOUS", change)
    if change < -tolerance - uncertainty:
        classification = "ATTENUATION_DETECTED"
        decision = "MEASURED_CHANGE_REQUIRES_REVIEW"
    elif change > tolerance + uncertainty:
        # Legacy four-class schema has no gain-increase finding; don't
        # mislabel the sound as clean or attenuation.
        out = _abstain("UNSUPPORTED_GAIN_INCREASE_CLASS", change)
        out["technical_classification"] = "GAIN_INCREASE_MEASURED"
        return out
    else:
        classification = "NO_ISSUE_DETECTED"
        decision = "NO_MEASURED_GAIN_DEVIATION"
    return {
        "schema": "HazewaveGainSemanticAssessment/v1",
        "measurement_authority": "DETERMINISTIC_FFMPEG",
        "measured_change_db": change,
        "technical_classification": classification,
        "decision": decision,
        "reason": "NONE",
        "professional_certification": False,
        "production_authorized": False,
    }


def _valid_model_proposal(proposal: Any) -> bool:
    if not isinstance(proposal, dict) or set(proposal) != {
        "finding", "action", "evidence_keys", "requires_human_review"
    }:
        return False
    return (type(proposal["finding"]) is str
            and proposal["finding"] in _FINDINGS
            and type(proposal["action"]) is str
            and proposal["action"] in _ACTIONS
            and type(proposal["evidence_keys"]) is list
            and proposal["evidence_keys"] == ["attenuation_db"]
            and proposal["requires_human_review"] is True)


def reconcile_gain_decision(evidence: Mapping[str, Any],
                            model_proposal: Any) -> dict[str, Any]:
    """A mismatch creates an audit failure and an abstention, not oracle PASS.

    Returns BOTH independent and SLM-only outcomes; never rewrites model output.
    """
    physical = assess_gain_evidence(evidence)
    finding = physical["technical_classification"]
    result: dict[str, Any] = {
        "schema": "HazewaveHazeDecision/v1",
        "model_role": "EVIDENCE_INTERPRETER_ONLY",
        "deterministic_classification": finding,
        "deterministic_decision": physical["decision"],
        "model_proposal_present": model_proposal is not None,
        "slm_only_grade": "NOT_EVALUATED",
        "haze_decision": "ABSTAIN",
        "abstention_reason": "NONE",
        "hybrid_model_override": False,
        "professional_certification": False,
        "production_authorized": False,
        "action_execution_authorized": False,
    }
    if not _valid_model_proposal(model_proposal):
        result.update(slm_only_grade="FAIL", abstention_reason="MODEL_SCHEMA_INVALID")
        return result
    expected = {
        "ATTENUATION_DETECTED": ("ATTENUATION_DETECTED", "REVIEW_GAIN_STAGE"),
        "NO_ISSUE_DETECTED": ("NO_ISSUE_DETECTED", "NO_ACTION"),
    }
    if finding not in expected or physical["decision"] == "ABSTAIN":
        result["abstention_reason"] = physical["reason"]
        return result
    correct_finding, correct_action = expected[finding]
    if (model_proposal["finding"], model_proposal["action"]) != (
        correct_finding, correct_action
    ):
        result.update(slm_only_grade="FAIL",
                      abstention_reason="MODEL_CONTRADICTS_MEASUREMENT")
        return result
    # A sound measured classification remains only a bounded technical
    # suggestion requiring human review, never mastering authority.
    result.update(slm_only_grade="PASS", haze_decision="REVIEW_ONLY")
    return result


def evaluation_metrics(rows: list[dict[str, str]], *,
                       attestation: str) -> dict[str, Any]:
    """Compute evaluation metrics ONLY when run provenance attests real inference.

    A caller-supplied attestation string is not a cryptographic proof: the
    runner must validate SHA/model/receipt provenance before calling this.
    """
    if attestation != "VERIFIED_MODEL_INFERENCE":
        raise HazeEvidenceError("UNATTESTED_MODEL_DATA")
    classes = {"ATTENUATION_DETECTED", "NO_ISSUE_DETECTED"}
    if not rows or any(not isinstance(r,dict) or
                       r.get("true") not in classes or
                       r.get("pred") not in classes | {"ABSTAIN"} for r in rows):
        raise HazeEvidenceError("INVALID_BENCHMARK_ROWS")
    count = len(rows)
    total = Counter(r["true"] for r in rows)
    predictions = Counter(r["pred"] for r in rows)
    correct = sum(r["true"] == r["pred"] for r in rows)
    ab = sum(r["pred"] == "ABSTAIN" for r in rows)
    tp = sum(r["true"] == "ATTENUATION_DETECTED" and
             r["pred"] == "ATTENUATION_DETECTED" for r in rows)
    fn = sum(r["true"] == "ATTENUATION_DETECTED" and
             r["pred"] != "ATTENUATION_DETECTED" for r in rows)
    fp = sum(r["true"] == "NO_ISSUE_DETECTED" and
             r["pred"] == "ATTENUATION_DETECTED" for r in rows)
    tn = sum(r["true"] == "NO_ISSUE_DETECTED" and
             r["pred"] != "ATTENUATION_DETECTED" for r in rows)
    return {
        "sample_count": count,
        "accuracy": correct/count,
        "false_positive_rate": fp/(fp+tn) if fp+tn else None,
        "false_negative_rate": fn/(tp+fn) if tp+fn else None,
        "false_abstention_rate": ab/count,  # all in-domain labelled rows
        "per_class_recall": {
            cl: sum(r["true"]==cl and r["pred"]==cl for r in rows)/total[cl]
            if total[cl] else None for cl in sorted(classes)
        },
        "per_class_precision": {
            cl: sum(r["true"]==cl and r["pred"]==cl for r in rows)/predictions[cl]
            if predictions[cl] else None for cl in sorted(classes)
        },
        "unsafe_confident_decisions": sum(
            r["pred"] != "ABSTAIN" and r["pred"] != r["true"] for r in rows
        ),
        "attestation": "CALLER_ASSERTED_VERIFIED_INFERENCE_REQUIRES_EXTERNAL_RECEIPT",
        "professional_certification": False,
    }
