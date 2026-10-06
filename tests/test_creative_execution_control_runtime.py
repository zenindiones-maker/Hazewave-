from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "scripts" / "codespaces" / "creative-execution-control.sh"
RUNTIME_PROOF = ROOT / "scripts" / "codespaces" / "hazewave-runtime-proof.sh"


def test_creative_execution_control_is_bounded_and_non_provisioning() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'BRANCH="work/creative-execution-plane-v1"' in text
    assert "python -m hazewave.creative_cli doctor" in text
    assert "python -m hazewave.creative_cli snapshot" in text
    assert "python -m hazewave.creative_cli execute" in text
    assert "ffprobe" in text
    assert "ffmpeg" in text
    assert "aplay" in text

    for forbidden in (
        "gh codespace create",
        "git reset",
        "git checkout",
        "git pull",
        "git merge",
        "git push",
        "sudo ",
    ):
        assert forbidden not in text


def test_candidate_runtime_proof_binds_to_creative_branch_and_bridge() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert 'BRANCH="work/creative-execution-plane-v1"' in text
    assert "CreativeProducerDoctor/v1" in text
    assert "HAZEWAVE_REAPER_BRIDGE" in text
    assert "LIVE_REAPER_PROOF=NOT_PROVEN" in text


def test_creative_execution_control_exposes_render_preview_with_qc() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert "cmd_render_preview()" in text
    assert "python -m hazewave.creative_cli render-preview" in text
    assert "render-preview) cmd_render_preview" in text
    assert "HUMAN_APPROVAL=REQUIRED" in text
