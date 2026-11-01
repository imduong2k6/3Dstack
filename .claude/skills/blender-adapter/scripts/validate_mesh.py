"""Validate one mesh object for the modeling checklist, and against its asset spec (tested headless with bpy 5.2.3;
verify in your Blender on the first project). selftest_validate_mesh.py tests it.

In the live Blender (the worker's one writer session):

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/validate_mesh.py").read())
    print(validate("SM_Office_Wall_Door_A", budget_tris=800))
    print(validate("SM_Office_Wall_Door_A", spec=r"<project>/kit/SM_Office_Wall_Door_A.md", repo=r"<repo>"))   # also dims, pivot, materials

Headless, on the asset's file (exit 0 when everything passes, 1 otherwise or on an error):

    bash bin/blender-bg <asset.blend> --python validate_mesh.py -- SM_X [--spec kit/SM_X.md] [--budget-tris N] [--tol-mm MM] [--repo <repo>] [--out validation.json]

It also splits the object (and its mesh children, UCX_ and the other helper parts left out) into connected parts and reports, under `parts`:
coplanar overlapping faces of two parts (z-fighting: makes `pass` false), back-to-back touching faces, parts fully inside another closed part,
and small floating fragments (the last three are warnings). Tolerances are shares of the bounding diagonal (coplanar 0.01 %, touching 0.2 %),
so a decal 0.1 mm proud of a 0.37 m asset is not z-fighting. `pass` is also false when the UV map has no area on most faces, unless
`--stage mesh` says this is the mesh waiting for approval, before UVs exist.

`topology` measures the evaluated mesh: quad share, n-gons and the ones that don't lie flat, thin triangles, high poles, vertices inside flat
areas that shape nothing, and Bevel modifiers with an odd segment count. Warnings only; it never fails `pass`. Read it with the wire captures.

With a spec (a path to the `kit/*.md`, or its parsed front matter as a dict) it also checks:
  - dims: the bounding box of the object and its mesh children (UCX_, UBX_, UCP_, USP_ and SOCKET_ parts left out) against
    `dims_m` [W (X), D (Y), H (Z)], within 1 cm, or within the tolerance a `done_when` line gives for the size ("bounding box
    within 1 mm of dims_m"; the tightest such line wins), or tolerance_m / --tol-mm when given
  - pivot: where the origin sits in that box, per the spec's `pivot` word (bottom-center, top-center, back-face-centre, center,
    corner; see pivot_anchor in modular-kit/scripts/check_spec.py). A word it does not know is reported as not checked
  - materials: no empty slot, one slot per `material_group`, and the groups on the slots (the material's `material_group` custom
    property, else its name without the M_ prefix) are the groups the spec lists
  - the object is named like the spec's `asset`, and `budget_tris` is the budget when none is passed
  - form: for each section with `symmetry`, how far every vertex, mirrored, lands from the section's own surface. Over `tol_mm` (1 mm) fails,
    except inside an `asymmetries` box. `parts` picks the section by material or child object name; a name that matches nothing fails
"""
import argparse
import json
import math
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

_HELPER_PREFIX = ("UCX_", "UBX_", "UCP_", "USP_", "SOCKET_")
_check_spec = None
# parts check, all as shares of the asset's bounding diagonal
_COPLANAR = 1e-4        # two faces this close and parallel sit in one plane (a decal 0.1 mm proud of a 0.37 m asset is 2.5 x this)
_TOUCH = 2e-3           # parts this close count as touching
_WELD = 1e-6            # vertices this close are one vertex
_FRAGMENT_AREA = 0.05   # a detached piece with at most this share of the surface is a floating fragment
_MAX_PARTS = 2000       # more parts than this: the enclosed and floating checks are skipped
_MIRROR_TOL_MM = 1.0    # default for a form section
_MIRROR_SAMPLES = 20000 # vertices tested per section and axis
# topology warnings, provisional: set from the first rerun of the benchmark meter, one asset, so read them with the wire captures
_TOPO_MAX_FACES = 500000
_MIN_QUAD_SHARE = 0.6
_MAX_THIN_TRI_SHARE = 0.15
_THIN_TRI_ASPECT = 10
_MAX_IDLE_SHARE = 0.1
_CLEAR_ROWS = 2         # flat rows beside a curve or edge have a job: they keep poles off the curve and rims regular
_MAX_VALENCE = 8
_MAX_SPACING_DEG = 5.0  # a wide edge left beside a narrow one on a curve reads 8 to 17; a ring evened after a reduction reads under 5
_MAX_BEND = 1.0         # radians: a sharper turn between two edges of a loop is a held edge, not a curve


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


