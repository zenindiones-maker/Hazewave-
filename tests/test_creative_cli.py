from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hazewave.creative_cli import CreativeBridgeClient, CreativeControlError


def _heartbeat(root: Path, *, state: int = 9) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "heartbeat.json").write_text(
        json.dumps(
            {
                "schema": "ReaperBridgeHeartbeat/v1",
                "bridge_id": "HAZEWAVE_REAPER_BRIDGE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "project_identity": "/tmp/fixture.rpp",
                "project_state_change_count": state,
            }
        ),
        encoding="utf-8",
    )


def test_producer_doctor_requires_fresh_bridge_and_reports_project_binding(tmp_path: Path) -> None:
    _heartbeat(tmp_path, state=9)

    report = CreativeBridgeClient(tmp_path).doctor()

    assert report["schema"] == "CreativeProducerDoctor/v1"
    assert report["authority"] == "HAZEWAVE_HARNESS"
    assert report["reaper_bridge"] == "PASS"
    assert report["project_identity"] == "/tmp/fixture.rpp"
    assert report["project_state_change_count"] == 9


def test_snapshot_round_trip_uses_current_heartbeat_state(tmp_path: Path) -> None:
    _heartbeat(tmp_path, state=9)
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "schema": "ReaperProjectSnapshot/v1",
        "project_identity": "/tmp/fixture.rpp",
        "project_path": "/tmp/fixture.rpp",
        "project_state_change_count": 9,
        "dirty": False,
        "sample_rate": 48000,
        "tempo": 120.0,
        "time_signature": {"numerator": 4, "denominator": 4},
        "project_length": 10.0,
        "markers": [],
        "regions": [],
        "tracks": [],
        "items": [],
        "routing": [],
        "fx": [],
    }
    (responses / "req-snapshot.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-snapshot",
                "task_id": "task-snapshot",
                "operation": "session.inspect",
                "status": "PASS",
                "state_before": {"project_state_change_count": 9},
                "state_after": {"project_state_change_count": 9},
                "result": {"snapshot": snapshot},
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    result = CreativeBridgeClient(tmp_path).snapshot(
        task_id="task-snapshot",
        request_id="req-snapshot",
        idempotency_key="snapshot-idem",
        timeout_seconds=0.1,
    )

    assert result.project_identity == "/tmp/fixture.rpp"
    assert result.project_state_change_count == 9
    request = json.loads((tmp_path / "requests" / "req-snapshot.json").read_text())
    assert request["expected_project_state_change_count"] == 9
    assert request["operation"] == "session.inspect"


def test_execute_command_refuses_stale_planned_state_before_submission(tmp_path: Path) -> None:
    _heartbeat(tmp_path, state=10)
    command = tmp_path / "command.json"
    command.write_text(
        json.dumps(
            {
                "schema": "CreativeExecutionCommand/v1",
                "task_id": "task-1",
                "request_id": "req-1",
                "idempotency_key": "idem-1",
                "operation": "track.create",
                "arguments": {"name": "Fixture"},
                "expected_project_identity": "/tmp/fixture.rpp",
                "expected_project_state_change_count": 9,
                "deadline_seconds": 5,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CreativeControlError, match="REAPER_STATE_STALE"):
        CreativeBridgeClient(tmp_path).execute_command(command, timeout_seconds=0.1)

    assert not list((tmp_path / "requests").glob("*.json"))


def test_wait_timeout_is_typed_failure_not_success(tmp_path: Path) -> None:
    _heartbeat(tmp_path, state=9)

    with pytest.raises(CreativeControlError, match="REAPER_RESPONSE_TIMEOUT"):
        CreativeBridgeClient(tmp_path).snapshot(
            task_id="task-timeout",
            request_id="req-timeout",
            idempotency_key="timeout-idem",
            timeout_seconds=0.01,
        )
