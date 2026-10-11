"""Join seven real ArtCraft CLI proof artifacts from ONE GitHub Actions run.

Every app was already run in a separate network-isolated sandbox, admitted by
Hazewave Harness. This code ONLY validates and stages public synthetic outputs.
No owner artwork, deployment, automatic publication or independent authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256 as hashlib_sha256
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps/hazewave-site/experiments/travessia-v4"))
from wave_artcraft_external_tools import verify as verify_craft, sha256, validate_lock, LOCK
from artcraft_vector_bridge import validate_png as verify_vector_png, source_svg
from artcraft_portal_pipeline import verify as verify_effect_film

SCHEMA = "HazewaveArtCraftSevenLabHandoff/v1"
REPO = "zenindiones-maker/Hazewave-"
TOOLS = frozenset({
    "photocraft", "lightcraft", "designcraft", "pdfcraft",
    "vectorcraft", "effectcraft", "filmcraft",
})
RUN_RE = re.compile(r"^[0-9]{8,15}$")
HEAD_RE = re.compile(r"^[a-f0-9]{40}$")
COPY_MAP = {
    "photocraft": ("image", "photocraft-render.png", "assets/photocraft.png"),
    "lightcraft": ("image", "lightcraft-render.png", "assets/lightcraft.png"),
    "designcraft": ("editorial", "designcraft-layout.pdf", "assets/designcraft.pdf"),
    "pdfcraft": ("editorial", "pdfcraft-render.png", "assets/pdfcraft.png"),
    "vectorcraft": ("vector", "wave-signal-vectorcraft.png", "assets/vectorcraft.png"),
    "effectcraft": ("motion", "frames/sonic-portal-00.png", "assets/sonic-portal-00.png"),
    "filmcraft": ("motion", "effectcraft-reference.webm", "assets/effectcraft-reference.webm"),
}
EVIDENCE = {
    "photocraft": ("image", "photocraft-receipt.json"),
    "lightcraft": ("image", "lightcraft-receipt.json"),
    "designcraft": ("editorial", "designcraft-receipt.json"),
    "pdfcraft": ("editorial", "pdfcraft-receipt.json"),
    "vectorcraft": ("vector", "proof.json"),
    "effectcraft": ("motion", "effectcraft-filmcraft-proof.json"),
    "filmcraft": ("motion", "filmcraft-probe.txt"),
}


def _safe_file(root: Path, rel: str) -> Path:
    if not rel or rel.startswith("/") or "\\" in rel or any(
        p in (".", "..", "") for p in rel.split("/")
    ):
        raise ValueError("SEVEN_TOOL_ARTIFACT_PATH_ESCAPE")
    path = root / rel
    if not path.is_file() or path.is_symlink():
        raise ValueError("SEVEN_TOOL_ARTIFACT_MISSING_OR_SYMLINK:" + rel)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError("SEVEN_TOOL_ARTIFACT_ESCAPE")
    return path


def _require_identity(run_id: str, head_sha: str) -> None:
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        raise ValueError("SEVEN_TOOL_RUN_ID_REQUIRED")
    if not isinstance(head_sha, str) or not HEAD_RE.fullmatch(head_sha):
        raise ValueError("SEVEN_TOOL_EXACT_COMMIT_REQUIRED")


def _validate_sources(
    *, image: Path, editorial: Path, vector: Path, motion: Path, run_id: str
) -> dict[str, Path]:
    sources = {
        name: path.resolve(strict=True)
        for name, path in (
            ("image", image), ("editorial", editorial),
            ("vector", vector), ("motion", motion)
        )
    }
    if len(set(sources.values())) != 4:
        raise ValueError("SEVEN_TOOL_DUPLICATE_SOURCE_DIRECTORY")
    for key, folder in sources.items():
        if not folder.is_dir() or folder.is_symlink() or folder.is_relative_to(ROOT):
            raise ValueError("SEVEN_TOOL_SOURCE_BOUNDARY:" + key)
    for name, folder in sources.items():
        for other, other_folder in sources.items():
            if name != other and folder.is_relative_to(other_folder):
                raise ValueError("SEVEN_TOOL_NESTED_SOURCE")
    for name in ("photocraft", "lightcraft", "designcraft", "pdfcraft"):
        upstream = {
            "lightcraft": "photocraft",
            "pdfcraft": "designcraft",
        }.get(name)
        root = sources["image" if name in ("photocraft", "lightcraft") else "editorial"]
        provenance_kwargs = (
            {
                "provenance_receipt": root / "receipt.json",
                "provenance_id": f"artcraft-{run_id}-designcraft",
            } if name == "pdfcraft" else {}
        )
        verify_craft(
            name, root, task_id=f"artcraft-{run_id}-{name}",
            upstream_task_id=f"artcraft-{run_id}-{upstream}" if upstream else None,
            **provenance_kwargs,
        )

    vector_root = sources["vector"]
    vector_info = json.loads(_safe_file(vector_root, "proof.json").read_text())
    svg_source = ROOT / "apps/hazewave-site/experiments/travessia-v4/index.html"
    _, original_sha = source_svg(svg_source)
    lock = validate_lock(json.loads(LOCK.read_text()))
    vector_png = _safe_file(vector_root, "wave-signal-vectorcraft.png")
    if (
        vector_info.get("schema") != "HazewaveVectorCraftSiteAssetProof/v1"
        or vector_info.get("project") != REPO
        or vector_info.get("tool_executed") is not True
        or vector_info.get("production_approved") is not False
        or vector_info.get("merged_or_published") is not False
        or vector_info.get("site_engine_source_sha256") != original_sha
        or vector_info.get("external_release_archive_sha256") != lock["vectorcraft"]["sha256"]
        or vector_info.get("output_png_sha256") != verify_vector_png(vector_png)
    ):
        raise ValueError("SEVEN_TOOL_VECTORCRAFT_PROVENANCE_MISMATCH")

    motion_root = sources["motion"]
    fx = verify_effect_film(motion_root)
    if (
        fx.get("effectcraft_release_sha256") != lock["effectcraft"]["sha256"]
        or fx.get("filmcraft_release_sha256") != lock["filmcraft"]["sha256"]
        or fx.get("owner_visual_approval") != "PENDING"
        or fx.get("owner_private_media_used") is not False
        or fx.get("production_approved") is not False
    ):
        raise ValueError("SEVEN_TOOL_MOTION_PROVENANCE_MISMATCH")
    return sources


def assemble(
    *, image: Path, editorial: Path, vector: Path, motion: Path,
    output: Path, run_id: str, head_sha: str,
) -> dict:
    _require_identity(run_id, head_sha)
    target = output.resolve(strict=False)
    if target.exists() or target.is_relative_to(ROOT):
        raise ValueError("SEVEN_TOOL_OUTPUT_MUST_BE_NEW_OUTSIDE_REPO")
    sources = _validate_sources(
        image=image, editorial=editorial, vector=vector, motion=motion,
        run_id=run_id,
    )
    for source in sources.values():
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise ValueError("SEVEN_TOOL_OUTPUT_OVERLAPS_SOURCE")
    planned_assets = {
        name: (sources[group], relative, dest)
        for name, (group, relative, dest) in COPY_MAP.items()
    }
    for group_root, rel, _ in planned_assets.values():
        _safe_file(group_root, rel)
    for group, relative in EVIDENCE.values():
        _safe_file(sources[group], relative)
    from wave_artcraft_external_tools import verify_designcraft_provenance
    editorial_provenance = verify_designcraft_provenance(
        sources["editorial"],
        receipt=_safe_file(sources["editorial"], "receipt.json"),
        stage_id=f"artcraft-{run_id}-designcraft",
    )
    # Motion requires ALL eight frames, not a still-image substitute.
    frames = [
        (sources["motion"], f"frames/sonic-portal-{i:02d}.png",
         f"assets/sonic-portal-{i:02d}.png")
        for i in range(8)
    ]
    for group_root, rel, _ in frames:
        _safe_file(group_root, rel)

    target.mkdir(parents=True, mode=0o700)
    asset_receipts: dict[str, dict] = {}
    proof_receipts: dict[str, dict] = {}
    for name, (source_root, rel, dest) in planned_assets.items():
        item = _safe_file(source_root, rel)
        destination = target / dest
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, destination)
        asset_receipts[name] = {"path": dest, "sha256": sha256(destination)}
    frame_receipts = []
    for source_root, rel, dest in frames:
        item = _safe_file(source_root, rel)
        destination = target / dest
        if not destination.exists():
            shutil.copyfile(item, destination)
        frame_receipts.append({"path": dest, "sha256": sha256(destination)})
    for name, (group, relative) in EVIDENCE.items():
        item = _safe_file(sources[group], relative)
        dest = "receipts/" + name + Path(relative).suffix
        destination = target / dest
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, destination)
        proof_receipts[name] = {"path": dest, "sha256": sha256(destination)}

    external_receipt = _safe_file(sources["editorial"], "receipt.json")
    provenance_dest = target / "receipts" / "designcraft-provenance.json"
    shutil.copyfile(external_receipt, provenance_dest)
    provenance = {
        "path": "receipts/designcraft-provenance.json",
        "sha256": sha256(provenance_dest),
        "stage_id": editorial_provenance["stage_id"],
        "artifact_hash": editorial_provenance["artifact_hash"],
    }
    owner_source = ROOT / "apps/hazewave-site/owner-art-provenance.json"
    identity_source = json.loads(owner_source.read_text(encoding="utf-8"))
    approved = {a["asset"]: a for a in identity_source["assets"]}
    site_public = ROOT / "apps/hazewave-site/public"
    identities = {}
    for key, original, final in (
        ("hazewave", "/media/hazewave-world.jpg", "media/hazewave-world.jpg"),
        ("indionesbala", "/media/artists/indionesbala.webp",
         "media/artists/indionesbala.jpg"),
    ):
        actual = _safe_file(site_public, original.lstrip("/"))
        if sha256(actual) != approved[original]["sha256"]:
            raise ValueError("SEVEN_TOOL_OWNER_IDENTITY_SHA_MISMATCH")
        identities[key] = {"path": final, "sha256": sha256(actual)}
    receipt = {
        "schema": SCHEMA, "repository": REPO, "run_id": run_id,
        "head_sha": head_sha, "domain": "WAVE",
        "authority": "HAZEWAVE_HARNESS", "classification": "PUBLIC",
        "owner_private_media_used": False, "production_approved": False,
        "publication_attempted": False, "site_integration_status": "LAB_ASSETS_ONLY",
        "all_seven_external_clis_executed": True,
        "artifacts": asset_receipts, "evidence": proof_receipts,
        "motion_frames": frame_receipts,
        "designcraft_provenance": provenance,
        "identity_assets": identities,
    }
    (target / "integration_manifest.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_bundle(target, run_id=run_id, head_sha=head_sha)
    return receipt


def verify_bundle(root: Path, *, run_id: str, head_sha: str) -> dict:
    _require_identity(run_id, head_sha)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("SEVEN_TOOL_BUNDLE_DIRECTORY_INVALID")
    manifest = json.loads(_safe_file(root, "integration_manifest.json").read_text())
    if not isinstance(manifest, dict) or (
        manifest.get("schema") != SCHEMA
        or manifest.get("repository") != REPO
        or manifest.get("run_id") != run_id
        or manifest.get("head_sha") != head_sha
        or manifest.get("domain") != "WAVE"
        or manifest.get("authority") != "HAZEWAVE_HARNESS"
        or manifest.get("classification") != "PUBLIC"
        or manifest.get("owner_private_media_used") is not False
        or manifest.get("production_approved") is not False
        or manifest.get("publication_attempted") is not False
        or manifest.get("site_integration_status") != "LAB_ASSETS_ONLY"
        or manifest.get("all_seven_external_clis_executed") is not True
    ):
        raise ValueError("SEVEN_TOOL_BUNDLE_AUTHORITY_OR_STATUS_INVALID")
    artifacts = manifest.get("artifacts")
    evidence = manifest.get("evidence")
    frames = manifest.get("motion_frames")
    prov = manifest.get("designcraft_provenance")
    if (
        not isinstance(artifacts, dict) or set(artifacts) != TOOLS
        or not isinstance(evidence, dict) or set(evidence) != TOOLS
        or not isinstance(frames, list) or len(frames) != 8
    ):
        raise ValueError("SEVEN_TOOL_INCOMPLETE_MANIFEST")
    for kind, receipts in (("asset", artifacts), ("proof", evidence)):
        for name, item in receipts.items():
            if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                raise ValueError("SEVEN_TOOL_MANIFEST_FORMAT:" + kind + ":" + name)
            expected = (
                COPY_MAP[name][2] if kind == "asset"
                else "receipts/" + name + Path(EVIDENCE[name][1]).suffix
            )
            if item["path"] != expected:
                raise ValueError("SEVEN_TOOL_MANIFEST_PATH_CHANGED:" + name)
            if sha256(_safe_file(root, expected)) != item["sha256"]:
                raise ValueError("SEVEN_TOOL_MANIFEST_HASH_CHANGED:" + name)
    if not isinstance(prov, dict) or set(prov) != {
        "path", "sha256", "stage_id", "artifact_hash"
    }:
        raise ValueError("SEVEN_TOOL_DESIGNCRAFT_PROVENANCE_MISSING")
    if (prov["path"] != "receipts/designcraft-provenance.json"
        or prov["stage_id"] != f"artcraft-{run_id}-designcraft"
        or prov["artifact_hash"] != artifacts["designcraft"]["sha256"]
        or sha256(_safe_file(root, prov["path"])) != prov["sha256"]):
        raise ValueError("SEVEN_TOOL_DESIGNCRAFT_PROVENANCE_MISMATCH")
    record = json.loads(_safe_file(root, prov["path"]).read_text(encoding="utf-8"))
    if (record.get("stage_id") != prov["stage_id"]
        or record.get("artifact_hash") != prov["artifact_hash"]
        or record.get("source_path") != "designcraft-layout.pdf"
        or record.get("schema") != "HazewaveDesignCraftProvenance/v1"
        or record.get("producer") != "designcraft"):
        raise ValueError("SEVEN_TOOL_DESIGNCRAFT_RECEIPT_CHANGED")
    identity = manifest.get("identity_assets")
    if (not isinstance(identity, dict) or set(identity) != {"hazewave", "indionesbala"}):
        raise ValueError("SEVEN_TOOL_OWNER_BRAND_IDENTITY_MISSING")
    canonical = {
        "hazewave": ("media/hazewave-world.jpg", "media/hazewave-world.jpg"),
        "indionesbala": ("media/artists/indionesbala.jpg",
                        "media/artists/indionesbala.webp"),
    }
    public = ROOT / "apps/hazewave-site/public"
    for key, (browser_path, source_path) in canonical.items():
        row = identity[key]
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
            or row["path"] != browser_path
            or sha256(_safe_file(public, source_path)) != row["sha256"]):
            raise ValueError("SEVEN_TOOL_OWNER_IDENTITY_PROVENANCE_MISMATCH")
    for i, item in enumerate(frames):
        expected = f"assets/sonic-portal-{i:02d}.png"
        if (
            not isinstance(item, dict) or set(item) != {"path", "sha256"}
            or item["path"] != expected
            or sha256(_safe_file(root, expected)) != item["sha256"]
        ):
            raise ValueError("SEVEN_TOOL_FX_FRAME_HASH_CHANGED")
    return manifest


def main() -> int:
    cli = argparse.ArgumentParser()
    actions = cli.add_subparsers(dest="action", required=True)
    build = actions.add_parser("assemble")
    for name in ("image", "editorial", "vector", "motion"):
        build.add_argument("--" + name, type=Path, required=True)
    for action in (build, actions.add_parser("verify")):
        action.add_argument("--output", type=Path, required=True)
        action.add_argument("--run-id", required=True)
        action.add_argument("--head-sha", required=True)
    args = cli.parse_args()
    if args.action == "assemble":
        assemble(image=args.image, editorial=args.editorial,
                 vector=args.vector, motion=args.motion,
                 output=args.output, run_id=args.run_id, head_sha=args.head_sha)
    else:
        verify_bundle(args.output, run_id=args.run_id, head_sha=args.head_sha)
    print("HAZEWAVE_SEVEN_REAL_CLIS_ONE_RUN_VERIFIED=PASS")
    print("HAZEWAVE_SITE_OWNER_MEDIA=NOT_CONNECTED")
    print("HAZEWAVE_PUBLICATION=FORBIDDEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
