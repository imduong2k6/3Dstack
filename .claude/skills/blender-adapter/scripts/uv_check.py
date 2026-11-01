"""UV and texel-density check for one mesh object (tested headless with bpy 5.2.3). selftest_uv_check.py tests it.

It measures, on the object with its modifiers applied: texel density in px per metre at a texture size, the spread of density between
UV islands, flipped and zero-area UV faces, overlap, the gap between islands, how much of the 0-1 tile is used, and hard edges that
are not on a seam. The density is compared with the spec's `texel_density_px_m` within 10 % (modeling/SKILL.md); a spec without one
says "not checked".

In the live Blender:

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/uv_check.py").read())
    print(uv_check("SM_Pipe_A", tex_size=2048, spec=r"<project>/kit/SM_Pipe_A.md", repo=r"<repo>"))

Headless, on the asset's file (exit 0 when it passes, 1 on a failure or an error):

    bash bin/blender-bg <asset.blend> --python uv_check.py -- SM_X [--spec kit/SM_X.md] [--tex-size 2048] [--profile unique|trim] [--uv-map NAME] [--gap-px N] [--repo <repo>] [--out uv.json]

Profiles:
  unique (default)  one unwrap in 0-1 that no other part shares: overlap above 0.1 % of the covered pixels fails
  trim              tiling or trim-sheet piece: overlap and leaving 0-1 are allowed, coverage and gap are not measured; density still counts

Fails: density off the target, flipped UV faces, zero-area UV faces, and (unique) overlap.
Warns only (the user textures later, this is not a bake gate): coverage under 70 %, island gap under tex_size/128 px, hard edges
inside an island, an island off the target density, UVs outside 0-1 (unique).
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np

DENSITY_TOL = 0.10          # modeling/SKILL.md: texel density within 10 % of the project value
OVERLAP_LIMIT_PCT = 0.1     # unique: share of the covered pixels that more than one UV face covers
COVERAGE_MIN = 0.70
ZERO_UV_AREA = 1e-12        # UV area (tile units squared) under which a face has none at all
COLLAPSED = 0.01            # a face whose density is under this share of the median has collapsed in UV, however small it is in 3D
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


def _wpct(v, w, q):
    """Weighted percentile: the first value where the share of the weight reaches q."""
    o = np.argsort(v)
    c = np.cumsum(w[o])
    return float(v[o][min(np.searchsorted(c, q * c[-1]), len(v) - 1)])


def _get(coll, attr, n, dtype, width=1):
    a = np.empty(n * width, dtype=dtype)
    coll.foreach_get(attr, a)
    return a.reshape(-1, width) if width > 1 else a


def _cover(tri, ids, x0, y0, k, res):
    """Pixel centres in k x k windows at (x0, y0) of the triangles tri (n, 3, 2, in pixels): flat indices inside (edges included),
    their island ids, and the flat indices strictly inside (so two faces that share an edge never both count a pixel)."""
    gx = x0[:, None, None] + np.arange(k)[None, None, :]
    gy = y0[:, None, None] + np.arange(k)[None, :, None]
    px, py = gx + 0.5, gy + 0.5
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    area = ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))[:, None, None]

    def side(p, q):     # which side of the edge p-q the pixel centre is on, divided by the triangle's area so all three agree in sign
        return ((q[:, 0] - p[:, 0])[:, None, None] * (py - p[:, 1][:, None, None]) - (q[:, 1] - p[:, 1])[:, None, None] * (px - p[:, 0][:, None, None])) / np.where(area == 0, 1, area)
    w = np.stack([side(a, b), side(b, c), side(c, a)])
    ok = (gx >= 0) & (gx < res) & (gy >= 0) & (gy < res) & (area != 0)
    inc = ok & (w >= -1e-6).all(axis=0)
    strict = ok & (w > 1e-6).all(axis=0)
    flat = gy * res + gx
    ids = np.broadcast_to(ids[:, None, None], flat.shape)
    return flat[inc], ids[inc], flat[strict]


def _raster(tri, ids, res):
    """Rasterise UV triangles (n, 3, 2) in pixels of a res x res tile: (strict cover count, island id of the last face to land, covered)."""
    lo = np.ceil(tri.min(axis=1) - 0.5).clip(0, res).astype(np.int64)
    hi = np.floor(tri.max(axis=1) - 0.5).clip(-1, res - 1).astype(np.int64)
    size = np.maximum((hi - lo + 1).max(axis=1), 0)
    inc, lab, strict = [], [], []
    k = 1
    todo = size > 0
    while todo.any():
        sel = np.nonzero(todo & (size <= k))[0] if k <= 64 else np.nonzero(todo)[0][:1]
        k_here = k if k <= 64 else int(size[sel[0]])
        step = max(1, 400000 // (k_here * k_here))
        for s in range(0, len(sel), step):
            i = sel[s:s + step]
            f, l, st = _cover(tri[i], ids[i], lo[i, 0], lo[i, 1], k_here, res)
            inc.append(f)
            lab.append(l)
            strict.append(st)
        todo[sel] = False
        if k <= 64:
            k *= 2
    inc = np.concatenate(inc) if inc else np.zeros(0, int)
    cnt = np.bincount(np.concatenate(strict) if strict else np.zeros(0, int), minlength=res * res)
    img = np.full(res * res, -1, dtype=np.int64)
    if len(inc):
        img[inc] = np.concatenate(lab)
    return cnt.reshape(res, res), img.reshape(res, res)


def _min_gap(img, cap):
    """Smallest number of empty pixels between two different islands in the label image, or None when it is over cap."""
    res = img.shape[0]
    offs = sorted(((dx, dy) for dx in range(0, cap + 1) for dy in range(-cap, cap + 1) if (dx, dy) > (0, 0) and dx * dx + dy * dy <= cap * cap),
                  key=lambda d: d[0] ** 2 + d[1] ** 2)
    for dx, dy in offs:
        a = img[max(0, -dy):res - max(0, dy), :res - dx]
        b = img[max(0, dy):res - max(0, -dy), dx:]
        if ((a >= 0) & (b >= 0) & (a != b)).any():
            return max(math.sqrt(dx * dx + dy * dy) - 1, 0.0)
    return None


def uv_check(name, tex_size=2048, profile="unique", spec=None, repo=None, uv_map=None, gap_px=None, raster_res=1024):
    if profile not in ("unique", "trim"):
        raise ValueError("profile is unique or trim")
    ob = bpy.data.objects[name]
    if ob.type != "MESH":
        raise ValueError(f"{name} is a {ob.type}: check a mesh object")
    if isinstance(spec, str):
        spec = _find_check_spec(spec, repo).load_spec(spec)
    target = (spec or {}).get("texel_density_px_m")
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    try:
        layer = me.uv_layers[uv_map] if uv_map else me.uv_layers.active
        if layer is None:
            raise ValueError(f"{name} has no UV map")
        lname = layer.name
        me.calc_loop_triangles()
        nf, nl, ne, nt = len(me.polygons), len(me.loops), len(me.edges), len(me.loop_triangles)
        if not nf:
            raise ValueError(f"{name} has no faces")
        m = np.array(ob.matrix_world)
        co = _get(me.vertices, "co", len(me.vertices), np.float32, 3).astype(float) @ m[:3, :3].T * bpy.context.scene.unit_settings.scale_length
        uv = _get(layer.uv, "vector", nl, np.float32, 2).astype(float)
        tl = _get(me.loop_triangles, "loops", nt, np.int32, 3)
        tv = _get(me.loop_triangles, "vertices", nt, np.int32, 3)
        tp = _get(me.loop_triangles, "polygon_index", nt, np.int32)
        start = _get(me.polygons, "loop_start", nf, np.int32)
        total = _get(me.polygons, "loop_total", nf, np.int32)
        lv = _get(me.loops, "vertex_index", nl, np.int32)
        le = _get(me.loops, "edge_index", nl, np.int32)
        sharp = np.zeros(ne, dtype=bool)
        if "sharp_edge" in me.attributes:
            me.attributes["sharp_edge"].data.foreach_get("value", sharp)
    finally:
        ev.to_mesh_clear()

    # area in UV (signed: negative is flipped) and in metres, per face
    u = uv[tl]
    a_uv = np.bincount(tp, 0.5 * ((u[:, 1, 0] - u[:, 0, 0]) * (u[:, 2, 1] - u[:, 0, 1]) - (u[:, 1, 1] - u[:, 0, 1]) * (u[:, 2, 0] - u[:, 0, 0])), minlength=nf)
    p = co[tv]
    a_3d = np.bincount(tp, 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1), minlength=nf)
    real = a_3d > 1e-12                                  # faces with no area in 3D have no density to speak of
    dens = tex_size * np.sqrt(np.abs(a_uv) / np.maximum(a_3d, 1e-18))
    none = real & (np.abs(a_uv) < ZERO_UV_AREA)
    med = _wpct(dens[real & ~none], a_3d[real & ~none], 0.5) if (real & ~none).any() else 0.0
    zero = none | (real & (dens < COLLAPSED * med))
    flipped = real & ~zero & (a_uv < 0)
    live = real & ~zero

    # islands: faces that share an edge whose two ends have the same UV
    face_of_loop = np.repeat(np.arange(nf), total)
    nxt = np.arange(nl) + 1
    nxt[start + total - 1] = start
    order = np.argsort(le, kind="stable")
    es = le[order]
    first = np.nonzero((es[:-1] == es[1:]) & np.r_[True, es[:-2] != es[1:-1]] & np.r_[es[2:] != es[1:-1], True])[0]
    l1, l2 = order[first], order[first + 1]
    same_start = lv[l1] == lv[l2]
    eps = 1e-5
    ok_a = np.where(same_start, np.abs(uv[l1] - uv[l2]).max(axis=1), np.abs(uv[l1] - uv[nxt[l2]]).max(axis=1)) < eps
    ok_b = np.where(same_start, np.abs(uv[nxt[l1]] - uv[nxt[l2]]).max(axis=1), np.abs(uv[nxt[l1]] - uv[l2]).max(axis=1)) < eps
    joined = ok_a & ok_b
    isl = _components(nf, face_of_loop[l1[joined]], face_of_loop[l2[joined]])
    _, isl = np.unique(isl, return_inverse=True)
    isl = isl.ravel()
    n_isl = int(isl.max()) + 1
    on_seam_free = np.zeros(ne, dtype=bool)               # mesh edges inside an island
    on_seam_free[le[l1[joined]]] = True
    hard_inside = int((sharp & on_seam_free).sum())

    rep = {"object": name, "uv_map": lname, "tex_size": tex_size, "profile": profile, "faces": nf, "islands": n_isl}
    failures, warnings = [], []

    # density
    isl_area = np.bincount(isl, a_3d * live, minlength=n_isl)
    isl_uv = np.bincount(isl, np.abs(a_uv) * live, minlength=n_isl)
    isl_ok = isl_area > 0
    isl_d = tex_size * np.sqrt(isl_uv[isl_ok] / isl_area[isl_ok])
    if live.any():
        d = _wpct(dens[live], a_3d[live], 0.5)
        rep["density"] = {"px_per_m": round(d, 1), "island_min_max": [round(float(isl_d.min()), 1), round(float(isl_d.max()), 1)],
                          "island_spread_p95_p05": round(_wpct(isl_d, isl_area[isl_ok], 0.95) / max(_wpct(isl_d, isl_area[isl_ok], 0.05), 1e-9), 2)}
    else:
        d = None
        rep["density"] = {"px_per_m": None}
    if target and d:
        off = d / target - 1
        bad = int((np.abs(isl_d / target - 1) > DENSITY_TOL).sum())
        rep["density"].update(target_px_per_m=target, off_pct=round(off * 100, 1), ok=abs(off) <= DENSITY_TOL, islands_off_target=bad, checked=True)
        if abs(off) > DENSITY_TOL:
            failures.append(f"texel density {d:.0f} px/m is {off * 100:+.1f} % from the spec's {target} (limit 10 %)")
        if bad:
            warnings.append(f"{bad} islands are more than 10 % from the target density")
    else:
        rep["density"].update(ok=True, checked=False, reason="the spec has no texel_density_px_m" if not target else "no face has UV area")
    if flipped.any():
        failures.append(f"{int(flipped.sum())} flipped UV faces")
    if zero.any():
        failures.append(f"{int(zero.sum())} faces with zero UV area")
    rep["flipped_faces"], rep["zero_area_faces"] = int(flipped.sum()), int(zero.sum())
    rep["hard_edges_not_on_seams"] = hard_inside
    if hard_inside:
        warnings.append(f"{hard_inside} hard edges are inside UV islands (no seam there)")

    # layout
    cen = np.stack([np.bincount(face_of_loop, uv[:, k], minlength=nf) / total for k in range(2)], axis=1)
    tile = np.floor(cen + 1e-9)
    outside = np.bincount(face_of_loop, ((uv < tile[face_of_loop] - 1e-5) | (uv > tile[face_of_loop] + 1 + 1e-5)).any(axis=1), minlength=nf) > 0
    rep["faces_outside_0_1"] = int((outside | (tile != 0).any(axis=1)).sum())
    if profile == "trim":
        rep["overlap"] = rep["coverage"] = rep["gap"] = {"checked": False, "reason": "trim profile"}
    else:
        if rep["faces_outside_0_1"]:
            warnings.append(f"{rep['faces_outside_0_1']} UV faces are outside 0-1")
        res = min(tex_size, raster_res)
        ov = cov = 0
        pairs, gap, tiles = 0.0, None, np.unique(tile[live], axis=0)
        need = tex_size / 128.0 if gap_px is None else gap_px
        cap = int(math.ceil(need * res / tex_size)) + 1
        in_ov = set()
        for t in tiles:
            sel = (live[tp]) & (tile[tp] == t).all(axis=1)
            tri = (u[sel] - t) * res
            cnt, img = _raster(tri, isl[tp[sel]], res)
            ov += int((cnt > 1).sum())
            cov += int((img >= 0).sum())
            in_ov |= set(np.unique(img[cnt > 1]).tolist())
            g = _min_gap(img, cap) if n_isl > 1 else None
            if g is not None:
                gap = g * tex_size / res if gap is None else min(gap, g * tex_size / res)
        ov_pct = 100.0 * ov / max(cov, 1)
        rep["overlap"] = {"checked": True, "pct_of_covered": round(ov_pct, 3), "islands_in_overlap": sorted(in_ov)[:10]}
        rep["coverage"] = {"checked": True, "share": round(cov / (res * res * max(len(tiles), 1)), 3)}
        rep["gap"] = {"checked": n_isl > 1, "min_px": None if gap is None else round(gap, 1), "required_px": round(need, 1),
                      "note": None if gap is not None or n_isl < 2 else f"wider than {round(cap * tex_size / res)} px"}
        if ov_pct > OVERLAP_LIMIT_PCT:
            failures.append(f"UV overlap: {ov_pct:.2f} % of the covered pixels (limit {OVERLAP_LIMIT_PCT} %)")
        if rep["coverage"]["share"] < COVERAGE_MIN:
            warnings.append(f"coverage {rep['coverage']['share']:.0%} of the tile (under {COVERAGE_MIN:.0%})")
        if gap is not None and gap < need - 1:
            warnings.append(f"islands are {gap:.1f} px apart (want {need:.0f} px)")
    rep["failures"], rep["warnings"], rep["pass"] = failures, warnings, not failures
    return rep


def main(argv):
    ap = argparse.ArgumentParser(prog="uv_check.py")
    ap.add_argument("name", help="the mesh object to check")
    ap.add_argument("--spec", help="the asset spec, kit/<asset>.md (texel_density_px_m is the target)")
    ap.add_argument("--tex-size", type=int, default=2048, help="texture size in px the density is measured at")
    ap.add_argument("--profile", choices=("unique", "trim"), default="unique")
    ap.add_argument("--uv-map", help="the UV map to check; the active one by default")
    ap.add_argument("--gap-px", type=float, help="wanted gap between islands at the texture size; default tex-size / 128")
    ap.add_argument("--repo", help="the repo folder, when check_spec.py cannot be found from here")
    ap.add_argument("--out", help="write the result as JSON here")
    a = ap.parse_args(argv)
    rep = uv_check(a.name, a.tex_size, a.profile, spec=a.spec, repo=a.repo, uv_map=a.uv_map, gap_px=a.gap_px)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    print("UVCHECK", json.dumps(rep))
    return 0 if rep["pass"] else 1


if any(os.path.basename(a) == "uv_check.py" for a in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except Exception as e:   # Blender exits 0 after an exception under --python
        print("UVCHECK ERROR:", repr(e))
        code = 1
    sys.exit(code)
