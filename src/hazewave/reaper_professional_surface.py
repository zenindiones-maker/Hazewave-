from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Final, Iterable


REQUIRED_HAZE_PRODUCTION_CAPABILITIES: Final[tuple[str, ...]] = (
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
)

DIRECT_REAPER_CAPABILITIES: Final[tuple[str, ...]] = (
    "session.inspect",
    "session.checkpoint",
    "arrangement.marker",
    "arrangement.region",
    "audio.import",
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
    "fx.inventory",
    "fx.add",
    "fx.remove",
    "fx.bypass",
    "fx.preset",
    "fx.parameter.read",
    "fx.parameter.write",
    "fx.automation",
    "render.preview",
    "render.stems",
    "render.master",
)

INTERNAL_REAPER_OPERATIONS: Final[tuple[str, ...]] = (
    "session.rollback",
    "session.fixture.open",
    "session.fixture.close",
)

LOCAL_ANALYSIS_CAPABILITIES: Final[tuple[str, ...]] = (
    "audio.analyze",
    "audio.compare",
    "audio.qc",
)

PRODUCER_COMPOSITE_CAPABILITIES: Final[tuple[str, ...]] = (
    "arrangement.structure",
    "audio.edit",
    "routing.sidechain",
    "routing.parallel",
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
)


@dataclass(frozen=True)
class CapabilityExecutionPlan:
    capability: str
    mode: str
    reaper_operations: tuple[str, ...] = ()
    local_operations: tuple[str, ...] = ()
    requires_snapshot: bool = True
    requires_plugin_selection: bool = False
    requires_typed_suboperation: bool = False
    allowed_suboperations: tuple[str, ...] = ()
    schema: str = "CapabilityExecutionPlan/v1"


@dataclass(frozen=True)
class ToolSurfaceMetrics:
    mission_kind: str
    capability_count: int
    utf8_bytes: int
    sha256: str
    schema: str = "ToolSurfaceMetrics/v1"


_COMPOSITE_PLANS: Final[dict[str, CapabilityExecutionPlan]] = {
    "arrangement.structure": CapabilityExecutionPlan(
        capability="arrangement.structure",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("session.inspect",),
    ),
    "audio.edit": CapabilityExecutionPlan(
        capability="audio.edit",
        mode="PRODUCER_COMPOSITE",
        requires_typed_suboperation=True,
        allowed_suboperations=(
            "audio.split",
            "audio.trim",
            "audio.fade",
            "audio.align",
            "audio.time_stretch",
            "audio.pitch",
        ),
    ),
    "routing.sidechain": CapabilityExecutionPlan(
        capability="routing.sidechain",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("track.configure", "routing.send"),
    ),
    "routing.parallel": CapabilityExecutionPlan(
        capability="routing.parallel",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("routing.bus", "routing.send"),
    ),
    "mix.gainstage": CapabilityExecutionPlan(
        capability="mix.gainstage",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("session.inspect", "track.configure", "render.preview"),
        local_operations=("audio.analyze",),
    ),
    "mix.balance": CapabilityExecutionPlan(
        capability="mix.balance",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("session.inspect", "track.configure", "render.preview"),
        local_operations=("audio.analyze",),
    ),
    "mix.eq": CapabilityExecutionPlan(
        capability="mix.eq",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("fx.inventory", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
        requires_plugin_selection=True,
    ),
    "mix.dynamics": CapabilityExecutionPlan(
        capability="mix.dynamics",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("fx.inventory", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
        requires_plugin_selection=True,
    ),
    "mix.saturation": CapabilityExecutionPlan(
        capability="mix.saturation",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("fx.inventory", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
        requires_plugin_selection=True,
    ),
    "mix.spatial": CapabilityExecutionPlan(
        capability="mix.spatial",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("track.configure", "fx.inventory", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
    ),
    "mix.delay": CapabilityExecutionPlan(
        capability="mix.delay",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("routing.bus", "routing.send", "fx.add", "fx.parameter.write", "fx.automation", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
        requires_plugin_selection=True,
    ),
    "mix.reverb": CapabilityExecutionPlan(
        capability="mix.reverb",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("routing.bus", "routing.send", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare"),
        requires_plugin_selection=True,
    ),
    "mix.automation": CapabilityExecutionPlan(
        capability="mix.automation",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("fx.automation", "render.preview"),
        local_operations=("audio.analyze",),
    ),
    "master.prepare": CapabilityExecutionPlan(
        capability="master.prepare",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("session.inspect", "render.preview"),
        local_operations=("audio.analyze", "audio.compare", "audio.qc"),
    ),
    "master.process": CapabilityExecutionPlan(
        capability="master.process",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("fx.inventory", "fx.add", "fx.parameter.write", "render.preview"),
        local_operations=("audio.analyze", "audio.compare", "audio.qc"),
        requires_plugin_selection=True,
    ),
    "master.render": CapabilityExecutionPlan(
        capability="master.render",
        mode="PRODUCER_COMPOSITE",
        reaper_operations=("render.master",),
    ),
}

_TASK_SURFACES: Final[dict[str, tuple[str, ...]]] = {
    "mix": (
        "session.inspect",
        "session.checkpoint",
        "track.configure",
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
        "render.preview",
        "audio.analyze",
        "audio.compare",
        "audio.qc",
    ),
    "master": (
        "session.inspect",
        "session.checkpoint",
        "fx.inventory",
        "fx.add",
        "fx.remove",
        "fx.bypass",
        "fx.preset",
        "fx.parameter.read",
        "fx.parameter.write",
        "fx.automation",
        "master.prepare",
        "master.process",
        "master.render",
        "render.preview",
        "render.master",
        "audio.analyze",
        "audio.compare",
        "audio.qc",
    ),
    "audio-edit": (
        "session.inspect",
        "session.checkpoint",
        "audio.import",
        "audio.edit",
        "audio.split",
        "audio.trim",
        "audio.fade",
        "audio.align",
        "audio.time_stretch",
        "audio.pitch",
        "render.preview",
        "audio.analyze",
        "audio.qc",
    ),
}


def capability_execution_plan(capability: str) -> CapabilityExecutionPlan:
    value = str(capability or "").strip()
    if value in DIRECT_REAPER_CAPABILITIES:
        return CapabilityExecutionPlan(
            capability=value,
            mode="REAPER_DIRECT",
            reaper_operations=(value,),
        )
    if value in LOCAL_ANALYSIS_CAPABILITIES:
        return CapabilityExecutionPlan(
            capability=value,
            mode="LOCAL_ANALYSIS",
            requires_snapshot=False,
        )
    try:
        return _COMPOSITE_PLANS[value]
    except KeyError as exc:
        raise KeyError(f"UNKNOWN_HAZE_PRODUCTION_CAPABILITY:{value}") from exc


def task_surface(mission_kind: str) -> tuple[str, ...]:
    key = str(mission_kind or "").strip().casefold()
    try:
        return _TASK_SURFACES[key]
    except KeyError as exc:
        raise KeyError(f"UNKNOWN_HAZE_MISSION_KIND:{mission_kind}") from exc


def tool_surface_metrics(
    *,
    mission_kind: str,
    capabilities: Iterable[str],
) -> ToolSurfaceMetrics:
    materialized = tuple(str(item) for item in capabilities)
    payload = json.dumps(
        {
            "mission_kind": str(mission_kind),
            "capabilities": list(materialized),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return ToolSurfaceMetrics(
        mission_kind=str(mission_kind),
        capability_count=len(materialized),
        utf8_bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )
