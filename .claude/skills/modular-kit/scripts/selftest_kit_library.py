"""Self-test for kit_library.py. Headless, builds a tiny synthetic scene and assets in a temp folder, never touches a project:

    bash bin/blender-bg --python .claude/skills/modular-kit/scripts/selftest_kit_library.py

Scene: an instance family with transforms, custom properties, a modifier and a master in a parked collection; a second family
that stays untouched; a one-off; a pipe run family (skipped); a mesh that a built asset maps to. Assets: that piece (with a collision
proxy, a socket and a variant) and a pilot that is not in the scene. Then: build, edit the library (shrink a knob; shift one piece's
origin and give it a new material), sync dry run (reports, changes nothing), sync apply (transforms, names, properties, modifiers and
the scene's own materials kept, only the edited pieces swapped, the origin warning, the new material listed), and a second sync
that finds nothing to do.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_library as kl  # noqa: E402

SCRIPT = os.path.join(HERE, "kit_library.py")
FAILS = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def blender(args, blend=None):
    cmd = [bpy.app.binary_path, "--background", "--factory-startup"] + ([blend] if blend else []) + ["--python", SCRIPT, "--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_py(code, blend=None):
    fd, path = tempfile.mkstemp(suffix=".py")
    os.write(fd, code.encode())
    os.close(fd)
    cmd = [bpy.app.binary_path, "--background", "--factory-startup"] + ([blend] if blend else []) + ["--python", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(path)
    if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
        print(r.stdout[-1500:], r.stderr[-1500:])
        raise RuntimeError("helper script failed")


def mat(name, color, marker=None):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    if marker is not None:
        m["scene_marker"] = marker
    return m


def knob_mesh(name, mats):
    """A flat base (slot 0) with a knob on top (slot 1)."""
    def box(x0, x1, y0, y1, z0, z1, i0):
        v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return v, [tuple(i + i0 for i in q) for q in f]
    v1, f1 = box(-0.05, 0.05, -0.05, 0.05, 0.0, 0.02, 0)
    v2, f2 = box(-0.02, 0.02, -0.02, 0.02, 0.02, 0.04, 8)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v1 + v2, [], f1 + f2)
    for m in mats:
        me.materials.append(m)
    for i, p in enumerate(me.polygons):
        p.material_index = 0 if i < 6 else max(0, min(1, len(mats) - 1))
    uv = me.uv_layers.new(name="UVMap")
    for lp in me.loops:
        uv.uv[lp.index].vector = me.vertices[lp.vertex_index].co.xy
    me.update()
    return me


def build_assets_and_scene(root):
    assets = os.path.join(root, "assets")
    for piece, extra in (("SM_Test", True), ("SM_Pilot", False)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ma, mb = mat("M_A", (0, 1, 0, 1)), mat("M_B", (0, 0, 1, 1))
        col = bpy.data.collections.new("COL_Kit")
        bpy.context.scene.collection.children.link(col)
        master = bpy.data.objects.new(piece, knob_mesh(piece, [ma, mb]))
        col.objects.link(master)
        if extra:
            ucx = bpy.data.objects.new("UCX_%s_01" % piece, knob_mesh("UCX_%s_01" % piece, []))
            ucx.hide_render = True
            sock = bpy.data.objects.new("SOCKET_top", None)
            sock.parent = master
            sock.location = (0, 0, 0.04)
            var = bpy.data.objects.new(piece + "_Open", knob_mesh(piece + "_Open", [ma, mb]))
            for o in (ucx, sock, var):
                col.objects.link(o)
        d = os.path.join(assets, piece)
        os.makedirs(d)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, piece + ".blend"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ma, mb = mat("M_A", (1, 0, 0, 1), marker=7), mat("M_B", (0, 0, 1, 1))
    masters = bpy.data.collections.new("Masters")
    props = bpy.data.collections.new("Props")
    for c in (masters, props):
        bpy.context.scene.collection.children.link(c)

    def inst(name, me, col, loc, rot=0.0, scale=1.0):
        o = bpy.data.objects.new(name, me)
        o.location, o.rotation_euler.z, o.scale = loc, rot, (scale,) * 3
        col.objects.link(o)
        return o
    fam, other, test = knob_mesh("FAM_Knob", [ma, mb]), knob_mesh("FAM_Other", [ma, mb]), knob_mesh("SM_Test", [ma, mb])
    inst("FAM_Knob", fam, masters, (0, 0, 0))
    a = inst("Knob_a", fam, props, (1, 2, 3), 0.5)
    a["tag"] = "alpha"
    a.modifiers.new("Bev", 'BEVEL')
    inst("Knob_b", fam, props, (4, 5, 6), 1.0, 2.0)["tag"] = "beta"
    inst("Knob_c", fam, props, (7, 8, 9))
    inst("Other_a", other, props, (10, 0, 0))
    inst("Other_b", other, props, (11, 0, 0))
    inst("Wall_01", knob_mesh("Wall_01", [ma]), props, (0, 20, 0))
    run = knob_mesh("SM_Pipe_Run_X", [ma])
    inst("SM_Pipe_Run_X", run, props, (0, 30, 0))
    inst("SM_Pipe_Run_X.001", run, props, (1, 30, 0))
    inst("Test_a", test, props, (20, 0, 0), 1.0)
    inst("Test_b", test, props, (21, 0, 0))
    bpy.context.view_layer.layer_collection.children["Masters"].exclude = True
    scene = os.path.join(root, "scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=scene)
    return scene, assets


EDIT = r'''
import bpy
from mathutils import Vector
for o in bpy.data.objects:
    if o.name == "FAM_Knob":   # shrink the knob in plan, inside the base footprint, same bbox
        for v in o.data.vertices:
            if v.co.z > 0.0201:
                v.co.x *= 0.5; v.co.y *= 0.5
    if o.name == "SM_Test":    # move the origin by 5 mm and add a new material
        for v in o.data.vertices:
            v.co.x += 0.005
        nm = bpy.data.materials.new("M_New")
        o.data.materials.append(nm)
        o.data.polygons[0].material_index = 2
bpy.ops.wm.save_mainfile()
'''

PROBE = r'''
import bpy, json, sys
sys.path.insert(0, %r)
import kit_library as kl
out = {"meshes": {}, "objects": {}, "materials": sorted(m.name for m in bpy.data.materials), "marker": bpy.data.materials["M_A"].get("scene_marker")}
for m in bpy.data.meshes:
    out["meshes"][m.name] = [kl.mesh_info(m)["hash"], m.users, [x.name if x else None for x in m.materials]]
for o in bpy.data.objects:
    out["objects"][o.name] = [o.data.name if o.data else None, [round(v, 5) for v in o.location], round(o.rotation_euler.z, 5),
                              [round(v, 5) for v in o.scale], o.get("tag"), [m.type for m in o.modifiers]]
json.dump(out, open(%r, "w"))
'''


def probe(blend, root, tag):
    out = os.path.join(root, "probe_%s.json" % tag)
    run_py(PROBE % (HERE, out), blend)
    with open(out) as f:
        return json.load(f)


def main():
    root = tempfile.mkdtemp(prefix="kit_library_selftest_")
    scene, assets = build_assets_and_scene(root)
    lib = os.path.join(root, "lib", "Kit.blend")
    man = lib + ".manifest.json"

    code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
    check(code == 0 and os.path.isfile(lib) and os.path.isfile(man), "build exits 0 and writes the library and the manifest")
    if code != 0:
        print(out[-2000:])
        return 1
    m = json.load(open(man))["pieces"]
    check(set(m) == {"FAM_Knob", "FAM_Other", "SM_Test", "SM_Pilot"}, "pieces: two families, a mapped asset, a pilot (got %s)" % sorted(m))
    check(m["FAM_Knob"]["source"] == "scene_family" and m["FAM_Knob"]["members"]["FAM_Knob"]["scene_rendered"] == 3
          and m["FAM_Knob"]["members"]["FAM_Knob"]["scene_objects"] == 4, "family counts: 3 rendered, 4 with the parked master")
    check(m["SM_Test"]["source"] == "asset" and m["SM_Test"]["members"]["SM_Test"]["scene_meshes"] == ["SM_Test"]
          and m["SM_Test"]["members"]["UCX_SM_Test_01"]["role"] == "collision" and m["SM_Test"]["members"]["SM_Test_Open"]["role"] == "variant"
          and m["SM_Test"]["members"]["SOCKET_top"]["role"] == "socket", "asset piece maps to its scene mesh and keeps proxy, socket and variant")
    check(m["SM_Pilot"]["in_scene"] is False and "not placed" in m["SM_Pilot"]["note"], "a pilot that is not in the scene says so")
    check(m["FAM_Knob"]["members"]["FAM_Knob"]["scene_hash_match"], "the library copy matches the scene mesh")

    # a second build keeps everything and changes no hash
    h1 = open(man).read()
    code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
    check(code == 0 and json.load(open(man))["pieces"] == json.loads(h1)["pieces"], "re-running build is safe: pieces and hashes unchanged")

    # the library has assets and labels
    run_py(r'''
import bpy
a = [o.name for o in bpy.data.objects if o.asset_data]
assert set(a) == {"FAM_Knob", "FAM_Other", "SM_Test", "SM_Test_Open", "SM_Pilot"}, a
assert all("spec:" + o.name.replace("_Open", "") in o.asset_data.tags for o in bpy.data.objects if o.asset_data)
assert {"LBL_FAM_Knob", "LBL_SM_Pilot"} <= {o.name for o in bpy.data.objects}
assert len(bpy.data.collections) == 4
assert sorted(m.name for m in bpy.data.materials) == ["M_A", "M_B"], [m.name for m in bpy.data.materials]
''', lib)
    check(True, "library: masters and the variant are assets with a spec tag, labels exist, one collection per piece, materials not duplicated")

    run_py(EDIT, lib)
    before = probe(scene, root, "before")
    report = os.path.join(root, "dry.json")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--report", report], blend=scene)
    check(code == 0, "dry run exits 0")
    rep = json.load(open(report))
    rows = {r["piece"]: r for r in rep["pieces"]}
    check(set(rows) == {"FAM_Knob", "SM_Test"}, "dry run lists only the two edited pieces (got %s)" % sorted(rows))
    check(rows["FAM_Knob"]["status"] == "would_swap" and rows["FAM_Knob"]["objects"] == 4 and not rows["FAM_Knob"]["warnings"],
          "knob family: 4 objects, no warning (bbox unchanged)")
    check(rows["FAM_Knob"]["tris_before"] == rows["FAM_Knob"]["tris_after"] == 24, "tris before and after reported")
    check(any("origin moved" in w for w in rows["SM_Test"]["warnings"]) and rows["SM_Test"]["worst_mm"] > 4.9, "the 5 mm origin move warns")
    check(rows["SM_Test"]["new_materials"] == ["M_New"], "the new material is listed")
    check(json.load(open(man))["pieces"] == json.loads(h1)["pieces"], "dry run leaves the manifest alone")

    synced = os.path.join(root, "scene_synced.blend")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--apply", "--report", os.path.join(root, "apply.json"), "--save-as", synced], blend=scene)
    check(code == 0 and os.path.isfile(synced), "apply exits 0 and the caller's save is written")
    after = probe(synced, root, "after")
    check(before["objects"].keys() == after["objects"].keys(), "same object names")
    for n, row in before["objects"].items():
        a = after["objects"][n]
        check(row[1:] == a[1:], "%s keeps transform, tag and modifiers" % n) if n.startswith(("Knob", "Test", "Other")) else None
        check(row[0] == a[0], "%s keeps its mesh datablock name (%s)" % (n, a[0])) if n.startswith(("Knob", "Test", "Other", "FAM")) else None
    check(after["marker"] == 7 and after["materials"] == ["M_A", "M_B", "M_New", ], "scene materials kept (marker survives), no .001 copies, only M_New added: %s" % after["materials"])
    check(after["meshes"]["FAM_Knob"][0] != before["meshes"]["FAM_Knob"][0] and after["meshes"]["FAM_Knob"][2] == ["M_A", "M_B"],
          "knob family changed and points at the scene's materials")
    check(after["meshes"]["FAM_Other"] == before["meshes"]["FAM_Other"], "the untouched family is not swapped")
    check(after["meshes"]["SM_Test"][2] == ["M_A", "M_B", "M_New"], "asset piece got the new slot")
    lib_hash = json.load(open(man))["pieces"]["FAM_Knob"]["members"]["FAM_Knob"]["hash"]
    check(after["meshes"]["FAM_Knob"][0] == lib_hash, "the swapped mesh hashes like the library piece, and the manifest holds it")
    check(after["meshes"]["FAM_Knob"][1] == 4, "all 4 objects use the new mesh")

    report2 = os.path.join(root, "again.json")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--apply", "--report", report2], blend=synced)
    rep2 = json.load(open(report2))
    check(code == 0 and rep2["summary"]["pieces_changed"] == 0, "a second sync is a no-op")
    if not FAILS:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print("selftest folder kept:", root)
    print("KIT_LIBRARY_SELFTEST", "FAIL %d" % len(FAILS) if FAILS else "PASS")
    return 1 if FAILS else 0


if any(os.path.basename(a) == "selftest_kit_library.py" for a in sys.argv):
    try:
        code = main()
    except Exception as e:   # Blender exits 0 after an exception under --python
        import traceback
        traceback.print_exc()
        print("KIT_LIBRARY_SELFTEST ERROR:", repr(e))
        code = 1
    sys.exit(code)
