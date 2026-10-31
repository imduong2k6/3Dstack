"""Join built kit pieces at their ports and check the seams (headless Blender, tested with 5.2.3). Writes nothing to the .blend files.

    bash bin/blender-bg [scene.blend] --python .claude/skills/modular-kit/scripts/kit_joint_test.py -- \
        --specs kit/*.md [--assets-dir <work_dir>/assets] [--pairs SM_A.end_b:SM_B.end_a ...] [--kinds wall_4m,pipe_45] \
        [--tol-mm 1] [--skip-missing] [--out joints.json]

Per the Ports paragraph of the modular-kit skill, a port is the centre of an open end (`pos_m`), its outward unit normal
(`dir`), the family it may join (`kind`) and its section (`size_m`: [d] round, [w, h] rectangular), all in the piece's local
frame. Each spec's mesh is found as the object named like the asset in the open file (with its mesh children), else in
`<assets-dir>/<asset>/<asset>.blend`, `<assets-dir>/<asset>.blend` or the spec's `file`. A piece with no mesh is an error
(a warning with --skip-missing). Objects named UCX_, UBX_, UCP_, USP_ or SOCKET_ and `<asset>_LOD*` are not part of the mesh.

Each port is checked on its own mesh: the mesh must end on the port plane (not short of it, not past it), the open end ring
(the vertices within the tolerance of the end) must be centred on `pos_m`, and its size must equal `size_m` (a round end by its
diameter, a rectangular end by its two sides in either order). A `dir` that points into the piece is reported as such.
Then every unordered pair of ports with the same kind (a piece with itself included) is joined: the second piece is moved so
its port sits on the first one's and faces it (a rectangular end is tried at 0 and 90 degrees, the better one counts), and the
pair passes only when the positions meet within the tolerance, the directions oppose, the specs' sections match, the end rings
match and the seam has no gap or overlap beyond the tolerance. A pair that includes a port that failed on its own is not
repeated. Ports whose kind appears on only one port are listed as unmated (a warning). Units: one Blender unit is one metre.

Opening and inset ports (a door or window in a bay's opening). A wall bay's port on the face an opening is cut in has `role: opening`
(or a name that starts with `opening`), the door or window that fills it has `role: inset` (or a name that starts with `reveal` or
`inset`); every other port is an `end`. The face of such a port is not an open end, so it is not read whole: an opening port reads the
rim of the declared opening (the vertices on the port plane within a band of the `size_m` outline, centred on `pos_m`), an inset port
the outer outline of its face. Then every opening is joined with every inset piece of the same kind: the inset piece is moved so its
port frame lies on the opening's (same direction, the same face), and the pair passes only when the inset's outline is the opening
(centre and section within the tolerance) and nothing of the inset between the host's two faces lies outside the opening (vertices and
points along its edges; a flange proud of the face is not between them). Openings join only insets, ends only ends.

A piece that stands on the face round a hole (a surface-mounted door frame, a louvre on a wall) has `role: surface`: `pos_m` the hole's
centre on the face, `dir` the face's outward normal, `size_m` the hole, so its mesh lies on the +dir side of the port. It joins an opening
of its kind by the same test as an inset; its back beyond the hole stands on the wall and is not read.

Exit 1 when any port or pair fails, or a spec or mesh cannot be used. JSON report with --out; the last stdout line is
`KIT_JOINT {...}` with the summary, and the lines before it name each failure.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_spec  # noqa: E402

SKIP_PREFIX = ("UCX_", "UBX_", "UCP_", "USP_", "SOCKET_")


class JointError(Exception):
    pass


# ---- geometry (numpy only) ---------------------------------------------------

def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def frame(d):
    """(w, h, d): a right-handed frame whose third axis is d; w is horizontal for any port that is not vertical."""
    d = unit(d)
    up = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.999 else np.array([1.0, 0.0, 0.0])
    w = unit(np.cross(up, d))
    return w, np.cross(d, w), d


def ring_of(verts, d, tol_m):
    """The open end: the vertices within tol of the furthest point along d."""
    t = verts @ d
    return verts[t >= t.max() - tol_m]


def section_in(ring, w, h):
    """Centre (in w, h), the two sides and the largest radius about the centre of a set of end vertices."""
    cw, ch = ring @ w, ring @ h
    mid = np.array([(cw.min() + cw.max()) / 2, (ch.min() + ch.max()) / 2])
    return {"centre": mid, "extent": np.array([np.ptp(cw), np.ptp(ch)]), "radius": float(np.max(np.hypot(cw - mid[0], ch - mid[1])))}


def section(ring, d):
    return section_in(ring, *frame(d)[:2])


def port_role(p):
    """end (a joint between pieces), opening (a hole in a face: a door or window bay) or inset (the piece that fills one): the port's
    `role`, else read from its name (opening*, reveal*, inset*)."""
    if p.get("role"):
        return p["role"]
    m = re.match(r"(opening|reveal|inset)", str(p["name"]).lower())
    return "end" if not m else "opening" if m.group(1) == "opening" else "inset"


def port_info(p):
    return {"name": p["name"], "kind": p["kind"], "pos": np.array(p["pos_m"], dtype=float), "dir": unit(p["dir"]),
            "size": [float(x) for x in p["size_m"]], "shape": "round" if len(p["size_m"]) == 1 else "rect", "role": port_role(p)}


def rim_of(verts, p, tol_m):
    """The vertices that outline a port's declared opening: those on the port plane within a band of the size_m outline (the outline
    may be given in either order). Returns (vertices, nearest): the vertices are empty when none is that close, and nearest is then
    how far the closest vertex of the plane is from the outline in metres (None when no vertex is on the plane at all). Inside an
    opening there is no vertex, and the wall around it is farther than the band, so the opening port reads its rim; an inset port
    reads its outer outline (the lining inside is nearer the centre, and extents come from the outermost vertices)."""
    w, h, d = frame(p["dir"])
    on = verts[np.abs(verts @ d - p["pos"] @ d) <= tol_m]
    if not len(on):
        return on, None
    x, y = on @ w - p["pos"] @ w, on @ h - p["pos"] @ h
    band = max(3 * tol_m, 0.02 * min(p["size"]))
    if p["shape"] == "round":
        s = np.abs(np.hypot(x, y) - p["size"][0] / 2)
    else:
        s = None
        for sw, sh in (p["size"], p["size"][::-1]):
            e = np.abs(np.maximum(np.abs(x) - sw / 2, np.abs(y) - sh / 2))
            if p["role"] == "surface":                                  # its back beyond the hole stands on the wall: the ring is what lies round the hole
                e[(np.abs(x) > sw / 2 + tol_m) | (np.abs(y) > sh / 2 + tol_m)] = np.inf
            k = e <= band
            if k.any() and abs(np.ptp(x[k]) - sw) <= band and abs(np.ptp(y[k]) - sh) <= band:     # a whole outline: on a near-square piece the bars can crowd the other order's band
                s = e
                break
            s = e if s is None or k.sum() > (s <= band).sum() else s
    return on[s <= band], float(s.min())


def sizes_match(a, b, tol_m):
    return a["shape"] == b["shape"] and all(abs(x - y) <= tol_m for x, y in zip(sorted(a["size"]), sorted(b["size"])))


def check_rim_port(verts, p, tol_mm):
    """An opening or inset port against its own mesh: its face lies on the port plane, and the outline of the declared opening in it is
    centred on pos_m and as large as size_m says. The rest of the face (the wall around an opening, the lining inside an inset) is not read."""
    tol_m, d, pos = tol_mm / 1000, p["dir"], p["pos"]
    w, h, _ = frame(d)
    t = verts @ d
    plane = float(pos @ d)
    gap = float(np.min(np.abs(t - plane))) * 1000                  # how far the nearest vertex is off the port plane
    rim, near = rim_of(verts, p, tol_m)
    pr, measured, off = [], [], 0.0
    if p["role"] == "surface" and float(t.max()) <= plane + tol_m:
        pr.append("nothing stands proud of the port plane: a surface port's dir is the face's outward normal, into the piece")
    elif p["role"] != "surface" and plane < (float(t.min()) + float(t.max())) / 2:
        pr.append("dir points into the piece (the mesh lies on the +dir side of the port plane)")
    elif near is None:
        pr.append(f"no mesh vertex on the port plane (the nearest is {gap:.2f} mm off it)")
    elif not len(rim):
        pr.append(f"no vertex of the face is within {max(3 * tol_m, 0.02 * min(p['size'])) * 1000:.0f} mm of the declared outline "
                  f"(the nearest is {near * 1000:.2f} mm off it)")
    else:
        sec = section_in(rim, w, h)
        off = float(np.hypot(sec["centre"][0] - pos @ w, sec["centre"][1] - pos @ h)) * 1000
        if off > tol_mm:
            pr.append(f"{'opening' if p['role'] == 'opening' else 'outline'} is {off:.2f} mm off pos_m")
        if p["shape"] == "round":
            measured = [round(2 * sec["radius"] * 1000, 3)]
            if abs(measured[0] - p["size"][0] * 1000) > tol_mm:
                pr.append(f"{p['role']} diameter is {measured[0]:.2f} mm, size_m says {p['size'][0] * 1000:.2f} mm")
        else:
            measured = sorted(round(float(x) * 1000, 3) for x in sec["extent"])
            if any(abs(m - s * 1000) > tol_mm for m, s in zip(measured, sorted(p["size"]))):
                pr.append(f"{p['role']} is {measured[0]:.2f} x {measured[1]:.2f} mm, size_m says "
                          f"{sorted(p['size'])[0] * 1000:.2f} x {sorted(p['size'])[1] * 1000:.2f} mm")
    return {"port": p["name"], "kind": p["kind"], "role": p["role"], "ok": not pr, "end_gap_mm": round(gap, 3) + 0.0,
            "centre_off_mm": round(off, 3) + 0.0, "section_mm": measured, "problems": pr}


def check_port(verts, p, tol_mm):
    """One port against its own mesh. Returns the measurements and a list of problems."""
    if p["role"] != "end":
        return check_rim_port(verts, p, tol_mm)
    tol_m, d, pos = tol_mm / 1000, p["dir"], p["pos"]
    t = verts @ d
    plane, t_max = float(pos @ d), float(t.max())
    gap = (plane - t_max) * 1000                       # + the mesh stops short of the port plane, - it passes it
    sec = section(ring_of(verts, d, tol_m), d)
    w, h, _ = frame(d)
    off = float(np.hypot(sec["centre"][0] - pos @ w, sec["centre"][1] - pos @ h)) * 1000
    pr = []
    if plane < (float(t.min()) + t_max) / 2:
        pr.append("dir points into the piece (the mesh lies on the +dir side of the port plane)")
    elif abs(gap) > tol_mm:
        pr.append(f"mesh stops {gap:.2f} mm short of the port plane" if gap > 0 else f"mesh passes the port plane by {-gap:.2f} mm")
    if off > tol_mm:
        pr.append(f"open end is {off:.2f} mm off pos_m")
    if p["shape"] == "round":
        measured = [round(2 * sec["radius"] * 1000, 3)]
        if abs(measured[0] - p["size"][0] * 1000) > tol_mm:
            pr.append(f"open end diameter is {measured[0]:.2f} mm, size_m says {p['size'][0] * 1000:.2f} mm")
    else:
        measured = sorted(round(float(x) * 1000, 3) for x in sec["extent"])
        if any(abs(m - s * 1000) > tol_mm for m, s in zip(measured, sorted(p["size"]))):
            pr.append(f"open end is {measured[0]:.2f} x {measured[1]:.2f} mm, size_m says "
                      f"{sorted(p['size'])[0] * 1000:.2f} x {sorted(p['size'])[1] * 1000:.2f} mm")
    return {"port": p["name"], "kind": p["kind"], "ok": not pr, "end_gap_mm": round(gap, 3) + 0.0, "centre_off_mm": round(off, 3) + 0.0,
            "section_mm": measured, "problems": pr}


def place(pa, pb, spin, inset=False):
    """Rotation that takes port b's frame onto port a's, facing it, or for an inset piece lying the same way as the opening
    (spin 1 turns a rectangular end a quarter turn)."""
    wa, ha, da = frame(pa["dir"])
    wb, hb, db = frame(pb["dir"])
    if inset:
        target = np.column_stack([wa, ha, da]) if spin == 0 else np.column_stack([ha, -wa, da])
    else:
        target = np.column_stack([wa, -ha, -da]) if spin == 0 else np.column_stack([ha, wa, -da])
    return target @ np.column_stack([wb, hb, db]).T


def check_pair(va, pa, vb, pb, tol_mm):
    """Join piece b to piece a at their ports and measure the seam. va, vb are the meshes' vertices in each piece's frame."""
    tol_m, n = tol_mm / 1000, pa["dir"]
    w, h, _ = frame(n)
    pr = []
    if not sizes_match(pa, pb, tol_m):
        pr.append(f"specs differ in section: {pa['shape']} {pa['size']} against {pb['shape']} {pb['size']}")
    ring_a = section_in(ring_of(va, n, tol_m), w, h)
    best = None
    for spin in ((0,) if pa["shape"] == "round" else (0, 1)):
        rot = place(pa, pb, spin)
        placed = (vb - pb["pos"]) @ rot.T + pa["pos"]
        t = placed @ n
        gap = float(t.min() - (va @ n).max())
        ring_b = section_in(placed[t <= t.min() + tol_m], w, h)
        lateral = float(np.hypot(*(ring_b["centre"] - ring_a["centre"])))
        mismatch = (2 * abs(ring_b["radius"] - ring_a["radius"]) if pa["shape"] == "round"
                    else float(np.max(np.abs(ring_b["extent"] - ring_a["extent"]))))
        row = (max(abs(gap), lateral, mismatch), spin, gap, lateral, mismatch, float(n @ (rot @ pb["dir"])))
        best = row if best is None or row[0] < best[0] else best
    _, spin, gap, lateral, mismatch, dot = best
    angle = math.degrees(math.acos(max(-1.0, min(1.0, -dot))))
    if angle > 0.05:
        pr.append(f"directions do not oppose ({angle:.2f} degrees off)")
    if math.hypot(gap, lateral) * 1000 > tol_mm:
        pr.append(f"positions are {math.hypot(gap, lateral) * 1000:.2f} mm apart")
    if abs(gap) * 1000 > tol_mm:
        pr.append(f"seam has a {gap * 1000:.2f} mm gap" if gap > 0 else f"seam overlaps by {-gap * 1000:.2f} mm")
    if mismatch * 1000 > tol_mm:
        pr.append(f"end rings differ by {mismatch * 1000:.2f} mm in section")
    return {"ok": not pr, "gap_mm": round(gap * 1000, 3) + 0.0, "lateral_mm": round(lateral * 1000, 3) + 0.0, "section_diff_mm": round(mismatch * 1000, 3) + 0.0,
            "angle_off_deg": round(angle, 4), "spin_deg": 90 * spin, "problems": pr}


def edge_points(v, e, step=0.01):
    """The vertices plus a point every `step` m along each edge longer than that: a block that spans a wall has no vertex inside it."""
    a, b = v[e[:, 0]], v[e[:, 1]]
    m = np.ceil(np.linalg.norm(b - a, axis=1) / step).astype(int)
    cnt = np.maximum(m - 1, 0)
    k = np.repeat(np.arange(len(e)), cnt)
    j = np.arange(len(k)) - np.repeat(np.cumsum(cnt) - cnt, cnt) + 1
    return np.vstack([v, a[k] + (b[k] - a[k]) * (j / m[k])[:, None]])


def check_inset_pair(va, pa, vb, eb, pb, tol_mm):
    """Inset piece b (vertices vb, edges eb) in the opening of piece a. b is moved so its port frame lies on a's (same direction, the
    same face). Then b's outline at that face must be the opening (centre and section), and no point of b between a's two faces
    (its vertices and points along its edges) may lie outside the opening."""
    tol_m, n = tol_mm / 1000, pa["dir"]
    w, h, _ = frame(n)
    pr = []
    if not sizes_match(pa, pb, tol_m):
        pr.append(f"specs differ in section: {pa['shape']} {pa['size']} against {pb['shape']} {pb['size']}")
    ring_a = section_in(rim_of(va, pa, tol_m)[0], w, h)           # a passed its own port check, so its rim is there
    ta, pts = va @ n, edge_points(vb, eb)
    best = None
    for spin in ((0,) if pa["shape"] == "round" else (0, 1)):
        rot = place(pa, pb, spin, inset=True)
        placed, along = [(q - pb["pos"]) @ rot.T + pa["pos"] for q in (vb, pts)]
        rim_b = rim_of(placed, dict(pb, pos=pa["pos"], dir=pa["dir"]), tol_m)[0]
        if not len(rim_b):
            row = (math.inf, spin, math.inf, math.inf, None)
        else:
            ring_b = section_in(rim_b, w, h)
            lateral = float(np.hypot(*(ring_b["centre"] - ring_a["centre"])))
            mismatch = (2 * abs(ring_b["radius"] - ring_a["radius"]) if pa["shape"] == "round"
                        else float(np.max(np.abs(ring_b["extent"] - ring_a["extent"]))))
            tb = along @ n
            deep = along[(tb > ta.min() + tol_m) & (tb < ta.max() - tol_m)]      # between the host's faces
            x, y = deep @ w - ring_a["centre"][0], deep @ h - ring_a["centre"][1]
            reach = (np.hypot(x, y) - ring_a["radius"] if pa["shape"] == "round"
                     else np.maximum(np.abs(x) - ring_a["extent"][0] / 2, np.abs(y) - ring_a["extent"][1] / 2))
            over = float(reach.max()) if len(deep) else 0.0
            row = (max(lateral, mismatch, over or 0.0), spin, lateral, mismatch, over)
        best = row if best is None or row[0] < best[0] else best
    _, spin, lateral, mismatch, over = best
    if math.isinf(lateral):
        pr.append("the inset's face has no outline at the opening: no vertex of it lies within the band of the declared size on the port plane")
    else:
        if lateral * 1000 > tol_mm:
            pr.append(f"inset outline is {lateral * 1000:.2f} mm off the centre of the opening")
        if mismatch * 1000 > tol_mm:
            pr.append(f"inset outline differs from the opening by {mismatch * 1000:.2f} mm in section")
        if over * 1000 > tol_mm:
            pr.append(f"inset reaches {over * 1000:.2f} mm outside the opening between the host's faces (it overlaps the wall)")
    fin = lambda x: round(x * 1000, 3) + 0.0 if x is not None and math.isfinite(x) else None
    return {"ok": not pr, "mode": "inset", "lateral_mm": fin(lateral), "section_diff_mm": fin(mismatch), "overlap_mm": fin(max(over, 0.0)),
            "angle_off_deg": 0.0, "spin_deg": 90 * spin, "problems": pr}


# ---- Blender: find and read a piece ------------------------------------------

def _is_part(ob, asset):
    return ob.type == "MESH" and not ob.name.startswith(SKIP_PREFIX) and not ob.name.startswith(asset + "_LOD")


def _load_from(path, asset):
    """Append every object of a .blend and return the root named like the asset with its children, or None."""
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = list(src.objects)
        dst.objects = list(names)   # Blender swaps this list's names for the objects, so hand it a copy
    loaded = dict(zip(names, dst.objects))
    root = loaded.get(asset)
    for ob in loaded.values():
        if ob is not None:
            bpy.context.scene.collection.objects.link(ob)
    return root


def find_root(asset, spec, assets_dir):
    ob = bpy.data.objects.get(asset)
    if ob is not None and ob.users_scene:
        return ob
    f = spec.get("file")
    for path in ([os.path.join(assets_dir, asset, asset + ".blend"), os.path.join(assets_dir, asset + ".blend")] if assets_dir else []) + \
            ([f] if isinstance(f, str) else []):
        if os.path.exists(path):
            root = _load_from(path, asset)
            if root is not None:
                return root
    return None


def piece_points(root, asset):
    """Evaluated vertices of the asset's mesh parts, in the asset's frame (metres)."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    inv, scale = root.matrix_world.inverted(), np.array(root.matrix_world.to_scale())
    out, edges, n = [], [], 0
    for ob in [root] + list(root.children_recursive):
        if not _is_part(ob, asset):
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        a = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", a)
        m = np.array(inv @ ob.matrix_world)
        out.append(a.reshape(-1, 3).astype(float) @ m[:3, :3].T + m[:3, 3])
        e = np.empty(len(me.edges) * 2, dtype=np.int64)
        me.edges.foreach_get("vertices", e)
        edges.append(e.reshape(-1, 2) + n)
        n += len(me.vertices)
        ev.to_mesh_clear()
    if not out:
        raise JointError("no mesh part under the asset object")
    return np.vstack(out) * scale, np.vstack(edges)


