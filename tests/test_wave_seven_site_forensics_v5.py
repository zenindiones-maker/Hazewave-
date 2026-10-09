"""Seven-site research evidence is bounded, not external browser attestation."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"knowledge/wave-seven-site-forensics-v5.json"
ENGINE=ROOT/"apps/hazewave-site/experiments/travessia-v4"


def test_evidence_categories_and_source_rights_are_honest():
    data=json.loads(LEDGER.read_text(encoding="utf8"))
    assert data["schema"]=="HazewaveSevenPublicSitesReverseEngineeringEvidence/v1"
    assert data["source_count"]==len(data["sources"])==7
    assert data["harness"]=="HAZEWAVE_HARNESS"
    assert data["authority"]=="NONE"
    assert data["live_external_browser_used"] is False
    assert data["approved_for_site_copying"] is False
    assert data["production_approved"] is False
    assert {s["id"] for s in data["sources"]}=={
        "nasa-prospect","ponpon-mania","sbs-the-boat",
        "nyt-tomato-can-blues","who-is-guilty","genie-studio-app","esimple",
    }
    for source in data["sources"]:
        assert source["external_live_browser_inspected"] is False
        assert source["external_artwork_reused"] is False
        assert source["external_proprietary_code_reused"] is False
        assert source["production_authorized"] is False
        assert source["observed_public_mechanism"]
        assert source["hazewave_transfer"]
        for key in ["official","source_url",*("evidence_urls",)]:
            urls=source[key] if key=="evidence_urls" else [source[key]]
            for url in urls:
                parsed=urlsplit(url)
                assert parsed.scheme=="https" and parsed.hostname
                assert not parsed.username and not parsed.password
    nasa=next(s for s in data["sources"] if s["id"]=="nasa-prospect")
    assert nasa["license"]=="MIT"
    assert nasa["source_class"]=="OPEN_MIT_LICENSE_REPOSITORY_DIRECT_CODE_INSPECTION"
    assert nasa["verified_sha1_blobs"]=={
        "navigator":"e3479a31ad7b3ea5f249252116361f8965f4ee91",
        "section":"6981d4e9d5b52540f45a54422b1fae533fe3c2f0",
        "main":"e6e436ef887a67efd27453a46cfde01874074f7f",
    }


def test_real_five_act_nav_quality_are_in_v4_engine_not_an_unbound_plan():
    index=(ENGINE/"index.html").read_text()
    js=(ENGINE/"travessia.js").read_text()
    css=(ENGINE/"travessia.css").read_text()
    assert index.count('data-world-stop=')==5
    assert 'id="chapter-nav"' in index
    assert 'id="lightweight-mode"' in index
    assert "Object.freeze([0,.25,.47,.70,.92])" in js
    for required in (
        "setupChapterNavigation()","function gotoAct(index)",
        "requestAnimationFrame((ts)=>","observeFrameBudget(ts)",
        "aria-current","phase","window.__HAZEWAVE_RESEARCH_V5",
        "visualQualityTier","qualityDowngradeAutomatic",
        "state.productionApproved=false",
    ):
        assert required in js,required
    assert '[data-quality="lite"]' in css
    assert '.chapter-nav button:focus-visible' in css
    assert 'drop-shadow' in css
    assert 'portalRadiusPct' in js and 'mechanicalSplitPx' in js
    assert "window.__HAZEWAVE_TRAVERSAL_V4" in js
    # Original canvas illustrations and 24 painted moving pieces remain owner art.
    assert "counts.pad!==12||counts.knob!==8||counts.speaker!==4" in js
    assert "asset-manifest.json" in js


def test_no_proprietary_site_js_import_or_private_media_committed():
    index=(ENGINE/"index.html").read_text()
    js=(ENGINE/"travessia.js").read_text()
    for item in ("ponpon-mania.com","nasaprospect.com","whoisguilty.com",
                 "sbs.com.au","nytimes.com","geniestudio.app","esimple.it"):
        assert item not in index+js
    for path in ENGINE.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in {".png",".jpg",".jpeg",".webp",
                                               ".mp4",".webm",".woff",".woff2"}
