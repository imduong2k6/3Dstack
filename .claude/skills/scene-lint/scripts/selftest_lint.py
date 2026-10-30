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
import numpy as np
from types import SimpleNamespace
from mathutils import Euler, Vector

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


def text(name, loc, props=None, cname="COL_P5_Props", body="x", size=0.1):
    """A live text object (FONT) lying on the floor: lint reads it like a mesh."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size = body, size
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    for k, v in (props or {}).items():
        ob[k] = v
    return link(ob, cname)


def multibox(name, boxes, cname, **kw):
    bm = bmesh.new()
    for lo, hi in boxes:
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])), verts=r["verts"])
        bmesh.ops.translate(bm, vec=Vector([(a + b) / 2 for a, b in zip(lo, hi)]), verts=r["verts"])
    return finish(name, bm, cname, **kw)


def _tube(bm, pts, radius, k, closed=False):
    """One tube along world points into bm: fan caps, or a closed loop (no ends) when closed."""
    pts = [Vector(p) for p in pts]
    n, rings = len(pts), []
    for i, p in enumerate(pts):
        tg = ((pts[(i + 1) % n] - pts[i - 1]) if closed else (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])).normalized()
        ref = Vector((0, 0, 1)) if abs(tg.z) < 0.9 else Vector((1, 0, 0))
        u = tg.cross(ref).normalized()
        w = tg.cross(u)
        rings.append([bm.verts.new(p + (u * math.cos(a) + w * math.sin(a)) * radius) for a in (2 * math.pi * j / k for j in range(k))])
    for r0, r1 in zip(rings, rings[1:] + ([rings[0]] if closed else [])):
        for j in range(k):
            bm.faces.new((r0[j], r0[(j + 1) % k], r1[(j + 1) % k], r1[j]))
    for ring, flip in (() if closed else ((rings[0], True), (rings[-1], False))):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / k)
        for j in range(k):
            bm.faces.new((c, ring[j], ring[(j + 1) % k]) if not flip else (c, ring[(j + 1) % k], ring[j]))


def tube(name, pts, radius=0.01, k=8, cname="COL_P3_Services", closed=False, **kw):
    """A capped k-sided tube along world points (fan caps), like the pipeline's swept cables. pts may be a list of paths: one
    mesh of separate tubes, a bundle."""
    bm = bmesh.new()
    for run in (pts if isinstance(pts[0][0], (list, tuple)) else [pts]):
        _tube(bm, run, radius, k, closed)
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
box("SM_Vent_Good", (0.1, 2.9, 1.5), (0.5, 3.3, 1.9), "COL_P3_Services")              # inside the cut opening, flush with its sides
box("SM_Vent_Bad", (0.1, -3.3, 1.5), (0.5, -2.9, 1.9), "COL_P3_Services")              # through a solid wall
multibox("SM_Wall_P", [((4.2, -3.2, 0), (5.2, -3.12, 3)), ((4.2, -3.12, 0), (4.5, -3.0, 3)), ((4.9, -3.12, 0), (5.2, -3.0, 3)),
                       ((4.5, -3.12, 0), (4.9, -3.0, 1.5)), ((4.5, -3.12, 1.9), (4.9, -3.0, 3))], "COL_P1_Structure")
box("SM_Vent_Pocket", (4.52, -3.12, 1.52), (4.88, -2.95, 1.88), "COL_P3_Services")      # in a 0.12 m blind pocket: under 0.15 m, a major
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
box("Prop_Seat_Gap", (-5.6, 2.0, 0.015), (-5.2, 2.4, 0.3))                               # 1.5 cm above the floor: inside the 2 cm touch tolerance, but not seated
box("Prop_Seat_Ok", (-5.6, 2.8, 0.001), (-5.2, 3.2, 0.3))                                # 1 mm above it: seated
box("Prop_Seat_Allowed", (-5.6, 3.6, 0.015), (-5.2, 4.0, 0.3), props={"seat_ok": 1})       # an intended gap
box("Prop_Touch_B", (-3.005, -5.4, 0.1), (-2.5, -4.9, 0.6))                                # 5 mm into A: inside the tolerance
box("Prop_At_Origin", (-0.4, -0.2, 0), (-0.1, 0.2, 0.3))                                 # object origin at (0, 0, 0)
box("Prop_Origin_OK", (0.1, -0.2, 0), (0.4, 0.2, 0.3), props={"origin_ok": 1})
text("Text_Untagged", (0.0, -5.5, 0), cname="COL_Blockout")                                # no phase tag, no map_id
text("Text_Tagged", (0.5, -5.5, 0), {"phase": "P5"})
text("Text_AtOrigin", (0, 0, 0), {"phase": "P5"})                                          # a text object at the world origin
text("Text_EyeHidden", (1.0, -5.5, 0), {"phase": "P5"}).hide_set(True)                       # renders, hidden in the viewport
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
box("Wall_Gland_Entry", (1.97, 2.9, 1.92), (2.03, 3.0, 1.98), "COL_P3_Services")          # hardware at the wall entry
tube("Cable_Entry", path((1.6, 2.95, 1.95), (2.0, 2.95, 1.95), (2.0, 3.0, 1.95)))       # ends head-on in the wall, through the gland
box("Box_Feed", (2.45, 2.9, 2.2), (2.65, 3.0, 2.4), "COL_P3_Services")
tube("Cable_Bare_Entry", path((2.45, 2.95, 2.3), (2.0, 2.95, 2.3), (2.0, 3.0, 2.3)))     # ends head-on in the wall with no hardware near
box("SM_Sign_Plate", (3.0, 2.9, 1.3), (3.6, 3.0, 1.7), "COL_P3_Services")                 # a sign face a cable must not end on
box("SM_Sign_Box", (3.62, 2.9, 1.3), (3.8, 3.0, 1.5), "COL_P3_Services")                  # the sign's own box is hardware
tube("Cable_OnPlate", path((2.65, 2.95, 2.35), (3.3, 2.95, 2.35), (3.3, 2.95, 1.7)))      # ends on the sign's top face
tube("Cable_ToHardware", path((2.65, 2.95, 2.22), (3.71, 2.95, 2.22), (3.71, 2.95, 1.5)))  # ends on the sign's box
tube("Cable_FloatA", path((-4, -4.5, 1.0), (-3, -4.5, 1.0)))
tube("Cable_FloatB", path((-3, -4.5, 1.0), (-2, -4.5, 1.0)))
tube("Cable_Droop", path((1.2, -4.0, 1.9), (2.1, -4.0, 0.9), (3.0, -4.0, 1.9), n=8))
# a bundle: ten strands in one mesh (20 ends), strand 4 stops in the air, strand 7 pokes into wall B with no hardware; a small tie ring has no ends
box("Box_BA", (-3.7, -3.0, 0.8), (-3.5, -2.9, 2.2), "COL_P3_Services")
box("Box_BB", (-1.7, -3.0, 0.8), (-1.5, -2.9, 2.2), "COL_P3_Services")
strands = [path((-3.5, -2.95, 0.9 + 0.12 * i), (-1.7, -2.95, 0.9 + 0.12 * i), n=3) for i in range(10)]
strands[4] = path((-3.5, -2.95, 1.38), (-3.2, -2.7, 1.38), (-2.4, -2.7, 1.38), n=2)
strands[7] = path((-3.5, -2.95, 1.74), (-2.6, -2.95, 1.74), (-2.6, -3.0, 1.74), n=3)
bm = bmesh.new()
for run in strands:
    _tube(bm, run, 0.01, 8)
_tube(bm, [(-2.6 + 0.05 * math.cos(a), -2.95, 2.15 + 0.05 * math.sin(a)) for a in (2 * math.pi * j / 16 for j in range(16))], 0.003, 8, closed=True)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
finish("Cable_Bundle", bm, "COL_P3_Services")
tube("Cable_Ring", [(-4.5 + 0.3 * math.cos(a), 4.5 + 0.3 * math.sin(a), 1.0) for a in (2 * math.pi * j / 12 for j in range(12))], closed=True)   # a closed loop: no ends to read
tube("Cable_EndsOk", path((-4.0, -7.0, 1.0), (-3.0, -7.0, 1.0)), props={"ends_ok": 1})   # ends_ok: a cable that leaves the frame
box("SM_Window_Pane", (-0.9, -3.0, 1.2), (-0.3, -2.94, 2.3), "COL_P3_Services")          # a window a cable end must not enter
tube("Cable_InWindow", path((-1.5, -2.97, 2.1), (-0.6, -2.97, 2.1)))
# conduit: nine pieces in one mesh (18 ends), the fifth stops 0.3 m short of its box
box("Box_CT", (1.0, -3.0, 2.5), (3.4, -2.9, 2.7), "COL_P3_Services")
box("Box_CB", (1.0, -3.0, 0.3), (3.4, -2.9, 0.5), "COL_P3_Services")
tube("Conduit_Merged", [path((1.2 + 0.25 * i, -2.95, 0.5), (1.2 + 0.25 * i, -2.95, 2.2 if i == 4 else 2.5), n=2) for i in range(9)], radius=0.016)
tube("Conduit_Ok", path((-3.4, 2.95, 2.1), (-3.4, 2.95, 2.5)), radius=0.016)
tube("Conduit_Open", path((-1.4, 2.95, 2.1), (-1.4, 2.95, 2.4)), radius=0.016)
# narrow gap on the walk path, an enclosed room with something floating in it
box("Pillar_N_A", (-4.7, 0.9, 0), (-4.3, 1.4, 2.5))
box("Pillar_N_B", (-4.7, 0.0, 0), (-4.3, 0.5, 2.5))
box("Stag_L", (-0.15, 5.0, 0), (0.15, 5.4, 2.2))                                         # 0.4 m left of the path, 0.5 m along from Stag_R: each side alone leaves 1.4 m
box("Stag_R", (0.35, 3.8, 0), (0.65, 4.2, 2.2))                                          # 0.4 m right of it: no body fits between the two
box("Apart_L", (2.5, 5.0, 0), (2.8, 5.4, 2.2))                                           # the same pair 1.1 m apart along the path: passes
box("Apart_R", (3.9, 3.8, 0), (4.2, 4.2, 2.2))
box("Prop_Sign_Over", (-5.65, 0.55, 1.92), (-5.45, 0.85, 2.0))                          # above the 1.8 m capsule, under the 2.1 m headroom
tube("Prop_Hose_Over", path((-5.3, 0.82, 2.05), (-4.9, 0.82, 2.05)))                    # thin and parallel to the path, between the head rays
box("SM_Landing_R", (4.2, 0.8, 0), (5.8, 1.2, 0.2), "COL_P1_Structure")                  # a raised strip with a path along it, and beside it
box("Prop_Hood_Edge", (4.8, 1.22, 2.2), (5.2, 1.5, 2.3))                                 # 2.0 m over the strip, 2.2 m over the floor it hangs above
box("Prop_Shin_A", (-3.65, 0.24, 0), (-3.45, 0.31, 0.4))                                # 0.78 m apart at shin height only,
box("Prop_Shin_B", (-3.65, 1.09, 0), (-3.45, 1.16, 0.4))                                # outside the knee reach
box("SM_DoorGod_L", (2.0, 5.5, 1.2), (2.3, 5.51, 1.75))                                 # prints and soft goods named after the door
box("SM_EndDoor_Curtain", (2.6, 5.5, 0.3), (3.05, 5.52, 1.88))
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
J("plan/walk.json", {"paths": {"main": [[-5.8, 0.7], [-3.2, 0.7]], "edge": [[4.3, 1.0, 0.2], [5.7, 1.0]], "stag": [[-2.0, 4.6], [4.5, 4.6]]}})
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
has(rep, "names_tags", "Cube.001", "Bad Name", "Camera", "Prop_Untagged", "Text_Untagged", absent=("Prop_Float", "CAM_A", "Prop_Crate", "Text_Tagged"))
has(rep, "origin_objects", "Prop_At_Origin", "Inst_Prop", "Text_AtOrigin", absent=("Prop_Origin_OK", "SM_Floor"))
has(rep, "visibility_states", "Stub_Review_Bad", "Ref_Box", "Prop_EyeHidden", "Text_EyeHidden", absent=("Stub_Review_Ok", "Parked_Box"))
check(any(it["object"] == "Stub_Review_Bad" and it["class"] == "blocker" for it in C["visibility_states"]["items"]), "review-only visible must be a blocker")
has(rep, "wear_geometry", "Grime_Band_01", "Stain_Overlay", absent=("SM_Stainless_Tray", "Prop_Dent_Repair"))
has(rep, "step_backup", "step 2", absent=("step 1",))
fl = flagged(rep, "floating")
for o in ("Prop_Float", "Prop_Float_Pair_A", "Prop_Float_Pair_B", "Enclosed_Float"):
    check(o in fl, f"floating: expected {o}, got {sorted(fl)}")
for o in ("Prop_Crate", "SM_Vent_Good", "Box_A", "Box_Post_H1", "SM_Door_Ok", "Prop_Touch_A", "Stub_Review_Bad"):
    check(o not in fl, f"floating: {o} rests on something, got {sorted(fl)}")
sg = {it["object"]: it for it in C["seat_gap"]["items"]}
check(set(sg) == {"Prop_Seat_Gap"} and abs(sg["Prop_Seat_Gap"]["gap_m"] - 0.015) < 0.0005 and sg["Prop_Seat_Gap"]["on"] == "SM_Floor" and sg["Prop_Seat_Gap"]["class"] == "major",
      f"seat gap: the 1.5 cm prop only (1 mm, flush, crossing, seat_ok and floating objects pass): {sg}")
check("Prop_Seat_Gap" not in fl, "the 1.5 cm prop is inside the touch tolerance, so `floating` passes it and seat_gap catches it")
pen = flagged(rep, "interpenetration")
check("Prop_Overlap_A x Prop_Overlap_B" in pen or "Prop_Overlap_B x Prop_Overlap_A" in pen, f"interpenetration missed the 5 cm overlap: {sorted(pen)}")
check(not any("Prop_Touch" in p for p in pen), f"interpenetration flagged a 5 mm overlap: {sorted(pen)}")
has(rep, "through_wall_openings", "SM_Vent_Bad", absent=("SM_Vent_Good",))
tw = {it["object"]: it for it in C["through_wall_openings"]["items"]}
check(tw["SM_Vent_Bad"]["class"] == "major", f"vent on solid wall must be major: {tw['SM_Vent_Bad']}")
check(tw.get("SM_Vent_Pocket", {}).get("class") == "major" and abs(tw["SM_Vent_Pocket"]["pocket_m"] - 0.12) < 0.01,
      f"vent in a 0.12 m blind pocket (under 0.15 m) must be major: {tw.get('SM_Vent_Pocket')}")
check(rep["command"] == sys.argv and rep["project"] == proj and rep["inputs"]["walk"].endswith("walk.json"), "lint.json records the command and its inputs")
has(rep, "door_sizes", "SM_Door_Narrow", absent=("SM_Door_Ok", "SM_DoorGod_L", "SM_EndDoor_Curtain"))
check(any(it["object"] == "SM_Stair_Step" and it.get("riser_max_m") == 0.22 for it in C["stair_risers"]["items"]), f"stair riser: {C['stair_risers']['items']}")
check(not any("tread" in it["what"] for it in C["stair_risers"]["items"]), "tread depth 0.3 m must pass")
pc = C["path_clearance"]["items"]
check(any(it["type"] == "width" for it in pc) and any(it["type"] == "capsule" for it in pc), f"path clearance should flag the 0.4 m gap: {pc}")
sign = {it["type"] for it in pc if "Prop_Sign_Over" in it["object"]}
check(sign == {"head"}, f"a sign at 1.92 m is a headroom item, not inside the 1.8 m capsule: {sign}")
hose = [it for it in pc if "Prop_Hose_Over" in it["object"]]
check([it["type"] for it in hose] == ["head"] and 2.0 < hose[0]["worst"] < 2.1, f"a thin hose at 2.04 m, off the head rays, is a headroom item: {hose}")
check(not any("Prop_Hood_Edge" in it["object"] for it in pc), f"2.2 m over its own floor clears, though the sphere reaches it from the raised strip: {pc}")
stag = [it for it in pc if it["path"] == "stag"]
check(len(stag) == 1 and stag[0]["type"] == "width" and "Stag_L" in stag[0]["object"] and "Stag_R" in stag[0]["object"] and 0.79 < stag[0]["worst"] < 0.81,
      f"obstacles on opposite sides 0.5 m apart along the path leave 0.8 m: {stag}")   # and the pair 1.1 m apart passes (nothing else on this path)
check(any(it["type"] == "width" and "Prop_Shin_A" in it["object"] and "Prop_Shin_B" in it["object"] for it in pc), f"shin-height clutter narrows the path: {pc}")

# cable ends: the hooked run must show its hanging end; two floaters must not vouch for each other
cab = {}
for it in C["cable_ends"]["items"]:
    cab.setdefault(it["object"], []).append(it)
dead = {n for n, its in cab.items() if any("reason" in it for it in its)}
want = {"Cable_Hook", "Cable_Tail", "Cable_FloatA", "Cable_FloatB", "Cable_Bare_Entry", "Cable_OnPlate", "Cable_InWindow", "Cable_Bundle"}
check(dead == want, f"cable dead ends: {sorted(dead)}")
check(set(cab) - dead == {"Cable_Ring"} and cab["Cable_Ring"][0]["class"] == "minor", f"only the closed loop is unresolved: {sorted(set(cab) - dead)}")
check(not ({"Cable_Ok", "Cable_Chain", "Cable_Entry", "Cable_Droop", "Cable_ToHardware", "Cable_EndsOk"} & set(cab)), f"attached, terminated or ends_ok cables flagged: {sorted(cab)}")
at = lambda n, i=0: cab[n][i]["at"]
check(len(cab["Cable_Hook"]) == 1 and abs(at("Cable_Hook")[0] - 3.8) < 0.01 and abs(at("Cable_Hook")[1] - 1.0) < 0.01, cab["Cable_Hook"])
check(cab["Cable_Hook"][0]["reason"] == "float" and cab["Cable_Hook"][0]["surface"] is None and "tail along SM_Wall_A" == cab["Cable_Tail"][0]["reason"], "hook end is a float, tail end lies along the wall")
check(all("dead end: " in it["what"] and it["reason"] in it["what"] for its in cab.values() for it in its if "reason" in it), "each dead end names its reason")
check(all(any("ungrounded" in it["what"] for it in cab[n]) and any(it["reason"] == "float" for it in cab[n]) for n in ("Cable_FloatA", "Cable_FloatB")), "floating cables must not vouch for each other")
be = cab["Cable_Bare_Entry"][0]
check(be["reason"] == "enters SM_Wall_A, no hardware within 5 cm" and be["surface"] == "SM_Wall_A" and abs(be["at"][1] - 3.0) < 0.01 and abs(be["at"][2] - 2.3) < 0.01, f"bare wall entry: {be}")
sg = cab["Cable_OnPlate"][0]
check(sg["reason"] == "on a sign face: SM_Sign_Plate" and sg["surface"] == "SM_Sign_Plate" and abs(sg["at"][2] - 1.7) < 0.01, f"end on a sign: {sg}")
check(cab["Cable_InWindow"][0]["reason"] == "on a window face: SM_Window_Pane" and cab["Cable_InWindow"][0]["surface"] == "SM_Window_Pane", f"end in a window: {cab['Cable_InWindow']}")
bu = {it["reason"]: it for it in cab["Cable_Bundle"]}   # 10 strands in one mesh: 20 ends, used to be given up on past 16
check(len(cab["Cable_Bundle"]) == 2 and "float" in bu and "enters SM_Wall_B, no hardware within 5 cm" in bu, f"bundle dead ends: {cab['Cable_Bundle']}")
check(abs(bu["float"]["at"][0] + 2.4) < 0.01 and abs(bu["float"]["at"][2] - 1.38) < 0.01, f"bundle float end: {bu['float']}")
check(all(len(e) == 3 for it in cab["Cable_Bundle"] for e in [it["at"]]) and bu["float"]["surface"] is None, "dead end items carry the world position")
t = C["cable_ends"]["ends"]
check(t["dead_end"] == 11 and t["terminated"] == 2 and t["attached"] == 33, f"end tally {t}")   # dead: hook, tail, floaters 4, bare entry, sign, window, bundle 2
check(C["cable_ends"]["checked"] == 15 and C["cable_ends"]["unresolved"] == 1, f"cables checked, unresolved: {C['cable_ends']}")
has(rep, "cable_sag", "Cable_Droop", absent=("Cable_Ok", "Cable_Bundle"))
has(rep, "conduit_open_ends", "Conduit_Open", "Conduit_Merged", absent=("Conduit_Ok",))
cm = next(it for it in C["conduit_open_ends"]["items"] if it["object"] == "Conduit_Merged")
check(cm["what"].startswith("1 open end(s)") and "2.2" in cm["what"], f"merged conduit (18 ends): only the short piece is open: {cm['what']}")
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

# the same mesh reads the same ends to the last bit, capped or open: a float sum over a set of BMesh elements follows memory addresses
capped = tube("Conduit_Repeat_T", path((12.345, -7.891, 3.217), (12.911, -7.433, 3.871), n=1), radius=0.0173, k=32)
opened = tube("Conduit_RepeatOpen_T", path((12.345, -6.891, 3.217), (12.911, -6.433, 3.871), n=1), radius=0.0173, k=32)
bm = bmesh.new()
bm.from_mesh(opened.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if len(f.verts) == 3], context="FACES")
bm.to_mesh(opened.data)
bm.free()
dg = bpy.context.evaluated_depsgraph_get()
for ob in (capped, opened):
    reads, keep = set(), []
    for _ in range(12):
        ends, _m = lint.object_ends(SimpleNamespace(ob=ob), dg, 0.4)
        reads.add(tuple(tuple(p) + tuple(d) for p, d in ends))
        keep.append(bmesh.new())   # holds memory, so the next read's elements land at other addresses
        keep[-1].from_mesh(ob.data)
    check(len(ends) == 2 and len(reads) == 1, f"{ob.name}: {len(ends)} ends, {len(reads)} different reads of the same mesh")
    for b in keep:
        b.free()
    bpy.data.objects.remove(ob)

# a point on a face is not inside, whatever the rotation: ray parity there is rounding noise
rot = Euler((0.4, 0.7, 0.2)).to_matrix()
cube = lib.Solid("T", None, np.array([rot @ Vector((x, y, z)) for x in (0, 1) for y in (0, 1) for z in (0, 1)]), np.array(
    [t for a, b, c, d in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)) for t in ((a, b, c), (a, c, d))]), set())
on_face = [rot @ Vector((x, 0.03 + i * 0.047, 0.03 + j * 0.047)) for x in (0, 1) for i in range(20) for j in range(20)]
n_in = sum(cube.inside(p) for p in on_face)
check(n_in == 0, f"{n_in} of {len(on_face)} points on a face read as inside")
check(cube.inside(rot @ Vector((0.998, 0.5, 0.5))) and not cube.inside(rot @ Vector((1.002, 0.5, 0.5))), "2 mm under a face is inside, 2 mm over it is not")

# rules file: a project threshold and a severity change take effect
open(os.path.join(proj, "plan", "lint_rules.yaml"), "w").write("# test\nriser_max_m: 0.25\nvent_pocket_min_m: 0.1\ncable_end_hardware_m: 0.5\nseverity:\n  names_tags: minor\ndisable: [wear_geometry]\noverlap_allow:\n  - [a, b]\n")
rep2 = lint.run_lint(project=proj, out_dir=os.path.join(out, "r2"))
check(not any(it.get("riser_max_m") for it in rep2["checks"]["stair_risers"]["items"]), "riser_max_m 0.25 should accept 0.22")
check(rep2["checks"]["stair_risers"]["count"] == 1 and "uneven" in rep2["checks"]["stair_risers"]["items"][0]["what"], "only the uneven-riser minor is left")
check(rep2["checks"]["names_tags"]["counts"]["major"] == 0 and rep2["checks"]["names_tags"]["counts"]["minor"] > 0, "severity override turns the names_tags majors into minors")
check("wear_geometry" not in rep2["checks"], "disable list")
check(not any("Prop_Overlap" in p for p in flagged(rep2, "interpenetration")) and "SM_Vent_Bad" in "".join(flagged(rep2, "interpenetration")), "overlap_allow clears the A/B pair only")
check(rep2["checks"]["file_path"]["status"] == "skipped", "file_path skipped without --expect-file")
tw2 = {it["object"]: it for it in rep2["checks"]["through_wall_openings"]["items"]}
check(tw2["SM_Vent_Pocket"]["class"] == "minor" and tw2["SM_Vent_Bad"]["class"] == "major", "vent_pocket_min_m 0.1 turns the 0.12 m pocket into a note")
ce2 = {}
for it in rep2["checks"]["cable_ends"]["items"]:
    ce2.setdefault(it["object"], []).append(it)
check("Cable_Bare_Entry" not in ce2 and len(ce2["Cable_Bundle"]) == 2, f"cable_end_hardware_m 0.5 accepts the wall entry 0.32 m from the gland, not the bundle's: {sorted(ce2)}")
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

# --baseline shows only what a run adds: the same scene against itself shows nothing, a problem that moved is not new, a new one is
base = os.path.join(out, "r3", "lint.json")
b1 = lint.run_lint(project=proj, out_dir=os.path.join(out, "b1"), baseline=base)
check(b1["new"] == {} and b1["baseline"]["new"] == {"blocker": 0, "major": 0, "minor": 0} and b1["baseline"]["gone"] == 0, f"same scene against itself: {b1['new']}")
victim = next(it["object"] for name in ("door_sizes", "stair_risers", "floating") for it in rep3["checks"][name]["items"] if it["object"] in bpy.data.objects and it["object"] != "Prop_Float")
bpy.data.objects.remove(bpy.data.objects[victim])
bpy.data.objects["Prop_Float"].location.z += 0.003
box("Prop_New_Float", (7.0, 7.0, 3.0), (7.2, 7.2, 3.2))
b2 = lint.run_lint(project=proj, out_dir=os.path.join(out, "b2"), baseline=base)
new_float = {it["object"] for it in b2["new"].get("floating", [])}
check("Prop_New_Float" in new_float and "Prop_Float" not in new_float, f"baseline: a new problem shows, a moved one doesn't: {sorted(new_float)}")
check(b2["baseline"]["new"]["major"] >= 1 and b2["baseline"]["gone"] >= 1, f"baseline counts: {b2['baseline']}")
check(json.load(open(os.path.join(out, "b2", "lint.json")))["new"].keys() == b2["new"].keys(), "lint.json carries `new`")
# past max_items the keys still hold every item, and an older lint.json without them says so
cap_rules = os.path.join(out, "cap_rules.yaml")
open(cap_rules, "w").write("max_items: 1\n")
t1 = lint.run_lint(project=proj, out_dir=os.path.join(out, "t1"), rules=cap_rules)
capped = sorted(n for n, ch in t1["checks"].items() if ch.get("items_truncated"))
check(capped and all(len(t1["checks"][n]["keys"]) == t1["checks"][n]["count"] for n in capped), f"keys hold every item past max_items: {capped}")
t1_file = os.path.join(out, "t1", "lint.json")
t2 = lint.run_lint(project=proj, out_dir=os.path.join(out, "t2"), rules=cap_rules, baseline=t1_file)
check(t2["new"] == {} and t2["baseline"]["partial"] == [], f"items past max_items are not new: {list(t2['new'])}")
older = json.load(open(t1_file))
for ch in older["checks"].values():
    ch.pop("keys", None)
older_file = os.path.join(out, "older.json")
json.dump(older, open(older_file, "w"))
check(lint.run_lint(project=proj, out_dir=os.path.join(out, "t3"), rules=cap_rules, baseline=older_file)["baseline"]["partial"] == capped, "an older baseline is reported as partial")
not_lint = os.path.join(out, "not_lint.json")
json.dump({"a": 1}, open(not_lint, "w"))
for bad in (os.path.join(out, "nope.json"), not_lint, scene_file):
    try:
        lint.run_lint(project=proj, out_dir=os.path.join(out, "x"), baseline=bad)
        check(False, f"a bad baseline must stop the run: {bad}")
    except lint.L.LintError:
        pass

# the CLI exits 2 on a blocker and 0 when only majors are left
bl = bpy.app.binary_path
cmd = [bl, "--background", "--factory-startup", scene_file, "--python", os.path.join(HERE, "lint_blender.py"), "--", "--project", proj, "--out", os.path.join(out, "cli")]
p = subprocess.run(cmd, capture_output=True, text=True)
check(p.returncode == 2 and os.path.exists(os.path.join(out, "cli", "lint.json")), f"CLI exit code {p.returncode} (want 2): {p.stdout[-300:]}")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli2"), "--only", "door_sizes,stair_risers"], capture_output=True, text=True)
check(p.returncode == 0, f"CLI exit code {p.returncode} (want 0) with majors only: {p.stdout[-300:]}")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli3"), "--only", "nonsense"], capture_output=True, text=True)
check(p.returncode == 1, f"CLI exit code {p.returncode} (want 1) for an unknown check")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli4"), "--baseline", os.path.join(out, "cli", "lint.json")], capture_output=True, text=True)
check(p.returncode == 2 and "NEW blocker=0 major=0 minor=0 gone=0" in p.stdout, f"CLI with a baseline: exit {p.returncode}, keeps the exit code, prints NEW: {p.stdout[-300:]}")
p = subprocess.run(cmd[:-2] + ["--out", os.path.join(out, "cli5"), "--baseline", os.path.join(out, "nope.json")], capture_output=True, text=True)
check(p.returncode == 1 and "LINT ERROR" in p.stdout, f"CLI exit code {p.returncode} (want 1) for a missing baseline")

# cable_in_rigid and the stable cable_ends key, in a fresh small scene so the tallies above stay as they are
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
MAT = bpy.data.materials.new("M_Test")
MAT["material_group"] = "plaster"
cols.clear()
col("COL_P3_Services")


def open_tube(name, pts, radius):
    """A single-surface tube with open ends: a conduit whose bore is open."""
    bm = bmesh.new()
    _tube(bm, pts, radius, 8)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if len(f.verts) == 3], context="FACES")
    return finish(name, bm, "COL_P3_Services")


# a conduit and a rotated, scaled linked duplicate of it: the cable through the duplicate is a defect, the one 3 cm off its wall is not
src = tube("SM_Conduit_Straight_Src", path((0, 0, 0), (0, 0, 1), n=3), radius=0.03, k=16)
dup = bpy.data.objects.new("SM_Conduit_Straight_Inst", src.data)
dup.location, dup.rotation_euler, dup.scale = (3, -2, 0.5), (0.6, 0.4, 1.1), (1.5, 1.5, 1.2)
link(dup, "COL_P3_Services")
bpy.context.view_layer.update()
mw = dup.matrix_world
mid, ax, side = mw @ Vector((0, 0, 0.5)), (mw.to_3x3() @ Vector((0, 0, 1))).normalized(), (mw.to_3x3() @ Vector((1, 0, 0))).normalized()   # 4.5 cm radius, 1.2 m long
tube("Cable_Thru_Inst", path(mid - side * 0.15, mid + side * 0.15, n=12), radius=0.004)
tube("Cable_Near_Inst", path(mid + side * 0.079 - ax * 0.3, mid + side * 0.079 + ax * 0.3, n=12), radius=0.004)
# a straight pipe: a cable lying 15 mm into it, a cable lying on it (2 mm in)
tube("SM_Pipe_Straight_A", path((0, 5, 0.5), (2, 5, 0.5), n=8), radius=0.05, k=16)
tube("Cable_In_Pipe", path((0.4, 5, 0.545), (1.6, 5, 0.545), n=12))
tube("Cable_On_Pipe", path((0.4, 5, 0.442), (1.6, 5, 0.442), n=12))
# a thin sign board: a cable through it, a cable 2 cm in front of it, a marked cable through it
box("SM_Sign_Board_A", (5, 5.0, 0.5), (6, 5.03, 1.1), "COL_P3_Services")
tube("Cable_Thru_Sign", path((5.5, 4.8, 0.8), (5.5, 5.25, 0.8), n=12))
tube("Cable_Ahead_Sign", path((5.2, 4.97, 0.6), (5.2, 4.97, 1.0), n=8))
tube("Cable_Marked", path((5.8, 4.8, 0.8), (5.8, 5.25, 0.8), n=12), props={"overlap_ok": 1})
# boxes: a cable that ends inside one passes, a cable through one does not
box("SM_JunctionBox_A", (8, 5, 0.5), (8.14, 5.07, 0.63), "COL_P3_Services")
tube("Cable_End_In_J", path((8.07, 4.7, 0.565), (8.07, 5.035, 0.565), n=8))
box("SM_JunctionBox_B", (9, 5, 0.5), (9.14, 5.07, 0.63), "COL_P3_Services")
tube("Cable_Pass_J", path((9.07, 4.7, 0.565), (9.07, 5.4, 0.565), n=10))
# never hosts: a saddle, a wall, a box tagged kind=anchor by hand
box("SM_Saddle_A", (11, 5, 0.5), (11.1, 5.1, 0.6), "COL_P3_Services")
tube("Cable_Pass_Saddle", path((11.05, 4.7, 0.55), (11.05, 5.4, 0.55), n=10))
box("SM_Wall_X", (13, 5, 0), (13.2, 6, 3), "COL_P3_Services")
tube("Cable_Pass_Wall", path((13.1, 4.7, 1), (13.1, 6.3, 1), n=10))
box("Block_Tagged", (15, 5, 0.5), (15.1, 5.1, 0.6), "COL_P3_Services", props={"kind": "anchor"})
tube("Cable_Pass_Anchor", path((15.05, 4.7, 0.55), (15.05, 5.4, 0.55), n=10))
# a cable in its conduit: from the end of a capped solid tube and of an open tube, coaxial; one that leaves through the wall is not
tube("SM_Conduit_Straight_Cap", path((17, 5, 0.5), (18, 5, 0.5), n=8), radius=0.03, k=16)
tube("Cable_Cap_Run", path((16.7, 5, 0.5), (17.8, 5, 0.5), n=11))
tube("SM_Conduit_Straight_Cap2", path((17, 6, 0.5), (18, 6, 0.5), n=8), radius=0.03, k=16)
tube("Cable_Cap_Exit", path((16.7, 6, 0.5), (17.3, 6, 0.5), (17.3, 6, 0.9), n=6))
open_tube("SM_Conduit_Straight_Open", path((20, 5, 0.5), (21, 5, 0.5), n=8), 0.03)
tube("Cable_Open_Run", path((19.7, 5, 0.5), (20.6, 5, 0.5), n=9))
rig = lint.run_lint(project=None, out_dir=os.path.join(out, "cir"), only=["cable_in_rigid"])
ci = {it["object"]: it for it in rig["checks"]["cable_in_rigid"]["items"]}
want = {"Cable_Thru_Inst x SM_Conduit_Straight_Inst", "Cable_In_Pipe x SM_Pipe_Straight_A", "Cable_Thru_Sign x SM_Sign_Board_A",
        "Cable_Pass_J x SM_JunctionBox_B", "Cable_Cap_Exit x SM_Conduit_Straight_Cap2"}
check(set(ci) == want and rig["checks"]["cable_in_rigid"]["checked"] == 14 and not rig["summary"]["errors"], f"cable_in_rigid: expected {sorted(want)}, got {sorted(ci)}")
check(all(it["class"] == "major" and it["what"].startswith("cable runs through ") for it in ci.values()), "cable_in_rigid is a major, one item per pair")
check(rig["checks"]["cable_in_rigid"]["pairs_inside"] == 8, f"the 5 defects and the 3 allowed cases (end in a box, in a capped conduit, in an open one) all go deep: {rig['checks']['cable_in_rigid']['pairs_inside']}")
dp = {k.split(" x ")[0]: it["depth_m"] for k, it in ci.items()}
check(0.035 < dp["Cable_Thru_Inst"] < 0.046 and 0.014 < dp["Cable_In_Pipe"] < 0.016 and 0.013 < dp["Cable_Thru_Sign"] < 0.016,
      f"depths: the 4.5 cm duplicate's axis, 15 mm into the pipe, the middle of a 3 cm board: {dp}")
# a limit and a token pair in the rules file
rules_path = os.path.join(out, "cir_rules.yaml")
open(rules_path, "w").write("cable_rigid_depth_max_m: 0.02\noverlap_allow:\n  - [thru, board]\n")
rig2 = lint.run_lint(project=None, out_dir=os.path.join(out, "cir2"), only=["cable_in_rigid"], rules=rules_path)
check({it["object"] for it in rig2["checks"]["cable_in_rigid"]["items"]} == {"Cable_Thru_Inst x SM_Conduit_Straight_Inst", "Cable_Pass_J x SM_JunctionBox_B", "Cable_Cap_Exit x SM_Conduit_Straight_Cap2"},
      f"cable_rigid_depth_max_m 0.02 passes the 15 mm pipe case, overlap_allow clears the sign board: {[it['object'] for it in rig2['checks']['cable_in_rigid']['items']]}")
# the key of a cable_ends dead end ignores its reason: the end moves 1 cm into the wall and its text flips from "enters" to "buried"
box("SM_Wall_K", (-1, 5.0, 0), (1, 5.2, 2), "COL_P3_Services")
box("SM_JunctionBox_K", (-0.1, 4.5, 0.9), (0.1, 4.6, 1.1), "COL_P3_Services")
tube("Cable_Key", path((0, 4.6, 1.0), (0, 5.0, 1.0), n=6))
k1 = lint.run_lint(project=None, out_dir=os.path.join(out, "key1"), only=["cable_ends"])
tube("Cable_Key2", path((0, 4.6, 1.0), (0, 5.01, 1.0), n=6))
bpy.data.objects.remove(bpy.data.objects["Cable_Key"])
bpy.data.objects["Cable_Key2"].name = "Cable_Key"
k2 = lint.run_lint(project=None, out_dir=os.path.join(out, "key2"), only=["cable_ends"], baseline=os.path.join(out, "key1", "lint.json"))
d1 = [it for it in k1["checks"]["cable_ends"]["items"] if it["object"] == "Cable_Key"]
d2 = [it for it in k2["checks"]["cable_ends"]["items"] if it["object"] == "Cable_Key"]
check(len(d1) == len(d2) == 1 and d1[0]["reason"].startswith("enters") and d2[0]["reason"].startswith("buried") and d1[0]["end"] == d2[0]["end"], f"the end changes its reason: {d1} {d2}")
check(k2["new"] == {} and k2["baseline"]["gone"] == 0, f"a dead end whose reason flips is the same end, not new: {k2['new']}")
moved = dict(d1[0], what="dead end: tail along SM_Wall_K", at=[d1[0]["at"][0] + 0.002, d1[0]["at"][1] - 0.003, d1[0]["at"][2]])
check(lint.item_key(d1[0]) == lint.item_key(moved) and lint.item_key(d1[0]) != lint.item_key(dict(moved, end=d1[0]["end"] + 1)), "item_key: same cable, end number and position to 0.1 m")
older = json.load(open(os.path.join(out, "key1", "lint.json")))
for it in older["checks"]["cable_ends"]["items"]:
    it.pop("end", None)   # a lint.json from before the end number: readable, and its dead ends read as new and gone once
json.dump(older, open(os.path.join(out, "key_old.json"), "w"))
k3 = lint.run_lint(project=None, out_dir=os.path.join(out, "key3"), only=["cable_ends"], baseline=os.path.join(out, "key_old.json"))
check(k3["baseline"]["gone"] >= 1 and len(k3["new"]["cable_ends"]) == len(k2["checks"]["cable_ends"]["items"]), f"an older baseline reads as new and gone once: {k3['baseline']}")

# the yaml subset reader
y = lib.parse_yaml("a: 1\nb: [x, y]\nc:\n  d: true\n  e:\n    - p\n    - q\nf: 'z' # note\n")
check(y == {"a": 1, "b": ["x", "y"], "c": {"d": True, "e": ["p", "q"]}, "f": "z"}, f"yaml subset: {y}")
print("SCENE-LINT SELFTEST", "FAILED" if fails else "OK", f"({len(C)} checks, {rep['seconds']} s)")
sys.exit(1 if fails else 0)
