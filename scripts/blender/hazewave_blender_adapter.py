from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

import bpy


BLENDER_EXPECTED_VERSION = "5.2.2"
REQUEST_SCHEMA = "BlenderExecutionRequest/v1"
RESPONSE_SCHEMA = "BlenderExecutionReceipt/v1"

root = Path(
    os.environ.get(
        "HAZEWAVE_BLENDER_ROOT",
        str(Path.home() / ".local" / "state" / "hazewave" / "blender"),
    )
).expanduser().resolve()
fixture_root = root / "fixtures"
frame_root = root / "frames"
fixture_root.mkdir(parents=True, exist_ok=True)
frame_root.mkdir(parents=True, exist_ok=True)

_FIXTURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def scene_identity(scene) -> str:
    value = scene.get("hazewave_scene_identity")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return scene.name


def current_snapshot() -> dict:
    scene = bpy.context.scene
    blend_raw = bpy.data.filepath
    blend_path = Path(blend_raw).expanduser().resolve() if blend_raw else None
    blend_sha256 = (
        sha256_file(blend_path)
        if blend_path is not None and blend_path.is_file()
        else "UNSAVED"
    )

    objects = []
    grease_pencil_objects = []
    cameras = []
    for obj in sorted(scene.objects, key=lambda item: item.name):
        objects.append(
            {
                "name": obj.name,
                "type": obj.type,
                "visible_render": not bool(obj.hide_render),
            }
        )
        if obj.type == "GREASEPENCIL":
            grease_pencil_objects.append(obj.name)
        if obj.type == "CAMERA":
            cameras.append(obj.name)

    dependencies = []
    for library in bpy.data.libraries:
        if library.filepath:
            dependencies.append(str(Path(bpy.path.abspath(library.filepath)).resolve()))

    fps = float(scene.render.fps) / float(scene.render.fps_base or 1.0)
    return {
        "schema": "BlenderSceneSnapshot/v1",
        "blender_version": bpy.app.version_string,
        "blend_path": str(blend_path) if blend_path is not None else "",
        "blend_sha256": blend_sha256,
        "scene_identity": scene_identity(scene),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "fps": fps,
        "resolution_x": int(scene.render.resolution_x),
        "resolution_y": int(scene.render.resolution_y),
        "resolution_percentage": int(scene.render.resolution_percentage),
        "render_engine": str(scene.render.engine),
        "view_transform": str(scene.view_settings.view_transform),
        "look": str(scene.view_settings.look),
        "display_device": str(scene.display_settings.display_device),
        "objects": objects,
        "grease_pencil_objects": grease_pencil_objects,
        "cameras": cameras,
        "dependencies": dependencies,
    }


def validate_common(request: dict) -> None:
    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        raise RuntimeError("BLENDER_REQUEST_SCHEMA_INVALID")
    for key in (
        "request_id",
        "task_id",
        "authorization_id",
        "idempotency_key",
        "operation",
        "expected_blender_version",
        "expected_scene_identity",
        "expected_blend_sha256",
    ):
        if not isinstance(request.get(key), str) or not request[key]:
            raise RuntimeError(f"BLENDER_REQUEST_FIELD_REQUIRED:{key}")
    if not isinstance(request.get("arguments"), dict):
        raise RuntimeError("BLENDER_REQUEST_ARGUMENTS_MALFORMED")
    if not isinstance(request.get("seed"), int) or request["seed"] < 0:
        raise RuntimeError("BLENDER_REQUEST_SEED_INVALID")
    if not isinstance(request.get("deadline_epoch_seconds"), (int, float)):
        raise RuntimeError("BLENDER_REQUEST_DEADLINE_INVALID")
    if time.time() > float(request["deadline_epoch_seconds"]):
        raise RuntimeError("BLENDER_REQUEST_DEADLINE_EXCEEDED")
    if request["expected_blender_version"] != BLENDER_EXPECTED_VERSION:
        raise RuntimeError("BLENDER_VERSION_NOT_QUALIFIED")
    if bpy.app.version_string != BLENDER_EXPECTED_VERSION:
        raise RuntimeError("BLENDER_VERSION_MISMATCH")


def validate_existing_scene(request: dict, snapshot: dict) -> None:
    if snapshot["scene_identity"] != request["expected_scene_identity"]:
        raise RuntimeError("BLENDER_SCENE_IDENTITY_MISMATCH")
    if snapshot["blend_sha256"] != request["expected_blend_sha256"]:
        raise RuntimeError("BLENDER_BLEND_STATE_STALE")


