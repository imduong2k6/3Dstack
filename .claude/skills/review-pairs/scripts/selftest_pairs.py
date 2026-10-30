"""Headless self-test for the review-pairs scripts on a synthetic scene (never touches a project):

    bash bin/blender-bg --python .claude/skills/review-pairs/scripts/selftest_pairs.py -- <repo> <out_dir>

Builds a before and an after file (one object moved and recoloured, one untouched, a screen hiding one target from the
nearest review camera, and a different exposure in the after file). Then it runs fix_cams.py, render_pairs.py on each side
and compose_pairs.py as the manager does, and checks: every target is in frame, the hidden target gets a clear view, the
untouched object renders pixel-identical on both sides (same camera, same exposure), the changed one differs, the exposure
was matched, the pairs and the board index are written, and a missing target exits 1.
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

repo, out = sys.argv[sys.argv.index("--") + 1:][:2]
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out)
SK = os.path.join(repo, ".claude/skills/review-pairs/scripts")
FACES = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
VERTS = [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5), (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)]


def cube(name, size, loc, rgb):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x * size[0], y * size[1], z * size[2]) for x, y, z in VERTS], [], FACES)
    m = bpy.data.materials.new("M_" + name)
    m.diffuse_color = (*rgb, 1)
    for n in (m.node_tree.nodes if m.node_tree else []):
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (*rgb, 1)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


def cam(name, loc, aim):
    d = bpy.data.cameras.new(name)
    d.lens = 28
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


def build(path, after):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 640, 480
    sc.view_settings.view_transform, sc.view_settings.exposure = "AgX", 0.5 + (0.7 if after else 0.0)
    cube("Floor", (12, 14, 0.1), (0, 2, -0.05), (.6, .6, .6))
    cube("Pillar", (0.4, 0.4, 2), (-2, 2, 1), (.2, .7, .3))
    cube("Box_A", (0.5, 0.5, 0.5), (-1 + (0.8 if after else 0), 0, 0.25), (.2, .2, .9) if after else (.9, .2, .2))
    cube("Screen", (3, 0.1, 2), (3, 1.5, 1), (.5, .5, .5))
    cube("Target_B", (0.5, 0.5, 0.5), (3, 3, 0.3), (.9, .8, .1))
    if after:
        cube("Added_C", (0.4, 0.4, 0.8), (-3, -2, 0.4), (.8, .3, .8))  # a fix that adds an object
    sc.camera = cam("CAM_Main", (3, -5, 1.5), (3, 2, 1))
    cam("CAM_Side", (-6, 2, 1.5), (3, 2, 0.5))
    ld = bpy.data.lights.new("Sun", "SUN")
    ld.energy = 3
    lo = bpy.data.objects.new("Sun", ld)
    lo.rotation_euler = (0.8, 0.2, 0.5)
    sc.collection.objects.link(lo)
    w = bpy.data.worlds.new("W")
    sc.world = w
    if w.node_tree:
        w.node_tree.nodes["Background"].inputs["Color"].default_value = (.5, .5, .5, 1)
    bpy.ops.wm.save_as_mainfile(filepath=path)


def sh(*args):
    r = subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def py(blend, script, *args):
    return sh(*([blend] if blend else []), "--python", os.path.join(SK, script), "--", *args)


def pixels(p):
    im = bpy.data.images.load(p, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


BEFORE, AFTER = os.path.join(out, "before.blend"), os.path.join(out, "after.blend")
build(BEFORE, False)
build(AFTER, True)
cams_json = os.path.join(out, "cameras.json")
json.dump([{"id": "CAM_Main", "pos_m": [3, -5, 1.5], "rot_deg": [round(math.degrees(v), 3) for v in bpy.data.objects["CAM_Main"].rotation_euler],
            "lens_mm": 28, "sensor_fit": "AUTO", "shift": [0, 0], "res_px": [640, 480]}], open(cams_json, "w"))
issues = {"res_px": [640, 480], "issues": [
    {"id": "I1", "caption": "Box_A is red and sits in the wrong place: it moves and turns blue.", "targets": ["Box_A"], "engine": "WORKBENCH", "fill": 0.6},
    {"id": "I2", "caption": "Target_B is hidden behind the screen from the main camera.", "targets": ["Target_B"], "engine": "WORKBENCH", "fill": 0.5, "from_camera": "CAM_Main"},
    {"id": "I3", "kind": "review_cam", "camera": "CAM_Main", "engine": "CYCLES", "caption": "Whole view from the main review camera."},
    {"id": "I4", "caption": "The pillar is untouched: both sides must be identical.", "targets": ["Pillar"], "engine": "WORKBENCH", "fill": 0.5},
    {"id": "I6", "caption": "Added_C is missing before the fix.", "targets": ["Added_C", "Box_A"], "engine": "WORKBENCH", "fill": 0.6},
    {"id": "I7", "caption": "A location, not an object: the box around the pillar, from a fixed eye-height camera.", "boxes": [[[-2.3, 1.7, 0], [-1.7, 2.3, 2]]],
     "loc_m": [-2, -3, 1.5], "lens_mm": 30, "engine": "WORKBENCH"},
    {"id": "I5", "kind": "plan", "centre_xy": [0, 2], "ortho_scale": 12, "cut_z": 1.0, "engine": "WORKBENCH", "caption": "Top view, cut at 1 m."}]}
issues_json = os.path.join(out, "fix_issues.json")
json.dump(issues, open(issues_json, "w"))
fix = os.path.join(out, "fix_cams.json")

rc, log = py(BEFORE, "fix_cams.py", "--issues", issues_json, "--out", fix, "--cameras", cams_json)
assert rc == 1 and "Added_C" in json.load(open(fix))["missing"], "a target only in the new file needs --after"
rc, log = py(BEFORE, "fix_cams.py", "--issues", issues_json, "--out", fix, "--cameras", cams_json, "--after", AFTER)
assert rc == 0, log[-1500:]
cams = {c["id"]: c for c in json.load(open(fix))["cams"]}
assert list(cams) == ["I1", "I2", "I3", "I4", "I6", "I7", "I5"] and cams["I2"]["visible_fraction"] >= 0.75 and cams["I3"]["res_px"] == [640, 480]
assert cams["I7"]["loc_m"] == [-2, -3, 1.5] and cams["I7"]["lens_mm"] == 30 and "visible_fraction" not in cams["I7"], "explicit camera is kept"
wrapped, one = os.path.join(out, "cameras_wrapped.json"), os.path.join(out, "fix_issues_one.json")   # the {"cameras": [...]} shape with aim_m, as lint reads it
json.dump({"cameras": [{"id": "CAM_Main", "pos_m": [3, -5, 1.5], "aim_m": [0, 2, 1], "lens_mm": 28}]}, open(wrapped, "w"))
json.dump({"res_px": [640, 480], "issues": [issues["issues"][2]]}, open(one, "w"))
rc, log = py(BEFORE, "fix_cams.py", "--issues", one, "--out", os.path.join(out, "fix_cams_wrapped.json"), "--cameras", wrapped)
assert rc == 0 and json.load(open(os.path.join(out, "fix_cams_wrapped.json")))["cams"][0]["loc_m"] == [3, -5, 1.5], log[-1500:]
ortho, one_o, fix_o = (os.path.join(out, n) for n in ("cameras_ortho.json", "fix_issues_ortho.json", "fix_cams_ortho.json"))  # a plan review camera: no lens
json.dump({"cameras": [{"id": "CAM_Plan", "type": "ortho", "pos_m": [0, 2, 20], "rot_deg": [0, 0, 0], "lens_mm": None, "ortho_scale": 12,
                        "clip_m": [18.5, 30], "res_px": [320, 240]}]}, open(ortho, "w"))
json.dump({"res_px": [320, 240], "issues": [{"id": "I8", "kind": "review_cam", "camera": "CAM_Plan", "engine": "WORKBENCH", "caption": "Plan view.", "res_px": [200, 150]},
                                            {"id": "I9", "targets": ["Pillar"], "engine": "WORKBENCH", "fill": 0.85, "res_px": [240, 640], "caption": "Portrait."}]}, open(one_o, "w"))
rc, log = py(BEFORE, "fix_cams.py", "--issues", one_o, "--out", fix_o, "--cameras", ortho)
c8 = json.load(open(fix_o))["cams"][0]
assert rc == 0 and c8["ortho_scale"] == 12 and c8["clip_m"] == [18.5, 30] and c8["res_px"] == [200, 150], log[-1500:]   # the issue's res_px wins
cwd = os.getcwd()
os.chdir(out)  # a relative --out: Blender reads a relative render path from the drive root
rc, log = py(BEFORE, "render_pairs.py", "--cams", fix_o, "--out", "pairs_ortho", "--side", "before", "--scale", "0.5")
os.chdir(cwd)
assert rc == 0 and os.path.exists(os.path.join(out, "pairs_ortho", "I8.png")), log[-1500:]
assert json.load(open(os.path.join(out, "pairs_ortho", "_meta.json")))["frames"]["I9"]["targets_in_frame"] == 1.0, "portrait frame measured at the scene's aspect"


def in_frame(blend, cid, names):
    """Every bounding-box corner of the named objects is inside camera cid's frame."""
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    d = bpy.data.cameras.new(cid)
    d.lens, d.sensor_width, d.sensor_fit = cams[cid]["lens_mm"], 36, "HORIZONTAL"
    o = bpy.data.objects.new(cid, d)
    o.location, o.rotation_euler = cams[cid]["loc_m"], [math.radians(v) for v in cams[cid]["rot_deg"]]
    sc.collection.objects.link(o)
    bpy.context.view_layer.update()
    for t in names:
        for c in bpy.data.objects[t].bound_box:
            v = world_to_camera_view(sc, o, bpy.data.objects[t].matrix_world @ Vector(c))
            assert 0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0, (blend, cid, t, tuple(v))


