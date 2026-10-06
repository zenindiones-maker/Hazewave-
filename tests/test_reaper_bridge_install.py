from pathlib import Path

from hazewave.reaper_bridge_install import install_reaper_bridge


def test_bridge_installer_preserves_existing_startup_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source.lua"
    source.write_text("-- bridge v1\n", encoding="utf-8")
    resource = tmp_path / "REAPER"
    scripts = resource / "Scripts"
    scripts.mkdir(parents=True)
    startup = scripts / "__startup.lua"
    startup.write_text('reaper.ShowConsoleMsg("mine\\n")\n', encoding="utf-8")

    first = install_reaper_bridge(source=source, resource_dir=resource)
    second = install_reaper_bridge(source=source, resource_dir=resource)

    target = scripts / "Hazewave" / "hazewave_reaper_bridge.lua"
    text = startup.read_text(encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "-- bridge v1\n"
    assert 'reaper.ShowConsoleMsg("mine\\n")' in text
    assert text.count("-- Hazewave REAPER bridge: start") == 1
    assert text.count("-- Hazewave REAPER bridge: end") == 1
    assert 'reaper.GetResourcePath()' in text
    assert 'pcall(dofile, bridge_path)' in text
    assert first["schema"] == "ReaperBridgeInstallReceipt/v1"
    assert first["changed"] is True
    assert second["changed"] is False
    assert first["source_sha256"] == first["target_sha256"]


def test_bridge_installer_backs_up_existing_startup_before_managed_change(tmp_path: Path) -> None:
    source = tmp_path / "source.lua"
    source.write_text("-- bridge v1\n", encoding="utf-8")
    resource = tmp_path / "REAPER"
    scripts = resource / "Scripts"
    scripts.mkdir(parents=True)
    startup = scripts / "__startup.lua"
    startup.write_text("-- owner startup\n", encoding="utf-8")

    receipt = install_reaper_bridge(source=source, resource_dir=resource)

    assert receipt["startup_backup"] is not None
    backup = Path(receipt["startup_backup"])
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == "-- owner startup\n"


def test_bridge_installer_update_replaces_only_managed_block(tmp_path: Path) -> None:
    source = tmp_path / "source.lua"
    source.write_text("-- bridge v1\n", encoding="utf-8")
    resource = tmp_path / "REAPER"

    install_reaper_bridge(source=source, resource_dir=resource)
    startup = resource / "Scripts" / "__startup.lua"
    existing = startup.read_text(encoding="utf-8")
    startup.write_text('-- owner before\n' + existing + '-- owner after\n', encoding="utf-8")

    source.write_text("-- bridge v2\n", encoding="utf-8")
    install_reaper_bridge(source=source, resource_dir=resource)

    text = startup.read_text(encoding="utf-8")
    assert "-- owner before" in text
    assert "-- owner after" in text
    assert text.count("-- Hazewave REAPER bridge: start") == 1
    assert (resource / "Scripts" / "Hazewave" / "hazewave_reaper_bridge.lua").read_text(
        encoding="utf-8"
    ) == "-- bridge v2\n"


def test_professional_desktop_installs_exact_bridge_before_reaper_launch() -> None:
    start = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "codespaces"
        / "start-professional-desktop.sh"
    ).read_text(encoding="utf-8")

    installer_at = start.index("python -m hazewave.reaper_bridge_install")
    reaper_start_at = start.index('--start="$REAPER_BIN"')

    assert installer_at < reaper_start_at
    assert "scripts/reaper/hazewave_reaper_bridge.lua" in start
    assert "--receipt" in start
