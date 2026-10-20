from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "codespaces" / "install-wave-runtime-pinned.sh"
UPGRADE = ROOT / "scripts" / "codespaces" / "upgrade-professional-v2.sh"
DOCTOR = ROOT / "scripts" / "codespaces" / "professional-doctor.sh"
RUNTIME_PROOF = ROOT / "scripts" / "codespaces" / "hazewave-runtime-proof.sh"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_wave_runtime_installer_uses_isolated_pinned_venv() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert 'OTIO_VERSION="0.18.1"' in text
    assert 'SCENEDETECT_VERSION="0.7.1"' in text
    assert 'OpenTimelineIO==0.18.1' in text
    assert 'scenedetect-headless==0.7.1' in text
    assert 'WAVE_RUNTIME_ROOT="${HOME}/.local/opt/hazewave-wave-runtime/0.18.1-0.7.1"' in text
    assert 'python3 -m venv "$WAVE_RUNTIME_ROOT"' in text
    assert '"$WAVE_RUNTIME_PYTHON" -m pip install --only-binary=:all:' in text
    assert 'import opentimelineio as otio' in text
    assert 'import scenedetect' in text
    assert 'WAVE_OTIO_VERSION=0.18.1' in text
    assert 'WAVE_SCENEDETECT_VERSION=0.7.1' in text
    assert 'PAID_FALLBACK=FALSE' in text
    assert 'UNKNOWN_COST_FALLBACK=FALSE' in text

    for forbidden in (
        "pip install OpenTimelineIO",
        "pip install scenedetect-headless",
        "sudo ",
        "conda ",
    ):
        assert forbidden not in text


def test_professional_upgrade_installs_wave_runtime_before_doctor() -> None:
    text = UPGRADE.read_text(encoding="utf-8")

    wave_index = text.index("install-wave-runtime-pinned.sh")
    doctor_index = text.index("professional-doctor.sh")
    assert wave_index < doctor_index


def test_professional_doctor_verifies_exact_wave_python_runtime() -> None:
    text = DOCTOR.read_text(encoding="utf-8")

    assert 'WAVE_RUNTIME_PYTHON="${HOME}/.local/opt/hazewave-wave-runtime/0.18.1-0.7.1/bin/python"' in text
    assert 'WAVE_RUNTIME=FAIL_NOT_INSTALLED' in text
    assert 'OpenTimelineIO' in text
    assert '0.18.1' in text
    assert 'scenedetect' in text
    assert '0.7.1' in text
    assert 'WAVE_OTIO_RUNTIME=PASS' in text
    assert 'WAVE_SCENE_RUNTIME=PASS' in text


def test_runtime_proof_uses_pinned_wave_runtime_python() -> None:
    text = RUNTIME_PROOF.read_text(encoding="utf-8")

    assert 'WAVE_RUNTIME_PYTHON="${HOME}/.local/opt/hazewave-wave-runtime/0.18.1-0.7.1/bin/python"' in text
    assert '"$WAVE_RUNTIME_PYTHON" -m hazewave.wave_live_proof' in text
    assert 'python -m hazewave.wave_live_proof' not in text


def test_ci_validates_wave_runtime_installer_shell_syntax() -> None:
    text = CI.read_text(encoding="utf-8")

    assert "bash -n scripts/codespaces/install-wave-runtime-pinned.sh" in text
