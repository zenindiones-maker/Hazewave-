"""Append-only, non-authoritative learning from cross-layer WAVE fixture evidence.

Knowledge is evidence, never task authorization. The payload is born from
validated owned browser pixels plus an independently checked REA6 JS graph;
neither envelope establishes Codespace or third-party website readiness.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from hazewave.rea6_provider_conformance import fixture_tree_sha, validate_javascript_probe
from hazewave.wave_scroll_evidence import (
    ScrollResearchError, load_capture_json, verify_owned_scroll_capture
)

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "tests/fixtures/wave-scroll-js-owned"
REPO_SHA = re.compile(r"^[a-f0-9]{40}$")


class ScrollLearningError(ValueError):
    pass


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScrollLearningError("REA_JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def load_rea_evidence(path: Path) -> dict[str, Any]:
    source = Path(path)
    if (source.is_symlink() or not source.is_file()
            or source.stat().st_size > 4_000_000):
        raise ScrollLearningError("REA_EVIDENCE_FILE_UNSAFE")
    try:
        data = json.loads(source.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_duplicates)
    except (ValueError, UnicodeError, OSError) as exc:
        raise ScrollLearningError("REA_EVIDENCE_MALFORMED") from exc
    if not isinstance(data, dict):
        raise ScrollLearningError("REA_EVIDENCE_MALFORMED")
    return data


def learn_from_owned_scroll(
    *, capture: Mapping[str, Any], capture_root: Path,
    repo_sha: str, rea_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(repo_sha, str) or not REPO_SHA.fullmatch(repo_sha):
        raise ScrollLearningError("REPO_SHA_INVALID")
    browser = verify_owned_scroll_capture(
        capture, capture_root=Path(capture_root), repo_sha=repo_sha
    )
    try:
        graph = validate_javascript_probe(
            rea_evidence, fixture_sha256=fixture_tree_sha(APP_ROOT)
        )
    except (ValueError, OSError) as exc:
        raise ScrollLearningError("REA_STATIC_GRAPH_UNVERIFIED") from exc
    if graph["module_node_count"] < 1 or not graph["rea_evidence_id"]:
        raise ScrollLearningError("REA_STATIC_GRAPH_UNVERIFIED")
    expected = sha256((APP_ROOT / "main.js").read_bytes()).hexdigest()
    if browser["app_source_sha256"] != expected:
        raise ScrollLearningError("BROWSER_REA_SOURCE_DRIFT")
    pixel = browser["pixel_sha256"]
    techniques = [
        {"id": "SCROLL_SVG_STROKE_DRAW", "proof_frames": [0, 1, 2]},
        {"id": "CAUSAL_MPC_PAD_ACTIVATION", "proof_frames": [1, 2, 3]},
        {"id": "PHYSICAL_MACHINE_TRANSLATION", "proof_frames": [0, 3, 5]},
        {"id": "ILLUSTRATED_CAMERA_PARALLAX", "proof_frames": [0, 3, 5]},
        {"id": "REVERSIBLE_PHYSICAL_POSE", "proof_frames": [0, 2, 6, 7]},
    ]
    return {
        "schema": "HazewaveWaveScrollLearningPacket/v1",
        "authority": "NONE",
        "project_authority": "HAZEWAVE_HARNESS",
        "domain": "WAVE",
        "source_scope": "FIRST_PARTY_OWNED_FIXTURE",
        "repo_sha_claimed_by_caller": repo_sha,
        "svg_fixture_sha256": browser["source_sha256"],
        "js_runtime_and_rea_target_sha256": expected,
        "rea_evidence_id": graph["rea_evidence_id"],
        "rea_fixture_tree_sha256": graph["fixture_tree_sha256"],
        "rea_static_module_nodes": graph["module_node_count"],
        "browser": browser["browser"],
        "viewport": browser["viewport"],
        "verified_frame_count": browser["verified_frames"],
        "verified_pixel_sha256": pixel,
        "techniques": [
            {**item, "evidence_type": "OWNED_BROWSER_REPRODUCTION",
             "pixel_sha256": [pixel[i] for i in item["proof_frames"]]}
            for item in techniques
        ],
        "learned_from_external_sites": False,
        "cross_layer_static_graph_and_browser_proven_on_ci_fixture": True,
        "rea_process_host_independently_attested": False,
        "codespace_runtime_proven": False,
        "existing_agent_mcp_connected": False,
        "grants_execution_authority": False,
        "capability_measured_ready": False,
        "production_approved": False,
        "human_review": "PENDING",
        "limitations": [
            "Source-known test fixture, not independently reverse-engineered third-party source.",
            "Validated REA Evidence envelope and browser pixels do not attest owner Codespace.",
            "No external live site, signed target grant, auto-promotion or asset redistribution.",
        ],
    }


def store_append_only_packet(*, packet: Mapping[str, Any], state_root: Path) -> Path:
    if packet.get("schema") != "HazewaveWaveScrollLearningPacket/v1" or (
        packet.get("authority") != "NONE"
        or packet.get("grants_execution_authority") is not False
        or packet.get("production_approved") is not False
    ):
        raise ScrollLearningError("LEARNING_PACKET_AUTHORITY_INVALID")
    root = Path(state_root).expanduser()
    if root.is_symlink() or root.resolve(strict=False).is_relative_to(ROOT):
        raise ScrollLearningError("LEARNING_STATE_LOCATION_UNSAFE")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ScrollLearningError("LEARNING_STATE_LOCATION_UNSAFE")
    folder = root / "wave-scroll-learning"
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink():
        raise ScrollLearningError("LEARNING_STATE_LOCATION_UNSAFE")
    folder.chmod(0o700)
    data = (json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    digest = sha256(data).hexdigest()
    destination = folder / f"owned-scroll-{digest}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(destination, flags, 0o600)
    except FileExistsError:
        if destination.is_symlink() or destination.read_bytes() != data:
            raise ScrollLearningError("LEARNING_RECEIPT_CONFLICT")
        return destination
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return destination


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--capture-root", type=Path, required=True)
    p.add_argument("--rea-evidence", type=Path, required=True)
    p.add_argument("--repo-sha", required=True)
    p.add_argument("--state-root", type=Path, required=True)
    args = p.parse_args()
    try:
        packet = learn_from_owned_scroll(
            capture=load_capture_json(args.capture),
            capture_root=args.capture_root,
            repo_sha=args.repo_sha,
            rea_evidence=load_rea_evidence(args.rea_evidence),
        )
        path = store_append_only_packet(packet=packet, state_root=args.state_root)
    except (OSError, ValueError, ScrollResearchError) as exc:
        print("WAVE_SCROLL_LEARNING=BLOCKED:" + str(exc))
        return 20
    print("WAVE_SCROLL_LEARNING=PASS_OWNED_FIXTURE")
    print("WAVE_SCROLL_LEARNING_PACKET_SHA256=" + sha256(path.read_bytes()).hexdigest())
    print("WAVE_SCROLL_LEARNING_TECHNIQUES=" + str(len(packet["techniques"])))
    print("WAVE_EXTERNAL_SITE_LEARNING=NOT_PROVEN")
    print("WAVE_PRODUCTION_APPROVED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
