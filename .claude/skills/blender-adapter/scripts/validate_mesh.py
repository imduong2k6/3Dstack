"""Validate one mesh object for the modeling checklist, and against its asset spec (tested headless with bpy 5.2.3;
verify in your Blender on the first project). selftest_validate_mesh.py tests it.

In the live Blender (the worker's one writer session):

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/validate_mesh.py").read())
    print(validate("SM_Office_Wall_Door_A", budget_tris=800))
    print(validate("SM_Office_Wall_Door_A", spec=r"<project>/kit/SM_Office_Wall_Door_A.md", repo=r"<repo>"))   # also dims, pivot, materials

Headless, on the asset's file (exit 0 when everything passes, 1 otherwise or on an error):

    bash bin/blender-bg <asset.blend> --python validate_mesh.py -- SM_X [--spec kit/SM_X.md] [--budget-tris N] [--tol-mm MM] [--repo <repo>] [--out validation.json]

With a spec (a path to the `kit/*.md`, or its parsed front matter as a dict) it also checks:
  - dims: the bounding box of the object and its mesh children (UCX_, UBX_, UCP_, USP_ and SOCKET_ parts left out) against
    `dims_m` [W (X), D (Y), H (Z)], within 1 cm, or within the tolerance a `done_when` line gives for the size ("bounding box
    within 1 mm of dims_m"; the tightest such line wins), or tolerance_m / --tol-mm when given
  - pivot: where the origin sits in that box, per the spec's `pivot` word (bottom-center, top-center, back-face-centre, center,
    corner; see pivot_anchor in modular-kit/scripts/check_spec.py). A word it does not know is reported as not checked
  - materials: no empty slot, one slot per `material_group`, and the groups on the slots (the material's `material_group` custom
    property, else its name without the M_ prefix) are the groups the spec lists
  - the object is named like the spec's `asset`, and `budget_tris` is the budget when none is passed
"""
import argparse
import json
import os
import re
import sys

import bmesh
import bpy
import numpy as np

_HELPER_PREFIX = ("UCX_", "UBX_", "UCP_", "USP_", "SOCKET_")
_check_spec = None


def _find_check_spec(spec_path=None, repo=None):
    """check_spec.py is in the modular-kit skill: look next to this file, in repo, up from the working folder and from the spec."""
    global _check_spec
    if _check_spec is not None:
        return _check_spec
    import importlib.util
    here = globals().get("__file__")      # not set when the live Blender exec()s this file
    starts = [os.path.join(os.path.dirname(here), "..", "..", "..", "..")] if here else []
    starts += [repo] if repo else []
    for s in (os.getcwd(), os.path.dirname(os.path.abspath(spec_path)) if isinstance(spec_path, str) else None):
        while s and os.path.dirname(s) != s:
            starts.append(s)
            s = os.path.dirname(s)
    for root in starts:
        p = os.path.join(root, ".claude", "skills", "modular-kit", "scripts", "check_spec.py")
        if os.path.exists(p):
            sp = importlib.util.spec_from_file_location("check_spec", p)
            _check_spec = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(_check_spec)
            return _check_spec
    raise ValueError("cannot find .claude/skills/modular-kit/scripts/check_spec.py: pass repo=<repo folder>")


