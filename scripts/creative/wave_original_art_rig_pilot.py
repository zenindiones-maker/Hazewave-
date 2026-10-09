"""Experimental, owner-art-only real physical layer extraction.

This module does not modify input PNGs, install packages or grant approval.
Pillow, NumPy, cv2 are opt-in preexisting dependencies (no auto-install).
Manually review masks and inpaint holes before making any production claims.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import shutil

SOURCE_SHA = "460eaf43069e608fc959ca95dd7431330e98ace110752640145d5d711cb8be96"
FOG_SHA = "bc38da43aa8d21100ec116c7247a1613e75b6168e91d656f4be0b7b299320b51"
SHAPE = (1448, 1086)
KNOB = ("encoder_right", [
    (1060,393),(1071,390),(1083,391),(1100,401),
    (1117,414),(1125,430),(1120,459),(1101,483),
    (1084,486),(1066,472),(1051,456),(1049,428),
])


def hash_file(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _decode(path: Path, *, wanted_sha: str, width: int, height: int):
    from PIL import Image
    path = Path(path)
    if not path.is_file() or path.is_symlink() or hash_file(path) != wanted_sha:
        raise ValueError("SOURCE_NOT_APPROVED_OR_SHA_MISMATCH")
    image = Image.open(path)
    if image.size != (width, height) or image.mode != "RGBA":
        raise ValueError("SOURCE_FORMAT_OR_DIMENSIONS_MISMATCH")
    return image.copy()


def masks_for_shape(image, pieces=(KNOB,)):
    """Find nine painted orange pad faces from their actual pixels, not guessed rectangles."""
    import numpy as np
    import cv2
    if tuple(image.size) != SHAPE or image.mode != "RGBA":
        raise ValueError("ONLY_SURVEYED_COORDINATES_ADMITTED")
    data = np.asarray(image)
    r = data[350:580, 520:1100, 0].astype(np.int16)
    g = data[350:580, 520:1100, 1].astype(np.int16)
    b = data[350:580, 520:1100, 2].astype(np.int16)
    threshold = np.uint8((r > 185) & (g > 105) & (b < 155) & (r > g + 30)) * 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats(threshold, 8)
    components = []
    for index in range(1, n):
        x, y, w, h, area = map(int, stats[index])
        if 1500 <= area <= 5500 and 105 <= w <= 150 and 25 <= h <= 70:
            components.append((index, x + 520, y + 350, w, h, area))
    if len(components) != 9:
        raise ValueError("PAD_COMPONENT_COUNT_MISMATCH")
    components.sort(key=lambda item: item[2])
    masks = {}
    for row in range(3):
        group = sorted(components[row * 3:row * 3 + 3], key=lambda item: item[1])
        for col, (index, x, y, width, height, area) in enumerate(group):
            local = np.uint8(labels == index) * 255
            local = cv2.dilate(local, np.ones((7, 7), np.uint8), iterations=1)
            mask = np.zeros((SHAPE[1], SHAPE[0]), dtype=np.uint8)
            mask[350:580, 520:1100] = local
            masks[f"p{row}{col}"] = mask
    for name, polygon in pieces:
        mask = np.zeros((SHAPE[1], SHAPE[0]), dtype=np.uint8)
        cv2.fillPoly(mask, [np.asarray(polygon, dtype=np.int32)], 255)
        masks[name] = mask
    seen = np.zeros((SHAPE[1], SHAPE[0]), dtype=np.uint8)
    for name, mask in masks.items():
        if cv2.countNonZero(mask) < 350 or cv2.countNonZero(cv2.bitwise_and(seen, mask)) > 30:
            raise ValueError("PIECE_GEOMETRY_OVERLAPS")
        seen = cv2.bitwise_or(seen, mask)
    return masks


def extract(source: Path, fog: Path, output: Path) -> dict:
    import cv2
    import numpy as np
    from PIL import Image, ImageFilter
    source, fog = Path(source), Path(fog)
    src = _decode(source, wanted_sha=SOURCE_SHA, width=1448, height=1086)
    nebula = _decode(fog, wanted_sha=FOG_SHA, width=1672, height=941)
    out = Path(output).expanduser().resolve(strict=False)
    if out.exists() or out.is_relative_to(source.resolve().parent):
        raise ValueError("OUTPUT_LOCATION_DENIED_OR_NOT_EMPTY")
    array = np.asarray(src)
    masks = masks_for_shape(src)
    hole = np.zeros(array.shape[:2], dtype=np.uint8)
    out.mkdir(mode=0o700, parents=True)
    pieces = []
    for name, mask in masks.items():
        hole = cv2.bitwise_or(hole, mask)
        ys, xs = np.where(mask > 0)
        x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
        feather = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(radius=0.6))
        alpha = np.asarray(feather, dtype=np.uint16)
        region = array[y0:y1, x0:x1].copy()
        region[:, :, 3] = (
            region[:, :, 3].astype("uint16") * alpha[y0:y1, x0:x1] // 255
        ).astype("uint8")
        name_png = f"{name}.png"
        file_path = out / name_png
        Image.fromarray(region, mode="RGBA").save(file_path, optimize=True)
        pieces.append({
            "id": name, "x": x0, "y": y0,
            "width": x1 - x0, "height": y1 - y0,
            "sha256": hash_file(file_path), "path": name_png,
            "pixels_masked": int((mask > 0).sum()),
        })
    # Reconstructed occluded area, NOT owner-approved original pixels.
    expanded = cv2.dilate(hole, np.ones((7, 7), np.uint8), iterations=1)
    rgb = cv2.inpaint(array[:, :, :3], expanded, 8, cv2.INPAINT_TELEA)
    alpha = cv2.inpaint(array[:, :, 3], expanded, 8, cv2.INPAINT_TELEA)
    clean = np.dstack((rgb, alpha))
    Image.fromarray(clean, mode="RGBA").save(
        out / "controller-cleanplate-EXPERIMENTAL.png", optimize=True
    )
    shutil.copyfile(source, out / "controller-original.png")
    shutil.copyfile(fog, out / "fog-original.png")
    manifest = {
        "schema": "HazewaveWaveRigPilot/v1",
        "authority": "NONE",
        "source_art_sha256": SOURCE_SHA,
        "fog_art_sha256": FOG_SHA,
        "source_format": "PNG/RGBA",
        "coordinates_space": list(SHAPE),
        "individual_art_pieces": len(pieces),
        "pieces": pieces,
        "source_byte_identity_checked": True,
        "cleanplate_status": "EXPERIMENTAL_CV2_INPAINT_HUMAN_NOT_APPROVED",
        "mask_geometry_status": "PROVISIONAL_PIXEL_COMPONENT_SEGMENTATION",
        "independent_pads_visual_qa": "PENDING",
        "independent_knob_visual_qa": "PENDING",
        "production_approved": False,
        "codespace_runtime_attested": False,
        "mcp_agent_connected": False,
        "external_sites_reverse_engineered": False,
        "generated": {
            name: hash_file(out / name)
            for name in (
                "controller-original.png",
                "controller-cleanplate-EXPERIMENTAL.png",
                "fog-original.png",
            )
        },
    }
    (out / "pilot-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract(args.source, args.fog, args.output)
    except (OSError, ValueError, ImportError) as exc:
        print("WAVE_RIG_PILOT=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("WAVE_RIG_PILOT=EXPERIMENTAL_PIECES_" + str(result["individual_art_pieces"]))
    print("WAVE_RIG_VISUAL_APPROVED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
