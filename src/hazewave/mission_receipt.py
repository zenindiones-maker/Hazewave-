from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Final, Iterable


_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EVIDENCE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "DOCUMENTATION",
        "STATIC_IMPLEMENTED",
        "CI_PROVEN",
        "RUNTIME_PROVEN",
        "HUMAN_APPROVED_RUNTIME",
    }
)

REQUIRED_FIELDS: Final[tuple[str, ...]] = (
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
)

_RUNTIME_ONLY: Final[frozenset[str]] = frozenset(
    {
        "REAPER_BRIDGE",
        "REAPER_SNAPSHOT",
        "UNDO_TRANSACTION",
        "HAZE_PRODUCER_LOOP",
        "LIVE_REAPER_PROOF",
        "LIVE_WAVE_PROOF",
        "PLUGIN_PRODUCTION_APPROVAL",
        "GREASE_PENCIL_RUNTIME",
        "OPENTOONZ_QUALIFICATION",
        "KRITA_QUALIFICATION",
        "ANIMATION_FRAME_SEQUENCE",
        "CARTOON_LIVE_PROOF",
        "HAZE_REAPER_EXPERT",
        "WAVE_VIDEO_EXPERT",
        "WAVE_CARTOON_EXPERT",
    }
)

_EXPERT_CASES: Final[dict[str, frozenset[str]]] = {
    "HAZE_REAPER_EXPERT": frozenset(
        {
            "clean-transparent",
            "colored-character",
            "dub-send-fx",
            "dynamic-control",
            "mix-bus-master",
        }
    ),
    "WAVE_VIDEO_EXPERT": frozenset(
        {
            "editorial-reasoning",
            "scene-analysis",
            "color-management",
            "conform-render",
            "video-qc",
        }
    ),
    "WAVE_CARTOON_EXPERT": frozenset(
        {
            "storyboard-reasoning",
            "timing-reasoning",
            "character-continuity",
            "shot-continuity",
            "animation-construction",
            "compositing",
            "final-qc",
        }
    ),
}

_DECLARED_VALUES: Final[dict[str, str]] = {
    "HAZEWAVE_HARNESS_AUTHORITY": "HAZEWAVE_HARNESS",
    "PORTFOLIO_AUTHORITY": "NONE",
    "FREE_PLUGIN_POLICY": "ZERO_COST_ONLY",
    "NATIVE_LINUX_PLUGIN_POLICY": "NATIVE_LINUX_X86_64",
    "WAVE_FINAL_VIDEO_MODE": "ANIMATED_CARTOON",
}


class MissionReceiptError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceRecord:
    key: str
    evidence_type: str
    source_id: str
    candidate_head: str
    evidence_digest: str
    passed: bool
    acceptance_cases: tuple[str, ...] = ()
    schema: str = "MissionEvidenceRecord/v1"

    def __post_init__(self) -> None:
        if self.key not in REQUIRED_FIELDS:
            raise MissionReceiptError(f"RECEIPT_UNKNOWN_FIELD:{self.key}")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise MissionReceiptError(
                f"RECEIPT_EVIDENCE_TYPE_INVALID:{self.evidence_type}"
            )
        if not str(self.source_id or "").strip():
            raise MissionReceiptError("RECEIPT_EVIDENCE_SOURCE_REQUIRED")
        if not _SHA1_RE.fullmatch(str(self.candidate_head or "")):
            raise MissionReceiptError("RECEIPT_EVIDENCE_HEAD_INVALID")
        if not _SHA256_RE.fullmatch(str(self.evidence_digest or "")):
            raise MissionReceiptError("RECEIPT_EVIDENCE_DIGEST_INVALID")
        if not isinstance(self.passed, bool):
            raise MissionReceiptError("RECEIPT_EVIDENCE_RESULT_INVALID")
        if len(set(self.acceptance_cases)) != len(self.acceptance_cases):
            raise MissionReceiptError(
                "RECEIPT_EVIDENCE_ACCEPTANCE_CASE_DUPLICATE"
            )
        if any(not str(item or "").strip() for item in self.acceptance_cases):
            raise MissionReceiptError(
                "RECEIPT_EVIDENCE_ACCEPTANCE_CASE_INVALID"
            )


@dataclass(frozen=True)
class MissionFieldStatus:
    field: str
    status: str
    required_evidence_type: str
    evidence_type: str | None
    source_id: str | None
    evidence_digest: str | None
    acceptance_cases: tuple[str, ...]
    declared_value: str | None = None
    schema: str = "MissionFieldStatus/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["acceptance_cases"] = list(self.acceptance_cases)
        return value


@dataclass(frozen=True)
class CreativeExecutionPlaneReceipt:
    BASE_REF: str
    BASE_SHA: str
    CANDIDATE_REF: str
    CANDIDATE_HEAD: str
    fields: dict[str, MissionFieldStatus]
    PAID_FALLBACK: bool
    UNKNOWN_COST_FALLBACK: bool
    CANONICAL_PROMOTION_ATTEMPTED: bool
    schema: str = "CreativeExecutionPlaneReceipt/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "BASE_REF": self.BASE_REF,
            "BASE_SHA": self.BASE_SHA,
            "CANDIDATE_REF": self.CANDIDATE_REF,
            "CANDIDATE_HEAD": self.CANDIDATE_HEAD,
            **{
                key: self.fields[key].to_dict()
                for key in REQUIRED_FIELDS
            },
            "PAID_FALLBACK": self.PAID_FALLBACK,
            "UNKNOWN_COST_FALLBACK": self.UNKNOWN_COST_FALLBACK,
            "CANONICAL_PROMOTION_ATTEMPTED": self.CANONICAL_PROMOTION_ATTEMPTED,
        }


