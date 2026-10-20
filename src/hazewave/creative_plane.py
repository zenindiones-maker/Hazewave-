from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import hmac
import json
from typing import Final


FREE_PRODUCTION_COST_CLASSES: Final[frozenset[str]] = frozenset(
    {"FREE_OPEN_SOURCE", "FREEWARE_NO_PAYMENT"}
)
NATIVE_LINUX_FORMATS: Final[frozenset[str]] = frozenset(
    {"VST3", "CLAP", "LV2", "JSFX"}
)


@dataclass(frozen=True)
class ExecutionReceiptPayload:
    project_id: str
    task_id: str
    capability: str
    domain: str
    candidate_head: str
    policy_digest: str
    runtime_identity: str
    reaper_project_identity: str
    state_before: int
    state_after: int
    idempotency_key: str
    operation_result: str
    artifact_hashes: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionReceipt:
    project_id: str
    task_id: str
    capability: str
    domain: str
    candidate_head: str
    policy_digest: str
    runtime_identity: str
    reaper_project_identity: str
    state_before: int
    state_after: int
    idempotency_key: str
    operation_result: str
    artifact_hashes: tuple[str, ...]
    signature: str
    attestation: str = "HMAC_SHA256_RUNTIME_KEY"
    schema: str = "HazewaveExecutionReceipt/v1"


class RuntimeReceiptSigner:
    """Signs runtime execution evidence with a project-local secret.

    The key is deliberately supplied by runtime state/config and is never derived
    from caller-controlled receipt fields or repository contents.
    """

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("RUNTIME_ATTESTATION_KEY_TOO_SHORT")
        self._key = key

    @staticmethod
    def _canonical(payload: ExecutionReceiptPayload) -> bytes:
        value = asdict(payload)
        value["artifact_hashes"] = list(payload.artifact_hashes)
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def sign(self, payload: ExecutionReceiptPayload) -> ExecutionReceipt:
        signature = hmac.new(
            self._key,
            self._canonical(payload),
            hashlib.sha256,
        ).hexdigest()
        return ExecutionReceipt(
            **asdict(payload),
            signature=signature,
        )

    def verify(self, receipt: ExecutionReceipt) -> bool:
        if (
            receipt.schema != "HazewaveExecutionReceipt/v1"
            or receipt.attestation != "HMAC_SHA256_RUNTIME_KEY"
        ):
            return False
        payload = ExecutionReceiptPayload(
            project_id=receipt.project_id,
            task_id=receipt.task_id,
            capability=receipt.capability,
            domain=receipt.domain,
            candidate_head=receipt.candidate_head,
            policy_digest=receipt.policy_digest,
            runtime_identity=receipt.runtime_identity,
            reaper_project_identity=receipt.reaper_project_identity,
            state_before=receipt.state_before,
            state_after=receipt.state_after,
            idempotency_key=receipt.idempotency_key,
            operation_result=receipt.operation_result,
            artifact_hashes=receipt.artifact_hashes,
        )
        expected = hmac.new(
            self._key,
            self._canonical(payload),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, receipt.signature)


@dataclass(frozen=True)
class PluginDescriptor:
    plugin_id: str
    name: str
    vendor: str
    format: str
    version: str
    platform: str
    architecture: str
    cost_class: str
    roles: tuple[str, ...]
    schema: str = "PluginSemanticProfile/v1"

    def __post_init__(self) -> None:
        for field_name in (
            "plugin_id",
            "name",
            "vendor",
            "format",
            "version",
            "platform",
            "architecture",
            "cost_class",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"PLUGIN_DESCRIPTOR_FIELD_REQUIRED:{field_name}")


