from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "codespaces" / "install-blender-pinned.sh"
UPGRADE = ROOT / "scripts" / "codespaces" / "upgrade-professional-v2.sh"
DOCTOR = ROOT / "scripts" / "codespaces" / "professional-doctor.sh"


def test_blender_installer_is_official_pinned_checksum_verified_portable() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert 'BLENDER_VERSION="5.2.2"' in text
    assert 'blender-5.2.2-linux-x64.tar.xz' in text
    assert 'https://download.blender.org/release/Blender5.2' in text
    assert 'blender-5.2.2.sha256' in text
    assert "sha256sum -c" in text
    assert "--disable-autoexec" in text
    assert '${HOME}/.local/opt/blender/5.2.2' in text
    assert '${HOME}/.local/bin/blender' in text
    assert "BLENDER_VERSION_PIN=5.2.2" in text
    assert "BLENDER_SOURCE=OFFICIAL_BLENDER_FOUNDATION" in text
    assert "PAID_FALLBACK=FALSE" in text
    assert "UNKNOWN_COST_FALLBACK=FALSE" in text

    for forbidden in ("snap install", "flatpak install", "sudo apt-get install blender"):
        assert forbidden not in text


def test_professional_upgrade_installs_blender_before_runtime_doctor() -> None:
    text = UPGRADE.read_text(encoding="utf-8")

    blender_index = text.index("install-blender-pinned.sh")
    doctor_index = text.index("professional-doctor.sh")
    assert blender_index < doctor_index


def test_professional_doctor_requires_exact_blender_522_runtime() -> None:
    text = DOCTOR.read_text(encoding="utf-8")

    assert 'EXPECTED_BLENDER="${HOME}/.local/opt/blender/5.2.2/blender"' in text
    assert 'BLENDER_LINK="${HOME}/.local/bin/blender"' in text
    assert "BLENDER_RUNTIME=FAIL_NOT_INSTALLED" in text
    assert "BLENDER_RUNTIME=FAIL_UNEXPECTED_BINARY" in text
    assert '"$BLENDER_LINK" --background --factory-startup --disable-autoexec --version' in text
    assert "Blender 5.2.2 LTS" in text
    assert "BLENDER_RUNTIME=PASS" in text
    assert "BLENDER_VERSION_PIN=5.2.2" in text
