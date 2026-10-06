from __future__ import annotations

import pytest

from hazewave.harness import WAVE, classify_capability_domain
from hazewave.wave_professional_surface import (
    REQUIRED_WAVE_PRODUCTION_CAPABILITIES,
    WaveExecutionMode,
    capability_execution_plan,
    task_surface,
    tool_surface_metrics,
)


REQUIRED = {
    "media.inspect",
    "media.ingest",
    "image.inspect",
    "image.crop",
    "image.resize",
    "image.color",
    "image.retouch",
    "image.composite",
    "image.export",
    "image.qc",
    "illustration.create",
    "storyboard.create",
    "animation.plan",
    "animation.scene.inspect",
    "animation.fixture.create",
    "animation.shot.build",
    "animation.grease_pencil",
    "animation.rig",
    "animation.lipsync",
    "animation.composite",
    "animation.render.frames",
    "animation.render.frames.repair",
    "scene.detect",
    "timeline.create",
    "timeline.inspect",
    "timeline.cut",
    "timeline.trim",
    "timeline.move",
    "timeline.transition",
    "timeline.marker",
    "timeline.caption",
    "timeline.audio_sync",
    "visual.reframe",
    "visual.compose",
    "visual.color",
    "visual.qc",
    "delivery.encode",
    "web.architecture",
    "web.implement",
    "web.responsive",
    "web.accessibility",
    "web.performance",
    "web.visual_regression",
    "web.browser_compat",
    "web.preview",
}


def test_required_wave_professional_surface_is_complete_and_routed_to_wave() -> None:
    assert set(REQUIRED_WAVE_PRODUCTION_CAPABILITIES) == REQUIRED
    for capability in REQUIRED_WAVE_PRODUCTION_CAPABILITIES:
        assert classify_capability_domain(capability) == WAVE


def test_wave_surface_has_no_autonomous_publication_capability() -> None:
    assert all("publish" not in capability for capability in REQUIRED)
    with pytest.raises(KeyError, match="UNKNOWN_WAVE_PRODUCTION_CAPABILITY"):
        capability_execution_plan("web.publish")


def test_photo_surface_uses_qualified_raster_tooling_and_qc() -> None:
    surface = set(task_surface("photo"))

    assert {
        "image.inspect",
        "image.crop",
        "image.resize",
        "image.color",
        "image.retouch",
        "image.composite",
        "image.export",
        "image.qc",
    }.issubset(surface)

    retouch = capability_execution_plan("image.retouch")
    assert retouch.mode == WaveExecutionMode.KRITA_SCRIPTED
    assert retouch.required_tool_ids == ("krita",)
    assert retouch.requires_tool_qualification is True
    assert retouch.requires_runtime_proof is True


def test_cartoon_surface_combines_storyboard_2d_3d_and_render_quality() -> None:
    surface = set(task_surface("cartoon"))

    assert {
        "storyboard.create",
        "animation.plan",
        "animation.grease_pencil",
        "animation.rig",
        "animation.lipsync",
        "animation.composite",
        "animation.render.frames",
        "visual.qc",
    }.issubset(surface)

    grease = capability_execution_plan("animation.grease_pencil")
    assert grease.mode == WaveExecutionMode.BLENDER_SCRIPTED
    assert grease.required_tool_ids == ("blender",)
    assert grease.requires_runtime_proof is True

    lipsync = capability_execution_plan("animation.lipsync")
    assert lipsync.mode == WaveExecutionMode.WAVE_COMPOSITE
    assert set(lipsync.allowed_tool_ids) == {"blender", "opentoonz"}
    assert lipsync.requires_tool_qualification is True


def test_video_surface_uses_existing_editorial_and_qc_primitives() -> None:
    surface = set(task_surface("video"))

    assert {
        "media.inspect",
        "scene.detect",
        "timeline.create",
        "timeline.cut",
        "timeline.trim",
        "visual.color",
        "visual.qc",
        "delivery.encode",
    }.issubset(surface)

    cut = capability_execution_plan("timeline.cut")
    assert cut.mode == WaveExecutionMode.WAVE_EDITORIAL
    assert cut.local_operations == ("timeline.cut",)
    assert cut.requires_runtime_proof is True

    qc = capability_execution_plan("visual.qc")
    assert qc.mode == WaveExecutionMode.LOCAL_ANALYSIS
    assert "video_qc" in qc.evidence_engines
    assert qc.requires_runtime_proof is False


def test_website_surface_requires_accessibility_performance_and_visual_regression() -> None:
    surface = set(task_surface("website"))

    assert {
        "web.architecture",
        "web.implement",
        "web.responsive",
        "web.accessibility",
        "web.performance",
        "web.visual_regression",
        "web.browser_compat",
        "web.preview",
    } == surface

    accessibility = capability_execution_plan("web.accessibility")
    assert accessibility.mode == WaveExecutionMode.WEB_PIPELINE
    assert "wcag-2.2" in accessibility.evidence_engines
    assert accessibility.requires_runtime_proof is True

    performance = capability_execution_plan("web.performance")
    assert "lighthouse" in performance.evidence_engines

    regression = capability_execution_plan("web.visual_regression")
    assert "playwright" in regression.evidence_engines


def test_external_creative_tools_never_gain_harness_authority() -> None:
    for capability in (
        "image.retouch",
        "animation.grease_pencil",
        "animation.rig",
        "animation.lipsync",
        "web.implement",
    ):
        plan = capability_execution_plan(capability)
        assert plan.authority == "HAZEWAVE_HARNESS"
        assert plan.tool_authority == "NONE"


def test_task_surfaces_are_bounded_and_metrics_are_stable() -> None:
    full = set(REQUIRED_WAVE_PRODUCTION_CAPABILITIES)
    for mission in ("photo", "cartoon", "video", "website"):
        surface = task_surface(mission)
        assert set(surface) < full
        metrics = tool_surface_metrics(mission_kind=mission, capabilities=surface)
        assert metrics.capability_count == len(surface)
        assert metrics.utf8_bytes > 0
        assert len(metrics.sha256) == 64


def test_unknown_wave_capability_and_mission_fail_closed() -> None:
    with pytest.raises(KeyError, match="UNKNOWN_WAVE_PRODUCTION_CAPABILITY"):
        capability_execution_plan("visual.magic")
    with pytest.raises(KeyError, match="UNKNOWN_WAVE_MISSION_KIND"):
        task_surface("anything")