@dataclass(frozen=True)
class PluginQualification:
    plugin_id: str
    plugin_version: str
    status: str
    runtime_proven: bool
    reaper_discovered: bool
    instantiation_passed: bool
    save_reload_recall_passed: bool
    parameter_enumeration_passed: bool
    offline_render_passed: bool
    schema: str = "PluginQualification/v1"


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginDescriptor] = {}
        self._qualifications: dict[str, PluginQualification] = {}

    def register(self, descriptor: PluginDescriptor) -> None:
        self._plugins[descriptor.plugin_id] = descriptor

    def qualify(self, qualification: PluginQualification) -> None:
        descriptor = self._plugins.get(qualification.plugin_id)
        if descriptor is None:
            raise KeyError(f"PLUGIN_NOT_REGISTERED:{qualification.plugin_id}")
        if descriptor.version != qualification.plugin_version:
            raise ValueError("PLUGIN_QUALIFICATION_VERSION_MISMATCH")
        self._qualifications[qualification.plugin_id] = qualification

    def descriptor(self, plugin_id: str) -> PluginDescriptor:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise KeyError(f"PLUGIN_NOT_REGISTERED:{plugin_id}") from exc

    def qualification(self, plugin_id: str) -> PluginQualification | None:
        return self._qualifications.get(plugin_id)

    def production_eligible(self, plugin_id: str) -> bool:
        descriptor = self._plugins.get(plugin_id)
        qualification = self._qualifications.get(plugin_id)
        if descriptor is None or qualification is None:
            return False
        if qualification.plugin_version != descriptor.version:
            return False
        if descriptor.cost_class not in FREE_PRODUCTION_COST_CLASSES:
            return False
        if descriptor.platform.lower() != "linux":
            return False
        if descriptor.architecture.lower() not in {"x86_64", "amd64"}:
            return False
        if descriptor.format.upper() not in NATIVE_LINUX_FORMATS:
            return False
        return (
            qualification.status == "PRODUCTION_APPROVED"
            and qualification.runtime_proven
            and qualification.reaper_discovered
            and qualification.instantiation_passed
            and qualification.save_reload_recall_passed
            and qualification.parameter_enumeration_passed
            and qualification.offline_render_passed
        )


class ProducerDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REVISE = "REVISE"
    ROLLBACK = "ROLLBACK"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass(frozen=True)
class ProducerIteration:
    iteration: int
    mutation_fingerprint: str
    decision: ProducerDecision
    technical_pass: bool
    evidence_digest: str
    schema: str = "ProductionReview/v1"


class ProducerLoop:
    def __init__(self, *, max_iterations: int) -> None:
        if max_iterations < 1:
            raise ValueError("PRODUCER_ITERATION_BUDGET_INVALID")
        self.max_iterations = max_iterations
        self._history: list[ProducerIteration] = []

    @property
    def history(self) -> tuple[ProducerIteration, ...]:
        return tuple(self._history)

    def record(
        self,
        *,
        mutation_fingerprint: str,
        decision: ProducerDecision,
        technical_pass: bool,
        evidence_digest: str,
    ) -> ProducerIteration:
        if len(self._history) >= self.max_iterations:
            raise RuntimeError("PRODUCER_ITERATION_BUDGET_EXHAUSTED")
        if not mutation_fingerprint.strip() or not evidence_digest.strip():
            raise ValueError("PRODUCER_EVIDENCE_REQUIRED")

        if self._history:
            previous = self._history[-1]
            previous_failed = (
                not previous.technical_pass
                or previous.decision in {ProducerDecision.REVISE, ProducerDecision.ROLLBACK}
            )
            if (
                previous_failed
                and previous.mutation_fingerprint == mutation_fingerprint
                and previous.evidence_digest == evidence_digest
            ):
                raise RuntimeError("UNCHANGED_FAILED_MUTATION_RETRY_FORBIDDEN")

        item = ProducerIteration(
            iteration=len(self._history) + 1,
            mutation_fingerprint=mutation_fingerprint,
            decision=decision,
            technical_pass=technical_pass,
            evidence_digest=evidence_digest,
        )
        self._history.append(item)
        return item
