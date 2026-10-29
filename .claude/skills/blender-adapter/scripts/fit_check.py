"""Print each landmark's pixel error against the photo at a review camera (check_fit.py is the self-check).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/fit_check.py").read())
    fit_check(r"<project>/kit/LB_Box_A.landmarks.json", overlay=r"<work_dir>/reviews/P8-r1/fit_LB_Box_A.png")

landmarks.json, kept next to the asset spec:
    {"camera": "CAM_A", "res": [600, 800], "photo": "<work_dir>/refs/corridor-01.png",
     "landmarks": [{"id": "lid_front_left", "object": "LB_Box_A.003", "local_m": [-0.15, -0.09, 0.30],
                    "photo_px": [212, 431], "tol_px": 5}]}
photo_px is measured on the photo scaled to res, from the top-left. The overlay draws the photo point green and the
model's point red on the photo, so the worker and the supervisor read the same numbers.
"""
import json

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def fit_check(path, overlay=None):
    spec = json.load(open(path))
    sc = bpy.context.scene
    cam = bpy.data.objects[spec.get("camera", "CAM_A")]
    W, H = spec.get("res", [600, 800])
    if abs(W / H - sc.render.resolution_x / sc.render.resolution_y) > 0.01:
        raise ValueError(f"res {W}x{H} has a different aspect from the scene's {sc.render.resolution_x}x{sc.render.resolution_y}")
    rows = []
    for lm in spec["landmarks"]:
        ob = bpy.data.objects[lm["object"]]
        p = world_to_camera_view(sc, cam, ob.matrix_world @ Vector(lm["local_m"]))
        model = [p.x * W, (1 - p.y) * H]
        err = ((model[0] - lm["photo_px"][0]) ** 2 + (model[1] - lm["photo_px"][1]) ** 2) ** 0.5
        tol = lm.get("tol_px", 5)
        rows.append({"id": lm["id"], "model_px": [round(model[0], 1), round(model[1], 1)], "photo_px": lm["photo_px"],
                     "error_px": round(err, 1), "tol_px": tol, "pass": err <= tol})
    for r in rows:
        print(f'{r["id"]:<28} {r["error_px"]:6.1f} px  (limit {r["tol_px"]})  {"ok" if r["pass"] else "MISS"}')
    if overlay and spec.get("photo"):
        _overlay(spec["photo"], rows, W, H, overlay)
    return rows


def _overlay(photo, rows, W, H, out):
    import numpy as np
    img = bpy.data.images.load(photo, check_existing=False)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    s = max(2, w // 300)                       # marker half-size in photo pixels
    for r in rows:
        for (x, y), col in ((r["photo_px"], (0, 1, 0, 1)), (r["model_px"], (1, 0, 0, 1))):
            cx, cy = int(x * w / W), h - 1 - int(y * h / H)   # Blender rows start at the bottom
            px[max(0, cy - s):cy + s + 1, max(0, cx - s):cx + s + 1] = col
    img.pixels[:] = px.ravel()
    img.filepath_raw, img.file_format = out, "PNG"
    img.save()
    bpy.data.images.remove(img)
