import ast
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

    tree = ast.parse(text)
    forbidden_calls = {"eval", "exec", "compile"}
    forbidden_imports = {"subprocess", "socket", "requests"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden_imports for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_imports


def test_blender_adapter_owns_fixture_path_and_snapshot_contract() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert "BlenderSceneSnapshot/v1" in text
    assert "fixtures" in text
    assert "bpy.ops.wm.save_as_mainfile" in text
    assert "GREASEPENCIL" in text
    assert "BLENDER_FIXTURE_ALREADY_EXISTS" in text
