"""Regression for the user-approved Hazewave root engineering protocol.

Checks the real AGENTS.md; no synthetic harness is used.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

def test_existing_harness_authority_remains_intact():
    assert "Hazewave Harness" in TEXT
    assert "config/project-profile-v2.json" in TEXT
    assert "HAZE" in TEXT and "WAVE" in TEXT and "BRIDGE" in TEXT
    assert "Do not push directly to the canonical branch" in TEXT

def test_five_phase_operational_contract_installed_once():
    heading = "Mandatory principal-engineer audit and real-execution protocol"
    assert TEXT.count(heading) == 1
    for item in (
        "PHASE 1 — Reverse engineer before modifying",
        "PHASE 2 — Adversarial GAP MAP",
        "PHASE 3 — Current primary-source research",
        "PHASE 4 — Correct and harden",
        "PHASE 5 — Clean end-to-end verification",
        "initial GAP MAP",
        "final GAP MAP",
        "the exact single launch/check command",
        "FIXED_VERIFIED",
        "OPEN",
        "BLOCKED",
    ):
        assert item in TEXT, item

def test_zero_cost_private_media_and_human_gate_remain_explicit():
    for item in (
        "not a new control plane",
        "Hazewave Harness",
        "Indionesbala",
        "human approval",
        "private-media",
        "single documented entrypoint",
        "not an unsupervised infinite loop",
    ):
        assert item.lower() in TEXT.lower(), item
