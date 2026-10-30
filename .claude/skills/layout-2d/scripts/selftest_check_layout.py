"""Self-test for check_layout.py: a small layout with one too-narrow door, one 0.193 m riser and one clean path.

    python .claude/skills/layout-2d/scripts/selftest_check_layout.py
"""
import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check_layout.py")
spec = importlib.util.spec_from_file_location("check_layout", SCRIPT)
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# a 12 x 2 m corridor with walls (black blockers) 0.3 m thick: the path along y = 1 keeps 0.7 m clear each side
FIXTURE = {"title": "fixture", "grid_m": 0.5, "shapes": [
    {"id": "F01", "legend": "white", "poly_m": rect(0, 0, 12, 2)},
    {"id": "WALL_S", "legend": "black", "poly_m": rect(0, 0, 12, 0.3)},
    {"id": "WALL_N", "legend": "black", "poly_m": rect(0, 1.7, 12, 2)},
    {"id": "P01", "legend": "white", "kind": "passage", "poly_m": rect(0, 0.3, 12, 1.7), "clear_height_m": 2.4},
    {"id": "D_OK", "legend": "red", "kind": "door", "poly_m": rect(3, 1.9, 3.95, 2.0), "clear_height_m": 2.1},
    {"id": "D_NARROW", "legend": "red", "kind": "door", "poly_m": rect(6, 1.9, 6.8, 2.0)},
    {"id": "ST1", "legend": "grey", "kind": "stair", "poly_m": rect(8, 0.4, 10.24, 1.6), "z_m": [0, 1.544], "steps": 8},
], "path": [[1, 1], [11, 1]]}


def run(layout, rules=None, *flags):
    d = tempfile.mkdtemp()
    lp = os.path.join(d, "layout.json")
    json.dump(layout, open(lp, "w"))
    args = [sys.executable, SCRIPT, lp, "--out", os.path.join(d, "check.json"), *flags]
    if rules is not None:
        rp = os.path.join(d, "lint_rules.yaml")
        open(rp, "w").write(rules)
    r = subprocess.run(args, capture_output=True, text=True)
    rep = os.path.join(d, "check.json")
    return r.returncode, (json.load(open(rep)) if os.path.exists(rep) else None), r.stdout + r.stderr


def row(rep, id_, check):
    return next(r for r in rep["rows"] if r["id"] == id_ and r["check"] == check)


def without(layout, *ids):
    out = copy.deepcopy(layout)
    out["shapes"] = [s for s in out["shapes"] if s["id"] not in ids]
    return out


# geometry: a 0.9 x 0.1 door turned 30 degrees still reads 0.9 wide; distances by hand
a, b = math.cos(math.radians(30)), math.sin(math.radians(30))
turned = [[0, 0], [0.9 * a, 0.9 * b], [0.9 * a - 0.1 * b, 0.9 * b + 0.1 * a], [-0.1 * b, 0.1 * a]]
long_, short = cl.rect_dims(turned)
assert abs(long_ - 0.9) < 1e-9 and abs(short - 0.1) < 1e-9, (long_, short)
assert abs(cl.seg_poly_dist([0, 0], [4, 0], rect(1, 0.5, 2, 1)) - 0.5) < 1e-9
assert cl.seg_poly_dist([0, 0], [4, 0], rect(1, -1, 2, 1)) == 0.0      # crosses
assert cl.seg_poly_dist([1.5, 0.5], [1.6, 0.5], rect(1, 0, 2, 1)) == 0.0  # starts inside

# 1. the fixture: exactly two blockers (the narrow door, the riser), everything else ok, exit 1
code, rep, out = run(FIXTURE)
assert code == 1, (code, out)
assert [(r["id"], r["check"]) for r in rep["rows"] if r["status"] == "blocker"] == [("D_NARROW", "width"), ("ST1", "riser")], out
assert row(rep, "D_NARROW", "width")["value"] == 0.8
assert row(rep, "ST1", "riser")["value"] == 0.193 and row(rep, "ST1", "riser")["max"] == 0.178
assert row(rep, "ST1", "tread")["value"] == 0.28 and row(rep, "ST1", "tread")["status"] == "ok"      # 2.24 m / 8
assert row(rep, "D_OK", "width")["value"] == 0.95 and row(rep, "D_OK", "width")["status"] == "ok"
assert row(rep, "P01", "width")["value"] == 1.4 and row(rep, "P01", "headroom")["status"] == "ok"
assert row(rep, "path[0]", "clear width")["value"] == 1.4 and row(rep, "path[0]", "clear width")["status"] == "ok"
assert rep["counts"]["blocker"] == 2 and "BLOCKER" in out, out

