"""Headless self-check for tripo_cleanup.py: fake Tripo imports (a turned, offset, scaled cube with a 2K image) go in,
and each master must come out at the spec size, with its pivot by mount, renamed material and textures, a UCX box
and the one-time turn applied once.

    bash bin/blender-bg --python .claude/skills/tripo-props/scripts/tests/check_tripo_cleanup.py
"""
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ns = {"__name__": "tripo_cleanup"}
exec(open(os.path.join(HERE, "..", "tripo_cleanup.py"), encoding="utf-8").read(), ns)
bpy.ops.wm.read_factory_settings(use_empty=True)


def fake(name):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3, 2, 1), rotation=(0, 0, 0.3), scale=(0.5, 0.8, 0.3))
    ob = bpy.context.object
    ob.name = name
    mat = bpy.data.materials.new("tripo_mat_abc")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.new(name + "_basecolor", 2048, 2048)
    ob.data.materials.append(mat)
    return ob


fails = []
for name in ("SM_Box_Wall", "SM_Box_Floor", "SM_Lamp_Hang"):
    fake(name)
props = {"SM_Box_Wall": (0.30, 0.40, 0.15, "wall", True), "SM_Box_Floor": (0.60, 0.25, 0.40, "floor", False),
         "SM_Lamp_Hang": (0.20, 0.30, 0.20, "hang", False)}
for _ in range(2):  # the second run must change nothing
    ns["cleanup"](props, rot_z={"SM_Box_Floor": 90})

for name, (W, H, D, mount, collide) in props.items():
    ob = bpy.data.objects[name]
    co = [v.co for v in ob.data.vertices]
    mn = [min(c[i] for c in co) for i in range(3)]
    mx = [max(c[i] for c in co) for i in range(3)]
    want_min = {"wall": (-W / 2, -D, -H / 2), "floor": (-W / 2, -D / 2, 0), "hang": (-W / 2, -D / 2, -H)}[mount]
    if any(abs(a - b) > 1e-4 for a, b in zip(mn, want_min)) or abs(mx[0] - mn[0] - W) > 1e-4:
        fails.append(f"{name}: bbox {mn} .. {mx}")
    if ob.active_material.name != "M_" + name[3:] or max(bpy.data.images["T_" + name[3:] + "_BC"].size) != 1024:
        fails.append(f"{name}: material or texture names, or texture size")
    if bool(bpy.data.objects.get("UCX_" + name)) != collide:
        fails.append(f"{name}: UCX {'missing' if collide else 'unexpected'}")
    if ob.users_collection[0].name != ns["MASTERS"]:
        fails.append(f"{name}: not in {ns['MASTERS']}")
print("FAIL:\n" + "\n".join(fails) if fails else "check_tripo_cleanup: all checks passed")
if fails:
    raise SystemExit(1)