def handle_scene_inspect(request: dict) -> dict:
    before = current_snapshot()
    validate_existing_scene(request, before)
    return {
        "state_before": before,
        "state_after": before,
        "result": {"snapshot": before},
    }


def handle_fixture_create(request: dict) -> dict:
    args = request["arguments"]
    if set(args) != {"fixture_id"}:
        raise RuntimeError("BLENDER_FIXTURE_ARGUMENTS_INVALID")
    fixture_id = args["fixture_id"]
    if not isinstance(fixture_id, str) or not _FIXTURE_ID_RE.fullmatch(fixture_id):
        raise RuntimeError("BLENDER_FIXTURE_ID_INVALID")

    output = (fixture_root / f"{fixture_id}.blend").resolve()
    try:
        output.relative_to(fixture_root.resolve())
    except ValueError as exc:
        raise RuntimeError("BLENDER_FIXTURE_PATH_OUTSIDE_ROOT") from exc
    if output.exists():
        raise RuntimeError("BLENDER_FIXTURE_ALREADY_EXISTS")

    before = current_snapshot()
    scene = bpy.context.scene
    scene.name = fixture_id
    scene["hazewave_scene_identity"] = request["expected_scene_identity"]
    scene.frame_start = 1
    scene.frame_end = 48
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE_NEXT"

    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("BLENDER_FIXTURE_SAVE_FAILED")

    after = current_snapshot()
    if after["scene_identity"] != request["expected_scene_identity"]:
        raise RuntimeError("BLENDER_FIXTURE_IDENTITY_MISMATCH")

    return {
        "state_before": before,
        "state_after": after,
        "result": {
            "fixture_path": str(output),
            "snapshot": after,
        },
    }


def handle_shot_build(request: dict) -> dict:
    before = current_snapshot()
    validate_existing_scene(request, before)
    args = request["arguments"]

    shot_id = safe_id(args.get("shot_id"), "BLENDER_SHOT_ID_INVALID")
    frame_start = int(args["frame_start"])
    breakdown_frame = int(args["breakdown_frame"])
    frame_end = int(args["frame_end"])
    if not (1 <= frame_start < breakdown_frame < frame_end <= 10000):
        raise RuntimeError("BLENDER_SHOT_FRAME_RANGE_INVALID")

    character_name = str(args.get("character_name") or "").strip()
    background_name = str(args.get("background_name") or "").strip()
    if not character_name or not background_name:
        raise RuntimeError("BLENDER_SHOT_NAME_INVALID")

    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene["hazewave_shot_id"] = shot_id

    if bpy.data.objects.get(character_name) is not None:
        raise RuntimeError("BLENDER_SHOT_CHARACTER_ALREADY_EXISTS")
    if bpy.data.objects.get(background_name) is not None:
        raise RuntimeError("BLENDER_SHOT_BACKGROUND_ALREADY_EXISTS")
    if bpy.data.objects.get("HazewaveCamera") is not None:
        raise RuntimeError("BLENDER_SHOT_CAMERA_ALREADY_EXISTS")

    grease_pencil = bpy.data.grease_pencils.new(character_name + "Data")
    character = bpy.data.objects.new(character_name, grease_pencil)
    scene.collection.objects.link(character)
    ensure_gp_material(grease_pencil, "HazewaveInk")
    layer = grease_pencil.layers.new("Character", set_active=True)

    make_character_frame(layer, frame_start, "EXTREME", -0.35)
    make_character_frame(layer, breakdown_frame, "BREAKDOWN", 0.0)
    make_character_frame(layer, frame_end, "EXTREME", 0.35)

    background = create_background(background_name)
    camera = create_camera()

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    after = current_snapshot()
    if character_name not in after["grease_pencil_objects"]:
        raise RuntimeError("BLENDER_GREASE_PENCIL_OBJECT_MISSING")
    if "HazewaveCamera" not in after["cameras"]:
        raise RuntimeError("BLENDER_CAMERA_MISSING")

    return {
        "state_before": before,
        "state_after": after,
        "result": {
            "shot_id": shot_id,
            "character_object": character.name,
            "background_object": background.name,
            "camera_object": camera.name,
            "keyframes": [frame_start, breakdown_frame, frame_end],
            "keyframe_types": ["EXTREME", "BREAKDOWN", "EXTREME"],
            "snapshot": after,
        },
    }


def frame_sha256(path: Path) -> str:
    return sha256_file(path)


