from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any, Final, Mapping

from hazewave.harness import HAZE, HazewaveAuthorization, validate_authorization
from hazewave.reaper_professional_surface import (
    DIRECT_REAPER_CAPABILITIES,
    INTERNAL_REAPER_OPERATIONS,
)


REAPER_REQUEST_SCHEMA: Final = "ReaperExecutionRequest/v1"
REAPER_RESPONSE_SCHEMA: Final = "ReaperExecutionResponse/v1"
REAPER_HEARTBEAT_SCHEMA: Final = "ReaperBridgeHeartbeat/v1"

REAPER_OPERATION_ALLOWLIST: Final[frozenset[str]] = frozenset(
    (*DIRECT_REAPER_CAPABILITIES, *INTERNAL_REAPER_OPERATIONS)
)

REAPER_READ_ONLY_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        "session.inspect",
        "fx.inventory",
        "fx.parameter.read",
        "audio.analyze",
        "audio.compare",
        "audio.qc",
    }
)

_ALLOWED_RESPONSE_STATUSES: Final[frozenset[str]] = frozenset(
    {"PASS", "FAIL", "REJECTED", "ROLLED_BACK", "PARTIAL"}
)


class ReaperBridgeError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass(frozen=True)
class ReaperProjectSnapshot:
    project_identity: str
    project_state_change_count: int
    dirty: bool
    project_path: str = ""
    sample_rate: int = 0
    tempo: float = 0.0
    time_signature: Mapping[str, int] | None = None
    project_length: float = 0.0
    markers: tuple[Mapping[str, Any], ...] = ()
    regions: tuple[Mapping[str, Any], ...] = ()
    tracks: tuple[Mapping[str, Any], ...] = ()
    items: tuple[Mapping[str, Any], ...] = ()
    routing: tuple[Mapping[str, Any], ...] = ()
    fx: tuple[Mapping[str, Any], ...] = ()
    schema: str = "ReaperProjectSnapshot/v1"

    def __post_init__(self) -> None:
        if not self.project_identity.strip():
            raise ReaperBridgeError("REAPER_PROJECT_IDENTITY_REQUIRED")
        if self.project_state_change_count < 0:
            raise ReaperBridgeError("REAPER_PROJECT_STATE_INVALID")
        if self.sample_rate < 0 or self.tempo < 0 or self.project_length < 0:
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReaperProjectSnapshot":
        required = {
            "schema",
            "project_identity",
            "project_path",
            "project_state_change_count",
            "dirty",
            "sample_rate",
            "tempo",
            "time_signature",
            "project_length",
            "markers",
            "regions",
            "tracks",
            "items",
            "routing",
            "fx",
        }
        if not isinstance(payload, Mapping) or required.difference(payload):
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED")
        if payload.get("schema") != "ReaperProjectSnapshot/v1":
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED")

        collections = ("markers", "regions", "tracks", "items", "routing", "fx")
        for name in collections:
            value = payload.get(name)
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(item, Mapping) for item in value
            ):
                raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED", name)
        time_signature = payload.get("time_signature")
        if (
            not isinstance(time_signature, Mapping)
            or not isinstance(time_signature.get("numerator"), int)
            or not isinstance(time_signature.get("denominator"), int)
            or time_signature["numerator"] <= 0
            or time_signature["denominator"] <= 0
        ):
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED", "time_signature")
        try:
            sample_rate = int(payload["sample_rate"])
            tempo = float(payload["tempo"])
            project_length = float(payload["project_length"])
            state_count = int(payload["project_state_change_count"])
        except (TypeError, ValueError) as exc:
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED") from exc
        if sample_rate <= 0 or tempo <= 0 or project_length < 0 or state_count < 0:
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED")

        identity = str(payload["project_identity"] or "").strip()
        project_path = str(payload["project_path"] or "").strip()
        if not identity:
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED", "project_identity")
        if not isinstance(payload["dirty"], bool):
            raise ReaperBridgeError("REAPER_SNAPSHOT_MALFORMED", "dirty")

        return cls(
            project_identity=identity,
            project_path=project_path,
            project_state_change_count=state_count,
            dirty=payload["dirty"],
            sample_rate=sample_rate,
            tempo=tempo,
            time_signature=dict(time_signature),
            project_length=project_length,
            markers=tuple(dict(item) for item in payload["markers"]),
            regions=tuple(dict(item) for item in payload["regions"]),
            tracks=tuple(dict(item) for item in payload["tracks"]),
            items=tuple(dict(item) for item in payload["items"]),
            routing=tuple(dict(item) for item in payload["routing"]),
            fx=tuple(dict(item) for item in payload["fx"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_identity": self.project_identity,
            "project_path": self.project_path,
            "project_state_change_count": self.project_state_change_count,
            "dirty": self.dirty,
            "sample_rate": self.sample_rate,
            "tempo": self.tempo,
            "time_signature": dict(self.time_signature or {}),
            "project_length": self.project_length,
            "markers": [dict(item) for item in self.markers],
            "regions": [dict(item) for item in self.regions],
            "tracks": [dict(item) for item in self.tracks],
            "items": [dict(item) for item in self.items],
            "routing": [dict(item) for item in self.routing],
            "fx": [dict(item) for item in self.fx],
        }


@dataclass(frozen=True)
class ReaperExecutionRequest:
    request_id: str
    task_id: str
    authorization_id: str
    idempotency_key: str
    operation: str
    arguments: Mapping[str, Any]
    expected_project_identity: str
    expected_project_state_change_count: int
    deadline: datetime
    issued_at: datetime
    schema: str = REAPER_REQUEST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "authorization_id": self.authorization_id,
            "idempotency_key": self.idempotency_key,
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "expected_project_identity": self.expected_project_identity,
            "expected_project_state_change_count": self.expected_project_state_change_count,
            "deadline": self.deadline.isoformat(),
            "issued_at": self.issued_at.isoformat(),
            "deadline_epoch_seconds": self.deadline.timestamp(),
            "issued_at_epoch_seconds": self.issued_at.timestamp(),
        }


def _require_aware(value: datetime, *, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReaperBridgeError(code)
    return value.astimezone(timezone.utc)


def _parse_aware(value: object, *, code: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReaperBridgeError(code)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReaperBridgeError(code) from exc
    return _require_aware(parsed, code=code)


def build_reaper_request(
    *,
    authorization: HazewaveAuthorization,
    request_id: str,
    idempotency_key: str,
    operation: str,
    arguments: Mapping[str, Any],
    expected_project_identity: str,
    expected_project_state_change_count: int,
    issued_at: datetime,
    deadline: datetime,
) -> ReaperExecutionRequest:
    operation = str(operation or "").strip()
    if operation not in REAPER_OPERATION_ALLOWLIST:
        raise ReaperBridgeError("REAPER_OPERATION_NOT_ALLOWLISTED", operation)
    if authorization.domain != HAZE:
        raise ReaperBridgeError("REAPER_AUTHORIZATION_DOMAIN_MISMATCH")
    if authorization.capability_id != operation:
        raise ReaperBridgeError("REAPER_AUTHORIZATION_CAPABILITY_MISMATCH")
    try:
        validate_authorization(
            authorization,
            expected_task_id=authorization.task_id,
            expected_capability=operation,
        )
    except (PermissionError, ValueError) as exc:
        raise ReaperBridgeError("REAPER_AUTHORIZATION_INVALID", str(exc)) from exc

    request_id = str(request_id or "").strip()
    idempotency_key = str(idempotency_key or "").strip()
    project_identity = str(expected_project_identity or "").strip()
    if not request_id:
        raise ReaperBridgeError("REAPER_REQUEST_ID_REQUIRED")
    if not idempotency_key:
        raise ReaperBridgeError("REAPER_IDEMPOTENCY_KEY_REQUIRED")
    if not project_identity:
        raise ReaperBridgeError("REAPER_PROJECT_IDENTITY_REQUIRED")
    if expected_project_state_change_count < 0:
        raise ReaperBridgeError("REAPER_EXPECTED_STATE_INVALID")
    if not isinstance(arguments, Mapping):
        raise ReaperBridgeError("REAPER_ARGUMENTS_MALFORMED")

    if operation == "session.checkpoint":
        caller_path_keys = {"path", "output_path", "checkpoint_path", "destination"}
        if caller_path_keys.intersection(arguments):
            raise ReaperBridgeError("REAPER_CHECKPOINT_PATH_CALLER_CONTROLLED")
    if operation in {"render.preview", "render.master", "render.stems"}:
        caller_path_keys = {"path", "output_path", "render_path", "destination", "directory"}
        if caller_path_keys.intersection(arguments):
            raise ReaperBridgeError("REAPER_RENDER_PATH_CALLER_CONTROLLED")
    if operation == "session.fixture.open":
        forbidden_fixture_keys = {
            "path",
            "project_path",
            "fixture_path",
            "output_path",
            "destination",
            "directory",
        }
        if forbidden_fixture_keys.intersection(arguments):
            raise ReaperBridgeError("REAPER_FIXTURE_PATH_CALLER_CONTROLLED")
        if set(arguments) != {"fixture_id"}:
            raise ReaperBridgeError("REAPER_FIXTURE_ARGUMENTS_INVALID")
        fixture_id = arguments.get("fixture_id")
        if (
            not isinstance(fixture_id, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", fixture_id)
        ):
            raise ReaperBridgeError("REAPER_FIXTURE_ID_INVALID")
    if operation == "session.fixture.close" and arguments:
        raise ReaperBridgeError("REAPER_FIXTURE_CLOSE_ARGUMENTS_FORBIDDEN")
    if operation == "session.rollback":
        expected_undo = arguments.get("expected_undo_description")
        if not isinstance(expected_undo, str) or not expected_undo.strip():
            raise ReaperBridgeError("REAPER_ROLLBACK_EXPECTED_UNDO_REQUIRED")
        expected_undo = expected_undo.strip()
        if (
            not expected_undo.startswith("Hazewave: ")
            or "[" not in expected_undo
            or not expected_undo.endswith("]")
            or "\n" in expected_undo
            or "\r" in expected_undo
            or len(expected_undo) > 512
        ):
            raise ReaperBridgeError("REAPER_ROLLBACK_EXPECTED_UNDO_NOT_HAZEWAVE")

    issued = _require_aware(issued_at, code="REAPER_ISSUED_AT_INVALID")
    due = _require_aware(deadline, code="REAPER_DEADLINE_INVALID")
    if due <= issued:
        raise ReaperBridgeError("REAPER_DEADLINE_INVALID")

    return ReaperExecutionRequest(
        request_id=request_id,
        task_id=authorization.task_id,
        authorization_id=authorization.authorization_id,
        idempotency_key=idempotency_key,
        operation=operation,
        arguments=dict(arguments),
        expected_project_identity=project_identity,
        expected_project_state_change_count=expected_project_state_change_count,
        deadline=due,
        issued_at=issued,
    )


def preflight_mutation(
    request: ReaperExecutionRequest,
    snapshot: ReaperProjectSnapshot,
) -> None:
    if snapshot.project_identity != request.expected_project_identity:
        raise ReaperBridgeError("REAPER_PROJECT_IDENTITY_MISMATCH")
    if (
        snapshot.project_state_change_count
        != request.expected_project_state_change_count
    ):
        raise ReaperBridgeError("REAPER_STATE_STALE")


class BridgeHeartbeat:
    def __init__(self, path: Path | str, *, max_age_seconds: float) -> None:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        self.path = Path(path)
        self.max_age_seconds = float(max_age_seconds)

    def require_fresh(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = _require_aware(
            now or datetime.now(timezone.utc),
            code="REAPER_HEARTBEAT_NOW_INVALID",
        )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ReaperBridgeError("REAPER_BRIDGE_HEARTBEAT_MISSING") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ReaperBridgeError("REAPER_BRIDGE_HEARTBEAT_MALFORMED") from exc

        if not isinstance(payload, dict) or payload.get("schema") != REAPER_HEARTBEAT_SCHEMA:
            raise ReaperBridgeError("REAPER_BRIDGE_HEARTBEAT_MALFORMED")
        updated_at = _parse_aware(
            payload.get("updated_at"),
            code="REAPER_BRIDGE_HEARTBEAT_MALFORMED",
        )
        age_seconds = (current - updated_at).total_seconds()
        if age_seconds < -5:
            raise ReaperBridgeError("REAPER_BRIDGE_HEARTBEAT_FUTURE")
        if age_seconds > self.max_age_seconds:
            raise ReaperBridgeError("REAPER_BRIDGE_HEARTBEAT_STALE")
        return payload


class FilesystemReaperBridge:
    def __init__(
        self,
        root: Path | str,
        *,
        heartbeat_max_age_seconds: float = 5.0,
    ) -> None:
        self.root = Path(root)
        self.requests_dir = self.root / "requests"
        self.responses_dir = self.root / "responses"
        self.idempotency_dir = self.root / "idempotency"
        self.heartbeat_path = self.root / "heartbeat.json"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self.idempotency_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat = BridgeHeartbeat(
            self.heartbeat_path,
            max_age_seconds=heartbeat_max_age_seconds,
        )

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @classmethod
    def _atomic_write_json(cls, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_name = handle.name
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            cls._fsync_dir(path.parent)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _reserve_idempotency_key(self, request: ReaperExecutionRequest) -> Path:
        digest = sha256(request.idempotency_key.encode("utf-8")).hexdigest()
        marker = self.idempotency_dir / f"{digest}.json"
        payload = {
            "schema": "ReaperIdempotencyReservation/v1",
            "idempotency_key_sha256": digest,
            "request_id": request.request_id,
            "task_id": request.task_id,
            "operation": request.operation,
            "status": "RESERVED",
        }
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise ReaperBridgeError("REAPER_DUPLICATE_IDEMPOTENCY_KEY") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._fsync_dir(marker.parent)
        except Exception:
            # A durable reservation is intentionally left in place when the
            # outcome is uncertain. Retrying the same key must fail closed.
            raise
        return marker

    def submit(
        self,
        request: ReaperExecutionRequest,
        *,
        now: datetime | None = None,
    ) -> Path:
        current = _require_aware(
            now or datetime.now(timezone.utc),
            code="REAPER_SUBMIT_TIME_INVALID",
        )
        self.heartbeat.require_fresh(now=current)
        if current > request.deadline:
            raise ReaperBridgeError("REAPER_REQUEST_DEADLINE_EXCEEDED")

        path = self.requests_dir / f"{request.request_id}.json"
        if path.exists():
            raise ReaperBridgeError("REAPER_DUPLICATE_REQUEST_ID")

        self._reserve_idempotency_key(request)
        self._atomic_write_json(path, request.to_dict())
        return path


def parse_reaper_response(
    payload: Mapping[str, Any],
    *,
    request: ReaperExecutionRequest,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReaperBridgeError("REAPER_RESPONSE_MALFORMED")
    required = {
        "schema",
        "request_id",
        "task_id",
        "operation",
        "status",
        "state_before",
        "state_after",
        "result",
        "error",
        "started_at",
        "completed_at",
    }
    if required.difference(payload):
        raise ReaperBridgeError("REAPER_RESPONSE_MALFORMED")
    if payload.get("schema") != REAPER_RESPONSE_SCHEMA:
        raise ReaperBridgeError("REAPER_RESPONSE_SCHEMA_MISMATCH")
    if payload.get("request_id") != request.request_id:
        raise ReaperBridgeError("REAPER_RESPONSE_REQUEST_MISMATCH")
    if payload.get("task_id") != request.task_id:
        raise ReaperBridgeError("REAPER_RESPONSE_TASK_MISMATCH")
    if payload.get("operation") != request.operation:
        raise ReaperBridgeError("REAPER_RESPONSE_OPERATION_MISMATCH")
    if payload.get("status") not in _ALLOWED_RESPONSE_STATUSES:
        raise ReaperBridgeError("REAPER_RESPONSE_STATUS_INVALID")
    if not isinstance(payload.get("state_before"), Mapping):
        raise ReaperBridgeError("REAPER_RESPONSE_STATE_BEFORE_MALFORMED")
    if not isinstance(payload.get("state_after"), Mapping):
        raise ReaperBridgeError("REAPER_RESPONSE_STATE_AFTER_MALFORMED")
    if not isinstance(payload.get("result"), Mapping):
        raise ReaperBridgeError("REAPER_RESPONSE_RESULT_MALFORMED")
    _parse_aware(payload.get("started_at"), code="REAPER_RESPONSE_STARTED_AT_INVALID")
    _parse_aware(
        payload.get("completed_at"),
        code="REAPER_RESPONSE_COMPLETED_AT_INVALID",
    )
    return dict(payload)
