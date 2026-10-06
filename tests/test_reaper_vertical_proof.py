from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.audio_qc import AudioQCReport
from hazewave.reaper_bridge import ReaperProjectSnapshot
from hazewave.reaper_vertical_proof import (
    ReaperVerticalProofRunner,
    VerticalProofError,
    discover_tape_echo_2_semantics,
    ensure_disposable_fixture,
    select_fixture_adjustment,
)
from hazewave.runtime_receipts import RuntimeReceiptStore


def _snapshot(*, project: str, dirty: bool = False) -> ReaperProjectSnapshot:
    return ReaperProjectSnapshot(
        project_identity=project,
        project_path=project,
        project_state_change_count=7,
        dirty=dirty,
        sample_rate=48000,
        tempo=120.0,
        time_signature={"numerator": 4, "denominator": 4},
        project_length=2.0,
    )


def _qc(*, true_peak: float = -4.0, clipping: bool = False) -> AudioQCReport:
    return AudioQCReport(
        source_path="/tmp/a.wav",
        source_sha256="a" * 64,
        codec_name="pcm_s24le",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        duration_seconds=2.0,
        integrated_lufs=-20.0,
        integrated_threshold_lufs=-30.0,
        loudness_range_lu=2.0,
        true_peak_dbfs=true_peak,
        sample_peak_dbfs=true_peak - 0.2,
        rms_dbfs=-24.0,
        dc_offset=0.0,
        crest_factor_ratio=8.0,
        clipping_detected=clipping,
        technical_flags=("CLIPPING_OR_OVERS_DETECTED",) if clipping else (),
    )


