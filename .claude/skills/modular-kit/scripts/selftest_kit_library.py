"""Self-test for kit_library.py. Headless, builds a tiny synthetic scene and assets in a temp folder, never touches a project:

    bash bin/blender-bg --python .claude/skills/modular-kit/scripts/selftest_kit_library.py

Scene: an instance family with transforms, custom properties, a modifier and a master in a parked collection; a second family
that stays untouched; a third that the user will empty; a one-off; a pipe run family (skipped); a mesh that a built asset maps to.
Assets: that piece (with a collision proxy, a socket and a variant, which is a piece of its own) and a pilot that is not in the scene.
Then: build (sections, one collection per piece, no text objects, a build re-run keeps the user's edits), edit the library (add an
object to one piece and rename its master; add a visible and a hidden object to another and delete its master; empty a third;
delete the variant's collection), sync dry run (reports, changes nothing, no backups), apply without a backup (refused), apply with
one (transforms, names, properties, modifiers and the scene's own materials kept, collision not joined, backups written, emptied and
deleted collections reported and not applied), a second sync that finds nothing, and the undo through the first library copy.
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
    for piece, extra in (("SM_Test", True), ("SM_Lamp_Pilot", False)):
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
    third = knob_mesh("FAM_Third", [ma, mb])
    inst("FAM_Knob", fam, masters, (0, 0, 0))
    a = inst("Knob_a", fam, props, (1, 2, 3), 0.5)
    a["tag"] = "alpha"
    a.modifiers.new("Bev", 'BEVEL')
    inst("Knob_b", fam, props, (4, 5, 6), 1.0, 2.0)["tag"] = "beta"
    inst("Knob_c", fam, props, (7, 8, 9))
    inst("Other_a", other, props, (10, 0, 0))
    inst("Other_b", other, props, (11, 0, 0))
    inst("Third_a", third, props, (12, 0, 0))
    inst("Third_b", third, props, (13, 0, 0))
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

def cube(name, mats):
    v = [(x, y, z) for x in (-.05, .05) for y in (-.05, .05) for z in (0, .1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    for m in mats:
        me.materials.append(m)
    if len(mats) > 1:
        me.polygons[0].material_index = 1
    me.update()
    return me

def add(colname, name, dx, mats, hide=False):
    col = bpy.data.collections[colname]
    ob = bpy.data.objects.new(name, cube(name, mats))
    ob.location = Vector(col.instance_offset) + Vector((dx, 0, 0))
    ob.hide_render = hide
    col.objects.link(ob)

mats = bpy.data.materials
for o in bpy.data.collections["FAM_Knob"].objects:      # a renamed master changes nothing
    o.name = "Renamed_knob"
add("FAM_Knob", "Knob_Extra", 0.2, [])   # no material, like a cube added by hand
add("SM_Test", "Extra_A", 0.1, [mats["M_A"], bpy.data.materials.new("M_New")])
add("SM_Test", "Extra_B", -0.3, [mats["M_A"]], hide=True)   # hidden: stays out
bpy.data.objects.remove(bpy.data.objects["SM_Test"])        # the old master is deleted; the UCX proxy stays but is not joined
for o in list(bpy.data.collections["FAM_Other"].objects):   # emptied: refused
    bpy.data.objects.remove(o)
bpy.data.collections.remove(bpy.data.collections["SM_Test_Open"])   # deleted: reported
bpy.ops.wm.save_mainfile()
'''

STRUCTURE = r'''
import bpy
c = bpy.data.collections
secs = {s.name: sorted(x.name for x in s.children) for s in bpy.context.scene.collection.children}
assert secs == {"Props": ["FAM_Knob", "FAM_Other", "FAM_Third", "SM_Test", "SM_Test_Open"], "Lamps": ["SM_Lamp_Pilot"]}, secs
assert not [o for o in bpy.data.objects if o.type == 'FONT'], "text objects in the library"
assert sorted(o.name for o in c["SM_Test"].objects) == ["SM_Test", "SOCKET_top", "UCX_SM_Test_01"], [o.name for o in c["SM_Test"].objects]
assert [o.name for o in c["SM_Test_Open"].objects] == ["SM_Test_Open"]
assert all(c[n].asset_data and ("spec:" + n) in c[n].asset_data.tags for n in ("FAM_Knob", "SM_Test", "SM_Lamp_Pilot"))
assert all((c[o.name].instance_offset - o.location).length < 1e-5 for o in bpy.data.objects if o.type == 'MESH' and o.name in c)
assert len(bpy.data.collections) == 8, len(bpy.data.collections)
assert sorted(m.name for m in bpy.data.materials) == ["M_A", "M_B"], [m.name for m in bpy.data.materials]
'''

PROBE = r'''
import bpy, json, sys
sys.path.insert(0, %r)
import kit_library as kl
out = {"meshes": {}, "objects": {}, "materials": sorted(m.name for m in bpy.data.materials), "marker": bpy.data.materials["M_A"].get("scene_marker")}
for m in bpy.data.meshes:
    i = kl.mesh_info(m)
    out["meshes"][m.name] = [i["hash"], m.users, [x.name if x else None for x in m.materials], i["tris"], i["bbox_m"]]
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


def backups(lib):
    d = os.path.splitext(lib)[0] + "_backups"
    return sorted(f for f in os.listdir(d) if f.endswith(".blend")) if os.path.isdir(d) else []


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
    check(set(m) == {"FAM_Knob", "FAM_Other", "FAM_Third", "SM_Test", "SM_Test_Open", "SM_Lamp_Pilot"}, "pieces: three families, an asset, its variant, a pilot (got %s)" % sorted(m))
    check(m["SM_Lamp_Pilot"]["section"] == "Lamps" and m["FAM_Knob"]["section"] == "Props", "sections: a name in the table goes to its section, the rest to Props")
    check(m["FAM_Knob"]["source"] == "scene_family" and m["FAM_Knob"]["scene_rendered"] == 3 and m["FAM_Knob"]["scene_objects"] == 4,
          "family counts: 3 rendered, 4 with the parked master")
    check(m["SM_Test"]["scene_meshes"] == ["SM_Test"] and m["SM_Test_Open"]["scene_meshes"] == [] and not m["SM_Test_Open"]["in_scene"],
          "asset piece maps to its scene mesh; the variant is a piece of its own that is not placed")
    check(m["SM_Lamp_Pilot"]["in_scene"] is False and "not placed" in m["SM_Lamp_Pilot"]["note"], "a pilot that is not in the scene says so")
    check(m["FAM_Knob"]["scene_hash_match"], "the joined library piece matches the scene mesh")
    check(m["SM_Test"]["prev_hash"] is None and len(backups(lib)) == 1, "a fresh build keeps a first copy of the library")
    run_py(STRUCTURE, lib)
    check(True, "library: sections > piece collections, no text objects, collision and socket inside their piece, assets tagged, offset = piece origin, materials not duplicated")

    # a second build keeps everything and changes no hash
    h1 = open(man).read()
    code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
    check(code == 0 and json.load(open(man))["pieces"] == json.loads(h1)["pieces"], "re-running build is safe: pieces and hashes unchanged")

    run_py(EDIT, lib)
    code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
    run_py('import bpy; assert "Knob_Extra" in bpy.data.collections["FAM_Knob"].objects and "Extra_A" in bpy.data.collections["SM_Test"].objects', lib)
    check(code == 0, "build after the user's edits keeps them and adds nothing back")
    h1 = open(man).read()
    before = probe(scene, root, "before")
    nbk = len(backups(lib))
    report = os.path.join(root, "dry.json")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--report", report], blend=scene)
    check(code == 0, "dry run exits 0")
    rep = json.load(open(report))
    rows = {r["piece"]: r for r in rep["pieces"]}
    check(set(rows) == {"FAM_Knob", "SM_Test", "FAM_Other", "SM_Test_Open"}, "dry run lists the two edited pieces and the two refused ones (got %s)" % sorted(rows))
    check(rows["FAM_Knob"]["status"] == "would_swap" and rows["FAM_Knob"]["objects"] == 4 and rows["FAM_Knob"]["parts"] == ["Knob_Extra", "Renamed_knob"],
          "knob family: 4 scene objects, joined from the renamed master and the added object")
    check(any("Knob_Extra has no material" in w for w in rows["FAM_Knob"]["warnings"]), "an object added without a material is filled and warned about")
    check(rows["FAM_Knob"]["tris_before"] == 24 and rows["FAM_Knob"]["tris_after"] == 36, "tris before and after reported (24 -> 36)")
    check(rows["SM_Test"]["parts"] == ["Extra_A"] and rows["SM_Test"]["tris_after"] == 12, "hidden object and the collision proxy are not joined")
    check(rows["SM_Test"]["new_materials"] == ["M_New"], "the new material is listed")
    check(rows["FAM_Other"]["status"] == "empty_collection" and rows["SM_Test_Open"]["status"] == "missing_collection", "emptied and deleted collections are reported")
    check(json.load(open(man)) == json.loads(h1) and len(backups(lib)) == nbk, "dry run leaves the manifest alone and writes no library copy")

    synced = os.path.join(root, "scene_synced.blend")
    bk1 = os.path.join(root, "bk", "scene_bk1.blend")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--apply", "--save-as", synced], blend=scene)
    check(code != 0 and not os.path.isfile(synced) and len(backups(lib)) == nbk and json.load(open(man)) == json.loads(h1),
          "apply without --backup is refused and changes nothing")
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--apply", "--backup", bk1, "--report", os.path.join(root, "apply.json"), "--save-as", synced], blend=scene)
    check(code == 0 and os.path.isfile(synced) and os.path.isfile(bk1), "apply with a backup exits 0, saves the scene copy and the caller's save")
    check(len(backups(lib)) == nbk + 1 and os.path.isfile(os.path.join(os.path.splitext(lib)[0] + "_backups", backups(lib)[-1] + ".manifest.json")),
          "a timestamped library copy and its manifest are written before the swap")
    after = probe(synced, root, "after")
    check(before["objects"].keys() == after["objects"].keys(), "same object names")
    for n, row in before["objects"].items():
        a = after["objects"][n]
        if n.startswith(("Knob", "Test", "Other", "Third")):
            check(row[1:] == a[1:] and row[0] == a[0], "%s keeps mesh name, transform, tag and modifiers" % n)
    check(after["marker"] == 7 and after["materials"] == ["M_A", "M_B", "M_New"], "scene materials kept (marker survives), no .001 copies, only M_New added: %s" % after["materials"])
    k, t = after["meshes"]["FAM_Knob"], after["meshes"]["SM_Test"]
    check(k[3] == 36 and abs(k[4][1][0] - 0.25) < 1e-5 and k[2] == ["M_A", "M_B"] and k[1] == 4, "knob family: joined mesh, bbox to 0.25, the scene's material, all 4 objects use it (%s)" % k)
    check(t[3] == 12 and abs(t[4][0][0] - 0.05) < 1e-5 and abs(t[4][1][0] - 0.15) < 1e-5 and t[2] == ["M_A", "M_New"],
          "asset piece: only Extra_A at +0.1 m from the piece origin, new slot (%s)" % t)
    check(after["meshes"]["FAM_Other"] == before["meshes"]["FAM_Other"] and after["meshes"]["FAM_Third"] == before["meshes"]["FAM_Third"],
          "the emptied piece and the untouched one keep their scene meshes")
    mj = json.load(open(man))["pieces"]
    check(mj["FAM_Knob"]["prev_hash"] == json.loads(h1)["pieces"]["FAM_Knob"]["hash"] and mj["FAM_Knob"]["hash"] == k[0], "the manifest keeps the previous hash and holds the new one")

    bk2 = os.path.join(root, "bk", "scene_bk2.blend")
    report2 = os.path.join(root, "again.json")
    nbk = len(backups(lib))
    code, out = blender(["sync", "--library", lib, "--manifest", man, "--apply", "--backup", bk2, "--report", report2], blend=synced)
    rep2 = json.load(open(report2))
    check(code == 0 and rep2["summary"]["pieces_changed"] == 0 and not os.path.exists(bk2) and len(backups(lib)) == nbk, "a second sync is a no-op and writes no backups")

    first = os.path.join(os.path.splitext(lib)[0] + "_backups", backups(lib)[0])
    undone = os.path.join(root, "scene_undone.blend")
    code, out = blender(["sync", "--library", first, "--manifest", man, "--apply", "--backup", os.path.join(root, "bk", "scene_bk3.blend"), "--save-as", undone], blend=synced)
    back = probe(undone, root, "undone")
    check(code == 0 and back["meshes"]["FAM_Knob"][0] == before["meshes"]["FAM_Knob"][0] and back["meshes"]["SM_Test"][0] == before["meshes"]["SM_Test"][0],
          "syncing the first library copy swaps the previous meshes back")
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
