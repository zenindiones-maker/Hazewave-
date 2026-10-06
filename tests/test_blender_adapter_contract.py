from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "blender" / "hazewave_blender_adapter.py"


def test_blender_adapter_is_static_local_dispatch_without_dynamic_code_execution() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert "import bpy" in text
    assert "HAZEWAVE_BLENDER_ROOT" in text
    assert '"animation.scene.inspect"' in text
    assert '"animation.fixture.create"' in text
    assert "handlers[request[\"operation\"]]" in text
    assert "bpy.app.version_string" in text
    assert "os.replace" in text
    for forbidden in ("eval(", "exec(", "compile(", "subprocess", "socket", "requests."):
        assert forbidden not in text


def test_blender_adapter_owns_fixture_path_and_snapshot_contract() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert "BlenderSceneSnapshot/v1" in text
    assert "fixtures" in text
    assert "bpy.ops.wm.save_as_mainfile" in text
    assert "GREASEPENCIL" in text
    assert "BLENDER_FIXTURE_ALREADY_EXISTS" in text
