from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any, Mapping

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reaper_bridge import (
    BridgeHeartbeat,
    FilesystemReaperBridge,
    ReaperBridgeError,
    ReaperProjectSnapshot,
    build_reaper_request,
    parse_reaper_response,
)


class CreativeControlError(RuntimeError):
    pass


class CreativeBridgeClient:
    def __init__(
        self,
        bridge_root: Path | str,
        *,
        heartbeat_max_age_seconds: float = 5.0,
    ) -> None:
        self.root = Path(bridge_root)
        self.bridge = FilesystemReaperBridge(
            self.root,
            heartbeat_max_age_seconds=heartbeat_max_age_seconds,
        )
        self.heartbeat = BridgeHeartbeat(
            self.root / "heartbeat.json",
            max_age_seconds=heartbeat_max_age_seconds,
        )

    def _binding(self) -> tuple[dict[str, Any], str, int]:
        try:
            payload = self.heartbeat.require_fresh()
        except ReaperBridgeError as exc:
            raise CreativeControlError(str(exc)) from exc
        identity = payload.get("project_identity")
        state = payload.get("project_state_change_count")
        if not isinstance(identity, str) or not identity.strip():
            raise CreativeControlError("REAPER_HEARTBEAT_PROJECT_IDENTITY_MISSING")
        if not isinstance(state, int) or state < 0:
            raise CreativeControlError("REAPER_HEARTBEAT_PROJECT_STATE_MISSING")
        return payload, identity, state

    def doctor(self) -> dict[str, Any]:
        payload, identity, state = self._binding()
        return {
            "schema": "CreativeProducerDoctor/v1",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "reaper_bridge": "PASS",
            "bridge_id": payload.get("bridge_id"),
            "project_identity": identity,
            "project_state_change_count": state,
            "heartbeat_updated_at": payload.get("updated_at"),
        }

    @staticmethod
    def _authorization(*, task_id: str, operation: str):
        try:
            return issue_authorization(
                route_task(
                    HazewaveTask(
                        task_id=task_id,
                        goal=f"Execute bounded REAPER operation {operation}",
                        required_capability=operation,
                        requested_domain=HAZE,
                    )
                )
            )
        except (KeyError, PermissionError, ValueError) as exc:
            raise CreativeControlError(f"REAPER_AUTHORIZATION_FAILED:{exc}") from exc

    def _submit_and_wait(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        operation: str,
        arguments: Mapping[str, Any],
        expected_project_identity: str,
        expected_project_state_change_count: int,
        deadline_seconds: float,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if deadline_seconds <= 0 or deadline_seconds > 300:
            raise CreativeControlError("REAPER_DEADLINE_SECONDS_INVALID")
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise CreativeControlError("REAPER_TIMEOUT_SECONDS_INVALID")

        now = datetime.now(timezone.utc)
        authorization = self._authorization(task_id=task_id, operation=operation)
        try:
            request = build_reaper_request(
                authorization=authorization,
                request_id=request_id,
                idempotency_key=idempotency_key,
                operation=operation,
                arguments=arguments,
                expected_project_identity=expected_project_identity,
                expected_project_state_change_count=expected_project_state_change_count,
                issued_at=now,
                deadline=now + timedelta(seconds=deadline_seconds),
            )
            self.bridge.submit(request, now=now)
        except ReaperBridgeError as exc:
            raise CreativeControlError(str(exc)) from exc

        response_path = self.bridge.responses_dir / f"{request_id}.json"
        wait_deadline = time.monotonic() + timeout_seconds
        while True:
            if response_path.is_file():
                try:
                    payload = json.loads(response_path.read_text(encoding="utf-8"))
                    response = parse_reaper_response(payload, request=request)
                except (OSError, json.JSONDecodeError, ReaperBridgeError) as exc:
                    raise CreativeControlError(f"REAPER_RESPONSE_INVALID:{exc}") from exc
                if response["status"] != "PASS":
                    error = response.get("error")
                    code = error.get("code") if isinstance(error, Mapping) else "UNKNOWN"
                    raise CreativeControlError(
                        f"REAPER_EXECUTION_FAILED:{response['status']}:{code}"
                    )
                return response

            if time.monotonic() >= wait_deadline:
                raise CreativeControlError("REAPER_RESPONSE_TIMEOUT")
            time.sleep(0.01)

    def snapshot(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        timeout_seconds: float = 10.0,
    ) -> ReaperProjectSnapshot:
        _, identity, state = self._binding()
        response = self._submit_and_wait(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            operation="session.inspect",
            arguments={},
            expected_project_identity=identity,
            expected_project_state_change_count=state,
            deadline_seconds=min(timeout_seconds, 30.0),
            timeout_seconds=timeout_seconds,
        )
        result = response.get("result")
        snapshot_payload = result.get("snapshot") if isinstance(result, Mapping) else None
        try:
            return ReaperProjectSnapshot.from_dict(snapshot_payload)
        except ReaperBridgeError as exc:
            raise CreativeControlError(f"REAPER_SNAPSHOT_INVALID:{exc}") from exc

    def execute_command(
        self,
        command_path: Path | str,
        *,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        path = Path(command_path)
        try:
            command = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CreativeControlError("CREATIVE_EXECUTION_COMMAND_NOT_FOUND") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CreativeControlError("CREATIVE_EXECUTION_COMMAND_MALFORMED") from exc

        required = {
            "schema",
            "task_id",
            "request_id",
            "idempotency_key",
            "operation",
            "arguments",
            "expected_project_identity",
            "expected_project_state_change_count",
            "deadline_seconds",
        }
        if not isinstance(command, dict) or required.difference(command):
            raise CreativeControlError("CREATIVE_EXECUTION_COMMAND_MALFORMED")
        if command["schema"] != "CreativeExecutionCommand/v1":
            raise CreativeControlError("CREATIVE_EXECUTION_COMMAND_SCHEMA_INVALID")
        if not isinstance(command["arguments"], dict):
            raise CreativeControlError("CREATIVE_EXECUTION_ARGUMENTS_MALFORMED")

        _, identity, state = self._binding()
        if command["expected_project_identity"] != identity:
            raise CreativeControlError("REAPER_PROJECT_IDENTITY_MISMATCH")
        if command["expected_project_state_change_count"] != state:
            raise CreativeControlError("REAPER_STATE_STALE")

        return self._submit_and_wait(
            task_id=str(command["task_id"]),
            request_id=str(command["request_id"]),
            idempotency_key=str(command["idempotency_key"]),
            operation=str(command["operation"]),
            arguments=command["arguments"],
            expected_project_identity=identity,
            expected_project_state_change_count=state,
            deadline_seconds=float(command["deadline_seconds"]),
            timeout_seconds=timeout_seconds,
        )


def default_bridge_root() -> Path:
    import os

    explicit = os.environ.get("HAZEWAVE_REAPER_BRIDGE_DIR")
    if explicit:
        return Path(explicit)
    return Path.home() / ".local" / "state" / "hazewave" / "reaper-bridge"


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hazewave-creative")
    parser.add_argument(
        "--bridge-root",
        type=Path,
        default=default_bridge_root(),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    snapshot_parser = sub.add_parser("snapshot")
    snapshot_parser.add_argument("--task-id", default="creative-snapshot")
    snapshot_parser.add_argument("--request-id", required=True)
    snapshot_parser.add_argument("--idempotency-key", required=True)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("command_file", type=Path)

    args = parser.parse_args(argv)
    client = CreativeBridgeClient(args.bridge_root)

    try:
        if args.command == "doctor":
            _print_json(client.doctor())
            return 0
        if args.command == "snapshot":
            snapshot = client.snapshot(
                task_id=args.task_id,
                request_id=args.request_id,
                idempotency_key=args.idempotency_key,
            )
            _print_json(snapshot.to_dict())
            return 0
        if args.command == "execute":
            _print_json(client.execute_command(args.command_file))
            return 0
    except CreativeControlError as exc:
        print(f"CREATIVE_CONTROL=FAIL:{exc}")
        return 20

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
