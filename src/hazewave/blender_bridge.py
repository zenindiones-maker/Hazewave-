from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Final, Mapping

from hazewave.harness import WAVE, HazewaveAuthorization, validate_authorization


BLENDER_EXPECTED_VERSION: Final = "5.2.2"
BLENDER_REQUEST_SCHEMA: Final = "BlenderExecutionRequest/v1"
BLENDER_RESPONSE_SCHEMA: Final = "BlenderExecutionReceipt/v1"

BLENDER_OPERATION_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "animation.scene.inspect",
        "animation.fixture.create",
        "animation.shot.build",
        "animation.render.frames",
        "animation.render.frames.repair",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FIXTURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class BlenderBridgeError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass(frozen=True)
class BlenderExecutionRequest:
    request_id: str
    task_id: str
    authorization_id: str
    idempotency_key: str
    operation: str
    arguments: Mapping[str, Any]
    expected_blender_version: str
    expected_scene_identity: str
    expected_blend_sha256: str
    seed: int
    issued_at: datetime
    deadline: datetime
    schema: str = BLENDER_REQUEST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "authorization_id": self.authorization_id,
            "idempotency_key": self.idempotency_key,
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "expected_blender_version": self.expected_blender_version,
            "expected_scene_identity": self.expected_scene_identity,
            "expected_blend_sha256": self.expected_blend_sha256,
            "seed": self.seed,
            "issued_at": self.issued_at.isoformat(),
            "deadline": self.deadline.isoformat(),
            "issued_at_epoch_seconds": self.issued_at.timestamp(),
            "deadline_epoch_seconds": self.deadline.timestamp(),
        }


