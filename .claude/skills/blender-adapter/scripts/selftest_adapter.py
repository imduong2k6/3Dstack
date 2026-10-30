"""Self-test for the step ledger, stats, capture lint gate and measure.grid_stats (headless; writes only under <out_dir>):

    bash bin/blender-bg --python-exit-code 1 --python .claude/skills/blender-adapter/scripts/selftest_adapter.py -- <out_dir>

Ends with ADAPTER SELFTEST OK, or FAILED and exit 1. check_capture.py still tests that capture restores every setting.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(os.getcwd(), "selftest_adapter_out")
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stepmod, statsmod, capmod, meas = load("step_log"), load("stats"), load("capture"), load("measure")
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL:", msg)


def expect_raises(exc, fn, msg):
    try:
        fn()
    except exc:
        return
    except Exception as e:
        fails.append(f"{msg}: raised {type(e).__name__}: {e}")
        print("FAIL:", fails[-1])
        return
    fails.append(f"{msg}: did not raise")
    print("FAIL:", fails[-1])


def box(name, lo, hi, mat=True):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]), verts=bm.verts)
    bmesh.ops.translate(bm, vec=[(a + b) / 2 for a, b in zip(lo, hi)], verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(M)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def run_blender(file, *args):
    p = subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", file, "--python", *args], capture_output=True, text=True)
    return p.returncode, p.stdout[-400:]


# ---- scene ---------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
M = bpy.data.materials.new("M")
M.diffuse_color = (0.8, 0.2, 0.2, 1)
box("Floor", (-3, -3, -0.1), (3, 3, 0))
box("Crate", (0, 0, 0), (1, 1, 1))
cd = bpy.data.cameras.new("CAM_A")
cd.lens = 24
cam = bpy.data.objects.new("CAM_A", cd)
cam.location, cam.rotation_euler = (5, -5, 3), (1.1, 0, 0.785)
sc.collection.objects.link(cam)
sc.render.resolution_x, sc.render.resolution_y = 300, 400
proj = os.path.join(out, "project")
os.makedirs(os.path.join(proj, "light"))
os.makedirs(os.path.join(proj, "plan"))
json.dump([{"id": "CAM_A", "pos_m": [5, -5, 3], "lens_mm": 24, "res_px": [200, 100], "shift": [0.1, -0.05], "sensor_mm": 30, "sensor_fit": "VERTICAL"}],
          open(os.path.join(proj, "light", "cameras.json"), "w"))
work = os.path.join(out, "work", "scene.blend")
os.makedirs(os.path.dirname(work))
bpy.ops.wm.save_as_mainfile(filepath=work)

# ---- step ledger ---------------------------------------------------------------
steps = os.path.join(proj, "plan", "steps.json")
bk = stepmod.backup_path(os.path.join(out, "phase"), "scene", "P1", "first")
check(bk.endswith(os.path.join("backups", "scene_P1_01_first.blend")), f"backup name {bk}")
e1 = stepmod.log_step(steps, "tester", "first step", bk, "P1", "first")
check(os.path.getsize(bk) > 0 and e1["n"] == 1 and e1["objects"] == 3, f"first entry {e1}")
check(stepmod.backup_path(os.path.join(out, "phase"), "scene", "P1", "next").endswith("scene_P1_02_next.blend"), "next backup number")
d = stepmod.diff_state(steps)
check(d["ok"] and not d["drift"] and d["file_is_last_entry_file"], f"clean diff {d}")
cam.location.x += 1.0
bpy.data.objects.remove(bpy.data.objects["Crate"])
d = stepmod.diff_state(steps)
check(d["drift"]["objects"]["removed"] == ["Crate"] and d["drift"]["cameras_lights"]["changed"] == ["CAM_A"], f"drift report {d['drift']}")
for fn, msg in ((lambda: stepmod.log_step(steps, "", "x", bk), "log without who"), (lambda: stepmod.log_step(steps, "t", "x", None), "log without backup")):
    expect_raises(stepmod.StepLogError, fn, msg)
os.remove(bk)
check(not stepmod.diff_state(steps)["ok"] and stepmod.diff_state(steps)["missing_backups"][0]["n"] == 1, "a missing backup must show in diff")
open(bk, "wb").close()
check(not stepmod.diff_state(steps)["ok"], "an empty backup counts as missing")
open(steps, "w").write("not json")
expect_raises(stepmod.StepLogError, lambda: stepmod.diff_state(steps), "unreadable ledger")
os.remove(steps)
check(capmod._scene_state(sc)["name_hash"] == stepmod.scene_state()["name_hash"] and capmod._scene_state(sc)["cam_light_hash"] == stepmod.scene_state()["cam_light_hash"],
      "capture.py and step_log.py must hash the scene alike")
# the same through the command line
bpy.ops.wm.save_as_mainfile(filepath=work)
cli_steps = os.path.join(out, "cli_steps.json")
code, o = run_blender(work, os.path.join(HERE, "step_log.py"), "--", "log", "--steps", cli_steps, "--who", "cli", "--what", "x", "--backup", os.path.join(out, "cli_b.blend"))
check(code == 0 and os.path.exists(os.path.join(out, "cli_b.blend")), f"step_log log CLI exit {code}: {o}")
code, o = run_blender(work, os.path.join(HERE, "step_log.py"), "--", "diff", "--steps", cli_steps)
check(code == 0, f"step_log diff CLI exit {code}: {o}")
os.remove(os.path.join(out, "cli_b.blend"))
code, o = run_blender(work, os.path.join(HERE, "step_log.py"), "--", "diff", "--steps", cli_steps)
check(code == 1, f"step_log diff CLI must exit 1 with a missing backup, got {code}: {o}")
code, o = run_blender(work, os.path.join(HERE, "step_log.py"), "--", "log", "--steps", cli_steps)
check(code == 1, f"step_log log CLI must exit 1 on missing arguments, got {code}")

# ---- stats: faces without material, file path ------------------------------------
sp = os.path.join(out, "stats.json")
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
M = bpy.data.materials.new("M")
box("Crate", (0, 0, 0), (1, 1, 1))
box("Bare", (2, 0, 0), (3, 1, 1), mat=False)
bpy.ops.wm.save_as_mainfile(filepath=work)
expect_raises(statsmod.StatsError, lambda: statsmod.write_stats(sp), "stats with faces on an empty slot")
st = json.load(open(sp))
check(st["faces_without_material"] == 6 and st["faces_without_material_by_object"] == {"Bare": 6} and st["errors"], f"stats content {st['faces_without_material_by_object']}")
bpy.data.objects["Bare"].data.materials.append(M)
st = statsmod.write_stats(sp, expect_file=work)
check(not st["errors"] and os.path.normcase(os.path.realpath(st["file"])) == os.path.normcase(os.path.realpath(work)), "clean stats")
expect_raises(statsmod.StatsError, lambda: statsmod.write_stats(sp, expect_file=os.path.join(out, "gate.blend")), "stats on the wrong file")
st = statsmod.write_stats(sp, expect_file=os.path.join(out, "gate.blend"), strict=False)
check(len(st["errors"]) == 1 and "gate.blend" in st["errors"][0], "non-strict stats lists the file error")
bpy.ops.wm.save_as_mainfile(filepath=work)
code, o = run_blender(work, os.path.join(HERE, "stats.py"), "--", "--out", sp, "--expect-file", os.path.join(out, "gate.blend"))
check(code == 1, f"stats CLI must exit 1 on the wrong file, got {code}: {o}")
code, o = run_blender(work, os.path.join(HERE, "stats.py"), "--", "--out", sp, "--expect-file", work)
check(code == 0, f"stats CLI exit {code}: {o}")

# ---- measure: one metric, grid_stats ---------------------------------------------
px = np.zeros((90, 90, 4))
px[..., 3] = 1
px[:, 45:, :3] = 1.0                       # right half white
px[:30, :30, :3] = (0.0, 1.0, 0.0)         # top-left cell pure green
g = meas.grid_stats(px, 3, 3)
green = float(meas.luminance_level(np.array([[[0.0, 1.0, 0.0]]]))[0, 0])
check(abs(green - float(meas.encode(0.7152)) * 255) < 0.01, f"green is Rec.709 on linear values, got {green}")
check(abs(green - 0.587 * 255) > 20, "not Rec.601 luma on encoded values")
check(g["grid_mean"][0][0] == round(green, 2) and g["grid_mean"][2][0] == 0.0 and g["grid_mean"][1][2] == 255.0, f"grid cells {g['grid_mean']}")
check(g["clip_pct"] > 49 and g["black_pct"] > 38 and g["grid_clip_pct"][1][2] == 100.0 and g["grid_black_pct"][2][0] == 100.0, f"clip and black {g['clip_pct']} {g['black_pct']}")
png = os.path.join(out, "grid.png")
img = bpy.data.images.new("grid", 90, 90)
img.colorspace_settings.name = "Non-Color"
img.pixels = px[::-1].ravel().tolist()
img.filepath_raw, img.file_format = png, "PNG"
img.save()
code, o = run_blender(work, os.path.join(HERE, "measure.py"), "--", png, "--grid", "3x3")
check(code == 0 and "grid_mean" in o, f"measure CLI exit {code}: {o}")
code, o = run_blender(work, os.path.join(HERE, "measure.py"), "--", os.path.join(out, "nope.png"))
check(code == 1, f"measure CLI must exit 1 for a missing image, got {code}")

# ---- capture: lint gate, per-camera resolution, shift and sensor fit -------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
M = bpy.data.materials.new("M")
box("Floor", (-3, -3, -0.1), (3, 3, 0))
box("Crate", (0, 0, 0), (1, 1, 1))
cd = bpy.data.cameras.new("CAM_A")
cd.lens = 24
cam = bpy.data.objects.new("CAM_A", cd)
cam.location, cam.rotation_euler = (5, -5, 3), (1.1, 0, 0.785)
sc.collection.objects.link(cam)
sc.render.resolution_x, sc.render.resolution_y = 300, 400
rd = sc.render
size = lambda p: tuple(bpy.data.images.load(p, check_existing=False).size)
kw = dict(engine="BLENDER_WORKBENCH", project=proj, repo=REPO)
o0 = os.path.join(out, "cap0")
capmod.capture_set(o0, ["CAM_A"], engine="BLENDER_WORKBENCH", project=proj, lint=False)     # camera data differs from cameras.json: the render uses the json values
check(size(os.path.join(o0, "CAM_A.png")) == (200, 100), f"per-camera resolution from cameras.json, got {size(os.path.join(o0, 'CAM_A.png'))}")
check((rd.resolution_x, rd.resolution_y) == (300, 400) and cd.shift_x == 0 and cd.shift_y == 0 and cd.sensor_fit == "AUTO" and abs(cd.sensor_width - 36) < 1e-6,
      "scene resolution and camera data restored")
cd.shift_x, cd.shift_y, cd.sensor_width, cd.sensor_fit = 0.1, -0.05, 30, "VERTICAL"        # now the file matches the json, as lint wants
o1 = os.path.join(out, "cap1")
capmod.capture_set(o1, ["CAM_A"], **kw)                        # no lint.json: scene-lint runs here, then renders
check(os.path.exists(os.path.join(o1, "lint.json")) and json.load(open(os.path.join(o1, "lint.json")))["tool"] == "scene-lint", "lint.json written next to the images")
check(size(os.path.join(o1, "CAM_A.png")) == (200, 100) and (rd.resolution_x, rd.resolution_y) == (300, 400), "gated render at the camera's own resolution")
o2 = os.path.join(out, "cap2")
capmod.capture_set(o2, ["CAM_A"], width=64, height=48, **kw)
check(size(os.path.join(o2, "CAM_A.png")) == (64, 48), "an explicit width and height win")
# a stale lint.json (the scene changed) is not trusted: lint reruns, finds the new blocker and the capture is refused
box("Bare", (2, 0, 0), (3, 1, 1), mat=False)
o3 = os.path.join(out, "cap3")
shutil.copy(os.path.join(o1, "lint.json"), os.makedirs(o3) or os.path.join(o3, "lint.json"))
expect_raises(capmod.CaptureRefused, lambda: capmod.capture_set(o3, ["CAM_A"], **kw), "capture with a blocker")
check(not os.path.exists(os.path.join(o3, "CAM_A.png")), "nothing is rendered on a refusal")
check("faces_no_material" in json.dumps(json.load(open(os.path.join(o3, "lint.json")))["blockers"]), "the rerun lint names the blocker")
capmod.capture_set(o3, ["CAM_A"], override_lint="selftest override", **kw)
log = open(os.path.join(o3, "lint_overrides.log")).read()
check(os.path.exists(os.path.join(o3, "CAM_A.png")) and "selftest override" in log and "faces_no_material" in log, f"override renders and is logged: {log!r}")
# no repo to run lint with and no fresh lint.json: refused
expect_raises(capmod.CaptureRefused, lambda: capmod.capture_set(os.path.join(out, "cap4"), ["CAM_A"], engine="BLENDER_WORKBENCH"), "capture with no lint at all")
capmod.capture_set(os.path.join(out, "cap5"), ["CAM_A"], engine="BLENDER_WORKBENCH", lint=False)
check(os.path.exists(os.path.join(out, "cap5", "CAM_A.png")), "lint=False skips the gate")
expect_raises(RuntimeError, lambda: capmod.capture_set(os.path.join(out, "cap6"), ["CAM_A", "CAM_Nope"], lint=False), "a missing camera")
check(not os.path.exists(os.path.join(out, "cap6", "CAM_A.png")), "a missing camera stops before any render")

print("ADAPTER SELFTEST", "FAILED" if fails else "OK")
sys.exit(1 if fails else 0)
