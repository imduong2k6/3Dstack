"""Self-test for scene-lint: builds a small synthetic scene with one planted defect per check and a clean control next to each, runs
lint_blender.py and visible_set.py on it, and asserts what is (and is not) found. Headless, nothing outside <out_dir> is written:

    bash bin/blender-bg --python-exit-code 1 --python .claude/skills/scene-lint/scripts/selftest_lint.py -- <out_dir>

The cable cases include the one that once passed as "0 floating": a hooked run whose farthest vertices sit on anchors while its
real end hangs in mid-air, and two floating cables that touch each other.
"""
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from types import SimpleNamespace
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(os.getcwd(), "selftest_out")
shutil.rmtree(out, ignore_errors=True)   # a visible_set.json from an earlier run would scope this one
os.makedirs(out, exist_ok=True)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, HERE)
lint, vset, lib = load("lint_blender"), load("visible_set"), load("lintlib")

# ---- scene builders ------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
MAT = bpy.data.materials.new("M_Test")
MAT["material_group"] = "plaster"
cols = {}


def col(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or sc.collection).children.link(c)
    cols[name] = c
    return c


for n in ("COL_Blockout", "COL_P1_Structure", "COL_P3_Services", "COL_P5_Props", "COL_Review", "COL_Parked", "COL_Kit", "COL_Ref", "COL_Cameras", "COL_Lights"):
    col(n)


def link(ob, cname):
    cols[cname].objects.link(ob)
    return ob


def finish(name, bm, cname, loc=(0, 0, 0), mat=True, props=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    if mat:
        me.materials.append(MAT)
    for k, v in (props or {}).items():
        ob[k] = v
    return link(ob, cname)


def box(name, lo, hi, cname="COL_P5_Props", **kw):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector([(a + b) / 2 for a, b in zip(lo, hi)]), verts=bm.verts)
    return finish(name, bm, cname, **kw)


def multibox(name, boxes, cname, **kw):
    bm = bmesh.new()
    for lo, hi in boxes:
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])), verts=r["verts"])
        bmesh.ops.translate(bm, vec=Vector([(a + b) / 2 for a, b in zip(lo, hi)]), verts=r["verts"])
    return finish(name, bm, cname, **kw)


