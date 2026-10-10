"""Real-source checks for WAVE's reproducible dependency lock gate."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_wave_ci_does_not_rewrite_committed_lockfile():
    workflow = (ROOT / ".github/workflows/wave-site-ci.yml").read_text(encoding="utf-8")
    assert "npm install --package-lock-only" not in workflow
    assert "npm ci --ignore-scripts --no-audit --no-fund" in workflow
    assert "git diff --exit-code HEAD -- package-lock.json" in workflow
    assert workflow.index("npm ci --ignore-scripts") < workflow.index("git diff --exit-code")
