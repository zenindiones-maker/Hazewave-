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


def test_termux_execute_and_audition_forward_one_bounded_argument() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'execute) cmd_creative_remote execute "${2:-}" ;;' in text
    assert 'audition) cmd_creative_remote audition "${2:-}" ;;' in text
    assert 'printf -v remote_arg' in text


def test_termux_control_can_invoke_render_preview_on_existing_codespace() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert "render-preview) cmd_creative_remote render-preview" in text
    assert "gh codespace create" not in text



def test_termux_control_can_invoke_vertical_proof_on_existing_codespace() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'vertical-proof) cmd_creative_remote vertical-proof "${2:-}" ;;' in text
    assert "gh codespace create" not in text


def test_termux_vertical_proof_requires_no_cross_device_file_path() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert "vertical-proof) cmd_creative_remote vertical-proof ;;" in text
    assert 'cmd_creative_remote vertical-proof "${2:-}"' not in text
