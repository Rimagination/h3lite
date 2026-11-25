"""Export a compact scene snapshot from inside Blender (headless or MCP).

Usage:
  blender -b scene.blend --python blender_scene_snapshot.py -- --out scene_info.json
  blender -b scene.blend --python blender_scene_snapshot.py -- --out scene_info.json --render-frame --render-path smoke.png

Run inside Blender only; system Python cannot import bpy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write scene_info.json here")
    parser.add_argument("--render-frame", action="store_true", help="render the current frame as a smoke test")
    parser.add_argument("--render-path", default="//scene_smoke.png", help="smoke render output path")
    parser.add_argument("--audit", action="store_true", help="run naming/framing/camera/action checks")
    parser.add_argument("--expected-fps", type=float, help="audit: expected scene fps")
    parser.add_argument("--expected-width", type=int, help="audit: expected render width")
    parser.add_argument("--expected-height", type=int, help="audit: expected render height")
    parser.add_argument("--expect-camera-move", action="store_true", help="audit: require an action on the active camera")
    parser.add_argument("--fail-on-warnings", action="store_true", help="exit 1 when audit has warnings or errors")
    return parser.parse_args(argv)


def vector(value: Vector) -> list[float]:
    return [round(float(component), 4) for component in value]


def camera_info(obj) -> dict:
    data = obj.data
    return {
        "name": obj.name,
        "location": vector(obj.matrix_world.translation),
        "rotation_euler": [round(float(value), 4) for value in obj.rotation_euler],
        "lens_mm": round(float(data.lens), 3),
        "sensor_width_mm": round(float(data.sensor_width), 3),
        "clip_start": round(float(data.clip_start), 4),
        "clip_end": round(float(data.clip_end), 2),
        "type": data.type,
    }


def object_info(obj) -> dict:
    entry = {
        "name": obj.name,
        "type": obj.type,
        "location": vector(obj.matrix_world.translation),
        "scale": vector(obj.scale),
        "hide_render": bool(obj.hide_render),
        "parent": obj.parent.name if obj.parent else None,
        "collections": [collection.name for collection in obj.users_collection],
    }
    if obj.animation_data and obj.animation_data.action:
        entry["action"] = obj.animation_data.action.name
    return entry


def main() -> int:
    args = parse_args()
    scene = bpy.context.scene
    bpy.context.view_layer.update()

    cameras = [obj for obj in scene.objects if obj.type == "CAMERA"]
    lights = [obj for obj in scene.objects if obj.type == "LIGHT"]
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    materials = list(bpy.data.materials)
    actions = list(bpy.data.actions)

    snapshot = {
        "blender_version": bpy.app.version_string,
        "filepath": bpy.data.filepath,
        "scene": scene.name,
        "fps": float(scene.render.fps) / float(scene.render.fps_base or 1.0),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "frame_current": int(scene.frame_current),
        "resolution": {
            "x": int(scene.render.resolution_x),
            "y": int(scene.render.resolution_y),
            "percentage": int(scene.render.resolution_percentage),
            "aspect_x": int(scene.render.pixel_aspect_x),
            "aspect_y": int(scene.render.pixel_aspect_y),
        },
        "engine": scene.render.engine,
        "camera": scene.camera.name if scene.camera else None,
        "cameras": [camera_info(obj) for obj in cameras],
        "lights": [{"name": obj.name, "type": obj.data.type, "energy": float(obj.data.energy)} for obj in lights],
        "object_counts": {
            "total": len(scene.objects),
            "mesh": len(meshes),
            "camera": len(cameras),
            "light": len(lights),
        },
        "collections": [collection.name for collection in bpy.data.collections],
        "materials": [material.name for material in materials],
        "actions": [{"name": action.name, "frame_range": [float(value) for value in action.frame_range]} for action in actions],
        "objects": [object_info(obj) for obj in scene.objects],
        "warnings": [],
    }

    if not scene.camera:
        snapshot["warnings"].append("scene has no active camera")
    if scene.render.resolution_percentage != 100:
        snapshot["warnings"].append("resolution_percentage is not 100; final render will be scaled")

    if args.render_frame:
        if not scene.camera:
            snapshot["warnings"].append("smoke render skipped: no active camera")
        else:
            render_path = bpy.path.abspath(args.render_path)
            os.makedirs(os.path.dirname(render_path) or ".", exist_ok=True)
            scene.render.filepath = render_path
            scene.render.image_settings.file_format = "PNG"
            bpy.ops.render.render(write_still=True)
            snapshot["smoke_render"] = {
                "path": render_path,
                "exists": os.path.isfile(render_path),
                "bytes": os.path.getsize(render_path) if os.path.isfile(render_path) else None,
            }

    exit_code = 0
    if args.audit:
        checks: list[dict] = []
        warnings: list[str] = []
        errors: list[str] = []

        def check(name: str, ok: bool, message: str, *, error: bool = False) -> None:
            checks.append({"check": name, "ok": bool(ok), "message": message if not ok else "ok"})
            if not ok:
                (errors if error else warnings).append(message)

        check("active_camera", bool(scene.camera), "scene has no active camera", error=True)
        check("frame_range", scene.frame_end > scene.frame_start, "frame_end must be greater than frame_start", error=True)
        check(
            "resolution_percentage",
            scene.render.resolution_percentage == 100,
            "resolution_percentage is not 100; final render will be scaled",
        )
        camera_names = [obj.name for obj in cameras]
        check(
            "camera_naming",
            all(name.startswith("CAM_") for name in camera_names) if camera_names else True,
            "camera names should start with CAM_: " + ", ".join(name for name in camera_names if not name.startswith("CAM_")),
        )
        target_names = [obj.name for obj in scene.objects if obj.type == "EMPTY" and obj.name.startswith("EMPTY_CamTarget_")]
        check(
            "camera_target",
            bool(target_names) if cameras else True,
            "no EMPTY_CamTarget_* empty found; camera aim is not explicit",
        )
        action_names = [action.name for action in actions]
        check(
            "action_naming",
            all(name.startswith("AN_") for name in action_names) if action_names else True,
            "action names should start with AN_: " + ", ".join(name for name in action_names if not name.startswith("AN_")),
        )
        check(
            "collection_naming",
            any(collection.name.startswith("COL_") for collection in bpy.data.collections) if scene.objects else True,
            "no COL_* collection found",
        )
        if scene.camera:
            active = scene.camera
            check("camera_lens", float(active.data.lens) > 0.0, "active camera lens must be > 0", error=True)
            if args.expect_camera_move:
                has_move = bool(active.animation_data and active.animation_data.action)
                check("camera_move", has_move, "expect_camera_move is set but active camera has no action", error=True)
        if args.expected_fps is not None:
            current_fps = float(scene.render.fps) / float(scene.render.fps_base or 1.0)
            check("expected_fps", abs(current_fps - args.expected_fps) <= 0.01, f"fps {current_fps} != expected {args.expected_fps}", error=True)
        if args.expected_width is not None:
            check("expected_width", int(scene.render.resolution_x) == args.expected_width, f"width {scene.render.resolution_x} != expected {args.expected_width}", error=True)
        if args.expected_height is not None:
            check("expected_height", int(scene.render.resolution_y) == args.expected_height, f"height {scene.render.resolution_y} != expected {args.expected_height}", error=True)

        snapshot["audit"] = {"checks": checks, "warnings": warnings, "errors": errors}
        if errors or warnings:
            snapshot["warnings"].extend(warnings)
        if args.fail_on_warnings and (warnings or errors):
            exit_code = 1

    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    print(text, flush=True)
    if args.out:
        output_path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"snapshot written: {output_path}", file=sys.stderr, flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
