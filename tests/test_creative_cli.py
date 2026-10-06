from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hazewave.audio_qc import AudioQCReport
import hazewave.creative_cli as creative_cli
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


def _qc_report(path: Path) -> AudioQCReport:
    return AudioQCReport(
        source_path=str(path),
        source_sha256="a" * 64,
        codec_name="pcm_s24le",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        duration_seconds=2.0,
        integrated_lufs=-16.0,
        integrated_threshold_lufs=-26.0,
        loudness_range_lu=3.0,
        true_peak_dbfs=-1.0,
        sample_peak_dbfs=-1.2,
        rms_dbfs=-18.0,
        dc_offset=0.0,
        crest_factor_ratio=7.0,
        clipping_detected=False,
        technical_flags=(),
    )


def test_render_preview_returns_artifact_plus_audio_qc(tmp_path: Path) -> None:
    _heartbeat(tmp_path, state=9)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "req-render.wav"
    artifact.write_bytes(b"RIFFfixture")

    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-render.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-render",
                "task_id": "task-render",
                "operation": "render.preview",
                "status": "PASS",
                "state_before": {"project_state_change_count": 9},
                "state_after": {"project_state_change_count": 10},
                "result": {
                    "artifact_path": str(artifact),
                    "artifact_size_bytes": len(artifact.read_bytes()),
                    "format": "WAV",
                    "sample_rate": 48000,
                    "channels": 2,
                },
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    analyzed: list[Path] = []

    def analyzer(path: Path):
        analyzed.append(path)
        return _qc_report(path)

    result = CreativeBridgeClient(
        tmp_path,
        audio_qc_analyzer=analyzer,
    ).render_preview(
        task_id="task-render",
        request_id="req-render",
        idempotency_key="idem-render",
        timeout_seconds=0.1,
    )

    assert result["schema"] == "AuditionRender/v1"
    assert result["artifact_path"] == str(artifact.resolve())
    assert result["audio_qc"]["schema"] == "AudioQCReport/v1"
    assert result["state_before"] == 9
    assert result["state_after"] == 10
    assert analyzed == [artifact.resolve()]

    request = json.loads((tmp_path / "requests" / "req-render.json").read_text())
    assert request["operation"] == "render.preview"
    assert request["arguments"] == {}


def test_render_preview_rejects_bridge_artifact_outside_project_owned_root(
    tmp_path: Path,
) -> None:
    _heartbeat(tmp_path, state=9)
    outside = tmp_path.parent / "outside.wav"
    outside.write_bytes(b"fixture")
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-render-escape.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-render-escape",
                "task_id": "task-render-escape",
                "operation": "render.preview",
                "status": "PASS",
                "state_before": {"project_state_change_count": 9},
                "state_after": {"project_state_change_count": 10},
                "result": {
                    "artifact_path": str(outside),
                    "artifact_size_bytes": len(outside.read_bytes()),
                },
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CreativeControlError, match="REAPER_RENDER_ARTIFACT_OUTSIDE_ROOT"):
        CreativeBridgeClient(
            tmp_path,
            audio_qc_analyzer=lambda path: _qc_report(path),
        ).render_preview(
            task_id="task-render-escape",
            request_id="req-render-escape",
            idempotency_key="idem-render-escape",
            timeout_seconds=0.1,
        )


def test_execute_bound_operation_chains_response_state_without_heartbeat_rebind(
    tmp_path: Path,
) -> None:
    _heartbeat(tmp_path, state=9)
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-bound.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-bound",
                "task_id": "task-bound",
                "operation": "track.create",
                "status": "PASS",
                "state_before": {"project_state_change_count": 10},
                "state_after": {"project_state_change_count": 11},
                "result": {"track_index": 0, "track_guid": "{TRACK}"},
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    client = CreativeBridgeClient(tmp_path)
    response = client.execute_bound_operation(
        task_id="task-bound",
        request_id="req-bound",
        idempotency_key="idem-bound",
        operation="track.create",
        arguments={"name": "Fixture"},
        expected_project_identity="/tmp/fixture.rpp",
        expected_project_state_change_count=10,
        timeout_seconds=0.1,
    )

    assert response["state_after"]["project_state_change_count"] == 11
    request = json.loads((tmp_path / "requests" / "req-bound.json").read_text())
    assert request["expected_project_state_change_count"] == 10


def test_render_preview_bound_uses_exact_supplied_state_and_runs_qc(
    tmp_path: Path,
) -> None:
    _heartbeat(tmp_path, state=9)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "req-render-bound.wav"
    artifact.write_bytes(b"RIFFfixture")
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-render-bound.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-render-bound",
                "task_id": "task-render-bound",
                "operation": "render.preview",
                "status": "PASS",
                "state_before": {"project_state_change_count": 10},
                "state_after": {"project_state_change_count": 10},
                "result": {
                    "artifact_path": str(artifact),
                    "artifact_size_bytes": len(artifact.read_bytes()),
                },
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    client = CreativeBridgeClient(
        tmp_path,
        audio_qc_analyzer=lambda path: _qc_report(path),
    )
    result = client.render_preview_bound(
        task_id="task-render-bound",
        request_id="req-render-bound",
        idempotency_key="idem-render-bound",
        expected_project_identity="/tmp/fixture.rpp",
        expected_project_state_change_count=10,
        timeout_seconds=0.1,
    )

    assert result["state_before"] == 10
    request = json.loads(
        (tmp_path / "requests" / "req-render-bound.json").read_text()
    )
    assert request["expected_project_state_change_count"] == 10



