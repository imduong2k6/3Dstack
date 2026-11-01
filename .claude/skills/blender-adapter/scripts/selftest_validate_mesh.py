"""Self-test for validate_mesh.py. Headless, builds tiny synthetic assets, never touches a project:

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/selftest_validate_mesh.py

Loads validate_mesh.py the way the live Blender does (exec, no __file__), then checks that the old call still works and that a
spec adds the dims, pivot and material checks: each one passes on a good asset and fails, for the right reason, on a bad one.
Then the parts check (z-fighting fails; back-to-back, enclosed and floating parts warn; a decal 0.1 mm proud and a UCX_ collider do
not count; 30,000 triangles stay fast), the zero-area UV check, and last the command line exit codes.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

import bmesh
import bpy
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
NS = {"__name__": "exec_test"}
exec(open(os.path.join(HERE, "validate_mesh.py"), encoding="utf-8").read(), NS)
validate = NS["validate"]


def box_uv(bm, zero_faces=0):
    """Project each face flat along its main axis; the first zero_faces faces get no UV area."""
    uv = bm.loops.layers.uv.new("UVMap")
    bm.normal_update()
    for n, f in enumerate(bm.faces):
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [i for i in range(3) if i != ax]
        for lp in f.loops:
            lp[uv].uv = (0.0, 0.0) if n < zero_faces else (lp.vert.co[a], lp.vert.co[b])


def asset(name, dims=(4.0, 0.15, 3.0), z0=0.0, groups=("upper_wall", "trim", "door_frames"), extra_slots=(), zero_uv_faces=0):
    """A closed box with its origin at the bottom centre (z0 = 0), one UV map, one material per group."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * dims[0], v.co.y * dims[1], (v.co.z + 0.5) * dims[2] + z0)
    box_uv(bm, zero_uv_faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for g in groups:
        m = bpy.data.materials.get("M_" + g) or bpy.data.materials.new("M_" + g)
        m["material_group"] = g
        me.materials.append(m)
    for m in extra_slots:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def spec_file(folder, name, pivot="bottom-center", done="bounding box within 1 cm of dims_m", dims="[4.0, 0.15, 3.0]", asset_name=None,
              groups="[upper_wall, trim, door_frames]", budget=100):
    p = os.path.join(folder, name + ".md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"---\nasset: {asset_name or name}\ntype: kit\ndims_m: {dims}\npivot: {pivot}\nmaterial_group: {groups}\nbudget_tris: {budget}\n"
                f"done_when:\n  - {done}\n  - door leaf opening 0.90 x 2.04 m within 1 mm\n---\nbody\n")
    return p


def run(ob, path, **kw):
    return validate(ob.name, spec=path, repo=REPO, **kw)


def test_plain(tmp):
    ob = asset("SM_Plain")
    r = validate("SM_Plain")
    assert r["pass"] and "spec" not in r and r["tris_evaluated"] == 12 and r["dimensions_m"] == [4.0, 0.15, 3.0], r
    assert validate("SM_Plain", 100)["pass"] and not validate("SM_Plain", 10)["pass"], "budget as the 2nd positional argument still works"
    bad = asset("SM_PlainBad")
    bad.scale = (2, 1, 1)
    assert not validate("SM_PlainBad")["transforms_applied"], "the old checks still run"


def test_dims(tmp):
    good = asset("SM_Good")
    r = run(good, spec_file(tmp, "SM_Good"))
    s = r["spec"]
    assert r["pass"] and s["dims"]["ok"] and s["pivot"]["checked"] and s["pivot"]["ok"] and s["materials"]["ok"] and s["asset"]["ok"], r
    assert s["tolerance_from"] == "done_when" and s["tolerance_mm"] == 10.0, s              # the "within 1 mm" line is about the door, not the size
    assert r["within_budget"], "budget_tris comes from the spec"
    off = asset("SM_Off", dims=(4.012, 0.15, 3.0))
    r = run(off, spec_file(tmp, "SM_Off", done="walls are finished"))
    assert not r["pass"] and r["spec"]["dims"]["off_mm"] == [12.0, 0.0, 0.0] and r["spec"]["tolerance_from"] == "default 1 cm", r["spec"]["dims"]
    assert run(off, spec_file(tmp, "SM_Off", done="overall size within 2 cm of the plan"))["pass"]
    assert not run(asset("SM_Off3", dims=(4.003, 0.15, 3.0)), spec_file(tmp, "SM_Off3", done="bounding box within 1 mm of dims_m"))["pass"]
    assert run(off, spec_file(tmp, "SM_Off", done="x"), tolerance_m=0.05)["pass"], "an explicit tolerance wins"
    # a mesh child counts toward the size, a collision child does not
    kid = asset("SM_KidPart", dims=(0.2, 0.2, 0.2))
    kid.parent = good
    kid.location = (3.0, 0, 0)
    r = run(good, spec_file(tmp, "SM_Good"))
    assert not r["pass"] and r["spec"]["dims"]["actual_m"][0] > 4.5, r["spec"]["dims"]
    kid.name = "UCX_SM_Good_01"
    assert run(good, spec_file(tmp, "SM_Good"))["pass"]
    # the name must be the spec's asset
    assert not run(asset("SM_Named"), spec_file(tmp, "SM_Named", asset_name="SM_Other"))["pass"]


def test_pivot(tmp):
    mid = asset("SM_Mid", z0=-1.5)                                   # origin at the centre
    r = run(mid, spec_file(tmp, "SM_Mid", pivot="bottom-center"))
    z = r["spec"]["pivot"]["axes"]["z"]
    assert not r["pass"] and not r["spec"]["pivot"]["ok"] and z["origin_at"] == "min" and abs(z["origin_off_mm"] - 1500) < 1e-3, r["spec"]["pivot"]
    assert run(mid, spec_file(tmp, "SM_Mid", pivot="center"))["pass"]
    assert run(asset("SM_Top", z0=-3.0), spec_file(tmp, "SM_Top", pivot="top-center"))["pass"]
    r = run(asset("SM_Unk"), spec_file(tmp, "SM_Unk", pivot="open-end-centre-on-axis"))
    assert r["pass"] and r["spec"]["pivot"]["checked"] is False, r["spec"]["pivot"]


def test_materials(tmp):
    r = run(asset("SM_Two", groups=("upper_wall", "trim")), spec_file(tmp, "SM_Two"))
    assert not r["pass"] and r["spec"]["materials"]["missing_groups"] == ["door_frames"], r["spec"]["materials"]
    r = run(asset("SM_Extra", groups=("upper_wall", "trim", "door_frames", "glass")), spec_file(tmp, "SM_Extra"))
    assert not r["pass"] and r["spec"]["materials"]["extra_groups"] == ["glass"], r["spec"]["materials"]
    r = run(asset("SM_Empty", extra_slots=(None,)), spec_file(tmp, "SM_Empty"))
    assert not r["pass"] and r["spec"]["materials"]["empty_slots"] == 1, r["spec"]["materials"]
    twin = bpy.data.materials.new("M_trim_b")
    twin["material_group"] = "trim"
    r = run(asset("SM_Twin", extra_slots=(twin,)), spec_file(tmp, "SM_Twin"))
    assert not r["pass"] and r["spec"]["materials"]["groups_on_two_slots"] == ["trim"], r["spec"]["materials"]
    plain = bpy.data.materials.new("M_wood")                           # no property: the name without M_ is the group
    r = run(asset("SM_ByName", groups=(), extra_slots=(plain,)), spec_file(tmp, "SM_ByName", groups="[M_wood]"))
    assert r["spec"]["materials"]["ok"], r["spec"]["materials"]


def test_loading(tmp):
    ob = asset("SM_Load")
    parsed = NS["_find_check_spec"](None, REPO).load_spec(spec_file(tmp, "SM_Load"))
    assert validate("SM_Load", spec=parsed, repo=REPO)["pass"], "a parsed spec works as well as a path"
    empty = bpy.data.objects.new("SM_Empty_Root", None)
    bpy.context.scene.collection.objects.link(empty)
    try:
        validate("SM_Empty_Root")
        raise AssertionError("an empty must be refused")
    except ValueError:
        pass
    # with no repo given and nothing to find from, say so
    old = os.getcwd()
    NS["_check_spec"] = None
    os.chdir(tempfile.gettempdir())
    try:
        validate("SM_Load", spec=parsed)
        raise AssertionError("expected a ValueError naming check_spec.py")
    except ValueError as e:
        assert "check_spec.py" in str(e), e
    finally:
        os.chdir(old)
        NS["_check_spec"] = None


BODY = ((-0.094, -0.047, 0.0), (0.094, 0.047, 0.369))        # a meter-sized body, diagonal 0.43 m, so the coplanar tolerance is 0.043 mm


def parts_asset(name, boxes=(), quads=()):
    """Several separate boxes (lo, hi) and single quads (4 corners) in one mesh, one UV map, one material."""
    bm = bmesh.new()
    for lo, hi in boxes:
        for v in bmesh.ops.create_cube(bm, size=1.0)["verts"]:
            v.co = tuple(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))
    for q in quads:
        bm.faces.new([bm.verts.new(p) for p in q])
    box_uv(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials.get("M_p") or bpy.data.materials.new("M_p"))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def decal(y, w=0.05, h=0.03):
    """A quad facing +y at height y, over the front of BODY."""
    return [(-w, y, 0.1), (-w, y, 0.1 + h), (w, y, 0.1 + h), (w, y, 0.1)]


