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
    "audio.mix": HAZE,
    "audio.master": HAZE,
    "audio.voice": HAZE,
    "visual.render": WAVE,
    "visual.image": WAVE,
    "visual.video": WAVE,
    "visual.site": WAVE,
    "visual.animate": WAVE,
    "bridge.haze_to_wave": BRIDGE,
}


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
    try:
        return _CAPABILITY_DOMAINS[value]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_HAZEWAVE_CAPABILITY:{value}") from exc


def route_task(task: HazewaveTask) -> HazewaveRouteDecision:
    if not task.task_id.strip():
        raise ValueError("TASK_ID_REQUIRED")
    if not task.goal.strip():
        raise ValueError("GOAL_REQUIRED")
    selected_domain = classify_capability_domain(task.required_capability)
    if task.requested_domain not in {HAZE, WAVE, BRIDGE}:
        raise ValueError("UNKNOWN_HAZEWAVE_DOMAIN")
    if selected_domain != task.requested_domain:
        raise PermissionError("DOMAIN_CAPABILITY_MISMATCH")
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
    if classify_capability_domain(expected_capability) != authorization.domain:
        raise PermissionError("AUTHORIZATION_DOMAIN_MISMATCH")
    return authorization


def harness_status() -> dict[str, object]:
    return {
        "schema": "HazewaveHarnessStatus/v1",
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "domains": [HAZE, WAVE, BRIDGE],
        "capabilities": sorted(_CAPABILITY_DOMAINS),
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
