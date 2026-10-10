"""Real-source checks for immutable npm dependency admission."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_wave_ci_invokes_frozen_real_site_entrypoint():
    workflow=(ROOT/".github/workflows/wave-site-ci.yml").read_text(encoding="utf-8")
    script=(ROOT/"scripts/run_hazewave_site.sh").read_text(encoding="utf-8")
    assert "npm install --package-lock-only" not in workflow
    assert "bash ../../scripts/run_hazewave_site.sh verify" in workflow
    assert "npm ci --ignore-scripts --no-audit --no-fund" in script
    assert "git -C \"$ROOT\" diff --exit-code HEAD -- apps/hazewave-site/package-lock.json" in script
    assert script.index("npm ci --ignore-scripts") < script.index('git -C "$ROOT" diff --exit-code HEAD -- apps/hazewave-site/package-lock.json')
