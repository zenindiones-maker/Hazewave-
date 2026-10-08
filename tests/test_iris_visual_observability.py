from __future__ import annotations

import base64

import hashlib
from pathlib import Path
import struct
import zlib
import subprocess

import pytest

from hazewave.iris_capture import IrisCaptureError, iris_capture_policy, verify_iris_capture

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "codespaces" / "install-iris-open-tool.sh"
FIXTURE = ROOT / "tests" / "fixtures" / "iris-proof.html"
SOURCE_REPO = "brijr/iris"
VERSION = "0.4.1"
RELEASE_SHA256 = "aa6073ba255c0bcf09364a5503cbd4794791b832e5934a52b169a455d66101c7"


def test_upstream_iris_installer_is_exactly_versioned_and_digest_bound() -> None:
    s = INSTALLER.read_text(encoding="utf-8")
    assert "v0.4.1" in s
    assert RELEASE_SHA256 in s
    assert "iris-x86_64-unknown-linux-musl.tar.gz" in s
    assert "sha256sum -c" in s
    assert "curl -fsSL" in s
    assert "curl | sh" not in s
    assert '"$ROOT/v0.4.1/bin/iris"' in s
    assert "gh codespace create" not in s
    assert "hazewave-reflex serve-stop" not in s
    assert "sudo " not in s


def test_upstream_iris_is_opt_in_and_codespace_scoped() -> None:
    s = INSTALLER.read_text(encoding="utf-8")
    for flag in ("--preflight", "--install", "--doctor", "--smoke"):
        assert flag in s
    assert "hazewave-zero-cost-4jxp45676rq6279xx" in s
    assert '"--install"' in s
    assert "IRIS_CODESPACE_INSTALL=NOT_ATTEMPTED" in s
    result = subprocess.run(["bash", "-n", str(INSTALLER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_iris_fixture_is_owned_and_has_stable_selector() -> None:
    s = FIXTURE.read_text(encoding="utf-8")
    assert 'id="hazewave-iris-proof"' in s
    assert "<script" not in s
    assert "https://" not in s


def test_iris_policy_accepts_only_first_party_fixture_by_default() -> None:
    allowed = iris_capture_policy(FIXTURE.as_uri(), workspace=ROOT)
    assert allowed == FIXTURE.as_uri()
    with pytest.raises(IrisCaptureError, match="IRIS_TARGET_NOT_ADMITTED"):
        iris_capture_policy("https://example.com", workspace=ROOT)
    with pytest.raises(IrisCaptureError, match="IRIS_TARGET_NOT_ADMITTED"):
        iris_capture_policy("/etc/passwd", workspace=ROOT)
    with pytest.raises(IrisCaptureError, match="IRIS_TARGET_NOT_ADMITTED"):
        iris_capture_policy("file:///etc/passwd", workspace=ROOT)


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",
    "http://127.0.0.1:28080/",
    "https://github.com/",
    "http://localhost:9000/@private",
    "http://user:pass@127.0.0.1:3000/",
])
def test_iris_policy_blocks_arbitrary_urls(url: str) -> None:
    with pytest.raises(IrisCaptureError, match="IRIS_TARGET_NOT_ADMITTED"):
        iris_capture_policy(url, workspace=ROOT)


def test_iris_policy_requires_exact_explicit_preview_origin() -> None:
    allowed = iris_capture_policy(
        "http://127.0.0.1:3000/artists",
        workspace=ROOT,
        admitted_preview_origin="http://127.0.0.1:3000",
    )
    assert allowed == "http://127.0.0.1:3000/artists"
    with pytest.raises(IrisCaptureError, match="IRIS_TARGET_NOT_ADMITTED"):
        iris_capture_policy(
            "http://127.0.0.1:3001/",
            workspace=ROOT,
            admitted_preview_origin="http://127.0.0.1:3000",
        )


def _valid_png() -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", crc)
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes.fromhex("0022aaee"))
    return bytes.fromhex("89504e470d0a1a0a") + chunk(b"IHDR", header) + chunk(b"IDAT", pixel) + chunk(b"IEND", b"")


def test_iris_receipt_does_not_promote_mcp_or_human_approval(tmp_path: Path) -> None:
    png = tmp_path / "iris.png"
    png.write_bytes(_valid_png())
    result = verify_iris_capture(
        {
            "status": "ok", "url": FIXTURE.as_uri(), "format": "png",
            "bytes": png.stat().st_size, "css_width": 140, "css_height": 30,
        },
        output=png,
        source_url=FIXTURE.as_uri(),
    )
    assert result["status"] == "CAPTURE_FILE_VERIFIED"
    assert result["image_sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert result["mcp_connected"] is False
    assert result["harness_live_route_proven"] is False
    assert result["production_approved"] is False


def test_iris_capture_rejects_mismatched_json_path_status(tmp_path: Path) -> None:
    png = tmp_path / "iris.png"
    png.write_bytes(_valid_png())
    with pytest.raises(IrisCaptureError):
        verify_iris_capture({"status": "error"}, output=png, source_url=FIXTURE.as_uri())


def test_mcp_fixture_invocation_is_explicit_and_never_registers_globally() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "--mcp-smoke" in installer
    assert "hazewave.iris_mcp_fixture_probe" in installer
    assert "IRIS_MCP_PROCESS_FIXTURE=PASS" in installer
    assert "IRIS_OWNER_AGENT_CONNECTED=NOT_PROVEN" in installer
    assert "codex mcp add" not in installer
    assert "iris mcp --help" not in installer
