"""Self-test for validate_mesh.py. Headless, builds tiny synthetic assets, never touches a project:

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/selftest_validate_mesh.py

Loads validate_mesh.py the way the live Blender does (exec, no __file__), then checks that the old call still works and that a
spec adds the dims, pivot and material checks: each one passes on a good asset and fails, for the right reason, on a bad one.
Last, the command line exit codes.
"""
import json
import os
import subprocess
import sys
import tempfile

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
NS = {"__name__": "exec_test"}
exec(open(os.path.join(HERE, "validate_mesh.py"), encoding="utf-8").read(), NS)
validate = NS["validate"]


def asset(name, dims=(4.0, 0.15, 3.0), z0=0.0, groups=("upper_wall", "trim", "door_frames"), extra_slots=()):
    """A closed box with its origin at the bottom centre (z0 = 0), one UV map, one material per group."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * dims[0], v.co.y * dims[1], (v.co.z + 0.5) * dims[2] + z0)
    bm.loops.layers.uv.new("UVMap")
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


def test_cli(tmp):
    asset("SM_Cli")
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
    rc, text = go("SM_Nope")
    assert rc == 1 and "VALIDATE ERROR" in text, (rc, text[-200:])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for fn in (test_plain, test_dims, test_pivot, test_materials, test_loading, test_cli):
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
