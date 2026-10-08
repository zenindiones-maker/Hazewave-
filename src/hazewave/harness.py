from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
from typing import Final

PROJECT_ID: Final = "HAZEWAVE"
AUTHORITY: Final = "HAZEWAVE_HARNESS"

HAZE: Final = "HAZE"
WAVE: Final = "WAVE"
BRIDGE: Final = "BRIDGE"

_CAPABILITY_DOMAINS: Final[dict[str, str]] = {
    "audio.generate": HAZE,
    "audio.separate": HAZE,
    "audio.analyze": HAZE,
    "research.audio.inspect": HAZE,
    "research.visual.inspect": WAVE,
    "audio.mix": HAZE,
    "audio.master": HAZE,
    "audio.voice": HAZE,
    "audio.transcribe": HAZE,
    "audio.reason": HAZE,
    "audio.describe": HAZE,
    "audio.structure": HAZE,
    "session.inspect": HAZE,
    "session.checkpoint": HAZE,
    "session.rollback": HAZE,
    "session.fixture.open": HAZE,
    "session.fixture.close": HAZE,
    "arrangement.structure": HAZE,
    "arrangement.marker": HAZE,
    "arrangement.region": HAZE,
    "audio.import": HAZE,
    "audio.edit": HAZE,
    "audio.split": HAZE,
    "audio.trim": HAZE,
    "audio.fade": HAZE,
    "audio.align": HAZE,
    "audio.time_stretch": HAZE,
    "audio.pitch": HAZE,
    "audio.compare": HAZE,
    "audio.qc": HAZE,
    "track.create": HAZE,
    "track.configure": HAZE,
    "track.folder": HAZE,
    "routing.bus": HAZE,
    "routing.send": HAZE,
    "routing.sidechain": HAZE,
    "routing.parallel": HAZE,
    "fx.inventory": HAZE,
    "fx.add": HAZE,
    "fx.remove": HAZE,
    "fx.bypass": HAZE,
    "fx.preset": HAZE,
    "fx.parameter.read": HAZE,
    "fx.parameter.write": HAZE,
    "fx.automation": HAZE,
    "mix.gainstage": HAZE,
    "mix.balance": HAZE,
    "mix.eq": HAZE,
    "mix.dynamics": HAZE,
    "mix.saturation": HAZE,
    "mix.spatial": HAZE,
    "mix.delay": HAZE,
    "mix.reverb": HAZE,
    "mix.automation": HAZE,
    "master.prepare": HAZE,
    "master.process": HAZE,
    "master.render": HAZE,
    "render.preview": HAZE,
    "render.stems": HAZE,
    "render.master": HAZE,
    "image.inspect": WAVE,
    "image.crop": WAVE,
    "image.resize": WAVE,
    "image.color": WAVE,
    "image.retouch": WAVE,
    "image.composite": WAVE,
    "image.export": WAVE,
    "image.qc": WAVE,
    "illustration.create": WAVE,
    "storyboard.create": WAVE,
    "animation.plan": WAVE,
    "animation.grease_pencil": WAVE,
    "animation.rig": WAVE,
    "animation.lipsync": WAVE,
    "animation.composite": WAVE,
    "web.architecture": WAVE,
    "web.implement": WAVE,
    "web.responsive": WAVE,
    "web.accessibility": WAVE,
    "web.performance": WAVE,
    "web.visual_regression": WAVE,
    "web.browser_compat": WAVE,
    "web.preview": WAVE,
    "visual.render": WAVE,
    "visual.image": WAVE,
    "visual.video": WAVE,
    "visual.site": WAVE,
    "visual.animate": WAVE,
    "animation.scene.inspect": WAVE,
    "animation.fixture.create": WAVE,
    "animation.shot.build": WAVE,
    "animation.render.frames": WAVE,
    "animation.render.frames.repair": WAVE,
    "visual.analyze": WAVE,
    "visual.storyboard": WAVE,
    "visual.reason": WAVE,
    "visual.describe": WAVE,
    "media.inspect": WAVE,
    "media.ingest": WAVE,
    "scene.detect": WAVE,
    "timeline.create": WAVE,
    "timeline.inspect": WAVE,
    "timeline.cut": WAVE,
    "timeline.trim": WAVE,
    "timeline.move": WAVE,
    "timeline.transition": WAVE,
    "timeline.marker": WAVE,
    "timeline.caption": WAVE,
    "timeline.audio_sync": WAVE,
    "visual.reframe": WAVE,
    "visual.compose": WAVE,
    "visual.color": WAVE,
    "visual.qc": WAVE,
    "delivery.encode": WAVE,
    "bridge.haze_to_wave": BRIDGE,
    "bridge.semantic_translation": BRIDGE,
    "bridge.motif_to_topology": BRIDGE,
    "bridge.section_to_transition": BRIDGE,
}

