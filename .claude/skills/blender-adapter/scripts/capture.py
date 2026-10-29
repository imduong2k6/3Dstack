"""Render the review camera set without touching the user's viewport (tested headless with bpy 5.2.3 using Cycles and Workbench).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/capture.py").read())
    capture_set(r"<project>/reviews/P3-r1", ["CAM_A", "CAM_B", "CAM_TOP"], engine="BLENDER_WORKBENCH")

Every render and output setting it changes is restored afterwards, in the order it was set.
"""
import os

import bpy


def capture_set(out_dir, cameras, engine="BLENDER_WORKBENCH", width=None, height=None, samples=64, color_type="OBJECT"):
    """width/height default to the scene's own resolution, so portrait cameras keep their frame.
    color_type is the Workbench colour source: OBJECT for blockout and placement, MATERIAL for single assets."""
    scene = bpy.context.scene
    r, im = scene.render, scene.render.image_settings
    changes = [(r, "engine", engine), (r, "resolution_x", width or r.resolution_x),
               (r, "resolution_y", height or r.resolution_y), (r, "resolution_percentage", 100),
               # A user's startup compositor (e.g. File Output nodes with empty paths) can blank every capture.
               (r, "use_compositing", False),
               # Multilayer EXR allows no PNG until media_type is IMAGE (Blender 5.x); an output colour-management
               # override would ignore the scene's locked exposure.
               (im, "media_type", "IMAGE"), (im, "file_format", "PNG"), (im, "color_depth", "8"),
               (im, "color_management", "FOLLOW_SCENE")]
    if engine == "CYCLES":
        changes += [(scene.cycles, "samples", samples), (scene.cycles, "use_denoising", True)]
    if engine == "BLENDER_WORKBENCH":
        # Object colours are read without the lighting exposure or white balance, which would blow out or tint them.
        vs = scene.view_settings
        changes += [(scene.display.shading, "color_type", color_type), (vs, "view_transform", "Standard"),
                    (vs, "look", "None"), (vs, "exposure", 0.0), (vs, "use_white_balance", False)]
    saved = [(o, a, getattr(o, a)) for o, a, _ in changes] + [(scene, "camera", scene.camera), (r, "filepath", r.filepath)]
    os.makedirs(out_dir, exist_ok=True)
    try:
        for o, a, v in changes:
            setattr(o, a, v)
        for name in cameras:
            cam = bpy.data.objects.get(name)
            if not cam or cam.type != "CAMERA":
                print(f"missing camera {name}")
                continue
            scene.camera = cam
            r.filepath = os.path.join(out_dir, f"{name}.png")
            bpy.ops.render.render(write_still=True)
    finally:
        for o, a, v in saved:
            setattr(o, a, v)
