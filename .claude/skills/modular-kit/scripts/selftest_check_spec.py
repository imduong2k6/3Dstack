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
form:
  measured_from: ref/C05_rect.png
  sections:
    - name: wall
      box_m: [[-2, 0, 0], [2, 0.15, 3]]
      symmetry: [x]
      circles:
        - {name: peephole, kind: full, center_m: [0, 0, 1.5], axis: y, diameter_m: 0.04, segments: 24, repeat: 6}
      repeats:
        - {name: hinge, count: 3, pitch_m: [0, 0, 0.8]}
      asymmetries:
        - {what: door, evidence: real door off centre in C05, box_m: [[-1.4, 0, 0], [-0.5, 0.15, 2.04]]}
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
    assert cs.pivot_anchor("bottom-left-front") == {"x": "min", "y": "min", "z": "min"}   # the facade modules' pivot (references/facade-pcg.md): bottom-left of the outer face, outer face -Y
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
        ("dir: [1, 0, 0], kind", "dir: [1, 0, 0], role: hole, kind", "port"), ("dir: [1, 0, 0]", "dir: [1, 1, 0]", "port"), ("pos_m: [2, 0, 1.5]", "pos_m: [2, 0]", "port"), ("name: end_b", "name: end_a", "port"),
        ("size_m: [0.15, 3.0]}\n  - {name: end_b", "size_m: [0.15, 3.0, 1]}\n  - {name: end_b", "port"), ("sockets:\n  - {name: hinge_L, pos_m: [-0.45, 0, 0]}", "sockets:\n  - {name: hinge_L}", "socket"),
        ("service_id: null", "service_id: LP99", "service_id"), ("source: model", "source: generate", "missing_key"),
        ("material_group: [upper_wall, trim, door_frames]", "material_group: upper_wall", "type"), ("done_when:\n  - snaps", "done_when: []\nx:\n  - snaps", "type"),
        ("phase: 2", "phase: 12", "type"), ("method: null", "method: sculpt", "enum"),
    ]
    for old, new, want in cases:
        assert old in GOOD, old
        e, _, _ = codes(GOOD.replace(old, new, 1), metrics={"wall_module": {}}, services={"LP01"})
        assert want in e, (old, new, want, e)
    # the form read: every way of getting it wrong, and who is exempt
    for old, new in (("symmetry: [x]", "symmetry: [q]"), ("symmetry: [x]", "symmetry: []"), ("measured_from: ref/C05_rect.png\n", ""),
                     ("box_m: [[-2, 0, 0], [2, 0.15, 3]]", "box_m: [[2, 0, 0], [-2, 0.15, 3]]"), ("segments: 24, repeat: 6", "segments: 26, repeat: 6"),
                     ("segments: 24, repeat: 6", "segments: 18, repeat: 6"), ("kind: full", "kind: round"), ("count: 3", "count: 1"),
                     ("evidence: real door off centre in C05, ", ""), ("axis: y", "axis: q")):
        assert old in GOOD, old
        assert "form" in codes(GOOD.replace(old, new, 1))[0], (old, new)
    assert codes(GOOD.replace("symmetry: [x]", "symmetry: []\n      why_none: a real offset door", 1))[0] == []
    # 6 segments need a reason; other counts that aren't a multiple of 4 stay refused even with one
    assert "form" in codes(GOOD.replace("segments: 24, repeat: 6", "segments: 6, repeat: 6", 1))[0]
    assert codes(GOOD.replace("segments: 24, repeat: 6", "segments: 6, repeat: 6, why_6: no room to retopologise", 1))[0] == []
    assert "form" in codes(GOOD.replace("segments: 24, repeat: 6", "segments: 10, repeat: 1, why_6: no room", 1))[0]
    no_form = GOOD[:GOOD.index("form:\n")] + GOOD[GOOD.index("method: null"):]
    assert "missing_key" in codes(no_form)[0], "a modelled asset needs a form block"
    for old, new in (("method: null", "method: fast_cg"), ("method: null", "method: repair"), ("validation: null", "validation: {pass: true}")):
        assert codes(no_form.replace(old, new, 1))[0] == [], (old, new)
    assert codes(no_form.replace("source: model", "source: library", 1))[0] == []
    # a port role of opening or inset (a bay's opening and what fills it) is fine
    for role in ("end", "opening", "inset"):
        assert codes(GOOD.replace("dir: [1, 0, 0], kind", f"dir: [1, 0, 0], role: {role}, kind", 1))[0] == [], role
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


