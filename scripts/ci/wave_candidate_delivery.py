"""Deterministic WAVE V4 source-only CD artifact; never deploy private owner media.

Only immutable Git HEAD blobs are deliverable. This script neither connects to
Codespaces nor accesses network resources, tokens, publication or private files.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PROJECT = "apps/hazewave-site/experiments/travessia-v4"
FILES = tuple(
    f"{PROJECT}/{name}" for name in (
        "index.html",
        "travessia.css",
        "travessia.js",
        "build_assets.py",
        "build_standalone.py",
        "browser_verify_manual.py",
        "integrate_private_astro.py",
        "README.md",
    )
) + ("tests/test_wave_v4_traversal_sources.py",
     "tests/test_wave_seven_site_forensics_v5.py",
     "knowledge/wave-seven-site-forensics-v5.json",
     "docs/research/WAVE_SEVEN_SITES_REVERSE_ENGINEERING_V5.md",
     "apps/hazewave-site/tests/wave-v4-seven-site-technique-regression.spec.ts",
     "apps/hazewave-site/experiments/travessia-v4/artcraft_vector_bridge.py",
     "tests/test_wave_artcraft_vector_bridge.py",
     "docs/research/WAVE_ARTCRAFT_EXTERNAL_TOOL_BOUNDARY_V6.md",
     ".github/workflows/wave-vectorcraft-real-cli-proof.yml")
SCHEMA = "HazewaveWaveSourceOnlyDelivery/v1"
RECEIPT_SCHEMA = "HazewaveWaveSourceOnlyDeliveryReceipt/v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES_PER_FILE = 300_000
MAX_ARCHIVE_BYTES = 3_000_000
MAX_MANIFEST_BYTES = 30_000


class DeliveryDenied(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeliveryDenied(message)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, check=False, timeout=15,
    )
    require(result.returncode == 0, "GIT_SOURCE_UNVERIFIED")
    return result.stdout


def _head(root: Path) -> tuple[str, str]:
    head = _git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    tree = _git(root, "rev-parse", "--verify", "HEAD^{tree}").decode().strip()
    require(bool(SHA.fullmatch(head)) and bool(SHA.fullmatch(tree)),
            "GIT_IDENTITY_INVALID")
    return head, tree


def _head_blob(root: Path, name: str) -> bytes:
    require(name in FILES, "UNAUTHORIZED_DELIVERY_PATH")
    path = root / name
    require(path.is_file() and not path.is_symlink(),
            "TRACKED_SOURCE_NOT_REGULAR")
    # Comparing on-disk content to committed blob prevents mixing arbitrary
    # runtime WIP with the reviewed exact HEAD.
    committed = _git(root, "show", f"HEAD:{name}")
    require(0 < len(committed) <= MAX_BYTES_PER_FILE,
            "TRACKED_SOURCE_EXCEEDS_BUDGET")
    require(committed == path.read_bytes(), "WORKTREE_SOURCE_DIFFERS_FROM_HEAD")
    require(b"\x00" not in committed, "BINARY_DATA_FORBIDDEN")
    try:
        committed.decode("utf-8")
    except UnicodeError as exc:
        raise DeliveryDenied("SOURCE_NOT_UTF8") from exc
    return committed


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _entry(name: str, payload: bytes, output: ZipFile) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (0o100644 << 16)
    info.create_system = 3
    output.writestr(info, payload)


def create_package(repo: Path, output: Path, *, expected_sha: str) -> dict:
    root = repo.resolve(strict=True)
    head, tree = _head(root)
    require(bool(SHA.fullmatch(expected_sha)) and expected_sha == head,
            "EXACT_HEAD_BINDING_FAILED")
    output = output.resolve(strict=False)
    require(not output.exists() and not output.is_relative_to(root),
            "DELIVERY_OUTPUT_NOT_PRIVATE_OR_EXISTS")
    sources = {name: _head_blob(root, name) for name in FILES}
    hashes = {name: sha256(payload).hexdigest()
              for name, payload in sources.items()}
    manifest = {
        "schema": SCHEMA,
        "repository": "zenindiones-maker/Hazewave-",
        "domain": "WAVE",
        "capability": "web.scrollytelling.source_candidate",
        "harness_authority": "HAZEWAVE_HARNESS",
        "authority_granted_by_artifact": "NONE",
        "reviewed_sha": head,
        "reviewed_tree": tree,
        "source_sha256": hashes,
        "source_file_count": len(sources),
        "media_bytes_embedded": 0,
        "private_assets_present": False,
        "source_only": True,
        "real_browser_media_proven_by_this_artifact": False,
        "existing_codespace_runtime_proven": False,
        "human_approval": "PENDING",
        "production_approved": False,
        "publication_attempted": False,
        "merge_attempted": False,
        "stage": "INTERNAL_SOURCE_CANDIDATE_ONLY",
    }
    manifest_bytes = _json_bytes(manifest)
    require(len(manifest_bytes) <= MAX_MANIFEST_BYTES, "MANIFEST_TOO_LARGE")
    output.parent.mkdir(parents=True, exist_ok=True)
    # x mode refuses reuse and retains earlier delivery as immutable WIP.
    with ZipFile(output, "x") as archive:
        _entry("manifest.json", manifest_bytes, archive)
        for name in sorted(sources):
            _entry("source/" + name, sources[name], archive)
    require(output.stat().st_size <= MAX_ARCHIVE_BYTES, "ARCHIVE_TOO_LARGE")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "reviewed_sha": head,
        "reviewed_tree": tree,
        "archive_sha256": sha256(output.read_bytes()).hexdigest(),
        "archive_name": output.name,
        "source_file_count": len(sources),
        "delivery_stage": "INTERNAL_SOURCE_CANDIDATE_ONLY",
        "visual_proof_from_private_owner_art": "NOT_INCLUDED",
        "production_approved": False,
        "deployment_attempted": False,
    }
    receipt_path = output.with_name(output.name + ".receipt.json")
    receipt_path.write_bytes(_json_bytes(receipt))
    return receipt


def verify_package(package: Path, *, expected_sha: str) -> dict:
    require(bool(SHA.fullmatch(expected_sha)), "EXPECTED_SHA_INVALID")
    require(package.is_file() and not package.is_symlink() and
            package.stat().st_size <= MAX_ARCHIVE_BYTES,
            "ARCHIVE_MISSING_OR_TOO_LARGE")
    with ZipFile(package) as archive:
        names = archive.namelist()
        required = ["manifest.json"] + ["source/" + p for p in sorted(FILES)]
        require(len(names) == len(required) and sorted(names) == sorted(required),
                "ARCHIVE_PATHS_ESCALATED")
        require(archive.testzip() is None, "ARCHIVE_CRC_INVALID")
        manifest_raw = archive.read("manifest.json")
        require(len(manifest_raw) <= MAX_MANIFEST_BYTES, "MANIFEST_TOO_LARGE")
        def no_duplicates(pairs):
            result = {}
            for k, v in pairs:
                require(k not in result, "DUPLICATE_MANIFEST_KEY")
                result[k] = v
            return result
        manifest = json.loads(manifest_raw, object_pairs_hook=no_duplicates)
        require(isinstance(manifest, dict) and
                manifest.get("schema") == SCHEMA and
                manifest.get("reviewed_sha") == expected_sha and
                manifest.get("source_file_count") == len(FILES) and
                manifest.get("stage") == "INTERNAL_SOURCE_CANDIDATE_ONLY" and
                manifest.get("source_only") is True and
                manifest.get("private_assets_present") is False and
                manifest.get("media_bytes_embedded") == 0 and
                manifest.get("human_approval") == "PENDING" and
                manifest.get("production_approved") is False and
                manifest.get("publication_attempted") is False and
                manifest.get("merge_attempted") is False and
                manifest.get("real_browser_media_proven_by_this_artifact") is False and
                manifest.get("existing_codespace_runtime_proven") is False and
                manifest.get("authority_granted_by_artifact") == "NONE",
                "UNAUTHORIZED_STAGING_OR_PRODUCTION_CLAIM")
        recorded = manifest.get("source_sha256")
        require(isinstance(recorded, dict) and
                set(recorded) == set(FILES), "SOURCE_LIST_CHANGED")
        for filename in FILES:
            payload = archive.read("source/" + filename)
            require(0 < len(payload) <= MAX_BYTES_PER_FILE and
                    isinstance(recorded[filename], str) and
                    HASH.fullmatch(recorded[filename]) and
                    sha256(payload).hexdigest() == recorded[filename] and
                    b"\x00" not in payload,
                    "SOURCE_BYTES_CHANGED")
    receipt_file = package.with_name(package.name + ".receipt.json")
    require(receipt_file.is_file() and not receipt_file.is_symlink(),
            "DELIVERY_RECEIPT_NOT_FOUND")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    require(receipt.get("schema") == RECEIPT_SCHEMA and
            receipt.get("reviewed_sha") == expected_sha and
            receipt.get("reviewed_tree") == manifest.get("reviewed_tree") and
            receipt.get("archive_sha256") ==
            sha256(package.read_bytes()).hexdigest() and
            receipt.get("deployment_attempted") is False and
            receipt.get("production_approved") is False,
            "DELIVERY_RECEIPT_UNTRUSTED")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("package")
    pack.add_argument("--repo-root", type=Path, default=Path("."))
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--expected-sha", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        if args.command == "package":
            receipt = create_package(args.repo_root, args.out,
                                     expected_sha=args.expected_sha)
        else:
            receipt = verify_package(args.package,
                                     expected_sha=args.expected_sha)
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
        print("WAVE_SOURCE_CD=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("WAVE_SOURCE_CD=PASS_INTERNAL_CODE_CANDIDATE")
    print("WAVE_DELIVERY_SHA=" + receipt["reviewed_sha"])
    print("WAVE_DELIVERY_ARCHIVE_SHA256=" + receipt["archive_sha256"])
    print("WAVE_PRIVATE_MEDIA_IN_CI=FALSE")
    print("WAVE_PRODUCTION_APPROVED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
