from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Final, Iterable


class WaveExecutionMode(str, Enum):
    LOCAL_ANALYSIS = "LOCAL_ANALYSIS"
    WAVE_EDITORIAL = "WAVE_EDITORIAL"
    BLENDER_SCRIPTED = "BLENDER_SCRIPTED"
    KRITA_SCRIPTED = "KRITA_SCRIPTED"
    OPENTOONZ_SCRIPTED = "OPENTOONZ_SCRIPTED"
    WEB_PIPELINE = "WEB_PIPELINE"
    WAVE_COMPOSITE = "WAVE_COMPOSITE"


@dataclass(frozen=True)
class WaveCapabilityExecutionPlan:
    capability: str
    mode: WaveExecutionMode
    local_operations: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    evidence_engines: tuple[str, ...] = ()
    requires_checkpoint: bool = True
    requires_tool_qualification: bool = False
    requires_runtime_proof: bool = False
    authority: str = "HAZEWAVE_HARNESS"
    tool_authority: str = "NONE"
    schema: str = "WaveCapabilityExecutionPlan/v1"


@dataclass(frozen=True)
class WaveToolSurfaceMetrics:
    mission_kind: str
    capability_count: int
    utf8_bytes: int
    sha256: str
    schema: str = "WaveToolSurfaceMetrics/v1"


REQUIRED_WAVE_PRODUCTION_CAPABILITIES: Final[tuple[str, ...]] = (
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
)


def _local(
    capability: str,
    *,
    evidence: tuple[str, ...] = (),
) -> WaveCapabilityExecutionPlan:
    return WaveCapabilityExecutionPlan(
        capability=capability,
        mode=WaveExecutionMode.LOCAL_ANALYSIS,
        local_operations=(capability,),
        evidence_engines=evidence,
        requires_checkpoint=False,
    )


def _editorial(
    capability: str,
    *,
    evidence: tuple[str, ...] = (),
) -> WaveCapabilityExecutionPlan:
    return WaveCapabilityExecutionPlan(
        capability=capability,
        mode=WaveExecutionMode.WAVE_EDITORIAL,
        local_operations=(capability,),
        evidence_engines=evidence,
        requires_runtime_proof=True,
    )


def _tool(
    capability: str,
    *,
    mode: WaveExecutionMode,
    tool_id: str,
    evidence: tuple[str, ...] = (),
) -> WaveCapabilityExecutionPlan:
    return WaveCapabilityExecutionPlan(
        capability=capability,
        mode=mode,
        required_tool_ids=(tool_id,),
        allowed_tool_ids=(tool_id,),
        evidence_engines=evidence,
        requires_tool_qualification=True,
        requires_runtime_proof=True,
    )


def _web(
    capability: str,
    *,
    evidence: tuple[str, ...] = (),
) -> WaveCapabilityExecutionPlan:
    return WaveCapabilityExecutionPlan(
        capability=capability,
        mode=WaveExecutionMode.WEB_PIPELINE,
        local_operations=(capability,),
        evidence_engines=evidence,
        requires_runtime_proof=True,
    )


