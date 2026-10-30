"""Render one side (before or after) of the fix_cams.json frames, headless, on a saved copy; nothing is saved (tested with bpy 5.2.3).

    bash bin/blender-bg <before_copy.blend> --python .claude/skills/review-pairs/scripts/render_pairs.py -- \
        --cams <reviews>/fix_cams.json --out <reviews>/pairs/before --side before [--scale 1] [--ids U1,U2] [--spp 64]
    bash bin/blender-bg <new_gate_copy.blend> --python .../render_pairs.py -- \
        --cams <reviews>/fix_cams.json --out <reviews>/pairs/after --side after --match <reviews>/pairs/before/_meta.json

The cameras come from fix_cams.json, so both sides use identical frames. `--match` puts the before side's view transform, look and
exposure on the after render (and restores the file's own afterwards), so the pair compares the scene and not the exposure.
Cycles uses the file's colour management; Workbench renders in material colour (blender-adapter's capture.py does both).
Writes <id>.png per camera and _meta.json (exposure used, the file's own exposure, device, and how much of each camera's targets is in frame).
Exit 1 if a frame is missing.
"""
import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "..", "..", "blender-adapter", "scripts", "capture.py")).read())

VIEW = ("view_transform", "look", "exposure", "gamma", "use_white_balance", "white_balance_temperature", "white_balance_tint")


def use_gpu():
    """GPU for this session only (factory startup, preferences never saved); CPU when there is none."""
    cp = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            cp.compute_device_type = t
            cp.get_devices()
            devs = [d for d in cp.devices if d.type == t]
            if devs:
                for d in cp.devices:
                    d.use = d.type == t
                bpy.context.scene.cycles.device = "GPU"
                return t + ": " + ", ".join(d.name for d in devs)
        except Exception:
            pass
    bpy.context.scene.cycles.device = "CPU"
    return "CPU"


def view_state():
    vs = bpy.context.scene.view_settings
    return {k: getattr(vs, k) for k in VIEW if hasattr(vs, k)}


def in_frame(scene, cam, names):
    """Share of the targets' bounding-box corners inside the camera frame; None when none of them exists in this file
    (an object the fix adds is absent on the before side, one it removes on the after side)."""
    pts = []
    for n in names:
        o = bpy.data.objects.get(n)
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box] if o else []
    if not pts:
        return None
    ok = 0
    for p in pts:
        v = world_to_camera_view(scene, cam, p)
        ok += 0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0
    return round(ok / len(pts), 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cams", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--side", required=True, choices=["before", "after"])
    ap.add_argument("--scale", type=float, default=1.0, help="below 1 renders a quick framing preview")
    ap.add_argument("--ids", help="comma list of camera IDs to render")
    ap.add_argument("--spp", type=int, help="Cycles samples (default 64; 16 for a preview)")
    ap.add_argument("--match", help="the before side's _meta.json: use its exposure and view transform")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = json.load(open(a.cams))
    only = set(a.ids.split(",")) if a.ids else None
    sc = bpy.context.scene
    own = view_state()
    meta = {"side": a.side, "file": bpy.data.filepath, "file_view": own}
    if a.match:
        want = json.load(open(a.match))["view"]
        for k, v in want.items():
            if hasattr(sc.view_settings, k):
                setattr(sc.view_settings, k, v)
        meta["matched_to"] = a.match
        meta["file_differs"] = {k: [own[k], want[k]] for k in want if k in own and own[k] != want[k]}
    meta["view"] = view_state()
    meta["device"] = use_gpu()
    spp = a.spp or (64 if a.scale >= 1 else 16)
    sc.cycles.seed = 7
    os.makedirs(a.out, exist_ok=True)
    col = bpy.data.collections.new("PAIRS_tmp_cams")
    sc.collection.children.link(col)
    done, frames = [], {}
    for c in spec["cams"]:
        if only and c["id"] not in only:
            continue
        t = dict(c, **c["before"]) if a.side == "before" and c.get("before") else c
        W, H = (max(16, round(v * a.scale)) for v in c.get("res_px") or spec["res_px"])
        cd = bpy.data.cameras.new("FIXCAM_" + c["id"])
        cd.sensor_width, cd.sensor_fit = 36.0, t["sensor_fit"]
        cd.shift_x, cd.shift_y = t["shift"]
        cd.clip_start, cd.clip_end = t.get("clip_m") or (0.05, 300)  # a plan or review camera's clip sets its cut plane
        if t.get("ortho_scale"):
            cd.type, cd.ortho_scale = "ORTHO", t["ortho_scale"]
        else:
            cd.lens = t["lens_mm"]
        ob = bpy.data.objects.new("FIXCAM_" + c["id"], cd)
        col.objects.link(ob)
        ob.location, ob.rotation_euler = t["loc_m"], [math.radians(r) for r in t["rot_deg"]]
        shown = [bpy.data.objects[n] for n in c.get("show", []) if n in bpy.data.objects]
        for o in shown:
            col.objects.link(o)
        bpy.context.view_layer.update()
        frames[c["id"]] = {"targets_in_frame": in_frame(sc, ob, c.get("targets", []))}
        kw = {"color_type": "MATERIAL"} if c["engine"] == "BLENDER_WORKBENCH" else {"samples": spp}
        capture_set(a.out, ["FIXCAM_" + c["id"]], engine=c["engine"], width=W, height=H, lint=False, **kw)  # BEFORE is an old backup; the gate capture is what lint gates
        for o in shown:
            col.objects.unlink(o)
        tmp, dst = os.path.join(a.out, "FIXCAM_" + c["id"] + ".png"), os.path.join(a.out, c["id"] + ".png")
        if os.path.exists(tmp):
            os.replace(tmp, dst)
        if os.path.exists(dst):
            done.append(c["id"])
    meta.update(rendered=done, frames=frames, cycles_spp=spp, size_scale=a.scale)
    json.dump(meta, open(os.path.join(a.out, "_meta.json"), "w"), indent=1)
    want_ids = [c["id"] for c in spec["cams"] if not only or c["id"] in only]
    print("PAIRS", a.side, "rendered", len(done), "of", len(want_ids), "device", meta["device"], "exposure", meta["view"].get("exposure"))
    low = [k for k, v in frames.items() if v["targets_in_frame"] is not None and v["targets_in_frame"] < 0.5]
    if low:
        print("WARN targets mostly outside the frame in", low)
    if done != want_ids:
        print("MISSING", sorted(set(want_ids) - set(done)))
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:  # under --python an exception would exit 0
        import traceback
        traceback.print_exc()
        print("render_pairs error:", repr(e))
        sys.exit(1)
