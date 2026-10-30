"""Self-test for check_spec.py (plain Python, no Blender):

    python .claude/skills/modular-kit/scripts/selftest_check_spec.py

Builds the template's example spec in a temp folder, checks that it passes, then breaks one thing at a time and asserts the
finding code. Also tests the YAML reader, pivot words, the legacy keys, --migrate (including CRLF files) and the exit codes.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_spec as cs  # noqa: E402

GOOD = """---
asset: SM_Office_Wall_Door_A   # same as the file name
type: kit
kit: Office
phase: 2
source: model
priority: 2
count_in_scene: 12
photos: [C05]
dims_m: [4.00, 0.15, 3.00]
dims_source: metrics.wall_module
mount: floor
pivot: bottom-center
snap_grid_m: 0.5
ports:
  - {name: end_a, pos_m: [-2, 0, 1.5], dir: [-1, 0, 0], kind: wall_4m, size_m: [0.15, 3.0]}
  - {name: end_b, pos_m: [2, 0, 1.5], dir: [1, 0, 0], kind: wall_4m, size_m: [0.15, 3.0]}
sockets:
  - {name: hinge_L, pos_m: [-0.45, 0, 0]}
clearance_m:
  door_swing: {radius: 0.9, side: +y}
material_group: [upper_wall, trim, door_frames]
texture_set: TS_Office_Walls
texel_density_px_m: 512
camera_tier: mid
budget_tris: 800
collision: UCX_SM_Office_Wall_Door_A_01
service_id: null
landmarks: kit/SM_Office_Wall_Door_A.landmarks.json
generated: null
done_when:
  - snaps to the 0.5 m grid with no gaps against SM_Office_Wall_Plain_A
  - door leaf opening 0.90 x 2.04 m within 1 cm
