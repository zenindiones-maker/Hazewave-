from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Final


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAINTENANCE_STATUSES: Final[frozenset[str]] = frozenset(
    {"ACTIVE", "ARCHIVED", "UNKNOWN"}
)


class ReaperExtensionRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReaperExtensionDescriptor:
    extension_id: str
    name: str
    version: str
    source_repository: str
    source_url: str
    license_id: str
    platform: str
    architecture: str
    binary_sha256: str
    purpose: tuple[str, ...]
    maintenance_status: str
    schema: str = "ReaperExtensionDescriptor/v1"

    def __post_init__(self) -> None:
        for field_name in (
            "extension_id",
            "name",
            "version",
            "source_repository",
            "source_url",
            "license_id",
            "platform",
            "architecture",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ReaperExtensionRegistryError(
                    f"REAPER_EXTENSION_FIELD_REQUIRED:{field_name}"
                )
        if not _SHA256_RE.fullmatch(self.binary_sha256):
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_BINARY_SHA256_INVALID"
            )
        if not self.purpose or not all(str(item).strip() for item in self.purpose):
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_PURPOSE_REQUIRED"
            )
        if self.maintenance_status not in MAINTENANCE_STATUSES:
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_MAINTENANCE_STATUS_INVALID"
            )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["purpose"] = list(self.purpose)
        return value


