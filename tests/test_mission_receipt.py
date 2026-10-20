from __future__ import annotations

import pytest

from hazewave.mission_receipt import (
    EvidenceRecord,
    MissionReceiptError,
    compile_creative_execution_receipt,
)


def _evidence(
    key: str,
    *,
    evidence_type: str = "CI_PROVEN",
    candidate_head: str = "c" * 40,
    passed: bool = True,
    acceptance_cases: tuple[str, ...] = (),
) -> EvidenceRecord:
    return EvidenceRecord(
        key=key,
        evidence_type=evidence_type,
        source_id=f"source:{key}",
        candidate_head=candidate_head,
        evidence_digest="a" * 64,
        passed=passed,
        acceptance_cases=acceptance_cases,
    )


def test_receipt_is_exact_bound_and_defaults_missing_proofs_to_not_proven() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="work/zero-cost-workstation-v3",
        base_sha="b" * 40,
        candidate_ref="work/creative-execution-plane-v1",
        candidate_head="c" * 40,
        evidence=(
            _evidence("HAZEWAVE_HARNESS_AUTHORITY"),
            _evidence("PORTFOLIO_AUTHORITY"),
            _evidence("OPTIMISTIC_CONCURRENCY"),
            _evidence("IDEMPOTENCY"),
            _evidence("DURABLE_RECEIPTS"),
            _evidence("AUDIO_QC"),
            _evidence("REFERENCE_PROFILE"),
            _evidence("WAVE_EDITORIAL"),
            _evidence("OTIO_TIMELINE"),
            _evidence("VIDEO_QC"),
            _evidence("COLOR_MANAGEMENT"),
            _evidence("HAZE_WAVE_BRIDGE"),
            _evidence("UNIT_TESTS"),
            _evidence("CONTRACT_VALIDATION"),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.schema == "CreativeExecutionPlaneReceipt/v1"
    assert receipt.BASE_REF == "work/zero-cost-workstation-v3"
    assert receipt.BASE_SHA == "b" * 40
    assert receipt.CANDIDATE_REF == "work/creative-execution-plane-v1"
    assert receipt.CANDIDATE_HEAD == "c" * 40
    assert receipt.fields["AUDIO_QC"].status == "PASS"
    assert receipt.fields["LIVE_REAPER_PROOF"].status == "NOT_PROVEN"
    assert receipt.fields["LIVE_WAVE_PROOF"].status == "NOT_PROVEN"
    assert receipt.fields["CARTOON_LIVE_PROOF"].status == "NOT_PROVEN"
    assert receipt.fields["HAZE_REAPER_EXPERT"].status == "NOT_PROVEN"
    assert receipt.fields["WAVE_CARTOON_EXPERT"].status == "NOT_PROVEN"
    assert receipt.PAID_FALLBACK is False
    assert receipt.UNKNOWN_COST_FALLBACK is False
    assert receipt.CANONICAL_PROMOTION_ATTEMPTED is False


@pytest.mark.parametrize(
    "field",
    [
        "REAPER_BRIDGE",
        "REAPER_SNAPSHOT",
        "UNDO_TRANSACTION",
        "HAZE_PRODUCER_LOOP",
        "LIVE_REAPER_PROOF",
        "LIVE_WAVE_PROOF",
        "GREASE_PENCIL_RUNTIME",
        "CARTOON_LIVE_PROOF",
    ],
)
def test_runtime_only_fields_cannot_pass_from_ci(field: str) -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(_evidence(field, evidence_type="CI_PROVEN"),),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields[field].status == "NOT_PROVEN"
    assert receipt.fields[field].evidence_type == "CI_PROVEN"
    assert receipt.fields[field].required_evidence_type == "RUNTIME_PROVEN"


def test_runtime_only_field_passes_with_exact_bound_runtime_evidence() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(
            _evidence(
                "LIVE_REAPER_PROOF",
                evidence_type="RUNTIME_PROVEN",
            ),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields["LIVE_REAPER_PROOF"].status == "PASS"


def test_documentation_evidence_can_never_emit_pass() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(
            _evidence(
                "AUDIO_QC",
                evidence_type="DOCUMENTATION",
            ),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields["AUDIO_QC"].status == "NOT_PROVEN"


def test_evidence_bound_to_different_candidate_head_is_rejected() -> None:
    with pytest.raises(MissionReceiptError, match="RECEIPT_EVIDENCE_HEAD_MISMATCH"):
        compile_creative_execution_receipt(
            base_ref="base",
            base_sha="b" * 40,
            candidate_ref="candidate",
            candidate_head="c" * 40,
            evidence=(
                _evidence(
                    "AUDIO_QC",
                    candidate_head="d" * 40,
                ),
            ),
            paid_fallback=False,
            unknown_cost_fallback=False,
            canonical_promotion_attempted=False,
        )


def test_failed_evidence_never_emits_pass() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(
            _evidence("AUDIO_QC", passed=False),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields["AUDIO_QC"].status == "FAIL"


def test_expertise_requires_runtime_acceptance_cases_not_generic_runtime_marker() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(
            _evidence(
                "HAZE_REAPER_EXPERT",
                evidence_type="RUNTIME_PROVEN",
                acceptance_cases=("clean", "colored", "dub"),
            ),
            _evidence(
                "WAVE_CARTOON_EXPERT",
                evidence_type="RUNTIME_PROVEN",
                acceptance_cases=("storyboard", "timing", "continuity"),
            ),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields["HAZE_REAPER_EXPERT"].status == "NOT_PROVEN"
    assert receipt.fields["WAVE_CARTOON_EXPERT"].status == "NOT_PROVEN"


def test_expertise_passes_only_with_required_distinct_acceptance_cases() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(
            _evidence(
                "HAZE_REAPER_EXPERT",
                evidence_type="RUNTIME_PROVEN",
                acceptance_cases=(
                    "clean-transparent",
                    "colored-character",
                    "dub-send-fx",
                    "dynamic-control",
                    "mix-bus-master",
                ),
            ),
            _evidence(
                "WAVE_CARTOON_EXPERT",
                evidence_type="RUNTIME_PROVEN",
                acceptance_cases=(
                    "storyboard-reasoning",
                    "timing-reasoning",
                    "character-continuity",
                    "shot-continuity",
                    "animation-construction",
                    "compositing",
                    "final-qc",
                ),
            ),
        ),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    assert receipt.fields["HAZE_REAPER_EXPERT"].status == "PASS"
    assert receipt.fields["WAVE_CARTOON_EXPERT"].status == "PASS"


def test_receipt_refuses_paid_unknown_or_canonical_promotion_claims() -> None:
    with pytest.raises(MissionReceiptError, match="RECEIPT_ZERO_COST_INVARIANT_VIOLATION"):
        compile_creative_execution_receipt(
            base_ref="base",
            base_sha="b" * 40,
            candidate_ref="candidate",
            candidate_head="c" * 40,
            evidence=(),
            paid_fallback=True,
            unknown_cost_fallback=False,
            canonical_promotion_attempted=False,
        )

    with pytest.raises(MissionReceiptError, match="RECEIPT_CANONICAL_PROMOTION_FORBIDDEN"):
        compile_creative_execution_receipt(
            base_ref="base",
            base_sha="b" * 40,
            candidate_ref="candidate",
            candidate_head="c" * 40,
            evidence=(),
            paid_fallback=False,
            unknown_cost_fallback=False,
            canonical_promotion_attempted=True,
        )


def test_updated_receipt_contains_all_required_user_fields() -> None:
    receipt = compile_creative_execution_receipt(
        base_ref="base",
        base_sha="b" * 40,
        candidate_ref="candidate",
        candidate_head="c" * 40,
        evidence=(),
        paid_fallback=False,
        unknown_cost_fallback=False,
        canonical_promotion_attempted=False,
    )

    required = {
        "HAZEWAVE_HARNESS_AUTHORITY",
        "PORTFOLIO_AUTHORITY",
        "REAPER_BRIDGE",
        "REAPER_SNAPSHOT",
        "OPTIMISTIC_CONCURRENCY",
        "UNDO_TRANSACTION",
        "IDEMPOTENCY",
        "DURABLE_RECEIPTS",
        "HAZE_PRODUCER_LOOP",
        "AUDIO_QC",
        "REFERENCE_PROFILE",
        "WAVE_EDITORIAL",
        "OTIO_TIMELINE",
        "VIDEO_QC",
        "COLOR_MANAGEMENT",
        "HAZE_WAVE_BRIDGE",
        "UNIT_TESTS",
        "CONTRACT_VALIDATION",
        "LIVE_REAPER_PROOF",
        "LIVE_WAVE_PROOF",
        "REAPER_EXPERT_KNOWLEDGE",
        "REAPER_EXTENSION_REGISTRY",
        "PLUGIN_REGISTRY",
        "PLUGIN_QUALIFICATION_LAB",
        "FREE_PLUGIN_POLICY",
        "NATIVE_LINUX_PLUGIN_POLICY",
        "PLUGIN_PRODUCTION_APPROVAL",
        "MUSIC_PRODUCTION_KNOWLEDGE",
        "GENRE_PRODUCTION_PROFILES",
        "DUB_PRODUCTION_PROFILE",
        "LISTENING_REASONING",
        "WAVE_FINAL_VIDEO_MODE",
        "ANIMATION_KNOWLEDGE",
        "CHARACTER_BIBLE",
        "STYLE_BIBLE",
        "STORYBOARD",
        "ANIMATIC",
        "SHOT_CONTRACTS",
        "EXPOSURE_SHEET",
        "BLENDER_BRIDGE",
        "GREASE_PENCIL_RUNTIME",
        "OPENTOONZ_QUALIFICATION",
        "KRITA_QUALIFICATION",
        "LIP_SYNC_PIPELINE",
        "ANIMATION_FRAME_SEQUENCE",
        "ANIMATION_QC",
        "CARTOON_LIVE_PROOF",
        "KNOWLEDGE_FRESHNESS",
        "HAZE_REAPER_EXPERT",
        "WAVE_VIDEO_EXPERT",
        "WAVE_CARTOON_EXPERT",
    }

    assert required.issubset(receipt.fields)
