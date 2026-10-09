"""Fail-closed WAVE owned learning receipt tests; no external site authority."""
from __future__ import annotations
from pathlib import Path
import json
import stat

import pytest

from test_wave_scroll_evidence import _report, REPO_SHA
from hazewave.wave_scroll_learning import (
    ScrollLearningError, learn_from_owned_scroll,
    load_rea_evidence, store_append_only_packet,
)


def _rea() -> dict:
    return {"evidence_id": "ev_" + "a" * 64,
            "normalized_result": {"graph": {"nodes": [
                {"kind": "javascript-module", "path": "main.js"}
            ]}}}


def test_cross_layer_learning_is_append_only_private_and_non_authoritative(tmp_path):
    browser_root = tmp_path / "frames"
    report = _report(browser_root)
    learned = learn_from_owned_scroll(
        capture=report, capture_root=browser_root,
        repo_sha=REPO_SHA, rea_evidence=_rea(),
    )
    assert learned["authority"] == "NONE"
    assert learned["project_authority"] == "HAZEWAVE_HARNESS"
    assert learned["source_scope"] == "FIRST_PARTY_OWNED_FIXTURE"
    assert learned["rea_static_module_nodes"] == 1
    assert learned["verified_frame_count"] == 8
    assert len(learned["techniques"]) == 5
    assert learned["learned_from_external_sites"] is False
    assert learned["production_approved"] is False
    assert learned["capability_measured_ready"] is False

    private = tmp_path / "state"
    first = store_append_only_packet(packet=learned, state_root=private)
    second = store_append_only_packet(packet=learned, state_root=private)
    assert first == second
    assert len(list((private / "wave-scroll-learning").glob("*.json"))) == 1
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    assert json.loads(first.read_text())["rea_evidence_id"] == _rea()["evidence_id"]


def test_rejects_unverified_rea_graph(tmp_path):
    browser_root = tmp_path / "frames"
    report = _report(browser_root)
    with pytest.raises(ScrollLearningError, match="REA_STATIC_GRAPH_UNVERIFIED"):
        learn_from_owned_scroll(
            capture=report, capture_root=browser_root,
            repo_sha=REPO_SHA, rea_evidence={"evidence_id": "ev_" + "a"*64},
        )


def test_rejects_privileged_knowledge_packet(tmp_path):
    for field, value in (("authority", "HAZEWAVE_HARNESS"),
                         ("grants_execution_authority", True),
                         ("production_approved", True)):
        packet = {"schema": "HazewaveWaveScrollLearningPacket/v1",
                  "authority": "NONE",
                  "grants_execution_authority": False,
                  "production_approved": False}
        packet[field] = value
        with pytest.raises(ScrollLearningError, match="LEARNING_PACKET_AUTHORITY_INVALID"):
            store_append_only_packet(packet=packet, state_root=tmp_path / field)


def test_rejects_learning_state_inside_repository():
    from hazewave.wave_scroll_learning import ROOT
    with pytest.raises(ScrollLearningError, match="LEARNING_STATE_LOCATION_UNSAFE"):
        store_append_only_packet(
            packet={"schema":"HazewaveWaveScrollLearningPacket/v1",
                    "authority":"NONE",
                    "grants_execution_authority":False,
                    "production_approved":False},
            state_root=ROOT / "runtime-receipts-forbidden",
        )


def test_rejects_corrupted_existing_immutable_receipt(tmp_path):
    browser_root = tmp_path / "frames"
    learned = learn_from_owned_scroll(
        capture=_report(browser_root), capture_root=browser_root,
        repo_sha=REPO_SHA, rea_evidence=_rea(),
    )
    path = store_append_only_packet(packet=learned, state_root=tmp_path / "state")
    path.write_text("poisoned")
    with pytest.raises(ScrollLearningError, match="LEARNING_RECEIPT_CONFLICT"):
        store_append_only_packet(packet=learned, state_root=tmp_path / "state")


def test_duplicate_rea_json_is_rejected(tmp_path):
    path = tmp_path / "rea.json"
    path.write_text('{"evidence_id":"one","evidence_id":"two"}')
    with pytest.raises(ScrollLearningError, match="REA_EVIDENCE_MALFORMED"):
        load_rea_evidence(path)
