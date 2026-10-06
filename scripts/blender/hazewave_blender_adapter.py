from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
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
fixture_root.mkdir(parents=True, exist_ok=True)

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


handlers = {
    "animation.scene.inspect": handle_scene_inspect,
    "animation.fixture.create": handle_fixture_create,
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