# ---- run ------------------------------------------------------------------------

def run(specs, assets_dir=None, tol_mm=1.0, pairs=None, kinds=None, skip_missing=False):
    rep = {"pass": False, "tol_mm": tol_mm, "pieces": [], "pairs": [], "kinds": {}, "unmated_ports": [], "errors": [], "warnings": []}
    if abs(bpy.context.scene.unit_settings.scale_length - 1.0) > 1e-9:
        rep["warnings"].append(f"scene unit scale is {bpy.context.scene.unit_settings.scale_length}: ports are read as metres per Blender unit")
    pieces = {}
    for path in specs:
        try:
            spec = check_spec.load_spec(path)
            asset = spec.get("asset") if isinstance(spec.get("asset"), str) else os.path.splitext(os.path.basename(path))[0]
            ports = spec.get("ports")
            if not ports:
                rep["warnings"].append(f"{asset}: no ports in the spec, skipped" if spec.get("type") != "kit" else f"{asset}: a kit piece with no ports, skipped")
                continue
            bad = []
            check_spec._check_ports(ports, lambda c, k, m, **kw: bad.append(m), lambda *a, **kw: None)
            if bad:
                raise JointError("ports are malformed: " + "; ".join(bad[:3]))
            root = find_root(asset, spec, assets_dir)
            if root is None:
                raise JointError("no built mesh: no object of this name in the open file, and no .blend in the assets folder or at `file`")
            pieces[asset] = {"asset": asset, "ports": [port_info(p) for p in ports], "verts": None, "edges": None}
            pieces[asset]["verts"], pieces[asset]["edges"] = piece_points(root, asset)
        except (check_spec.SpecError, JointError) as e:
            msg = f"{path}: {e}" if isinstance(e, check_spec.SpecError) else f"{asset}: {e}"
            (rep["warnings"] if skip_missing and "no built mesh" in msg else rep["errors"]).append(msg)
    bad_ports = set()
    for a, pc in pieces.items():
        row = {"asset": a, "ports": []}
        for p in pc["ports"]:
            r = check_port(pc["verts"], p, tol_mm)
            row["ports"].append(r)
            if not r["ok"]:
                bad_ports.add((a, p["name"]))
        rep["pieces"].append(row)
    all_ports = [(a, p) for a, pc in pieces.items() for p in pc["ports"] if not kinds or p["kind"] in kinds]
    ends = [x for x in all_ports if x[1]["role"] == "end"]
    holes = [x for x in all_ports if x[1]["role"] == "opening"]
    fills = [x for x in all_ports if x[1]["role"] in ("inset", "surface")]
    if pairs:
        wanted = []
        for s in pairs:
            try:
                (a, pn), (b, qn) = [x.rsplit(".", 1) for x in s.split(":")]
                wanted.append(((a, next(p for p in pieces[a]["ports"] if p["name"] == pn)), (b, next(p for p in pieces[b]["ports"] if p["name"] == qn))))
            except (ValueError, KeyError, StopIteration):
                rep["errors"].append(f"--pairs {s}: no such piece or port (format Asset.port:Asset.port)")
        todo = wanted
    else:
        todo = [(ends[i], ends[j]) for i in range(len(ends)) for j in range(i, len(ends)) if ends[i][1]["kind"] == ends[j][1]["kind"]]
        todo += [(hole, fill) for hole in holes for fill in fills if hole[1]["kind"] == fill[1]["kind"]]
    for (a, pa), (b, pb) in todo:
        row = {"a": f"{a}.{pa['name']}", "b": f"{b}.{pb['name']}", "kind": pa["kind"]}
        if pa["kind"] != pb["kind"]:
            row.update(ok=False, problems=[f"kinds differ: {pa['kind']} and {pb['kind']}: two ports mate only when the kinds are equal"])
        elif {pa["role"], pb["role"]} not in ({"end"}, {"opening", "inset"}, {"opening", "surface"}):
            row.update(ok=False, problems=[f"{pa['role']} port and {pb['role']} port do not join: ends join ends, an opening joins its inset or surface piece"])
        elif (a, pa["name"]) in bad_ports or (b, pb["name"]) in bad_ports:
            continue
        elif pa["role"] == "end":
            row.update(check_pair(pieces[a]["verts"], pa, pieces[b]["verts"], pb, tol_mm))
        elif pa["role"] == "opening":
            row.update(check_inset_pair(pieces[a]["verts"], pa, pieces[b]["verts"], pieces[b]["edges"], pb, tol_mm))
        else:                                                    # --pairs named the inset first
            row.update(check_inset_pair(pieces[b]["verts"], pb, pieces[a]["verts"], pieces[a]["edges"], pa, tol_mm))
        rep["pairs"].append(row)
    for kind in sorted({p["kind"] for _, p in all_ports}):
        ports = [(a, p) for a, p in all_ports if p["kind"] == kind]
        rows = [r for r in rep["pairs"] if r["kind"] == kind]
        rep["kinds"][kind] = {"ports": len(ports), "pairs": len(rows), "failed": sum(not r["ok"] for r in rows)}
        by = lambda role: [f"{a}.{p['name']}" for a, p in ports if p["role"] == role]
        if len(by("end")) == 1 and not pairs:
            rep["unmated_ports"].append(f"{by('end')[0]} ({kind}) is the only port of its kind: it can only join a copy of itself")
        fill = by("inset") + by("surface")
        for mine, role, other, theirs in ((by("opening"), "opening", "inset", fill), (by("inset"), "inset", "opening", by("opening")), (by("surface"), "surface", "opening", by("opening"))):
            if mine and not theirs and not pairs:
                rep["unmated_ports"] += [f"{x} ({kind}) is an {role} port and no {other} port has its kind" for x in mine]
    rep["warnings"] += rep["unmated_ports"]
    failed_ports = [f"{a}.{n}" for a, n in sorted(bad_ports)]
    failed_pairs = [r for r in rep["pairs"] if not r["ok"]]
    rep["summary"] = {"pieces": len(pieces), "ports_failed": len(failed_ports), "pairs": len(rep["pairs"]), "pairs_failed": len(failed_pairs),
                      "errors": len(rep["errors"])}
    if not pieces and not rep["errors"]:
        rep["errors"].append("no piece with ports and a mesh to test")
        rep["summary"]["errors"] = 1
    rep["pass"] = not (failed_ports or failed_pairs or rep["errors"])
    return rep


