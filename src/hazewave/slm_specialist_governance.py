"""Fail-closed specialist registry, evidence gating and observed reliability statistics.

The registry is an evaluation proposal, not agent authorization. Even perfect
unattested model outputs NEVER promote professional competence. Real task
execution still flows through the existing Harness and zero-cost 9Router gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from hazewave.harness import AUTHORITY, HazewaveAuthorization, validate_authorization

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "config" / "slm-specialist-registry-v2.json"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_TRIAL = re.compile(r"^[a-z0-9][a-z0-9_-]{7,31}$")
_CASE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,95}$")
_EXPECTED_IDS = ("HAZE_AUDIO_QC", "WAVE_VISUAL_QC", "RE_NATIVE_ANALYSIS")
_ALLOWED_STATES = {"AVAILABLE", "CONNECTED", "EXECUTABLE", "VERIFIED", "PROFESSIONAL"}


class SpecialistGovernanceError(ValueError):
    pass


def load_specialist_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 100000:
            raise SpecialistGovernanceError("REGISTRY_OVERSIZE")
        registry = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise SpecialistGovernanceError("REGISTRY_UNREADABLE") from exc
    if (not isinstance(registry, dict)
            or registry.get("schema") != "HazewaveSpecialistRegistry/v2"
            or registry.get("authority") != AUTHORITY):
        raise SpecialistGovernanceError("REGISTRY_AUTHORITY_INVALID")
    items = registry.get("specialists")
    if not isinstance(items, list) or tuple(s.get("id") for s in items if isinstance(s, dict)) != _EXPECTED_IDS:
        raise SpecialistGovernanceError("REGISTRY_IDENTITY_INVALID")
    for item in items:
        if (item.get("authority") != "NONE"
                or item.get("qualification") not in _ALLOWED_STATES
                or item.get("qualification") != "AVAILABLE"
                or item.get("production_approved") is not False
                or item.get("professional") is not False
                or item.get("harness_authority") != AUTHORITY
                or item.get("domain") not in {"HAZE", "WAVE", "RE"}
                or not isinstance(item.get("tools"), list)
                or not isinstance(item.get("knowledge_refs"), list)
                or not isinstance(item.get("evaluation_suite"), str)
                or item.get("max_attempts") != 1):
            raise SpecialistGovernanceError("REGISTRY_PRETEND_READINESS")
        if item["id"] == "HAZE_AUDIO_QC":
            if (item.get("domain") != "HAZE" or item.get("workflow") != "audio.qc"
                    or item.get("model_id") != "oc/mimo-v2.6-flash-free"
                    or item.get("model_classification") != "UNVERIFIED_ROUTER_ALIAS_LARGE_FAMILY_RISK"
                    or item.get("reference_role") != "EXPERIMENTAL_UNVERIFIED_SIZE_NOT_SLM"
                    or not isinstance(item.get("upstream_family"), dict)
                    or item["upstream_family"].get("exact_router_alias_mapping_verified") is not False):
                raise SpecialistGovernanceError("REGISTRY_HAZE_BINDING_INVALID")
        elif item.get("model_id") is not None:
            raise SpecialistGovernanceError("REGISTRY_UNVERIFIED_MODEL_BINDING")
    registry["policy_sha256"] = hashlib.sha256(raw).hexdigest()
    return registry


def select_specialist(
    authorization: HazewaveAuthorization,
    *, domain: str, requested_workflow: str, risk: str,
    data_classification: str, registry_path: Path = DEFAULT_REGISTRY,
    require_small_model: bool = True,
) -> dict[str, Any]:
    """Propose a candidate only. This function has no tool permissions."""
    registry = load_specialist_registry(registry_path)
    selected = None
    if not isinstance(authorization, HazewaveAuthorization):
        raise SpecialistGovernanceError("HARNESS_AUTHORIZATION_REQUIRED")
    try:
        validate_authorization(
            authorization, expected_task_id=authorization.task_id,
            expected_capability=authorization.capability_id
        )
    except (ValueError, PermissionError) as exc:
        raise SpecialistGovernanceError("HARNESS_AUTHORIZATION_INVALID") from exc
    if (authorization.domain == domain
            and authorization.capability_id == "reason.general"
            and risk == "LOW" and data_classification == "PUBLIC"):
        selected = next(
            (entry for entry in registry["specialists"]
             if entry["domain"] == domain and entry["workflow"] == requested_workflow),
            None
        )
    if selected is not None and selected["id"] == "HAZE_AUDIO_QC" and require_small_model:
        return {
            "schema": "HazewaveSpecialistRoutingProposal/v2",
            "harness_authority": AUTHORITY,
            "task_id": authorization.task_id,
            "decision": "ABSTAIN",
            "reason": "SLM_SIZE_AND_ROUTER_ALIAS_NOT_VERIFIED",
            "specialist_id": None,
            "model_id": None,
            "execution_authorized": False,
            "production_approved": False,
            "policy_sha256": registry["policy_sha256"],
        }
    if selected is not None and selected["id"] == "HAZE_AUDIO_QC":
        return {
            "schema": "HazewaveSpecialistRoutingProposal/v2",
            "harness_authority": AUTHORITY,
            "task_id": authorization.task_id,
            "decision": "EVALUATION_CANDIDATE",
            "reason": "LIVE_ADMISSION_AND_COMPETENCE_NOT_PROVEN",
            "specialist_id": selected["id"],
            "model_id": selected["model_id"],
            "execution_authorized": False,
            "reference_only": True,
            "production_approved": False,
            "policy_sha256": registry["policy_sha256"],
        }
    return {
        "schema": "HazewaveSpecialistRoutingProposal/v2",
        "harness_authority": AUTHORITY,
        "task_id": authorization.task_id,
        "decision": "ABSTAIN",
        "reason": "NO_VERIFIED_SPECIALIST_ROUTE",
        "specialist_id": None,
        "model_id": None,
        "execution_authorized": False,
        "production_approved": False,
        "policy_sha256": registry["policy_sha256"],
    }


def _rate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecialistGovernanceError("BENCHMARK_METRIC_INVALID")
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise SpecialistGovernanceError("BENCHMARK_METRIC_INVALID")
    return x


def evaluate_reliability(reports: list[Mapping[str, Any]], *, min_trials: int = 3) -> dict[str, Any]:
    """Aggregate real or synthetic trials with no authority to promote routing.

    pass@1 is the observed per-trial rate, not a probability estimator.
    observed_pass_all_trials is NOT a population-level pass^k guarantee.
    """
    if not isinstance(reports, list) or len(reports) < min_trials or min_trials < 3 or min_trials > 50:
        raise SpecialistGovernanceError("TRIAL_COUNT_INSUFFICIENT")
    if len(reports) > 50:
        raise SpecialistGovernanceError("TRIAL_BUDGET_EXCEEDED")

    seen: set[str] = set()
    case_ids: set[str] = set()
    hashes: set[str] = set()
    case_successes: dict[str, list[bool]] = {}
    case_digest: dict[str, str] = {}
    current_model: str | None = None
    current_sha: str | None = None
    successes = 0
    baseline_successes = 0
    total_tokens = 0
    total_latency_ms = 0.0

    for row in reports:
        if not isinstance(row, Mapping) or row.get("schema") != "HazewaveSLMAudioSpecialistBenchmark/v1":
            raise SpecialistGovernanceError("TRIAL_SCHEMA_INVALID")
        if (row.get("production_approved") is not False
                or row.get("agent_tool_execution_proven") is not False
                or row.get("model_improvement_proven") is not False):
            raise SpecialistGovernanceError("UNAUTHORIZED_PROMOTION_CLAIM")
        trial, case, digest, sha = (
            row.get("trial_id"), row.get("case_id"),
            row.get("source_evidence_digest_sha256"), row.get("reviewed_source_sha")
        )
        if not isinstance(trial, str) or not _TRIAL.fullmatch(trial):
            raise SpecialistGovernanceError("TRIAL_ID_INVALID")
        if trial in seen:
            raise SpecialistGovernanceError("TRIAL_REPLAY")
        seen.add(trial)
        if not isinstance(case, str) or not _CASE.fullmatch(case):
            raise SpecialistGovernanceError("CASE_ID_INVALID")
        if not isinstance(digest, str) or not _SHA64.fullmatch(digest):
            raise SpecialistGovernanceError("SOURCE_DIGEST_INVALID")
        if not isinstance(sha, str) or not _SHA40.fullmatch(sha):
            raise SpecialistGovernanceError("SOURCE_SHA_INVALID")
        case_ids.add(case)
        hashes.add(digest)
        if case in case_digest and case_digest[case] != digest:
            raise SpecialistGovernanceError("CASE_DIGEST_MISMATCH")
        case_digest[case] = digest
        model = row.get("model_id")
        if not isinstance(model, str) or not model.startswith("oc/") or model == "oc/auto":
            raise SpecialistGovernanceError("MODEL_COHORT_MISMATCH")
        if current_model is None:
            current_model = model
            current_sha = sha
        if current_model != model or current_sha != sha:
            raise SpecialistGovernanceError("MODEL_COHORT_MISMATCH")
        specialist, baseline = row.get("specialist"), row.get("baseline")
        if not isinstance(specialist, Mapping) or not isinstance(baseline, Mapping):
            raise SpecialistGovernanceError("BASELINE_REQUIRED")
        if specialist.get("model_id") != model or baseline.get("model_id") != model:
            raise SpecialistGovernanceError("MODEL_COHORT_MISMATCH")
        if specialist.get("grade") not in {"PASS", "FAIL"} or baseline.get("grade") not in {"PASS", "FAIL"}:
            raise SpecialistGovernanceError("INVALID_GRADE")
        for result in (specialist, baseline):
            tokens = result.get("total_tokens")
            if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
                raise SpecialistGovernanceError("BENCHMARK_METRIC_INVALID")
            total_tokens += tokens
            total_latency_ms += _rate(result.get("elapsed_ms"))
        succeeded = specialist["grade"] == "PASS"
        successes += succeeded
        case_successes.setdefault(case, []).append(succeeded)
        baseline_successes += baseline["grade"] == "PASS"

    # Report pass@k (any of k successful) and observed pass^k
    # (all k successful) ONLY when all cases have exactly k distinct
    # attempts, with at least three distinct cases and three repetitions.
    # Do not estimate repeated consistency from one observation per case.
    repeated_k = (
        len(next(iter(case_successes.values())))
        if len(case_successes) >= 3 else None
    )
    complete_repeats = bool(
        repeated_k is not None and repeated_k >= 3
        and all(len(x) == repeated_k for x in case_successes.values())
    )
    pass_at_k = (
        sum(any(xs) for xs in case_successes.values()) / len(case_successes)
        if complete_repeats else None
    )
    pass_power_k = (
        sum(all(xs) for xs in case_successes.values()) / len(case_successes)
        if complete_repeats else None
    )
    diversity = len(case_ids)
    status = ("INSUFFICIENT_CASE_DIVERSITY" if diversity < 3 or len(hashes) < 3
              else "OBSERVED_UNATTESTED_NOT_PROFESSIONAL")
    return {
        "schema": "HazewaveSpecialistReliabilityObservation/v2",
        "status": status,
        "model_id": current_model,
        "observed_from": "CALLER_SUPPLIED_UNATTESTED_BENCHMARK_RECORDS",
        "attempt_count": len(reports),
        "distinct_case_count": diversity,
        "distinct_evidence_count": len(hashes),
        "pass_at_1": successes / len(reports),
        "baseline_pass_at_1": baseline_successes / len(reports),
        "observed_pass_all_trials": successes == len(reports),
        "repeat_count_per_case": repeated_k if complete_repeats else None,
        "pass_at_k": pass_at_k,
        "pass_power_k": pass_power_k,
        "measured_total_tokens": total_tokens,
        "sum_reported_latency_ms": total_latency_ms,
        "independently_attested": False,
        "professional": False,
        "route_promotion_allowed": False,
        "limits": [
            "No independent workload attestation or professional-grade holdout.",
            "Observed pass across repeats is not a guarantee of future consistency.",
            "pass@k = cases with at least one success in k repeats; pass^k = cases with all k successes. No values for incomplete cohorts.",
            "No trust upgrade from model- or caller-supplied grade labels.",
        ]
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only Hazewave specialist evaluation")
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = p.parse_args(argv)
    try:
        obj = load_specialist_registry(args.registry)
    except SpecialistGovernanceError as exc:
        print("HAZEWAVE_SLM_GOVERNANCE=BLOCKED:" + str(exc))
        return 20
    print(json.dumps({
        "schema": obj["schema"],
        "authority": obj["authority"],
        "policy_sha256": obj["policy_sha256"],
        "specialists": [{
            "id": x["id"], "domain": x["domain"],
            "workflow": x["workflow"],
            "qualification": x["qualification"],
            "professional": x["professional"]
        } for x in obj["specialists"]],
        "production_approved": False,
        "live_model_routing": "NOT_TESTED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
