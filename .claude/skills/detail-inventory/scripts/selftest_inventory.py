"""Self-test for check_inventory.py. Schema and YAML reader run in plain Python; counting tags in a .blend runs when
Blender is the interpreter (bpy), which is how the other self-tests run:

    python .claude/skills/detail-inventory/scripts/selftest_inventory.py                       # schema only
    bash bin/blender-bg --python .claude/skills/detail-inventory/scripts/selftest_inventory.py -- <repo> <out_dir>   # also counts tags in a .blend

Uses the two templates as the fixture, then breaks them one rule at a time.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
here = os.path.dirname(os.path.abspath(__file__))
skill = os.path.dirname(here)
spec = importlib.util.spec_from_file_location("ci", os.path.join(here, "check_inventory.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

inv = ci.mini_yaml(open(os.path.join(skill, "templates/inventory.yaml"), encoding="utf-8").read())
svc = ci.mini_yaml(open(os.path.join(skill, "templates/services.yaml"), encoding="utf-8").read())

# the reader: flow lists and maps, nested blocks, quotes with colons and hashes, comments
vent = inv["zones"][0]["walls"][0]["items"][0]
assert vent["size_m"] == [0.4, 0.1, 0.3] and vent["count"] == 3 and vent["ref"]["box"][3] == 0.24 and vent["ref"]["image"] == "corridor-01"
assert inv["zones"][0]["items"][0]["count"] == [4, 6] and inv["zones"][0]["area_m2"] == 24.0
assert svc["networks"][0]["runs"][3]["fittings"][1]["at_m"] == [4.0, 0.1, 2.4] and svc["networks"][0]["nodes"][0]["mount"].startswith("pole bracket")
assert ci.mini_yaml('a: "x: y # not a comment"  # comment\nb: [1, {c: d}, "e,f"]\nc:\n- 1\n- k: v\n  w: 2\n') == \
    {"a": "x: y # not a comment", "b": [1, {"c": "d"}, "e,f"], "c": [1, {"k": "v", "w": 2}]}
try:
    ci.mini_yaml("a: |\n  text\n")
    raise SystemExit("block scalar should be refused")
except ValueError:
    pass
print("ok  YAML subset reader")


def run(inv_, svc_=None, metrics=None, refs=None):
    rep = ci.Report()
    rows, zones = ci.check_inventory(inv_, rep, refs)
    out = ci.check_services(svc_, rep, rows, metrics) if svc_ else None
    return rep, rows, zones, out


METRICS = {"conduit_od_mm": 25, "service_cable_od_mm": 12}
rep, rows, zones, (summary, shapes, runs) = run(inv, svc, METRICS, ci.ref_ids([{"id": "corridor-01"}, {"id": "corridor-02"}, {"file": "x/corridor-03.jpg"}]))
assert not rep.blockers and not rep.majors, rep.blockers
assert zones["Z1"] == {"area_m2": 24.0, "fixture": 4, "dressing": 6, "surface": 1, "dressing_per_m2": 0.25}, zones
assert summary["ELEC"]["fittings"] == {"elbow": 2} and not summary["ELEC"]["unreached"]
assert {r["id"] for r in runs} >= {"R01", "R04"} and any(s["id"] == "F01" and s["point_m"] == [0.3, 0.1] and s["z_m"] == 2.4 for s in shapes)
print("ok  templates pass; zone density and layout shapes", zones["Z1"])


def broken(label, mutate, level="blocker", services=False):
    i, s = copy.deepcopy(inv), copy.deepcopy(svc)
    mutate(s if services else i)
    rep, *_ = run(i, s, METRICS)
    got = getattr(rep, level + "s")
    assert got, (label, "expected a " + level, rep.blockers, rep.majors, rep.minors)
    return got


item = lambda d: d["zones"][0]["walls"][0]["items"][0]
broken("duplicate id", lambda d: d["zones"][0]["walls"][0]["items"][1].update(id="Z1.W_left.vent"))
broken("id off the zone", lambda d: item(d).update(id="Q9.vent"))
broken("negative count", lambda d: item(d).update(count=-1))
broken("range reversed", lambda d: item(d).update(count=[5, 2]))
broken("no size", lambda d: item(d).pop("size_m"))
broken("bad mount", lambda d: item(d).update(mount="sideways"))
broken("no reference", lambda d: item(d).pop("ref"))
broken("no source", lambda d: item(d).update(source=""))
broken("assumed without a note", lambda d: d["zones"][0]["items"][0].pop("note"))
broken("bad phase", lambda d: item(d).update(phase="P12"))
broken("no zones", lambda d: d.update(zones=[]))
broken("no crop", lambda d: item(d)["ref"].pop("crop"), level="minor")
net = lambda d: d["networks"][0]
broken("node without height", lambda d: net(d)["nodes"][1].update(at_m=[0.2, 2.0]), services=True)
broken("run to nowhere", lambda d: net(d)["runs"][1].update(to="NOPE"), services=True)
broken("island node", lambda d: net(d)["nodes"].append({"id": "X9", "type": "fixture", "at_m": [1, 1, 1]}), services=True)
broken("unreachable after cutting a run", lambda d: net(d)["runs"].pop(2), services=True)
broken("metric not in metrics.yaml", lambda d: net(d)["runs"][0].update(metric="no_such_key"), services=True)
broken("size without a source", lambda d: net(d)["runs"][4].pop("source"), services=True)
broken("path off its anchor", lambda d: net(d)["runs"][3].update(path_m=[[9, 9, 9], [0.3, 0.1, 2.4], [4.0, 0.1, 2.0]]), services=True)
broken("inv row missing", lambda d: net(d)["nodes"][2].update(inv="Z1.nope"), services=True)
broken("duplicate fitting id", lambda d: net(d)["runs"][3]["fittings"][1].update(id="F01"), services=True)
print("ok  21 broken fixtures each refused")

rep = ci.Report()
tags = {"Z1.W_left.vent": 3, "Z1.W_left.meter_board": 0, "Z1.crates": 9, "Z1.W_right.paint": 0, "Z1.extra": 2}
out = ci.compare(rows, tags, "P3", rep)
assert out["Z1.W_left.vent"]["status"] == "ok" and out["Z1.W_left.meter_board"]["status"] == "short"
assert out["Z1.crates"]["status"] == "not_due" and out["Z1.W_right.paint"]["status"] == "not_due" and out["Z1.extra"]["status"] == "no_row"
assert len(rep.majors) == 1 and len(rep.minors) == 1
rep = ci.Report()
assert ci.compare(rows, tags, "P6", rep)["Z1.crates"]["status"] == "over" and len(rep.majors) == 2
print("ok  counts: ok, short, over, not due yet, tag with no row")

if ci.bpy:
    import bpy
    out_dir = argv[1] if len(argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "inventory_selftest")
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new("C")
    bpy.context.scene.collection.children.link(col)
    hidden = bpy.data.collections.new("H")
    hidden.hide_render = True
    bpy.context.scene.collection.children.link(hidden)
    n = 0
    for tag, k, c in (("Z1.W_left.vent", 3, col), ("Z1.W_left.meter_board", 1, col), ("Z1.crates", 5, col), ("Z1.W_left.vent", 4, hidden), ("Z1.stray", 1, col)):
        for _ in range(k):
            n += 1
            o = bpy.data.objects.new(f"O{n}", None)
            o["inv_id"] = tag
            c.objects.link(o)
    blend = os.path.join(out_dir, "inventory_scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    assert ci.count_tags() == {"Z1.W_left.vent": 3, "Z1.W_left.meter_board": 1, "Z1.crates": 5, "Z1.stray": 1}, ci.count_tags()
    inv_path = os.path.join(skill, "templates/inventory.yaml")
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", "--python", os.path.join(here, "check_inventory.py"), "--", inv_path,
           "--services", os.path.join(skill, "templates/services.yaml"), "--blend", blend, "--upto", "P6", "--out", os.path.join(out_dir, "report.json")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    rpt = json.load(open(os.path.join(out_dir, "report.json")))
    assert rpt["counts"]["Z1.crates"]["status"] == "ok" and rpt["counts"]["Z1.stray"]["status"] == "no_row" and not rpt["blockers"], rpt["counts"]
    bad = os.path.join(out_dir, "bad_inventory.yaml")
    open(bad, "w").write(open(inv_path, encoding="utf-8").read().replace("count: 3 ", "count: x "))
    r = subprocess.run(cmd[:6] + [bad], capture_output=True, text=True)
    assert r.returncode == 1 and "BLOCKER" in r.stdout, (r.returncode, r.stdout[-400:])
    print("ok  tags counted in a .blend (hidden-from-render collections skipped); CLI exit 0, and exit 1 on a blocker")
else:
    print("skip  .blend counting (run under bin/blender-bg)")
print("check_inventory self-test passed")
