"""WAVE ArtCraft seven-release external bridge. No installation or Harness authority.

Usage:
  python scripts/wave_artcraft_external_tools.py validate
  python scripts/wave_artcraft_external_tools.py extract TOOL ARCHIVE OUTPUT_DIR
  python scripts/wave_artcraft_external_tools.py smoke TOOL EXECUTABLE OUTPUT_DIR
  python scripts/wave_artcraft_external_tools.py verify TOOL OUTPUT_DIR

All executable smokes operate on ORIGINAL synthetic WAVE fixtures, never owner media.
The caller must isolate untrusted executables with --network none, read-only FS and
a bounded writable temporary mount. No app is installed into the site or A15.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tarfile
import zlib

# Do not duplicate routing authority: import only the project-owned Harness.
# Scripts run from /src/scripts in the isolated container without editable installs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hazewave.wave_artcraft import ArtCraftHarnessAdmission, admit_artcraft, verify_admission

LOCK = Path(__file__).with_name("wave_artcraft-seven-lock.json")
NAMES = frozenset({"photocraft", "lightcraft", "designcraft", "pdfcraft",
                   "vectorcraft", "effectcraft", "filmcraft"})
CAPABILITIES = {
    "photocraft": "IMAGE_LAYER_EDIT",
    "lightcraft": "IMAGE_COLOR_DEVELOP",
    "designcraft": "EDITORIAL_LAYOUT",
    "pdfcraft": "PDF_PREVIEW_QA",
    "vectorcraft": "SVG_INK_DRAW",
    "effectcraft": "MOTION_COMPOSITION",
    "filmcraft": "VIDEO_QC",
}
# Preserve existing three proven exact releases; no hidden upgrades.
EXISTING_PINS = {
    "vectorcraft": ("0.7.0", "d6b0ee57e1bdbd377b44c8524e8569ad2b4dff46b792fc10b0edbf8d74292acd"),
    "effectcraft": ("0.6.0", "71810719903378cdab32a1fe328f23c874d38cd3d833abb19c6263dd2bad218c"),
    "filmcraft": ("0.4.0", "841790ff6649f0d49daa4a8ade1cb18d948e5ca43d00771046663e06c8d8ce83"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_lock(data: object) -> dict[str, dict]:
    if not isinstance(data, dict) or set(data) != {
        "schema", "repo", "scope", "approval", "auto_install", "auto_activate", "tools"
    }:
        raise ValueError("ARTCRAFT_LOCK_KEYS_INVALID")
    if (data["schema"] != "HazewaveArtCraftSevenExternalLock/v1"
        or data["repo"] != "zenindiones-maker/Hazewave-"
        or data["scope"] != "WAVE_ONLY"
        or data["approval"] != "CANDIDATE_NOT_PUBLISHED"
        or data["auto_install"] is not False
        or data["auto_activate"] is not False):
        raise ValueError("ARTCRAFT_LOCK_AUTHORITY_ESCALATION")
    tools = data["tools"]
    if not isinstance(tools, dict) or set(tools) != NAMES:
        raise ValueError("ARTCRAFT_REQUIRED_SEVEN_MISSING")
    for name, tool in tools.items():
        if not isinstance(tool, dict) or set(tool) != {
            "repository", "version", "url", "asset", "sha256", "binary",
            "capability", "authority", "data_classification", "execution", "publication"
        }:
            raise ValueError("ARTCRAFT_TOOL_SCHEMA:" + name)
        if (tool["repository"] != "storytold/" + name
            or tool["binary"] != name + "-cli"
            or tool["capability"] != CAPABILITIES[name]
            or tool["authority"] != "NONE"
            or tool["data_classification"] != "PUBLIC"
            or tool["execution"] != "OFFLINE_ISOLATED"
            or tool["publication"] != "FORBIDDEN"):
            raise ValueError("ARTCRAFT_TOOL_AUTHORITY_OR_IDENTITY:" + name)
        version, asset, digest = tool["version"], tool["asset"], tool["sha256"]
        if (not isinstance(version, str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or not isinstance(asset, str)
            or asset not in (f"{name}-{version}-linux-x86_64.tar.gz",
                             f"{name}-cli-{version}-linux-x86_64.tar.gz")
            or (name != "pdfcraft" and asset.startswith(name + "-cli-"))
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or digest == "0" * 64
            or tool["url"] != f"https://github.com/storytold/{name}/releases/download/v{version}/{asset}"):
            raise ValueError("ARTCRAFT_UNPINNED_RELEASE:" + name)
        if name in EXISTING_PINS and (version, digest) != EXISTING_PINS[name]:
            raise ValueError("ARTCRAFT_PREVIOUSLY_PROVEN_VERSION_CHANGED:" + name)
    return tools


def extract_cli(archive: Path, dest: Path, name: str) -> Path:
    if name not in NAMES or archive.is_symlink() or not archive.is_file():
        raise ValueError("UNAUTHORIZED_ARTCRAFT_ARCHIVE")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("REFUSE_TO_OVERWRITE_EXISTING_TOOL")
    with tarfile.open(archive, "r:gz") as package:
        members = package.getmembers()
        if (len(members) > 1200 or
            sum(max(0, entry.size) for entry in members) > 900_000_000):
            raise ValueError("ARTCRAFT_ARCHIVE_RESOURCE_BUDGET")
        for entry in members:
            key = PurePosixPath(entry.name)
            if (key.is_absolute() or ".." in key.parts or not (entry.isfile() or entry.isdir())
                or entry.size < 0 or entry.size > 180_000_000):
                raise ValueError("ARTCRAFT_UNSAFE_ARCHIVE_ENTRY")
        choices = [entry for entry in members
                   if entry.isfile() and PurePosixPath(entry.name).name == name + "-cli"]
        if len(choices) != 1 or not 50_000 < choices[0].size < 180_000_000:
            raise ValueError("ARTCRAFT_EXACTLY_ONE_REAL_CLI_REQUIRED:" + name)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / (name + "-cli")
        with package.extractfile(choices[0]) as src, path.open("xb") as target:
            for block in iter(lambda: src.read(1024 * 1024), b""):
                target.write(block)
        path.chmod(0o500)
    return path


def small_png(path: Path) -> None:
    """Small deterministically painted original synthetic WAVE fixture, not owner art."""
    width, height = 160, 96
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend((int(20 + 175 * x / (width - 1)),
                         int(15 + 180 * y / (height - 1)),
                         180 if abs(y - (48 + 20 * __import__("math").sin(x / 24))) < 4 else 38))
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def run_one(args: list[str], root: Path, label: str) -> str:
    try:
        response = subprocess.run(args, cwd=root, timeout=110, capture_output=True, text=True,
                                  check=False, env=os.environ.copy())
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("ARTCRAFT_TOOL_NOT_EXECUTED:" + label) from error
    if response.returncode != 0:
        raise ValueError("ARTCRAFT_TOOL_FAILED:" + label + ":" +
                         (response.stderr or response.stdout)[-1700:])
    return response.stdout[:5000]


def verify_png(path: Path) -> None:
    if (not path.is_file() or path.stat().st_size < 100
        or path.stat().st_size > 12_000_000):
        raise ValueError("ARTCRAFT_IMAGE_MISSING_OR_TOO_LARGE")
    with path.open("rb") as inp:
        header = inp.read(24)
    if not header.startswith(b"\x89PNG\r\n\x1a\n") or header[12:16] != b"IHDR":
        raise ValueError("ARTCRAFT_OUTPUT_NOT_PNG")
    width, height = struct.unpack(">II", header[16:24])
    if not 2 <= width <= 6000 or not 2 <= height <= 6000:
        raise ValueError("ARTCRAFT_INVALID_IMAGE_DIMENSIONS")


def verify_pdf(path: Path) -> None:
    if not path.is_file() or not 100 < path.stat().st_size < 20_000_000:
        raise ValueError("ARTCRAFT_PDF_MISSING_OR_TOO_LARGE")
    if not path.open("rb").read(5) == b"%PDF-":
        raise ValueError("ARTCRAFT_OUTPUT_NOT_PDF")

def write_designcraft_provenance(root: Path, *, stage_id: str) -> Path:
    """Write an independent, explicit PDF producer receipt (not a bearer credential)."""
    admit_artcraft(task_id=stage_id, tool="designcraft",
                   data_classification="PUBLIC", requested_domain="WAVE")
    pdf = root / "designcraft-layout.pdf"
    if pdf.is_symlink():
        raise ValueError("DESIGNCRAFT_PDF_SYMLINK_FORBIDDEN")
    verify_pdf(pdf)
    receipt = root / "receipt.json"
    if receipt.exists() or receipt.is_symlink():
        raise ValueError("DESIGNCRAFT_RECEIPT_ALREADY_EXISTS")
    info = {
        "schema": "HazewaveDesignCraftProvenance/v1",
        "producer": "designcraft",
        "stage_id": stage_id,
        "artifact_hash": sha256(pdf),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_path": "designcraft-layout.pdf",
        "project": "zenindiones-maker/Hazewave-",
        "authority": "NONE",
    }
    receipt.write_text(json.dumps(info, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    return receipt


def verify_designcraft_provenance(root: Path, *, receipt: Path, stage_id: str) -> dict:
    """Hard fail BEFORE PdfCraft invocation on unbound receipt, path or digest."""
    expected = root / "receipt.json"
    if (root.is_symlink() or receipt.is_symlink() or not receipt.is_file()
        or receipt.resolve(strict=True) != expected.resolve(strict=False)):
        raise ValueError("PDFCRAFT_PROVENANCE_RECEIPT_REQUIRED_AT_BOUND_PATH")
    admit_artcraft(task_id=stage_id, tool="designcraft",
                   data_classification="PUBLIC", requested_domain="WAVE")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
        or set(data) != {"schema", "producer", "stage_id", "artifact_hash",
                          "timestamp", "source_path", "project", "authority"}
        or data["schema"] != "HazewaveDesignCraftProvenance/v1"
        or data["producer"] != "designcraft"
        or data["stage_id"] != stage_id
        or data["source_path"] != "designcraft-layout.pdf"
        or data["project"] != "zenindiones-maker/Hazewave-"
        or data["authority"] != "NONE"
        or not isinstance(data["artifact_hash"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", data["artifact_hash"])
        or not isinstance(data["timestamp"], str)
        or not re.fullmatch(r"\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\dZ", data["timestamp"])):
        raise ValueError("PDFCRAFT_DESIGNCRAFT_RECEIPT_INVALID")
    try:
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError("PDFCRAFT_PROVENANCE_TIME_INVALID") from err
    source = root / data["source_path"]
    if source.is_symlink():
        raise ValueError("PDFCRAFT_PROVENANCE_PDF_SYMLINK")
    verify_pdf(source)
    if sha256(source) != data["artifact_hash"]:
        raise ValueError("PDFCRAFT_PROVENANCE_HASH_MISMATCH")
    return data


def select_image_input(name: str, root: Path, *, upstream_task_id: str | None) -> Path:
    """PhotoCraft→LightCraft sequential handoff; never read an unverified artifact."""
    if name == "photocraft":
        if upstream_task_id is not None:
            raise ValueError("PHOTOCRAFT_MUST_BE_FIRST_STAGE")
        path = root / "hazewave-synthetic-signal.png"
        if not path.exists():
            small_png(path)
    elif name == "lightcraft":
        if upstream_task_id is None:
            raise ValueError("LIGHTCRAFT_PREVIOUS_TASK_ID_REQUIRED")
        verify("photocraft", root, task_id=upstream_task_id)
        path = root / "photocraft-render.png"
    else:
        raise ValueError("ARTCRAFT_CROSS_STAGE_TYPE_INVALID")
    verify_png(path)
    return path


def smoke(name: str, executable: Path, root: Path, *, task_id: str,
          upstream_task_id: str | None = None,
          provenance_receipt: Path | None = None,
          provenance_id: str | None = None) -> Path:
    if name not in {"photocraft", "lightcraft", "designcraft", "pdfcraft"}:
        raise ValueError("SMOKE_ONLY_NEW_FOUR")
    admission = admit_artcraft(task_id=task_id, tool=name,
                               data_classification="PUBLIC", requested_domain="WAVE")
    verify_admission(admission, expected_tool=name, expected_task_id=task_id)
    if executable.name != name + "-cli" or not executable.is_file():
        raise ValueError("ARTCRAFT_EXACT_EXECUTABLE_REQUIRED")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("ARTCRAFT_WORKDIR_MUST_EXIST")
    if name in {"photocraft", "lightcraft"}:
        input_png = select_image_input(name, root,
                                       upstream_task_id=upstream_task_id)
    elif name == "pdfcraft":
        if upstream_task_id is None:
            raise ValueError("PDFCRAFT_DESIGNCRAFT_TASK_REQUIRED")
        if provenance_receipt is None or provenance_id is None:
            raise ValueError("PDFCRAFT_PROVENANCE_FLAGS_REQUIRED")
        if provenance_id != upstream_task_id:
            raise ValueError("PDFCRAFT_PROVENANCE_ID_MISMATCH")
        verify("designcraft", root, task_id=upstream_task_id)
        verify_designcraft_provenance(
            root, receipt=provenance_receipt, stage_id=provenance_id
        )
        input_png = root / "designcraft-layout.pdf"
        verify_pdf(input_png)
    else:
        if upstream_task_id is not None:
            raise ValueError("DESIGNCRAFT_MUST_PRECEDE_PDFCRAFT")
        input_png = root / "hazewave-synthetic-signal.png"
        if not input_png.exists():
            small_png(input_png)
        verify_png(input_png)
    target = root / (name + "-render.png")
    if name == "photocraft":
        run_one([str(executable), "run", str(input_png), "--cmd",
                 "image.adjustments.invert", "--out", str(target)], root, name)
    elif name == "lightcraft":
        run_one([str(executable), "render", str(input_png), "-o", str(target),
                 "--set", "light.exposure=0.5"], root, name)
    elif name == "designcraft":
        target = root / "designcraft-layout.pdf"
        run_one([str(executable), "run", "--sample", "--export", str(target)], root, name)
    else:
        source = root / "designcraft-layout.pdf"
        verify_pdf(source)
        details = run_one([str(executable), "info", str(source)], root, name + "-info")
        if "page" not in details.lower():
            raise ValueError("PDFCRAFT_NO_DOCUMENT_INSPECTION")
        run_one([str(executable), "render", str(source), "--page", "1",
                 "--dpi", "72", "--out", str(target)], root, name + "-render")
    if name == "designcraft":
        verify_pdf(target)
    else:
        verify_png(target)
    if name in {"photocraft", "lightcraft"} and sha256(target) == sha256(input_png):
        raise ValueError("ARTCRAFT_EXPECTED_PIXEL_CHANGE_MISSING")
    if name == "designcraft":
        write_designcraft_provenance(root, stage_id=task_id)
    receipt = {
        "schema": "HazewaveArtCraftExternalRealSmoke/v1",
        "project": "zenindiones-maker/Hazewave-",
        "tool": name,
        "authority": "NONE",
        "source": "SYNTHETIC_FIRST_PARTY_ONLY",
        "owner_private_media_used": False,
        "production_approved": False,
        "publication_attempted": False,
        "executable_sha256": sha256(executable),
        "output": target.name,
        "output_sha256": sha256(target),
        "real_execution": True,
        "admission": admission.__dict__,
        "input": input_png.name,
        "input_sha256": sha256(input_png),
        "upstream_task_id": upstream_task_id,
    }
    receipt_file = root / (name + "-receipt.json")
    receipt_file.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_file


def verify(name: str, root: Path, *, task_id: str,
           upstream_task_id: str | None = None,
           provenance_receipt: Path | None = None,
           provenance_id: str | None = None) -> None:
    data = json.loads((root / (name + "-receipt.json")).read_text())
    if (data.get("schema") != "HazewaveArtCraftExternalRealSmoke/v1"
        or data.get("tool") != name or data.get("authority") != "NONE"
        or data.get("real_execution") is not True
        or data.get("source") != "SYNTHETIC_FIRST_PARTY_ONLY"
        or data.get("owner_private_media_used") is not False
        or data.get("production_approved") is not False
        or data.get("publication_attempted") is not False):
        raise ValueError("ARTCRAFT_SMOKE_RECEIPT_INCOMPATIBLE")
    # Admission IDs are correlation evidence only, not cryptographic capabilities.
    # The isolated workflow identity and sandbox still enforce the actual boundary.
    observed_admission = data.get("admission")
    expected_admission = admit_artcraft(task_id=task_id, tool=name,
                                       data_classification="PUBLIC",
                                       requested_domain="WAVE")
    if observed_admission != expected_admission.__dict__:
        raise ValueError("ARTCRAFT_RECEIPT_HARNESS_ROUTE_INVALID")
    verify_admission(expected_admission, expected_tool=name, expected_task_id=task_id)
    if data.get("upstream_task_id") != upstream_task_id:
        raise ValueError("ARTCRAFT_UPSTREAM_TASK_MISMATCH")
    if name in {"photocraft", "lightcraft"}:
        if name == "lightcraft":
            if upstream_task_id is None:
                raise ValueError("LIGHTCRAFT_PREVIOUS_TASK_ID_REQUIRED")
            verify("photocraft", root, task_id=upstream_task_id)
            expected_input = "photocraft-render.png"
        else:
            if upstream_task_id is not None:
                raise ValueError("PHOTOCRAFT_MUST_BE_FIRST_STAGE")
            expected_input = "hazewave-synthetic-signal.png"
        if data.get("input") != expected_input or sha256(root / expected_input) != data.get("input_sha256"):
            raise ValueError("ARTCRAFT_IMAGE_SOURCE_HASH_DRIFT")
    elif name == "pdfcraft":
        if upstream_task_id is None:
            raise ValueError("PDFCRAFT_DESIGNCRAFT_TASK_REQUIRED")
        if provenance_receipt is None or provenance_id != upstream_task_id:
            raise ValueError("PDFCRAFT_PROVENANCE_FLAGS_REQUIRED_OR_ID_MISMATCH")
        verify("designcraft", root, task_id=upstream_task_id)
        verify_designcraft_provenance(
            root, receipt=provenance_receipt, stage_id=provenance_id
        )
        if (data.get("input") != "designcraft-layout.pdf"
            or sha256(root / "designcraft-layout.pdf") != data.get("input_sha256")):
            raise ValueError("PDFCRAFT_LAYOUT_PROVENANCE_DRIFT")
    elif name == "designcraft":
        verify_designcraft_provenance(
            root, receipt=root / "receipt.json", stage_id=task_id
        )
        if upstream_task_id is not None:
            raise ValueError("DESIGNCRAFT_MUST_PRECEDE_PDFCRAFT")
        if (data.get("input") != "hazewave-synthetic-signal.png"
            or sha256(root / "hazewave-synthetic-signal.png") != data.get("input_sha256")):
            raise ValueError("DESIGNCRAFT_LAYOUT_SOURCE_DRIFT")
    else:
        raise ValueError("ARTCRAFT_UNSUPPORTED_VERIFICATION")
    expected_outputs = {
        "photocraft": "photocraft-render.png",
        "lightcraft": "lightcraft-render.png",
        "designcraft": "designcraft-layout.pdf",
        "pdfcraft": "pdfcraft-render.png",
    }
    if data.get("output") != expected_outputs.get(name):
        raise ValueError("ARTCRAFT_OUTPUT_FILE_IDENTITY_MISMATCH")
    path = root / expected_outputs[name]
    if root.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("ARTCRAFT_OUTPUT_UNSAFE_PATH")
    if sha256(path) != data["output_sha256"]:
        raise ValueError("ARTCRAFT_OUTPUT_HASH_DRIFT")
    verify_pdf(path) if name == "designcraft" else verify_png(path)


def main() -> None:
    cli = argparse.ArgumentParser()
    sub = cli.add_subparsers(dest="action", required=True)
    sub.add_parser("validate")
    admission = sub.add_parser("admit")
    admission.add_argument("name", choices=sorted(NAMES))
    admission.add_argument("--task-id", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("name", choices=sorted(NAMES))
    ex.add_argument("archive", type=Path)
    ex.add_argument("output", type=Path)
    for action in ("smoke", "verify"):
        p = sub.add_parser(action)
        p.add_argument("name", choices=sorted(NAMES))
        p.add_argument("--task-id", required=True)
        p.add_argument("--upstream-task-id")
        p.add_argument("--provenance-receipt", type=Path)
        p.add_argument("--provenance-id")
        if action == "smoke":
            p.add_argument("executable", type=Path)
        p.add_argument("output", type=Path)
    args = cli.parse_args()
    entries = validate_lock(json.loads(LOCK.read_text()))
    if args.action == "validate":
        print("HAZEWAVE_ARTCRAFT_SEVEN_LOCK=PASS")
    elif args.action == "admit":
        admitted = admit_artcraft(task_id=args.task_id, tool=args.name,
                                  data_classification="PUBLIC",
                                  requested_domain="WAVE")
        verify_admission(admitted, expected_tool=args.name,
                         expected_task_id=args.task_id)
        # The ID is a non-secret correlation hash; no privileged token issued.
        print("HAZEWAVE_ARTCRAFT_HARNESS_WAVE_ADMISSION=PASS:" + args.name)
        print("HAZEWAVE_ARTCRAFT_BOUND_CAPABILITY=" + admitted.capability_id)
    elif args.action == "extract":
        tool = entries[args.name]
        if sha256(args.archive) != tool["sha256"]:
            raise ValueError("ARTCRAFT_RELEASE_SHA256_MISMATCH")
        extracted = extract_cli(args.archive, args.output, args.name)
        print("ARTCRAFT_EXACT_CLI=" + str(extracted))
    elif args.action == "smoke":
        print("ARTCRAFT_SMOKE_RECEIPT=" + str(smoke(args.name, args.executable, args.output,
                                                           task_id=args.task_id,
                                                           upstream_task_id=args.upstream_task_id,
                                                           provenance_receipt=args.provenance_receipt,
                                                           provenance_id=args.provenance_id)))
    elif args.action == "verify":
        verify(args.name, args.output, task_id=args.task_id,
               upstream_task_id=args.upstream_task_id,
               provenance_receipt=args.provenance_receipt,
               provenance_id=args.provenance_id)
        print("ARTCRAFT_REAL_OUTPUT_VERIFIED=" + args.name)


if __name__ == "__main__":
    main()
