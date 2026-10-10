"""An E2E run must never reuse a previous server in CI."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_playwright_ci_launches_a_fresh_preview_server():
    config=(ROOT/"apps/hazewave-site/playwright.config.ts").read_text(encoding="utf8")
    runner=(ROOT/"scripts/run_hazewave_site.sh").read_text(encoding="utf8")
    assert "reuseExistingServer: !process.env.CI" in config
    assert "reuseExistingServer: true" not in config
    assert "CI=true npm test" in runner
    assert "http://127.0.0.1:4321" in config
    assert "npm run preview -- --host 127.0.0.1 --port 4321" in config
