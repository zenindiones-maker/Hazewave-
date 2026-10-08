#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE_ROOT="$REPO_ROOT/knowledge/brain"
DEFAULT_TARGET="$HOME/storage/shared/Documents/Obsidian/BR-no-GTA-Vault/Hazewave"
TARGET_ROOT="${HAZEWAVE_OBSIDIAN_ROOT:-$DEFAULT_TARGET}"

fail() {
  printf '%s\n' "$1" >&2
  exit "${2:-20}"
}

[[ -d "$SOURCE_ROOT" ]] || fail "HAZEWAVE_BRAIN_SOURCE_MISSING"

if [[ -L "$TARGET_ROOT" ]]; then
  fail "HAZEWAVE_OBSIDIAN_TARGET_SYMLINK_FORBIDDEN"
fi

mkdir -p "$TARGET_ROOT"
[[ -d "$TARGET_ROOT" ]] || fail "HAZEWAVE_OBSIDIAN_TARGET_NOT_DIRECTORY"
[[ ! -L "$TARGET_ROOT" ]] || fail "HAZEWAVE_OBSIDIAN_TARGET_SYMLINK_FORBIDDEN"

python3 - "$SOURCE_ROOT" "$TARGET_ROOT" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone

source = Path(sys.argv[1]).resolve()
target_input = Path(sys.argv[2])

if target_input.is_symlink():
    raise SystemExit("HAZEWAVE_OBSIDIAN_TARGET_SYMLINK_FORBIDDEN")

target = target_input.resolve()
if target == source or source in target.parents:
    raise SystemExit("HAZEWAVE_OBSIDIAN_TARGET_INSIDE_SOURCE_FORBIDDEN")

copied = 0
unchanged = 0
digests: dict[str, str] = {}

for src in sorted(source.rglob("*")):
    if not src.is_file():
        continue
    rel = src.relative_to(source)
    if any(part.startswith(".git") for part in rel.parts):
        continue
    if src.suffix.lower() not in {".md", ".json"}:
        continue

    dst = target / rel
    dst.parent.mkdir(parents=True, exist_ok=True)

    data = src.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    digests[rel.as_posix()] = digest

    if dst.exists() and dst.is_symlink():
        raise SystemExit(f"HAZEWAVE_OBSIDIAN_DESTINATION_SYMLINK_FORBIDDEN:{rel.as_posix()}")
    if dst.exists() and dst.is_file() and hashlib.sha256(dst.read_bytes()).hexdigest() == digest:
        unchanged += 1
        continue

    fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, dst)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    copied += 1

receipt = {
    "schema": "HazewaveObsidianProjectionReceipt/v1",
    "project": "HAZEWAVE",
    "authority": "KNOWLEDGE_ONLY",
    "grants_execution_authority": False,
    "source_root": str(source),
    "target_root": str(target),
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "copied_files": copied,
    "unchanged_files": unchanged,
    "source_digests": digests,
    "delete_policy": "NEVER_DELETE_TARGET_ONLY_FILES",
}
receipt_path = target / "00-Brain" / ".projection-receipt.json"
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(
    json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"HAZEWAVE_OBSIDIAN_SOURCE={source}")
print(f"HAZEWAVE_OBSIDIAN_TARGET={target}")
print(f"HAZEWAVE_OBSIDIAN_FILES_COPIED={copied}")
print(f"HAZEWAVE_OBSIDIAN_FILES_UNCHANGED={unchanged}")
print(f"HAZEWAVE_OBSIDIAN_RECEIPT={receipt_path}")
PY

echo "HAZEWAVE_OBSIDIAN_PROJECTION=PASS"