def handle_render_frames(request: dict) -> dict:
    before = current_snapshot()
    validate_existing_scene(request, before)
    args = request["arguments"]
    render_id = safe_id(args.get("render_id"), "BLENDER_RENDER_ID_INVALID")
    if args.get("format") != "PNG":
        raise RuntimeError("BLENDER_FRAME_RENDER_FORMAT_INVALID")
    frame_start = int(args["frame_start"])
    frame_end = int(args["frame_end"])
    if not (1 <= frame_start <= frame_end <= 10000):
        raise RuntimeError("BLENDER_FRAME_RENDER_RANGE_INVALID")

    output_dir = (frame_root / render_id).resolve()
    try:
        output_dir.relative_to(frame_root.resolve())
    except ValueError as exc:
        raise RuntimeError("BLENDER_FRAME_RENDER_PATH_OUTSIDE_ROOT") from exc
    if output_dir.exists():
        raise RuntimeError("BLENDER_FRAME_RENDER_ALREADY_EXISTS")
    output_dir.mkdir(parents=True, exist_ok=False)

    scene = bpy.context.scene
    saved = {
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "filepath": scene.render.filepath,
        "format": scene.render.image_settings.file_format,
    }
    try:
        scene.frame_start = frame_start
        scene.frame_end = frame_end
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(output_dir / "frame-")
        bpy.ops.render.render(animation=True)
    finally:
        scene.frame_start = saved["frame_start"]
        scene.frame_end = saved["frame_end"]
        scene.render.filepath = saved["filepath"]
        scene.render.image_settings.file_format = saved["format"]

    frame_files = sorted(output_dir.glob("frame-*.png"))
    expected_count = frame_end - frame_start + 1
    if not frame_files:
        raise RuntimeError("ANIMATION_FRAME_SEQUENCE_MISSING")
    if len(frame_files) != expected_count:
        raise RuntimeError("ANIMATION_FRAME_SEQUENCE_GAP")

    numbers = []
    frames = []
    for path in frame_files:
        match = re.search(r"(\\d+)\\.png$", path.name)
        if match is None:
            raise RuntimeError("ANIMATION_FRAME_SEQUENCE_NAME_INVALID")
        frame_number = int(match.group(1))
        numbers.append(frame_number)
        frames.append(
            {
                "frame_number": frame_number,
                "path": str(path),
                "sha256": frame_sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if numbers != list(range(frame_start, frame_end + 1)):
        raise RuntimeError("ANIMATION_FRAME_SEQUENCE_GAP")
    if any(item["size_bytes"] <= 0 for item in frames):
        raise RuntimeError("ANIMATION_FRAME_SEQUENCE_EMPTY_FRAME")

    after = current_snapshot()
    if after["blend_sha256"] != before["blend_sha256"]:
        raise RuntimeError("BLENDER_FRAME_RENDER_MUTATED_BLEND")

    return {
        "state_before": before,
        "state_after": after,
        "result": {
            "render_id": render_id,
            "format": "PNG",
            "frame_start": frame_start,
            "frame_end": frame_end,
            "frame_count": len(frames),
            "frames": frames,
        },
    }


handlers = {
    "animation.scene.inspect": handle_scene_inspect,
    "animation.fixture.create": handle_fixture_create,
    "animation.shot.build": handle_shot_build,
    "animation.render.frames": handle_render_frames,
}


def response_base(request: dict) -> dict:
    return {
        "schema": RESPONSE_SCHEMA,
        "request_id": str(request.get("request_id") or ""),
        "task_id": str(request.get("task_id") or ""),
        "operation": str(request.get("operation") or ""),
        "status": "FAIL",
        "blender_version": bpy.app.version_string,
        "state_before": {},
        "state_after": {},
        "result": {},
        "error": None,
        "started_at": utc_now(),
        "completed_at": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    args = parser.parse_args()

    request_path = Path(args.request).expanduser().resolve()
    response_path = Path(args.response).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = response_base(request)

    try:
        validate_common(request)
        if request["operation"] not in handlers:
            raise RuntimeError("BLENDER_OPERATION_NOT_ALLOWLISTED")
        outcome = handlers[request["operation"]](request)
        response["status"] = "PASS"
        response["state_before"] = outcome["state_before"]
        response["state_after"] = outcome["state_after"]
        response["result"] = outcome["result"]
    except Exception as exc:
        response["status"] = "FAIL"
        response["error"] = {"code": str(exc)}
        try:
            response["state_after"] = current_snapshot()
        except Exception:
            response["state_after"] = {}
    response["completed_at"] = utc_now()
    atomic_write_json(response_path, response)
    return 0 if response["status"] == "PASS" else 20


if __name__ == "__main__":
    raise SystemExit(main())
