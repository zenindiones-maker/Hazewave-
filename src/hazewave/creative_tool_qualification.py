from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Final


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FREE_COST_CLASSES: Final[frozenset[str]] = frozenset(
    {"FREE_OPEN_SOURCE", "FREEWARE_NO_PAYMENT"}
)


class CreativeToolQualificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreativeToolDescriptor:
    tool_id: str
    name: str
    version: str
    source_url: str
    source_type: str
    license_id: str
    cost_class: str
    platform: str
    architecture: str
    packaging: str
    roles: tuple[str, ...]
    auto_install: bool = False
    schema: str = "CreativeToolDescriptor/v1"

    def __post_init__(self) -> None:
        for field_name in (
            "tool_id",
            "name",
            "version",
            "source_url",
            "source_type",
            "license_id",
            "cost_class",
            "platform",
            "architecture",
            "packaging",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise CreativeToolQualificationError(
                    f"CREATIVE_TOOL_FIELD_REQUIRED:{field_name}"
                )
        if not self.roles or any(not str(role or "").strip() for role in self.roles):
            raise CreativeToolQualificationError("CREATIVE_TOOL_ROLES_REQUIRED")
        if self.auto_install:
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_AUTO_INSTALL_FORBIDDEN"
            )

    @classmethod
    def krita_5_3_4(cls) -> "CreativeToolDescriptor":
        return cls(
            tool_id="krita",
            name="Krita",
            version="5.3.4",
            source_url="https://krita.org/en/download/",
            source_type="OFFICIAL_PROJECT_DOWNLOAD",
            license_id="GPL-3.0-or-later",
            cost_class="FREE_OPEN_SOURCE",
            platform="linux",
            architecture="x86_64",
            packaging="APPIMAGE",
            roles=(
                "concept-art",
                "background-painting",
                "character-sheets",
                "raster-frame-animation",
                "storyboard-assets",
                "texture-paint-assets",
            ),
            auto_install=False,
        )

    @classmethod
    def opentoonz_1_8_0(cls) -> "CreativeToolDescriptor":
        return cls(
            tool_id="opentoonz",
            name="OpenToonz",
            version="1.8.0",
            source_url=(
                "https://github.com/opentoonz/opentoonz/releases/tag/v1.8.0"
            ),
            source_type="OFFICIAL_PROJECT_RELEASE",
            license_id="BSD-3-Clause",
            cost_class="FREE_OPEN_SOURCE",
            platform="linux",
            architecture="x86_64",
            packaging="PROJECT_RELEASE",
            roles=(
                "xsheet",
                "traditional-animation",
                "vector-raster-levels",
                "scene-hierarchy",
                "compositing",
                "lip-sync-surface",
            ),
            auto_install=False,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["roles"] = list(self.roles)
        return value


@dataclass(frozen=True)
class CreativeToolSecurityReview:
    source_identity_verified: bool
    license_verified: bool
    release_metadata_verified: bool
    signature_or_digest_verified: bool
    no_authority_bypass: bool
    reviewer_identity: str
    evidence_digest: str
    schema: str = "CreativeToolSecurityReview/v1"

    def __post_init__(self) -> None:
        if not str(self.reviewer_identity or "").strip():
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_SECURITY_REVIEWER_REQUIRED"
            )
        if not _SHA256_RE.fullmatch(str(self.evidence_digest or "")):
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_SECURITY_EVIDENCE_DIGEST_INVALID"
            )

    @property
    def passed(self) -> bool:
        return all(
            (
                self.source_identity_verified,
                self.license_verified,
                self.release_metadata_verified,
                self.signature_or_digest_verified,
                self.no_authority_bypass,
            )
        )


@dataclass(frozen=True)
class CreativeToolRuntimeProof:
    runtime_identity: str
    executable_discovered: bool
    version_matches: bool
    project_open_save: bool
    headless_or_scripted_execution: bool
    artifact_creation: bool
    restart_recall: bool
    crash_free: bool
    evidence_digest: str
    schema: str = "CreativeToolRuntimeProof/v1"

    def __post_init__(self) -> None:
        if not str(self.runtime_identity or "").strip():
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_RUNTIME_IDENTITY_REQUIRED"
            )
        if not _SHA256_RE.fullmatch(str(self.evidence_digest or "")):
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_RUNTIME_EVIDENCE_DIGEST_INVALID"
            )

    @property
    def checks(self) -> dict[str, bool]:
        return {
            "executable_discovered": self.executable_discovered,
            "version_matches": self.version_matches,
            "project_open_save": self.project_open_save,
            "headless_or_scripted_execution": self.headless_or_scripted_execution,
            "artifact_creation": self.artifact_creation,
            "restart_recall": self.restart_recall,
            "crash_free": self.crash_free,
        }

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


@dataclass(frozen=True)
class CreativeToolQualification:
    tool_id: str
    tool_version: str
    status: str
    zero_cost_policy: str
    native_linux_policy: str
    security_review: str
    runtime_proven: bool
    production_approved: bool
    failed_runtime_checks: tuple[str, ...]
    security_evidence_digest: str
    runtime_evidence_digest: str | None
    auto_install: bool = False
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "CreativeToolQualification/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["failed_runtime_checks"] = list(self.failed_runtime_checks)
        return value


