"""Self-test for kit_joint_test.py. Headless, builds tiny synthetic pieces, never touches a project:

    bash bin/blender-bg --python .claude/skills/modular-kit/scripts/selftest_kit_joint.py

Good pieces (walls, a wall with its section listed the other way round, a slab whose end needs a quarter turn, round tubes,
a post, a loner) must all join, both with the objects in the open file and loaded from one .blend per asset. Then one fault at
a time: a mesh 5 mm short, 4 mm long, a dir that points into the piece, an end 5 mm off its port, sections that differ, two
ends that are each 0.6 mm short (a 1.2 mm seam gap that neither port shows alone), a join across kinds, a missing mesh.
Inset mode: a door and a window in their bays' openings must fit (the wall face is not read whole), and one fault at a time: an
opening cut 100 mm short, a port off the face, an inset with a belly inside the wall, a block that spans the wall with no vertex
inside it, an inset 4 mm too narrow, an opening declared as an end (the whole wall face read, which is the false failure this mode replaces), a role that does not join. Last,
the command line: exit code 0 on the good sets, 1 on the faulty ones.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_joint_test as kj  # noqa: E402


def make(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    return make(name, v, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])


def tube(name, x0, x1, r, n=16):
    v = [(x, r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for x in (x0, x1) for k in range(n)]
    return make(name, v, [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)])


def port(name, pos, d, kind, size, **extra):
    return {"name": name, "pos_m": pos, "dir": d, "kind": kind, "size_m": size, **extra}


def ends(x, y_z, kind, size, a="end_a", b="end_b"):
    return [port(a, [-x, *y_z], [-1, 0, 0], kind, size), port(b, [x, *y_z], [1, 0, 0], kind, size)]


def write_spec(folder, asset, ports):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, asset + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\nasset: %s\ntype: kit\nports:\n%s\n---\nbody\n" % (asset, "\n".join("  - " + json.dumps(p) for p in ports)))
    return path


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_good(folder):
    """Returns the spec paths. Origin at the bottom centre of each piece."""
    pieces = {
        "SM_WallA": (box("SM_WallA", -2, 2, -.075, .075, 0, 3), ends(2, [0, 1.5], "wall_4m", [0.15, 3.0])),
        "SM_WallB": (box("SM_WallB", -1, 1, -.075, .075, 0, 3), ends(1, [0, 1.5], "wall_4m", [0.15, 3.0])),
        "SM_WallSw": (box("SM_WallSw", -1, 1, -.075, .075, 0, 3), ends(1, [0, 1.5], "wall_4m", [3.0, 0.15])),    # sides listed the other way
        "SM_Slab": (box("SM_Slab", -1, 1, -1.5, 1.5, 0, .15), ends(1, [0, .075], "wall_4m", [3.0, 0.15])),     # joins a wall after a quarter turn
        "SM_TubeA": (tube("SM_TubeA", 0, 1, .0225), [port("start", [0, 0, 0], [-1, 0, 0], "pipe", [0.045]), port("stop", [1, 0, 0], [1, 0, 0], "pipe", [0.045])]),
        "SM_TubeB": (tube("SM_TubeB", 0, .5, .0225), [port("start", [0, 0, 0], [-1, 0, 0], "pipe", [0.045]), port("stop", [.5, 0, 0], [1, 0, 0], "pipe", [0.045])]),
        "SM_Post": (box("SM_Post", -.05, .05, -.05, .05, 0, 2), [port("top", [0, 0, 2], [0, 0, 1], "post", [0.1, 0.1]), port("foot", [0, 0, 0], [0, 0, -1], "post", [0.1, 0.1])]),
        "SM_Solo": (box("SM_Solo", -.1, .1, -.1, .1, 0, .2), [port("only", [.1, 0, .1], [1, 0, 0], "solo", [0.2, 0.2])]),
    }
    return [write_spec(folder, name, p) for name, (_, p) in pieces.items()]


def build_bad(folder):
    box("SM_Short", -2, 1.995, -.075, .075, 0, 3)
    box("SM_Long", -2, 2.004, -.075, .075, 0, 3)
    box("SM_Flip", -2, 2, -.075, .075, 0, 3)
    box("SM_Off", -2, 2, -.07, .08, 0, 3)
    box("SM_ThinA", -2, 2, -.08, .08, 0, 3)
    box("SM_ThinB", -2, 2, -.075, .075, 0, 3)
    box("SM_E1", -2, 1.9994, -.075, .075, 0, 3)
    box("SM_E2", -1.9994, 2, -.075, .075, 0, 3)
    sec = [0.15, 3.0]
    z = [0, 1.5]
    return [write_spec(folder, "SM_Short", ends(2, z, "k_short", sec)), write_spec(folder, "SM_Long", ends(2, z, "k_long", sec)),
            write_spec(folder, "SM_Flip", [port("end_a", [-2, 0, 1.5], [-1, 0, 0], "k_flip", sec), port("end_b", [2, 0, 1.5], [-1, 0, 0], "k_flip", sec)]),
            write_spec(folder, "SM_Off", ends(2, z, "k_off", sec)),
            write_spec(folder, "SM_ThinA", ends(2, z, "k_thin", [0.16, 3.0])), write_spec(folder, "SM_ThinB", ends(2, z, "k_thin", sec)),
            write_spec(folder, "SM_E1", ends(2, z, "k_gap", sec)), write_spec(folder, "SM_E2", ends(2, z, "k_gap", sec))]


def parts(name, boxes):
    """One mesh of several boxes (x0, x1, y0, y1, z0, z1): a wall around an opening, a frame. Only the vertices matter to the test."""
    v, f = [], []
    for x0, x1, y0, y1, z0, z1 in boxes:
        k = len(v)
        v += [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        f += [tuple(k + i for i in q) for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    return make(name, v, f)


def door_ports(prefix, pos_z, kind, size, x=0.0):
    return [port(f"{prefix}_front", [x, -0.15, pos_z], [0, -1, 0], kind, size), port(f"{prefix}_back", [x, 0.15, pos_z], [0, 1, 0], kind, size)]


# a 1.4 m bay in a 0.3 m wall with a 1.0 x 2.1 door opening; a 1.4 m bay with a 0.9 x 1.2 window opening (sill 0.9 m)
BAY = [(-.7, -.5, -.15, .15, 0, 3.2), (.5, .7, -.15, .15, 0, 3.2), (-.5, .5, -.15, .15, 2.1, 3.2)]
DOOR = [(-.5, -.455, -.15, .15, 0, 2.1), (.455, .5, -.15, .15, 0, 2.1), (-.5, .5, -.15, .15, 2.055, 2.1), (-.45, .45, -.025, .025, 0, 2.05)]
WIN_BAY = [(-.7, -.45, -.15, .15, 0, 3.2), (.45, .7, -.15, .15, 0, 3.2), (-.45, .45, -.15, .15, 0, .9), (-.45, .45, -.15, .15, 2.1, 3.2)]
WINDOW = [(-.45, -.41, -.15, .15, .9, 2.1), (.41, .45, -.15, .15, .9, 2.1), (-.45, .45, -.15, .15, .9, .94), (-.45, .45, -.15, .15, 2.06, 2.1),
          (-.5, .5, -.2, -.15, .86, .9)]    # a sill tongue 50 mm wider than the opening, proud of the front face: it is not between the wall's faces
BAY_ENDS = lambda: ends(.7, [0, 1.6], "bay_wall", [0.3, 3.2])
D_KIND, W_KIND = "door_1000x2100", "window_900x1200"


def build_inset(folder):
    """A door bay with its door, a window bay with its window: the opening ports are read from the name (opening_*), the inset ports by role."""
    parts("SM_BayDoor", BAY)
    parts("SM_BayWin", WIN_BAY)
    parts("SM_Door", DOOR)
    parts("SM_Window", WINDOW)
    return [write_spec(folder, "SM_BayDoor", BAY_ENDS() + door_ports("opening", 1.05, D_KIND, [1.0, 2.1])),
            write_spec(folder, "SM_BayWin", BAY_ENDS() + door_ports("opening", 1.5, W_KIND, [0.9, 1.2])),
            write_spec(folder, "SM_Door", [{**p, "role": "inset"} for p in door_ports("frame", 1.05, D_KIND, [1.0, 2.1])]),
            write_spec(folder, "SM_Window", door_ports("reveal", 1.5, W_KIND, [0.9, 1.2]))]


def build_inset_faults(folder):
    parts("SM_BayDoor", BAY)
    parts("SM_Door", DOOR)
    parts("SM_BayShort", [(-.7, -.5, -.15, .15, 0, 3.2), (.5, .7, -.15, .15, 0, 3.2), (-.5, .5, -.15, .15, 2.0, 3.2)])      # the opening is 2.0 high
    parts("SM_BayPlane", BAY)
    parts("SM_BayAsEnd", BAY)
    parts("SM_DoorBelly", DOOR + [(-.52, .52, -.05, .05, .2, 1.9)])                                                             # 20 mm wider than the opening, inside the wall
    parts("SM_DoorBlock", DOOR + [(-.55, .55, -.15, .15, .2, 1.9)])                                                            # 50 mm wider, vertices only on the wall's two faces
    parts("SM_DoorNarrow", [(-.498, -.453, -.15, .15, 0, 2.1), (.453, .498, -.15, .15, 0, 2.1), (-.498, .498, -.15, .15, 2.055, 2.1)])
    parts("SM_Odd", [(0, .2, -.05, .05, 0, 1)])
    shifted = [port(p["name"], [p["pos_m"][0], p["pos_m"][1] * 2 / 3, p["pos_m"][2]], p["dir"], p["kind"], p["size_m"]) for p in door_ports("opening", 1.05, D_KIND, [1.0, 2.1])]
    return [write_spec(folder, "SM_BayDoor", door_ports("opening", 1.05, D_KIND, [1.0, 2.1])), write_spec(folder, "SM_Door", door_ports("reveal", 1.05, D_KIND, [1.0, 2.1])),
            write_spec(folder, "SM_BayShort", door_ports("opening", 1.05, D_KIND, [1.0, 2.1])),
            write_spec(folder, "SM_BayPlane", shifted),
            write_spec(folder, "SM_BayAsEnd", [{**p, "role": "end", "kind": "as_end"} for p in door_ports("opening", 1.05, D_KIND, [1.0, 2.1])]),
            write_spec(folder, "SM_DoorBelly", door_ports("reveal", 1.05, D_KIND, [1.0, 2.1])),
            write_spec(folder, "SM_DoorBlock", door_ports("reveal", 1.05, D_KIND, [1.0, 2.1])),
            write_spec(folder, "SM_DoorNarrow", door_ports("reveal", 1.05, D_KIND, [0.996, 2.1])),
            write_spec(folder, "SM_Odd", [port("odd_end", [0.2, 0, 0.5], [1, 0, 0], D_KIND, [0.1, 1.0])])]


def texts(rep):
    out = [f"{p['port']}: {m}" for pc in rep["pieces"] for p in pc["ports"] for m in p["problems"]]
    out += [f"{r['a']} + {r['b']}: {m}" for r in rep["pairs"] for m in r["problems"]]
    return out


def has(rep, *words):
    return any(all(w in t for w in words) for t in texts(rep))


def test_good(tmp):
    reset()
    specs = build_good(os.path.join(tmp, "good"))
    scene_blend = os.path.join(tmp, "good.blend")
    bpy.ops.wm.save_as_mainfile(filepath=scene_blend)
    rep = kj.run(specs)
    assert rep["pass"], texts(rep) + rep["errors"]
    s = rep["summary"]
    assert (s["pieces"], s["ports_failed"], s["pairs"], s["pairs_failed"]) == (8, 0, 36 + 10 + 3 + 1, 0), s
    assert rep["kinds"]["wall_4m"] == {"ports": 8, "pairs": 36, "failed": 0}, rep["kinds"]
    assert any("solo" in w for w in rep["warnings"]), rep["warnings"]
    spun = [r for r in rep["pairs"] if r["spin_deg"] == 90]
    assert spun, "the slab should have needed a quarter turn"
    assert max(abs(r["gap_mm"]) for r in rep["pairs"]) < 1e-3
    # one .blend per asset: take the objects out of the open file and read them from the assets folder
    assets = os.path.join(tmp, "assets")
    for ob in list(bpy.data.objects):
        d = os.path.join(assets, ob.name)
        os.makedirs(d)
        bpy.data.libraries.write(os.path.join(d, ob.name + ".blend"), {ob})
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    rep2 = kj.run(specs, assets_dir=assets)
    assert rep2["pass"] and rep2["summary"]["pairs"] == s["pairs"], (texts(rep2), rep2["errors"])
    return specs, scene_blend


def test_faults(tmp):
    reset()
    specs = build_bad(os.path.join(tmp, "bad"))
    bad_blend = os.path.join(tmp, "bad.blend")
    bpy.ops.wm.save_as_mainfile(filepath=bad_blend)
    rep = kj.run(specs)
    assert not rep["pass"]
    assert has(rep, "end_b", "short of the port plane", "5.00"), texts(rep)
    assert has(rep, "end_b", "passes the port plane by 4.00"), texts(rep)
    assert has(rep, "end_b", "dir points into the piece"), texts(rep)
    assert has(rep, "off pos_m", "5.00"), texts(rep)
    assert has(rep, "SM_ThinA", "SM_ThinB", "specs differ in section"), texts(rep)
    assert has(rep, "SM_E1.end_b + SM_E2.end_a", "1.20 mm gap"), texts(rep)
    assert not any(p["ok"] is False for pc in rep["pieces"] for p in pc["ports"] if pc["asset"] in ("SM_E1", "SM_E2", "SM_ThinA", "SM_ThinB")), "those ports are fine alone"
    # a looser tolerance lets the 5 mm short wall through
    r6 = kj.run(specs[:1], tol_mm=6.0)
    assert r6["summary"]["ports_failed"] == 0 and not has(r6, "short of"), texts(r6)      # its pair of two short ends (10 mm) still fails
    # a join across kinds, and a spec whose mesh does not exist
    reset()
    good = build_good(os.path.join(tmp, "good2"))
    rep = kj.run(good, pairs=["SM_WallA.end_b:SM_TubeA.start"])
    assert has(rep, "kinds differ") and not rep["pass"], texts(rep)
    ghost = write_spec(os.path.join(tmp, "ghost"), "SM_Ghost", ends(1, [0, 0], "wall_4m", [0.15, 3.0]))
    rep = kj.run(good[:2] + [ghost])
    assert any("SM_Ghost" in e and "no built mesh" in e for e in rep["errors"]) and not rep["pass"], rep["errors"]
    rep = kj.run(good[:2] + [ghost], skip_missing=True)
    assert rep["pass"] and any("SM_Ghost" in w for w in rep["warnings"]), (rep["errors"], rep["warnings"])
    return specs, bad_blend


def test_inset(tmp):
    reset()
    specs = build_inset(os.path.join(tmp, "inset"))
    inset_blend = os.path.join(tmp, "inset.blend")
    bpy.ops.wm.save_as_mainfile(filepath=inset_blend)
    rep = kj.run(specs)
    assert rep["pass"], texts(rep) + rep["errors"]
    s = rep["summary"]
    assert (s["pieces"], s["ports_failed"], s["pairs"], s["pairs_failed"]) == (4, 0, 10 + 4 + 4, 0), s       # ends: 4 ports; each opening with each of its inset's two ports
    inset = [r for r in rep["pairs"] if r.get("mode") == "inset"]
    assert len(inset) == 8 and all(r["overlap_mm"] < 1e-3 and r["lateral_mm"] < 1e-3 and r["section_diff_mm"] < 1e-3 for r in inset), inset
    assert rep["kinds"][D_KIND] == {"ports": 4, "pairs": 4, "failed": 0} and rep["kinds"][W_KIND] == {"ports": 4, "pairs": 4, "failed": 0}, rep["kinds"]
    assert not rep["unmated_ports"], rep["unmated_ports"]
    # the ports of an opening and its inset are not read as open ends: they sit on a whole wall face, and still pass
    assert all(p["role"] in ("opening", "inset") and p["ok"] for pc in rep["pieces"] for p in pc["ports"] if p["port"].split("_")[0] in ("opening", "frame", "reveal")), rep["pieces"]
    # one pair named by hand, the inset first
    r1 = kj.run(specs, pairs=["SM_Door.frame_front:SM_BayDoor.opening_back"])
    assert r1["pass"] and r1["pairs"][0]["mode"] == "inset", texts(r1)
    # an opening with no inset of its kind, and the reverse, are warnings
    r2 = kj.run([specs[0]])
    assert r2["pass"] and any("opening_front" in w and "no inset port has its kind" in w for w in r2["warnings"]), r2["warnings"]
    return specs, inset_blend


def test_inset_faults(tmp):
    reset()
    specs = build_inset_faults(os.path.join(tmp, "inset_bad"))
    bad_blend = os.path.join(tmp, "inset_bad.blend")
    bpy.ops.wm.save_as_mainfile(filepath=bad_blend)
    rep = kj.run(specs)
    assert not rep["pass"]
    assert has(rep, "opening_front: opening is 1000.00 x 2000.00 mm, size_m says 1000.00 x 2100.00 mm"), texts(rep)
    assert has(rep, "opening is 50.00 mm off pos_m"), texts(rep)
    assert has(rep, "no mesh vertex on the port plane (the nearest is 50.00 mm off it)"), texts(rep)
    # the whole wall face read as an open end: the false failure of an opening declared as an end
    assert has(rep, "open end is 1400.00 x 3200.00 mm, size_m says 1000.00 x 2100.00 mm"), texts(rep)
    assert has(rep, "SM_BayDoor.opening_front + SM_DoorBelly.reveal_front", "inset reaches 20.00 mm outside the opening"), texts(rep)
    assert has(rep, "SM_BayDoor.opening_back + SM_DoorBelly.reveal_back", "20.00 mm"), texts(rep)
    assert has(rep, "SM_BayDoor.opening_front + SM_DoorBlock.reveal_front", "inset reaches 50.00 mm outside the opening"), texts(rep)   # found along its edges
    assert not any(p["problems"] for pc in rep["pieces"] if pc["asset"] == "SM_DoorBlock" for p in pc["ports"]), "the block's ports are fine alone"
    assert has(rep, "SM_DoorNarrow.reveal_front", "specs differ in section") and has(rep, "SM_DoorNarrow.reveal_front", "differs from the opening by 4.00 mm"), texts(rep)
    assert not has(rep, "SM_BayDoor.opening_front + SM_Door.reveal_front") and not has(rep, "SM_BayDoor.opening_back + SM_Door.reveal_back"), "the good door fits the good bay"
    # a pair that fails alone is not repeated, and a role that does not join says so
    assert not any("SM_BayShort" in r["a"] or "SM_BayPlane" in r["a"] for r in rep["pairs"] if r["kind"] == D_KIND), "pairs of failed ports are skipped"
    r2 = kj.run(specs, pairs=["SM_BayDoor.opening_front:SM_Odd.odd_end"])
    assert has(r2, "opening port and end port do not join"), texts(r2)
    return specs, bad_blend


def test_cli(tmp, good_specs, good_blend, bad_specs, bad_blend):
    def go(blend, specs, out):
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", blend, "--python", os.path.join(HERE, "kit_joint_test.py"), "--", "--specs", *specs, "--out", out]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout
    rc, out = go(good_blend, good_specs, os.path.join(tmp, "good.json"))
    assert rc == 0 and "KIT_JOINT" in out and json.load(open(os.path.join(tmp, "good.json")))["pass"], (rc, out[-400:])
    rc, out = go(bad_blend, bad_specs, os.path.join(tmp, "bad.json"))
    assert rc == 1 and "PORT FAIL" in out and "PAIR FAIL" in out, (rc, out[-400:])
    rc, out = go(bad_blend, [os.path.join(tmp, "nothing*.md")], os.path.join(tmp, "x.json"))
    assert rc == 1, (rc, out[-200:])


def test_cli_inset(tmp, good_specs, good_blend, bad_specs, bad_blend):
    def go(blend, specs, out):
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", blend, "--python", os.path.join(HERE, "kit_joint_test.py"), "--", "--specs", *specs, "--out", out]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout
    rc, out = go(good_blend, good_specs, os.path.join(tmp, "inset.json"))
    assert rc == 0 and json.load(open(os.path.join(tmp, "inset.json")))["pass"], (rc, out[-400:])
    rc, out = go(bad_blend, bad_specs, os.path.join(tmp, "inset_bad.json"))
    assert rc == 1 and "PAIR FAIL" in out and "inset reaches" in out, (rc, out[-400:])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        good_specs, good_blend = test_good(tmp)
        print("ok good pieces join, in one file and from one .blend each")
        bad_specs, bad_blend = test_faults(tmp)
        print("ok every fault is reported")
        test_cli(tmp, good_specs, good_blend, bad_specs, bad_blend)
        print("ok command line exit codes")
        inset_specs, inset_blend = test_inset(tmp)
        print("ok a door and a window fit their bays' openings")
        inset_bad_specs, inset_bad_blend = test_inset_faults(tmp)
        print("ok every inset fault is reported")
        test_cli_inset(tmp, inset_specs, inset_blend, inset_bad_specs, inset_bad_blend)
        print("ok command line exit codes, inset mode")
    print("SELFTEST kit_joint_test PASS")


try:
    main()
except BaseException as e:   # Blender exits 0 after an exception under --python
    import traceback
    traceback.print_exc()
    print("SELFTEST kit_joint_test FAIL:", e)
    sys.exit(1)
