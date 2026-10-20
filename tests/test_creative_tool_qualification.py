from __future__ import annotations

import pytest

from hazewave.creative_tool_qualification import (
    CreativeToolDescriptor,
    CreativeToolQualificationLab,
    CreativeToolRuntimeProof,
    CreativeToolSecurityReview,
    CreativeToolQualificationError,
)


def _security() -> CreativeToolSecurityReview:
    return CreativeToolSecurityReview(
        source_identity_verified=True,
        license_verified=True,
        release_metadata_verified=True,
        signature_or_digest_verified=True,
        no_authority_bypass=True,
        reviewer_identity="hazewave-security-fixture",
        evidence_digest="a" * 64,
    )


def _runtime() -> CreativeToolRuntimeProof:
    return CreativeToolRuntimeProof(
        runtime_identity="codespace:fixture",
        executable_discovered=True,
        version_matches=True,
        project_open_save=True,
        headless_or_scripted_execution=True,
        artifact_creation=True,
        restart_recall=True,
        crash_free=True,
        evidence_digest="b" * 64,
    )


def test_opentoonz_source_verified_evaluation_is_not_runtime_proof() -> None:
    lab = CreativeToolQualificationLab()
    descriptor = CreativeToolDescriptor(
        tool_id="opentoonz",
        name="OpenToonz",
        version="1.8.0",
        source_url="https://github.com/opentoonz/opentoonz/releases/tag/v1.8.0",
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
    lab.register(descriptor)

    evaluation = lab.evaluate_source(
        tool_id="opentoonz",
        tool_version="1.8.0",
        security_review=_security(),
    )

    assert evaluation.schema == "CreativeToolQualification/v1"
    assert evaluation.status == "COMPATIBLE"
    assert evaluation.runtime_proven is False
    assert evaluation.production_approved is False
    assert evaluation.auto_install is False
    assert evaluation.grants_execution_authority is False


def test_krita_primary_stable_baseline_is_534_linux_appimage() -> None:
    descriptor = CreativeToolDescriptor.krita_5_3_4()

    assert descriptor.tool_id == "krita"
    assert descriptor.version == "5.3.4"
    assert descriptor.platform == "linux"
    assert descriptor.architecture == "x86_64"
    assert descriptor.packaging == "APPIMAGE"
    assert descriptor.cost_class == "FREE_OPEN_SOURCE"
    assert descriptor.auto_install is False
    assert "concept-art" in descriptor.roles
    assert "background-painting" in descriptor.roles
    assert "raster-frame-animation" in descriptor.roles
    assert "storyboard-assets" in descriptor.roles


def test_runtime_proof_can_promote_source_reviewed_tool_without_granting_authority() -> None:
    lab = CreativeToolQualificationLab()
    lab.register(CreativeToolDescriptor.krita_5_3_4())

    source = lab.evaluate_source(
        tool_id="krita",
        tool_version="5.3.4",
        security_review=_security(),
    )
    assert source.status == "COMPATIBLE"

    runtime = lab.qualify_runtime(
        tool_id="krita",
        tool_version="5.3.4",
        security_review=_security(),
        runtime_proof=_runtime(),
    )

    assert runtime.status == "PRODUCTION_APPROVED"
    assert runtime.runtime_proven is True
    assert runtime.production_approved is True
    assert runtime.grants_execution_authority is False
    assert runtime.authority == "NONE"


def test_runtime_proof_fails_closed_when_scripted_execution_is_missing() -> None:
    lab = CreativeToolQualificationLab()
    lab.register(CreativeToolDescriptor.krita_5_3_4())
    proof = CreativeToolRuntimeProof(
        runtime_identity="codespace:fixture",
        executable_discovered=True,
        version_matches=True,
        project_open_save=True,
        headless_or_scripted_execution=False,
        artifact_creation=True,
        restart_recall=True,
        crash_free=True,
        evidence_digest="c" * 64,
    )

    result = lab.qualify_runtime(
        tool_id="krita",
        tool_version="5.3.4",
        security_review=_security(),
        runtime_proof=proof,
    )

    assert result.status == "COMPATIBLE"
    assert result.runtime_proven is False
    assert result.production_approved is False
    assert "headless_or_scripted_execution" in result.failed_runtime_checks


def test_paid_unknown_or_non_native_tool_is_quarantined() -> None:
    lab = CreativeToolQualificationLab()
    lab.register(
        CreativeToolDescriptor(
            tool_id="unsafe",
            name="Unsafe",
            version="1.0",
            source_url="https://example.invalid/unsafe",
            source_type="UNKNOWN",
            license_id="UNKNOWN",
            cost_class="UNKNOWN_COST",
            platform="windows",
            architecture="x86_64",
            packaging="EXE",
            roles=("fixture",),
            auto_install=False,
        )
    )

    result = lab.evaluate_source(
        tool_id="unsafe",
        tool_version="1.0",
        security_review=_security(),
    )

    assert result.status == "QUARANTINED"
    assert result.zero_cost_policy == "FAIL"
    assert result.native_linux_policy == "FAIL"
    assert result.production_approved is False


def test_tool_version_change_invalidates_qualification() -> None:
    lab = CreativeToolQualificationLab()
    lab.register(CreativeToolDescriptor.krita_5_3_4())
    lab.qualify_runtime(
        tool_id="krita",
        tool_version="5.3.4",
        security_review=_security(),
        runtime_proof=_runtime(),
    )
    lab.register(
        CreativeToolDescriptor(
            **{
                **CreativeToolDescriptor.krita_5_3_4().__dict__,
                "version": "5.3.5",
                "schema": "CreativeToolDescriptor/v1",
            }
        )
    )

    snapshot = lab.snapshot()
    assert snapshot["schema"] == "CreativeToolRegistry/v1"
    assert snapshot["tools"][0]["version"] == "5.3.5"
    assert snapshot["tools"][0]["qualification"] is None


def test_auto_install_is_forbidden_for_secondary_creative_tools() -> None:
    with pytest.raises(
        CreativeToolQualificationError,
        match="CREATIVE_TOOL_AUTO_INSTALL_FORBIDDEN",
    ):
        CreativeToolDescriptor(
            tool_id="opentoonz",
            name="OpenToonz",
            version="1.8.0",
            source_url="https://github.com/opentoonz/opentoonz/releases/tag/v1.8.0",
            source_type="OFFICIAL_PROJECT_RELEASE",
            license_id="BSD-3-Clause",
            cost_class="FREE_OPEN_SOURCE",
            platform="linux",
            architecture="x86_64",
            packaging="PROJECT_RELEASE",
            roles=("xsheet",),
            auto_install=True,
        )