for cid, names in (("I1", ["Box_A"]), ("I2", ["Target_B"]), ("I4", ["Pillar"])):
    in_frame(BEFORE, cid, names)
for cid, names in (("I1", ["Box_A"]), ("I6", ["Added_C", "Box_A"])):
    in_frame(AFTER, cid, names)  # the same camera still holds the moved and the added object
bpy.ops.wm.open_mainfile(filepath=BEFORE)
sc = bpy.context.scene
cam2, tgt = Vector(cams["I2"]["loc_m"]), bpy.data.objects["Target_B"].location
hit = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), cam2, (tgt - cam2).normalized(), distance=(tgt - cam2).length - 0.5)
assert not hit[0] or hit[4].name == "Target_B", "I2 camera still looks through the screen: " + str(hit[4])
print("ok  fix_cams: 7 cameras, targets in frame on both sides (moved and added objects too), the hidden target gets a clear view", cams["I2"]["loc_m"], cams["I2"]["visible_fraction"])

bad = dict(issues, issues=issues["issues"] + [{"id": "I9", "caption": "x", "targets": ["No_Such_Object"]}])
json.dump(bad, open(os.path.join(out, "bad_issues.json"), "w"))
rc, log = py(BEFORE, "fix_cams.py", "--issues", os.path.join(out, "bad_issues.json"), "--out", os.path.join(out, "bad_cams.json"))
assert rc == 1 and "No_Such_Object" in json.load(open(os.path.join(out, "bad_cams.json")))["missing"]
print("ok  a missing target exits 1")

