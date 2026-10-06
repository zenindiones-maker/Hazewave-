from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "scripts" / "codespaces" / "creative-execution-control.sh"
RUNTIME_PROOF = ROOT / "scripts" / "codespaces" / "hazewave-runtime-proof.sh"


def test_creative_execution_control_is_bounded_and_non_provisioning() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'BRANCH="work/creative-execution-plane-v1"' in text
    assert "python -m hazewave.creative_cli doctor" in text
    assert "python -m hazewave.creative_cli snapshot" in text
    assert "python -m hazewave.creative_cli execute" in text
    assert "ffprobe" in text
    assert "ffmpeg" in text
    assert "aplay" in text

    for forbidden in (
        "gh codespace create",
        "git reset",
        "git checkout",
        "git pull",
        "git merge",
        "git push",
        "sudo ",
    ):
        assert forbidden not in text


def test_candidate_runtime_proof_binds_to_creative_branch_and_bridge() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert 'BRANCH="work/creative-execution-plane-v1"' in text
    assert "CreativeProducerDoctor/v1" in text
    assert "HAZEWAVE_REAPER_BRIDGE" in text
    assert "creative-execution-control.sh vertical-proof" in text
    assert "ReaperLiveVerticalProof/v1" in text
    assert "LIVE_REAPER_PROOF=PASS" in text
    assert "LIVE_REAPER_PROOF=NOT_PROVEN" not in text


def test_creative_execution_control_exposes_render_preview_with_qc() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert "cmd_render_preview()" in text
    assert "python -m hazewave.creative_cli render-preview" in text
    assert "render-preview) cmd_render_preview" in text
    assert "HUMAN_APPROVAL=REQUIRED" in text



def test_creative_execution_control_exposes_exact_bound_vertical_proof() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert "cmd_vertical_proof()" in text
    assert 'CANDIDATE_HEAD="$(git rev-parse HEAD)"' in text
    assert 'config/project-profile-v2.json' in text
    assert 'sha256sum' in text
    assert 'CODESPACE_NAME' in text
    assert "python -m hazewave.creative_cli vertical-proof" in text
    assert "--candidate-head" in text
    assert "--policy-digest" in text
    assert "--runtime-identity" in text
    assert "--fixture-root" in text
    assert "--source-audio" in text
    assert "vertical-proof) shift; cmd_vertical_proof" in text


def test_live_vertical_proof_creates_local_fixture_audio_and_restores_tab() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'fixture_root="$BRIDGE_ROOT/fixtures"' in text
    assert "sox -n -r 48000" in text
    assert "fixture-open" in text
    assert "vertical-proof" in text
    assert "fixture-close" in text
    assert "cleanup_fixture" in text
    assert "trap cleanup_fixture EXIT" in text
    assert "LIVE_REAPER_PROOF=PASS" in text
    assert "SOURCE_AUDIO_REQUIRED" not in text



def test_runtime_proof_preserves_live_vertical_proof_evidence() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert "reaper-live-vertical-proof.txt" in text
    assert "tee" in text
    assert "fixture-close=RUNNER_VERIFIED" in text
    assert "HUMAN_APPROVAL=REQUIRED" in text


def test_vertical_proof_persists_machine_readable_receipt() -> None:
    text = CONTROL.read_text(encoding="utf-8")

    assert 'CREATIVE_PROOF_ROOT="${HOME}/.local/state/hazewave-codespace/creative-proofs"' in text
    assert 'proof_dir="$CREATIVE_PROOF_ROOT/$proof_id"' in text
    assert 'proof_json="$proof_dir/reaper-live-proof.json"' in text
    assert 'echo "VERTICAL_PROOF_JSON=$proof_json"' in text
    assert 'rm -f "$source_audio" "$proof_json"' not in text


def test_runtime_proof_chains_real_haze_render_into_cartoon_live_proof() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert 'VERTICAL_PROOF_JSON=' in text
    assert 'render_b' in text
    assert 'artifact_path' in text
    assert 'python -m hazewave.cartoon_live_proof' in text
    assert 'CartoonLiveProof/v1' in text
    assert 'AnimationQCReport/v1' in text
    assert 'VideoQCReport/v1' in text
    assert 'CARTOON_LIVE_PROOF=PASS' in text
    assert 'CARTOON_LIVE_PROOF=NOT_PROVEN' not in text

    validate_index = text.index('CartoonLiveProof/v1')
    pass_index = text.index('echo "CARTOON_LIVE_PROOF=PASS"')
    assert validate_index < pass_index


def test_runtime_proof_chains_haze_into_wave_before_cartoon() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert 'python -m hazewave.wave_live_proof' in text
    assert 'WaveLiveProof/v1' in text
    assert 'SceneDetectionReport/v1' in text
    assert 'OTIOInterchangeReceipt/v1' in text
    assert 'VideoQCReport/v1' in text
    assert 'WAVE_LIVE_PROOF_JSON=' in text
    assert 'LIVE_WAVE_PROOF=PASS' in text
    assert 'LIVE_WAVE_PROOF=NOT_PROVEN' not in text

    haze_index = text.index('LIVE_REAPER_PROOF=PASS')
    wave_index = text.index('WaveLiveProof/v1')
    cartoon_index = text.index('CartoonLiveProof/v1')
    assert haze_index < wave_index < cartoon_index