def _required_evidence_type(field: str) -> str:
    return "RUNTIME_PROVEN" if field in _RUNTIME_ONLY else "CI_PROVEN"


def _evidence_satisfies(
    record: EvidenceRecord,
    *,
    required: str,
) -> bool:
    if not record.passed:
        return False
    if record.evidence_type in {"DOCUMENTATION", "STATIC_IMPLEMENTED"}:
        return False
    if required == "CI_PROVEN":
        return record.evidence_type in {
            "CI_PROVEN",
            "RUNTIME_PROVEN",
            "HUMAN_APPROVED_RUNTIME",
        }
    if required == "RUNTIME_PROVEN":
        return record.evidence_type in {
            "RUNTIME_PROVEN",
            "HUMAN_APPROVED_RUNTIME",
        }
    raise MissionReceiptError(
        f"RECEIPT_REQUIRED_EVIDENCE_TYPE_INVALID:{required}"
    )


def _field_status(
    field: str,
    record: EvidenceRecord | None,
) -> MissionFieldStatus:
    required = _required_evidence_type(field)
    declared_value = _DECLARED_VALUES.get(field)

    if record is None:
        return MissionFieldStatus(
            field=field,
            status="NOT_PROVEN",
            required_evidence_type=required,
            evidence_type=None,
            source_id=None,
            evidence_digest=None,
            acceptance_cases=(),
            declared_value=declared_value,
        )

    if not record.passed:
        status = "FAIL"
    elif not _evidence_satisfies(record, required=required):
        status = "NOT_PROVEN"
    else:
        required_cases = _EXPERT_CASES.get(field)
        if required_cases is not None and not required_cases.issubset(
            set(record.acceptance_cases)
        ):
            status = "NOT_PROVEN"
        else:
            status = "PASS"

    return MissionFieldStatus(
        field=field,
        status=status,
        required_evidence_type=required,
        evidence_type=record.evidence_type,
        source_id=record.source_id,
        evidence_digest=record.evidence_digest,
        acceptance_cases=record.acceptance_cases,
        declared_value=declared_value,
    )


def compile_creative_execution_receipt(
    *,
    base_ref: str,
    base_sha: str,
    candidate_ref: str,
    candidate_head: str,
    evidence: Iterable[EvidenceRecord],
    paid_fallback: bool,
    unknown_cost_fallback: bool,
    canonical_promotion_attempted: bool,
) -> CreativeExecutionPlaneReceipt:
    base_ref_value = str(base_ref or "").strip()
    candidate_ref_value = str(candidate_ref or "").strip()
    if not base_ref_value or not candidate_ref_value:
        raise MissionReceiptError("RECEIPT_REF_REQUIRED")
    if not _SHA1_RE.fullmatch(str(base_sha or "")):
        raise MissionReceiptError("RECEIPT_BASE_SHA_INVALID")
    if not _SHA1_RE.fullmatch(str(candidate_head or "")):
        raise MissionReceiptError("RECEIPT_CANDIDATE_HEAD_INVALID")
    if paid_fallback or unknown_cost_fallback:
        raise MissionReceiptError(
            "RECEIPT_ZERO_COST_INVARIANT_VIOLATION"
        )
    if canonical_promotion_attempted:
        raise MissionReceiptError(
            "RECEIPT_CANONICAL_PROMOTION_FORBIDDEN"
        )

    records: dict[str, EvidenceRecord] = {}
    source_ids: set[str] = set()
    for record in evidence:
        if not isinstance(record, EvidenceRecord):
            raise MissionReceiptError("RECEIPT_EVIDENCE_RECORD_INVALID")
        if record.candidate_head != candidate_head:
            raise MissionReceiptError(
                f"RECEIPT_EVIDENCE_HEAD_MISMATCH:{record.key}"
            )
        if record.key in records:
            raise MissionReceiptError(
                f"RECEIPT_DUPLICATE_EVIDENCE_KEY:{record.key}"
            )
        if record.source_id in source_ids:
            raise MissionReceiptError(
                f"RECEIPT_DUPLICATE_EVIDENCE_SOURCE:{record.source_id}"
            )
        records[record.key] = record
        source_ids.add(record.source_id)

    fields = {
        field: _field_status(field, records.get(field))
        for field in REQUIRED_FIELDS
    }

    return CreativeExecutionPlaneReceipt(
        BASE_REF=base_ref_value,
        BASE_SHA=str(base_sha),
        CANDIDATE_REF=candidate_ref_value,
        CANDIDATE_HEAD=str(candidate_head),
        fields=fields,
        PAID_FALLBACK=False,
        UNKNOWN_COST_FALLBACK=False,
        CANONICAL_PROMOTION_ATTEMPTED=False,
    )