def report_lines(rep):
    lines = []
    for e in rep["errors"]:
        lines.append("ERROR " + e)
    for pc in rep["pieces"]:
        for r in pc["ports"]:
            lines += [f"PORT FAIL {pc['asset']}.{r['port']}: {p}" for p in r["problems"]]
    for r in rep["pairs"]:
        if not r["ok"]:
            lines += [f"PAIR FAIL {r['a']} + {r['b']}: {p}" for p in r["problems"]]
    lines += ["warn " + w for w in rep["warnings"]]
    return lines


def main(argv):
    ap = argparse.ArgumentParser(prog="kit_joint_test.py")
    ap.add_argument("--specs", nargs="+", required=True, help="spec files (kit/*.md); wildcards are expanded here")
    ap.add_argument("--assets-dir", help="folder with <asset>/<asset>.blend or <asset>.blend")
    ap.add_argument("--pairs", nargs="*", help="only these joins, as Asset.port:Asset.port")
    ap.add_argument("--kinds", help="only these kinds, comma separated")
    ap.add_argument("--tol-mm", type=float, default=1.0)
    ap.add_argument("--skip-missing", action="store_true", help="a spec with no built mesh is a warning, not an error")
    ap.add_argument("--out", help="write the JSON report here")
    a = ap.parse_args(argv)
    specs = sorted({p for s in a.specs for p in (glob.glob(s) if any(c in s for c in "*?[") else [s])})
    if not specs:
        raise JointError("no spec files matched")
    rep = run(specs, a.assets_dir, a.tol_mm, a.pairs, set(a.kinds.split(",")) if a.kinds else None, a.skip_missing)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    for line in report_lines(rep):
        print(line)
    print("KIT_JOINT", json.dumps({"pass": rep["pass"], "tol_mm": rep["tol_mm"], **rep["summary"], "kinds": rep["kinds"]}))
    return 0 if rep["pass"] else 1


if any(os.path.basename(a) == "kit_joint_test.py" for a in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except Exception as e:   # Blender exits 0 after an exception under --python
        print("KIT_JOINT ERROR:", repr(e))
        code = 1
    sys.exit(code)
