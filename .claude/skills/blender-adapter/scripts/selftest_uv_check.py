"""Self-test for uv_check.py. Headless, builds tiny synthetic assets, never touches a project:

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/selftest_uv_check.py

Loads uv_check.py the way the live Blender does (exec, no __file__). Every check has a clean control and a planted defect: density
against the spec (off, within 10 %, no target), flipped and zero-area faces, overlap, UVs outside 0-1, island gap, coverage, hard
edges on and off seams, an island off the target, and the trim profile that lets overlap and 0-1 go but still holds the density.
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
exec(open(os.path.join(HERE, "uv_check.py"), encoding="utf-8").read(), NS)
uv_check = NS["uv_check"]

A = (0.02, 0.47, 0.05, 0.95)      # a UV rectangle (u0, u1, v0, v1) for a 0.25 x 0.5 m quad: 0.405 of the tile over 0.125 m2
B = (0.52, 0.97, 0.05, 0.95)
DENSITY = 2048 * (0.405 / 0.125) ** 0.5       # 3686 px/m at 2048


def strip(name, cells, sharp=()):
    """A row of 0.25 x 0.5 m quads sharing their corner vertices, quad i with the UV rectangle cells[i]. sharp: indices i whose
    edge between quad i and quad i+1 is hard."""
    bm = bmesh.new()
    top = [bm.verts.new((0.25 * i, 0.0, 0.0)) for i in range(len(cells) + 1)]
    bot = [bm.verts.new((0.25 * i, 0.5, 0.0)) for i in range(len(cells) + 1)]
    uv = bm.loops.layers.uv.new("UVMap")
    for i, (u0, u1, v0, v1) in enumerate(cells):
        f = bm.faces.new([top[i], top[i + 1], bot[i + 1], bot[i]])
        for lp, c in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            lp[uv].uv = c
    bm.edges.ensure_lookup_table()
    for i in sharp:
        next(e for e in bm.edges if set(e.verts) == {top[i + 1], bot[i + 1]}).smooth = False
    return finish(name, bm)


def finish(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cube(name):
    """A 1 m cube, every edge hard, each face its own 0.3 x 0.3 island in a 3 x 2 layout: 614.4 px/m at 2048."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    uv = bm.loops.layers.uv.new("UVMap")
    for n, f in enumerate(bm.faces):
        u0, v0 = 0.02 + 0.33 * (n % 3), 0.02 + 0.33 * (n // 3)
        for lp, c in zip(f.loops, ((u0, v0), (u0 + 0.3, v0), (u0 + 0.3, v0 + 0.3), (u0, v0 + 0.3))):
            lp[uv].uv = c
    for e in bm.edges:
        e.smooth = False
    return finish(name, bm)


def spec_file(folder, name, density):
    p = os.path.join(folder, name + ".md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"---\nasset: {name}\ntype: kit\n" + (f"texel_density_px_m: {density}\n" if density else "") + "---\nbody\n")
    return p


def run(ob, tmp, density=None, **kw):
    return uv_check(ob.name, spec=spec_file(tmp, ob.name, density), repo=REPO, **kw)


def test_density(tmp):
    r = run(strip("UV_Clean", [A, B]), tmp, 3700)
    d = r["density"]
    assert r["pass"] and r["failures"] == [] and r["warnings"] == [], r
    assert abs(d["px_per_m"] - DENSITY) < 1 and d["checked"] and d["ok"] and d["island_spread_p95_p05"] == 1.0 and d["islands_off_target"] == 0, d
    assert r["islands"] == 2 and r["flipped_faces"] == 0 and r["zero_area_faces"] == 0 and r["overlap"]["pct_of_covered"] == 0, r
    assert abs(r["coverage"]["share"] - 0.81) < 0.01 and r["gap"]["min_px"] is None and r["gap"]["checked"], r        # islands 100 px apart: wider than the 16 px wanted
    ob = bpy.data.objects["UV_Clean"]
    assert run(ob, tmp, 3400)["pass"], "8 % over the target is within 10 %"
    for target, sign in ((4300, -1), (3000, 1)):
        r = run(ob, tmp, target)
        assert not r["pass"] and "texel density" in r["failures"][0] and r["density"]["ok"] is False and (r["density"]["off_pct"] > 0) == (sign > 0), r
    r = run(ob, tmp, None)                                         # a spec without a target: not checked, never a failure
    assert r["pass"] and r["density"]["checked"] is False and "texel_density_px_m" in r["density"]["reason"], r["density"]
    assert uv_check("UV_Clean")["density"]["checked"] is False, "no spec at all"
    r = run(ob, tmp, 920, tex_size=512)                            # the same layout at 512 px is a quarter of the density
    assert r["pass"] and abs(r["density"]["px_per_m"] - DENSITY / 4) < 1, r["density"]
    # an island off the target is a warning, not a failure
    r = run(strip("UV_Island", [(0.02, 0.32, 0.05, 0.65), B]), tmp, 2458)
    assert r["pass"] and r["density"]["islands_off_target"] == 1 and any("islands" in w for w in r["warnings"]), r
    assert r["density"]["island_spread_p95_p05"] > 1.4, r["density"]
    # a cube with six islands, every edge hard, all on seams
    r = run(cube("UV_Cube"), tmp, 614)
    assert r["pass"] and r["islands"] == 6 and r["hard_edges_not_on_seams"] == 0 and abs(r["density"]["px_per_m"] - 614.4) < 0.1, r


def test_faces(tmp):
    flip = run(strip("UV_Flip", [A, (0.97, 0.52, 0.05, 0.95)]), tmp, 3700)
    assert not flip["pass"] and flip["flipped_faces"] == 1 and flip["zero_area_faces"] == 0 and flip["failures"] == ["1 flipped UV faces"], flip
    zero = run(strip("UV_Zero", [A, (0.5, 0.5, 0.05, 0.95)]), tmp, 3700)
    assert not zero["pass"] and zero["zero_area_faces"] == 1 and zero["flipped_faces"] == 0 and zero["failures"] == ["1 faces with zero UV area"], zero
    collapsed = run(strip("UV_Point", [A, B, (0.5, 0.50001, 0.5, 0.50001)]), tmp, 3700)       # a face squeezed to a point: UV area 1e-10, not exactly zero
    assert not collapsed["pass"] and collapsed["zero_area_faces"] == 1, collapsed
    assert run(strip("UV_Flip2", [A, (0.97, 0.52, 0.05, 0.95)]), tmp, 3700, profile="trim")["pass"] is False, "trim still fails a flipped face"
    assert run(strip("UV_Zero2", [A, (0.5, 0.5, 0.05, 0.95)]), tmp, 3700, profile="trim")["pass"] is False, "and a zero-area one"
    # a face that is just as tiny in 3D keeps its density and is not zero-area
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for (x0, x1, w), (u0, u1, v0, v1) in (((0.0, 0.25, 0.5), A), ((1.0, 1.00002, 0.00002), (0.6, 0.6 + 0.00002 * DENSITY / 2048, 0.6, 0.6 + 0.00002 * DENSITY / 2048))):
        vs = [bm.verts.new(c) for c in ((x0, 0.0, 0.0), (x1, 0.0, 0.0), (x1, w, 0.0), (x0, w, 0.0))]
        for lp, c in zip(bm.faces.new(vs).loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            lp[uv].uv = c
    ok = uv_check(finish("UV_Tiny", bm).name)
    assert ok["zero_area_faces"] == 0 and ok["flipped_faces"] == 0 and ok["pass"], ok


def test_layout(tmp):
    over = strip("UV_Over", [A, A])
    r = run(over, tmp, 3700)
    assert not r["pass"] and r["overlap"]["pct_of_covered"] > 40 and "UV overlap" in r["failures"][0], r
    r = run(over, tmp, 3700, profile="trim")                        # trim: overlap allowed, not measured, coverage and gap skipped
    assert r["pass"] and r["overlap"]["checked"] is False and r["coverage"]["checked"] is False and r["gap"]["checked"] is False and r["warnings"] == [], r
    assert not run(over, tmp, 4400, profile="trim")["pass"], "trim still holds the density"
    # a 1 % overlap sliver is over the limit, a clean layout is not
    sliver = run(strip("UV_Sliver", [A, (0.4, 0.97, 0.05, 0.95)]), tmp, 3700)
    assert 0 < sliver["overlap"]["pct_of_covered"] and not sliver["pass"], sliver["overlap"]
    # outside 0-1: a warning in unique (the other tile is rasterised on its own, so no overlap), allowed in trim
    out = strip("UV_Out", [A, (1.52, 1.97, 0.05, 0.95)])
    r = run(out, tmp, 3700)
    assert r["pass"] and r["faces_outside_0_1"] == 1 and "1 UV faces are outside 0-1" in r["warnings"] and r["overlap"]["pct_of_covered"] == 0, r
    r = run(out, tmp, 3700, profile="trim")
    assert r["pass"] and r["faces_outside_0_1"] == 1 and r["warnings"] == [], r
    # gap: 5 px apart warns, 100 px apart does not; coverage under 70 % warns
    r = run(strip("UV_Gap", [A, (0.4725, 0.9725, 0.05, 0.95)]), tmp, 3700)
    assert r["pass"] and r["gap"]["min_px"] is not None and 2 <= r["gap"]["min_px"] <= 8 and any("apart" in w for w in r["warnings"]), r["gap"]
    assert run(strip("UV_Gap2", [A, (0.4725, 0.9725, 0.05, 0.95)]), tmp, 3700, gap_px=4)["warnings"] == [], "--gap-px sets what is wanted"
    r = run(strip("UV_Small", [(0.02, 0.2, 0.02, 0.4), (0.5, 0.68, 0.02, 0.4)]), tmp, None)
    assert r["pass"] and r["coverage"]["share"] < 0.2 and any("coverage" in w for w in r["warnings"]), r
    # hard edges: one hard edge inside an island warns; the same edge on a seam does not
    joined = strip("UV_Hard", [(0.02, 0.47, 0.05, 0.95), (0.47, 0.97, 0.05, 0.95)], sharp=(0,))
    r = run(joined, tmp, 3700)
    assert r["pass"] and r["islands"] == 1 and r["hard_edges_not_on_seams"] == 1 and any("hard edges" in w for w in r["warnings"]), r
    r = run(strip("UV_Seam", [A, B], sharp=(0,)), tmp, 3700)
    assert r["pass"] and r["islands"] == 2 and r["hard_edges_not_on_seams"] == 0 and r["warnings"] == [], r


def test_errors(tmp):
    me = bpy.data.objects["UV_Clean"].data.copy()
    me.uv_layers.remove(me.uv_layers[0])
    bare = bpy.data.objects.new("UV_Bare", me)
    bpy.context.scene.collection.objects.link(bare)
    for bad in (lambda: uv_check("UV_Bare"), lambda: uv_check("UV_Clean", profile="tiling"), lambda: uv_check("UV_Clean", uv_map="Nope"),
                lambda: uv_check("UV_Nope")):
        try:
            bad()
            raise AssertionError("expected an error")
        except (ValueError, KeyError):
            pass
    empty = bpy.data.objects.new("UV_Empty", None)
    bpy.context.scene.collection.objects.link(empty)
    try:
        uv_check("UV_Empty")
        raise AssertionError("an empty must be refused")
    except ValueError:
        pass
    old = os.getcwd()
    NS["_check_spec"] = None
    os.chdir(tempfile.gettempdir())
    try:
        uv_check("UV_Clean", spec=os.path.join(tmp, "UV_Clean.md"))
        raise AssertionError("expected a ValueError naming check_spec.py")
    except ValueError as e:
        assert "check_spec.py" in str(e), e
    finally:
        os.chdir(old)
        NS["_check_spec"] = None


def test_cli(tmp):
    strip("UV_CliOk", [A, B])
    strip("UV_CliOver", [A, A])
    blend = os.path.join(tmp, "cli.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    def go(*args):
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", blend, "--python", os.path.join(HERE, "uv_check.py"), "--", *args]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout
    out = os.path.join(tmp, "uv.json")
    rc, text = go("UV_CliOk", "--spec", spec_file(tmp, "UV_CliOk", 3700), "--out", out)
    assert rc == 0 and "UVCHECK {" in text and json.load(open(out))["density"]["ok"], (rc, text[-300:])
    assert go("UV_CliOk", "--spec", spec_file(tmp, "UV_CliOk", 4500))[0] == 1
    assert go("UV_CliOk")[0] == 0 and go("UV_CliOk", "--tex-size", "1024")[0] == 0
    assert go("UV_CliOver")[0] == 1 and go("UV_CliOver", "--profile", "trim")[0] == 0
    rc, text = go("UV_CliNope")
    assert rc == 1 and "UVCHECK ERROR" in text, (rc, text[-200:])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for fn in (test_density, test_faces, test_layout, test_errors, test_cli):
            fn(tmp)
            print("ok", fn.__name__)
    print("SELFTEST uv_check PASS")


try:
    main()
except BaseException as e:   # Blender exits 0 after an exception under --python
    import traceback
    traceback.print_exc()
    print("SELFTEST uv_check FAIL:", e)
    sys.exit(1)
