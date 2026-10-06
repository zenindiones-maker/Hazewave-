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


def test_blender_snapshot_separates_view_transform_from_look() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert '"view_transform": str(scene.view_settings.view_transform)' in text
    assert '"look": str(scene.view_settings.look)' in text
    assert '"view_transform": str(scene.view_settings.look)' not in text


def test_blender_adapter_builds_real_grease_pencil_shot_contract() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert '"animation.shot.build"' in text
    assert "bpy.data.grease_pencils.new" in text
    assert ".layers.new(" in text
    assert ".frames.new(" in text
    assert ".drawing.add_strokes(" in text
    assert 'drawing.attributes["position"]' in text
    assert '"EXTREME"' in text
    assert '"BREAKDOWN"' in text
    assert "bpy.data.cameras.new" in text
    assert "bpy.data.meshes.new" in text
    assert "bpy.ops.wm.save_as_mainfile" in text


def test_blender_adapter_renders_project_owned_png_frame_sequence() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert '"animation.render.frames"' in text
    assert "frame_root" in text
    assert 'scene.render.image_settings.file_format = "PNG"' in text
    assert "bpy.ops.render.render(animation=True)" in text
    assert "ANIMATION_FRAME_SEQUENCE_MISSING" in text
    assert "ANIMATION_FRAME_SEQUENCE_GAP" in text
    assert "frame_sha256" in text
