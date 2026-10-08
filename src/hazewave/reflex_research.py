"""Read-only evidence gate for pinned, derived Colibri/Laya binaries.

Never starts processes, installs tools, changes models, or activates candidates.
The CLI can persist a private, append-only audit receipt in a caller-owned state
directory; missing or inconsistent evidence always results in BLOCKED.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from typing import Any


PINNED_UPSTREAM = "bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850"
VARIANTS = ("direct_y_store_v1", "mc_144_v2", "mc_408_v2", "mc_816_v2")
TOOLS = {
    "readelf": "readelf",
    "objdump": "objdump",
    "nm": "nm",
    "perf": "perf",
    "valgrind": "valgrind",
    "rizin": "rizin",
    "ghidra": "analyzeHeadless",
    "llvm-mca": "llvm-mca",
    "hyperfine": "hyperfine",
    "diffoscope": "diffoscope",
    "frida": "frida",
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def discover_tools() -> dict[str, str]:
    """Inventory commands without running them or installing dependencies."""
    return {
        name: "AVAILABLE" if shutil.which(command) else "NOT_INSTALLED"
        for name, command in TOOLS.items()
    }


def _safe_file(path: Path) -> bool:
    """Reject aliases/symlinks at the variant boundary and nonregular artifacts."""
    try:
        return (
            not path.is_symlink()
            and stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
        )
    except OSError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_derived_engines(
    *,
    stock_binary: Path,
    derived_root: Path,
    upstream_commit: str,
) -> dict[str, Any]:
    """Return a fail-closed report; do not touch or execute any engine binary."""
    errors: list[str] = []
    artifacts: list[dict[str, Any]] = []
    seen_digests: dict[str, str] = {}
    seen_inodes: dict[tuple[int, int], str] = {}

    if upstream_commit != PINNED_UPSTREAM:
        errors.append("RE_UPSTREAM_SHA_MISMATCH")

    if stock_binary.is_symlink() or not _safe_file(stock_binary):
        errors.append("RE_STOCK_BINARY_INVALID")
    else:
        stock_digest = _sha256_file(stock_binary)
        seen_digests[stock_digest] = "stock"
        stock_stat = stock_binary.stat(follow_symlinks=False)
        seen_inodes[(stock_stat.st_dev, stock_stat.st_ino)] = "stock"

    if derived_root.is_symlink() or not derived_root.is_dir():
        errors.append("RE_DERIVED_ROOT_INVALID")
        return _report(errors, artifacts, upstream_commit)

    for variant in VARIANTS:
        root = derived_root / variant
        path = root / "c" / "laya"
        metadata_path = root / "build.json"
        if root.is_symlink() or (root / "c").is_symlink():
            errors.append(f"RE_SYMLINK_FORBIDDEN:{variant}")
            continue
        if metadata_path.is_symlink() or path.is_symlink():
            errors.append(f"RE_SYMLINK_FORBIDDEN:{variant}")
            continue
        if not _safe_file(metadata_path):
            errors.append(f"RE_METADATA_MISSING:{variant}")
            continue
        if not _safe_file(path) or not os.access(path, os.X_OK):
            errors.append(f"RE_BINARY_MISSING:{variant}")
            continue

        try:
            if metadata_path.stat().st_size > 64 * 1024:
                raise ValueError("metadata size")
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeError):
            errors.append(f"RE_METADATA_INVALID:{variant}")
            continue

        if not isinstance(meta, dict):
            errors.append(f"RE_METADATA_INVALID:{variant}")
            continue

        generic_valid = (
            meta.get("schema") == "HazewaveReflexDerivedEngineBuild/v1"
            and meta.get("variant") == variant
            and meta.get("upstream_commit") == PINNED_UPSTREAM
            and meta.get("provider_authority") == "NONE"
            and meta.get("changes_model_or_precision") is False
            and meta.get("preserves_k_accumulation_order") is True
            and meta.get("requires_exact_output_gate") is True
            and isinstance(meta.get("patch_sha256"), str)
            and bool(_HEX64.fullmatch(meta["patch_sha256"]))
        )
        if not generic_valid:
            errors.append(f"RE_METADATA_INVALID:{variant}")
            continue

        if variant.startswith("mc_"):
            mc = int(variant.split("_")[1])
            if meta.get("qi_mc") != mc or meta.get("cache_block_mc_only") is not True:
                errors.append(f"RE_MC_METADATA_MISMATCH:{variant}")
                continue
        elif meta.get("direct_y_store_only") is not True or meta.get("full_tile_only") is not True:
            errors.append(f"RE_DIRECT_STORE_METADATA_MISMATCH:{variant}")
            continue

        actual_digest = _sha256_file(path)
        if meta.get("binary_sha256") != actual_digest:
            errors.append(f"RE_BINARY_SHA_MISMATCH:{variant}")
            continue

        binary_stat = path.stat(follow_symlinks=False)
        inode = (binary_stat.st_dev, binary_stat.st_ino)
        previous = seen_inodes.get(inode) or seen_digests.get(actual_digest)
        if previous:
            errors.append(f"RE_DUPLICATE_BINARY:{previous}:{variant}")
            continue
        seen_inodes[inode] = variant
        seen_digests[actual_digest] = variant
        artifacts.append({
            "variant": variant,
            "binary_sha256": actual_digest,
            "patch_sha256": meta["patch_sha256"],
            "size_bytes": binary_stat.st_size,
        })
    return _report(errors, artifacts, upstream_commit)


def _report(errors: list[str], artifacts: list[dict[str, Any]], upstream_commit: str) -> dict[str, Any]:
    return {
        "schema": "HazewaveReflexReverseEngineeringAudit/v1",
        "status": "BLOCKED" if errors else "PASS",
        "errors": errors,
        "upstream_commit": upstream_commit,
        "artifacts": artifacts,
        "tools": discover_tools(),
        "provider_authority": "NONE",
        "activation": "FORBIDDEN",
        "production_calibrated": False,
        "limitations": [
            "Static file integrity only; no runtime execution or inference proof.",
            "Binary hashes do not prove semantic or numerical equivalence.",
            "Tool presence does not prove usability or profiling permissions.",
        ],
    }


def _persist_report(report: dict[str, Any], state_root: Path) -> Path:
    if state_root.is_symlink():
        raise ValueError("RE_STATE_ROOT_SYMLINK_FORBIDDEN")
    root = state_root / "research" / "audits"
    if root.parent.is_symlink() or root.is_symlink():
        raise ValueError("RE_RECEIPT_DIRECTORY_SYMLINK_FORBIDDEN")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / f"{stamp}-{os.getpid()}.json"
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Reflex binary evidence gate")
    parser.add_argument("--stock-binary", type=Path, required=True)
    parser.add_argument("--derived-root", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--state-root", type=Path)
    args = parser.parse_args(argv)
    report = audit_derived_engines(
        stock_binary=args.stock_binary,
        derived_root=args.derived_root,
        upstream_commit=args.upstream_commit,
    )
    if args.state_root:
        receipt = _persist_report(report, args.state_root)
        print(f"REFLEX_RE_RESEARCH_RECEIPT={receipt}")
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    print(f"REFLEX_RE_RESEARCH_AUDIT={report['status']}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