def tube(name, pts, radius=0.01, k=8, cname="COL_P3_Services", **kw):
    """A capped k-sided tube along world points (fan caps), like the pipeline's swept cables."""
    bm = bmesh.new()
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        tg = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(tg.z) < 0.9 else Vector((1, 0, 0))
        u = tg.cross(ref).normalized()
        w = tg.cross(u)
        rings.append([bm.verts.new(p + (u * math.cos(a) + w * math.sin(a)) * radius) for a in (2 * math.pi * j / k for j in range(k))])
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(k):
            bm.faces.new((r0[j], r0[(j + 1) % k], r1[(j + 1) % k], r1[j]))
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / k)
        for j in range(k):
            bm.faces.new((c, ring[j], ring[(j + 1) % k]) if not flip else (c, ring[(j + 1) % k], ring[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, cname, **kw)


def subdivide(a, b, n=6):
    return [tuple(x + (y - x) * t / n for x, y in zip(a, b)) for t in range(n + 1)]


def path(*pts, n=6):
    out_ = []
    for a, b in zip(pts, pts[1:]):
        out_ += subdivide(a, b, n)[:-1]
    return out_ + [pts[-1]]


# structure
box("SM_Floor", (-6, -6, -0.1), (6, 6, 0), "COL_P1_Structure")
multibox("SM_Wall_A", [((-4, 3, 0), (0.1, 3.2, 3)), ((0.5, 3, 0), (4, 3.2, 3)), ((0.1, 3, 0), (0.5, 3.2, 1.4)), ((0.1, 3, 2.0), (0.5, 3.2, 3))], "COL_P1_Structure")
box("SM_Wall_B", (-4, -3.2, 0), (4, -3, 3), "COL_P1_Structure")
box("SM_Vent_Good", (0.11, 2.9, 1.51), (0.49, 3.3, 1.89), "COL_P3_Services")            # inside the cut opening
box("SM_Vent_Bad", (0.1, -3.3, 1.5), (0.5, -2.9, 1.9), "COL_P3_Services")              # through a solid wall
multibox("SM_Wall_P", [((4.2, -3.2, 0), (5.2, -3.12, 3)), ((4.2, -3.12, 0), (4.5, -3.0, 3)), ((4.9, -3.12, 0), (5.2, -3.0, 3)),
                       ((4.5, -3.12, 0), (4.9, -3.0, 1.5)), ((4.5, -3.12, 1.9), (4.9, -3.0, 3))], "COL_P1_Structure")
box("SM_Vent_Pocket", (4.52, -3.12, 1.52), (4.88, -2.95, 1.88), "COL_P3_Services")      # in a 0.12 m blind pocket: a minor note
box("SM_Door_Ok", (2.0, -1.05, 0), (2.92, -1.0, 2.1))
box("SM_Door_Narrow", (3.2, -1.05, 0), (3.9, -1.0, 2.1))
for i, top in enumerate((0.17, 0.34, 0.51, 0.73)):                                       # the last riser is 0.22 m
    box(f"SM_Stair_Step_{i + 1:02d}", (-3 + 0.3 * i, -2, 0), (-2.7 + 0.3 * i, -1, top), "COL_P1_Structure")
# props: floating, overlap, origin, materials, names
box("Prop_Crate", (1.5, -2.5, 0), (2.0, -2.0, 0.5))
box("Prop_Untagged", (-1.0, -2.5, 0), (-0.5, -2.0, 0.5), "COL_Blockout")      # no phase, no map_id
box("Prop_Float", (4.0, -2.0, 1.5), (4.5, -1.5, 2.0))
box("Prop_Float_Pair_A", (4.0, -5.0, 1.5), (4.5, -4.5, 2.0))
box("Prop_Float_Pair_B", (4.5, -5.0, 1.5), (5.0, -4.5, 2.0))
box("Prop_Overlap_A", (-5.5, -5.5, 0), (-5.0, -5.0, 0.5))
box("Prop_Overlap_B", (-5.05, -5.4, 0.1), (-4.55, -4.9, 0.6))                              # 5 cm into A
box("Prop_Touch_A", (-3.5, -5.5, 0), (-3.0, -5.0, 0.5))
box("Prop_Touch_B", (-3.005, -5.4, 0.1), (-2.5, -4.9, 0.6))                                # 5 mm into A: inside the tolerance
box("Prop_At_Origin", (-0.4, -0.2, 0), (-0.1, 0.2, 0.3))                                 # object origin at (0, 0, 0)
box("Prop_Origin_OK", (0.1, -0.2, 0), (0.4, 0.2, 0.3), props={"origin_ok": 1})
kit = box("SM_Kit_Piece", (-0.1, -0.5, 0), (0.1, -0.3, 0.2), "COL_Kit")
inst = bpy.data.objects.new("Inst_Prop", None)
inst.instance_type, inst.instance_collection = "COLLECTION", cols["COL_Kit"]
link(inst, "COL_P5_Props")                                                               # an instance left at the origin
box("Prop_NoMat", (1.0, -5.0, 0), (1.3, -4.7, 0.3), mat=False)
b = box("Prop_BadIndex", (1.5, -5.0, 0), (1.8, -4.7, 0.3))
b.data.polygons[0].material_index = 3
box("Cube.001", (2.2, -5.0, 0), (2.5, -4.7, 0.3))
box("Bad Name", (2.7, -5.0, 0), (3.0, -4.7, 0.3))
# wear
box("Grime_Band_01", (-3.5, 2.97, 0.5), (-3.0, 3.0, 0.7), "COL_P3_Services")
box("Stain_Overlay", (-2.5, 2.97, 0.5), (-2.0, 3.0, 0.7), "COL_P3_Services")
box("SM_Stainless_Tray", (2.0, 2.9, 1.0), (2.6, 3.0, 1.1), "COL_P3_Services")           # "stainless" is not "stain"
box("Prop_Dent_Repair", (3.0, 2.9, 1.0), (3.4, 3.0, 1.1), "COL_P3_Services", props={"wear_ok": 1})
# visibility
box("Stub_Review_Bad", (5.0, -5.8, 0), (5.2, -5.6, 0.2), "COL_Review")                  # review-only but visible
ok = box("Stub_Review_Ok", (5.4, -5.8, 0), (5.6, -5.6, 0.2), "COL_Review")
ok.hide_render = ok.hide_viewport = True
box("Parked_Box", (0, 0, 0), (0.2, 0.2, 0.2), "COL_Parked")
box("Ref_Box", (-5.9, -5.9, 0), (-5.7, -5.7, 0.2), "COL_Ref")                           # a parked-by-name collection left in the view layer
box("Prop_EyeHidden", (5.0, 4.0, 0), (5.3, 4.3, 0.3))
# anchors, cables, conduit (on the front of wall A, y = 3.0)
for n, x0, x1, z0, z1 in (("Box_A", -3.6, -3.2, 1.8, 2.1), ("Box_B", -1.6, -1.2, 1.8, 2.1), ("Box_E", 1.2, 1.6, 1.8, 2.1),
                          ("Box_Top", -3.6, -3.2, 2.5, 2.7), ("Junction_Box_D", -2.6, -2.2, 1.0, 1.2)):
    box(n, (x0, 2.9, z0), (x1, 3.0, z1), "COL_P3_Services")
box("Box_Post_H1", (3.0, -0.1, 0), (3.2, 0.1, 2.0), "COL_P3_Services")
box("Box_Post_H2", (5.4, 2.4, 0), (5.6, 2.6, 2.0), "COL_P3_Services")
box("Box_Post_S1", (1.0, -4.1, 0), (1.2, -3.9, 2.0), "COL_P3_Services")
box("Box_Post_S2", (3.0, -4.1, 0), (3.2, -3.9, 2.0), "COL_P3_Services")
tube("Cable_Ok", path((-3.2, 2.95, 1.95), (-2.4, 2.95, 1.8), (-1.6, 2.95, 1.95)))
tube("Cable_Chain", path((-2.4, 2.95, 1.8), (-2.4, 2.95, 1.2)))                         # joins Cable_Ok, ends on Junction_Box_D
tube("Cable_Hook", path((3.2, 0, 1.5), (5.5, 0, 1.5), (5.5, 2.5, 1.5), (3.8, 2.5, 1.5), (3.8, 1.0, 1.5)))
tube("Cable_Tail", path((-1.2, 2.97, 1.95), (-0.2, 2.97, 1.95)))                        # ends along the wall
box("Box_E_stub", (1.2, 2.9, 1.0), (1.6, 3.0, 1.1), "COL_P3_Services")
tube("Cable_Entry", path((1.6, 2.95, 1.95), (2.0, 2.95, 1.95), (2.0, 3.0, 1.95)))       # ends head-on in the wall
tube("Cable_FloatA", path((-4, -4.5, 1.0), (-3, -4.5, 1.0)))
tube("Cable_FloatB", path((-3, -4.5, 1.0), (-2, -4.5, 1.0)))
tube("Cable_Droop", path((1.2, -4.0, 1.9), (2.1, -4.0, 0.9), (3.0, -4.0, 1.9), n=8))
tube("Conduit_Ok", path((-3.4, 2.95, 2.1), (-3.4, 2.95, 2.5)), radius=0.016)
tube("Conduit_Open", path((-1.4, 2.95, 2.1), (-1.4, 2.95, 2.4)), radius=0.016)
# narrow gap on the walk path, an enclosed room with something floating in it
box("Pillar_N_A", (-4.7, 0.9, 0), (-4.3, 1.4, 2.5))
box("Pillar_N_B", (-4.7, 0.0, 0), (-4.3, 0.5, 2.5))
bm = bmesh.new()                                                                           # hollow closed room: outer shell and inverted cavity
for lo, hi, flip in (((-2.0, 0.8, 0), (-0.8, 2.0, 2.2), False), ((-1.9, 0.9, 0.1), (-0.9, 1.9, 2.1), True)):
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])), verts=r["verts"])
    bmesh.ops.translate(bm, vec=Vector([(a + b) / 2 for a, b in zip(lo, hi)]), verts=r["verts"])
    if flip:
        bmesh.ops.reverse_faces(bm, faces=list({f for v in r["verts"] for f in v.link_faces}))
