from __future__ import annotations
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/codespaces/research-closed-loop-qualification.sh"


def test_host_gated_closed_loop_is_opt_in_and_sha_bound():
    script = SCRIPT.read_text()
    assert "hazewave-zero-cost-4jxp45676rq6279xx" in script
    assert "HAZEWAVE_RESEARCH_EXPECTED_SHA" in script
    assert "--preflight|--native-auto|--av-metrics" in script
    assert "native_behavior_synthesis" in script
    assert "av_fidelity_oracle" in script
    assert 'git -C "$ROOT" status --porcelain' in script
    assert "STOCK_HEALTH=NOT_CHECKED" in script
    assert subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True).returncode == 0


def test_host_gate_denies_wrong_host_before_side_effects():
    result = subprocess.run(["bash",str(SCRIPT),"--preflight"],
        env={"CODESPACE_NAME":"not-our-codespace","HOME":"/tmp","PATH":"/usr/bin:/bin"},
        text=True,capture_output=True)
    assert result.returncode != 0
    assert "EXISTING_CODESPACE_REQUIRED" in result.stderr


def test_host_qualification_never_merges_installs_paid_tools_or_registers_global_agents():
    script=SCRIPT.read_text()
    for banned in ("gh codespace create","git reset","git merge","git push","sudo ",
                   "pip install","apt-get","npm install","codex mcp add",
                   "hazewave-reflex serve-stop","--no-sandbox","curl | bash"):
        assert banned not in script
