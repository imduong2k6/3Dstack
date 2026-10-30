"""Headless self-test for integrate_parts.py on a synthetic gate file and lane (never touches a project):

    bash bin/blender-bg --python .claude/skills/lane-integration/scripts/selftest_integrate.py -- <repo> <out_dir>

Builds a gate file (a master, a lane to rebuild, a lane that must stay untouched), a frozen part file with a stale red
material, and a manifest. Then it checks the happy path (rebuild by name, slots remapped by name, instances placed,
live patch replayed, a second join gives the same scene, link mode), each defect the script exists to stop (instance at
the origin, empty slot, part changed after the freeze, a foreign ID, a patch that is not repeatable), and the exit codes.
"""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace

import bpy

repo, out = sys.argv[sys.argv.index("--") + 1:][:2]
spec = importlib.util.spec_from_file_location("ip", os.path.join(repo, ".claude/skills/lane-integration/scripts/integrate_parts.py"))
ip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ip)
shutil.rmtree(out, ignore_errors=True)
os.makedirs(os.path.join(out, "parts", "a"))
GATE, PARTS = os.path.join(out, "gate.blend"), os.path.join(out, "parts")
FACES = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
VERTS = [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5), (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)]


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Base Color"].default_value = (*rgb, 1)
    return m


def col(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def box(name, c, mats, loc=(0, 0, 0), lane=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(VERTS, [], FACES)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", [i % len(mats) for i in range(6)])
    o = bpy.data.objects.new(name, me)
    o.location = loc
    c.objects.link(o)
    if lane:
        o["lane"] = lane
    return o


def build_part(path, slot_hole=False):
    reset()
    c = col("LANE_a")
    red, steel, new = mat("M_Paint", (.9, .1, .1)), mat("M_Steel", (.4, .4, .5)), mat("M_New", (0, 1, 0))
    box("A_Wall_01", c, [red, steel], (2, 0, 0))
    w2 = box("A_Wall_02", c, [red], (3, 0, 0))
    box("A_Post_01", c, [new], (4, 0, 0))
    if slot_hole:
        w2.data.materials[0] = None
    bpy.ops.wm.save_as_mainfile(filepath=path)


def build_gate(path, intruder=False):
    reset()
    kit = col("KIT")
    kit.hide_render = True
    parts = col("PARTS")
    gray, steel = mat("M_Paint", (.5, .5, .5)), mat("M_Steel", (.4, .4, .5))
    box("SM_Box", kit, [gray])
    a, b = col("LANE_a", parts), col("LANE_b", parts)
    box("A_Old_01", a, [gray], (7, 7, 7))
    stale = box("A_Box_99", b, [gray], (8, 8, 8), lane="a")  # a lane object that lives in another collection
    stale.data = bpy.data.objects["SM_Box"].data
    box("B_Wall_01", b, [gray, steel], (5, 5, 5))
    if intruder:
        box("A_Intruder", b, [gray], (6, 6, 6))
    bpy.ops.wm.save_as_mainfile(filepath=path)


def write_manifest(rows=None, **kw):
    m = {"lane": "a", "collection": "LANE_a", "id_prefix": "A_", "materials": ["M_Paint", "M_Steel", "M_New"],
         "instances": rows or [{"name": "A_Box_01", "master": "SM_Box", "loc": [1, 2, 3]},
                               {"name": "A_Box_02", "master": "SM_Box", "loc": [4, 5, 6], "rot_deg": [0, 0, 90]},
                               {"name": "A_Box_03", "master": "SM_Box", "loc": [0, 0, 0], "at_origin": True}]}
    m.update(kw)
    json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"), indent=1)


PATCH_OK = '@patch("p001", lane="a", note="wall 2 sits 9 m along")\ndef _(bpy):\n    ob = bpy.data.objects.get("A_Wall_02")\n    if ob:\n        ob.location.x = 9.0\n'
PATCH_BAD = '@patch("p002", lane="a")\ndef _(bpy):\n    bpy.data.objects["A_Wall_02"].location.x += 1.0\n'


def run(name, patches=PATCH_OK, mode="append", expect_ok=True, setup=None):
    """One scenario: fresh gate copy, join in-process, compare with the expectation."""
    gate = GATE if setup is None else setup()
    shutil.copy(gate, os.path.join(out, name + "_in.blend"))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out, name + "_in.blend"))
    pf = os.path.join(out, "live_patches.py")
    open(pf, "w").write(patches)
    o = os.path.join(out, name + ".blend")
    if os.path.exists(o):
        os.remove(o)
    rep = ip.join(Namespace(parts=PARTS, lanes="a", out=o, patches=pf, backup_dir=os.path.join(out, "bk"), step=name, mode=mode))
    assert rep["ok"] == expect_ok, (name, rep["failures"])
    assert os.path.exists(o) == expect_ok, (name, "saved only when the join passed")
    return rep


def failed(rep, check):
    return any(check in f for f in rep["failures"])


# ---------- scenarios ----------
build_gate(GATE)
build_part(os.path.join(PARTS, "a", "a.blend"))
write_manifest()
ip.freeze(PARTS, ["a"])