@dataclass(frozen=True)
class ExtensionSecurityReview:
    source_identity_verified: bool
    license_verified: bool
    release_digest_verified: bool
    repository_policy_reviewed: bool
    no_authority_bypass: bool
    reviewer_identity: str
    evidence_digest: str
    schema: str = "ReaperExtensionSecurityReview/v1"

    def __post_init__(self) -> None:
        if not self.reviewer_identity.strip():
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_SECURITY_REVIEWER_REQUIRED"
            )
        if not _SHA256_RE.fullmatch(self.evidence_digest):
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_SECURITY_EVIDENCE_DIGEST_INVALID"
            )

    @property
    def passed(self) -> bool:
        return all(
            (
                self.source_identity_verified,
                self.license_verified,
                self.release_digest_verified,
                self.repository_policy_reviewed,
                self.no_authority_bypass,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtensionRuntimeProof:
    reaper_version: str
    runtime_identity: str
    reaper_discovered: bool
    extension_loaded: bool
    restart_recall: bool
    action_registration: bool
    crash_free: bool
    evidence_digest: str
    schema: str = "ReaperExtensionRuntimeProof/v1"

    def __post_init__(self) -> None:
        if not self.reaper_version.strip() or not self.runtime_identity.strip():
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_RUNTIME_IDENTITY_REQUIRED"
            )
        if not _SHA256_RE.fullmatch(self.evidence_digest):
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_RUNTIME_EVIDENCE_DIGEST_INVALID"
            )

    @property
    def passed(self) -> bool:
        return all(
            (
                self.reaper_discovered,
                self.extension_loaded,
                self.restart_recall,
                self.action_registration,
                self.crash_free,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReaperExtensionQualification:
    extension_id: str
    extension_version: str
    status: str
    reaper_version: str
    runtime_identity: str
    security_review: str
    runtime_proven: bool
    production_approved: bool
    native_linux_policy: str
    maintenance_policy: str
    security_evidence_digest: str
    runtime_evidence_digest: str
    schema: str = "ReaperExtensionQualification/v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReaPackRepositoryCandidate:
    repository_id: str
    index_url: str
    source_repository: str
    license_id: str
    pinned_revision: str
    purpose: tuple[str, ...]
    schema: str = "ReaPackRepositoryCandidate/v1"

    def __post_init__(self) -> None:
        for field_name in (
            "repository_id",
            "index_url",
            "source_repository",
            "license_id",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ReaperExtensionRegistryError(
                    f"REAPACK_REPOSITORY_FIELD_REQUIRED:{field_name}"
                )
        if not self.purpose:
            raise ReaperExtensionRegistryError(
                "REAPACK_REPOSITORY_PURPOSE_REQUIRED"
            )


@dataclass(frozen=True)
class ReaPackRepositoryAdmission:
    repository_id: str
    index_url: str
    source_repository: str
    pinned_revision: str
    purpose: tuple[str, ...]
    status: str = "ADMITTED"
    auto_install: bool = False
    grants_execution_authority: bool = False
    schema: str = "ReaPackRepositoryAdmission/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["purpose"] = list(self.purpose)
        return value


class ReaperExtensionRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, ReaperExtensionDescriptor] = {}
        self._qualifications: dict[str, ReaperExtensionQualification] = {}
        self._reapack_repositories: dict[str, ReaPackRepositoryAdmission] = {}

    @staticmethod
    def _native_linux(descriptor: ReaperExtensionDescriptor) -> bool:
        return (
            descriptor.platform.casefold() == "linux"
            and descriptor.architecture.casefold() in {"x86_64", "amd64"}
        )

    def register(self, descriptor: ReaperExtensionDescriptor) -> None:
        previous = self._descriptors.get(descriptor.extension_id)
        self._descriptors[descriptor.extension_id] = descriptor
        if previous is not None and previous.version != descriptor.version:
            self._qualifications.pop(descriptor.extension_id, None)

    def qualify(
        self,
        *,
        extension_id: str,
        extension_version: str,
        security_review: ExtensionSecurityReview,
        runtime_proof: ExtensionRuntimeProof,
    ) -> ReaperExtensionQualification:
        descriptor = self._descriptors.get(extension_id)
        if descriptor is None:
            raise ReaperExtensionRegistryError(
                f"REAPER_EXTENSION_NOT_REGISTERED:{extension_id}"
            )
        if descriptor.version != extension_version:
            raise ReaperExtensionRegistryError(
                "REAPER_EXTENSION_VERSION_MISMATCH"
            )

        security_pass = security_review.passed
        native_pass = self._native_linux(descriptor)
        maintenance_pass = descriptor.maintenance_status == "ACTIVE"
        runtime_pass = security_pass and runtime_proof.passed

        if not native_pass or descriptor.maintenance_status == "ARCHIVED":
            status = "QUARANTINED"
            approved = False
        elif runtime_pass and maintenance_pass:
            status = "PRODUCTION_APPROVED"
            approved = True
        elif security_pass and runtime_proof.passed:
            status = "RUNTIME_PROVEN"
            approved = False
        else:
            status = "COMPATIBLE"
            approved = False

        qualification = ReaperExtensionQualification(
            extension_id=extension_id,
            extension_version=extension_version,
            status=status,
            reaper_version=runtime_proof.reaper_version,
            runtime_identity=runtime_proof.runtime_identity,
            security_review="PASS" if security_pass else "FAIL",
            runtime_proven=runtime_pass,
            production_approved=approved,
            native_linux_policy="PASS" if native_pass else "FAIL",
            maintenance_policy=(
                "PASS"
                if maintenance_pass
                else (
                    "FAIL_ARCHIVED"
                    if descriptor.maintenance_status == "ARCHIVED"
                    else "FAIL_UNKNOWN"
                )
            ),
            security_evidence_digest=security_review.evidence_digest,
            runtime_evidence_digest=runtime_proof.evidence_digest,
        )
        self._qualifications[extension_id] = qualification
        return qualification

    def production_eligible(self, extension_id: str) -> bool:
        descriptor = self._descriptors.get(extension_id)
        qualification = self._qualifications.get(extension_id)
        if descriptor is None or qualification is None:
            return False
        return (
            qualification.production_approved
            and qualification.status == "PRODUCTION_APPROVED"
            and qualification.extension_version == descriptor.version
            and descriptor.maintenance_status == "ACTIVE"
            and self._native_linux(descriptor)
        )

    def admit_reapack_repository(
        self,
        candidate: ReaPackRepositoryCandidate,
        *,
        security_review_pass: bool,
        human_approved: bool,
    ) -> ReaPackRepositoryAdmission:
        if not _GIT_SHA_RE.fullmatch(candidate.pinned_revision):
            raise ReaperExtensionRegistryError(
                "REAPACK_REPOSITORY_REVISION_NOT_PINNED"
            )
        if not security_review_pass:
            raise ReaperExtensionRegistryError(
                "REAPACK_REPOSITORY_SECURITY_REVIEW_REQUIRED"
            )
        if not human_approved:
            raise ReaperExtensionRegistryError(
                "REAPACK_REPOSITORY_HUMAN_APPROVAL_REQUIRED"
            )

        admission = ReaPackRepositoryAdmission(
            repository_id=candidate.repository_id,
            index_url=candidate.index_url,
            source_repository=candidate.source_repository,
            pinned_revision=candidate.pinned_revision,
            purpose=candidate.purpose,
        )
        self._reapack_repositories[candidate.repository_id] = admission
        return admission

    def snapshot(self) -> dict[str, Any]:
        extensions: list[dict[str, Any]] = []
        for extension_id in sorted(self._descriptors):
            descriptor = self._descriptors[extension_id]
            qualification = self._qualifications.get(extension_id)
            extensions.append(
                {
                    **descriptor.to_dict(),
                    "qualification": (
                        qualification.to_dict()
                        if qualification is not None
                        and qualification.extension_version == descriptor.version
                        else None
                    ),
                }
            )

        repositories = [
            self._reapack_repositories[key].to_dict()
            for key in sorted(self._reapack_repositories)
        ]
        return {
            "schema": "ReaperExtensionRegistry/v1",
            "authority": "NONE",
            "grants_execution_authority": False,
            "automatic_reapack_repository_install": "FORBIDDEN",
            "extensions": extensions,
            "reapack_repositories": repositories,
        }
