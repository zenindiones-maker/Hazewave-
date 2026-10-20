from __future__ import annotations

import pytest

from hazewave.reaper_extensions import (
    ExtensionRuntimeProof,
    ExtensionSecurityReview,
    ReaperExtensionDescriptor,
    ReaperExtensionRegistry,
    ReaperExtensionRegistryError,
    ReaPackRepositoryCandidate,
)


def _review() -> ExtensionSecurityReview:
    return ExtensionSecurityReview(
        source_identity_verified=True,
        license_verified=True,
        release_digest_verified=True,
        repository_policy_reviewed=True,
        no_authority_bypass=True,
        reviewer_identity="hazewave-security-fixture",
        evidence_digest="a" * 64,
    )


def _runtime() -> ExtensionRuntimeProof:
    return ExtensionRuntimeProof(
        reaper_version="7.82",
        runtime_identity="codespace:fixture",
        reaper_discovered=True,
        extension_loaded=True,
        restart_recall=True,
        action_registration=True,
        crash_free=True,
        evidence_digest="b" * 64,
    )


def _descriptor(
    *,
    extension_id: str = "sws",
    version: str = "2.14.0.7",
    maintenance_status: str = "ACTIVE",
) -> ReaperExtensionDescriptor:
    return ReaperExtensionDescriptor(
        extension_id=extension_id,
        name="SWS/S&M Extension",
        version=version,
        source_repository="reaper-oss/sws",
        source_url="https://github.com/reaper-oss/sws/releases/tag/v2.14.0.7",
        license_id="MIT",
        platform="linux",
        architecture="x86_64",
        binary_sha256="4cf0629aeeff346c1ed9a355ce826febfacf9775bd6f49f09b1b4f9f053b8644",
        purpose=("snapshots", "resources", "actions"),
        maintenance_status=maintenance_status,
    )


def test_extension_registry_is_non_authoritative_and_version_bound() -> None:
    registry = ReaperExtensionRegistry()
    registry.register(_descriptor())

    receipt = registry.qualify(
        extension_id="sws",
        extension_version="2.14.0.7",
        security_review=_review(),
        runtime_proof=_runtime(),
    )

    snapshot = registry.snapshot()
    assert snapshot["schema"] == "ReaperExtensionRegistry/v1"
    assert snapshot["authority"] == "NONE"
    assert snapshot["grants_execution_authority"] is False
    assert receipt.schema == "ReaperExtensionQualification/v1"
    assert receipt.status == "PRODUCTION_APPROVED"
    assert receipt.runtime_proven is True
    assert receipt.reaper_version == "7.82"


def test_archived_extension_cannot_be_production_approved_by_runtime_proof_alone() -> None:
    registry = ReaperExtensionRegistry()
    registry.register(
        ReaperExtensionDescriptor(
            extension_id="reapack",
            name="ReaPack",
            version="1.2.6",
            source_repository="cfillion/reapack",
            source_url="https://github.com/cfillion/reapack/releases/tag/v1.2.6",
            license_id="LGPL-3.0-or-later",
            platform="linux",
            architecture="x86_64",
            binary_sha256="35d80f63d8174c964af589c7d87c4728aa18f06899dce873e33f8d552d1bc7e0",
            purpose=("package-management",),
            maintenance_status="ARCHIVED",
        )
    )

    receipt = registry.qualify(
        extension_id="reapack",
        extension_version="1.2.6",
        security_review=_review(),
        runtime_proof=_runtime(),
    )

    assert receipt.status == "QUARANTINED"
    assert receipt.production_approved is False
    assert receipt.maintenance_policy == "FAIL_ARCHIVED"


def test_extension_version_change_invalidates_prior_security_and_runtime_evidence() -> None:
    registry = ReaperExtensionRegistry()
    registry.register(_descriptor())
    registry.qualify(
        extension_id="sws",
        extension_version="2.14.0.7",
        security_review=_review(),
        runtime_proof=_runtime(),
    )

    registry.register(_descriptor(version="2.14.0.8"))

    item = registry.snapshot()["extensions"][0]
    assert item["version"] == "2.14.0.8"
    assert item["qualification"] is None
    assert registry.production_eligible("sws") is False


def test_extension_wrong_platform_never_becomes_production_eligible() -> None:
    registry = ReaperExtensionRegistry()
    registry.register(
        ReaperExtensionDescriptor(
            extension_id="fixture-win",
            name="Fixture",
            version="1.0",
            source_repository="fixture/repo",
            source_url="https://example.invalid/fixture",
            license_id="MIT",
            platform="windows",
            architecture="x86_64",
            binary_sha256="c" * 64,
            purpose=("test",),
            maintenance_status="ACTIVE",
        )
    )

    receipt = registry.qualify(
        extension_id="fixture-win",
        extension_version="1.0",
        security_review=_review(),
        runtime_proof=_runtime(),
    )

    assert receipt.status == "QUARANTINED"
    assert receipt.native_linux_policy == "FAIL"
    assert receipt.production_approved is False


def test_incomplete_security_review_cannot_be_runtime_proven() -> None:
    registry = ReaperExtensionRegistry()
    registry.register(_descriptor())
    review = ExtensionSecurityReview(
        source_identity_verified=True,
        license_verified=True,
        release_digest_verified=False,
        repository_policy_reviewed=True,
        no_authority_bypass=True,
        reviewer_identity="hazewave-security-fixture",
        evidence_digest="d" * 64,
    )

    receipt = registry.qualify(
        extension_id="sws",
        extension_version="2.14.0.7",
        security_review=review,
        runtime_proof=_runtime(),
    )

    assert receipt.status == "COMPATIBLE"
    assert receipt.security_review == "FAIL"
    assert receipt.runtime_proven is False
    assert receipt.production_approved is False


def test_reapack_repository_requires_explicit_security_and_human_admission() -> None:
    registry = ReaperExtensionRegistry()
    candidate = ReaPackRepositoryCandidate(
        repository_id="reatem-extensions",
        index_url="https://raw.githubusercontent.com/ReaTeam/Extensions/master/index.xml",
        source_repository="ReaTeam/Extensions",
        license_id="MULTIPLE_PACKAGE_LICENSES",
        pinned_revision="0123456789abcdef0123456789abcdef01234567",
        purpose=("curated-reaper-extensions",),
    )

    with pytest.raises(
        ReaperExtensionRegistryError,
        match="REAPACK_REPOSITORY_HUMAN_APPROVAL_REQUIRED",
    ):
        registry.admit_reapack_repository(
            candidate,
            security_review_pass=True,
            human_approved=False,
        )

    admitted = registry.admit_reapack_repository(
        candidate,
        security_review_pass=True,
        human_approved=True,
    )

    assert admitted.schema == "ReaPackRepositoryAdmission/v1"
    assert admitted.status == "ADMITTED"
    assert admitted.auto_install is False
    assert admitted.grants_execution_authority is False


def test_reapack_repository_never_accepts_unpinned_revision() -> None:
    registry = ReaperExtensionRegistry()
    candidate = ReaPackRepositoryCandidate(
        repository_id="unsafe",
        index_url="https://example.invalid/index.xml",
        source_repository="example/repo",
        license_id="MIT",
        pinned_revision="main",
        purpose=("fixture",),
    )

    with pytest.raises(
        ReaperExtensionRegistryError,
        match="REAPACK_REPOSITORY_REVISION_NOT_PINNED",
    ):
        registry.admit_reapack_repository(
            candidate,
            security_review_pass=True,
            human_approved=True,
        )
