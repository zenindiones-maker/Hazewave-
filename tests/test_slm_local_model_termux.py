"""Termux A15 existing-local-model gate: no installs or interactive shell exit."""
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CTRL=ROOT/"scripts/termux/hazewave-slm-qualify-v3.sh"


def test_unrecognized_mode_stops_before_network_or_repo_changes():
    p=subprocess.run(["bash",str(CTRL),"--pull-new-model"],
                     text=True,capture_output=True,timeout=10)
    assert p.returncode==20
    assert "MODE_NOT_ADMITTED" in p.stderr


def test_missing_expected_sha_stops_before_any_remote_access():
    env={**os.environ,"HAZEWAVE_SLM_V3_EXPECTED_SHA":"bad"}
    p=subprocess.run(["bash",str(CTRL),"--inventory"],env=env,
                     text=True,capture_output=True,timeout=10)
    assert p.returncode==20
    assert "SHA_INVALID" in p.stderr


def test_termux_entrypoint_uses_isolated_existing_worktree_and_never_auto_wakes_machine():
    data=CTRL.read_text()
    assert 'work/slm-real-model-qualification-v3' in data
    assert 'worktree add --detach' in data
    assert 'sha256sum' in data or 'sha256(' in data
    assert '127.0.0.1:11434' in data or 'slm_local_model_qualification' in data
    assert 'LOCAL_MODEL_IDENTITY=NOT_UPSTREAM_ATTESTED' in data
    assert 'TERMUX_PARENT_SHELL_UNCHANGED=TRUE' in data
    for bad in ("gh codespace create", "gh codespace start",
                "git reset --hard", "pip install", "npm install",
                "ollama pull", "ollama run", "gh codespace cp"):
        assert bad not in data
    assert subprocess.run(["bash","-n",str(CTRL)],capture_output=True).returncode==0


def test_host_probe_has_exact_private_prior_audio_source_and_no_automatic_fallback():
    data=CTRL.read_text()
    assert '2d779b38cfa0d8b093160b9df5b7b130a13fa538' in data
    assert '0a5c4f3ba77a8e13ad3aa7dcad91f2853cfb6058d262e763381715749d07cfe4' in data
    assert '9dc6f17a60a4406dd2a233cb719a8e6145ca0a1533dd052173e7d408aa03b3b6' in data
    assert 'qwen3:4b' in data
    assert '--probe' in data
    assert '--expected-digest' in data
    assert '--model "$MODEL"' in data
    assert 'HAZE_MODEL_PRODUCTION_APPROVED=FALSE' in data