class CreativeToolQualificationLab:
    def __init__(self) -> None:
        self._descriptors: dict[str, CreativeToolDescriptor] = {}
        self._qualifications: dict[str, CreativeToolQualification] = {}

    def register(self, descriptor: CreativeToolDescriptor) -> None:
        current = self._descriptors.get(descriptor.tool_id)
        self._descriptors[descriptor.tool_id] = descriptor
        if current is not None and current.version != descriptor.version:
            self._qualifications.pop(descriptor.tool_id, None)

    def _descriptor(
        self,
        *,
        tool_id: str,
        tool_version: str,
    ) -> CreativeToolDescriptor:
        descriptor = self._descriptors.get(tool_id)
        if descriptor is None:
            raise CreativeToolQualificationError(
                f"CREATIVE_TOOL_NOT_REGISTERED:{tool_id}"
            )
        if descriptor.version != tool_version:
            raise CreativeToolQualificationError(
                "CREATIVE_TOOL_VERSION_MISMATCH"
            )
        return descriptor

    @staticmethod
    def _zero_cost(descriptor: CreativeToolDescriptor) -> bool:
        return descriptor.cost_class in FREE_COST_CLASSES

    @staticmethod
    def _native_linux(descriptor: CreativeToolDescriptor) -> bool:
        return (
            descriptor.platform.casefold() == "linux"
            and descriptor.architecture.casefold() in {"x86_64", "amd64"}
        )

    def evaluate_source(
        self,
        *,
        tool_id: str,
        tool_version: str,
        security_review: CreativeToolSecurityReview,
    ) -> CreativeToolQualification:
        descriptor = self._descriptor(
            tool_id=tool_id,
            tool_version=tool_version,
        )
        zero_cost = self._zero_cost(descriptor)
        native_linux = self._native_linux(descriptor)
        security_pass = security_review.passed

        if not zero_cost or not native_linux:
            status = "QUARANTINED"
        elif security_pass:
            status = "COMPATIBLE"
        else:
            status = "DISCOVERED"

        qualification = CreativeToolQualification(
            tool_id=descriptor.tool_id,
            tool_version=descriptor.version,
            status=status,
            zero_cost_policy="PASS" if zero_cost else "FAIL",
            native_linux_policy="PASS" if native_linux else "FAIL",
            security_review="PASS" if security_pass else "FAIL",
            runtime_proven=False,
            production_approved=False,
            failed_runtime_checks=(),
            security_evidence_digest=security_review.evidence_digest,
            runtime_evidence_digest=None,
            auto_install=False,
        )
        self._qualifications[descriptor.tool_id] = qualification
        return qualification

    def qualify_runtime(
        self,
        *,
        tool_id: str,
        tool_version: str,
        security_review: CreativeToolSecurityReview,
        runtime_proof: CreativeToolRuntimeProof,
    ) -> CreativeToolQualification:
        descriptor = self._descriptor(
            tool_id=tool_id,
            tool_version=tool_version,
        )
        zero_cost = self._zero_cost(descriptor)
        native_linux = self._native_linux(descriptor)
        security_pass = security_review.passed
        failed = tuple(
            name
            for name, passed in runtime_proof.checks.items()
            if not passed
        )
        runtime_proven = security_pass and not failed

        if not zero_cost or not native_linux:
            status = "QUARANTINED"
            approved = False
        elif runtime_proven:
            status = "PRODUCTION_APPROVED"
            approved = True
        else:
            status = "COMPATIBLE"
            approved = False

        qualification = CreativeToolQualification(
            tool_id=descriptor.tool_id,
            tool_version=descriptor.version,
            status=status,
            zero_cost_policy="PASS" if zero_cost else "FAIL",
            native_linux_policy="PASS" if native_linux else "FAIL",
            security_review="PASS" if security_pass else "FAIL",
            runtime_proven=runtime_proven,
            production_approved=approved,
            failed_runtime_checks=failed,
            security_evidence_digest=security_review.evidence_digest,
            runtime_evidence_digest=runtime_proof.evidence_digest,
            auto_install=False,
        )
        self._qualifications[descriptor.tool_id] = qualification
        return qualification

    def production_eligible(self, tool_id: str) -> bool:
        descriptor = self._descriptors.get(tool_id)
        qualification = self._qualifications.get(tool_id)
        if descriptor is None or qualification is None:
            return False
        return (
            qualification.production_approved
            and qualification.status == "PRODUCTION_APPROVED"
            and qualification.tool_version == descriptor.version
            and self._zero_cost(descriptor)
            and self._native_linux(descriptor)
            and not descriptor.auto_install
        )

    def snapshot(self) -> dict[str, Any]:
        tools: list[dict[str, Any]] = []
        for tool_id in sorted(self._descriptors):
            descriptor = self._descriptors[tool_id]
            qualification = self._qualifications.get(tool_id)
            tools.append(
                {
                    **descriptor.to_dict(),
                    "qualification": (
                        qualification.to_dict()
                        if qualification is not None
                        and qualification.tool_version == descriptor.version
                        else None
                    ),
                }
            )

        return {
            "schema": "CreativeToolRegistry/v1",
            "authority": "NONE",
            "grants_execution_authority": False,
            "automatic_installation": "FORBIDDEN",
            "tools": tools,
        }