pairs = os.path.join(out, "pairs")
rc, log = py(BEFORE, "render_pairs.py", "--cams", fix, "--out", os.path.join(pairs, "before"), "--side", "before", "--scale", "0.5", "--spp", "8")
assert rc == 0, log[-1500:]
rc, log = py(AFTER, "render_pairs.py", "--cams", fix, "--out", os.path.join(pairs, "after"), "--side", "after", "--scale", "0.5", "--spp", "8",
             "--match", os.path.join(pairs, "before", "_meta.json"))
assert rc == 0, log[-1500:]
mb, ma = (json.load(open(os.path.join(pairs, s, "_meta.json"))) for s in ("before", "after"))
assert mb["view"]["exposure"] == ma["view"]["exposure"] == 0.5 and abs(ma["file_view"]["exposure"] - 1.2) < 1e-6 and "exposure" in ma["file_differs"]
pb, pa = pixels(os.path.join(pairs, "before", "I4.png")), pixels(os.path.join(pairs, "after", "I4.png"))
green = (pb[..., 1] > pb[..., 0] + 0.1) & (pb[..., 1] > pb[..., 2] + 0.1)  # the untouched pillar; Box_A also moved into this frame
ys = np.nonzero(green)[0]
green[: int(np.median(ys))] = False  # rows are bottom-first: keep the pillar's upper half, clear of Box_A's edge
assert pb.shape == (240, 320, 4) and green.sum() > 150, green.sum()
assert np.abs(pb - pa)[green].max() == 0, "untouched object differs between sides"
diff = pixels(os.path.join(pairs, "before", "I1.png")) - pixels(os.path.join(pairs, "after", "I1.png"))
assert np.abs(diff).mean() > 0.002, "moved object looks the same on both sides"
c3 = np.abs(pixels(os.path.join(pairs, "before", "I3.png")) - pixels(os.path.join(pairs, "after", "I3.png")))
assert c3.mean() < 0.05 and ma["frames"]["I1"]["targets_in_frame"] >= 0.5
print("ok  render: identical frames and exposure (untouched object identical, moved object differs); exposure matched over the file's own 1.2")

rc, log = py(None, "compose_pairs.py", "pairs", "--cams", fix, "--dir", pairs, "--before-label", "r2", "--after-label", "r3", "--cell-width", "320")
assert rc == 0, log[-1500:]
idx = json.load(open(os.path.join(pairs, "pairs.json")))
assert [p["id"] for p in idx["pairs"]] == ["I1", "I2", "I3", "I4", "I6", "I7", "I5"] and idx["before"] == "r2"
im = bpy.data.images.load(idx["pairs"][0]["file"])
assert im.size[0] == 3 * 16 + 2 * 320 and im.size[1] > 240, tuple(im.size)
assert any("matched to the before side" in n for n in idx["pairs"][2]["notes"]) and "Exposure" in idx["pairs"][2]["notes"][0]
rc, log = py(None, "compose_pairs.py", "contact", "--cams", fix, "--dir", os.path.join(pairs, "before"), "--out", os.path.join(pairs, "framing.png"))
assert rc == 0 and os.path.getsize(os.path.join(pairs, "framing.png")) > 5000, log[-800:]
rc, log = py(None, "compose_pairs.py", "contact", "--dir", os.path.join(pairs, "before"), "--out", os.path.join(out, "contact.png"), "--title", "gate")
assert rc == 0 and os.path.getsize(os.path.join(out, "contact.png")) > 5000, log[-800:]   # the gate contact sheet, no fix_cams
print("ok  compose: 7 captioned pairs, pairs.json for the board, framing and gate contact sheets")
print("review-pairs self-test passed")
