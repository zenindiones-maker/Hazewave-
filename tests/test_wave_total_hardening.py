"""Guardrails for the exact real WAVE visual-hardening path."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_live_port3000_immutable_npm_and_lighthouse_gate():
    script=(ROOT/"scripts/verify.sh").read_text(encoding="utf8")
    for needle in (
       "set -euo pipefail", "rm -rf -- node_modules .next dist", "npm ci", "npm run build",
       "npm run start", "127.0.0.1:3000",
       "HAZEWAVE_DOT_GIT_COUNT", "verify-brand-screenshots.mjs",
       "lighthouse@12.8.2", "s<=90", "HAZEWAVE_VERIFY=PASS"
    ):
        assert needle in script,needle

def test_real_three_screen_sizes_and_mandatory_brand_rank():
    script=(ROOT/"apps/hazewave-site/scripts/verify-brand-screenshots.mjs").read_text(encoding="utf8")
    for needle in ("[360,768,1280]", "page.screenshot",
                   "brandWidth>=3*observed.artistWidth",
                   "artistOpacity-.7", "pageerror"):
        assert needle in script,needle

def test_optimized_image_keeps_owner_original_and_css_art_direction():
    script=(ROOT/"apps/hazewave-site/scripts/optimize-hero.mjs").read_text(encoding="utf8")
    for needle in ("createHash", "1024,height:475",
                   "webp({quality:90,effort:6})",
                   "HAZEWAVE_MASTER_PRESERVED_AND_RESPONSIVE_WEBP=PASS"):
        assert needle in script,needle
    pkg=json.loads((ROOT/"apps/hazewave-site/package.json").read_text(encoding="utf8"))
    assert "node scripts/optimize-hero.mjs" in pkg["scripts"]["build"]
    assert pkg["scripts"]["start"]=="astro preview --host 127.0.0.1 --port 3000"