def test_parts(tmp):
    front = BODY[1][1]
    clean = validate(parts_asset("SM_PClean", [BODY]).name)["parts"]
    assert clean["count"] == 1 and clean["ok"] and clean["warnings"] == [] and clean["coplanar_tol_mm"] == 0.0425, clean
    # z-fighting: a decal in the surface fails the asset; 0.1 mm proud, as a real decal sits, does not
    r = validate(parts_asset("SM_PFight", [BODY], [decal(front)]).name)
    z = r["parts"]["z_fighting"]
    assert not r["pass"] and not r["parts"]["ok"] and z["count"] == 1 and abs(z["examples"][0]["at_m"][1] - front) < 1e-6, r["parts"]
    assert r["parts"]["floating"]["count"] == 0
    r = validate(parts_asset("SM_PFight2", [BODY], [decal(front + 0.00001)]).name)           # 0.01 mm: under the tolerance
    assert not r["pass"] and r["parts"]["z_fighting"]["count"] == 1, r["parts"]
    r = validate(parts_asset("SM_PDecal", [BODY], [decal(front + 0.0001)]).name)             # 0.1 mm proud of a 0.37 m asset
    p = r["parts"]
    assert r["pass"] and p["count"] == 2 and p["z_fighting"]["count"] == 0 and p["floating"]["count"] == 0 and p["warnings"] == [], p
    # back-to-back: a box whose face lies flat on the body's side. A warning only
    side = ((0.094, -0.01, 0.1), (0.15, 0.01, 0.2))
    r = validate(parts_asset("SM_PBack", [BODY, side]).name)
    p = r["parts"]
    assert r["pass"] and p["back_to_back"]["count"] == 1 and p["z_fighting"]["count"] == 0 and p["back_to_back"]["examples"][0]["parts"] == [0, 1], p
    assert p["warnings"] == ["1 pairs of back-to-back touching faces"], p
    # enclosed: a box inside the body. A warning only
    r = validate(parts_asset("SM_PIn", [BODY, ((-0.03, -0.02, 0.1), (0.03, 0.02, 0.2))]).name)
    p = r["parts"]
    assert r["pass"] and p["enclosed"]["count"] == 1 and p["enclosed"]["examples"][0] == {"part": 1, "inside_part": 0, "at_m": [0.0, 0.0, 0.15]}, p
    assert p["floating"]["count"] == 0 and p["z_fighting"]["count"] == 0, "the enclosed part is not also a floating one"
    # a box poking out of the body is not enclosed
    assert validate(parts_asset("SM_POut", [BODY, ((-0.03, -0.02, 0.1), (0.03, 0.07, 0.2))]).name)["parts"]["enclosed"]["count"] == 0
    # floating: a small box 10 cm from the body. A warning only. A big one apart from the rest is not a fragment
    r = validate(parts_asset("SM_PFloat", [BODY, ((0.2, 0.0, 0.0), (0.205, 0.005, 0.005))]).name)
    p = r["parts"]
    assert r["pass"] and p["floating"]["count"] == 1 and p["floating"]["examples"][0]["gap_mm"] > 100 and p["floating"]["examples"][0]["parts"] == [1], p
    big = validate(parts_asset("SM_PBig", [BODY, ((0.2, -0.047, 0.0), (0.38, 0.047, 0.369))]).name)["parts"]
    assert big["floating"]["count"] == 0 and big["detached_large"] == 1, big
    # a piece that touches the body within the touching tolerance is attached, not floating
    assert validate(parts_asset("SM_PNear", [BODY, ((0.0945, 0.0, 0.0), (0.095, 0.005, 0.005))]).name)["parts"]["floating"]["count"] == 0
    # children are parts; a UCX_ collider is not
    body = parts_asset("SM_PKids", [BODY])
    col = parts_asset("UCX_SM_PKids_01", [BODY])
    col.parent = body
    r = validate("SM_PKids")
    assert r["pass"] and r["parts"]["count"] == 1 and r["parts"]["z_fighting"]["count"] == 0, r["parts"]
    col.name = "SM_PKids_Copy"
    r = validate("SM_PKids")
    assert not r["pass"] and r["parts"]["count"] == 2 and r["parts"]["z_fighting"]["count"] == 6, r["parts"]["z_fighting"]
    # 30,000 triangles with a hundred loose pieces stay fast
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=170, v_segments=90, radius=0.2)
    for k in range(100):
        c = mathutils.Vector((0.25 * ((k * 7) % 11) / 11 - 0.12, 0.25 * ((k * 3) % 13) / 13 - 0.12, 0.25 * ((k * 5) % 17) / 17 - 0.12))
        for v in bmesh.ops.create_cube(bm, size=0.01)["verts"]:
            v.co += c
    me = bpy.data.meshes.new("SM_PBigMesh")
    bm.to_mesh(me)
    bm.free()
    me.calc_loop_triangles()
    ob = bpy.data.objects.new("SM_PBigMesh", me)
    bpy.context.scene.collection.objects.link(ob)
    t = time.time()
    p = NS["_parts"](ob)
    took = time.time() - t
    assert len(me.loop_triangles) > 30000 and p["count"] >= 100 and took < 10, (len(me.loop_triangles), p["count"], took)
    print("   parts on", len(me.loop_triangles), "triangles,", p["count"], "parts:", round(took, 2), "s")


