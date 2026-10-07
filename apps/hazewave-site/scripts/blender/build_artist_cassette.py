#!/usr/bin/env python3
"""
Hazewave WAVE — deterministic artist cassette factory.

Run inside Blender, not normal CPython:

  blender --background --python apps/hazewave-site/scripts/blender/build_artist_cassette.py -- \
    --artist-id artist-slug \
    --artist-name "ARTIST NAME" \
    --accent "#8f2cff" \
    --shell "#101010" \
    --label-image /absolute/path/to/authorized-art.png \
    --output-glb /absolute/path/to/public/models/cassette-artist-slug.glb \
    --poster /absolute/path/to/public/media/cassette-artist-slug.jpg

The script deliberately creates an ORIGINAL Hazewave cassette grammar. It does
not reproduce any existing branded player/cassette product.

Only owner-authorized artwork may be passed to --label-image.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import bpy


def _hex(value: str) -> tuple[float, float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected 6-digit hex color, got {value!r}")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)


def _args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--artist-id", required=True)
    parser.add_argument("--artist-name", required=True)
    parser.add_argument("--accent", default="#8f2cff")
    parser.add_argument("--shell", default="#111111")
    parser.add_argument("--label-image")
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--poster", required=True)
    parser.add_argument("--poster-size", type=int, default=1200)
    parser.add_argument("--roughness", type=float, default=0.34)
    parser.add_argument("--metallic", type=float, default=0.08)
    parser.add_argument("--wear", type=float, default=0.18)
    return parser.parse_args(argv)


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        # Keep only data generated in this run.
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def _material(
    name: str,
    base: tuple[float, float, float, float],
    *,
    roughness: float,
    metallic: float = 0.0,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("Principled BSDF node unavailable")

    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = max(0.0, min(1.0, roughness))
    bsdf.inputs["Metallic"].default_value = max(0.0, min(1.0, metallic))

    if emission is not None:
        emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        strength_input = bsdf.inputs.get("Emission Strength")
        if emission_input is not None:
            emission_input.default_value = emission
        if strength_input is not None:
            strength_input.default_value = emission_strength

    return material


def _box(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material: bpy.types.Material,
    *,
    bevel: float = 0.08,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        modifier = obj.modifiers.new("HZ_Bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
    obj.data.materials.append(material)
    return obj


def _cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    material: bpy.types.Material,
    *,
    vertices: int = 48,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def _ring(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=48,
        minor_segments=12,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def _label_material(
    image_path: Path,
    fallback: bpy.types.Material,
) -> bpy.types.Material:
    if not image_path.exists():
        raise FileNotFoundError(f"Authorized label image not found: {image_path}")

    material = bpy.data.materials.new("HZ_LabelArtwork")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        return fallback

    image = bpy.data.images.load(str(image_path), check_existing=False)
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])

    alpha_input = bsdf.inputs.get("Alpha")
    if alpha_input is not None:
        links.new(texture.outputs["Alpha"], alpha_input)

    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Metallic"].default_value = 0.0
    return material


def _artist_text(
    artist_name: str,
    accent: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.object.text_add(location=(0.0, -1.56, 0.355))
    text = bpy.context.object
    text.name = "HZ_ArtistMark"
    text.data.body = artist_name.upper()[:28]
    text.data.align_x = "CENTER"
    text.data.align_y = "CENTER"
    text.data.size = 0.28
    text.data.extrude = 0.004
    text.data.bevel_depth = 0.002
    text.data.materials.append(accent)
    bpy.ops.object.convert(target="MESH")
    return text


def _build_cassette(args: argparse.Namespace) -> bpy.types.Object:
    shell_rgba = _hex(args.shell)
    accent_rgba = _hex(args.accent)

    shell = _material(
        "HZ_Shell",
        shell_rgba,
        roughness=args.roughness,
        metallic=args.metallic,
    )
    edge = _material(
        "HZ_Edge",
        tuple(min(1.0, channel * 1.24 + 0.03) for channel in shell_rgba[:3]) + (1.0,),
        roughness=max(0.18, args.roughness - 0.08),
        metallic=min(1.0, args.metallic + 0.10),
    )
    dark = _material("HZ_Window", (0.015, 0.018, 0.017, 1.0), roughness=0.16, metallic=0.18)
    hub = _material("HZ_Hub", (0.74, 0.72, 0.67, 1.0), roughness=0.28, metallic=0.58)
    accent = _material(
        "HZ_Accent",
        accent_rgba,
        roughness=0.28,
        metallic=0.15,
        emission=accent_rgba,
        emission_strength=0.08,
    )
    label_fallback = _material(
        "HZ_LabelFallback",
        tuple(channel * 0.42 for channel in accent_rgba[:3]) + (1.0,),
        roughness=0.44,
        metallic=0.0,
    )
    label_material = (
        _label_material(Path(args.label_image).expanduser().resolve(), label_fallback)
        if args.label_image
        else label_fallback
    )

    root = bpy.data.objects.new("HZ_CassetteRoot", None)
    bpy.context.collection.objects.link(root)
    root["hazewave_asset_type"] = "artist_cassette"
    root["artist_id"] = args.artist_id
    root["artist_name"] = args.artist_name
    root["source_policy"] = "OWNER_AUTHORIZED_ONLY"
    root["factory_version"] = "1"

    body = _box("HZ_Body", (0, 0, 0), (2.95, 1.82, 0.24), shell, bevel=0.14)
    body.parent = root

    inset = _box("HZ_LabelBed", (0, 0.03, 0.265), (2.48, 1.29, 0.035), label_material, bevel=0.10)
    inset.parent = root

    window = _box("HZ_TapeWindow", (0, 0.36, 0.318), (1.47, 0.48, 0.026), dark, bevel=0.12)
    window.parent = root

    for x in (-1.02, 1.02):
        reel_shadow = _cylinder("HZ_ReelShadow", (x, 0.36, 0.354), 0.54, 0.055, dark)
        reel_shadow.parent = root

        reel = _ring("HZ_Reel", (x, 0.36, 0.39), 0.36, 0.09, hub)
        reel.parent = root

        inner = _ring("HZ_ReelAccent", (x, 0.36, 0.405), 0.19, 0.028, accent)
        inner.parent = root

    bridge = _box("HZ_CenterBridge", (0, 0.36, 0.388), (0.30, 0.35, 0.025), edge, bevel=0.06)
    bridge.parent = root

    # Original Hazewave contact rail — visual mechanical grammar used by the site.
    for index, x in enumerate((-0.64, -0.32, 0.0, 0.32, 0.64)):
        contact = _box(
            f"HZ_Contact_{index + 1}",
            (x, -1.48, 0.315),
            (0.09, 0.17, 0.025),
            accent if index == 2 else hub,
            bevel=0.025,
        )
        contact.parent = root

    for index, (x, y) in enumerate(((-2.48, 1.38), (2.48, 1.38), (-2.48, -1.38), (2.48, -1.38))):
        screw = _cylinder(f"HZ_Screw_{index + 1}", (x, y, 0.31), 0.09, 0.045, hub, vertices=24)
        screw.parent = root

    artist_text = _artist_text(args.artist_name, accent)
    artist_text.parent = root

    # Wear is deterministic, not random. The final material pipeline can replace
    # this with authored masks from an authorized artist asset.
    if args.wear > 0:
        wear = _box(
            "HZ_WearStrip",
            (0, 1.50, 0.316),
            (2.18, 0.045 + min(args.wear, 1.0) * 0.04, 0.012),
            edge,
            bevel=0.02,
        )
        wear.parent = root

    return root


def _camera_look_at(camera: bpy.types.Object, target=(0.0, 0.0, 0.0)) -> None:
    direction = mathutils.Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _setup_render(args: argparse.Namespace, root: bpy.types.Object) -> None:
    global mathutils
    import mathutils  # Blender module; imported lazily for normal source linting.

    bpy.ops.object.camera_add(location=(0.0, -8.6, 7.4))
    camera = bpy.context.object
    camera.name = "HZ_PosterCamera"
    camera.data.lens = 58
    _camera_look_at(camera, (0.0, 0.0, 0.0))
    bpy.context.scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(-4.4, -4.0, 6.8))
    key = bpy.context.object
    key.name = "HZ_Key"
    key.data.energy = 920
    key.data.shape = "DISK"
    key.data.size = 4.2
    _camera_look_at(key, (0.0, 0.0, 0.0))

    bpy.ops.object.light_add(type="AREA", location=(4.2, -1.4, 3.8))
    rim = bpy.context.object
    rim.name = "HZ_Rim"
    rim.data.energy = 680
    rim.data.size = 3.2
    _camera_look_at(rim, (0.0, 0.0, 0.0))

    bpy.ops.object.light_add(type="AREA", location=(0.0, 4.0, 2.8))
    fill = bpy.context.object
    fill.name = "HZ_Fill"
    fill.data.energy = 340
    fill.data.size = 5.0
    _camera_look_at(fill, (0.0, 0.0, 0.0))

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = args.poster_size
    scene.render.resolution_y = args.poster_size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 90
    scene.render.film_transparent = False
    scene.render.filepath = str(Path(args.poster).expanduser().resolve())
    scene.world.color = (0.002, 0.002, 0.002)

    Path(scene.render.filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)

    # Cameras/lights are intentionally excluded from the public GLB.
    for obj in (camera, key, rim, fill):
        obj.hide_viewport = True
        obj.hide_render = True


def _export_glb(args: argparse.Namespace) -> None:
    output = Path(args.output_glb).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_extras=True,
    )


def main() -> None:
    args = _args()
    _clear_scene()
    root = _build_cassette(args)
    _setup_render(args, root)
    _export_glb(args)

    print(f"HAZEWAVE_CASSETTE_FACTORY=PASS")
    print(f"ARTIST_ID={args.artist_id}")
    print(f"GLB={Path(args.output_glb).expanduser().resolve()}")
    print(f"POSTER={Path(args.poster).expanduser().resolve()}")


if __name__ == "__main__":
    main()
