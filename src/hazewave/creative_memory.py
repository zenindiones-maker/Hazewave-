from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HUMAN_OUTCOMES = frozenset({"APPROVED", "REJECTED", "PENDING"})
_CREATIVE_DECISIONS = frozenset({"ACCEPT", "REVISE", "ROLLBACK", "HUMAN_REVIEW"})


class CreativeMemoryError(RuntimeError):
    pass


def _require_text(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CreativeMemoryError(code)
    return normalized


def _require_sha256(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not _SHA256_RE.fullmatch(normalized):
        raise CreativeMemoryError(code)
    return normalized


@dataclass(frozen=True)
class HumanPreferenceSignal:
    signal_id: str
    scope: str
    dimension: str
    preference_score: float
    source_review_id: str
    evidence_digest: str
    schema: str = "HumanPreferenceSignal/v1"

    def __post_init__(self) -> None:
        _require_text(self.signal_id, "CREATIVE_MEMORY_SIGNAL_ID_REQUIRED")
        _require_text(self.scope, "CREATIVE_MEMORY_SIGNAL_SCOPE_REQUIRED")
        _require_text(self.dimension, "CREATIVE_MEMORY_SIGNAL_DIMENSION_REQUIRED")
        _require_text(
            self.source_review_id,
            "CREATIVE_MEMORY_SIGNAL_SOURCE_REVIEW_REQUIRED",
        )
        _require_sha256(
            self.evidence_digest,
            "CREATIVE_MEMORY_SIGNAL_EVIDENCE_DIGEST_INVALID",
        )
        try:
            score = float(self.preference_score)
        except (TypeError, ValueError) as exc:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_PREFERENCE_SCORE_INVALID"
            ) from exc
        if score < -1.0 or score > 1.0:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_PREFERENCE_SCORE_INVALID"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HumanPreferenceSignal":
        if payload.get("schema") != "HumanPreferenceSignal/v1":
            raise CreativeMemoryError("CREATIVE_MEMORY_SIGNAL_SCHEMA_INVALID")
        try:
            return cls(
                signal_id=str(payload["signal_id"]),
                scope=str(payload["scope"]),
                dimension=str(payload["dimension"]),
                preference_score=float(payload["preference_score"]),
                source_review_id=str(payload["source_review_id"]),
                evidence_digest=str(payload["evidence_digest"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_SIGNAL_MALFORMED"
            ) from exc


@dataclass(frozen=True)
class MixDecision:
    decision_id: str
    scope: str
    capability: str
    tool_id: str
    parameter_summary: Mapping[str, Any]
    rationale: str
    evidence_digest: str
    schema: str = "MixDecision/v1"

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "CREATIVE_MEMORY_DECISION_ID_REQUIRED")
        _require_text(self.scope, "CREATIVE_MEMORY_DECISION_SCOPE_REQUIRED")
        _require_text(
            self.capability,
            "CREATIVE_MEMORY_DECISION_CAPABILITY_REQUIRED",
        )
        _require_text(self.tool_id, "CREATIVE_MEMORY_DECISION_TOOL_REQUIRED")
        if not isinstance(self.parameter_summary, Mapping):
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_DECISION_PARAMETERS_INVALID"
            )
        _require_text(
            self.rationale,
            "CREATIVE_MEMORY_DECISION_RATIONALE_REQUIRED",
        )
        _require_sha256(
            self.evidence_digest,
            "CREATIVE_MEMORY_DECISION_EVIDENCE_DIGEST_INVALID",
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parameter_summary"] = dict(self.parameter_summary)
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MixDecision":
        if payload.get("schema") != "MixDecision/v1":
            raise CreativeMemoryError("CREATIVE_MEMORY_DECISION_SCHEMA_INVALID")
        try:
            parameters = payload["parameter_summary"]
            if not isinstance(parameters, Mapping):
                raise TypeError("parameter_summary")
            return cls(
                decision_id=str(payload["decision_id"]),
                scope=str(payload["scope"]),
                capability=str(payload["capability"]),
                tool_id=str(payload["tool_id"]),
                parameter_summary=dict(parameters),
                rationale=str(payload["rationale"]),
                evidence_digest=str(payload["evidence_digest"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_DECISION_MALFORMED"
            ) from exc


@dataclass(frozen=True)
class ProductionReview:
    review_id: str
    decision_id: str
    artifact_sha256: str
    technical_status: str
    creative_decision: str
    human_outcome: str
    notes: str
    preference_signals: tuple[HumanPreferenceSignal, ...]
    schema: str = "ProductionReview/v1"

    def __post_init__(self) -> None:
        _require_text(self.review_id, "CREATIVE_MEMORY_REVIEW_ID_REQUIRED")
        _require_text(self.decision_id, "CREATIVE_MEMORY_REVIEW_DECISION_REQUIRED")
        _require_sha256(
            self.artifact_sha256,
            "CREATIVE_MEMORY_REVIEW_ARTIFACT_SHA_INVALID",
        )
        _require_text(
            self.technical_status,
            "CREATIVE_MEMORY_REVIEW_TECHNICAL_STATUS_REQUIRED",
        )
        if self.creative_decision not in _CREATIVE_DECISIONS:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_REVIEW_CREATIVE_DECISION_INVALID"
            )
        if self.human_outcome not in _HUMAN_OUTCOMES:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_REVIEW_HUMAN_OUTCOME_INVALID"
            )
        if not isinstance(self.preference_signals, tuple):
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_REVIEW_SIGNALS_INVALID"
            )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["preference_signals"] = [
            signal.to_dict() for signal in self.preference_signals
        ]
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProductionReview":
        if payload.get("schema") != "ProductionReview/v1":
            raise CreativeMemoryError("CREATIVE_MEMORY_REVIEW_SCHEMA_INVALID")
        try:
            raw_signals = payload["preference_signals"]
            if not isinstance(raw_signals, list):
                raise TypeError("preference_signals")
            return cls(
                review_id=str(payload["review_id"]),
                decision_id=str(payload["decision_id"]),
                artifact_sha256=str(payload["artifact_sha256"]),
                technical_status=str(payload["technical_status"]),
                creative_decision=str(payload["creative_decision"]),
                human_outcome=str(payload["human_outcome"]),
                notes=str(payload.get("notes") or ""),
                preference_signals=tuple(
                    HumanPreferenceSignal.from_dict(item)
                    for item in raw_signals
                    if isinstance(item, Mapping)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_REVIEW_MALFORMED"
            ) from exc


@dataclass(frozen=True)
class HumanPreferenceSummary:
    scope: str
    dimension: str
    signal_count: int
    preference_score: float
    include_global: bool
    grants_execution_authority: bool = False
    schema: str = "HumanPreferenceSummary/v1"


class CreativeMemoryStore:
    schema = "CreativeMemoryStore/v1"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "creative-memory-v1.json"
        self._decisions: dict[str, MixDecision] = {}
        self._reviews: dict[str, ProductionReview] = {}
        self._signals: dict[str, HumanPreferenceSignal] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_STORE_MALFORMED"
            ) from exc
        if not isinstance(payload, dict) or payload.get("schema") != self.schema:
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_SCHEMA_INVALID")
        if payload.get("authority") != "NONE":
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_AUTHORITY_INVALID")
        if payload.get("grants_execution_authority") is not False:
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_AUTHORITY_INVALID")
        if payload.get("can_publish") is not False:
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_AUTHORITY_INVALID")
        if payload.get("can_modify_canonical_policy") is not False:
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_AUTHORITY_INVALID")

        decisions = payload.get("decisions")
        reviews = payload.get("reviews")
        signals = payload.get("preference_signals")
        if not isinstance(decisions, list) or not isinstance(reviews, list) or not isinstance(signals, list):
            raise CreativeMemoryError("CREATIVE_MEMORY_STORE_MALFORMED")

        for item in decisions:
            if not isinstance(item, Mapping):
                raise CreativeMemoryError("CREATIVE_MEMORY_STORE_MALFORMED")
            decision = MixDecision.from_dict(item)
            if decision.decision_id in self._decisions:
                raise CreativeMemoryError("CREATIVE_MEMORY_DUPLICATE_DECISION_ID")
            self._decisions[decision.decision_id] = decision

        for item in reviews:
            if not isinstance(item, Mapping):
                raise CreativeMemoryError("CREATIVE_MEMORY_STORE_MALFORMED")
            review = ProductionReview.from_dict(item)
            if review.review_id in self._reviews:
                raise CreativeMemoryError("CREATIVE_MEMORY_DUPLICATE_REVIEW_ID")
            self._reviews[review.review_id] = review

        for item in signals:
            if not isinstance(item, Mapping):
                raise CreativeMemoryError("CREATIVE_MEMORY_STORE_MALFORMED")
            signal = HumanPreferenceSignal.from_dict(item)
            if signal.signal_id in self._signals:
                raise CreativeMemoryError("CREATIVE_MEMORY_DUPLICATE_SIGNAL_ID")
            self._signals[signal.signal_id] = signal

    def _write(self) -> None:
        payload = self.snapshot()
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".creative-memory-v1.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                json.dump(
                    payload,
                    handle,
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if temp_name is not None and os.path.exists(temp_name):
                os.unlink(temp_name)

    def record_decision(self, decision: MixDecision) -> None:
        if decision.decision_id in self._decisions:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_DUPLICATE_DECISION_ID"
            )
        self._decisions[decision.decision_id] = decision
        try:
            self._write()
        except Exception:
            self._decisions.pop(decision.decision_id, None)
            raise

    def record_review(self, review: ProductionReview) -> None:
        if review.review_id in self._reviews:
            raise CreativeMemoryError("CREATIVE_MEMORY_DUPLICATE_REVIEW_ID")
        decision = self._decisions.get(review.decision_id)
        if decision is None:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_REVIEW_DECISION_NOT_FOUND"
            )

        if review.preference_signals and review.human_outcome not in {
            "APPROVED",
            "REJECTED",
        }:
            raise CreativeMemoryError(
                "CREATIVE_MEMORY_HUMAN_OUTCOME_REQUIRED_FOR_SIGNALS"
            )

        seen: set[str] = set()
        for signal in review.preference_signals:
            if signal.source_review_id != review.review_id:
                raise CreativeMemoryError(
                    "CREATIVE_MEMORY_SIGNAL_REVIEW_MISMATCH"
                )
            if signal.scope != decision.scope:
                raise CreativeMemoryError(
                    "CREATIVE_MEMORY_SIGNAL_SCOPE_MISMATCH"
                )
            if signal.signal_id in self._signals or signal.signal_id in seen:
                raise CreativeMemoryError(
                    "CREATIVE_MEMORY_DUPLICATE_SIGNAL_ID"
                )
            seen.add(signal.signal_id)

        self._reviews[review.review_id] = review
        for signal in review.preference_signals:
            self._signals[signal.signal_id] = signal
        try:
            self._write()
        except Exception:
            self._reviews.pop(review.review_id, None)
            for signal in review.preference_signals:
                self._signals.pop(signal.signal_id, None)
            raise

    def preference_summary(
        self,
        *,
        scope: str,
        dimension: str,
        include_global: bool,
    ) -> HumanPreferenceSummary:
        scope_value = _require_text(
            scope,
            "CREATIVE_MEMORY_SUMMARY_SCOPE_REQUIRED",
        )
        dimension_value = _require_text(
            dimension,
            "CREATIVE_MEMORY_SUMMARY_DIMENSION_REQUIRED",
        )
        allowed_scopes = {scope_value}
        if include_global:
            allowed_scopes.add("global")

        matching = [
            signal
            for signal in self._signals.values()
            if signal.dimension == dimension_value
            and signal.scope in allowed_scopes
        ]
        score = (
            sum(float(signal.preference_score) for signal in matching)
            / len(matching)
            if matching
            else 0.0
        )
        return HumanPreferenceSummary(
            scope=scope_value,
            dimension=dimension_value,
            signal_count=len(matching),
            preference_score=score,
            include_global=include_global,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "authority": "NONE",
            "grants_execution_authority": False,
            "can_publish": False,
            "can_modify_canonical_policy": False,
            "decisions": [
                self._decisions[key].to_dict()
                for key in sorted(self._decisions)
            ],
            "reviews": [
                self._reviews[key].to_dict()
                for key in sorted(self._reviews)
            ],
            "preference_signals": [
                self._signals[key].to_dict()
                for key in sorted(self._signals)
            ],
        }