def test_cli_vertical_proof_runs_exact_bound_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFFfixture")
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    bridge_root = tmp_path / "bridge"
    bridge_root.mkdir()

    captured: dict[str, object] = {}
    fake_client = object()
    fake_store = object()

    monkeypatch.setattr(
        creative_cli,
        "CreativeBridgeClient",
        lambda root: fake_client,
    )
    monkeypatch.setattr(
        creative_cli,
        "default_runtime_receipt_store",
        lambda: fake_store,
        raising=False,
    )

    class FakeRunner:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def run(self, *, source_audio, proof_id):
            captured["run"] = {
                "source_audio": source_audio,
                "proof_id": proof_id,
            }
            return {
                "schema": "ReaperLiveVerticalProof/v1",
                "status": "PASS",
            }

    monkeypatch.setattr(
        creative_cli,
        "ReaperVerticalProofRunner",
        FakeRunner,
        raising=False,
    )

    rc = creative_cli.main(
        [
            "--bridge-root",
            str(bridge_root),
            "vertical-proof",
            "--source-audio",
            str(source),
            "--fixture-root",
            str(fixture_root),
            "--proof-id",
            "vertical-001",
            "--candidate-head",
            "candidate-sha",
            "--policy-digest",
            "policy-sha",
            "--runtime-identity",
            "codespace:fixture",
            "--tape-echo-version",
            "1.0.8",
        ]
    )

    assert rc == 0
    assert captured["init"] == {
        "client": fake_client,
        "receipt_store": fake_store,
        "fixture_root": fixture_root,
        "candidate_head": "candidate-sha",
        "policy_digest": "policy-sha",
        "runtime_identity": "codespace:fixture",
        "tape_echo_version": "1.0.8",
    }
    assert captured["run"] == {
        "source_audio": source,
        "proof_id": "vertical-001",
    }
    output = capsys.readouterr().out
    assert '"schema": "ReaperLiveVerticalProof/v1"' in output
    assert '"status": "PASS"' in output


def test_open_fixture_submits_only_fixture_id_and_waits_for_owned_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _heartbeat(tmp_path, state=2)
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    fixture = (tmp_path / "fixtures" / "vertical-001.rpp").resolve()
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-fixture-open.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-fixture-open",
                "task_id": "task-fixture-open",
                "operation": "session.fixture.open",
                "status": "PASS",
                "state_before": {"project_state_change_count": 2},
                "state_after": {"project_state_change_count": 0},
                "result": {
                    "fixture_id": "vertical-001",
                    "fixture_project": str(fixture),
                    "previous_project_identity": "/tmp/fixture.rpp",
                },
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    client = CreativeBridgeClient(tmp_path)
    monkeypatch.setattr(
        client,
        "_wait_for_project_identity",
        lambda expected, timeout_seconds: {
            "project_identity": expected,
            "project_state_change_count": 0,
        },
        raising=False,
    )

    result = client.open_fixture(
        fixture_id="vertical-001",
        task_id="task-fixture-open",
        request_id="req-fixture-open",
        idempotency_key="idem-fixture-open",
        timeout_seconds=0.1,
    )

    assert result["schema"] == "FixtureSessionOpen/v1"
    assert result["fixture_project"] == str(fixture)
    request = json.loads(
        (tmp_path / "requests" / "req-fixture-open.json").read_text()
    )
    assert request["operation"] == "session.fixture.open"
    assert request["arguments"] == {"fixture_id": "vertical-001"}


def test_close_fixture_has_no_force_argument_and_waits_for_previous_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = (tmp_path / "fixtures" / "vertical-001.rpp").resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "heartbeat.json").write_text(
        json.dumps(
            {
                "schema": "ReaperBridgeHeartbeat/v1",
                "bridge_id": "HAZEWAVE_REAPER_BRIDGE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "project_identity": str(fixture),
                "project_state_change_count": 9,
            }
        ),
        encoding="utf-8",
    )
    responses = tmp_path / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (responses / "req-fixture-close.json").write_text(
        json.dumps(
            {
                "schema": "ReaperExecutionResponse/v1",
                "request_id": "req-fixture-close",
                "task_id": "task-fixture-close",
                "operation": "session.fixture.close",
                "status": "PASS",
                "state_before": {"project_state_change_count": 9},
                "state_after": {"project_state_change_count": 2},
                "result": {
                    "restored_project_identity": "/tmp/user.rpp",
                    "closed_fixture_project": str(fixture),
                },
                "error": None,
                "started_at": now,
                "completed_at": now,
            }
        ),
        encoding="utf-8",
    )

    client = CreativeBridgeClient(tmp_path)
    monkeypatch.setattr(
        client,
        "_wait_for_project_identity",
        lambda expected, timeout_seconds: {
            "project_identity": expected,
            "project_state_change_count": 2,
        },
        raising=False,
    )

    result = client.close_fixture(
        task_id="task-fixture-close",
        request_id="req-fixture-close",
        idempotency_key="idem-fixture-close",
        timeout_seconds=0.1,
    )

    assert result["schema"] == "FixtureSessionClose/v1"
    assert result["restored_project_identity"] == "/tmp/user.rpp"
    request = json.loads(
        (tmp_path / "requests" / "req-fixture-close.json").read_text()
    )
    assert request["operation"] == "session.fixture.close"
    assert request["arguments"] == {}