rep = run("happy")
O, M = bpy.data.objects, bpy.data.materials
assert "A_Old_01" not in O and "A_Box_99" not in O, "old lane objects, including one tagged in another collection, are gone"
assert not [m.name for m in M if ip.DUP.search(m.name)], "no .001 materials"
assert [s.material.name for s in O["A_Wall_01"].material_slots] == ["M_Paint", "M_Steel"], "slots follow the part's names"
assert ip.base_color(M["M_Paint"]) == (.5, .5, .5), "the gate's M_Paint wins over the part's stale red"
assert rep["lanes"][0]["materials"]["drift"][0]["material"] == "M_Paint" and rep["lanes"][0]["materials"]["new"] == ["M_New"]
assert tuple(O["A_Box_01"].location) == (1, 2, 3) and O["A_Box_01"].data is O["SM_Box"].data
assert O["A_Box_03"].matrix_world.translation.length < 1e-6, "manifest allows this one at the origin"
assert O["A_Wall_02"].location.x == 9.0, "live patch replayed"
assert tuple(O["B_Wall_01"].location) == (5, 5, 5), "other lane untouched"
assert "A_Wall_01" in bpy.data.collections["LANE_a"].objects and bpy.data.collections["LANE_a"].users == 1
assert os.path.exists(os.path.join(out, "bk", "happy_blockout_01_happy.blend")), "backup written with the house-rule name"
assert rep["warnings"] == {"materials_orphaned": []}, rep["warnings"]
names1 = sorted(o.name for o in O)

# a second join of the same part on the result gives the same scene
shutil.copy(os.path.join(out, "happy.blend"), os.path.join(out, "second_gate.blend"))
run("second", setup=lambda: os.path.join(out, "second_gate.blend"))
assert sorted(o.name for o in bpy.data.objects) == names1, "rebuild is repeatable"
print("ok  rebuild by name, slots by name, instances, patch, repeat join")

# defects
write_manifest(rows=[{"name": "A_Box_01", "master": "SM_Box", "loc": [0, 0, 0]}])
ip.freeze(PARTS, ["a"])
assert failed(run("origin", expect_ok=False), "none_at_origin")
write_manifest()
ip.freeze(PARTS, ["a"])
print("ok  instance at the origin is refused")

m = json.load(open(os.path.join(PARTS, "a", "manifest.json")))
del m["materials"]  # no explicit list: the gate's own materials plus what the manifest declares as new
json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
ip.freeze(PARTS, ["a"])
assert failed(run("newmat", expect_ok=False), "materials_allowed"), "an undeclared new material is refused"
m["new_materials"] = ["M_New"]
json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
ip.freeze(PARTS, ["a"])
run("newmat_ok")
m["materials"] = ["M_Paint", "M_Steel", "M_New"]
json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
ip.freeze(PARTS, ["a"])
print("ok  a material the gate does not have is refused unless the manifest declares it")

build_part(os.path.join(PARTS, "a", "a_hole.blend"), slot_hole=True)
m = json.load(open(os.path.join(PARTS, "a", "manifest.json")))
m["part"] = "a_hole.blend"
json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
ip.freeze(PARTS, ["a"])
assert failed(run("hole", expect_ok=False), "material_slots_filled")
m["part"] = "a.blend"
json.dump(m, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
ip.freeze(PARTS, ["a"])
print("ok  empty slot is refused")

h = json.load(open(os.path.join(PARTS, "a", "manifest.json")))
h["frozen"]["sha256"] = "0" * 64
json.dump(h, open(os.path.join(PARTS, "a", "manifest.json"), "w"))
assert failed(run("stale", expect_ok=False), "frozen_hash_matches")
ip.freeze(PARTS, ["a"])
print("ok  part changed after the freeze is refused")

intr = os.path.join(out, "gate_intruder.blend")
build_gate(intr, intruder=True)
assert failed(run("foreign", expect_ok=False, setup=lambda: intr), "no_foreign_ids")
print("ok  an object using the lane's ID prefix outside the lane is refused")

bad = run("badpatch", patches=PATCH_OK + PATCH_BAD, expect_ok=False)
assert any(p["id"] == "p002" and not p["ok"] for p in bad["patches"])
print("ok  a patch that adds instead of sets is refused")

assert any(p["id"] == "p001" and not p["ok"] for p in run("link_patched", mode="link", expect_ok=False)["patches"]), "patches on a linked lane are refused"
run("link", patches="", mode="link")
holder = bpy.data.objects["LINK_LANE_a"]
assert holder.instance_collection.library is not None and "A_Wall_01" in holder.instance_collection.objects
assert tuple(bpy.data.objects["A_Box_01"].location) == (1, 2, 3)
print("ok  link mode")

# exit codes through the command line, as the manager runs it
binary = bpy.app.binary_path
script = os.path.join(repo, ".claude/skills/lane-integration/scripts/integrate_parts.py")
cmd = [binary, "--background", "--factory-startup", os.path.join(out, "cli_in.blend"), "--python", script, "--", "--parts", PARTS, "--lanes", "a",
       "--out", os.path.join(out, "cli_out.blend")]
shutil.copy(GATE, os.path.join(out, "cli_in.blend"))
r = subprocess.run(cmd, capture_output=True, text=True)
assert r.returncode == 0 and os.path.exists(os.path.join(out, "cli_out.blend")), r.stdout[-800:]
write_manifest(rows=[{"name": "A_Box_01", "master": "SM_Box", "loc": [0, 0, 0]}])
ip.freeze(PARTS, ["a"])
cmd[-1] = os.path.join(out, "cli_bad.blend")
r = subprocess.run(cmd, capture_output=True, text=True)
assert r.returncode == 1 and not os.path.exists(cmd[-1]) and "none_at_origin" in r.stdout, (r.returncode, r.stdout[-800:])
print("ok  exit 0 on a clean join, exit 1 and no file on a failed assert")
print("integrate_parts self-test passed")
