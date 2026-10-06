from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reaper_bridge import (
    BridgeHeartbeat,
    FilesystemReaperBridge,
    ReaperBridgeError,
    ReaperProjectSnapshot,
    build_reaper_request,
    parse_reaper_response,
    preflight_mutation,
)


def _authorization(capability: str = "session.inspect"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="task-reaper-001",
                goal="Operate REAPER through the governed local bridge",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _request(*, operation: str = "session.inspect", state: int = 7, key: str = "idem-001"):
    now = datetime.now(timezone.utc)
    return build_reaper_request(
        authorization=_authorization(operation),
        request_id="req-001",
        idempotency_key=key,
        operation=operation,
        arguments={},
        expected_project_identity="/tmp/fixture.rpp",
        expected_project_state_change_count=state,
        issued_at=now,
        deadline=now + timedelta(seconds=10),
    )


def test_request_contract_contains_required_exact_bound_fields() -> None:
    request = _request()
    payload = request.to_dict()

    assert payload["schema"] == "ReaperExecutionRequest/v1"
    assert payload["request_id"] == "req-001"
    assert payload["task_id"] == "task-reaper-001"
    assert payload["authorization_id"]
    assert payload["idempotency_key"] == "idem-001"
    assert payload["operation"] == "session.inspect"
    assert payload["expected_project_identity"] == "/tmp/fixture.rpp"
    assert payload["expected_project_state_change_count"] == 7
    assert payload["deadline"].endswith("+00:00")
    assert payload["issued_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "operation",
    ["execute_lua", "reaper.api", "lua.eval", "script.execute", "shell.execute"],
)
def test_bridge_rejects_generic_unrestricted_execution(operation: str) -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ReaperBridgeError, match="REAPER_OPERATION_NOT_ALLOWLISTED"):
        build_reaper_request(
            authorization=_authorization(),
            request_id="req-bad",
            idempotency_key="idem-bad",
            operation=operation,
            arguments={"source": "reaper.Main_OnCommand(40044, 0)"},
            expected_project_identity="/tmp/fixture.rpp",
            expected_project_state_change_count=1,
            issued_at=now,
            deadline=now + timedelta(seconds=10),
        )


def test_stale_project_state_fails_before_mutation() -> None:
    request = _request(operation="track.create", state=11)
    snapshot = ReaperProjectSnapshot(
        project_identity="/tmp/fixture.rpp",
        project_state_change_count=12,
        dirty=True,
    )

    with pytest.raises(ReaperBridgeError, match="REAPER_STATE_STALE"):
        preflight_mutation(request, snapshot)


def test_project_identity_mismatch_fails_before_mutation() -> None:
    request = _request(operation="track.create", state=11)
    snapshot = ReaperProjectSnapshot(
        project_identity="/tmp/another.rpp",
        project_state_change_count=11,
        dirty=False,
    )

    with pytest.raises(ReaperBridgeError, match="REAPER_PROJECT_IDENTITY_MISMATCH"):
        preflight_mutation(request, snapshot)


def test_stale_heartbeat_fails_closed(tmp_path: Path) -> None:
    heartbeat_path = tmp_path / "heartbeat.json"
    now = datetime.now(timezone.utc)
    heartbeat_path.write_text(
        json.dumps(
            {
                "schema": "ReaperBridgeHeartbeat/v1",
                "bridge_id": "fixture",
                "updated_at": (now - timedelta(seconds=30)).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    heartbeat = BridgeHeartbeat(heartbeat_path, max_age_seconds=5)

    with pytest.raises(ReaperBridgeError, match="REAPER_BRIDGE_HEARTBEAT_STALE"):
        heartbeat.require_fresh(now=now)


def test_request_files_are_request_specific_and_atomic(tmp_path: Path) -> None:
    bridge = FilesystemReaperBridge(tmp_path, heartbeat_max_age_seconds=5)
    now = datetime.now(timezone.utc)
    bridge.heartbeat_path.write_text(
        json.dumps(
            {
                "schema": "ReaperBridgeHeartbeat/v1",
                "bridge_id": "fixture",
                "updated_at": now.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    path = bridge.submit(_request(), now=now)

    assert path.name == "req-001.json"
    assert path.parent == bridge.requests_dir
    assert path.is_file()
    assert not list(bridge.requests_dir.glob("*.tmp"))


def test_duplicate_idempotency_key_is_rejected_durably(tmp_path: Path) -> None:
    bridge = FilesystemReaperBridge(tmp_path, heartbeat_max_age_seconds=5)
    now = datetime.now(timezone.utc)
    bridge.heartbeat_path.write_text(
        json.dumps(
            {
                "schema": "ReaperBridgeHeartbeat/v1",
                "bridge_id": "fixture",
                "updated_at": now.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    bridge.submit(_request(key="same-key"), now=now)

    restarted = FilesystemReaperBridge(tmp_path, heartbeat_max_age_seconds=5)
    with pytest.raises(ReaperBridgeError, match="REAPER_DUPLICATE_IDEMPOTENCY_KEY"):
        restarted.submit(
            build_reaper_request(
                authorization=_authorization(),
                request_id="req-002",
                idempotency_key="same-key",
                operation="session.inspect",
                arguments={},
                expected_project_identity="/tmp/fixture.rpp",
                expected_project_state_change_count=7,
                issued_at=now,
                deadline=now + timedelta(seconds=10),
            ),
            now=now,
        )


def test_malformed_or_cross_request_response_is_rejected() -> None:
    request = _request()

    with pytest.raises(ReaperBridgeError, match="REAPER_RESPONSE_REQUEST_MISMATCH"):
        parse_reaper_response(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "other",
                "task_id": request.task_id,
                "operation": request.operation,
                "status": "PASS",
                "state_before": {"project_state_change_count": 7},
                "state_after": {"project_state_change_count": 7},
                "result": {},
                "error": None,
                "started_at": request.issued_at.isoformat(),
                "completed_at": request.issued_at.isoformat(),
            },
            request=request,
        )


def test_capability_domain_authorization_is_enforced() -> None:
    authorization = _authorization("session.inspect")
    now = datetime.now(timezone.utc)

    with pytest.raises(ReaperBridgeError, match="REAPER_AUTHORIZATION_CAPABILITY_MISMATCH"):
        build_reaper_request(
            authorization=authorization,
            request_id="req-escalation",
            idempotency_key="idem-escalation",
            operation="track.create",
            arguments={"name": "Escalated"},
            expected_project_identity="/tmp/fixture.rpp",
            expected_project_state_change_count=1,
            issued_at=now,
            deadline=now + timedelta(seconds=10),
        )
