"""HAZEWAVE-only external tool adapter tests: never claim fake CLI is ArtCraft."""
from __future__ import annotations
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import zlib
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "apps/hazewave-site/experiments/travessia-v4/artcraft_vector_bridge.py"
spec = importlib.util.spec_from_file_location("wave_artcraft_vector_bridge", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def _fixture_png() -> bytes:
    # Transparent 420x820 8-bit RGBA: only a deterministic test fixture,
    # NEVER an output from VectorCraft or owner creative proof.
    ihdr = struct.pack(">IIBBBBB", 420, 820, 8, 6, 0, 0, 0)
    data = b"".join(b"\0" + b"\0" * (420 * 4) for _ in range(820))
    return (mod.PNG_SIGNATURE + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(data))
            + _chunk(b"IEND", b""))


def _fake_executable(tmp_path: Path, png: Path, *, actually_write=True) -> Path:
    script = tmp_path / "vectorcraft-test-double"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "assert len(sys.argv) == 4 and sys.argv[1]=='convert'\n"
        + (f"Path(sys.argv[3]).write_bytes(Path({str(png)!r}).read_bytes())\n"
           if actually_write else "pass\n")
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_first_party_signal_extracted_from_real_hazewave_page(tmp_path):
    data, html_sha = mod.source_svg(SCRIPT.parent / "index.html")
    assert data.startswith(b'<svg xmlns="http://www.w3.org/2000/svg"')
    assert b'd="' in data
    assert b"stroke=" in data
    assert len(html_sha) == 64
    output = tmp_path / "private"
    manifest = mod.prepare(SCRIPT.parent / "index.html", output)
    assert manifest["tool_executed"] is False
    assert manifest["production_approved"] is False
    assert manifest["project"] == "zenindiones-maker/Hazewave-"
    assert manifest["first_party_svg_sha256"] == sha256(data).hexdigest()
    assert (output / "wave-signal-source.svg").read_bytes() == data
    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_FRESH"):
        mod.prepare(SCRIPT.parent / "index.html", output)


def test_sha_bound_binary_and_png_validation_with_test_double_only(tmp_path):
    output = tmp_path / "private"
    mod.prepare(SCRIPT.parent / "index.html", output)
    fixture = tmp_path / "test-only.png"
    fixture.write_bytes(_fixture_png())
    fake = _fake_executable(tmp_path, fixture)
    binary_sha = sha256(fake.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="BINARY_HASH_DRIFT"):
        mod.render(output, fake, "a" * 64)
    receipt = mod.render(output, fake, binary_sha)
    assert receipt["tool_executed"] is True
    assert receipt["output_png_sha256"] == sha256(fixture.read_bytes()).hexdigest()
    assert receipt["production_approved"] is False
    with pytest.raises(ValueError, match="WRONG_BRIDGE_RECEIPT_OR_REPLAY"):
        mod.render(output, fake, binary_sha)


def test_no_output_fake_cli_fails_closed(tmp_path):
    output = tmp_path / "private"
    mod.prepare(SCRIPT.parent / "index.html", output)
    fixture = tmp_path / "test.png"
    fixture.write_bytes(_fixture_png())
    fake = _fake_executable(tmp_path, fixture, actually_write=False)
    with pytest.raises(ValueError, match="VECTORCRAFT_PNG_NOT_GENERATED"):
        mod.render(output, fake, sha256(fake.read_bytes()).hexdigest())
    assert json.loads((output / "proof.json").read_text())["tool_executed"] is False


def test_reject_binary_and_image_spoofing(tmp_path):
    bad = tmp_path / "fake.png"
    bad.write_bytes(mod.PNG_SIGNATURE + b"\0" * 400)
    with pytest.raises(ValueError, match="WRONG_CANVAS_SIZE"):
        mod.validate_png(bad)
    bad.write_bytes(b"not a png")
    with pytest.raises(ValueError, match="OUTPUT_NOT_PNG"):
        mod.validate_png(bad)


def test_external_apps_never_change_website_or_user_art_sources():
    source = SCRIPT.read_text()
    assert "storytold/vectorcraft" in source
    assert "BR-no-GTA" not in source
    assert "os.system(" not in source
    assert "shell=True" not in source
    assert "git push" not in source
    assert "npm install" not in source
    assert "production_approved" in source
    assert not (SCRIPT.parent / "assets" / "wave-signal-vectorcraft.png").exists()
