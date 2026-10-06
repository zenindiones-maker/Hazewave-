from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "scripts" / "codespaces" / "hazewave-termux-control.sh"


def test_creative_plane_reuses_existing_codespace_and_targets_candidate() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'BRANCH="work/creative-execution-plane-v1"' in text
    assert "EXISTING_CODESPACE_REUSE=REQUIRED" in text
    assert "gh codespace create" not in text


def test_creative_plane_control_exposes_required_producer_commands() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    for command in (
        "producer-doctor",
        "snapshot",
        "execute",
        "audition",
        "proof",
        "open",
    ):
        assert command in text
