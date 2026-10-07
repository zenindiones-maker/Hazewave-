from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = (
    ROOT / "scripts" / "install_hazewave_termux_runtime.sh",
    ROOT / "scripts" / "hazewave_termux_control.sh",
    ROOT / "scripts" / "hazewave_reflex_termux_control.sh",
    ROOT / "scripts" / "install_hazewave_always_ready_termux.sh",
    ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh",
    ROOT / "scripts" / "codespaces" / "start-always-ready.sh",
)


def test_termux_shell_scripts_have_valid_bash_syntax() -> None:
    for script in SCRIPTS:
        completed = subprocess.run(
            ["bash", "-n", str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{script.name} failed bash -n\n"
            + completed.stdout
            + completed.stderr
        )


def test_termux_shell_scripts_do_not_embed_literal_newline_escape_between_commands() -> None:
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        assert "\\ntest -f" not in text


def test_reflex_candidate_ref_propagates_from_termux_to_codespace_runtime() -> None:
    termux = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert 'REF="${HAZEWAVE_REFLEX_REF:-work/hazewave-always-ready-v1}"' in termux
    assert 'REF="${HAZEWAVE_REFLEX_REF:-work/hazewave-always-ready-v1}"' in remote
    assert "HAZEWAVE_REFLEX_REF='$REF'" in termux


def test_reflex_codespace_lifecycle_waits_through_shutdown_transition_before_restart() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert "codespace_metadata_row() {" in text
    assert "codespace_state_action() {" in text
    assert "ShuttingDown|Stopping" in text
    assert 'printf \'%s\\n\' "WAIT"' in text
    assert 'printf \'%s\\n\' "START"' in text
    assert 'printf \'%s\\n\' "READY"' in text
    assert 'action="$(codespace_state_action "$current_state")"' in text
    assert 'if [[ "$action" == "START" && "$start_requested" == "0" ]]; then' in text
    assert 'gh codespace view -c "$CS" --json state' not in text


def test_reflex_codespace_metadata_avoids_full_details_view_endpoint() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert 'gh codespace list --limit 100 --json name,state,repository' in text
    assert 'gh codespace view -c "$CS" --json name' not in text
    assert 'gh codespace view -c "$CS" --json repository' not in text