method: null
validation: null
---
The photo crop first.
"""
METRICS = "wall_module: {value: 4.0, source: \"https://example.com/sheet\", note: \"6'8\\\" door\", role: kit_scale}\n"
SERVICES = "version: 1\nnetworks:\n  - id: ELEC\n    nodes:\n      - {id: LP01, type: fixture, at_m: [1, 2, 3]}\n    runs:\n      - {id: R01, from: A, to: B}\n"


def write(folder, name, text):
    p = os.path.join(folder, name)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return p


def codes(text, name="SM_Office_Wall_Door_A.md", metrics=None, services=None):
    with tempfile.TemporaryDirectory() as d:
        row = cs.check_file(write(d, name, text), metrics, services)
    return [f["code"] for f in row["errors"]], [f["code"] for f in row["warnings"]], row


def run(args):
    p = subprocess.run([sys.executable, os.path.join(HERE, "check_spec.py")] + args, capture_output=True, text=True)
    return p.returncode, p.stdout


def test_yaml():
    d = cs.parse_yaml("a: 1\nb: [1, 2.5, x y]\nc: {k: v, n: [1, 2]}\nd:\n  - e: 1\n    f: 'it''s'\n  - g\nh: |\n  one\n  two\ni: 6'8\"  # c\nj: 007\nk: ~\nl: \"a: b # x\"\n")
    assert d == {"a": 1, "b": [1, 2.5, "x y"], "c": {"k": "v", "n": [1, 2]}, "d": [{"e": 1, "f": "it's"}, "g"], "h": "one\ntwo\n",
                 "i": "6'8\"", "j": "007", "k": None, "l": "a: b # x"}, d
    assert cs.parse_yaml("x: [1,\n  2]\ny: plain\n  more\n") == {"x": [1, 2], "y": "plain more"}
    for bad in ("a: 1\na: 2\n", "a: 'open\n", "a:\n\t- 1\n", "a: [1, 2\n"):
        try:
            cs.parse_yaml(bad)
        except cs.SpecError:
            continue
        raise AssertionError("expected a parse error for " + repr(bad))
    assert cs.collect_ids(cs.parse_yaml(SERVICES)) == {"ELEC", "LP01", "R01"}


def test_pivot():
    assert cs.pivot_anchor("bottom-center") == {"x": "center", "y": "center", "z": "min"}
    assert cs.pivot_anchor("top_centre") == {"x": "center", "y": "center", "z": "max"}
    assert cs.pivot_anchor("back-face-centre") == {"x": "center", "y": "max", "z": "center"}
    assert cs.pivot_anchor("center") == {"x": "center", "y": "center", "z": "center"}
    assert cs.pivot_anchor("grid-corner") == {"x": "min", "y": "min", "z": "min"}
    assert cs.pivot_anchor("bottom") == {"z": "min"}
    assert cs.pivot_anchor("open-end-centre-on-axis") is None and cs.pivot_anchor("top-bottom") is None


def test_template():
    e, w, _ = codes(GOOD, metrics={"wall_module": {"value": 4}}, services={"LP01"})
    assert e == [] and w == [], (e, w)
    # (what to break, expected error code)
    cases = [
        ("type: kit", "type: wall", "enum"), ("source: model", "source: made", "enum"), ("mount: floor", "mount: ceiling", "enum"),
        ("camera_tier: mid", "camera_tier: near", "enum"), ("budget_tris: 800\n", "", "missing_key"), ("dims_source: metrics.wall_module\n", "", "missing_key"),
        ("kit: Office\n", "", "missing_key"), ("snap_grid_m: 0.5\n", "", "missing_key"), ("ports:\n", "portz:\n", "missing_key"),
        ("dims_m: [4.00, 0.15, 3.00]", "dims_m: [4.0, 0.15]", "dims"), ("dims_m: [4.00, 0.15, 3.00]", "dims_m: [4.0, 0, 3.0]", "dims"),
        ("dims_m: [4.00, 0.15, 3.00]", "dims_m: 4", "dims"), ("dims_source: metrics.wall_module", "dims_source: metrics.nope", "metrics_row"),
        ("asset: SM_Office_Wall_Door_A ", "asset: SM_Other ", "asset_name"), ("collision: UCX_SM_Office_Wall_Door_A_01", "collision: UCX_SM_Office_Wall_Door_A_1", "collision"),
        ("collision: UCX_SM_Office_Wall_Door_A_01", "collision: UCX_SM_Wall_01", "collision"), ("collision: UCX_SM_Office_Wall_Door_A_01", "collision: none", "collision"),
        ("kind: wall_4m, size_m: [0.15, 3.0]}\n  - {name: end_b", "size_m: [0.15, 3.0]}\n  - {name: end_b", "port"),
        ("dir: [1, 0, 0]", "dir: [1, 1, 0]", "port"), ("pos_m: [2, 0, 1.5]", "pos_m: [2, 0]", "port"), ("name: end_b", "name: end_a", "port"),
        ("size_m: [0.15, 3.0]}\n  - {name: end_b", "size_m: [0.15, 3.0, 1]}\n  - {name: end_b", "port"), ("sockets:\n  - {name: hinge_L, pos_m: [-0.45, 0, 0]}", "sockets:\n  - {name: hinge_L}", "socket"),
        ("service_id: null", "service_id: LP99", "service_id"), ("source: model", "source: generate", "missing_key"),
        ("material_group: [upper_wall, trim, door_frames]", "material_group: upper_wall", "type"), ("done_when:\n  - snaps", "done_when: []\nx:\n  - snaps", "type"),
        ("phase: 2", "phase: 12", "type"), ("method: null", "method: sculpt", "enum"),
    ]
    for old, new, want in cases:
        assert old in GOOD, old
        e, _, _ = codes(GOOD.replace(old, new, 1), metrics={"wall_module": {}}, services={"LP01"})
        assert want in e, (old, new, want, e)
    # collision none is fine with a reason in any of the three places
    for edit in ("collision: none\ncollision_reason: under the floor", "collision: \"none: sits behind a wall\"", "collision: none   # too small to matter"):
        e, _, _ = codes(GOOD.replace("collision: UCX_SM_Office_Wall_Door_A_01", edit), metrics={"wall_module": {}})
        assert "collision" not in e, (edit, e)
    # a UCX name may carry a description after it
    assert "collision" not in codes(GOOD.replace("_A_01\n", "_A_01   # one box\n", 1))[0]
    # the checks that need a file are skipped when the file is not given
    assert codes(GOOD.replace("metrics.wall_module", "metrics.nope"))[0] == [] and codes(GOOD.replace("service_id: null", "service_id: X"))[0] == []
    # warnings
    _, w, _ = codes(GOOD.replace("pivot: bottom-center", "pivot: open-end-centre"))
    assert "pivot" in w
    _, w, _ = codes(GOOD + "")
    _, w, _ = codes(GOOD.replace("texture_set: TS_Office_Walls\n", "extra_key: 1\n"))
    assert "unknown_key" in w and "missing_key" in w
    # no front matter, bad yaml
    assert codes("no front matter here\n")[0] == ["front_matter"] and codes("---\na: 'open\n---\n")[0] == ["parse"]


def test_legacy():
    old = GOOD.replace("asset:", "id:", 1).replace("source: model", "source: build").replace(
        "material_group: [upper_wall, trim, door_frames]", "material: M_Steel   # one slot").replace("ports:\n", "ends_local:\n", 1)
    e, _, row = codes(old)
    assert e.count("legacy_key") == 3 and "legacy_value" in e, e
    assert "missing_key" not in e, "a legacy key must not also be reported as missing: %s" % e
    by = {f["key"]: f for f in row["errors"]}
    assert by["id"]["replacement"] == "asset" and by["material"]["replacement"] == "material_group" and by["ends_local"]["replacement"] == "ports"
    assert by["id"]["fixable"] and by["material"]["fixable"] and not by["ends_local"]["fixable"] and by["source"]["replacement"] == "model"


def test_migrate_and_cli():
    legacy = GOOD.replace("asset:", "id:", 1).replace("source: model", "source: build  # was build").replace(
        "material_group: [upper_wall, trim, door_frames]", "material: M_Steel   # one slot").replace("ports:\n", "ends_local:\n", 1)
    with tempfile.TemporaryDirectory() as d:
        proj = os.path.join(d, "proj")
        os.makedirs(os.path.join(proj, "kit"))
        os.makedirs(os.path.join(proj, "plan"))
        write(proj, "plan/metrics.yaml", METRICS)
        write(proj, "plan/services.yaml", SERVICES)
        spec = write(proj, "kit/SM_Office_Wall_Door_A.md", legacy.replace("\n", "\r\n"))      # a Windows file
        other = write(proj, "kit/SM_Plain.md", GOOD.replace("SM_Office_Wall_Door_A", "SM_Plain"))
        # not migrated: the check reports the legacy keys, exit 1, metrics found next to the kit folder
        rc, out = run([spec, "--json"])
        rep = json.loads(out)
        assert rc == 1 and rep["checked"]["metrics"].endswith("metrics.yaml") and rep["checked"]["services"].endswith("services.yaml"), (rc, out[:300])
        assert rep["summary"]["by_code"]["errors"]["legacy_key"] == 3
        before = open(spec, encoding="utf-8", newline="").read()
        rc, out = run([spec, "--migrate"])
        after = open(spec, encoding="utf-8", newline="").read()
        assert rc == 1 and "MIGRATED" in out, out                  # ends_local is left for a person
        assert after.count("\r\n") == after.count("\n") == before.count("\n"), "line endings changed"
        assert after.startswith("---\r\nasset: SM_Office_Wall_Door_A") and "source: model  # was build\r\n" in after
        assert "material_group: [M_Steel]   # one slot\r\n" in after and "ends_local:" in after
        diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        assert len(diff) == 3, diff                                  # only the three renamed lines differ
        rep = json.loads(run([spec, "--json"])[1])
        assert [f["key"] for f in rep["specs"][0]["errors"] if f["code"].startswith("legacy")] == ["ends_local"]
        assert "MIGRATED" not in run([spec, "--migrate"])[1]       # nothing left to rename
        # a clean spec passes; wildcards are expanded by the script itself
        rc, out = run([other])
        assert rc == 0 and out.rstrip().endswith("PASS"), out
        rc, out = run([os.path.join(proj, "kit", "SM_P*.md")])
        assert rc == 0, out
        assert run([os.path.join(proj, "kit", "nothing*.md")])[0] == 2
        # a metrics row that does not exist is an error once metrics.yaml is found
        bad = write(proj, "kit/SM_Bad.md", GOOD.replace("SM_Office_Wall_Door_A", "SM_Bad").replace("metrics.wall_module", "metrics.gone"))
        rc, out = run([bad, "--out", os.path.join(d, "r.json")])
        assert rc == 1 and "metrics_row" in out and json.load(open(os.path.join(d, "r.json")))["pass"] is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("SELFTEST check_spec PASS")
