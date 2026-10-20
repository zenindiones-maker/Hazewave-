from __future__ import annotations

import re
from pathlib import Path

from hazewave.reaper_bridge import REAPER_OPERATION_ALLOWLIST
from hazewave.reaper_professional_surface import (
    DIRECT_REAPER_CAPABILITIES,
    INTERNAL_REAPER_OPERATIONS,
    LOCAL_ANALYSIS_CAPABILITIES,
    PRODUCER_COMPOSITE_CAPABILITIES,
    REQUIRED_HAZE_PRODUCTION_CAPABILITIES,
    capability_execution_plan,
    task_surface,
    tool_surface_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
LUA_BRIDGE = ROOT / "scripts" / "reaper" / "hazewave_reaper_bridge.lua"


REQUIRED = {
    "session.inspect",
    "session.checkpoint",
    "arrangement.structure",
    "arrangement.marker",
    "arrangement.region",
    "audio.import",
    "audio.edit",
    "audio.split",
    "audio.trim",
    "audio.fade",
    "audio.align",
    "audio.time_stretch",
    "audio.pitch",
    "track.create",
    "track.configure",
    "track.folder",
    "routing.bus",
    "routing.send",
    "routing.sidechain",
    "routing.parallel",
    "fx.inventory",
    "fx.add",
    "fx.remove",
    "fx.bypass",
    "fx.preset",
    "fx.parameter.read",
    "fx.parameter.write",
    "fx.automation",
    "mix.gainstage",
    "mix.balance",
    "mix.eq",
    "mix.dynamics",
    "mix.saturation",
    "mix.spatial",
    "mix.delay",
    "mix.reverb",
    "mix.automation",
    "master.prepare",
    "master.process",
    "master.render",
    "render.preview",
    "render.stems",
    "render.master",
    "audio.analyze",
    "audio.compare",
    "audio.qc",
}


def test_required_haze_professional_surface_is_complete_and_disjoint() -> None:
    assert set(REQUIRED_HAZE_PRODUCTION_CAPABILITIES) == REQUIRED

    direct = set(DIRECT_REAPER_CAPABILITIES)
    composite = set(PRODUCER_COMPOSITE_CAPABILITIES)
    local = set(LOCAL_ANALYSIS_CAPABILITIES)

    assert direct | composite | local == REQUIRED
    assert direct.isdisjoint(composite)
    assert direct.isdisjoint(local)
    assert composite.isdisjoint(local)


def test_direct_reaper_allowlist_has_exact_lua_handler_coverage() -> None:
    text = LUA_BRIDGE.read_text(encoding="utf-8")
    handlers = set(re.findall(r'handlers\["([^"]+)"\]\s*=', text))

    expected = set(DIRECT_REAPER_CAPABILITIES) | set(INTERNAL_REAPER_OPERATIONS)

    assert set(REAPER_OPERATION_ALLOWLIST) == expected
    assert handlers == expected


def test_local_analysis_never_crosses_into_reaper_ipc() -> None:
    assert set(LOCAL_ANALYSIS_CAPABILITIES) == {
        "audio.analyze",
        "audio.compare",
        "audio.qc",
    }
    for capability in LOCAL_ANALYSIS_CAPABILITIES:
        plan = capability_execution_plan(capability)
        assert plan.mode == "LOCAL_ANALYSIS"
        assert plan.reaper_operations == ()
        assert capability not in REAPER_OPERATION_ALLOWLIST


def test_composite_mix_capabilities_resolve_to_bounded_primitives() -> None:
    eq = capability_execution_plan("mix.eq")
    delay = capability_execution_plan("mix.delay")
    parallel = capability_execution_plan("routing.parallel")
    sidechain = capability_execution_plan("routing.sidechain")

    assert eq.mode == "PRODUCER_COMPOSITE"
    assert eq.requires_plugin_selection is True
    assert set(eq.reaper_operations).issubset(REAPER_OPERATION_ALLOWLIST)
    assert {"fx.inventory", "fx.add", "fx.parameter.write"}.issubset(
        eq.reaper_operations
    )

    assert delay.requires_plugin_selection is True
    assert {"routing.bus", "routing.send", "fx.add", "fx.parameter.write"}.issubset(
        delay.reaper_operations
    )

    assert parallel.reaper_operations == (
        "routing.bus",
        "routing.send",
    )
    assert sidechain.reaper_operations == (
        "track.configure",
        "routing.send",
    )


def test_master_render_is_composite_alias_to_bounded_render_master() -> None:
    plan = capability_execution_plan("master.render")

    assert plan.mode == "PRODUCER_COMPOSITE"
    assert plan.reaper_operations == ("render.master",)
    assert plan.requires_snapshot is True


def test_audio_edit_is_not_an_unrestricted_generic_reaper_command() -> None:
    plan = capability_execution_plan("audio.edit")

    assert plan.mode == "PRODUCER_COMPOSITE"
    assert plan.requires_typed_suboperation is True
    assert "audio.edit" not in REAPER_OPERATION_ALLOWLIST
    assert set(plan.allowed_suboperations) == {
        "audio.split",
        "audio.trim",
        "audio.fade",
        "audio.align",
        "audio.time_stretch",
        "audio.pitch",
    }


def test_task_surfaces_are_bounded_and_domain_specific() -> None:
    mix = set(task_surface("mix"))
    master = set(task_surface("master"))
    edit = set(task_surface("audio-edit"))

    assert mix
    assert master
    assert edit
    assert mix < REQUIRED
    assert master < REQUIRED
    assert edit < REQUIRED

    assert "mix.eq" in mix
    assert "mix.delay" in mix
    assert "master.render" not in mix
    assert "master.render" in master
    assert "audio.split" in edit
    assert "audio.pitch" in edit
    assert "mix.delay" not in edit


def test_tool_surface_metrics_measure_schema_overhead() -> None:
    surface = task_surface("mix")
    metrics = tool_surface_metrics(
        mission_kind="mix",
        capabilities=surface,
    )

    assert metrics.schema == "ToolSurfaceMetrics/v1"
    assert metrics.mission_kind == "mix"
    assert metrics.capability_count == len(surface)
    assert metrics.capability_count < len(REQUIRED)
    assert metrics.utf8_bytes > 0
    assert metrics.sha256
    assert len(metrics.sha256) == 64