def test_uv_zero(tmp):
    r = validate(asset("SM_UvOk").name)
    assert r["pass"] and r["uv_zero_area_share"] == 0.0, r
    r = validate(asset("SM_UvSome", zero_uv_faces=2).name)             # 2 of 6 faces: not most
    assert r["pass"] and abs(r["uv_zero_area_share"] - 2 / 6) < 1e-9, r
    r = validate(asset("SM_UvMost", zero_uv_faces=4).name)
    assert not r["pass"] and abs(r["uv_zero_area_share"] - 4 / 6) < 1e-9 and r["uv_layers"] == ["UVMap"], r
    r = validate(asset("SM_UvEmpty", zero_uv_faces=6).name)             # a layer that was never unwrapped
    assert not r["pass"] and r["uv_zero_area_share"] == 1.0, r
    me = bpy.data.objects["SM_UvOk"].data.copy()
    me.uv_layers.remove(me.uv_layers[0])
    nouv = bpy.data.objects.new("SM_NoUv", me)
    bpy.context.scene.collection.objects.link(nouv)
    r = validate("SM_NoUv")
    assert not r["pass"] and r["uv_layers"] == [] and r["uv_zero_area_share"] is None, r


def test_cli(tmp):
    asset("SM_Cli")
    parts_asset("SM_CliFight", [BODY], [decal(BODY[1][1])])
    blend = os.path.join(tmp, "cli.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    def go(*args):
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", blend, "--python", os.path.join(HERE, "validate_mesh.py"), "--", *args]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout
    out = os.path.join(tmp, "v.json")
    rc, text = go("SM_Cli", "--spec", spec_file(tmp, "SM_Cli"), "--out", out)
    assert rc == 0 and "VALIDATE {" in text and json.load(open(out))["spec"]["dims"]["ok"], (rc, text[-300:])
    assert go("SM_Cli", "--spec", spec_file(tmp, "SM_Cli", dims="[4.5, 0.15, 3.0]"))[0] == 1
    assert go("SM_Cli")[0] == 0 and go("SM_Cli", "--budget-tris", "5")[0] == 1
    rc, text = go("SM_CliFight")
    assert rc == 1 and '"z_fighting": {"count": 1' in text, (rc, text[-300:])
    rc, text = go("SM_Nope")
    assert rc == 1 and "VALIDATE ERROR" in text, (rc, text[-200:])


def form_box(name, move=None, mats=("M_body",)):
    """A box 0.2 x 0.1 x 0.3, centred on X. move: (vertex near this corner, offset)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * 0.2, v.co.y * 0.1, v.co.z * 0.3)
    if move:
        corner, off = move
        v = min(bm.verts, key=lambda q: (q.co - mathutils.Vector(corner)).length)
        v.co += mathutils.Vector(off)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(bpy.data.materials.new(m))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def test_form(tmp):
    sec = {"name": "body", "symmetry": ["x"]}
    good = NS["_form"](form_box("Fm_good"), {"sections": [sec]})
    assert good["ok"] and good["sections"][0]["axes"]["x"]["max_mm"] < 0.01, good
    corner = (0.1, -0.05, 0.15)
    bad = form_box("Fm_bad", move=(corner, (0.005, 0, 0)))
    r = NS["_form"](bad, {"sections": [sec]})
    ax = r["sections"][0]["axes"]["x"]
    assert not r["ok"] and 3 < ax["max_mm"] <= 5.1, r
    box = [[0.09, -0.06, 0.14], [0.11, -0.04, 0.16]]
    r = NS["_form"](bad, {"sections": [dict(sec, asymmetries=[{"what": "seal", "evidence": "real", "box_m": box}])]})
    assert r["ok"] and r["sections"][0]["axes"]["x"]["skipped_as_asymmetry"] == 2, r
    assert NS["_form"](bad, {"sections": [dict(sec, tol_mm=6)]})["ok"], "tol_mm widens it"
    assert NS["_form"](bad, {"sections": [dict(sec, symmetry=[])]})["ok"], "a section with no mirror is not measured"
    r = NS["_form"](bad, {"sections": [dict(sec, parts=["nothing"])]})
    assert not r["ok"] and "match no" in r["sections"][0]["reason"], r
    assert NS["_form"](form_box("Fm_mat"), {"sections": [dict(sec, parts=["m_body"])]})["ok"], "parts by material name"
    # a mirror plane away from zero, and a child object as a section
    root = form_box("Fm_root")
    root.location = (0, 0, 0)
    kid = form_box("Fm_lug", mats=("M_lug",))
    kid.parent = root
    kid.location = (0.3, 0, 0)
    bpy.context.view_layer.update()
    assert NS["_form"](root, {"sections": [dict(sec, parts=["lug"], plane_m={"x": 0.3})]})["ok"], "plane at 0.3 on the child"
    assert not NS["_form"](root, {"sections": [dict(sec, parts=["lug"])]})["ok"], "the child off the plane at 0 fails"
    # through validate, from a spec
    ob = form_box("SM_FormSpec", move=(corner, (0.005, 0, 0)))
    p = os.path.join(tmp, "SM_FormSpec.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\nasset: SM_FormSpec\ntype: prop\ndims_m: [0.205, 0.1, 0.3]\npivot: center\nmaterial_group: [body]\nbudget_tris: 100\ndone_when:\n  - box\n"
                "form:\n  measured_from: ref/a.png\n  sections:\n    - {name: body, box_m: [[-0.1, -0.05, -0.15], [0.1, 0.05, 0.15]], symmetry: [x]}\n---\n")
    rep = validate(ob.name, spec=p, repo=REPO, stage="mesh")
    assert rep["form"]["ok"] is False and rep["pass"] is False, rep["form"]
    assert validate("Fm_good", stage="mesh")["form" if False else "object"] == "Fm_good"


def test_topology(tmp):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=0.5)
    me = bpy.data.meshes.new("Topo_grid")
    bm.to_mesh(me)
    bm.free()
    grid = bpy.data.objects.new("Topo_grid", me)
    bpy.context.scene.collection.objects.link(grid)
    t = NS["_topology"](grid)
    assert t["quads"] == 100 and t["quad_share"] == 1.0 and t["idle_flat_verts"] == 81 and t["verts"] == 121, t
    assert any("flat areas" in w for w in t["warnings"]), t["warnings"]
    # triangulated: the quad warning; a long triangle counts as thin, a bevel strip of quads does not
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 0.02
    bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Topo_tri")
    bm.to_mesh(me)
    bm.free()
    tri = bpy.data.objects.new("Topo_tri", me)
    bpy.context.scene.collection.objects.link(tri)
    t = NS["_topology"](tri)
    assert t["quads"] == 0 and t["thin_tris"] == 8 and any("quads" in w for w in t["warnings"]) and any("thin" in w for w in t["warnings"]), t
    # an n-gon that lies flat is fine; one that doesn't is named
    for lift, n in ((0.0, 0), (0.2, 1)):
        bm = bmesh.new()
        vs = [bm.verts.new((__import__("math").cos(k * 1.2566), __import__("math").sin(k * 1.2566), lift if k == 0 else 0)) for k in range(5)]
        bm.faces.new(vs)
        me = bpy.data.meshes.new("Topo_ng")
        bm.to_mesh(me)
        bm.free()
        ng = bpy.data.objects.new("Topo_ng", me)
        bpy.context.scene.collection.objects.link(ng)
        t = NS["_topology"](ng)
        assert t["ngons"] == 1 and t["ngons_not_flat"] == n, (lift, t)
    # a Bevel modifier with odd segments warns, an even one does not, and modifiers count in the numbers
    box = form_box("Topo_bev")
    m = box.modifiers.new("B", "BEVEL")
    m.width, m.segments = 0.005, 3
    bpy.context.view_layer.update()
    t = NS["_topology"](box)
    assert t["odd_bevels"] and any("odd" in w for w in t["warnings"]) and t["faces"] > 6, t
    m.segments = 2
    bpy.context.view_layer.update()
    assert not NS["_topology"](box)["odd_bevels"]
    # a mesh waiting for approval needs no UVs; the final one does
    plain = form_box("Topo_stage")
    assert validate("Topo_stage", stage="mesh")["pass"] is True
    assert validate("Topo_stage")["pass"] is False
    assert plain.data.uv_layers.get("UVMap") is None
    try:
        validate("Topo_stage", stage="uv")
        raise AssertionError("a bad stage must be refused")
    except ValueError:
        pass


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for fn in (test_plain, test_dims, test_pivot, test_materials, test_loading, test_parts, test_uv_zero, test_form, test_topology, test_cli):
            fn(tmp)
            print("ok", fn.__name__)
    print("SELFTEST validate_mesh PASS")


try:
    main()
except BaseException as e:   # Blender exits 0 after an exception under --python
    import traceback
    traceback.print_exc()
    print("SELFTEST validate_mesh FAIL:", e)
    sys.exit(1)