_CROSS_DOMAIN_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "reason.general",
        "reason.deep",
        "reason.fusion",
        "code.generate",
        "code.review",
        "embedding.create",
    }
)


@dataclass(frozen=True)
class HazewaveTask:
    task_id: str
    goal: str
    required_capability: str
    requested_domain: str


@dataclass(frozen=True)
class HazewaveRouteDecision:
    project_id: str
    task_id: str
    selected_domain: str
    selected_capability: str
    authority: str = AUTHORITY
    schema: str = "HazewaveRouteDecision/v1"


@dataclass(frozen=True)
class HazewaveAuthorization:
    authorization_id: str
    project_id: str
    task_id: str
    capability_id: str
    domain: str
    authority: str = AUTHORITY
    schema: str = "HazewaveAuthorization/v1"


def classify_capability_domain(capability_id: str) -> str:
    value = str(capability_id or "").strip()
    if value in _CROSS_DOMAIN_CAPABILITIES:
        raise ValueError(f"CROSS_DOMAIN_CAPABILITY_REQUIRES_REQUESTED_DOMAIN:{value}")
    try:
        return _CAPABILITY_DOMAINS[value]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_HAZEWAVE_CAPABILITY:{value}") from exc


def capability_allows_domain(capability_id: str, domain: str) -> bool:
    value = str(capability_id or "").strip()
    if value in _CROSS_DOMAIN_CAPABILITIES:
        return domain in {HAZE, WAVE, BRIDGE}
    return classify_capability_domain(value) == domain


def route_task(task: HazewaveTask) -> HazewaveRouteDecision:
    if not task.task_id.strip():
        raise ValueError("TASK_ID_REQUIRED")
    if not task.goal.strip():
        raise ValueError("GOAL_REQUIRED")
    if task.requested_domain not in {HAZE, WAVE, BRIDGE}:
        raise ValueError("UNKNOWN_HAZEWAVE_DOMAIN")
    if not capability_allows_domain(task.required_capability, task.requested_domain):
        raise PermissionError("DOMAIN_CAPABILITY_MISMATCH")
    selected_domain = task.requested_domain
    return HazewaveRouteDecision(
        project_id=PROJECT_ID,
        task_id=task.task_id,
        selected_domain=selected_domain,
        selected_capability=task.required_capability,
    )


def issue_authorization(decision: HazewaveRouteDecision) -> HazewaveAuthorization:
    if decision.project_id != PROJECT_ID or decision.authority != AUTHORITY:
        raise PermissionError("ROUTE_DECISION_AUTHORITY_INVALID")
    payload = {
        "project_id": decision.project_id,
        "task_id": decision.task_id,
        "capability_id": decision.selected_capability,
        "domain": decision.selected_domain,
        "authority": AUTHORITY,
    }
    authorization_id = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return HazewaveAuthorization(
        authorization_id=authorization_id,
        project_id=PROJECT_ID,
        task_id=decision.task_id,
        capability_id=decision.selected_capability,
        domain=decision.selected_domain,
    )


def validate_authorization(
    authorization: HazewaveAuthorization,
    *,
    expected_task_id: str,
    expected_capability: str,
) -> HazewaveAuthorization:
    if authorization.authority != AUTHORITY or authorization.project_id != PROJECT_ID:
        raise PermissionError("AUTHORIZATION_AUTHORITY_INVALID")
    if authorization.task_id != expected_task_id:
        raise PermissionError("AUTHORIZATION_TASK_MISMATCH")
    if authorization.capability_id != expected_capability:
        raise PermissionError("AUTHORIZATION_CAPABILITY_MISMATCH")
    if not capability_allows_domain(expected_capability, authorization.domain):
        raise PermissionError("AUTHORIZATION_DOMAIN_MISMATCH")
    return authorization


def harness_status() -> dict[str, object]:
    return {
        "schema": "HazewaveHarnessStatus/v1",
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "domains": [HAZE, WAVE, BRIDGE],
        "capabilities": sorted(set(_CAPABILITY_DOMAINS) | set(_CROSS_DOMAIN_CAPABILITIES)),
        "portfolio_authority": "NONE",
        "status": "ONLINE",
    }


def _main() -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.harness")
    parser.add_argument("command", choices=("doctor",))
    args = parser.parse_args()
    if args.command == "doctor":
        status = harness_status()
        for key in (
            "project_id",
            "authority",
            "status",
            "portfolio_authority",
        ):
            print(f"{key.upper()}={status[key]}")
        print("HAZEWAVE_DOMAINS=" + ",".join(status["domains"]))
        print(f"HAZEWAVE_CAPABILITY_COUNT={len(status['capabilities'])}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
