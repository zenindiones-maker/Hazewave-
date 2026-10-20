from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Final, Iterable


_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^.{64}$")

EXPERTISE_CASES: Final[dict[str, tuple[str, ...]]] = {
    "HAZE_REAPER_EXPERT": (
        "clean-transparent",
        "colored-character",
        "dub-send-fx",
        "dynamic-control",
        "mix-bus-master",
    ),
    "WAVE_VIDEO_EXPERT": (
        "editorial-reasoning",
        "scene-analysis",
        "color-management",
        "conform-render",
        "video-qc",
    ),
    "WAVE_CARTOON_EXPERT": (
        "storyboard-reasoning",
        "timing-reasoning",
        "character-continuity",
        "shot-continuity",
        "animation-construction",
        "compositing",
        "final-qc",
    ),
}

_RUNTIME_EVIDENCE: Final[frozenset[str]] = frozenset(
    {"RUNTIME_PROVEN", "HUMAN_APPROVED_RUNTIME"}
)


class ExpertiseAcceptanceError(RuntimeError):
    pass


def _required_text(value: str, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExpertiseAcceptanceError(code)
    return text


@dataclass(frozen=True)
class ExpertiseCaseEvidence:
    expertise: str
    case_id: str
    proof_id: str
    evidence_type: str
    candidate_head: str
    runtime_identity: str
    decision_digest: str
    artifact_digest: str
    explanation: str
    technical_verification_passed: bool
    human_preference_applied: bool
    evidence_digest: str
    schema: str = "ExpertiseCaseEvidence/v1"

    def __post_init__(self) -> None:
        if self.expertise not in EXPERTISE_CASES:
            raise ExpertiseAcceptanceError(
                f"EXPERTISE_CASE_KIND_INVALID:{self.expertise}"
            )
        _required_text(self.case_id, "EXPERTISE_CASE_ID_REQUIRED")
        _required_text(self.proof_id, "EXPERTISE_CASE_PROOF_ID_REQUIRED")
        _required_text(
            self.runtime_identity,
            "EXPERTISE_CASE_RUNTIME_IDENTITY_REQUIRED",
        )
        _required_text(
            self.explanation,
            "EXPERTISE_CASE_EXPLANATION_REQUIRED",
        )
        if not _SHA1_RE.fullmatch(str(self.candidate_head or "")):
            raise ExpertiseAcceptanceError(
                "EXPERTISE_CASE_CANDIDATE_HEAD_INVALID"
            )
        for value, code in (
            (self.decision_digest, "EXPERTISE_CASE_DECISION_DIGEST_INVALID"),
            (self.artifact_digest, "EXPERTISE_CASE_ARTIFACT_DIGEST_INVALID"),
            (self.evidence_digest, "EXPERTISE_CASE_EVIDENCE_DIGEST_INVALID"),
        ):
            if not _DIGEST_RE.fullmatch(str(value or "")):
                raise ExpertiseAcceptanceError(code)
        if not isinstance(self.technical_verification_passed, bool):
            raise ExpertiseAcceptanceError(
                "EXPERTISE_CASE_TECHNICAL_RESULT_INVALID"
            )
        if not isinstance(self.human_preference_applied, bool):
            raise ExpertiseAcceptanceError(
                "EXPERTISE_CASE_HUMAN_PREFERENCE_RESULT_INVALID"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExpertiseAcceptanceReceipt:
    expertise: str
    candidate_head: str
    status: str
    acceptance_cases: tuple[str, ...]
    missing_cases: tuple[str, ...]
    failed_cases: tuple[str, ...]
    runtime_proven: bool
    distinct_proofs: bool
    distinct_decisions: bool
    distinct_artifacts: bool
    human_preference_learning_proven: bool
    evidence_digests: tuple[str, ...]
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "ExpertiseAcceptanceReceipt/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "acceptance_cases",
            "missing_cases",
            "failed_cases",
            "evidence_digests",
        ):
            value[key] = list(value[key])
        return value


class ExpertiseAcceptanceEvaluator:
    def __init__(self, *, candidate_head: str) -> None:
        if not _SHA1_RE.fullmatch(str(candidate_head or "")):
            raise ExpertiseAcceptanceError(
                "EXPERTISE_ACCEPTANCE_HEAD_INVALID"
            )
        self.candidate_head = candidate_head

    def evaluate(
        self,
        *,
        expertise: str,
        cases: Iterable[ExpertiseCaseEvidence],
    ) -> ExpertiseAcceptanceReceipt:
        required = EXPERTISE_CASES.get(expertise)
        if required is None:
            raise ExpertiseAcceptanceError(
                f"EXPERTISE_ACCEPTANCE_KIND_INVALID:{expertise}"
            )

        materialized = tuple(cases)
        by_case: dict[str, ExpertiseCaseEvidence] = {}
        proof_ids: set[str] = set()
        decisions: set[str] = set()
        artifacts: set[str] = set()

        for case in materialized:
            if not isinstance(case, ExpertiseCaseEvidence):
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_EVIDENCE_INVALID"
                )
            if case.expertise != expertise:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_KIND_MISMATCH"
                )
            if case.candidate_head != self.candidate_head:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_HEAD_MISMATCH"
                )
            if case.evidence_type not in _RUNTIME_EVIDENCE:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_RUNTIME_EVIDENCE_REQUIRED"
                )
            if case.case_id not in required:
                raise ExpertiseAcceptanceError(
                    f"EXPERTISE_CASE_UNEXPECTED:{case.case_id}"
                )
            if case.case_id in by_case:
                raise ExpertiseAcceptanceError(
                    f"EXPERTISE_CASE_DUPLICATE:{case.case_id}"
                )
            if case.proof_id in proof_ids:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_PROOF_REUSED"
                )
            if case.decision_digest in decisions:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_DECISION_REPLAY"
                )
            if case.artifact_digest in artifacts:
                raise ExpertiseAcceptanceError(
                    "EXPERTISE_CASE_ARTIFACT_REUSED"
                )

            by_case[case.case_id] = case
            proof_ids.add(case.proof_id)
            decisions.add(case.decision_digest)
            artifacts.add(case.artifact_digest)

        missing = tuple(case_id for case_id in required if case_id not in by_case)
        failed = tuple(
            case_id
            for case_id in required
            if case_id in by_case
            and not by_case[case_id].technical_verification_passed
        )
        accepted = tuple(
            case_id
            for case_id in required
            if case_id in by_case
            and by_case[case_id].technical_verification_passed
        )
        human_learning = any(
            case.human_preference_applied
            and case.technical_verification_passed
            for case in materialized
        )
        all_runtime_cases = not missing and not failed
        status = (
            "PASS"
            if all_runtime_cases and human_learning
            else "NOT_PROVEN"
        )

        return ExpertiseAcceptanceReceipt(
            expertise=expertise,
            candidate_head=self.candidate_head,
            status=status,
            acceptance_cases=accepted,
            missing_cases=missing,
            failed_cases=failed,
            runtime_proven=status == "PASS",
            distinct_proofs=len(proof_ids) == len(materialized),
            distinct_decisions=len(decisions) == len(materialized),
            distinct_artifacts=len(artifacts) == len(materialized),
            human_preference_learning_proven=human_learning,
            evidence_digests=tuple(case.evidence_digest for case in materialized),
        )