def _bbox(ob):
    """Min and max corner of the object and its mesh children, in the object's frame, in metres (scale applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    inv = ob.matrix_world.inverted()
    pts = []
    for o in [ob] + list(ob.children_recursive):
        if o.type != "MESH" or o.name.startswith(_HELPER_PREFIX):
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        a = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", a)
        m = np.array(inv @ o.matrix_world)
        pts.append(a.reshape(-1, 3).astype(float) @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    p = np.vstack(pts) * np.array(ob.matrix_world.to_scale())
    return p.min(axis=0), p.max(axis=0)


def _tolerance_m(spec, default=0.01):
    """The tightest `within N mm|cm|m` on a done_when line that is about the size; else the default (1 cm)."""
    best = None
    for line in spec.get("done_when") or []:
        s = str(line).lower()
        if re.search(r"dims_m|bounding box|bbox|overall size|dimensions", s):
            for num, unit in re.findall(r"within\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)\b", s):
                v = float(num) * {"mm": 0.001, "cm": 0.01, "m": 1.0}[unit]
                best = v if best is None else min(best, v)
    return best, (best if best is not None else default)


def _group(mat):
    g = mat.get("material_group") or mat.name
    return g[2:] if g.startswith("M_") else g


def _spec_report(ob, spec, repo, tolerance_m):
    cs = _find_check_spec(None, repo)
    lo, hi = _bbox(ob)
    dims = hi - lo
    done_tol, tol = _tolerance_m(spec)
    source = "done_when" if done_tol is not None else "default 1 cm"
    if tolerance_m is not None:
        tol, source = tolerance_m, "argument"
    rep = {"tolerance_mm": round(tol * 1000, 3), "tolerance_from": source}
    checks = []
    name_ok = spec.get("asset") in (None, ob.name)
    rep["asset"] = {"spec": spec.get("asset"), "object": ob.name, "ok": name_ok}
    checks.append(name_ok)
    exp = spec.get("dims_m")
    if isinstance(exp, list) and len(exp) == 3:
        off = [round(float(d - e) * 1000, 3) + 0.0 for d, e in zip(dims, exp)]
        ok = all(abs(o) <= tol * 1000 + 1e-6 for o in off)
        rep["dims"] = {"expected_m": exp, "actual_m": [round(float(d), 4) for d in dims], "off_mm": off, "ok": ok}
        checks.append(ok)
    else:
        rep["dims"] = {"ok": False, "reason": "the spec has no dims_m of three numbers"}
        checks.append(False)
    anchor = cs.pivot_anchor(spec.get("pivot")) if spec.get("pivot") else None
    if anchor is None:
        rep["pivot"] = {"pivot": spec.get("pivot"), "checked": False, "reason": "not a pivot word validate_mesh can check", "ok": True}
    else:
        axes = {}
        for i, ax in enumerate("xyz"):
            if ax in anchor:
                target = {"min": lo[i], "max": hi[i], "center": (lo[i] + hi[i]) / 2}[anchor[ax]]
                axes[ax] = {"origin_at": anchor[ax], "origin_off_mm": round(float(-target) * 1000, 3) + 0.0}     # + when the origin lies on the + side of where it belongs
        ok = all(abs(v["origin_off_mm"]) <= tol * 1000 + 1e-6 for v in axes.values())
        rep["pivot"] = {"pivot": spec["pivot"], "checked": True, "axes": axes, "ok": ok}
        checks.append(ok)
    want = spec.get("material_group")
    want = [want] if isinstance(want, str) else list(want or [])
    parts = [o for o in [ob] + list(ob.children_recursive) if o.type == "MESH" and not o.name.startswith(_HELPER_PREFIX)]
    per_part = [[_group(s.material) if s.material else None for s in o.material_slots] for o in parts]
    groups = sorted({g for p in per_part for g in p if g})
    want_g = [g[2:] if g.startswith("M_") else g for g in want]
    empty = sum(g is None for p in per_part for g in p)
    missing, extra = sorted(set(want_g) - set(groups)), sorted(set(groups) - set(want_g))
    dup = sorted({g for p in per_part for g in p if g and p.count(g) > 1})
    ok = bool(want_g) and not (empty or missing or extra or dup)
    rep["materials"] = {"slots": [[s.material.name if s.material else None for s in o.material_slots] for o in parts], "groups": groups,
                        "expected_groups": want_g, "empty_slots": empty, "missing_groups": missing, "extra_groups": extra,
                        "groups_on_two_slots": dup, "ok": ok}
    checks.append(ok)
    rep["ok"] = all(checks)
    return rep


def validate(name, budget_tris=None, merge_dist=0.0001, spec=None, repo=None, tolerance_m=None):
    ob = bpy.data.objects[name]
    if ob.type != "MESH":
        raise ValueError(f"{name} is a {ob.type}: validate a mesh object")
    if isinstance(spec, str):
        spec_file, spec = spec, _find_check_spec(spec, repo).load_spec(spec)
    else:
        spec_file = None
    if spec and budget_tris is None and isinstance(spec.get("budget_tris"), int):
        budget_tris = spec["budget_tris"]
    out = {"object": name}
    out["transforms_applied"] = (all(abs(s - 1) < 1e-6 for s in ob.scale)
                                 and all(abs(a) < 1e-6 for a in ob.rotation_euler))
    out["dimensions_m"] = [round(d, 4) for d in ob.dimensions]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out["non_manifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    out["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
    out["duplicate_verts"] = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=merge_dist)["targetmap"])
    has_subd = any(m.type == "SUBSURF" for m in ob.modifiers)
    out["ngons"] = sum(1 for f in bm.faces if len(f.verts) > 4)
    out["ngons_under_subd"] = out["ngons"] if has_subd else 0
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out["flipped_faces"] = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0)
    bm.free()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg).to_mesh()
    ev.calc_loop_triangles()
    out["tris_evaluated"] = len(ev.loop_triangles)
    ob.evaluated_get(dg).to_mesh_clear()
    out["uv_layers"] = [uv.name for uv in ob.data.uv_layers]
    out["materials"] = [s.material.name if s.material else None for s in ob.material_slots]
    checks = [out["transforms_applied"], out["non_manifold_edges"] == 0, out["duplicate_verts"] == 0,
              out["ngons_under_subd"] == 0, out["flipped_faces"] == 0, bool(out["uv_layers"])]
    if budget_tris:
        out["within_budget"] = out["tris_evaluated"] <= budget_tris
        checks.append(out["within_budget"])
    if spec:
        out["spec"] = _spec_report(ob, spec, repo, tolerance_m)
        out["spec"]["file"] = spec_file
        checks.append(out["spec"]["ok"])
    out["pass"] = all(checks)
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="validate_mesh.py")
    ap.add_argument("name", help="the mesh object to validate")
    ap.add_argument("--spec", help="the asset spec, kit/<asset>.md")
    ap.add_argument("--budget-tris", type=int)
    ap.add_argument("--merge-dist", type=float, default=0.0001)
    ap.add_argument("--tol-mm", type=float, help="size and pivot tolerance; the default is the spec's done_when, else 10 mm")
    ap.add_argument("--repo", help="the repo folder, when check_spec.py cannot be found from here")
    ap.add_argument("--out", help="write the result as JSON here")
    a = ap.parse_args(argv)
    rep = validate(a.name, a.budget_tris, a.merge_dist, spec=a.spec, repo=a.repo, tolerance_m=a.tol_mm / 1000 if a.tol_mm else None)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    print("VALIDATE", json.dumps(rep))
    return 0 if rep["pass"] else 1


if any(os.path.basename(a) == "validate_mesh.py" for a in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except Exception as e:   # Blender exits 0 after an exception under --python
        print("VALIDATE ERROR:", repr(e))
        code = 1
    sys.exit(code)
