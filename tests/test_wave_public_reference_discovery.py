"""Reference discovery has no authority to browse, copy art or promote tools."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

REGISTRY=Path(__file__).resolve().parents[1]/"knowledge/wave-reference-source-registry-v1.json"
EXPECTED_IDS={"nasa-prospect","nyt-tomato-can-blues","who-is-guilty",
              "ponpon-mania","genie-studio-app","esimple-3d","sbs-the-boat"}


def test_references_cover_exact_seven_with_clearly_limited_claims():
    data=json.loads(REGISTRY.read_text())
    assert data["schema"]=="HazewaveWavePublicReferenceDiscovery/v1"
    assert data["authority"]=="NONE"
    assert data["harness_authority"]=="HAZEWAVE_HARNESS"
    assert data["browser_observation_proven"] is False
    assert data["external_reverse_engineering_performed"] is False
    assert data["production_approved"] is False
    assert len(data["references"])==7
    assert {x["id"] for x in data["references"]}==EXPECTED_IDS
    for ref in data["references"]:
        assert ref["status"] in {"PUBLIC_TEXT_ONLY","HISTORICAL_SOURCE_UNVERIFIED"}
        assert ref["live_browser_scroll_observed"] is False
        assert ref["script_or_illustration_copied"] is False
        assert ref["rights"]=="NO_UNLICENSED_ASSET_OR_SOURCE_REUSE"
        assert ref["owner_signed_target_grant"] is False
        assert not ref["mechanisms_proven_by_our_browser"]
        assert ref["public_technique_hypotheses"]
        assert ref["source_urls"]
        for u in [ref["url"],*ref["source_urls"]]:
            p=urlparse(u)
            assert p.scheme=="https" and p.hostname
            assert p.username is None and p.password is None
            assert not p.fragment
        assert ref["evidence_basis"] in {"SITE_PUBLIC_PAGE",
                                         "CREATOR_TECHNICAL_WRITEUP",
                                         "EDITORIAL_SECONDARY_REFERENCE",
                                         "HISTORICAL_SOURCE_CITATION"}


def test_no_embedded_privilege_in_reference_registry():
    data=json.loads(REGISTRY.read_text())
    forbidden={"mcp_server","api_key","browser_arguments","cookie","token",
               "shell_command","approve","download_assets","crawl","execute"}
    for ref in data["references"]:
        assert not forbidden.intersection(ref)
    assert data["knowledge_use"]=="INFORMATIONAL_ONLY"
    assert data["approved_for_visual_reproduction"] is False