def _components(n, a, b):
    """Connected-component label of each of n nodes, given edges a[i]-b[i]."""
    lab = np.arange(n)
    while True:
        m = np.minimum(lab[a], lab[b])
        new = lab.copy()
        np.minimum.at(new, a, m)
        np.minimum.at(new, b, m)
        new = new[new]
        if np.array_equal(new, lab):
            return lab
        lab = new


def _world_tris(o, dg):
    """Vertices (world, metres), triangles, the face of each triangle and the material name of each face, of the object with its modifiers."""
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    tr = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tr)
    tp = np.empty(len(me.loop_triangles), dtype=np.int32)
    me.loop_triangles.foreach_get("polygon_index", tp)
    mi = np.zeros(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", mi)
    names = np.array([s.material.name if s.material else "" for s in o.material_slots] + [""])
    pm = names[np.minimum(mi, len(names) - 1)]
    ev.to_mesh_clear()
    m = np.array(o.matrix_world)
    return co.reshape(-1, 3).astype(float) @ m[:3, :3].T + m[:3, 3], tr.reshape(-1, 3), tp, pm


def _is_inside(tree, p, step):
    """True when p is inside the closed surface in tree: an odd number of crossings along a skew ray."""
    d, hits = Vector((0.5773, 0.5779, 0.5767)), 0
    for _ in range(64):
        loc = tree.ray_cast(p, d)[0]
        if loc is None:
            break
        hits += 1
        p = loc + d * step
    return hits % 2 == 1


def _parts(ob):
    """Split the object (and its mesh children, colliders left out) into connected parts and look for:
    coplanar overlapping faces of two parts (z-fighting), back-to-back touching faces, parts inside another closed part, and small
    fragments that touch nothing. Tolerances are shares of the bounding diagonal. Locations are world coordinates in metres."""
    objs = [o for o in [ob] + list(ob.children_recursive) if o.type == "MESH" and not o.name.startswith(_HELPER_PREFIX)]
    dg = bpy.context.evaluated_depsgraph_get()
    raw = [_world_tris(o, dg) for o in objs]
    raw = [r for r in raw if len(r[1])]
    if not raw:
        return {"count": 0, "ok": True, "skipped": "no faces to check", "warnings": []}
    allv = np.vstack([r[0] for r in raw])
    diag = float(np.linalg.norm(allv.max(axis=0) - allv.min(axis=0))) or 1.0
    eps, tol, weld = diag * _COPLANAR, diag * _TOUCH, diag * _WELD
    V, T, F, voff, foff = [], [], [], 0, 0
    PM = np.concatenate([r[3] for r in raw])
    for co, tr, tp, pm in raw:                                # weld per object, so the seams of one mesh do not cut it into parts
        _, first, inv = np.unique(np.round(co / weld).astype(np.int64), axis=0, return_index=True, return_inverse=True)
        t = inv.ravel()[tr]
        keep = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
        V.append(co[first])
        T.append(t[keep] + voff)
        F.append(tp[keep] + foff)
        voff, foff = voff + len(first), foff + len(pm)
    V, T, F = np.vstack(V), np.vstack(T), np.concatenate(F)
    nv = len(V)
    lab = _components(nv, np.r_[T[:, 0], T[:, 1]], np.r_[T[:, 1], T[:, 2]])
    uniq, part = np.unique(lab[T[:, 0]], return_inverse=True)
    part, P = part.ravel(), len(uniq)
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    cr = np.cross(B - A, C - A)
    tri_area = 0.5 * np.linalg.norm(cr, axis=1)
    live = tri_area > 1e-18
    nrm = cr / np.maximum(2 * tri_area, 1e-30)[:, None]
    cen = (A + B + C) / 3
    area = np.bincount(part, tri_area, minlength=P)
    order = np.argsort(part, kind="stable")
    starts = np.r_[0, np.cumsum(np.bincount(part, minlength=P))[:-1]]
    lo = np.minimum.reduceat(np.minimum(np.minimum(A, B), C)[order], starts, axis=0)
    hi = np.maximum.reduceat(np.maximum(np.maximum(A, B), C)[order], starts, axis=0)
    ptris = [T[order[s:e]] for s, e in zip(starts, list(starts[1:]) + [len(T)])]
    ekey = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    _, einv, ecnt = np.unique(ekey[:, 0] * nv + ekey[:, 1], return_inverse=True, return_counts=True)
    closed = np.bincount(np.tile(part, 3)[ecnt[einv.ravel()] != 2], minlength=P) == 0

    Vl = V.tolist()
    tree = BVHTree.FromPolygons(Vl, T.tolist())
    same, opp = {}, {}                                    # (face, face) -> (part, part, location), once per pair of faces
    for i in np.nonzero(live)[0]:
        c = Vector(cen[i])
        for loc, hn, j, _ in tree.find_nearest_range(c, eps):
            if part[j] == part[i] or not live[j]:
                continue
            dot = hn.dot(Vector(nrm[i]))
            off = c - loc
            if abs(dot) > 0.999 and (off - hn * off.dot(hn)).length < eps * 0.01:      # the centre lies over the other face
                key = (min(F[i], F[j]), max(F[i], F[j]))
                (same if dot > 0 else opp).setdefault(key, (*sorted((int(part[i]), int(part[j]))), [round(float(x), 4) for x in cen[i]], bool(PM[F[i]] == PM[F[j]])))

    def listing(d):     # same_material: two faces of one material in one plane show no artefact, so those are listed last
        return {"count": len(d), "same_material": sum(v[3] for v in d.values()),
                "examples": [{"parts": [a, b], "at_m": at, "same_material": sm} for a, b, at, sm in sorted(d.values(), key=lambda v: v[3])[:5]]}
    rep = {"count": P, "diagonal_m": round(diag, 4), "coplanar_tol_mm": round(eps * 1000, 4), "touch_tol_mm": round(tol * 1000, 4),
           "z_fighting": listing(same), "back_to_back": listing(opp), "enclosed": {"count": 0, "examples": []},
           "floating": {"count": 0, "examples": []}, "detached_large": 0}
    warnings = []
    if P > _MAX_PARTS:
        warnings.append(f"{P} parts: the enclosed and floating checks were skipped")
    elif P > 1:
        trees = {}

        def ptree(k):
            if k not in trees:
                trees[k] = BVHTree.FromPolygons(Vl, ptris[k].tolist())
            return trees[k]
        link = []
        within = np.all(lo[:, None] >= lo[None] - tol, axis=2) & np.all(hi[:, None] <= hi[None] + tol, axis=2)    # [a, b]: a lies in b's box
        within &= closed[None, :] & (area[:, None] < area[None, :])
        for a, b in zip(*np.nonzero(within)):
            vs = np.unique(ptris[a])
            vs = vs[::max(1, len(vs) // 16)]
            if all(_is_inside(ptree(b), Vector(V[v]), weld) for v in vs):
                rep["enclosed"]["count"] += 1
                rep["enclosed"]["examples"].append({"part": int(a), "inside_part": int(b), "at_m": [round(float(x), 4) for x in (lo[a] + hi[a]) / 2]})
                link.append((a, b))
        near = np.all((lo[:, None] <= hi[None] + tol) & (lo[None] <= hi[:, None] + tol), axis=2)
        for a, b in zip(*np.nonzero(np.triu(near, 1))):
            if ptree(a).overlap(ptree(b)) or any(ptree(y).find_nearest(Vl[v], tol)[0] is not None
                                                 for x, y in ((a, b), (b, a)) for v in np.unique(ptris[x])):
                link.append((a, b))
        link = np.array(link, dtype=int).reshape(-1, 2)
        grp = _components(P, link[:, 0], link[:, 1])
        share = {g: float(area[grp == g].sum() / area.sum()) for g in np.unique(grp)}
        main = max(share, key=share.get)
        body = BVHTree.FromPolygons(Vl, np.vstack([ptris[k] for k in np.nonzero(grp == main)[0]]).tolist())
        for g, s in share.items():
            if g == main:
                continue
            if s > _FRAGMENT_AREA:
                rep["detached_large"] += 1
                continue
            ks = np.nonzero(grp == g)[0]
            vs = np.unique(np.vstack([ptris[k] for k in ks]))
            gap = min(body.find_nearest(Vl[v])[3] for v in vs[::max(1, len(vs) // 32)])
            rep["floating"]["count"] += 1
            rep["floating"]["examples"].append({"parts": [int(k) for k in ks][:5], "at_m": [round(float(x), 4) for x in (lo[ks].min(axis=0) + hi[ks].max(axis=0)) / 2],
                                                "share_of_surface": round(s, 5), "gap_mm": round(float(gap) * 1000, 3)})
        rep["floating"]["examples"] = rep["floating"]["examples"][:5]
        rep["enclosed"]["examples"] = rep["enclosed"]["examples"][:5]
    for key, text in (("back_to_back", "pairs of back-to-back touching faces"), ("enclosed", "parts inside another part"),
                      ("floating", "small floating fragments")):
        if rep[key]["count"]:
            warnings.append(f"{rep[key]['count']} {text}")
    rep["warnings"] = warnings
    rep["ok"] = rep["z_fighting"]["count"] == 0       # only z-fighting fails; the rest are warnings
    return rep


def _meshes(ob):
    return [o for o in [ob] + list(ob.children_recursive) if o.type == "MESH" and not o.name.startswith(_HELPER_PREFIX)]


def _islands(bm):
    """The faces of each edge-connected island."""
    seen = set()
    for first in bm.faces:
        if first in seen:
            continue
        seen.add(first)
        stack, island = [first], []
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        yield island


def _border_edges(island):
    return {e for f in island for e in f.edges if e.is_boundary}


def _bad_subd_ngons(bm):
    """N-gons SubD would spoil: off their plane, touching a face out of it (no support row), or with a centre that can't see every edge, which folds."""
    bad = 0
    for f in bm.faces:
        if len(f.verts) < 5:
            continue
        c, n, tol = f.calc_center_median(), f.normal, 0.002 * max(e.calc_length() for e in f.edges)
        near = {v for u in f.verts for g in u.link_faces for v in g.verts}
        corners = [v.co - c for v in f.verts]
        bad += not (all(abs(n.dot(v.co - c)) <= tol for v in near)
                    and all(n.dot(a.cross(b)) > 0 for a, b in zip(corners, corners[1:] + corners[:1])))
    return bad


def _flipped_faces(bm):
    """Faces wound against recalc_face_normals. On a closed island it knows which side is out. On an open one it picks a side
    by shape, and can pick either, so there only a mixed winding counts; culling captures show a shell that is all inside out."""
    before = {f: f.normal.copy() for f in bm.faces}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    total = 0
    for island in _islands(bm):
        k = sum(1 for f in island if f.normal.dot(before[f]) < 0)
        total += min(k, len(island) - k) if _border_edges(island) else k
    return total


def _spacing_error(v):
    """Degrees of normal error from uneven edges along a loop through v: difference / (3 x radius), the radius read from how far the loop bends out of the surface."""
    worst = 0.0
    for e in v.link_edges:
        for x in v.link_edges:
            if x.index > e.index and not set(x.link_faces) & set(e.link_faces):
                a, b = e.calc_length(), x.calc_length()
                d1, d2 = (v.co - e.other_vert(v).co).normalized(), (x.other_vert(v).co - v.co).normalized()
                bend = abs((d2 - d1).dot(v.normal))
                if bend < _MAX_BEND:
                    worst = max(worst, math.degrees(abs(a - b) * 2 * bend / (3 * max(a + b, 1e-9))))
    return worst


def _topology(ob):
    """Counts on the evaluated mesh with SubD off, so live Mirror and Bevel modifiers count and the cage is what gets read. Warnings only."""
    dg = bpy.context.evaluated_depsgraph_get()
    t = {"faces": 0, "quads": 0, "tris": 0, "ngons": 0, "ngons_not_flat": 0, "thin_tris": 0, "high_poles": 0, "max_valence": 0,
         "verts": 0, "idle_flat_verts": 0, "odd_border_islands": 0, "uneven_on_curves": 0, "max_spacing_deg": 0.0, "odd_bevels": []}
    for o in _meshes(ob):
        t["odd_bevels"] += [f"{o.name}: {m.name} ({m.segments})" for m in o.modifiers if m.type == "BEVEL" and m.segments % 2]
        subd = [m for m in o.modifiers if m.type == "SUBSURF" and m.show_viewport]
        for m in subd:
            m.show_viewport = False
        dg.update()
        ev = o.evaluated_get(dg)
        bm = bmesh.new()
        bm.from_mesh(ev.to_mesh())
        ev.to_mesh_clear()
        for m in subd:
            m.show_viewport = True
        dg.update()
        t["faces"] += len(bm.faces)
        if t["faces"] > _TOPO_MAX_FACES:
            bm.free()
            return {"skipped": f"more than {_TOPO_MAX_FACES} faces", "warnings": []}
        for f in bm.faces:
            k = len(f.verts)
            if k == 3:
                t["tris"] += 1
                es = [e.calc_length() for e in f.edges]
                t["thin_tris"] += max(es) > _THIN_TRI_ASPECT * max(min(es), 1e-9)
            elif k == 4:
                t["quads"] += 1
            else:
                t["ngons"] += 1
                c, tol = f.calc_center_median(), 0.002 * max(e.calc_length() for e in f.edges)
                t["ngons_not_flat"] += any(abs(f.normal.dot(v.co - c)) > tol for v in f.verts)
        t["verts"] += len(bm.verts)
        t["odd_border_islands"] += sum(len(_border_edges(island)) % 2 for island in _islands(bm))
        bm.edges.index_update()
        flat, near = [], set()
        for v in bm.verts:
            fs = v.link_faces
            if not fs or any(e.is_boundary for e in v.link_edges):
                continue
            n = len(v.link_edges)
            t["high_poles"] += n >= 6
            t["max_valence"] = max(t["max_valence"], n)
            spacing = _spacing_error(v) if n == 4 else 0.0     # a pole has no straight loop through it
            t["max_spacing_deg"] = round(max(t["max_spacing_deg"], spacing), 2)
            t["uneven_on_curves"] += spacing > _MAX_SPACING_DEG
            if len({f.material_index for f in fs}) == 1 and all(f.normal.dot(fs[0].normal) > 0.9998 for f in fs):      # within about 1 degree
                flat.append(v)
            else:
                near.add(v)
        for _ in range(_CLEAR_ROWS):
            near |= {e.other_vert(v) for v in near for e in v.link_edges}
        t["idle_flat_verts"] += sum(v not in near for v in flat)
        bm.free()
    t["quad_share"] = round(t["quads"] / max(t["faces"], 1), 3)
    t["thin_tri_share"] = round(t["thin_tris"] / max(t["tris"], 1), 3)
    t["idle_share"] = round(t["idle_flat_verts"] / max(t["verts"], 1), 3)
    w = []
    if t["quad_share"] < _MIN_QUAD_SHARE:
        w.append(f"only {t['quad_share']:.0%} quads: keep a mostly-quad source and triangulate at export")
    if t["ngons_not_flat"]:
        w.append(f"{t['ngons_not_flat']} n-gons don't lie flat: their shading depends on how the engine triangulates them")
    if t["thin_tri_share"] > _MAX_THIN_TRI_SHARE:
        w.append(f"{t['thin_tri_share']:.0%} of the triangles are thin")
    if t["idle_share"] > _MAX_IDLE_SHARE:
        w.append(f"{t['idle_share']:.0%} of the vertices sit inside flat areas, more than {_CLEAR_ROWS} rows from any curve or edge: a grid on a flat face, or loops that end nowhere")
    if t["odd_border_islands"]:
        w.append(f"{t['odd_border_islands']} islands have an odd number of border edges: they can't be all quads until one border vertex is added or removed")
    if t["uneven_on_curves"]:
        w.append(f"{t['uneven_on_curves']} vertices on a curve have uneven edges along a loop, up to about {t['max_spacing_deg']:.0f} degrees of normal error: even the ring straight after the reduction, then look at --modes reflect")
    if t["max_valence"] > _MAX_VALENCE:
        w.append(f"a vertex with {t['max_valence']} edges")
    if t["odd_bevels"]:
        w.append("Bevel modifiers with odd segments: " + ", ".join(t["odd_bevels"]))
    t["warnings"] = w
    return t


def _form(ob, form):
    """The measured mirror check: each vertex of a section, mirrored, against the section's own surface, in the asset's frame."""
    dg = bpy.context.evaluated_depsgraph_get()
    inv = np.array(ob.matrix_world.inverted())
    raw = [(o, *_world_tris(o, dg)) for o in _meshes(ob)]
    rep = {"sections": [], "ok": True}
    for s in form.get("sections") or []:
        names = [str(p).lower() for p in s.get("parts") or []]
        V, T, off = [], [], 0
        for o, co, tr, tp, pm in raw:
            keep = np.ones(len(tr), bool)
            if names:
                by_mat = np.array([any(n in str(m).lower() for n in names) for m in pm], bool)[tp] if len(pm) else np.zeros(len(tr), bool)
                keep = by_mat | (o is not ob and any(n in o.name.lower() for n in names))
            if keep.any():
                V.append(co @ inv[:3, :3].T + inv[:3, 3])
                T.append(tr[keep] + off)
                off += len(co)
        row = {"name": s.get("name"), "axes": {}, "ok": True}
        if not T and s.get("symmetry"):
            row.update(ok=False, reason=f"parts {s.get('parts')} match no material or child object")
        elif T:
            V, T = np.vstack(V), np.vstack(T)
            tree = BVHTree.FromPolygons(V.tolist(), T.tolist())
            pts = V[np.unique(T)]
            pts = pts[::max(1, len(pts) // _MIRROR_SAMPLES)]
            tol = float(s.get("tol_mm") or _MIRROR_TOL_MM)
            boxes = [np.array(a["box_m"], float) for a in s.get("asymmetries") or []]
            for ax in s.get("symmetry") or []:
                i = "xyz".index(ax)
                mir = pts.copy()
                mir[:, i] = 2 * float((s.get("plane_m") or {}).get(ax, 0)) - mir[:, i]
                free = np.zeros(len(pts), bool)
                for b in boxes:        # skip what the listed asymmetry covers, and its other side
                    free |= np.all((pts >= b[0] - 1e-4) & (pts <= b[1] + 1e-4), axis=1) | np.all((mir >= b[0] - 1e-4) & (mir <= b[1] + 1e-4), axis=1)
                d = np.array([tree.find_nearest(Vector(p))[3] for p in mir[~free]]) * 1000 if (~free).any() else np.zeros(1)
                worst = pts[~free][int(np.argmax(d))] if (~free).any() else pts[0]
                row["axes"][ax] = {"median_mm": round(float(np.median(d)), 3), "p95_mm": round(float(np.percentile(d, 95)), 3), "max_mm": round(float(d.max()), 3),
                                   "worst_at_m": [round(float(x), 4) for x in worst], "skipped_as_asymmetry": int(free.sum()), "tol_mm": tol, "ok": bool(d.max() <= tol)}
            row["ok"] = all(a["ok"] for a in row["axes"].values())
        rep["sections"].append(row)
        rep["ok"] = rep["ok"] and row["ok"]
    return rep


def _uv_zero_share(me):
    """Share of the faces with no area in the active UV map; None when the mesh has no UV map. Needs calc_loop_triangles() done."""
    if not me.uv_layers:
        return None
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.uv.foreach_get("vector", uv)
    k = len(me.loop_triangles)
    tl = np.empty(k * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("loops", tl)
    tp = np.empty(k, dtype=np.int32)
    me.loop_triangles.foreach_get("polygon_index", tp)
    u = uv.reshape(-1, 2).astype(float)[tl.reshape(-1, 3)]
    a = 0.5 * ((u[:, 1, 0] - u[:, 0, 0]) * (u[:, 2, 1] - u[:, 0, 1]) - (u[:, 1, 1] - u[:, 0, 1]) * (u[:, 2, 0] - u[:, 0, 0]))
    return float((np.abs(np.bincount(tp, a, minlength=len(me.polygons))) < 1e-12).mean()) if len(me.polygons) else 0.0


def validate(name, budget_tris=None, merge_dist=0.0001, spec=None, repo=None, tolerance_m=None, stage="final"):
    if stage not in ("mesh", "final"):
        raise ValueError(f"stage is mesh or final, not {stage}")
    ob = bpy.data.objects[name]
    if ob.type != "MESH":
        raise ValueError(f"{name} is a {ob.type}: validate a mesh object")
    if isinstance(spec, str):
        spec_file, spec = spec, _find_check_spec(spec, repo).load_spec(spec)
    else:
        spec_file = None
    if spec and budget_tris is None and isinstance(spec.get("budget_tris"), int):
        budget_tris = spec["budget_tris"]
    out = {"object": name, "stage": stage}
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
    out["ngons_under_subd"] = _bad_subd_ngons(bm) if has_subd else 0
    out["flipped_faces"] = _flipped_faces(bm)
    bm.free()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg).to_mesh()
    ev.calc_loop_triangles()
    out["tris_evaluated"] = len(ev.loop_triangles)
    out["uv_zero_area_share"] = _uv_zero_share(ev)
    ob.evaluated_get(dg).to_mesh_clear()
    out["uv_layers"] = [uv.name for uv in ob.data.uv_layers]
    out["materials"] = [s.material.name if s.material else None for s in ob.material_slots]
    out["parts"] = _parts(ob)
    out["topology"] = _topology(ob)
    # a UV map must exist and most faces must have area in it, once the mesh is past approval
    uv_ok = stage == "mesh" or (bool(out["uv_layers"]) and (out["uv_zero_area_share"] or 0.0) <= 0.5)
    checks = [out["transforms_applied"], out["non_manifold_edges"] == 0, out["duplicate_verts"] == 0,
              out["ngons_under_subd"] == 0, out["flipped_faces"] == 0, uv_ok, out["parts"]["ok"]]
    if spec and isinstance(spec.get("form"), dict):
        out["form"] = _form(ob, spec["form"])
        checks.append(out["form"]["ok"])
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
    ap.add_argument("--stage", choices=("mesh", "final"), default="final", help="mesh: waiting for approval, UVs not made yet")
    ap.add_argument("--out", help="write the result as JSON here")
    a = ap.parse_args(argv)
    rep = validate(a.name, a.budget_tris, a.merge_dist, spec=a.spec, repo=a.repo, tolerance_m=a.tol_mm / 1000 if a.tol_mm else None, stage=a.stage)
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