def test_fixture_guard_accepts_only_clean_rpp_inside_owned_fixture_root(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    fixture = fixture_root / "proof.rpp"
    fixture.write_text("<REAPER_PROJECT 0.1\n>\n", encoding="utf-8")

    accepted = ensure_disposable_fixture(
        _snapshot(project=str(fixture)),
        fixture_root=fixture_root,
    )

    assert accepted == fixture.resolve()


@pytest.mark.parametrize(
    ("project", "dirty", "code"),
    [
        ("/tmp/user-song.rpp", False, "VERTICAL_PROOF_PROJECT_OUTSIDE_FIXTURE_ROOT"),
        ("/tmp/fixtures/not-rpp.txt", False, "VERTICAL_PROOF_PROJECT_NOT_RPP"),
    ],
)
def test_fixture_guard_rejects_non_fixture_projects(
    tmp_path: Path,
    project: str,
    dirty: bool,
    code: str,
) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()

    if "fixtures/" in project:
        path = fixture_root / Path(project).name
        path.write_text("fixture", encoding="utf-8")
        project = str(path)

    with pytest.raises(VerticalProofError, match=code):
        ensure_disposable_fixture(
            _snapshot(project=project, dirty=dirty),
            fixture_root=fixture_root,
        )


def test_fixture_guard_refuses_initial_dirty_fixture(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    fixture = fixture_root / "dirty.rpp"
    fixture.write_text("<REAPER_PROJECT 0.1\n>\n", encoding="utf-8")

    with pytest.raises(VerticalProofError, match="VERTICAL_PROOF_FIXTURE_DIRTY"):
        ensure_disposable_fixture(
            _snapshot(project=str(fixture), dirty=True),
            fixture_root=fixture_root,
        )


def test_tape_echo_semantics_are_bound_by_runtime_names_not_hardcoded_indices() -> None:
    fx = {
        "fx_guid": "{FX}",
        "fx_index": 4,
        "name": "VST3: Tape Echo 2 (Dusk Audio)",
        "parameters": [
            {"index": 17, "name": "Mix", "value": 0.5, "min": 0.0, "max": 1.0},
            {"index": 5, "name": "Echo Volume", "value": 0.4, "min": 0.0, "max": 1.0},
            {"index": 99, "name": "Intensity", "value": 0.2, "min": 0.0, "max": 1.0},
            {"index": 3, "name": "Repeat Rate", "value": 0.3, "min": 0.0, "max": 1.0},
        ],
    }

    semantics = discover_tape_echo_2_semantics(fx)

    assert semantics.fx_guid == "{FX}"
    assert semantics.fx_index == 4
    assert semantics.parameters["repeat_rate"].index == 3
    assert semantics.parameters["intensity"].index == 99
    assert semantics.parameters["echo_volume"].index == 5
    assert semantics.parameters["mix"].index == 17


def test_tape_echo_semantics_fail_closed_when_runtime_parameter_is_missing() -> None:
    fx = {
        "fx_guid": "{FX}",
        "fx_index": 0,
        "name": "Tape Echo 2",
        "parameters": [
            {"index": 0, "name": "Mix", "value": 0.5, "min": 0.0, "max": 1.0},
            {"index": 1, "name": "Repeat Rate", "value": 0.3, "min": 0.0, "max": 1.0},
        ],
    }

    with pytest.raises(VerticalProofError, match="TAPE_ECHO_2_PARAMETER_MISSING:intensity"):
        discover_tape_echo_2_semantics(fx)


def test_fixture_adjustment_uses_real_headroom_evidence_when_near_clipping() -> None:
    decision = select_fixture_adjustment(
        _qc(true_peak=-0.4, clipping=False),
        current_echo_volume=0.60,
        current_intensity=0.45,
    )

    assert decision.schema == "FixtureAnalysisAdjustment/v1"
    assert decision.scope == "FIXTURE_ONLY"
    assert decision.parameter_role == "echo_volume"
    assert decision.new_normalized_value == pytest.approx(0.50)
    assert decision.reason == "TRUE_PEAK_HEADROOM"


def test_fixture_adjustment_creates_safe_contrast_when_headroom_is_clear() -> None:
    decision = select_fixture_adjustment(
        _qc(true_peak=-4.0, clipping=False),
        current_echo_volume=0.60,
        current_intensity=0.45,
    )

    assert decision.scope == "FIXTURE_ONLY"
    assert decision.parameter_role == "intensity"
    assert decision.new_normalized_value == pytest.approx(0.50)
    assert decision.reason == "SAFE_FIXTURE_CONTRAST"


def test_fixture_adjustment_never_pushes_feedback_into_high_risk_range() -> None:
    decision = select_fixture_adjustment(
        _qc(true_peak=-6.0, clipping=False),
        current_echo_volume=0.60,
        current_intensity=0.54,
    )

    assert decision.parameter_role == "intensity"
    assert decision.new_normalized_value <= 0.55


class _FakeVerticalClient:
    def __init__(self, root: Path, fixture: Path) -> None:
        self.root = root
        self.fixture = fixture
        self.calls: list[dict] = []
        self.state = 1
        self.fx_index = 0
        self.fx_guid = "{TAPE-ECHO}"
        self.parameters = {
            "Repeat Rate": {"index": 31, "value": 0.10},
            "Intensity": {"index": 77, "value": 0.10},
            "Echo Volume": {"index": 12, "value": 0.10},
            "Mix": {"index": 44, "value": 0.50},
        }
        self._adjustment_previous: float | None = None
        self._adjustment_name: str | None = None
        (root / "checkpoints").mkdir(parents=True, exist_ok=True)
        (root / "artifacts").mkdir(parents=True, exist_ok=True)

    def snapshot(self, **kwargs):
        return ReaperProjectSnapshot(
            project_identity=str(self.fixture.resolve()),
            project_path=str(self.fixture.resolve()),
            project_state_change_count=self.state,
            dirty=False,
            sample_rate=48000,
            tempo=120.0,
            time_signature={"numerator": 4, "denominator": 4},
            project_length=2.0,
        )

    def _response(self, operation: str, before: int, after: int, result: dict):
        return {
            "schema": "ReaperExecutionResponse/v1",
            "operation": operation,
            "status": "PASS",
            "state_before": {"project_state_change_count": before},
            "state_after": {"project_state_change_count": after},
            "result": result,
            "error": None,
        }

    def execute_bound_operation(self, **kwargs):
        self.calls.append(dict(kwargs))
        operation = kwargs["operation"]
        before = kwargs["expected_project_state_change_count"]
        assert before == self.state

        if operation == "session.checkpoint":
            checkpoint = self.root / "checkpoints" / f"{kwargs['request_id']}.rpp"
            checkpoint.write_text(self.fixture.read_text(encoding="utf-8"), encoding="utf-8")
            return self._response(
                operation,
                before,
                before,
                {"checkpoint_path": str(checkpoint), "checkpoint_size_bytes": checkpoint.stat().st_size},
            )
        if operation == "track.create":
            self.state += 1
            name = kwargs["arguments"]["name"]
            if name == "Hazewave Proof Source":
                result = {"track_index": 0, "track_guid": "{SRC}"}
            else:
                result = {"track_index": 1, "track_guid": "{BUS}"}
            return self._response(operation, before, self.state, result)
        if operation == "audio.import":
            self.state += 1
            return self._response(operation, before, self.state, {"track_guid": "{SRC}"})
        if operation == "routing.bus":
            self.state += 1
            return self._response(
                operation,
                before,
                self.state,
                {"bus_index": 1, "bus_guid": "{BUS}", "sends": []},
            )
        if operation == "routing.send":
            self.state += 1
            return self._response(operation, before, self.state, {"send_index": 0})
        if operation == "fx.add":
            self.state += 1
            return self._response(
                operation,
                before,
                self.state,
                {"track_guid": "{BUS}", "fx_index": self.fx_index, "name": "VST3: Tape Echo 2"},
            )
        if operation == "fx.inventory":
            fx = {
                "track_guid": "{BUS}",
                "fx_guid": self.fx_guid,
                "fx_index": self.fx_index,
                "name": "VST3: Tape Echo 2 (Dusk Audio)",
                "parameters": [
                    {
                        "index": value["index"],
                        "name": name,
                        "value": value["value"],
                        "min": 0.0,
                        "max": 1.0,
                    }
                    for name, value in self.parameters.items()
                ],
            }
            return self._response(operation, before, before, {"fx": [fx]})
        if operation == "fx.parameter.write":
            args = kwargs["arguments"]
            name = args["expected_parameter_name"]
            if kwargs["task_id"].endswith("-adjustment"):
                self._adjustment_name = name
                self._adjustment_previous = self.parameters[name]["value"]
            self.parameters[name]["value"] = args["normalized_value"]
            self.state += 1
            return self._response(
                operation,
                before,
                self.state,
                {
                    "fx_index": self.fx_index,
                    "parameter_index": args["parameter_index"],
                    "name": name,
                    "normalized_value": args["normalized_value"],
                },
            )
        if operation == "session.rollback":
            expected = kwargs["arguments"]["expected_undo_description"]
            assert expected.startswith("Hazewave: fx.parameter.write [")
            assert self._adjustment_name is not None
            assert self._adjustment_previous is not None
            self.parameters[self._adjustment_name]["value"] = self._adjustment_previous
            self.state += 1
            return self._response(
                operation,
                before,
                self.state,
                {"undone_description": expected},
            )
        if operation == "fx.parameter.read":
            args = kwargs["arguments"]
            by_index = {
                value["index"]: (name, value["value"])
                for name, value in self.parameters.items()
            }
            name, value = by_index[args["parameter_index"]]
            return self._response(
                operation,
                before,
                before,
                {
                    "fx_index": self.fx_index,
                    "parameter_index": args["parameter_index"],
                    "name": name,
                    "value": value,
                    "min": 0.0,
                    "max": 1.0,
                },
            )
        raise AssertionError(operation)

    def render_preview_bound(self, **kwargs):
        self.calls.append({"operation": "render.preview", **kwargs})
        before = kwargs["expected_project_state_change_count"]
        assert before == self.state
        count = sum(1 for call in self.calls if call.get("operation") == "render.preview")
        artifact = self.root / "artifacts" / f"render-{count}.wav"
        artifact.write_bytes(b"RIFF" + bytes([count]) * 32)
        qc = _qc(true_peak=-4.0 if count == 1 else -3.7).to_dict()
        qc["source_path"] = str(artifact)
        qc["source_sha256"] = ("%x" % count) * 64
        return {
            "schema": "AuditionRender/v1",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "task_id": kwargs["task_id"],
            "request_id": kwargs["request_id"],
            "artifact_path": str(artifact.resolve()),
            "artifact_size_bytes": artifact.stat().st_size,
            "state_before": before,
            "state_after": before,
            "render": {"artifact_path": str(artifact.resolve())},
            "audio_qc": qc,
            "human_approval": "REQUIRED",
        }


def test_vertical_runner_executes_complete_fixture_ab_loop_with_receipts(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    fixture = fixture_root / "proof.rpp"
    fixture.write_text("<REAPER_PROJECT 0.1\n>\n", encoding="utf-8")
    source = fixture_root / "source.wav"
    source.write_bytes(b"RIFFsource")

    bridge_root = tmp_path / "bridge"
    client = _FakeVerticalClient(bridge_root, fixture)
    receipts = RuntimeReceiptStore(
        config_root=tmp_path / "config",
        state_root=tmp_path / "state",
    )

    result = ReaperVerticalProofRunner(
        client=client,
        receipt_store=receipts,
        fixture_root=fixture_root,
        candidate_head="candidate-sha",
        policy_digest="policy-sha256",
        runtime_identity="codespace:fixture",
        tape_echo_version="1.0.8",
    ).run(
        source_audio=source,
        proof_id="vertical-001",
    )

    assert result["schema"] == "ReaperLiveVerticalProof/v1"
    assert result["status"] == "PASS"
    assert result["fixture_project"] == str(fixture.resolve())
    assert result["plugin"]["version"] == "1.0.8"
    assert result["plugin"]["runtime_parameter_names"] == {
        "repeat_rate": "Repeat Rate",
        "intensity": "Intensity",
        "echo_volume": "Echo Volume",
        "mix": "Mix",
    }
    assert Path(result["render_a"]["artifact_path"]).is_file()
    assert Path(result["render_b"]["artifact_path"]).is_file()
    assert result["render_a"]["artifact_path"] != result["render_b"]["artifact_path"]
    assert result["adjustment"]["scope"] == "FIXTURE_ONLY"
    assert result["adjustment"]["parameter_role"] == "intensity"
    assert result["adjustment"]["new_normalized_value"] == pytest.approx(0.50)
    assert result["rollback"]["proven"] is True
    assert result["rollback"]["restored_normalized_value"] == pytest.approx(0.45)
    assert len(result["durable_receipts"]) >= 10
    assert all(Path(path).is_file() for path in result["durable_receipts"])

    operations = [call.get("operation") for call in client.calls]
    assert operations[:7] == [
        "session.checkpoint",
        "track.create",
        "audio.import",
        "routing.bus",
        "routing.send",
        "fx.add",
        "fx.inventory",
    ]
    writes = [
        call for call in client.calls
        if call.get("operation") == "fx.parameter.write"
    ]
    baseline_names = {
        call["arguments"]["expected_parameter_name"]
        for call in writes
        if not call["task_id"].endswith("-adjustment")
    }
    assert baseline_names == {"Repeat Rate", "Intensity", "Echo Volume", "Mix"}
    assert {call["arguments"]["parameter_index"] for call in writes[:4]} == {31, 77, 12, 44}
    assert operations.count("render.preview") == 2
    assert "session.rollback" in operations
    assert operations[-1] == "fx.parameter.read"
