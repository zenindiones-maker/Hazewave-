"""Deterministic read-only diagnostics contracts."""
from pathlib import Path
import importlib.util
import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts" / "fyahreaper-remote-doctor-existing-haze-workstation.py"
spec = importlib.util.spec_from_file_location("fyahreaper_doctor", FILE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_probe_web_interface_only_specific_port():
    ini = "[reaper]\ncsurf_0=HTTP 0 2307 '' 'index.html' 0 ''\ncsurf_1=HTTP 0 8000 '' 'index.html' 0 ''\n"
    assert module.has_web_interface(ini, 2307)
    assert not module.has_web_interface(ini, 2306)


def test_fake_comment_does_not_count_as_configuration():
    ini = "[reaper]\n;csurf_0=HTTP 0 2307 '' 'index.html' 0 ''\n#csurf_1=HTTP 0 2307\n"
    assert not module.has_web_interface(ini, 2307)


def test_source_validation_fail_closed_for_unexpected_pin(tmp_path):
    source = tmp_path / "source-bad" / "apps" / "fyahreaper_remote"
    source.mkdir(parents=True)
    (source / "reaper_bridge.py").write_text("pass\n")
    with pytest.raises(ValueError, match="SOURCE_NOT_EXPECTED_RELEASE"):
        module.validate_source(source)


def test_source_validation_rejects_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "reaper_bridge.py").write_text("pass\n")
    src = tmp_path / ("source-" + module.PIN) / "apps"
    src.mkdir(parents=True)
    (src / "fyahreaper_remote").symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="SOURCE_SYMLINK"):
        module.validate_source(src / "fyahreaper_remote")


def test_health_json_requires_real_connection():
    assert module.is_healthy('{"reaper_connected":true,"state":"stopped","reaper_version":"7.82"}')
    assert not module.is_healthy('{"reaper_connected":false,"state":"stopped"}')
    assert not module.is_healthy("not json")
