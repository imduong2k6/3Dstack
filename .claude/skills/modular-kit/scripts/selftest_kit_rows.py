"""Self-test for kit_library.py join-rows. Headless, a small synthetic scene, assets and rows file in a temp folder, no project data:

    bash bin/blender-bg --python .claude/skills/modular-kit/scripts/selftest_kit_rows.py

Scene: gate objects (two of them use a mesh named like an asset, but older), a host wall and a hidden copy of it, a camera, a light in an excluded
collection, a custom exposure. Assets: a box with two materials, a plate, a piece with no UV map. The library is built with `build`.
Rows: adds with a rotation and a scale, a slot override, an override with a material that does not exist, a gate claimed by two lanes, rows that must be
skipped (not placed, superseded, not in the library, at the origin), gate objects to hide (one of them missing from the file), host cuts on a shown and
on a hidden object, gate names that are new pieces, own row ids and a bad one.
Checks: the dry run changes nothing and lists the plan; apply without a backup is refused; apply puts every row where it says, one mesh per master,
overrides as per-object slots, no empty slot or .001 material, gate objects hidden (never deleted) once, the older gate meshes swapped, only a shown
host is cut (and can be restored), cameras, lights, render and view settings and collection exclusion untouched; a rerun changes nothing; --skip-lanes
leaves the gate objects only the skipped lane replaces; --skip-no-uv; a user edit in the library reaches the placed objects and a build re-run keeps it.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
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


def mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    return m


def box(name, mats, uv=True, s=0.1, extra=0.0):
    v = [(x, y, z) for x in (-s, s) for y in (-s, s) for z in (0, 2 * s + extra)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    for m in mats:
        me.materials.append(m)
    if len(mats) > 1:
        me.polygons[0].material_index = 1
    if uv:
        layer = me.uv_layers.new(name="UVMap")
        for lp in me.loops:
            layer.uv[lp.index].vector = me.vertices[lp.vertex_index].co.xy
    me.update()
    return me


def wall(name):
    """Two quads on the plane y = -1 (x 0 to 2) and one quad at y = 0."""
    v = [(0, -1, 0), (1, -1, 0), (1, -1, 1), (0, -1, 1), (2, -1, 0), (2, -1, 1), (0, 0, 0), (2, 0, 0), (2, 0, 1), (0, 0, 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], [(0, 1, 2, 3), (1, 4, 5, 2), (6, 7, 8, 9)])
    me.materials.append(bpy.data.materials["M_A"])
    me.update()
    return me


def build_world(root):
    assets = os.path.join(root, "assets")
    for piece, mats, uv in (("SM_Box", ("M_A", "M_B"), True), ("SM_Plate", ("M_A",), True), ("SM_NoUV", ("M_A",), False)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ms = [mat(n, (0.1, 0.5, 0.2, 1)) for n in mats]
        col = bpy.data.collections.new("COL_Kit")
        bpy.context.scene.collection.children.link(col)
        col.objects.link(bpy.data.objects.new(piece, box(piece, ms, uv)))
        d = os.path.join(assets, piece)
        os.makedirs(d)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, piece + ".blend"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ma, mo = mat("M_A", (1, 0, 0, 1)), mat("M_Over", (0, 0, 1, 1))
    mo.use_fake_user = True   # in the scene file, though no object uses it
    props, lights = bpy.data.collections.new("Props"), bpy.data.collections.new("Lights_Off")
    for c in (props, lights):
        sc.collection.children.link(c)

    def put(name, me, col, loc=(0, 0, 0)):
        o = bpy.data.objects.new(name, me)
        o.location = loc
        col.objects.link(o)
        return o
    for n in ("Gate_A", "Gate_B", "Gate_C", "Gate_Keep"):
        put(n, box("G_" + n, [ma]), props, (20, 0, 0))
    old = box("SM_Box", [ma], s=0.2)   # older than the asset's: hash differs, so rows mode swaps it
    put("Box_g1", old, props, (30, 0, 0))
    put("Box_g2", old, props, (31, 0, 0))
    put("Plate_g", box("SM_Plate", [ma], s=0.3), props, (32, 0, 0))   # named like an asset the rows file does not list: stays
    put("HostWall", wall("HostWall"), props)
    put("HostHidden", wall("HostHidden"), props)
    cam = bpy.data.objects.new("CAM_T", bpy.data.cameras.new("CAM_T"))
    cam.location = (0, -10, 2)
    props.objects.link(cam)
    sc.camera = cam
    lamp = bpy.data.objects.new("L_T", bpy.data.lights.new("L_T", 'POINT'))
    lamp.location = (5, 5, 5)
    lights.objects.link(lamp)
    sc.view_settings.exposure = 1.5
    sc.render.resolution_x = 1234
    bpy.context.view_layer.layer_collection.children["Lights_Off"].exclude = True
    scene = os.path.join(root, "scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=scene)
    return scene, assets


def row(lane, gate, master, loc, rot=(0, 0, 0), scale=1, **kw):
    return dict(lane=lane, gate=gate, master=master, kind="row", loc=list(loc), rot=list(rot), scale=scale, placed=True, **kw)


ROWS = {
    "rows": [
        row("L1", "Gate_A", "SM_Box", (1, 2, 3), (0, 0, 90), object="SM_Box.L1.0001"),
        row("L1", "Gate_A", "SM_Box", (4, 5, 6), (0, 0, 0), [1, 1, 2], slots={"1": "M_Over"}),
        row("L1", "L1_own_id", "SM_Box", (4.5, 5, 6), slots={"1": "M_Nope", "5": "M_Over"}),
        row("L2", "Gate_B", "SM_Plate", (7, 0, 0)),
        row("L3", "Gate_B", "SM_Plate", (8, 0, 0)),
        row("L3", "Gate_C", "SM_NoUV", (9, 0, 0)),
        dict(row("L1", "Gate_P", "SM_Box", (11, 0, 0)), placed=False, why="row says parked"),
        row("L1", "Gate_Q", "SM_Missing", (12, 0, 0)),
        row("L1", "Gate_R", "SM_Box", (0, 0, 0)),
        dict(row("L1", "Gate_S", "SM_Box", (13, 0, 0)), status="superseded"),
    ],
    "gate_hidden": {"Gate_A": ["L1"], "Gate_B": ["L2", "L3"], "Gate_C": ["L3"], "HostHidden": ["L1"], "Gate_Gone": ["L1"]},
    "swapped": {"SM_Box": 2},
    "gate_not_found": {"new:Thing": ["L1"], "weird name": ["L1"], "L1_own_id": ["L1"]},
    "host_cuts": [{"object": "HostWall", "faces": {"axis": "y", "at": -1, "between": {"x": [0, 2]}}, "only_if": "object_shown", "why": "test"},
                  {"object": "HostHidden", "faces": {"axis": "y", "at": -1, "between": {"x": [0, 2]}}, "only_if": "object_shown"}],
}

PROBE = r'''
import bpy, json, sys
vl = bpy.context.view_layer
kit = {}
for o in bpy.data.objects:
    if "kit_row" in o:
        kit[o["kit_row"]] = dict(name=o.name, loc=[round(v, 5) for v in o.location], rot=[round(v, 4) for v in o.rotation_euler], scale=[round(v, 4) for v in o.scale], mesh=o.data.name,
                                 users=o.data.users, slots=[(s.link, s.material.name if s.material else None) for s in o.material_slots],
                                 cols=[c.name for c in o.users_collection], phase=o.get("phase"), tris=len(o.data.polygons))
st = lambda n: (bpy.data.objects[n].hide_render, bpy.data.objects[n].hide_viewport, "kit_join_hidden" in bpy.data.objects[n]) if n in bpy.data.objects else None
res = dict(kit=kit, hide={n: st(n) for n in ("Gate_A", "Gate_B", "Gate_C", "Gate_Keep", "HostHidden", "HostWall")},
           mats=sorted(m.name for m in bpy.data.materials), n_objects=len(bpy.data.objects))
res["plate_g"] = bpy.data.objects["Plate_g"].data.name
res["box_g"] = [bpy.data.objects[n].data.name for n in ("Box_g1", "Box_g2")]
res["box_g_tris"] = [len(bpy.data.objects[n].data.polygons) for n in ("Box_g1", "Box_g2")]
res["box_g_mats"] = [[m.name if m else None for m in bpy.data.objects[n].data.materials] for n in ("Box_g1", "Box_g2")]
res["wall"] = [len(bpy.data.objects["HostWall"].data.polygons), len(bpy.data.objects["HostHidden"].data.polygons), sorted(m.name for m in bpy.data.meshes if m.name.endswith(".pre_cut"))]
sc = bpy.context.scene
res["guard"] = dict(exposure=sc.view_settings.exposure, res=sc.render.resolution_x, cam=sc.camera.name, cam_loc=list(bpy.data.objects["CAM_T"].location),
                    light=[list(bpy.data.objects["L_T"].location), bpy.data.objects["L_T"].data.energy, bpy.data.objects["L_T"].hide_render],
                    lights_excluded=vl.layer_collection.children["Lights_Off"].exclude, lane_cols=sorted(c.name for c in bpy.data.collections if c.name.startswith("COL_Lane_")),
                    parent_children=sorted(c.name for c in bpy.data.collections["Parent"].children) if "Parent" in bpy.data.collections else None)
res["empty_slots"] = [o.name for o in bpy.data.objects if o.type == 'MESH' and any(s.material is None for s in o.material_slots)]
json.dump(res, open(sys.argv[sys.argv.index("--") + 1], "w"))
'''


def probe(blend, out):
    fd, path = tempfile.mkstemp(suffix=".py")
    os.write(fd, PROBE.encode())
    os.close(fd)
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", blend, "--python", path, "--", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(path)
    if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
        print(r.stdout[-1500:], r.stderr[-1500:])
        raise RuntimeError("probe failed")
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def main():
    root = tempfile.mkdtemp(prefix="kit_rows_selftest_")
    try:
        scene, assets = build_world(root)
        lib = os.path.join(root, "lib", "Test_Kit.blend")
        man = lib + ".manifest.json"
        code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
        check(code == 0 and "KIT_LIBRARY" in out, "build makes the library (exit %d)" % code)
        rows = os.path.join(root, "rows.json")
        with open(rows, "w", encoding="utf-8") as f:
            json.dump(ROWS, f)
        base = ["join-rows", "--library", lib, "--manifest", man, "--rows", rows, "--parent", "Parent", "--phase", "T"]
        before = probe(scene, os.path.join(root, "p0.json"))
        size0, mtime0 = os.path.getsize(scene), os.path.getmtime(scene)

        # dry run: nothing changes, the plan is complete
        rep = os.path.join(root, "dry.json")
        code, out = blender(base + ["--report", rep], scene)
        check(code == 0 and "KIT_JOIN" in out, "dry run exits 0")
        d = json.load(open(rep))
        by = {e["key"]: e for e in d["rows"]}
        check(d["summary"]["rows_add"] == 6 and d["summary"]["rows_skip"] == 4, "dry run: 6 adds, 4 skips (%s)" % d["summary"])
        why = {e["master"] + "/" + str(e["gate"]): e["why"] for e in d["rows"] if e["action"] == "skip"}
        check("parked" in why["SM_Box/Gate_P"] and "not in the library" in why["SM_Missing/Gate_Q"] and "origin" in why["SM_Box/Gate_R"] and "superseded" in why["SM_Box/Gate_S"],
              "dry run: each skip says why (%s)" % why)
        check(sorted(h["gate"] for h in d["hides"] if h["action"] == "hide") == ["Gate_A", "Gate_B", "Gate_C", "HostHidden"] and
              [h["why"] for h in d["hides"] if h["gate"] == "Gate_Gone"] == ["no such object in this file"], "dry run: hides listed, a missing gate object skipped with its reason")
        check(list(d["claimed_by_two_lanes"]) == ["Gate_B"] and d["claimed_by_two_lanes"]["Gate_B"]["rows"] == 2, "dry run: the gate two lanes claim is listed with both rows")
        check(d["gate_not_found"] == {"total": 3, "new_piece": 1, "own_id_row": 1} and len(d["flags"]) == 1 and "weird name" in d["flags"][0], "dry run: gate_not_found sorted, the odd one flagged")
        check([(c["object"], c["action"]) for c in d["host_cuts"]] == [("HostWall", "cut"), ("HostHidden", "skip")] and d["host_cuts"][0]["faces"] == 2,
              "dry run: host cut planned on the shown object only (%s)" % d["host_cuts"])
        check(sorted(s["mesh"] for s in d["swaps"]) == ["SM_Box"] and d["swaps"][0]["objects"] == 2, "dry run: the older gate mesh named like the asset is listed for a swap")
        check(any("M_Nope" in w for w in d["rows"][2]["warnings"]) and any("only 2 slots" in w for w in d["rows"][2]["warnings"]), "dry run: an override with an unknown material or slot is a warning")
        check(os.path.getsize(scene) == size0 and os.path.getmtime(scene) == mtime0, "dry run saves nothing")

        # skip lanes / no uv change the plan, not the scene
        code, out = blender(base + ["--report", rep, "--skip-lanes", "L3", "--skip-no-uv"], scene)
        d3 = json.load(open(rep))
        check({h["gate"]: h["action"] for h in d3["hides"]}["Gate_C"] == "skip" and {h["gate"]: h["action"] for h in d3["hides"]}["Gate_B"] == "hide",
              "--skip-lanes: a gate only the skipped lane replaces stays, one another lane replaces is still hidden")
        check(d3["summary"]["rows_add"] == 4, "--skip-lanes L3: 4 adds (%s)" % d3["summary"])
        code, out = blender(base + ["--report", rep, "--skip-no-uv"], scene)
        d4 = json.load(open(rep))
        check([e["why"] for e in d4["rows"] if e["master"] == "SM_NoUV"] == ["piece has no UV map (--skip-no-uv)"], "--skip-no-uv leaves the row with no UV map out")
        code, out = blender(base + ["--report", rep], scene)
        check(any("no UV" in w for w in json.load(open(rep))["pieces"]["SM_NoUV"]["warnings"]), "a piece with no UV map is flagged")

        # apply: refused without a backup, then done
        code, out = blender(base + ["--apply", "--save-as", os.path.join(root, "nobackup.blend")], scene)
        check(code == 1 and not os.path.exists(os.path.join(root, "nobackup.blend")) and "needs backup" in out, "apply without --backup is refused and saves nothing")
        joined, backup = os.path.join(root, "joined.blend"), os.path.join(root, "backup.blend")
        code, out = blender(base + ["--apply", "--backup", backup, "--report", rep, "--save-as", joined], scene)
        check(code == 0 and os.path.isfile(backup) and os.path.isfile(joined), "apply with a backup (exit %d)" % code)
        if code:
            print(out[-2500:])
        a = json.load(open(rep))
        check(a["checks"]["failures"] == [] and a["checks"]["objects_placed"] == a["checks"]["rows_placed"] == 6, "apply: placed count equals the rows' placed count")
        r = probe(joined, os.path.join(root, "p1.json"))
        k = r["kit"]
        a1, a2, a3 = k["L1|Gate_A|SM_Box|1"], k["L1|Gate_A|SM_Box|2"], k["L1|L1_own_id|SM_Box|1"]
        check(a1["name"] == "SM_Box.L1.0001" and a1["loc"] == [1, 2, 3] and abs(a1["rot"][2] - 1.5708) < 1e-3, "a row lands at its location and rotation, named as the row says")
        check(a2["scale"] == [1, 1, 2] and a2["slots"] == [["DATA", "M_A"], ["OBJECT", "M_Over"]], "a slot override is a per-object slot (%s)" % a2["slots"])
        check(a3["slots"] == [["DATA", "M_A"], ["DATA", "M_B"]], "an override with an unknown material or slot is left out")
        check(a1["mesh"] == a2["mesh"] == a3["mesh"] and a1["users"] >= 3, "identical masters share one mesh (%s, %d users)" % (a1["mesh"], a1["users"]))
        check(all(v["cols"] == ["COL_Lane_" + key.split("|")[0]] for key, v in k.items()) and r["guard"]["lane_cols"] == ["COL_Lane_L1", "COL_Lane_L2", "COL_Lane_L3"] and
              r["guard"]["parent_children"] == ["COL_Lane_L1", "COL_Lane_L2", "COL_Lane_L3"], "objects sit in COL_Lane_<lane> under the parent collection")
        check(all(v["phase"] == "T" for v in k.values()) and not any(max(abs(c) for c in v["loc"]) < 1e-3 for v in k.values()), "phase tag set, nothing at the origin")
        check(r["empty_slots"] == [] and not [m for m in r["mats"] if m[-4:-3] == "." and m[-3:].isdigit()] and r["mats"].count("M_A") == 1 and "M_B" in r["mats"],
              "no empty slot, no .001 material, M_A stays one datablock, M_B came with the piece (%s)" % r["mats"])
        check(r["hide"]["Gate_A"] == [True, True, True] and r["hide"]["Gate_B"] == [True, True, True] and r["hide"]["Gate_C"] == [True, True, True] and r["hide"]["Gate_Keep"] == [False, False, False],
              "gate objects are hidden in render and viewport, never deleted, the rest untouched")
        check(r["box_g"][0] == r["box_g"][1] == a1["mesh"] and "M_B" in r["box_g_mats"][0], "the older gate meshes of a listed asset took the library mesh (swap)")
        check(r["plate_g"] == "SM_Plate" and k["L2|Gate_B|SM_Plate|1"]["mesh"] == "KP_SM_Plate", "a gate mesh named like an asset the rows file does not list is left, the placed plates share a mesh of their own")
        check(r["wall"][0] == 1 and r["wall"][1] == 3 and r["wall"][2] == ["HostWall.pre_cut"], "host cut: the shown wall lost its 2 faces, the hidden one is untouched, the old mesh is kept")
        g0, g1 = before["guard"], r["guard"]
        check({key: g0[key] for key in ("exposure", "res", "cam", "cam_loc", "light", "lights_excluded")} == {key: g1[key] for key in ("exposure", "res", "cam", "cam_loc", "light", "lights_excluded")} and
              g1["lights_excluded"] is True, "camera, light, exposure, resolution and the excluded light collection are as they were")

        # rerun on the result: nothing changes
        j2, b2 = os.path.join(root, "joined2.blend"), os.path.join(root, "backup2.blend")
        code, out = blender(base + ["--apply", "--backup", b2, "--report", rep, "--save-as", j2], joined)
        s2 = json.load(open(rep))["summary"]
        check(code == 0 and s2["rows_keep"] == 6 and "rows_add" not in s2 and "rows_move" not in s2 and s2["hide"] == 0 and s2["gate_meshes_swapped"] == 0 and s2["pieces_new_in_scene"] == 0,
              "rerun: every row kept, nothing hidden or swapped (%s)" % s2)
        r2 = probe(j2, os.path.join(root, "p2.json"))
        r1 = probe(joined, os.path.join(root, "p1b.json"))
        check(r2 == r1, "rerun: the probed scene is identical")

        # the user edits a piece in the library; the join carries it, build keeps it
        run_py('''
import bpy
from mathutils import Vector
col = bpy.data.collections["SM_Plate"]
me = bpy.data.meshes.new("extra")
me.from_pydata([(0, 0, 0), (0.05, 0, 0), (0.05, 0.05, 0), (0, 0.05, 0)], [], [(0, 1, 2, 3)])
me.materials.append(bpy.data.materials["M_A"])
ob = bpy.data.objects.new("UserAdded", me)
ob.location = Vector(col.instance_offset) + Vector((0.3, 0, 0))
col.objects.link(ob)
bpy.ops.wm.save_mainfile()
''', lib)
        code, out = blender(["build", "--scene", scene, "--assets-dir", assets, "--out", lib])
        check(code == 0, "build re-run on the edited library exits 0")
        j3, b3 = os.path.join(root, "joined3.blend"), os.path.join(root, "backup3.blend")
        code, out = blender(base + ["--apply", "--backup", b3, "--report", rep, "--save-as", j3], joined)
        s3 = json.load(open(rep))
        r3 = probe(j3, os.path.join(root, "p3.json"))
        check(code == 0 and s3["summary"]["pieces_updated"] == 1 and s3["summary"]["pieces_edited_in_library"] == 1, "a library edit is an update of that piece (%s)" % s3["summary"])
        check(r3["kit"]["L2|Gate_B|SM_Plate|1"]["tris"] == r1["kit"]["L2|Gate_B|SM_Plate|1"]["tris"] + 1 and r3["kit"]["L2|Gate_B|SM_Plate|1"]["loc"] == [7, 0, 0],
              "the placed plate has the user's added face and keeps its place")
        m = json.load(open(man))
        check(m["pieces"]["SM_Plate"]["prev_hash"] is None, "join-rows does not touch the manifest")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("KIT_ROWS_SELFTEST", "FAIL" if FAILS else "PASS")
    for f in FAILS:
        print("  failed:", f)
    sys.exit(1 if FAILS else 0)


main()
