from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any


AUTOSTART_BEGIN = "-- Hazewave REAPER bridge: start"
AUTOSTART_END = "-- Hazewave REAPER bridge: end"
TARGET_RELATIVE = Path("Scripts") / "Hazewave" / "hazewave_reaper_bridge.lua"


class ReaperBridgeInstallError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_name = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _autostart_block() -> str:
    return (
        f"{AUTOSTART_BEGIN}\n"
        "do\n"
        '  local bridge_path = reaper.GetResourcePath() .. "/Scripts/Hazewave/hazewave_reaper_bridge.lua"\n'
        "  local ok, err = pcall(dofile, bridge_path)\n"
        "  if not ok then\n"
        '    reaper.ShowConsoleMsg("Hazewave REAPER bridge did not start: " .. tostring(err) .. "\\n")\n'
        "  end\n"
        "end\n"
        f"{AUTOSTART_END}\n"
    )


def _without_managed_block(text: str) -> str:
    begin = text.find(AUTOSTART_BEGIN)
    end = text.find(AUTOSTART_END)
    if begin == -1 and end == -1:
        return text
    if begin == -1 or end == -1 or end < begin:
        raise ReaperBridgeInstallError("REAPER_STARTUP_MANAGED_BLOCK_MALFORMED")
    end += len(AUTOSTART_END)
    if text[end : end + 1] == "\n":
        end += 1
    if AUTOSTART_BEGIN in text[end:] or AUTOSTART_END in text[end:]:
        raise ReaperBridgeInstallError("REAPER_STARTUP_MULTIPLE_MANAGED_BLOCKS")
    return text[:begin] + text[end:]


def _desired_startup(existing: str) -> str:
    remaining = _without_managed_block(existing)
    if remaining and not remaining.endswith("\n"):
        remaining += "\n"
    if remaining.strip():
        remaining += "\n"
    return remaining + _autostart_block()


def install_reaper_bridge(
    *,
    source: Path | str,
    resource_dir: Path | str,
) -> dict[str, Any]:
    source_path = Path(source)
    resource = Path(resource_dir)
    if not source_path.is_file():
        raise ReaperBridgeInstallError("REAPER_BRIDGE_SOURCE_MISSING")

    scripts_dir = resource / "Scripts"
    target = resource / TARGET_RELATIVE
    startup = scripts_dir / "__startup.lua"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    source_bytes = source_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()

    target_changed = not target.is_file() or target.read_bytes() != source_bytes
    target_backup: Path | None = None
    if target_changed:
        if target.exists():
            target_backup = _backup(target)
        _atomic_write_bytes(target, source_bytes)

    existing_startup = startup.read_text(encoding="utf-8") if startup.exists() else ""
    desired_startup = _desired_startup(existing_startup)
    startup_changed = desired_startup != existing_startup
    startup_backup: Path | None = None
    if startup_changed:
        if startup.exists():
            startup_backup = _backup(startup)
        _atomic_write_bytes(startup, desired_startup.encode("utf-8"))

    target_sha = _sha256(target)
    if target_sha != source_sha:
        raise ReaperBridgeInstallError("REAPER_BRIDGE_COPY_HASH_MISMATCH")

    return {
        "schema": "ReaperBridgeInstallReceipt/v1",
        "source": str(source_path),
        "source_sha256": source_sha,
        "target": str(target),
        "target_sha256": target_sha,
        "startup": str(startup),
        "startup_sha256": _sha256(startup),
        "target_backup": str(target_backup) if target_backup else None,
        "startup_backup": str(startup_backup) if startup_backup else None,
        "autostart_marker": AUTOSTART_BEGIN,
        "changed": target_changed or startup_changed,
        "runtime_proven": False,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hazewave-reaper-bridge-install")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--resource-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)

    try:
        receipt = install_reaper_bridge(
            source=args.source,
            resource_dir=args.resource_dir,
        )
    except ReaperBridgeInstallError as exc:
        print(f"REAPER_BRIDGE_INSTALL=FAIL:{exc}")
        return 20

    rendered = json.dumps(receipt, sort_keys=True, indent=2)
    print(rendered)
    if args.receipt:
        _atomic_write_bytes(args.receipt, (rendered + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
