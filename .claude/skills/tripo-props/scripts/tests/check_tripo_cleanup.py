"""Headless self-check for tripo_cleanup.py. Fake Tripo imports go in; every expectation below is a literal number worked
out by hand from the spec triple [W, D, H], never read back from the script, so a swapped axis fails here.

    bash bin/blender-bg --python-exit-code 1 --python .claude/skills/tripo-props/scripts/tests/check_tripo_cleanup.py
    ... -- <path to a patched copy of tripo_cleanup.py>      # to prove the check fails on a bug

Cases: per-axis stretch with the one-time turn, the UCX box, M_/T_ names and the 1K cap, and a clean rerun; uniform scale
(exact fit, inside 8 %, a named governing axis, and the batch-stopping error beyond 8 %); tubes (vertical, horizontal,
oval refused); palette materials; the old (W, H, D) call refused.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and sys.argv.index("--") + 1 < len(sys.argv) else os.path.join(HERE, "..", "tripo_cleanup.py")
ns = {"__name__": "tripo_cleanup"}
exec(open(SRC, encoding="utf-8").read(), ns)
cleanup = ns["cleanup"]
bpy.ops.wm.read_factory_settings(use_empty=True)
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def textured(ob, name):
    mat = bpy.data.materials.new("tripo_mat_abc")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.new(name + "_basecolor", 2048, 2048)
    ob.data.materials.append(mat)


def make(name, build, loc=(3, 2, 1)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    textured(ob, name)
    return ob


def box(w, d, h):  # an axis-aligned box, w along X, d along Y, h along Z
    def build(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(w, d, h), verts=bm.verts)
    return build


def cylinder(dx, dy, length, axis):  # an elliptical tube, length along `axis`
    def build(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.5, radius2=0.5, depth=1.0)
        bmesh.ops.scale(bm, vec=(dx, dy, length), verts=bm.verts)
        if axis == "X":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    return build


def bbox(name):
    co = [v.co for v in bpy.data.objects[name].data.vertices]
    return [min(c[i] for c in co) for i in range(3)], [max(c[i] for c in co) for i in range(3)]


def expect_box(name, size, lo, tol=1e-4):
    mn, mx = bbox(name)
    got = [round(mx[i] - mn[i], 5) for i in range(3)]
    check(all(abs(got[i] - size[i]) <= tol for i in range(3)), f"{name}: size {got}, want {size}")
    check(all(abs(mn[i] - lo[i]) <= tol for i in range(3)), f"{name}: min corner {[round(v, 5) for v in mn]}, want {lo}")


def raises(fn, text, label):
    try:
        fn()
    except ValueError as e:
        check(text in str(e), f"{label}: wrong error: {e}")
    else:
        check(False, f"{label}: did not raise")


# 1. per-axis (the old behaviour, opt-in): a turned, offset, scaled cube is stretched to the spec's W x D x H.
#    Specs are [W, D, H] with D != H, so a swap shows. Hand-worked boxes and pivots:
for name in ("SM_Box_Wall", "SM_Box_Floor", "SM_Lamp_Hang"):
    ob = make(name, box(1, 1, 1))
    ob.scale, ob.rotation_euler = (0.5, 0.8, 0.3), (0, 0, 0.3)
props = {"SM_Box_Wall": ((0.30, 0.15, 0.40), "wall", True), "SM_Box_Floor": ((0.60, 0.40, 0.25), "floor", False),
         "SM_Lamp_Hang": ((0.20, 0.20, 0.30), "hang", False)}
for _ in range(2):  # the second run must change nothing
    cleanup(props, rot_z={"SM_Box_Floor": 90}, scale="per_axis")
expect_box("SM_Box_Wall", (0.30, 0.15, 0.40), (-0.15, -0.15, -0.20))   # back face on y = 0
expect_box("SM_Box_Floor", (0.60, 0.40, 0.25), (-0.30, -0.20, 0.0))
expect_box("SM_Lamp_Hang", (0.20, 0.20, 0.30), (-0.10, -0.10, -0.30))
for name, collide in (("SM_Box_Wall", True), ("SM_Box_Floor", False), ("SM_Lamp_Hang", False)):
    ob = bpy.data.objects[name]
    check(ob.active_material.name == "M_" + name[3:] and max(bpy.data.images["T_" + name[3:] + "_BC"].size) == 1024,
          f"{name}: material or texture names, or texture size")
    check(bool(bpy.data.objects.get("UCX_" + name + "_01")) == collide and not bpy.data.objects.get("UCX_" + name), f"{name}: UCX {'missing' if collide else 'unexpected'}")
    check(ob.users_collection[0].name == ns["MASTERS"], f"{name}: not in {ns['MASTERS']}")
ucx = bbox("UCX_SM_Box_Wall_01")
check(abs(ucx[1][2] - ucx[0][2] - 0.40) < 1e-4 and abs(ucx[1][1] - ucx[0][1] - 0.15) < 1e-4, "UCX box does not match the wall prop")

# 2. uniform (the default): a 0.2 x 0.1 x 0.5 box against the spec [0.4, 0.2, 1.0] is exactly x2. Under a W, H, D reading
#    Y would become 1.0 and Z 0.2.
make("SM_Fit", box(0.2, 0.1, 0.5))
for _ in range(2):
    cleanup({"SM_Fit": ((0.4, 0.2, 1.0), "floor", False)})
expect_box("SM_Fit", (0.4, 0.2, 1.0), (-0.2, -0.1, 0.0))
make("SM_Turned", box(0.1, 0.2, 0.5))   # the one-time turn comes first: 0.1 x 0.2 becomes 0.2 x 0.1
cleanup({"SM_Turned": ((0.4, 0.2, 1.0), "wall", False)}, rot_z={"SM_Turned": 90})
expect_box("SM_Turned", (0.4, 0.2, 1.0), (-0.2, -0.2, -0.5))

# 3. inside 8 %: factors 2, 2, 2.1. The default governing axis is H (the largest spec size), so the factor is 2.1; with
#    "governing": "W" it is 2.0.
make("SM_Gov_H", box(0.2, 0.1, 0.5))
make("SM_Gov_W", box(0.2, 0.1, 0.5))
cleanup({"SM_Gov_H": ((0.4, 0.2, 1.05), "floor", False), "SM_Gov_W": ((0.4, 0.2, 1.05), "floor", False, {"governing": "W"})})
expect_box("SM_Gov_H", (0.42, 0.21, 1.05), (-0.21, -0.105, 0.0))
expect_box("SM_Gov_W", (0.40, 0.20, 1.00), (-0.20, -0.10, 0.0))

# 4. beyond 8 %: factors 2, 2, 1.6 raise, and a bad prop in a batch stops the good one too, with no change to the scene
make("SM_Good", box(0.2, 0.1, 0.5), loc=(5, 5, 5))
make("SM_Bad", box(0.2, 0.1, 0.5), loc=(6, 6, 6))
good_co = [tuple(v.co) for v in bpy.data.objects["SM_Good"].data.vertices]
raises(lambda: cleanup({"SM_Good": ((0.4, 0.2, 1.0), "floor", False), "SM_Bad": ((0.4, 0.2, 0.8), "floor", False)}), "8 %", "uniform beyond 8 %")
for n, loc in (("SM_Good", (5, 5, 5)), ("SM_Bad", (6, 6, 6))):
    ob = bpy.data.objects[n]
    check(not ob.get("tripo_prop") and tuple(ob.location) == loc, f"{n}: changed by an aborted batch")
check([tuple(v.co) for v in bpy.data.objects["SM_Good"].data.vertices] == good_co, "SM_Good: mesh changed by an aborted batch")
cleanup({"SM_Bad": ((0.4, 0.2, 0.8), "floor", False)}, scale="per_axis")   # the opt-in still stretches it
expect_box("SM_Bad", (0.4, 0.2, 0.8), (-0.2, -0.1, 0.0))

# 5. tubes: a 0.10 m diameter, 1.0 m long generated tube against a 0.045 m conduit. s = 0.45 whatever the spec's length.
make("SM_Pipe_V", cylinder(0.10, 0.10, 1.0, "Z"))
make("SM_Pipe_H", cylinder(0.10, 0.10, 1.0, "X"))
cleanup({"SM_Pipe_V": ((0.045, 0.045, 0.45), "floor", False, {"kind": "tube", "diameter_m": 0.045}),
         "SM_Pipe_H": ((0.45, 0.045, 0.045), "wall", False, {"kind": "tube"})})   # axis = the longest spec size (W); diameter from the spec
expect_box("SM_Pipe_V", (0.045, 0.045, 0.45), (-0.0225, -0.0225, 0.0), tol=6e-4)  # a 48-gon is a hair under the circle
expect_box("SM_Pipe_H", (0.45, 0.045, 0.045), (-0.225, -0.045, -0.0225), tol=6e-4)
# an oval tube (0.10 x 0.138 m, like a 0.045 x 0.062 conduit) is refused rather than stretched round
make("SM_Pipe_Oval", cylinder(0.10, 0.138, 1.0, "Z"))
raises(lambda: cleanup({"SM_Pipe_Oval": ((0.045, 0.045, 0.45), "floor", False, {"kind": "tube", "diameter_m": 0.045})}), "oval", "oval tube")
check(not bpy.data.objects["SM_Pipe_Oval"].get("tripo_prop"), "SM_Pipe_Oval: changed by the refusal")

# 6. palette materials: no textures, no atlas; one flat M_<material_group>, shared by props of the group
for n in ("SM_Pal_A", "SM_Pal_B", "SM_Pal_C"):
    make(n, box(0.2, 0.1, 0.5))
images_before = {i.name for i in bpy.data.images}
cleanup({"SM_Pal_A": ((0.4, 0.2, 1.0), "floor", False, {"material_group": "conduit"}),
         "SM_Pal_B": ((0.4, 0.2, 1.0), "floor", False, {"material_group": ["conduit"]}),
         "SM_Pal_C": ((0.4, 0.2, 1.0), "floor", False, {"material_group": "box_metal"})}, materials="palette")
for n, grp in (("SM_Pal_A", "conduit"), ("SM_Pal_B", "conduit"), ("SM_Pal_C", "box_metal")):
    ob = bpy.data.objects[n]
    mats = [s.material for s in ob.material_slots]
    check(len(mats) == 1 and mats[0].name == "M_" + grp and mats[0].get("material_group") == grp, f"{n}: material {[m.name for m in mats]}")
    check(not any(nd.type == "TEX_IMAGE" for nd in mats[0].node_tree.nodes), f"{n}: palette material has an image node")
    check(any(nd.type == "BSDF_PRINCIPLED" for nd in mats[0].node_tree.nodes), f"{n}: palette material has no Principled node")
check(bpy.data.objects["SM_Pal_A"].active_material is bpy.data.objects["SM_Pal_B"].active_material, "one group, two materials")
check(not [m.name for m in bpy.data.materials if m.users == 0], "palette mode left orphan materials behind")
check(not any(i.name.startswith(("SM_Pal_A", "SM_Pal_B", "SM_Pal_C")) for i in bpy.data.images), "palette mode left the Tripo images behind")
check(not any(i.name.startswith("T_Pal_") for i in bpy.data.images), "palette mode made textures")
make("SM_Pal_D", box(0.2, 0.1, 0.5))
raises(lambda: cleanup({"SM_Pal_D": ((0.4, 0.2, 1.0), "floor", False)}, materials="palette"), "material_group", "palette without a group")

# 7. the old (W, H, D, mount, collide) call raises instead of swapping D and H
make("SM_Old", box(0.2, 0.1, 0.5))
raises(lambda: cleanup({"SM_Old": (0.4, 1.0, 0.2, "floor", False)}), "old (W, H, D", "old call")
raises(lambda: cleanup({"SM_Old": ((0.4, 0.2, 1.0), "floor", False, {"governng": "H"})}), "unknown opts", "typo in opts")

print("FAIL:\n" + "\n".join(fails) if fails else "check_tripo_cleanup: all checks passed")
if fails:
    raise SystemExit(1)
