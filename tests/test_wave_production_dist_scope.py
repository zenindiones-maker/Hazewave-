"""Reject unauthorized prototype routes, vendor bundles and media in WAVE production."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_production_build_is_a_strict_approved_only_distribution():
    guard=(ROOT/"apps/hazewave-site/scripts/enforce-indionesbala-only.mjs").read_text(encoding="utf8")
    for contract in (
      'HAZEWAVE_TEST_EXPERIMENTS !== "1"',
      'rm(join(dist,"living-universe-p0")',
      'rm(join(dist,"experimental")',
      'UNAPPROVED_STATIC_ROUTE_OR_MEDIA',
      'APPROVED_OUTPUT_MISSING',
      'PRODUCTION_DIST_ONLY_HAZEWAVE_AND_INDIONESBALA=PASS',
      'TEMPORARY_EXPERIMENT_QA_BUILD_NOT_FOR_DELIVERY=TRUE'
    ):
      assert contract in guard,contract

def test_single_command_retains_real_prototype_qa_then_proves_final_clean_site():
    source=(ROOT/"scripts/run_hazewave_site.sh").read_text(encoding="utf8")
    assert source.count("npm run build") == 2
    assert "HAZEWAVE_TEST_EXPERIMENTS=1 npm run build" in source
    assert 'CI=true npm test -- tests/cosmic-journey.spec.ts' in source
    assert source.index("HAZEWAVE_SITE_STAGE=APPROVED_PRODUCTION_BUILD")>source.index("HAZEWAVE_SITE_EXPERIMENTAL_QA=PASS")
    assert "HAZEWAVE_SITE_PRODUCTION_SCOPE=PASS" in source

def test_bundle_budget_requires_no_p0_js_in_production():
    source=(ROOT/"apps/hazewave-site/scripts/check-bundle-budget.mjs").read_text(encoding="utf8")
    assert "EXPERIMENTAL_P0_NOT_SHIPPED=PASS" in source
    assert "EXPERIMENTAL_P0_CHUNKS_NOT_ISOLATED" not in source
    assert "EXPERIMENTAL_P0_LARGEST_CHUNK_BUDGET_EXCEEDED" in source

def test_final_artist_image_extension_matches_jpeg_magic_preserving_owner_bytes():
    guard=(ROOT/"apps/hazewave-site/scripts/enforce-indionesbala-only.mjs").read_text(encoding="utf8")
    page=(ROOT/"apps/hazewave-site/src/pages/index.astro").read_text(encoding="utf8")
    verifier=(ROOT/"apps/hazewave-site/scripts/verify-owner-art.mjs").read_text(encoding="utf8")
    assert "OWNER_INDIONESBALA_JPEG_SIGNATURE_UNEXPECTED" in guard
    assert "await rename(oldFormat,correctFormat)" in guard
    assert "INDIONESBALA_PUBLIC_MIME=image/jpeg" in guard
    assert "/media/artists/indionesbala.jpg" in page
    assert 'media/artists/indionesbala.jpg' in verifier
