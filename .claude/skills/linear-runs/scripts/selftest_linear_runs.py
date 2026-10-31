"""Self-test for linear_runs.py: builds a wall corner with a window in the way, two boxes, two brackets and a valve pair, then builds
four rows and asserts the geometry, the report, the repeat run and what scene-lint says about the result. Headless, writes only
<out_dir>:

    bash bin/blender-bg --python-exit-code 1 --python .claude/skills/linear-runs/scripts/selftest_linear_runs.py -- <out_dir>
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(os.getcwd(), "selftest_lr_out")
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out, exist_ok=True)
sys.path.insert(0, HERE)
import linear_runs as LR  # noqa: E402

spec = importlib.util.spec_from_file_location("lint_blender", os.path.join(LR.SKILLS, "scene-lint", "scripts", "lint_blender.py"))
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)
L = LR.L

fails = []


def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        fails.append(what)


# ---- scene ---------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
for m in ("M_Test_Run", "M_Test_Steel", "M_Test_Wall"):
    bpy.data.materials.new(m)


def box(name, lo, hi):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials["M_Test_Wall"])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    lo, hi = Vector(lo), Vector(hi)
    ob.location, ob.scale = (lo + hi) / 2, hi - lo
    ob["phase"] = "P0"
    return ob


box("Floor", (-1, -1, -0.1), (6, 6, 0))
box("Wall_N", (0, 5.0, 0), (5.0, 5.2, 3))
box("Wall_E", (5.0, 0, 0), (5.2, 5.2, 3))
box("MeterBox_A", (1.0, 4.85, 1.3), (1.3, 5.0, 1.7))
box("JunctionBox_B", (4.9, 2.0, 1.4), (5.0, 2.15, 1.55))
box("Window_N", (2.5, 4.95, 1.0), (3.5, 5.0, 2.2))
box("Bracket_P1", (0.95, 0.95, 2.95), (1.05, 1.05, 3.05))
box("Bracket_P2", (3.95, 0.95, 2.95), (4.05, 1.05, 3.05))
box("Valve_Box_C", (1.7, 4.9, 1.55), (1.8, 5.0, 1.65))
box("Valve_Box_D", (4.0, 4.9, 1.55), (4.1, 5.0, 1.65))
bpy.context.view_layer.update()

SVC = {"networks": [{"id": "net_test", "nodes": [
    {"id": "A", "type": "meter", "at_m": [1.15, 4.92, 1.5], "mount": "wall", "asset": "MeterBox_A"},
    {"id": "B", "type": "junction", "at_m": [4.95, 2.075, 1.475], "mount": "wall", "asset": "JunctionBox_B"},
    {"id": "P1", "type": "bracket", "at_m": [1.0, 1.0, 3.0], "asset": "Bracket_P1"},
    {"id": "P2", "type": "bracket", "at_m": [4.0, 1.0, 3.0], "asset": "Bracket_P2"},
    {"id": "C", "type": "valve", "at_m": [1.75, 4.95, 1.6], "mount": "wall", "asset": "Valve_Box_C", "dir": "+x"},
    {"id": "D", "type": "valve", "at_m": [4.05, 4.95, 1.6], "mount": "wall", "asset": "Valve_Box_D", "dir": "-x"},
], "runs": [
    {"id": "R1", "from": "A", "to": "B", "by": "conduit", "dia_mm": 20, "source": "selftest"},
    {"id": "R2", "from": "A", "to": "B", "by": "cable", "dia_mm": 10, "source": "selftest", "count": 4, "strands_mm": [5, 6, 8, 10]},
    {"id": "R3", "from": "P1", "to": "P2", "by": "cable", "dia_mm": 8, "source": "selftest", "sag_m": 0.1},
    {"id": "R4", "from": "C", "to": "D", "by": "pipe", "dia_mm": 15, "source": "selftest", "path_m": [[2.0, 4.9905, 1.6], [3.8, 4.9905, 1.6]]},
]}]}
MATS = {"conduit": "M_Test_Run", "cable": "M_Test_Run", "pipe": "M_Test_Run", "support": "M_Test_Steel"}


def state():
    """{object name: hash of its matrix and vertices} for the services collection."""
    col = bpy.data.collections.get("COL_P3_Services")
    res = {}
    for ob in col.objects if col else []:
        h = hashlib.sha1((np.array(ob.matrix_world).round(6) + 0.0).tobytes())   # + 0.0: -0.0 and 0.0 are the same place
        if ob.type == "MESH":
            co = np.empty(len(ob.data.vertices) * 3)
            ob.data.vertices.foreach_get("co", co)
            h.update((co.round(6) + 0.0).tobytes())
        res[ob.name] = h.hexdigest()
    return res


def same(a, b):
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return not diff, diff[:6]


# ---- build ---------------------------------------------------------------------
print("linear_runs selftest")
rep = LR.build(SVC, materials=MATS)
json.dump(rep, open(os.path.join(out, "report_1.json"), "w"), indent=1)
built = {b["run"]: b for b in rep["built"]}
check(set(built) == {"R1", "R2", "R3"}, f"R1, R2, R3 built (got {sorted(built)}; errors {rep['errors']})")
check(len(rep["blocked"]) == 1 and rep["blocked"][0]["run"] == "R4" and rep["blocked"][0]["hit"] == "Window_N",
      f"R4 blocked by Window_N (got {rep['blocked']})")
check(not rep["ok"], "report not ok while a run is blocked")
check(bpy.data.objects.get("Pipe_R4") is None, "nothing built for the blocked run")
for rid, kind, sup in (("R1", "Conduit", "Saddle"), ("R2", "Cable", "Clip")):
    b = built.get(rid, {})
    check(b.get("route") == "auto" and b.get("supports", 0) >= 3, f"{rid} routed automatically with supports ({b.get('supports')} {sup}s, {b.get('length_m')} m, {b.get('bends')} bends)")
check(built.get("R2", {}).get("strands") == 4, "R2 has 4 strands")
check(built.get("R3", {}).get("route") == "hang" and built.get("R3", {}).get("supports") == 0, "R3 hangs with no supports")
print("  warnings:", json.dumps(rep["warnings"]))

h1 = state()
rep2 = LR.build(SVC, materials=MATS)
ok, diff = same(state(), h1)
check(ok, f"second build gives identical objects and vertices {diff}")
check(not [o.name for o in bpy.data.objects if ".00" in o.name] and not [m.name for m in bpy.data.meshes if ".00" in m.name],
      "no .001 objects or meshes after the second build")

geo = L.Geo(bpy.context.scene, L.load_rules(None))
S = geo.solids


def verts(name):
    ob = bpy.data.objects[name]
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def in_box(p, s, pad=0.0):
    return bool(np.all(p >= s.lo - pad) and np.all(p <= s.hi + pad))


for name in ("Conduit_R1", "Cable_R2"):
    if name not in S:
        check(False, f"{name} exists")
        continue
    vs = verts(name)
    bad = [(o, v) for v in vs for o in ("Wall_N", "Wall_E", "Floor", "Window_N") if in_box(v, S[o]) and S[o].inside(Vector(v))]
    check(not bad, f"{name}: no vertex inside a wall, the floor or the window ({len(bad)} found{', first ' + str(bad[0]) if bad else ''})")
    for anchor in ("MeterBox_A", "JunctionBox_B"):
        check(any(in_box(v, S[anchor]) for v in vs), f"{name} ends inside {anchor}")
walls = [S[n] for n in ("Wall_N", "Wall_E")]
for sup in ("Saddle_R1", "Clip_R2"):
    obs = [o for o in bpy.data.objects if o.name.startswith(sup + "_")]
    far = []
    for ob in obs:
        d = min(min((w.bvh.find_nearest(Vector(v))[3] for v in verts(ob.name)), default=9) for w in walls)
        if d > 1e-3:
            far.append((ob.name, round(d, 4)))
    check(obs and not far, f"{len(obs)} {sup} supports, every one with a foot on a wall ({far[:3]})")
    check(len({o.data.name for o in obs}) == 1, f"{sup} supports share one mesh")

if "Cable_R3" in S:
    vs = verts("Cable_R3")
    low = float(vs[:, 2].min())
    check(abs(low - (3.0 - 0.1 - 0.004)) < 0.01, f"R3 sags 0.1 m mid-span (lowest point {low:.3f}, expected about 2.896)")
    check(abs(float(vs[np.argmin(vs[:, 2]), 0]) - 2.5) < 0.1, "R3's lowest point is mid-span")

# ---- lint on the result ----------------------------------------------------------
lr = lint.run_lint(out_dir=out, only=["cable_ends", "cable_in_rigid", "cable_bend", "conduit_open_ends", "floating"])
mine = ("Cable_", "Conduit_", "Saddle_", "Clip_")
for name in ("cable_ends", "cable_in_rigid", "cable_bend", "conduit_open_ends", "floating"):   # cable_bend: the builder bends a cable at 4 diameters, the lint limit is 3.8
    ch = lr["checks"].get(name, {})
    items = [it for it in ch.get("items", []) if any(m in it["object"] for m in mine)]
    check(ch.get("status") != "error" and not items, f"lint {name}: {ch.get('status')}, {len(items)} item(s) on built runs"
          + (f": {json.dumps(items[:2])[:400]}" if items else ""))

# ---- guide mode, errors and surplus removal ---------------------------------------
rep3 = LR.build(SVC, runs=["R3"], materials=MATS, emit="guide")
check(bpy.data.objects.get("CBL_R3") is not None and bpy.data.objects.get("CBL_R3_Start") is not None
      and bpy.data.objects.get("Cable_R3") is None, "emit=guide makes CBL_R3 with end empties and removes the R3 mesh")
LR.build(SVC, runs=["R3"], materials=MATS)
check(bpy.data.objects.get("CBL_R3") is None and bpy.data.objects.get("Cable_R3") is not None, "a mesh rebuild removes the guide")
rep4 = LR.build(SVC, runs=["R1"], materials={"conduit": "M_Missing"})
check(rep4["errors"] and "M_Missing" in rep4["errors"][0]["what"] and bpy.data.objects.get("Conduit_R1") is not None,
      "a missing material is an error and keeps the last good run")
try:
    LR.build(SVC, runs=["R9"])
    check(False, "an unknown run id raises")
except LR.RunError:
    check(True, "an unknown run id raises")

yml = os.path.join(out, "services.yaml")   # the command line reads the file with the pipeline's own YAML reader
with open(yml, "w") as f:
    f.write("version: 1\nnetworks:\n  - id: net_test\n    nodes:\n")
    for n in SVC["networks"][0]["nodes"]:
        f.write("      - {" + ", ".join(f"{k}: {json.dumps(v)}" for k, v in n.items()) + "}\n")
    f.write("    runs:\n")
    for r in SVC["networks"][0]["runs"]:
        f.write("      - {" + ", ".join(f"{k}: {json.dumps(v)}" for k, v in r.items()) + "}\n")
h2 = state()
rc = LR.main(["--services", yml, "--runs", "R1,R2", "--material", "conduit=M_Test_Run", "--material", "cable=M_Test_Run",
              "--material", "support=M_Test_Steel", "--out", os.path.join(out, "report_cli.json")])
ok, diff = same(state(), h2)
check(rc == 0 and ok, f"command line on services.yaml rebuilds R1 and R2 to the same geometry (exit {rc}) {diff}")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "selftest_linear_runs.blend"))
print(f"SELFTEST {'FAIL' if fails else 'OK'} ({len(fails)} failed) out={out}")
if fails:
    raise SystemExit(1)
