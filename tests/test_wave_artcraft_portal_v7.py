"""Hazewave V7 contract tests, NOT real upstream tool execution.

Genuine native tool execution and media verification occur exclusively in the
pinned EffectCraft+FilmCraft Actions job. These are negative local gate tests.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import struct
import zlib
from hashlib import sha256
import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "apps/hazewave-site/experiments/travessia-v4"
SCRIPT = BASE / "artcraft_portal_pipeline.py"
spec = importlib.util.spec_from_file_location("wave_effectfilm", SCRIPT)
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def _synthetic_png(seed):
    # Test-only fixture: never claim this output came from an ArtCraft CLI.
    w, h = tool.CANVAS
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    raw = b"".join(b"\0" + bytes([seed, 31, 191, 255]) * w for _ in range(h))
    return (tool.PNG_MAGIC + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b""))


def test_output_dimensions_and_types_are_fail_closed(tmp_path):
    p = tmp_path / "raster.png"
    p.write_bytes(_synthetic_png(37))
    r = tool.checked_png(p)
    assert (r["width"], r["height"]) == (420, 820)
    assert r["alpha_channel"] is True
    p.write_bytes(b"this is not a png")
    with pytest.raises(ValueError, match="INVALID_PNG"):
        tool.checked_png(p)


def test_missing_actual_clis_never_create_output(tmp_path):
    outfile = tmp_path / "private_fx"
    fake = tmp_path / "not-a-real-cli"
    fake.write_bytes(b"test-double-only")
    with pytest.raises(ValueError, match="BINARY_SHA_MISMATCH"):
        tool.build(output=outfile, effect_cli=fake, film_cli=fake,
                   effect_sha="a"*64, film_sha="b"*64)
    assert not outfile.exists()


def test_fake_or_tampered_art_receipts_are_denied(tmp_path):
    place = tmp_path / "proof"
    place.mkdir()
    (place / "effectcraft-filmcraft-proof.json").write_text(json.dumps({
        "schema": tool.SCHEMA, "owner_repository": "another-project",
        "production_approved": False, "real_effectcraft_render": True,
    }))
    with pytest.raises(ValueError, match="FX_PROVENANCE_MISSING"):
        tool.verify(place)
    receipt = json.loads((place / "effectcraft-filmcraft-proof.json").read_text())
    receipt["owner_repository"] = tool.FIRST_PARTY_PROJECT
    receipt["production_approved"] = True
    (place / "effectcraft-filmcraft-proof.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="UNAUTHORIZED_CLAIMS"):
        tool.verify(place)


def test_source_is_scoped_to_hazewave_and_optional_private_artwork():
    js = (BASE / "travessia.js").read_text()
    css = (BASE / "travessia.css").read_text()
    html = (BASE / "index.html").read_text()
    standalone = (BASE / "build_standalone.py").read_text()
    private_astro = (BASE / "integrate_private_astro.py").read_text()
    assert 'id="effectcraft-aperture"' in html
    assert 'renderArtcraftEffect(p)' in js
    assert "fxSpec.production_approved!==false" in js
    assert "filmcraft_probe_executed!==true" in js
    assert "reduced-motion: reduce" in js
    assert 'data-quality="lite"] #effectcraft-aperture' in css
    assert "--effectcraft-proof" in standalone
    assert "--effectcraft-proof" in private_astro
    assert "verify_effectcraft" in standalone
    assert "verify_effectcraft" in private_astro
    assert "BR-no-GTA" not in js
    assert "filmcraft" in SCRIPT.read_text()
    assert "effectcraft" in SCRIPT.read_text()
    assert not any(BASE.rglob("sonic-portal-*.png"))
    assert not any(BASE.rglob("effectcraft-reference.webm"))


def test_first_party_tool_chain_is_one_sha_pinned_per_upstream():
    assert tool.RELEASE_ARCHIVES == {
        "effectcraft": "71810719903378cdab32a1fe328f23c874d38cd3d833abb19c6263dd2bad218c",
        "filmcraft": "841790ff6649f0d49daa4a8ade1cb18d948e5ca43d00771046663e06c8d8ce83",
    }
    assert len(tool.FRAME_TIMES) == 8
    assert tool.FRAME_TIMES[0] == 0
    assert tool.FRAME_TIMES[-1] == .875


def test_real_artcraft_private_site_composer_makes_media_parent_before_frames():
    composer = (BASE / "integrate_private_astro.py").read_text()
    parent = "target=entry/'assets';target.mkdir(mode=0o700)"
    child = "fx_out.mkdir(mode=0o700,parents=True)"
    assert parent in composer and child in composer
    assert composer.index(parent) < composer.index(child)
    assert "from artcraft_portal_pipeline import verify" in composer