@dataclass(frozen=True)
class BlenderSceneSnapshot:
    blender_version: str
    blend_path: str
    blend_sha256: str
    scene_identity: str
    frame_start: int
    frame_end: int
    fps: float
    resolution_x: int
    resolution_y: int
    resolution_percentage: int
    render_engine: str
    view_transform: str
    look: str
    display_device: str
    objects: tuple[Mapping[str, Any], ...]
    grease_pencil_objects: tuple[str, ...]
    cameras: tuple[str, ...]
    dependencies: tuple[str, ...]
    schema: str = "BlenderSceneSnapshot/v1"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BlenderSceneSnapshot":
        required = {
            "schema",
            "blender_version",
            "blend_path",
            "blend_sha256",
            "scene_identity",
            "frame_start",
            "frame_end",
            "fps",
            "resolution_x",
            "resolution_y",
            "resolution_percentage",
            "render_engine",
            "view_transform",
            "look",
            "display_device",
            "objects",
            "grease_pencil_objects",
            "cameras",
            "dependencies",
        }
        if not isinstance(payload, Mapping) or required.difference(payload):
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        if payload.get("schema") != "BlenderSceneSnapshot/v1":
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        if not isinstance(payload["objects"], (list, tuple)):
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        if not all(isinstance(item, Mapping) for item in payload["objects"]):
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        for name in ("grease_pencil_objects", "cameras", "dependencies"):
            if not isinstance(payload[name], (list, tuple)) or not all(
                isinstance(item, str) for item in payload[name]
            ):
                raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        try:
            frame_start = int(payload["frame_start"])
            frame_end = int(payload["frame_end"])
            fps = float(payload["fps"])
            resolution_x = int(payload["resolution_x"])
            resolution_y = int(payload["resolution_y"])
            resolution_percentage = int(payload["resolution_percentage"])
        except (TypeError, ValueError) as exc:
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED") from exc
        if (
            frame_start < 0
            or frame_end < frame_start
            or fps <= 0
            or resolution_x <= 0
            or resolution_y <= 0
            or not 1 <= resolution_percentage <= 100
        ):
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        blend_sha = str(payload["blend_sha256"])
        if blend_sha and blend_sha != "UNSAVED" and not _SHA256_RE.fullmatch(blend_sha):
            raise BlenderBridgeError("BLENDER_SNAPSHOT_MALFORMED")
        return cls(
            blender_version=str(payload["blender_version"]),
            blend_path=str(payload["blend_path"]),
            blend_sha256=blend_sha,
            scene_identity=str(payload["scene_identity"]),
            frame_start=frame_start,
            frame_end=frame_end,
            fps=fps,
            resolution_x=resolution_x,
            resolution_y=resolution_y,
            resolution_percentage=resolution_percentage,
            render_engine=str(payload["render_engine"]),
            view_transform=str(payload["view_transform"]),
            look=str(payload["look"]),
            display_device=str(payload["display_device"]),
            objects=tuple(dict(item) for item in payload["objects"]),
            grease_pencil_objects=tuple(payload["grease_pencil_objects"]),
            cameras=tuple(payload["cameras"]),
            dependencies=tuple(payload["dependencies"]),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["objects"] = [dict(item) for item in self.objects]
        value["grease_pencil_objects"] = list(self.grease_pencil_objects)
        value["cameras"] = list(self.cameras)
        value["dependencies"] = list(self.dependencies)
        return value


@dataclass(frozen=True)
class PreparedBlenderExecution:
    request_path: Path
    response_path: Path
    command: tuple[str, ...]


def _require_aware(value: datetime, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BlenderBridgeError(code)
    return value.astimezone(timezone.utc)


def build_blender_request(
    *,
    authorization: HazewaveAuthorization,
    request_id: str,
    idempotency_key: str,
    operation: str,
    arguments: Mapping[str, Any],
    expected_blender_version: str,
    expected_scene_identity: str,
    expected_blend_sha256: str,
    seed: int,
    issued_at: datetime,
    deadline: datetime,
) -> BlenderExecutionRequest:
    operation = str(operation or "").strip()
    if operation not in BLENDER_OPERATION_ALLOWLIST:
        raise BlenderBridgeError("BLENDER_OPERATION_NOT_ALLOWLISTED", operation)
    if authorization.domain != WAVE:
        raise BlenderBridgeError("BLENDER_AUTHORIZATION_DOMAIN_MISMATCH")
    if authorization.capability_id != operation:
        raise BlenderBridgeError("BLENDER_AUTHORIZATION_CAPABILITY_MISMATCH")
    try:
        validate_authorization(
            authorization,
            expected_task_id=authorization.task_id,
            expected_capability=operation,
        )
    except (PermissionError, ValueError) as exc:
        raise BlenderBridgeError("BLENDER_AUTHORIZATION_INVALID", str(exc)) from exc

    if not isinstance(arguments, Mapping):
        raise BlenderBridgeError("BLENDER_ARGUMENTS_MALFORMED")
    request_id = str(request_id or "").strip()
    idem = str(idempotency_key or "").strip()
    scene_identity = str(expected_scene_identity or "").strip()
    version = str(expected_blender_version or "").strip()
    if not request_id:
        raise BlenderBridgeError("BLENDER_REQUEST_ID_REQUIRED")
    if not idem:
        raise BlenderBridgeError("BLENDER_IDEMPOTENCY_KEY_REQUIRED")
    if not scene_identity:
        raise BlenderBridgeError("BLENDER_SCENE_IDENTITY_REQUIRED")
    if version != BLENDER_EXPECTED_VERSION:
        raise BlenderBridgeError("BLENDER_VERSION_NOT_QUALIFIED")
    if not _SHA256_RE.fullmatch(str(expected_blend_sha256 or "")):
        raise BlenderBridgeError("BLENDER_BLEND_SHA256_INVALID")
    if not isinstance(seed, int) or seed < 0 or seed > 2**63 - 1:
        raise BlenderBridgeError("BLENDER_SEED_INVALID")

    if operation == "animation.scene.inspect" and arguments:
        raise BlenderBridgeError("BLENDER_SCENE_INSPECT_ARGUMENTS_FORBIDDEN")
    if operation == "animation.fixture.create":
        forbidden = {
            "path",
            "output_path",
            "blend_path",
            "destination",
            "directory",
            "python",
            "script",
            "source",
            "code",
        }
        if forbidden.intersection(arguments):
            raise BlenderBridgeError("BLENDER_FIXTURE_PATH_CALLER_CONTROLLED")
        if set(arguments) != {"fixture_id"}:
            raise BlenderBridgeError("BLENDER_FIXTURE_ARGUMENTS_INVALID")
        fixture_id = arguments.get("fixture_id")
        if not isinstance(fixture_id, str) or not _FIXTURE_ID_RE.fullmatch(fixture_id):
            raise BlenderBridgeError("BLENDER_FIXTURE_ID_INVALID")

    if operation == "animation.shot.build":
        required = {
            "shot_id",
            "frame_start",
            "breakdown_frame",
            "frame_end",
            "character_name",
            "background_name",
        }
        if set(arguments) != required:
            raise BlenderBridgeError("BLENDER_SHOT_ARGUMENTS_INVALID")
        shot_id = arguments.get("shot_id")
        if not isinstance(shot_id, str) or not _FIXTURE_ID_RE.fullmatch(shot_id):
            raise BlenderBridgeError("BLENDER_SHOT_ID_INVALID")
        for name in ("character_name", "background_name"):
            value = arguments.get(name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 128
                or any(ch in value for ch in "\n\r\x00")
            ):
                raise BlenderBridgeError("BLENDER_SHOT_NAME_INVALID")
        try:
            frame_start = int(arguments["frame_start"])
            breakdown_frame = int(arguments["breakdown_frame"])
            frame_end = int(arguments["frame_end"])
        except (TypeError, ValueError) as exc:
            raise BlenderBridgeError("BLENDER_SHOT_FRAME_RANGE_INVALID") from exc
        if not (1 <= frame_start < breakdown_frame < frame_end <= 10000):
            raise BlenderBridgeError("BLENDER_SHOT_FRAME_RANGE_INVALID")

    if operation == "animation.render.frames.repair":
        required = {"render_id", "frame_numbers", "format"}
        if set(arguments) != required:
            raise BlenderBridgeError("BLENDER_FRAME_REPAIR_ARGUMENTS_INVALID")
        render_id = arguments.get("render_id")
        if not isinstance(render_id, str) or not _FIXTURE_ID_RE.fullmatch(render_id):
            raise BlenderBridgeError("BLENDER_RENDER_ID_INVALID")
        if arguments.get("format") != "PNG":
            raise BlenderBridgeError("BLENDER_FRAME_RENDER_FORMAT_INVALID")
        frame_numbers = arguments.get("frame_numbers")
        if (
            not isinstance(frame_numbers, list)
            or not frame_numbers
            or len(frame_numbers) > 120
            or any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in frame_numbers
            )
            or any(value < 1 or value > 10000 for value in frame_numbers)
            or len(set(frame_numbers)) != len(frame_numbers)
            or frame_numbers != sorted(frame_numbers)
        ):
            raise BlenderBridgeError("BLENDER_FRAME_REPAIR_RANGE_INVALID")

    if operation == "animation.render.frames":
        required = {"render_id", "frame_start", "frame_end", "format"}
        if set(arguments) != required:
            raise BlenderBridgeError("BLENDER_FRAME_RENDER_ARGUMENTS_INVALID")
        render_id = arguments.get("render_id")
        if not isinstance(render_id, str) or not _FIXTURE_ID_RE.fullmatch(render_id):
            raise BlenderBridgeError("BLENDER_RENDER_ID_INVALID")
        if arguments.get("format") != "PNG":
            raise BlenderBridgeError("BLENDER_FRAME_RENDER_FORMAT_INVALID")
        try:
            frame_start = int(arguments["frame_start"])
            frame_end = int(arguments["frame_end"])
        except (TypeError, ValueError) as exc:
            raise BlenderBridgeError("BLENDER_FRAME_RENDER_RANGE_INVALID") from exc
        if not (1 <= frame_start <= frame_end <= 10000):
            raise BlenderBridgeError("BLENDER_FRAME_RENDER_RANGE_INVALID")

    issued = _require_aware(issued_at, "BLENDER_ISSUED_AT_INVALID")
    due = _require_aware(deadline, "BLENDER_DEADLINE_INVALID")
    if due <= issued:
        raise BlenderBridgeError("BLENDER_DEADLINE_INVALID")

    return BlenderExecutionRequest(
        request_id=request_id,
        task_id=authorization.task_id,
        authorization_id=authorization.authorization_id,
        idempotency_key=idem,
        operation=operation,
        arguments=dict(arguments),
        expected_blender_version=version,
        expected_scene_identity=scene_identity,
        expected_blend_sha256=str(expected_blend_sha256),
        seed=seed,
        issued_at=issued,
        deadline=due,
    )


class BlenderCLIExecutor:
    def __init__(
        self,
        *,
        root: Path | str,
        blender_binary: Path | str,
        adapter_script: Path | str,
    ) -> None:
        self.root = Path(root)
        self.requests_dir = self.root / "requests"
        self.responses_dir = self.root / "responses"
        self.blender_binary = Path(blender_binary)
        self.adapter_script = Path(adapter_script).expanduser().resolve()
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        if not self.adapter_script.is_file():
            raise BlenderBridgeError("BLENDER_ADAPTER_SCRIPT_MISSING")

    @staticmethod
    def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
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

    def prepare(
        self,
        request: BlenderExecutionRequest,
        *,
        blend_path: Path | str | None = None,
    ) -> PreparedBlenderExecution:
        request_path = self.requests_dir / f"{request.request_id}.json"
        response_path = self.responses_dir / f"{request.request_id}.json"
        if request_path.exists() or response_path.exists():
            raise BlenderBridgeError("BLENDER_DUPLICATE_REQUEST_ID")
        self._atomic_write(request_path, request.to_dict())

        command: list[str] = [str(self.blender_binary), "--background", "--disable-autoexec"]
        if request.operation in {"animation.scene.inspect", "animation.shot.build", "animation.render.frames", "animation.render.frames.repair"}:
            if blend_path is None:
                raise BlenderBridgeError("BLENDER_BLEND_PATH_REQUIRED")
            source = Path(blend_path).expanduser().resolve()
            if not source.is_file():
                raise BlenderBridgeError("BLENDER_BLEND_PATH_NOT_FOUND")
            command.append(str(source))
        else:
            command.append("--factory-startup")
        command += [
            "--python",
            str(self.adapter_script),
            "--",
            "--request",
            str(request_path),
            "--response",
            str(response_path),
        ]
        return PreparedBlenderExecution(
            request_path=request_path,
            response_path=response_path,
            command=tuple(command),
        )

    @staticmethod
    def _default_runner(
        args: list[str],
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise BlenderBridgeError("BLENDER_BINARY_NOT_FOUND") from exc
        except subprocess.TimeoutExpired as exc:
            raise BlenderBridgeError("BLENDER_EXECUTION_TIMEOUT") from exc

    def execute(
        self,
        request: BlenderExecutionRequest,
        *,
        blend_path: Path | str | None = None,
        timeout_seconds: float = 300.0,
        runner: Any | None = None,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or timeout_seconds > 3600:
            raise BlenderBridgeError("BLENDER_EXECUTION_TIMEOUT_INVALID")

        prepared = self.prepare(request, blend_path=blend_path)
        execute = runner or self._default_runner
        try:
            completed = execute(list(prepared.command), timeout_seconds)
        except BlenderBridgeError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise BlenderBridgeError("BLENDER_EXECUTION_TIMEOUT") from exc
        except FileNotFoundError as exc:
            raise BlenderBridgeError("BLENDER_BINARY_NOT_FOUND") from exc
        except Exception as exc:
            raise BlenderBridgeError("BLENDER_EXECUTION_RUNNER_FAILED") from exc

        if not prepared.response_path.is_file():
            raise BlenderBridgeError(
                "BLENDER_RESPONSE_MISSING",
                f"exit={getattr(completed, 'returncode', 'UNKNOWN')}",
            )

        try:
            payload = json.loads(
                prepared.response_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BlenderBridgeError("BLENDER_RESPONSE_MALFORMED") from exc

        parsed = parse_blender_response(payload, request=request)
        if parsed["status"] != "PASS":
            error = parsed.get("error")
            detail = "UNKNOWN"
            if isinstance(error, Mapping):
                value = error.get("code")
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
            raise BlenderBridgeError("BLENDER_EXECUTION_FAILED", detail)

        if getattr(completed, "returncode", 0) != 0:
            raise BlenderBridgeError(
                "BLENDER_PROCESS_EXIT_NONZERO",
                str(completed.returncode),
            )
        return parsed


def parse_blender_response(
    payload: Mapping[str, Any],
    *,
    request: BlenderExecutionRequest,
) -> dict[str, Any]:
    required = {
        "schema",
        "request_id",
        "task_id",
        "operation",
        "status",
        "blender_version",
        "state_before",
        "state_after",
        "result",
        "error",
        "started_at",
        "completed_at",
    }
    if not isinstance(payload, Mapping) or required.difference(payload):
        raise BlenderBridgeError("BLENDER_RESPONSE_MALFORMED")
    if payload.get("schema") != BLENDER_RESPONSE_SCHEMA:
        raise BlenderBridgeError("BLENDER_RESPONSE_SCHEMA_MISMATCH")
    if payload.get("request_id") != request.request_id:
        raise BlenderBridgeError("BLENDER_RESPONSE_REQUEST_MISMATCH")
    if payload.get("task_id") != request.task_id:
        raise BlenderBridgeError("BLENDER_RESPONSE_TASK_MISMATCH")
    if payload.get("operation") != request.operation:
        raise BlenderBridgeError("BLENDER_RESPONSE_OPERATION_MISMATCH")
    if payload.get("blender_version") != request.expected_blender_version:
        raise BlenderBridgeError("BLENDER_VERSION_MISMATCH")
    if payload.get("status") not in {"PASS", "FAIL", "REJECTED"}:
        raise BlenderBridgeError("BLENDER_RESPONSE_STATUS_INVALID")
    if not isinstance(payload.get("state_before"), Mapping):
        raise BlenderBridgeError("BLENDER_RESPONSE_STATE_BEFORE_MALFORMED")
    if not isinstance(payload.get("state_after"), Mapping):
        raise BlenderBridgeError("BLENDER_RESPONSE_STATE_AFTER_MALFORMED")
    if not isinstance(payload.get("result"), Mapping):
        raise BlenderBridgeError("BLENDER_RESPONSE_RESULT_MALFORMED")
    for key in ("started_at", "completed_at"):
        value = payload.get(key)
        if not isinstance(value, str):
            raise BlenderBridgeError("BLENDER_RESPONSE_TIME_INVALID")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise BlenderBridgeError("BLENDER_RESPONSE_TIME_INVALID") from exc
        _require_aware(parsed, "BLENDER_RESPONSE_TIME_INVALID")
    return dict(payload)
