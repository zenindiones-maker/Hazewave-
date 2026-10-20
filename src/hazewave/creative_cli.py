from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from hazewave.audio_qc import AudioQCError, analyze_audio_qc
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reaper_vertical_proof import ReaperVerticalProofRunner, VerticalProofError
from hazewave.runtime_receipts import default_runtime_receipt_store
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
        audio_qc_analyzer: Callable[[Path], Any] = analyze_audio_qc,
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
        self.audio_qc_analyzer = audio_qc_analyzer

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

    def _wait_for_project_identity(
        self,
        expected_identity: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise CreativeControlError("REAPER_CONTEXT_SWITCH_TIMEOUT_INVALID")
        expected = str(expected_identity or "").strip()
        if not expected:
            raise CreativeControlError("REAPER_CONTEXT_SWITCH_IDENTITY_REQUIRED")

        deadline = time.monotonic() + timeout_seconds
        last_error: ReaperBridgeError | None = None
        while True:
            try:
                payload = self.heartbeat.require_fresh()
                last_error = None
            except ReaperBridgeError as exc:
                last_error = exc
                payload = {}

            identity = payload.get("project_identity")
            state = payload.get("project_state_change_count")
            if identity == expected and isinstance(state, int) and state >= 0:
                return dict(payload)

            if time.monotonic() >= deadline:
                detail = f":{last_error}" if last_error is not None else ""
                raise CreativeControlError(
                    f"REAPER_PROJECT_CONTEXT_SWITCH_TIMEOUT{detail}"
                )
            time.sleep(0.01)

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

    def execute_bound_operation(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        operation: str,
        arguments: Mapping[str, Any],
        expected_project_identity: str,
        expected_project_state_change_count: int,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        return self._submit_and_wait(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            operation=operation,
            arguments=arguments,
            expected_project_identity=expected_project_identity,
            expected_project_state_change_count=expected_project_state_change_count,
            deadline_seconds=min(timeout_seconds, 300.0),
            timeout_seconds=timeout_seconds,
        )

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

    def open_fixture(
        self,
        *,
        fixture_id: str,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        _, previous_identity, previous_state = self._binding()
        response = self._submit_and_wait(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            operation="session.fixture.open",
            arguments={"fixture_id": fixture_id},
            expected_project_identity=previous_identity,
            expected_project_state_change_count=previous_state,
            deadline_seconds=min(timeout_seconds, 60.0),
            timeout_seconds=timeout_seconds,
        )
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise CreativeControlError("REAPER_FIXTURE_OPEN_RESULT_MALFORMED")
        fixture_value = result.get("fixture_project")
        previous_value = result.get("previous_project_identity")
        if not isinstance(fixture_value, str) or not fixture_value.strip():
            raise CreativeControlError("REAPER_FIXTURE_OPEN_RESULT_MALFORMED")
        if previous_value != previous_identity:
            raise CreativeControlError("REAPER_FIXTURE_PREVIOUS_IDENTITY_MISMATCH")

        fixture_path = Path(fixture_value).expanduser().resolve()
        fixture_root = (self.root / "fixtures").resolve()
        try:
            fixture_path.relative_to(fixture_root)
        except ValueError as exc:
            raise CreativeControlError("REAPER_FIXTURE_PROJECT_OUTSIDE_ROOT") from exc

        binding = self._wait_for_project_identity(
            str(fixture_path),
            timeout_seconds,
        )
        return {
            "schema": "FixtureSessionOpen/v1",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "fixture_id": fixture_id,
            "fixture_project": str(fixture_path),
            "previous_project_identity": previous_identity,
            "project_state_change_count": binding["project_state_change_count"],
        }

    def close_fixture(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        _, fixture_identity, fixture_state = self._binding()
        fixture_path = Path(fixture_identity).expanduser().resolve()
        fixture_root = (self.root / "fixtures").resolve()
        try:
            fixture_path.relative_to(fixture_root)
        except ValueError as exc:
            raise CreativeControlError(
                "REAPER_FIXTURE_CLOSE_ACTIVE_PROJECT_OUTSIDE_ROOT"
            ) from exc

        response = self._submit_and_wait(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            operation="session.fixture.close",
            arguments={},
            expected_project_identity=fixture_identity,
            expected_project_state_change_count=fixture_state,
            deadline_seconds=min(timeout_seconds, 60.0),
            timeout_seconds=timeout_seconds,
        )
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise CreativeControlError("REAPER_FIXTURE_CLOSE_RESULT_MALFORMED")
        restored = result.get("restored_project_identity")
        closed = result.get("closed_fixture_project")
        if not isinstance(restored, str) or not restored.strip():
            raise CreativeControlError("REAPER_FIXTURE_CLOSE_RESULT_MALFORMED")
        if closed != fixture_identity:
            raise CreativeControlError("REAPER_FIXTURE_CLOSED_IDENTITY_MISMATCH")

        binding = self._wait_for_project_identity(restored, timeout_seconds)
        return {
            "schema": "FixtureSessionClose/v1",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "closed_fixture_project": fixture_identity,
            "restored_project_identity": restored,
            "project_state_change_count": binding["project_state_change_count"],
        }

    def _audition_from_render_response(
        self,
        response: Mapping[str, Any],
        *,
        task_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise CreativeControlError("REAPER_RENDER_RESULT_MALFORMED")
        artifact_value = result.get("artifact_path")
        if not isinstance(artifact_value, str) or not artifact_value.strip():
            raise CreativeControlError("REAPER_RENDER_ARTIFACT_MISSING")

        artifact_path = Path(artifact_value).resolve()
        artifact_root = (self.root / "artifacts").resolve()
        try:
            artifact_path.relative_to(artifact_root)
        except ValueError as exc:
            raise CreativeControlError("REAPER_RENDER_ARTIFACT_OUTSIDE_ROOT") from exc

        if not artifact_path.is_file():
            raise CreativeControlError("REAPER_RENDER_ARTIFACT_MISSING")
        actual_size = artifact_path.stat().st_size
        if actual_size <= 0:
            raise CreativeControlError("REAPER_RENDER_ARTIFACT_EMPTY")
        reported_size = result.get("artifact_size_bytes")
        if (
            isinstance(reported_size, int)
            and reported_size > 0
            and reported_size != actual_size
        ):
            raise CreativeControlError("REAPER_RENDER_ARTIFACT_SIZE_MISMATCH")

        try:
            qc_report = self.audio_qc_analyzer(artifact_path)
        except AudioQCError as exc:
            raise CreativeControlError(f"AUDIO_QC_FAILED:{exc}") from exc
        except Exception as exc:
            raise CreativeControlError("AUDIO_QC_FAILED:UNEXPECTED") from exc

        to_dict = getattr(qc_report, "to_dict", None)
        if not callable(to_dict):
            raise CreativeControlError("AUDIO_QC_REPORT_MALFORMED")
        qc_payload = to_dict()
        if (
            not isinstance(qc_payload, dict)
            or qc_payload.get("schema") != "AudioQCReport/v1"
        ):
            raise CreativeControlError("AUDIO_QC_REPORT_MALFORMED")

        state_before = response.get("state_before")
        state_after = response.get("state_after")
        before_count = (
            state_before.get("project_state_change_count")
            if isinstance(state_before, Mapping)
            else None
        )
        after_count = (
            state_after.get("project_state_change_count")
            if isinstance(state_after, Mapping)
            else None
        )
        if not isinstance(before_count, int) or not isinstance(after_count, int):
            raise CreativeControlError("REAPER_RENDER_STATE_MALFORMED")

        return {
            "schema": "AuditionRender/v1",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "task_id": task_id,
            "request_id": request_id,
            "artifact_path": str(artifact_path),
            "artifact_size_bytes": actual_size,
            "state_before": before_count,
            "state_after": after_count,
            "render": dict(result),
            "audio_qc": qc_payload,
            "human_approval": "REQUIRED",
        }

    def render_preview_bound(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        expected_project_identity: str,
        expected_project_state_change_count: int,
        timeout_seconds: float = 180.0,
    ) -> dict[str, Any]:
        response = self.execute_bound_operation(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            operation="render.preview",
            arguments={},
            expected_project_identity=expected_project_identity,
            expected_project_state_change_count=expected_project_state_change_count,
            timeout_seconds=timeout_seconds,
        )
        return self._audition_from_render_response(
            response,
            task_id=task_id,
            request_id=request_id,
        )

    def render_preview(
        self,
        *,
        task_id: str,
        request_id: str,
        idempotency_key: str,
        timeout_seconds: float = 180.0,
    ) -> dict[str, Any]:
        _, identity, state = self._binding()
        return self.render_preview_bound(
            task_id=task_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            expected_project_identity=identity,
            expected_project_state_change_count=state,
            timeout_seconds=timeout_seconds,
        )

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
    fixture_open_parser = sub.add_parser("fixture-open")
    fixture_open_parser.add_argument("--fixture-id", required=True)
    fixture_open_parser.add_argument("--task-id", default="creative-fixture-open")
    fixture_open_parser.add_argument("--request-id", required=True)
    fixture_open_parser.add_argument("--idempotency-key", required=True)
    fixture_open_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    fixture_close_parser = sub.add_parser("fixture-close")
    fixture_close_parser.add_argument("--task-id", default="creative-fixture-close")
    fixture_close_parser.add_argument("--request-id", required=True)
    fixture_close_parser.add_argument("--idempotency-key", required=True)
    fixture_close_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    render_parser = sub.add_parser("render-preview")
    render_parser.add_argument("--task-id", default="creative-render-preview")
    render_parser.add_argument("--request-id", required=True)
    render_parser.add_argument("--idempotency-key", required=True)
    render_parser.add_argument("--timeout-seconds", type=float, default=180.0)
    vertical_parser = sub.add_parser("vertical-proof")
    vertical_parser.add_argument("--source-audio", type=Path, required=True)
    vertical_parser.add_argument("--fixture-root", type=Path, required=True)
    vertical_parser.add_argument("--proof-id", required=True)
    vertical_parser.add_argument("--candidate-head", required=True)
    vertical_parser.add_argument("--policy-digest", required=True)
    vertical_parser.add_argument("--runtime-identity", required=True)
    vertical_parser.add_argument("--tape-echo-version", default="1.0.8")

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
        if args.command == "fixture-open":
            _print_json(
                client.open_fixture(
                    fixture_id=args.fixture_id,
                    task_id=args.task_id,
                    request_id=args.request_id,
                    idempotency_key=args.idempotency_key,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            return 0
        if args.command == "fixture-close":
            _print_json(
                client.close_fixture(
                    task_id=args.task_id,
                    request_id=args.request_id,
                    idempotency_key=args.idempotency_key,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            return 0
        if args.command == "render-preview":
            _print_json(
                client.render_preview(
                    task_id=args.task_id,
                    request_id=args.request_id,
                    idempotency_key=args.idempotency_key,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            return 0
        if args.command == "vertical-proof":
            runner = ReaperVerticalProofRunner(
                client=client,
                receipt_store=default_runtime_receipt_store(),
                fixture_root=args.fixture_root,
                candidate_head=args.candidate_head,
                policy_digest=args.policy_digest,
                runtime_identity=args.runtime_identity,
                tape_echo_version=args.tape_echo_version,
            )
            _print_json(
                runner.run(
                    source_audio=args.source_audio,
                    proof_id=args.proof_id,
                )
            )
            return 0
    except (CreativeControlError, VerticalProofError) as exc:
        print(f"CREATIVE_CONTROL=FAIL:{exc}")
        return 20

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