_PLANS: Final[dict[str, WaveCapabilityExecutionPlan]] = {
    "media.inspect": _local("media.inspect", evidence=("ffprobe",)),
    "media.ingest": _editorial("media.ingest", evidence=("sha256", "ffprobe")),
    "image.inspect": _local("image.inspect", evidence=("ffprobe", "sha256")),
    "image.crop": _tool(
        "image.crop",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash",),
    ),
    "image.resize": _tool(
        "image.resize",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash",),
    ),
    "image.color": _tool(
        "image.color",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("color-metadata", "artifact-hash"),
    ),
    "image.retouch": _tool(
        "image.retouch",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash",),
    ),
    "image.composite": _tool(
        "image.composite",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash",),
    ),
    "image.export": _tool(
        "image.export",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash", "format-probe"),
    ),
    "image.qc": _local(
        "image.qc",
        evidence=("format-probe", "dimensions", "color-metadata", "artifact-hash"),
    ),
    "illustration.create": _tool(
        "illustration.create",
        mode=WaveExecutionMode.KRITA_SCRIPTED,
        tool_id="krita",
        evidence=("artifact-hash",),
    ),
    "storyboard.create": WaveCapabilityExecutionPlan(
        capability="storyboard.create",
        mode=WaveExecutionMode.WAVE_COMPOSITE,
        allowed_tool_ids=("krita", "blender"),
        evidence_engines=("artifact-hash", "human-review"),
        requires_tool_qualification=True,
        requires_runtime_proof=True,
    ),
    "animation.plan": WaveCapabilityExecutionPlan(
        capability="animation.plan",
        mode=WaveExecutionMode.WAVE_COMPOSITE,
        evidence_engines=("shot-plan", "human-review"),
        requires_checkpoint=False,
    ),
    "animation.scene.inspect": _tool(
        "animation.scene.inspect",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("blender-scene-state",),
    ),
    "animation.fixture.create": _tool(
        "animation.fixture.create",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("blend-artifact-hash",),
    ),
    "animation.shot.build": _tool(
        "animation.shot.build",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("blend-artifact-hash", "shot-manifest"),
    ),
    "animation.grease_pencil": _tool(
        "animation.grease_pencil",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("grease-pencil-state", "blend-artifact-hash"),
    ),
    "animation.rig": _tool(
        "animation.rig",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("rig-state", "blend-artifact-hash"),
    ),
    "animation.lipsync": WaveCapabilityExecutionPlan(
        capability="animation.lipsync",
        mode=WaveExecutionMode.WAVE_COMPOSITE,
        allowed_tool_ids=("blender", "opentoonz"),
        evidence_engines=("phoneme-timing", "frame-timing", "human-review"),
        requires_tool_qualification=True,
        requires_runtime_proof=True,
    ),
    "animation.composite": _tool(
        "animation.composite",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("compositor-state", "artifact-hash"),
    ),
    "animation.render.frames": _tool(
        "animation.render.frames",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("frame-manifest", "artifact-hash"),
    ),
    "animation.render.frames.repair": _tool(
        "animation.render.frames.repair",
        mode=WaveExecutionMode.BLENDER_SCRIPTED,
        tool_id="blender",
        evidence=("frame-manifest", "repair-receipt"),
    ),
    "scene.detect": _editorial(
        "scene.detect",
        evidence=("pyscenedetect", "source-sha256"),
    ),
    "timeline.create": _editorial("timeline.create", evidence=("opentimelineio",)),
    "timeline.inspect": _editorial("timeline.inspect", evidence=("opentimelineio",)),
    "timeline.cut": _editorial("timeline.cut", evidence=("opentimelineio",)),
    "timeline.trim": _editorial("timeline.trim", evidence=("opentimelineio",)),
    "timeline.move": _editorial("timeline.move", evidence=("opentimelineio",)),
    "timeline.transition": _editorial(
        "timeline.transition",
        evidence=("opentimelineio",),
    ),
    "timeline.marker": _editorial("timeline.marker", evidence=("opentimelineio",)),
    "timeline.caption": _editorial("timeline.caption", evidence=("opentimelineio",)),
    "timeline.audio_sync": _editorial(
        "timeline.audio_sync",
        evidence=("ffprobe", "sync-analysis"),
    ),
    "visual.reframe": _editorial("visual.reframe", evidence=("ffmpeg",)),
    "visual.compose": _editorial("visual.compose", evidence=("ffmpeg",)),
    "visual.color": _editorial(
        "visual.color",
        evidence=("ffmpeg", "color-metadata"),
    ),
    "visual.qc": _local(
        "visual.qc",
        evidence=("video_qc", "ffprobe", "blackdetect", "freezedetect"),
    ),
    "delivery.encode": _editorial(
        "delivery.encode",
        evidence=("ffmpeg", "ffprobe", "artifact-hash"),
    ),
    "web.architecture": _web(
        "web.architecture",
        evidence=("requirements-contract",),
    ),
    "web.implement": _web(
        "web.implement",
        evidence=("build", "browser-smoke"),
    ),
    "web.responsive": _web(
        "web.responsive",
        evidence=("playwright", "viewport-matrix"),
    ),
    "web.accessibility": _web(
        "web.accessibility",
        evidence=("wcag-2.2", "axe-playwright", "manual-review-required"),
    ),
    "web.performance": _web(
        "web.performance",
        evidence=("lighthouse", "core-web-vitals"),
    ),
    "web.visual_regression": _web(
        "web.visual_regression",
        evidence=("playwright", "screenshot-baseline"),
    ),
    "web.browser_compat": _web(
        "web.browser_compat",
        evidence=("playwright", "browser-matrix"),
    ),
    "web.preview": _web(
        "web.preview",
        evidence=("build", "browser-smoke", "human-review"),
    ),
}


_TASK_SURFACES: Final[dict[str, tuple[str, ...]]] = {
    "photo": (
        "media.ingest",
        "image.inspect",
        "image.crop",
        "image.resize",
        "image.color",
        "image.retouch",
        "image.composite",
        "image.export",
        "image.qc",
    ),
    "cartoon": (
        "media.ingest",
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
        "visual.qc",
        "delivery.encode",
    ),
    "video": (
        "media.inspect",
        "media.ingest",
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
    ),
    "website": (
        "web.architecture",
        "web.implement",
        "web.responsive",
        "web.accessibility",
        "web.performance",
        "web.visual_regression",
        "web.browser_compat",
        "web.preview",
    ),
}


def capability_execution_plan(capability: str) -> WaveCapabilityExecutionPlan:
    value = str(capability or "").strip()
    try:
        return _PLANS[value]
    except KeyError as exc:
        raise KeyError(f"UNKNOWN_WAVE_PRODUCTION_CAPABILITY:{value}") from exc


def task_surface(mission_kind: str) -> tuple[str, ...]:
    key = str(mission_kind or "").strip().casefold()
    try:
        return _TASK_SURFACES[key]
    except KeyError as exc:
        raise KeyError(f"UNKNOWN_WAVE_MISSION_KIND:{mission_kind}") from exc


def tool_surface_metrics(
    *,
    mission_kind: str,
    capabilities: Iterable[str],
) -> WaveToolSurfaceMetrics:
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
    return WaveToolSurfaceMetrics(
        mission_kind=str(mission_kind),
        capability_count=len(materialized),
        utf8_bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )
