"""Non-destructive Termux entrypoint for live free specialist benchmarking."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/termux/hazewave-slm-audio-proof.sh"


def test_entrypoint_refuses_unknown_mode_without_touching_runtime(tmp_path):
    p = subprocess.run(["bash", str(SCRIPT), "--install-everything"],
                       text=True, capture_output=True, timeout=10)
    assert p.returncode == 20
    assert "MODE_UNSUPPORTED" in p.stderr


def test_entrypoint_requires_exact_sha_and_never_wakes_codespace():
    s = SCRIPT.read_text()
    assert "work/slm-professional-audio-triage-v1" in s
    assert "HAZEWAVE_SLM_EXPECTED_SHA" in s
    assert 'gh api "user/codespaces/$CS"' in s
    assert "CODESPACE_SHUTDOWN_NOT_ADMITTED" in s
    assert "worktree add --detach" in s
    assert "--compare-baseline" in s
    assert "timeout --kill-after=5s 175s" in s
    assert "python3 -m hazewave.slm_audio_specialist" not in s  # bound A15 venv
    assert "hazewave.slm_audio_specialist" in s
    assert "TERMUX_PARENT_SHELL_UNCHANGED" in s
    assert "install" not in s.split("HAZEWAVE_SLM_RUNTIME_SCOPE=", 1)[-1]
    for unsafe in ("gh codespace create", "gh codespace start", "git reset --hard",
                   "git push --force", "hazewave-reflex serve-stop", "npm install", "pip install"):
        assert unsafe not in s
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_entrypoint_rejects_invalid_sha_without_gh_network(tmp_path):
    env = {**os.environ, "HAZEWAVE_SLM_EXPECTED_SHA": "invalid"}
    p = subprocess.run(["bash", str(SCRIPT), "--benchmark"],
                       env=env, text=True, capture_output=True, timeout=10)
    assert p.returncode == 20
    assert "REVIEWED_SHA_INVALID" in p.stderr


def test_remote_file_transfer_uses_descriptor_bound_nofollow_proof() -> None:
    script = SCRIPT.read_text()
    assert "os.O_NOFOLLOW" in script
    assert "os.fstat(stream.fileno())" in script
    assert "hashlib.sha256(secure(path)).hexdigest()" in script
    assert "def secure(p):" in script
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
