"""Check that the ONE command is the CI exercised WAVE site path, not a placeholder."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_site_launcher_has_real_install_build_browser_start():
    source=(ROOT/"scripts/run_hazewave_site.sh").read_text(encoding="utf8")
    expected=[
        "set -Eeuo pipefail", 'npm ci --ignore-scripts --no-audit --no-fund',
        'npx tsc --noEmit', 'npm run build',
        'node scripts/verify-owner-art.mjs --dist',
        'node scripts/check-bundle-budget.mjs',
        'npx playwright install chromium',
        'CI=true npm test -- --workers=1 --project=chromium-desktop --project=chromium-mobile',
        'exec npm run preview -- --host 127.0.0.1 --port 4321'
    ]
    for command in expected:
        assert command in source, command
    assert "HAZEWAVE_SITE_E2E=PASS" in source
    assert "exit 69" in source
    assert "curl" not in source

def test_original_and_distribution_media_verifiers_have_distinct_scopes():
    source=(ROOT/"apps/hazewave-site/scripts/verify-owner-art.mjs").read_text(encoding="utf8")
    assert "if (useDist" in source
    assert "allowedDistAssets" in source
    assert "/media/hazewave-world.jpg" in source
    assert "/media/artists/indionesbala.webp" in source
