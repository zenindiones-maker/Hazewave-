"""Read-only, bounded, locally curated HAZE music collection.

Inventory tracks sessions and audio across project folders without moving any
original files. Curated references require explicit owner genre/role + rights
confirmation; they are analyzed locally and are never used for model training.
No cloud/API/DAW calls or filesystem modification of the music corpus.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from typing import Any, Mapping, Sequence

from hazewave.reference_profile import (
    DEFAULT_ANALYSIS_SAMPLE_RATE,
    DecodedPCM,
    ReferenceProfileError,
    build_reference_profile,
)


class CatalogError(RuntimeError):
    pass


_AUDIO = frozenset({
    ".wav", ".flac", ".aiff", ".aif", ".mp3", ".m4a", ".ogg",
    ".opus", ".aac", ".wma",
})
_MIDI = frozenset({".mid", ".midi"})
_BLOCKED_DIRS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".cache",
    ".trash", "trash", "lost+found",
})
_OWNER_ROLES = frozenset({
    "MIX_REFERENCE", "MASTER_REFERENCE", "ARRANGEMENT_REFERENCE",
    "BEAT_REFERENCE", "SOUND_DESIGN_REFERENCE", "VOCAL_REFERENCE",
})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HASH_CHUNK = 1024 * 1024
_PCM_MAX_SECONDS = 30.0  # 12 kHz stereo, bounded memory on existing 2vCPU host


def _root_path(root: Path | str) -> Path:
    raw = Path(root).expanduser()
    if not raw.is_dir():
        raise CatalogError("CATALOG_ROOT_INVALID")
    resolved = raw.resolve(strict=True)
    if resolved == Path("/") or resolved == Path.home().resolve():
        raise CatalogError("CATALOG_ROOT_FORBIDDEN")
    return resolved


def _sha_file(path: Path) -> str:
    digest = sha256()
    before = path.stat()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ):
        raise CatalogError("CATALOG_SOURCE_CHANGED_DURING_READ")
    return digest.hexdigest()


def _role(path: Path) -> str | None:
    name = path.name.casefold()
    if name.endswith(".rpp") or name.endswith(".rpp-bak"):
        return "REAPER_SESSION"
    if path.suffix.casefold() in _AUDIO:
        return "AUDIO"
    if path.suffix.casefold() in _MIDI:
        return "MIDI"
    return None


def _reject_walk_error(error: OSError) -> None:
    raise CatalogError("CATALOG_FOLDER_READ_FAILED") from error


def scan_music_catalog(
    root: Path | str, *, authorized: bool,
    max_files: int = 5000, hash_audio_up_to_bytes: int = 0,
) -> dict[str, Any]:
    """Read metadata by project. Optional *bounded* content hash is opt-in.

    A SHA digest identifies byte-identical files, not similar arrangements or
    mixes. Project names are only folder provenance, never inferred genres.
    """
    if authorized is not True:
        raise CatalogError("CATALOG_NOT_AUTHORIZED")
    if type(max_files) is not int or not 1 <= max_files <= 100000:
        raise CatalogError("CATALOG_FILE_LIMIT_INVALID")
    if type(hash_audio_up_to_bytes) is not int or not 0 <= hash_audio_up_to_bytes <= 2**40:
        raise CatalogError("CATALOG_HASH_BUDGET_INVALID")
    source = _root_path(root)
    records: list[dict[str, Any]] = []
    skipped_symlinks = 0
    seen_projects: set[str] = set()

    for current, dirs, files in os.walk(
        source, topdown=True, followlinks=False, onerror=_reject_walk_error
    ):
        safe_dirs = []
        for name in sorted(dirs, key=str.casefold):
            folder = Path(current) / name
            if folder.is_symlink():
                skipped_symlinks += 1
            elif name.startswith(".") or name.casefold() in _BLOCKED_DIRS:
                continue
            else:
                safe_dirs.append(name)
        dirs[:] = safe_dirs

        for name in sorted(files, key=str.casefold):
            candidate = Path(current) / name
            if candidate.is_symlink():
                skipped_symlinks += 1
                continue
            if name.startswith("."):
                continue
            role = _role(candidate)
            if role is None:
                continue
            if len(records) >= max_files:
                raise CatalogError("CATALOG_FILE_LIMIT_EXCEEDED")
            if not candidate.is_file():
                raise CatalogError("CATALOG_UNEXPECTED_MEDIA_TYPE")
            rel = candidate.relative_to(source)
            project = rel.parts[0] if len(rel.parts) > 1 else "_ROOT_UNSORTED"
            stat = candidate.stat()
            fingerprint = None
            if role == "AUDIO" and 0 < stat.st_size <= hash_audio_up_to_bytes:
                fingerprint = _sha_file(candidate)
            seen_projects.add(project)
            records.append({
                "relative_path": rel.as_posix(),
                "project": project,
                "asset_role": role,
                "size_bytes": stat.st_size,
                "sha256": fingerprint,
                "owner_genre": None,
                "curation_status": "UNREVIEWED",
            })

    records.sort(key=lambda x: x["relative_path"].casefold())
    duplicates: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record["asset_role"] == "AUDIO" and record["sha256"]:
            duplicates[record["sha256"]].append(record["relative_path"])
    return {
        "schema": "HazePrivateCatalog/v1",
        "source_root": str(source),
        "has_private_paths": True,
        "project_count": len(seen_projects),
        "file_count": len(records),
        "content_hash_count": sum(x["sha256"] is not None for x in records),
        "skipped_symlinks": skipped_symlinks,
        "projects": sorted(seen_projects, key=str.casefold),
        "items": records,
        "exact_duplicate_groups": [
            {"sha256":digest,"relative_paths":paths}
            for digest, paths in sorted(duplicates.items()) if len(paths) > 1
        ],
        "genre_labels_are_owner_provided_only": True,
        "filesystem_changes": 0,
        "style_learned": False,
        "training_started": False,
        "private_audio_exported": False,
        "execution_authority": "NONE",
    }


def _checked_owned_audio(
    root: Path, relative_path: str,
) -> Path:
    if not isinstance(relative_path,str) or not relative_path.strip():
        raise CatalogError("CURATION_PATH_INVALID")
    rel = Path(relative_path)
    if rel.is_absolute() or any(part in (".", "..", "") for part in rel.parts):
        raise CatalogError("CURATION_UNOWNED_SOURCE")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise CatalogError("CURATION_UNOWNED_SOURCE")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise CatalogError("CURATION_UNOWNED_SOURCE") from exc
    if not resolved.is_file() or _role(resolved) != "AUDIO":
        raise CatalogError("CURATION_SOURCE_NOT_AUDIO")
    return resolved


def _bounded_pcm_decoder(source: Path) -> DecodedPCM:
    """Analyze at most a middle 30 s excerpt; full-program loudness is separate."""
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(source),
        ], capture_output=True, text=True, timeout=30, check=False)
        if probe.returncode != 0:
            raise CatalogError("CURATION_AUDIO_DURATION_PROBE_FAILED")
        length = float(probe.stdout.strip())
        if not math.isfinite(length) or length <= 0:
            raise CatalogError("CURATION_AUDIO_DURATION_INVALID")
        start = max(0.0, (length - _PCM_MAX_SECONDS) / 2.0)
        duration = min(length, _PCM_MAX_SECONDS)
        result = subprocess.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
            "-ss", f"{start:.3f}", "-i", str(source),
            "-t", f"{duration:.3f}", "-map", "0:a:0",
            "-ac", "2", "-ar", str(DEFAULT_ANALYSIS_SAMPLE_RATE),
            "-f", "s16le", "pipe:1",
        ], capture_output=True, timeout=60, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as exc:
        raise CatalogError("CURATION_BOUNDED_PCM_DECODE_FAILED") from exc
    if result.returncode != 0 or not result.stdout or len(result.stdout) % 4:
        raise CatalogError("CURATION_BOUNDED_PCM_DECODE_FAILED")
    frames = tuple(
        (left / 32768.0, right / 32768.0)
        for left, right in struct.iter_unpack("<hh", result.stdout)
    )
    if not frames:
        raise CatalogError("CURATION_BOUNDED_PCM_EMPTY")
    return DecodedPCM(
        sample_rate=DEFAULT_ANALYSIS_SAMPLE_RATE, channels=2, frames=frames
    )


def curate_style_references(
    catalog: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]], *,
    root: Path | str, authorized: bool,
) -> dict[str, Any]:
    """Create *descriptive* sonic memory from separately owner-approved tracks.

    Technical characterization is not model fine-tuning, style authorship proof,
    whole-track timbral ground truth, or a license to control REAPER.
    """
    if authorized is not True:
        raise CatalogError("CURATION_NO_AUTHORITY")
    source = _root_path(root)
    if catalog.get("schema") != "HazePrivateCatalog/v1" or catalog.get("source_root") != str(source):
        raise CatalogError("CURATION_CATALOG_IDENTITY_MISMATCH")
    if not isinstance(selections,(list,tuple)) or not 1 <= len(selections) <= 16:
        raise CatalogError("CURATION_BATCH_LIMIT_OR_EMPTY")
    by_path = {r["relative_path"]:r for r in catalog.get("items",[]) if isinstance(r,dict)}
    references = []
    visited = set()
    for selected in selections:
        if not isinstance(selected,dict):
            raise CatalogError("CURATION_SELECTION_INVALID")
        if selected.get("owner_approved") is not True:
            raise CatalogError("CURATION_OWNER_APPROVAL_REQUIRED")
        if selected.get("rights_confirmed") is not True:
            raise CatalogError("CURATION_RIGHTS_REQUIRED")
        genre = selected.get("owner_genre")
        if not isinstance(genre,str) or not genre.strip() or len(genre)>120:
            raise CatalogError("CURATION_GENRE_REQUIRED")
        role = selected.get("reference_role")
        if role not in _OWNER_ROLES:
            raise CatalogError("CURATION_REFERENCE_ROLE_INVALID")
        rel = selected.get("relative_path")
        if not isinstance(rel,str) or rel in visited:
            raise CatalogError("CURATION_DUPLICATE_OR_INVALID_SELECTION")
        visited.add(rel)
        row = by_path.get(rel)
        if row is None or row.get("asset_role") != "AUDIO":
            raise CatalogError("CURATION_NOT_IN_CATALOG")
        expected = row.get("sha256")
        if not isinstance(expected,str) or not _HEX64.fullmatch(expected):
            raise CatalogError("CURATION_DIGEST_NOT_AVAILABLE")
        audio = _checked_owned_audio(source,rel)
        if _sha_file(audio) != expected:
            raise CatalogError("CURATION_SOURCE_CHANGED")
        try:
            profile = build_reference_profile(
                audio, authorized=True, pcm_decoder=_bounded_pcm_decoder,
                section_count=8,
            )
        except (ReferenceProfileError, CatalogError) as exc:
            raise CatalogError("CURATION_ACOUSTIC_PROFILE_FAILED") from exc
        if profile.source_sha256 != expected:
            raise CatalogError("CURATION_SOURCE_CHANGED")
        data = profile.to_dict()
        data.pop("source_path",None)  # no absolute paths in style feature records
        references.append({
            "relative_path":rel,
            "source_sha256":expected,
            "owner_genre":genre.strip(),
            "reference_role":role,
            "acoustic_profile":data,
            "sonic_features_scope":"BOUNDED_MIDDLE_EXCERPT_MAX_30S",
            "loudness_scope":"COMPLETE_AUDIO_SOURCE",
            "status":"OWNER_REFERENCE_APPROVED_NOT_A_MODEL_TRAINING_GRANT",
        })
    return {
        "schema":"HazeCuratedStyleMemory/v1",
        "source_catalog_schema":catalog["schema"],
        "reference_count":len(references),
        "references":references,
        "model_weights_updated":False,
        "training_started":False,
        "private_audio_exported":False,
        "reaper_runtime_proven":False,
        "production_approved":False,
        "human_review_required":True,
        "authority":"NONE",
    }


def write_private_receipt(
    payload: Mapping[str, Any], output:Path | str, *, source_root:Path | str,
) -> Path:
    """Create mode-0600 JSON outside source, atomically and without overwrite."""
    root = _root_path(source_root)
    destination = Path(output).expanduser().absolute()
    if destination.resolve(strict=False).is_relative_to(root):
        raise CatalogError("CATALOG_OUTPUT_INSIDE_SOURCE")
    if destination.exists() or destination.is_symlink():
        raise CatalogError("CATALOG_OUTPUT_EXISTS")
    parent = destination.parent.resolve(strict=False)
    for ancestor in (parent, *parent.parents):
        if ancestor.name == ".git" or (ancestor / ".git").exists():
            raise CatalogError("CATALOG_OUTPUT_IN_GIT_WORKTREE")
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".haze-private-",suffix=".tmp",dir=destination.parent
    )
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(payload,handle,ensure_ascii=False,sort_keys=True,indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary,destination)  # O_EXCL-like: never replace existing
    except FileExistsError as exc:
        raise CatalogError("CATALOG_OUTPUT_EXISTS") from exc
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="python -m hazewave.haze_catalog")
    parser.add_argument("command",choices=("inventory","curate"))
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--allow-private-corpus",action="store_true")
    parser.add_argument("--hash-max-mb",type=int,default=0)
    parser.add_argument("--max-files",type=int,default=5000)
    parser.add_argument("--catalog",type=Path)
    parser.add_argument("--selections",type=Path)
    args=parser.parse_args(argv)
    try:
        if not args.allow_private_corpus:
            raise CatalogError("CATALOG_NOT_AUTHORIZED")
        if args.command=="inventory":
            result=scan_music_catalog(
                args.root,authorized=True,max_files=args.max_files,
                hash_audio_up_to_bytes=args.hash_max_mb*1024*1024,
            )
        else:
            if args.catalog is None or args.selections is None:
                raise CatalogError("CURATION_INPUTS_REQUIRED")
            catalog=json.loads(args.catalog.read_text(encoding="utf-8"))
            selections=json.loads(args.selections.read_text(encoding="utf-8"))
            result=curate_style_references(
                catalog,selections,root=args.root,authorized=True
            )
        location=write_private_receipt(result,args.output,source_root=args.root)
    except (CatalogError,OSError,ValueError,json.JSONDecodeError) as exc:
        print(f"HAZE_CATALOG=BLOCKED:{exc}")
        return 20
    # Private filenames, song titles and the corpus root are never printed.
    print("HAZE_CATALOG=LOCAL_RECEIPT_WRITTEN")
    print(f"HAZE_CATALOG_SCHEMA={result['schema']}")
    print("HAZE_MODEL_TRAINING=NOT_STARTED")
    print("HAZE_REAPER_CONTROL=NOT_GRANTED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
