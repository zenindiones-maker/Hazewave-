from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hazewave.blender_bridge import (
    BlenderBridgeError,
    BlenderCLIExecutor,
    BlenderSceneSnapshot,
    build_blender_request,
    parse_blender_response,
)
from hazewave.harness import WAVE, HazewaveTask, issue_authorization, route_task


def _authorization(operation: str):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="task-blender-001",
                goal="Execute bounded Blender WAVE operation",
                required_capability=operation,
                requested_domain=WAVE,
            )
        )
    )


def _request(operation: str = "animation.scene.inspect"):
    now = datetime.now(timezone.utc)
    return build_blender_request(
        authorization=_authorization(operation),
        request_id="blend-req-001",
        idempotency_key="blend-idem-001",
        operation=operation,
        arguments={},
        expected_blender_version="5.2.2",
        expected_scene_identity="fixture-scene",
        expected_blend_sha256="a" * 64,
        seed=1234,
        issued_at=now,
        deadline=now + timedelta(seconds=30),
    )


def test_blender_request_contract_is_exact_bound_and_wave_authorized() -> None:
    request = _request()
    payload = request.to_dict()

    assert payload["schema"] == "BlenderExecutionRequest/v1"
    assert payload["request_id"] == "blend-req-001"
    assert payload["task_id"] == "task-blender-001"
    assert payload["authorization_id"]
    assert payload["operation"] == "animation.scene.inspect"
    assert payload["expected_blender_version"] == "5.2.2"
    assert payload["expected_scene_identity"] == "fixture-scene"
    assert payload["expected_blend_sha256"] == "a" * 64
    assert payload["seed"] == 1234
    assert payload["deadline_epoch_seconds"] > payload["issued_at_epoch_seconds"]


@pytest.mark.parametrize(
    "operation",
    ["python.execute", "script.execute", "blender.eval", "shell.execute"],
)
def test_blender_bridge_rejects_generic_execution(operation: str) -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(BlenderBridgeError, match="BLENDER_OPERATION_NOT_ALLOWLISTED"):
        build_blender_request(
            authorization=_authorization("animation.scene.inspect"),
            request_id="bad",
            idempotency_key="bad",
            operation=operation,
            arguments={"python": "import os; os.system('id')"},
            expected_blender_version="5.2.2",
            expected_scene_identity="fixture",
            expected_blend_sha256="a" * 64,
            seed=1,
            issued_at=now,
            deadline=now + timedelta(seconds=10),
        )


def test_fixture_create_accepts_only_safe_fixture_id() -> None:
    now = datetime.now(timezone.utc)
    auth = _authorization("animation.fixture.create")

    with pytest.raises(BlenderBridgeError, match="BLENDER_FIXTURE_PATH_CALLER_CONTROLLED"):
        build_blender_request(
            authorization=auth,
            request_id="fixture-bad-path",
            idempotency_key="fixture-bad-path",
            operation="animation.fixture.create",
            arguments={"fixture_id": "cartoon-001", "output_path": "/tmp/a.blend"},
            expected_blender_version="5.2.2",
            expected_scene_identity="cartoon-001",
            expected_blend_sha256="0" * 64,
            seed=1,
            issued_at=now,
            deadline=now + timedelta(seconds=10),
        )

    with pytest.raises(BlenderBridgeError, match="BLENDER_FIXTURE_ID_INVALID"):
        build_blender_request(
            authorization=auth,
            request_id="fixture-bad-id",
            idempotency_key="fixture-bad-id",
            operation="animation.fixture.create",
            arguments={"fixture_id": "../escape"},
            expected_blender_version="5.2.2",
            expected_scene_identity="cartoon-001",
            expected_blend_sha256="0" * 64,
            seed=1,
            issued_at=now,
            deadline=now + timedelta(seconds=10),
        )


def test_scene_snapshot_parses_professional_minimum_surface() -> None:
    snapshot = BlenderSceneSnapshot.from_dict(
        {
            "schema": "BlenderSceneSnapshot/v1",
            "blender_version": "5.2.2",
            "blend_path": "/tmp/cartoon.blend",
            "blend_sha256": "b" * 64,
            "scene_identity": "cartoon-scene",
            "frame_start": 1,
            "frame_end": 48,
            "fps": 24.0,
            "resolution_x": 1920,
            "resolution_y": 1080,
            "resolution_percentage": 100,
            "render_engine": "BLENDER_EEVEE_NEXT",
            "view_transform": "AgX",
            "look": "Medium High Contrast",
            "display_device": "sRGB",
            "objects": [{"name": "Character", "type": "GREASEPENCIL"}],
            "grease_pencil_objects": ["Character"],
            "cameras": ["Camera"],
            "dependencies": [],
        }
    )

    assert snapshot.blender_version == "5.2.2"
    assert snapshot.frame_end == 48
    assert snapshot.grease_pencil_objects == ("Character",)
    assert snapshot.cameras == ("Camera",)


def test_cli_executor_builds_background_command_with_project_owned_adapter(
    tmp_path: Path,
) -> None:
    adapter = tmp_path / "scripts" / "blender" / "hazewave_blender_adapter.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("# adapter\n", encoding="utf-8")
    blend = tmp_path / "scene.blend"
    blend.write_bytes(b"blend")
    request = _request()

    executor = BlenderCLIExecutor(
        root=tmp_path / "runtime",
        blender_binary=Path("/opt/blender-5.2.2/blender"),
        adapter_script=adapter,
    )

    prepared = executor.prepare(
        request,
        blend_path=blend,
    )

    assert prepared.request_path.is_file()
    assert prepared.response_path.parent == (tmp_path / "runtime" / "responses")
    assert prepared.command[:3] == (
        "/opt/blender-5.2.2/blender",
        "--background",
        str(blend.resolve()),
    )
    assert "--python" in prepared.command
    assert str(adapter.resolve()) in prepared.command
    assert prepared.command[-4:] == (
        "--request",
        str(prepared.request_path),
        "--response",
        str(prepared.response_path),
    )
    payload = json.loads(prepared.request_path.read_text(encoding="utf-8"))
    assert payload["operation"] == "animation.scene.inspect"


def test_response_parser_rejects_cross_request_or_wrong_version() -> None:
    request = _request()
    payload = {
        "schema": "BlenderExecutionReceipt/v1",
        "request_id": "other",
        "task_id": request.task_id,
        "operation": request.operation,
        "status": "PASS",
        "blender_version": "5.2.2",
        "state_before": {"blend_sha256": "a" * 64},
        "state_after": {"blend_sha256": "b" * 64},
        "result": {},
        "error": None,
        "started_at": request.issued_at.isoformat(),
        "completed_at": request.issued_at.isoformat(),
    }
    with pytest.raises(BlenderBridgeError, match="BLENDER_RESPONSE_REQUEST_MISMATCH"):
        parse_blender_response(payload, request=request)

    payload["request_id"] = request.request_id
    payload["blender_version"] = "5.2.1"
    with pytest.raises(BlenderBridgeError, match="BLENDER_VERSION_MISMATCH"):
        parse_blender_response(payload, request=request)