NEW_KEYS = """slots:
  - {material_group: trim, texture_set: TS_Office_Trim, uv: "trim strips 512 px/m", strips: [S3, S7]}   # frame
  - {material_group: upper_wall, texture_set: TS_Office_Walls, uv: box 512 px/m, strips: null}
asset_tech:    # headless
  fbx: "D:/work/SM_Office_Wall_Door_A.fbx"
  reimport: "PASS: dims off 0 mm"
  tris: 44
  slots: [M_Trim, M_Wall]
  ucx_count: 3
  sockets_exported: [SOCKET_door_set]
  nanite: yes
"""
SUPERSEDED = "---\nasset: SM_Old\ntype: kit\nsuperseded_by: \"SM_New_A (1.00), SM_New_B (0.90)\"   # split, kept\n---\nbody\n"


def test_new_keys():
    # slots, asset_tech and superseded_by pass in a full spec
    full = GOOD.replace("texel_density_px_m: 512\n", "texel_density_px_m: 512\n" + NEW_KEYS, 1).replace("---\nasset:", "---\nsuperseded_by: null\nasset:", 1)
    e, w, _ = codes(full, metrics={"wall_module": {}}, services={"LP01"})
    assert e == [] and w == [], (e, w)
    # an asset marked superseded_by needs no build field: only asset and type
    e, w, _ = codes(SUPERSEDED, "SM_Old.md")
    assert e == [] and w == [], (e, w)
    assert codes(SUPERSEDED.replace('"SM_New_A (1.00), SM_New_B (0.90)"', "[SM_New_A, SM_New_B]"), "SM_Old.md")[0] == []
    # not superseded: the same file is missing its build fields
    e, _, _ = codes(SUPERSEDED.replace("superseded_by:", "superseded_by: null #"), "SM_Old.md")
    assert e.count("missing_key") >= 10, e
    # a superseded spec that still carries build fields has them checked
    assert "dims" in codes(SUPERSEDED.replace("---\nbody", "dims_m: [1, 2]\n---\nbody"), "SM_Old.md")[0]
    # asset and type stay required, and superseded_by must be a line or a list of lines
    assert codes(SUPERSEDED.replace("type: kit\n", ""), "SM_Old.md")[0] == ["missing_key"]
    for bad in ("superseded_by: 5", "superseded_by: []", "superseded_by: [a, 3]"):
        e, _, _ = codes(SUPERSEDED.replace(SUPERSEDED.splitlines()[3], bad), "SM_Old.md")
        assert "type" in e, (bad, e)
    # bad slots and asset_tech
    base = GOOD.replace("texel_density_px_m: 512\n", "texel_density_px_m: 512\n" + NEW_KEYS, 1)
    for old, new, want in (("texture_set: TS_Office_Trim, ", "", "slot"), ("strips: [S3, S7]", "strips: S3", "slot"),
                           ("material_group: upper_wall, texture_set", "material_group: trim, texture_set", "slot"),
                           ("tris: 44", "tris: 0", "type"), ("ucx_count: 3", "ucx_count: -1", "type"), ("slots: [M_Trim, M_Wall]", "slots: M_Trim", "type"),
                           ("asset_tech:    # headless\n  fbx:", "asset_tech: 5\nx:\n  fbx:", "type"),
                           ("slots:\n  - {material_group: trim", "slots: 5\nx:\n  - {material_group: trim", "slot")):
        assert old in base, old
        e, _, _ = codes(base.replace(old, new, 1))
        assert want in e, (old, e)
    _, w, _ = codes(base.replace("material_group: upper_wall, texture_set", "material_group: roof, texture_set", 1))
    assert w == ["slot"], w
    _, w, _ = codes(base.replace("nanite: yes", "nanite: yes\n  made_up: 1", 1))
    assert w == ["unknown_key"], w


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
    legacy = legacy.replace("texel_density_px_m: 512\n", "texel_density_px_m: 512\n" + NEW_KEYS, 1)   # the new blocks must not confuse the rename
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