finish("Room_Shell", bm, "COL_P1_Structure")
box("Enclosed_Float", (-1.6, 1.2, 0.8), (-1.3, 1.5, 1.1))
# cameras and lights
for name, loc, rot in (("CAM_A", (0, -5, 1.6), (90, 0, 0)), ("CAM_B", (2, -5, 1.6), (90, 0, 2.0)), ("Camera", (-2, -5, 1.6), (90, 0, 0))):
    cd = bpy.data.cameras.new(name)
    cd.lens = 24
    ob = bpy.data.objects.new(name, cd)
    ob.location, ob.rotation_euler = loc, [math.radians(a) for a in rot]
    link(ob, "COL_Cameras")
for name, kind, loc, w in (("L_Key", "AREA", (0, 0, 6), 500.0), ("L_Fill", "POINT", (1, 1, 3), 100.0)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = w
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    link(ob, "COL_Lights")
# phase tags: everything except the planted untagged object
for ob in sc.objects:
    if ob.type == "MESH" and ob.name != "Prop_Untagged":
        ob["phase"] = "P5"
        ob["map_id"] = ob.name
bpy.context.view_layer.layer_collection.children["COL_Kit"].exclude = True
bpy.context.view_layer.layer_collection.children["COL_Parked"].exclude = True
bpy.data.objects["Prop_EyeHidden"].hide_set(True)
sc.view_settings.exposure = 0.0

# ---- project files ---------------------------------------------------------------
proj = os.path.join(out, "project")
for d in ("light", "plan"):
    os.makedirs(os.path.join(proj, d), exist_ok=True)
J = lambda p, o: json.dump(o, open(os.path.join(proj, p), "w"), indent=1)
J("light/cameras.json", [{"id": "CAM_A", "pos_m": [0, -5, 1.6], "rot_deg": [90, 0, 0], "lens_mm": 24, "shift": [0, 0]},
                         {"id": "CAM_B", "pos_m": [2, -5, 1.6], "rot_deg": [90, 0, 0], "lens_mm": 24},
                         {"id": "CAM_Gone", "pos_m": [0, 0, 0], "rot_deg": [0, 0, 0]}])
J("light/lights.json", [{"id": "L_Key", "type": "area", "pos_m": [0, 0, 6], "energy_w": 500}, {"id": "L_Fill", "type": "point", "energy_w": 120}])
J("light/exposure.json", {"exposure": 1.5, "view_transform": "Standard", "look": "None"})
J("plan/walk.json", {"paths": {"main": [[-5.8, 0.7], [-3.2, 0.7]]}})
backup_ok = os.path.join(out, "step_ok.blend")
open(backup_ok, "wb").write(b"x")
J("plan/steps.json", {"version": 1, "steps": [{"n": 1, "backup": backup_ok}, {"n": 2, "backup": os.path.join(out, "step_missing.blend")}]})
scene_file = os.path.join(out, "scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=scene_file)

# ---- run and assert --------------------------------------------------------------
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL:", msg)


def flagged(rep, name):
    return {it["object"] for it in rep["checks"][name]["items"]}


def has(rep, name, *objs, absent=()):
    f = flagged(rep, name)
    for o in objs:
        check(o in f, f"{name}: expected {o}, got {sorted(f)}")
    for o in absent:
        check(o not in f, f"{name}: {o} must not be flagged (got {sorted(f)})")


gate = os.path.join(out, "gate", "gate.blend")
rep = lint.run_lint(project=proj, out_dir=os.path.join(out, "r1"), expect_file=gate)
C = rep["checks"]
check(os.path.exists(os.path.join(out, "r1", "lint.json")), "lint.json not written")
check(rep["summary"]["blocker"] > 0 and not rep["summary"]["pass"], "summary should show blockers")
check(not rep["summary"]["errors"], f"a check crashed: {[(k, v.get('error')) for k, v in C.items() if v['status'] == 'error']}")
check(all(v["status"] != "no_subjects" for v in C.values()), f"checks without subjects: {rep['summary']['no_subjects']}")

has(rep, "file_path", bpy.data.filepath)
has(rep, "faces_no_material", "Prop_NoMat", "Prop_BadIndex", absent=("Prop_Crate",))
has(rep, "cameras_match", "CAM_B", "CAM_Gone", "Camera", absent=("CAM_A",))
has(rep, "lights_match", "L_Fill", absent=("L_Key",))
check(len(C["exposure_match"]["items"]) == 2, f"exposure: expected exposure and view transform, got {C['exposure_match']['items']}")
has(rep, "names_tags", "Cube.001", "Bad Name", "Camera", "Prop_Untagged", absent=("Prop_Float", "CAM_A", "Prop_Crate"))
has(rep, "origin_objects", "Prop_At_Origin", "Inst_Prop", absent=("Prop_Origin_OK", "SM_Floor"))
has(rep, "visibility_states", "Stub_Review_Bad", "Ref_Box", "Prop_EyeHidden", absent=("Stub_Review_Ok", "Parked_Box"))
check(any(it["object"] == "Stub_Review_Bad" and it["class"] == "blocker" for it in C["visibility_states"]["items"]), "review-only visible must be a blocker")
has(rep, "wear_geometry", "Grime_Band_01", "Stain_Overlay", absent=("SM_Stainless_Tray", "Prop_Dent_Repair"))
has(rep, "step_backup", "step 2", absent=("step 1",))
fl = flagged(rep, "floating")
for o in ("Prop_Float", "Prop_Float_Pair_A", "Prop_Float_Pair_B", "Enclosed_Float"):
    check(o in fl, f"floating: expected {o}, got {sorted(fl)}")
for o in ("Prop_Crate", "SM_Vent_Good", "Box_A", "Box_Post_H1", "SM_Door_Ok", "Prop_Touch_A", "Stub_Review_Bad"):
    check(o not in fl, f"floating: {o} rests on something, got {sorted(fl)}")
pen = flagged(rep, "interpenetration")
check("Prop_Overlap_A x Prop_Overlap_B" in pen or "Prop_Overlap_B x Prop_Overlap_A" in pen, f"interpenetration missed the 5 cm overlap: {sorted(pen)}")
check(not any("Prop_Touch" in p for p in pen), f"interpenetration flagged a 5 mm overlap: {sorted(pen)}")
has(rep, "through_wall_openings", "SM_Vent_Bad", absent=("SM_Vent_Good",))
tw = {it["object"]: it for it in C["through_wall_openings"]["items"]}
check(tw["SM_Vent_Bad"]["class"] == "major", f"vent on solid wall must be major: {tw['SM_Vent_Bad']}")
check(tw.get("SM_Vent_Pocket", {}).get("class") == "minor" and abs(tw["SM_Vent_Pocket"]["pocket_m"] - 0.12) < 0.01,
      f"vent in a 0.12 m blind pocket must be a minor note: {tw.get('SM_Vent_Pocket')}")
has(rep, "door_sizes", "SM_Door_Narrow", absent=("SM_Door_Ok",))
check(any(it["object"] == "SM_Stair_Step" and it.get("riser_max_m") == 0.22 for it in C["stair_risers"]["items"]), f"stair riser: {C['stair_risers']['items']}")
check(not any("tread" in it["what"] for it in C["stair_risers"]["items"]), "tread depth 0.3 m must pass")
pc = C["path_clearance"]["items"]
check(any(it["type"] == "width" for it in pc) and any(it["type"] == "capsule" for it in pc), f"path clearance should flag the 0.4 m gap: {pc}")

# cable ends: the hooked run must show its hanging end; two floaters must not vouch for each other
cab = {it["object"]: it for it in C["cable_ends"]["items"]}
check(set(cab) == {"Cable_Hook", "Cable_Tail", "Cable_FloatA", "Cable_FloatB"}, f"cable dead ends: {sorted(cab)}")
check("Cable_Ok" not in cab and "Cable_Chain" not in cab and "Cable_Entry" not in cab and "Cable_Droop" not in cab, "attached or terminated cables flagged")
check("3.8, 1.0, 1.5" in cab["Cable_Hook"]["what"].replace("[", "").replace("]", "") or "1.0" in cab["Cable_Hook"]["what"], cab["Cable_Hook"]["what"])
check("float" in cab["Cable_Hook"]["what"] and "tail" in cab["Cable_Tail"]["what"], "hook end is a float, tail end lies along the wall")
check(all(e["class"] == "attached" for e in cab["Cable_Hook"]["ends"] if e["at"][0] < 3.3), "hook's first end is on its post")
check("ungrounded" in cab["Cable_FloatA"]["what"] and "ungrounded" in cab["Cable_FloatB"]["what"], "floating cables must not vouch for each other")
t = C["cable_ends"]["ends"]
check(t["dead_end"] == 6 and t["terminated"] == 1 and t["attached"] == 9, f"end tally {t}")   # 6 = hook 1, tail 1, floaters 4
check(C["cable_ends"]["checked"] == 8, "all eight cables are checked, not zero")
has(rep, "cable_sag", "Cable_Droop", absent=("Cable_Ok",))
has(rep, "conduit_open_ends", "Conduit_Open", absent=("Conduit_Ok",))
check(C["conduit_open_ends"]["status"] == "fail" and C["conduit_open_ends"]["unresolved"] == 0, f"conduit: {C['conduit_open_ends']}")

# fittings: a coupling shorter than it is wide, with two screw heads merged in, reads exactly its two ends;
# saddles and boxes named after the conduit are anchors, not pieces with ends
cpl = tube("Conduit_Coupling_T", path((4.5, -5.0, 1.0), (4.53, -5.0, 1.0), n=1), radius=0.02, k=16)
bm = bmesh.new()
bm.from_mesh(cpl.data)
for x in (4.505, 4.525):
    r_ = bmesh.ops.create_cube(bm, size=0.006)
    bmesh.ops.translate(bm, vec=Vector((x, -5.0, 1.023)), verts=r_["verts"])
bm.to_mesh(cpl.data)
bm.free()
dg = bpy.context.evaluated_depsgraph_get()
ends, _ = lint.object_ends(SimpleNamespace(ob=cpl), dg, 0.4, strict=True)
check(len(ends) == 2 and sorted(round(p.x, 2) for p, _ in ends) == [4.5, 4.53], f"coupling ends: {[tuple(p) for p, _ in ends]}")
for n, conduit in (("SM_Conduit_Saddle_01", False), ("SM_ConduitBox_Round_1", False), ("SM_Conduit_Straight_01", True), ("SM_Conduit_Elbow_02", True)):
    ob = bpy.data.objects.new(n, None)
    link(ob, "COL_P3_Services")
    k = lib.kinds_of(ob, lib.load_rules())
    check(("conduit" in k) == conduit and "anchor" in k, f"{n}: kinds {sorted(k)}")
    bpy.data.objects.remove(ob)
bpy.data.objects.remove(cpl)

# rules file: a project threshold and a severity change take effect
open(os.path.join(proj, "plan", "lint_rules.yaml"), "w").write("# test\nriser_max_m: 0.25\nseverity:\n  names_tags: minor\ndisable: [wear_geometry]\noverlap_allow:\n  - [a, b]\n")
rep2 = lint.run_lint(project=proj, out_dir=os.path.join(out, "r2"))
check(not any(it.get("riser_max_m") for it in rep2["checks"]["stair_risers"]["items"]), "riser_max_m 0.25 should accept 0.22")
check(rep2["checks"]["stair_risers"]["count"] == 1 and "uneven" in rep2["checks"]["stair_risers"]["items"][0]["what"], "only the uneven-riser minor is left")
check(rep2["checks"]["names_tags"]["counts"]["major"] == 0 and rep2["checks"]["names_tags"]["counts"]["minor"] > 0, "severity override turns the names_tags majors into minors")
check("wear_geometry" not in rep2["checks"], "disable list")
check(not any("Prop_Overlap" in p for p in flagged(rep2, "interpenetration")) and "SM_Vent_Bad" in "".join(flagged(rep2, "interpenetration")), "overlap_allow clears the A/B pair only")
check(rep2["checks"]["file_path"]["status"] == "skipped", "file_path skipped without --expect-file")
os.remove(os.path.join(proj, "plan", "lint_rules.yaml"))

# visible set: the enclosed float is hidden, and lint then leaves it out
vs = vset.compute(project=proj, sphere=1500, pix=8)
json.dump(vs, open(os.path.join(proj, "plan", "visible_set.json"), "w"))
check("Enclosed_Float" in vs["hidden"] and "Enclosed_Float" not in vs["visible"], "enclosed object must be hidden")
check({"SM_Floor", "SM_Wall_A", "Prop_Float"} <= set(vs["visible"]), f"visible set misses big objects: {vs['counts']}")
check("CAM_A" in vs["cameras"] and vs["cameras"]["CAM_A"]["hits"] > 0, "camera rays")
check(any(vs["visible"][n]["cams"] for n in vs["visible"] if n in ("SM_Wall_B",)), "CAM_A sees wall B")
rep3 = lint.run_lint(project=proj, out_dir=os.path.join(out, "r3"))
check("Enclosed_Float" not in flagged(rep3, "floating") and "Prop_Float" in flagged(rep3, "floating"), "lint scopes floating to the visible set")
check(rep3["scope"]["in_scope"] < rep3["scope"]["solids"], "scope counts")

# the CLI exits 2 on a blocker and 0 when only majors are left
bl = bpy.app.binary_path
cmd = [bl, "--background", "--factory-startup", scene_file, "--python", os.path.join(HERE, "lint_blender.py"), "--", "--project", proj, "--out", os.path.join(out, "cli")]
p = subprocess.run(cmd, capture_output=True, text=True)
check(p.returncode == 2 and os.path.exists(os.path.join(out, "cli", "lint.json")), f"CLI exit code {p.returncode} (want 2): {p.stdout[-300:]}")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli2"), "--only", "door_sizes,stair_risers"], capture_output=True, text=True)
check(p.returncode == 0, f"CLI exit code {p.returncode} (want 0) with majors only: {p.stdout[-300:]}")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli3"), "--only", "nonsense"], capture_output=True, text=True)
check(p.returncode == 1, f"CLI exit code {p.returncode} (want 1) for an unknown check")

# the yaml subset reader
y = lib.parse_yaml("a: 1\nb: [x, y]\nc:\n  d: true\n  e:\n    - p\n    - q\nf: 'z' # note\n")
check(y == {"a": 1, "b": ["x", "y"], "c": {"d": True, "e": ["p", "q"]}, "f": "z"}, f"yaml subset: {y}")
print("SCENE-LINT SELFTEST", "FAILED" if fails else "OK", f"({len(C)} checks, {rep['seconds']} s)")
sys.exit(1 if fails else 0)
