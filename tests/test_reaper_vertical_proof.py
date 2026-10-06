from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.audio_qc import AudioQCReport
from hazewave.reaper_bridge import ReaperProjectSnapshot
from hazewave.reaper_vertical_proof import (
    VerticalProofError,
    discover_tape_echo_2_semantics,
    ensure_disposable_fixture,
    select_fixture_adjustment,
)


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