# 2. fix them: clean, exit 0
fixed = without(FIXTURE, "D_NARROW")
fixed["shapes"] = [dict(s, steps=9, poly_m=rect(8, 0.4, 10.52, 1.6)) if s["id"] == "ST1" else s for s in fixed["shapes"]]   # 9 risers of 0.172, 9 treads of 0.28
code, rep, out = run(fixed)
assert code == 0 and rep["counts"]["blocker"] == 0, (code, out)

# 3. rules file: under `layout:` or flat; both lift the two limits; an unknown key is an error (exit 2)
for text in ("layout:\n  door_min_width_m: 0.75   # a service door\n  riser_max_m: 0.2\n", "door_min_width_m: 0.75\nriser_max_m: 0.2\n"):
    code, rep, out = run(FIXTURE, text)
    assert code == 0 and rep["rules"]["riser_max_m"] == 0.2 and rep["rules_file"], (code, out)
code, rep, out = run(FIXTURE, "layout:\n  riser_max: 0.2\n")
assert code == 2 and "unknown keys" in out, (code, out)
code, rep, out = run(FIXTURE, "scene_lint:\n  anything: 1\n")      # another section is not ours
assert code == 1, out

# 4. headroom and soffit; a squeezed path
low = copy.deepcopy(FIXTURE)
low["shapes"] += [{"id": "SOF", "legend": "white", "kind": "soffit", "poly_m": rect(4, 0.4, 5, 1.6), "z_m": [1.9, 2.4]}]
low["shapes"][3]["clear_height_m"] = 1.9
code, rep, out = run(low)
assert row(rep, "SOF", "headroom")["status"] == "blocker" and row(rep, "P01", "headroom")["status"] == "blocker", out
tight = copy.deepcopy(FIXTURE)
tight["path"] = [[1, 0.6], [11, 0.6]]                      # 0.3 m from the south wall: 0.6 m clear
code, rep, out = run(tight)
assert row(rep, "path[0]", "clear width")["value"] == 0.6 and row(rep, "path[0]", "clear width")["status"] == "blocker", out

# 5. a kind guessed from the label only warns, and reads steps from the label
guess = without(FIXTURE, "D_NARROW", "ST1")
guess["shapes"] += [{"id": "X1", "legend": "red", "label": "back door", "poly_m": rect(6, 1.9, 6.7, 2.0)},
                    {"id": "X2", "legend": "grey", "label": "stairs, 8 steps up", "poly_m": rect(8, 0.4, 10.24, 1.6), "z_m": [0, 1.544]}]
code, rep, out = run(guess)
assert code == 0 and row(rep, "X1", "width")["status"] == "warn" and row(rep, "X2", "riser")["status"] == "warn", (code, out)
assert row(rep, "X1", "width")["inferred"] and rep["counts"]["blocker"] == 0

# 6. nothing to measure fails, unless allowed; a misspelt kind and a missing file are errors
bare = {"shapes": [{"id": "F01", "legend": "white", "poly_m": rect(0, 0, 4, 4)}], "path": [[1, 1], [3, 3]]}
code, rep, out = run(bare)
assert code == 1 and "nothing checked" in out and rep["counts"]["skipped"] == 1, (code, out)
code, rep, out = run(bare, None, "--allow-empty")
assert code == 0, out
code, rep, out = run({"shapes": [{"id": "D1", "kind": "doors", "poly_m": rect(0, 0, 1, 0.1)}]})
assert code == 2 and "not one of" in out, (code, out)
r = subprocess.run([sys.executable, SCRIPT, os.path.join(tempfile.gettempdir(), "no_such_layout.json")], capture_output=True, text=True)
assert r.returncode == 2, r.returncode

print("selftest_check_layout: all checks passed")
