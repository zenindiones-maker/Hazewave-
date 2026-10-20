from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codespaces" / "harness-live-research-bridge.sh"


def test_bridge_is_existing_codespace_only_with_accurate_scoped_modes():
    s = SCRIPT.read_text()
    for text in (
        "hazewave-zero-cost-4jxp45676rq6279xx",
        "--preflight", "--prove", "--mcp",
        "HAZEWAVE_RESEARCH_EXPECTED_SHA",
        "harness_research_execution",
        "harness_research_mcp",
        "rea-6.0.0/bin/rea",
        "iris/v0.4.1/bin/iris",
        "NO_EXTERNAL_TARGETS",
    ):
        assert text in s
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_bridge_does_not_mutate_existing_codespace_or_global_agents():
    s = SCRIPT.read_text()
    for banned in ("gh codespace create", "git checkout", "git reset",
                   "git merge", "git push", "sudo ", "curl | sh",
                   "hazewave-reflex serve-stop", "codex mcp add",
                   "rea-agents@latest", "--no-sandbox", "npm install",
                   "pip install", "rm -rf"):
        assert banned not in s
    assert "--host-id" not in s
    assert 'git -C "$ROOT" status --porcelain' in s


def test_codespace_bridge_bails_out_before_any_side_effects_offhost():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--preflight"],
        env={"HOME": "/tmp", "PATH": "/usr/bin:/bin", "CODESPACE_NAME": "unknown"},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "CODESPACE_ID_MISMATCH" in result.stderr
