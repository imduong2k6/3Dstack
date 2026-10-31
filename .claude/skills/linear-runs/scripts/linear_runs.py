"""Build service runs (cables, conduit, pipes, downpipes, round ducts) from plan/services.yaml rows in Blender 5.2. The script routes
each run along the walls, tests every segment against the scene, sweeps it with real bends, puts supports at a set spacing and ends
it inside its anchors, so an agent writes a row instead of coordinates. Import it in a lane's patch, or run it headless:

    import sys; sys.path.insert(0, r"<repo>/.claude/skills/linear-runs/scripts"); import linear_runs as LR
    rep = LR.build("plan/services.yaml", runs=["R02", "R04"], metrics="plan/metrics.yaml", collection="COL_P3_Services",
                   materials={"conduit": "M_PVC_Grey", "support": "M_Steel"})

    bash bin/blender-bg <copy.blend> --python .claude/skills/linear-runs/scripts/linear_runs.py -- --services plan/services.yaml \
        --metrics plan/metrics.yaml --runs R02,R04 --collection COL_P3_Services --material conduit=M_PVC_Grey \
        --material support=M_Steel --out lr_report.json [--save]

The same rows and scene give the same geometry, and every object is found or made by name, so a patch can run it twice. A run that
would hit something is not built: the report names the object, the point and how to change the row.
"""
import argparse
import itertools
import json
import math
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

SKILLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SKILLS, "scene-lint", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "detail-inventory", "scripts"))
import lintlib as L  # noqa: E402  (the lint's scene geometry and kinds, so a built run is judged the way lint judges it)
from check_inventory import load  # noqa: E402  (services.yaml and metrics.yaml without PyYAML)

# name: object name (lint reads the kind from it), support: holder name, rigid: fittings and saddles, pitch_m: support spacing,
# bend: centreline bend radius in outside diameters, sides: tube resolution, sockets: socket rings at each bend.
# Defaults only: a row's clip_m and bend_r_m, sourced from metrics.yaml, override them.
KINDS = {
    "cable":    dict(name="Cable", support="Clip", rigid=False, pitch_m=0.3, bend=4.0, sides=8, sockets=False),
    "conduit":  dict(name="Conduit", support="Saddle", rigid=True, pitch_m=0.9, bend=4.0, sides=16, sockets=False),
    "pipe":     dict(name="Pipe", support="Clamp", rigid=True, pitch_m=1.2, bend=1.5, sides=16, sockets=True),
    "downpipe": dict(name="Downpipe", support="Clamp", rigid=True, pitch_m=1.5, bend=1.5, sides=16, sockets=True),
    "duct":     dict(name="Duct", support="Clamp", rigid=True, pitch_m=1.5, bend=1.0, sides=20, sockets=False),
}
STRAP = {"Clip": (0.008, 0.0012, 0.006), "Saddle": (0.016, 0.0015, 0.012), "Clamp": (0.025, 0.002, 0.015)}   # width, thickness, foot (m)
GAP = 0.002       # wall to tube surface: the saddle's spacer
INSET = 0.008     # how far a run end goes into its anchor
MARGIN = 0.15     # a support this close to each end of a straight (boxes and bends)
SAG_RATIO = 0.03  # a hanging span sags this share of its length unless the row says (2 to 5 % is typical)
AXES = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
ORDERS = list(itertools.permutations(range(3)))
OUT_NAME = re.compile(r"^(?:Cable|Conduit|Pipe|Downpipe|Duct|Clip|Saddle|Clamp|CBL)_(.+?)(?:_\d+|_Start|_End)?$")


class RunError(Exception):
    pass


class Scene:
    """The rendered scene as lint sees it, plus the runs built in this call. Objects in `own` (this tool's earlier output for the runs
    being rebuilt) are never obstacles."""

    def __init__(self, rules, own):
        self.geo = L.Geo(bpy.context.scene, rules)
        self.own = set(own)
        self.extra = []   # (name, BVHTree) of runs built in this call: later runs route around them
        self.sol = [s for s in self.geo.solids.values() if s.name not in self.own]
        self.lo = np.array([s.lo for s in self.sol]).reshape(-1, 3) - 1e-5
        self.hi = np.array([s.hi for s in self.sol]).reshape(-1, 3) + 1e-5

    def solid(self, name):
        return self.geo.solids.get(name) if name else None

    def cast(self, o, d, dist, accept):
        """(distance, name, location) of the first face along o -> o + d * dist whose object passes accept(name), or None. Each solid
        is cast on its own: a box face lying on a wall face would hide the wall from one combined tree."""
        o3, d3 = np.array(o), np.array(d)
        with np.errstate(divide="ignore", invalid="ignore"):
            t1, t2 = (self.lo - o3) / d3, (self.hi - o3) / d3
            near, far = np.nanmax(np.minimum(t1, t2), axis=1), np.nanmin(np.maximum(t1, t2), axis=1)
        best = None
        for i in sorted(np.flatnonzero((far >= np.maximum(near, 0)) & (near <= dist)), key=lambda i: near[i]):
            if best and near[i] > best[0]:
                break
            s = self.sol[i]
            if s.bvh is None or not accept(s.name):
                continue
            loc, _n, _i, t = s.bvh.ray_cast(Vector(o), Vector(d), dist)
            if loc is not None and (best is None or t < best[0]):
                best = (t, s.name, loc)
        return best

    def hit(self, o, d, dist, ignore=()):
        """(name, location) of the first obstacle on the segment, built runs included, or None."""
        best = self.cast(o, d, dist, lambda n: n not in ignore)
        for name, tree in self.extra:
            loc, _n, _i, t = tree.ray_cast(Vector(o), d, dist)
            if loc is not None and name not in ignore and (best is None or t < best[0]):
                best = (t, name, loc)
        return None if best is None else (best[1], best[2])

    def inside(self, p, ignore=()):
        """Name of a solid that contains p, or None."""
        pa = np.array(p)
        for i in np.where(np.all((self.lo <= pa) & (self.hi >= pa), axis=1))[0]:
            s = self.sol[i]
            if s.name not in ignore and s.inside(p):
                return s.name
        return None


# ---- rows --------------------------------------------------------------------

def _diameter(run, metrics):
    if run.get("dia_mm"):
        return float(run["dia_mm"]) / 1000
    key = run.get("metric")
    if not key:
        raise RunError("no size: give dia_mm with a source, or metric: <key in metrics.yaml>")
    if not metrics or key not in metrics:
        raise RunError(f"metric {key} is not in metrics.yaml (pass metrics=)")
    v = metrics[key].get("value") if isinstance(metrics[key], dict) else metrics[key]
    if key.endswith("_mm"):
        return float(v) / 1000
    if key.endswith("_m"):
        return float(v)
    raise RunError(f"metric {key}: end the key in _mm or _m so the unit is known")


def _axis(s):
    s = str(s).strip().lower()
    if len(s) != 2 or s[0] not in "+-" or s[1] not in "xyz":
        raise RunError(f"direction {s!r}: use +x, -x, +y, -y, +z or -z")
    v = Vector((0, 0, 0))
    v["xyz".index(s[1])] = 1 if s[0] == "+" else -1
    return v


def _snap(v):
    """The axis nearest the direction v."""
    return max(AXES, key=lambda a: a.dot(v))


def _wall(sc, p, mount, ignore):
    """(normal, plane point, distance) of the wall, ceiling or floor a node is mounted on: the nearest shell face along the axes from
    its point (horizontal first unless the mount says ceiling or floor). The normal points back to the node. None when nothing is
    within 0.6 m."""
    m = str(mount or "").lower()
    groups = [[AXES[4]]] if m.startswith("ceiling") else [[AXES[5]]] if m.startswith("floor") else [AXES[:4], AXES[4:]]
    shell = lambda n: n not in ignore and "shell" in sc.geo.solids[n].kinds
    for dirs in groups:
        best = None
        for a in dirs:
            h = sc.cast(p, a, 0.6, shell)
            if h and (best is None or h[0] < best[2]):
                best = (-a, h[2], h[0])
        if best:
            return best
    return None


def _node(sc, nid, nodes):
    if nid not in nodes:
        raise RunError(f"node {nid} is not in services.yaml")
    n = dict(nodes[nid])
    if not n.get("at_m"):
        raise RunError(f"node {nid} has no at_m")
    n["id"], n["p"] = nid, Vector(n["at_m"])
    name = n.get("object") or n.get("asset")
    n["solid"] = sc.solid(name)
    n["warn"] = None if n["solid"] else (f"node {nid}: no object {name!r} in the scene, so the end touches nothing" if name else
                                         f"node {nid}: no object or asset, so the end touches nothing (lint reads it as a dead end)")
    n["wall"] = _wall(sc, n["p"], n.get("mount"), {name} if name else set())
    return n


def _dirs(n, other):
    """Directions a run may leave node n by: the node's `dir`, else the axes along its wall, nearest the other end first."""
    if n.get("dir"):
        return [_axis(n["dir"])]
    ds = [a for a in AXES if not n["wall"] or abs(a.dot(n["wall"][0])) < 0.5]
    return sorted(ds, key=lambda a: -a.dot((other - n["p"]).normalized()) if (other - n["p"]).length > 1e-6 else 0)


def _end(n, d, s_run):
    """(end, port) where a run leaving node n along d starts: the port on the anchor's face at the run's distance from the wall,
    the end INSET inside the anchor. None when the anchor isn't there along that direction."""
    p = n["p"].copy()
    if n["wall"] and s_run is not None:
        nrm, w, _ = n["wall"]
        p += nrm * (s_run - (p - w).dot(nrm))
    a = n["solid"]
    if a is None or a.bvh is None:
        return p, p
    loc = a.bvh.ray_cast(p, d)[0] if a.inside(p) else a.bvh.ray_cast(p, -d, 0.3)[0]   # leave through the face ahead, or start on the face just behind
    if loc is None:
        q = a.bvh.find_nearest(p)[0]
        return (p, p) if q is not None and (q - p).length <= 0.02 else None   # a thin plate beside the run: end against it
    return loc - d * INSET, loc


# ---- routes ------------------------------------------------------------------

def _clean(pts):
    """Drop repeated and collinear points; None when the path doubles back on itself."""
    out = [pts[0]]
    for p in pts[1:]:
        if (p - out[-1]).length > 1e-6:
            out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b = (out[i] - out[i - 1]).normalized(), (out[i + 1] - out[i]).normalized()
        if a.dot(b) < -0.999:
            return None
        if a.dot(b) > 0.9999:
            out.pop(i)
        else:
            i += 1
    return out


def _manhattan(a, b, order, level):
    """Axis moves from a to b in the given axis order; with a level, up or down to it first, across, then to b."""
    p, out = a.copy(), []
    if level is not None:
        p.z = level
        out.append(p.copy())
        for ax in order:
            if ax != 2:
                p[ax] = b[ax]
                out.append(p.copy())
        return out
    for ax in order:
        p[ax] = b[ax]
        out.append(p.copy())
    return out


def _blocked(sc, pts, rr, ia, ib, zone):
    """(name, location) of the first thing the tube of radius rr along pts would hit, or None. Anchor ia is ignored within `zone` of
    the first point and ib within zone of the last (the run enters them); corners are tested for lying inside a solid."""
    for i in range(len(pts) - 1):
        p, q = pts[i], pts[i + 1]
        v = q - p
        n = v.length
        if n < 1e-6:
            continue
        d = v / n
        ig = ({ia} if (p - pts[0]).length <= zone else set()) | ({ib} if (q - pts[-1]).length <= zone else set())
        u = d.orthogonal().normalized()
        w = d.cross(u)
        for off in (Vector(), u * rr, -u * rr, w * rr, -w * rr):
            h = sc.hit(p + off, d, n, ig)
            if h:
                return h
        if 0 < i + 1 < len(pts) - 1:
            name = sc.inside(q, ig)
            if name:
                return name, q
    return None


def _behind(sc, p, t, reach, ignore=()):
    """(normal, distance, name) of the nearest surface across the run at p (a wall, ceiling or box to hold a support), or None."""
    dirs = [a for a in AXES if abs(a.dot(t)) < 0.1] or [t.orthogonal().normalized(), -t.orthogonal().normalized()]
    ok = lambda n: n not in ignore and "cable" not in sc.geo.solids[n].kinds
    best = None
    for a in dirs:
        h = sc.cast(p, a, reach, ok)
        if h and (best is None or h[0] < best[1]):
            best = (-a, h[0], h[1])
    return best


def _hug(sc, pts, reach, ignore):
    """Metres of the path with no surface within reach across it (a rigid run there hangs in the air)."""
    off = 0.0
    for p, q in zip(pts, pts[1:]):
        v = q - p
        if v.length > 1e-6 and not _behind(sc, (p + q) / 2, v.normalized(), reach, ignore):
            off += v.length
    return off


def _route(sc, A, B, r, s_run, lead, via_z):
    """The best wall-hugging axis route from A to B: fewest metres, bends and unsupported metres, nothing hit. Returns
    (points, None) or (None, (name, location) of what blocked the nearest try)."""
    ia, ib = (A["solid"].name if A["solid"] else None), (B["solid"].name if B["solid"] else None)
    zone = lead + INSET - 1e-3   # only the lead out of each anchor may pass through it
    rr = r + 0.0005
    best, miss, levels = None, None, [None] + ([float(via_z)] if via_z is not None else [])
    for attempt in range(2):
        blockers = {}
        for dA in _dirs(A, B["p"]):
            ea = _end(A, dA, s_run)
            for dB in (_dirs(B, A["p"]) if ea else []):
                eb = _end(B, dB, s_run)
                if not eb:
                    continue
                a1, b1 = ea[1] + dA * lead, eb[1] + dB * lead
                for level, order in itertools.product(levels, ORDERS):
                    pts = _clean([ea[0], a1] + _manhattan(a1, b1, order, level) + [b1, eb[0]])
                    if pts is None:
                        continue
                    length = sum((q - p).length for p, q in zip(pts, pts[1:]))
                    jogs = sum(1 for p, q in zip(pts[1:-1], pts[2:-1]) if (q - p).length < lead - 1e-6)   # too short to bend into and out of
                    score = length + 0.25 * (len(pts) - 2) + 0.5 * jogs
                    if best and score >= best[0]:
                        continue
                    h = _blocked(sc, pts, rr, ia, ib, zone)
                    if h:
                        blockers.setdefault(h[0], h[1])
                        miss = miss or h
                        continue
                    off = _hug(sc, pts[1:-1], s_run + 0.02 if s_run else r + 0.03, {ia, ib})
                    if best is None or score + 3 * off < best[0]:
                        best = (score + 3 * off, pts, off)
        if attempt or (best and best[2] < 0.05):
            break
        levels = []   # second try: over or under what blocked the wall-hugging tries (or none was clear)
        for name in list(blockers)[:3]:
            s = sc.solid(name)
            if s is not None:
                levels += [float(s.hi[2]) + r + 0.04, float(s.lo[2]) - r - 0.04]
        if via_z is not None:
            levels.append(float(via_z))
        if not levels:
            break
    return (best[1], None) if best else (None, miss)


def _span_k(ratio):
    """Catenary shape parameter k (half-span over a) for a level span that sags `ratio` of its length: ratio = (cosh k - 1) / 2k."""
    lo, hi = 1e-6, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if (math.cosh(mid) - 1) / (2 * mid) < ratio:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _hang(pts, sag_m, n=24):
    """Dense points of spans that hang between consecutive points as catenaries, sagging below the chord. The longest span sags sag_m
    (or SAG_RATIO of it); shorter ones scale with the square of their length, as at equal tension."""
    spans = [(q - p).length for p, q in zip(pts, pts[1:])]
    top = max(spans)
    out = [pts[0]]
    for (p, q), span in zip(zip(pts, pts[1:]), spans):
        sag = (sag_m if sag_m is not None else SAG_RATIO * top) * (span / top) ** 2
        k = _span_k(sag / span) if sag > 1e-5 else 0.0
        for j in range(1, n + 1):
            t = j / n
            g = (math.cosh(k) - math.cosh(k * (2 * t - 1))) / (math.cosh(k) - 1) if k else 0.0
            out.append(p.lerp(q, t) - Vector((0, 0, sag * g)))
    return out


# ---- geometry ----------------------------------------------------------------

def _fillet(c, R):
    """Dense centreline with each corner of c rounded at radius R, the tangent length kept within half of each neighbouring straight
    (all of it next to an end). -> (points, bends, tight bends as [corner, radius used], tangent length per corner)."""
    pts, bends, tight, tl = [c[0]], 0, [], [0.0] * len(c)
    for i in range(1, len(c) - 1):
        a, b = c[i] - c[i - 1], c[i + 1] - c[i]
        la, lb = a.length, b.length
        a, b = a / la, b / lb
        theta = math.acos(max(-1.0, min(1.0, a.dot(b))))
        if theta < 1e-3:
            continue
        bends += 1
        t = R * math.tan(theta / 2)
        cap = min(la * (0.95 if i == 1 else 0.5), lb * (0.95 if i == len(c) - 2 else 0.5))
        rr = R
        if t > cap:
            t, rr = cap, cap / math.tan(theta / 2)
            tight.append([[round(x, 3) for x in c[i]], round(rr, 4)])
        tl[i] = t
        axis = a.cross(b).normalized()
        p1 = c[i] - a * t
        centre = p1 + axis.cross(a).normalized() * rr
        steps = max(12, math.ceil(math.degrees(theta) / 8))   # placement-phases: at least 12 segments a bend, no facet over 8 degrees
        for k in range(steps + 1):
            pts.append(centre + Matrix.Rotation(theta * k / steps, 3, axis) @ (p1 - centre))
    pts.append(c[-1])
    return [p for i, p in enumerate(pts) if i == 0 or (p - pts[i - 1]).length > 1e-6], bends, tight, tl


def _frames(pts):
    """Twist-free frames (N, B) along a polyline: the first normal carried along by the smallest rotation between tangents."""
    n = len(pts)
    ts = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    t0 = ts[0]
    N = t0.cross(Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))).normalized()
    out = []
    for i, t in enumerate(ts):
        if i:
            N = ts[i - 1].rotation_difference(t) @ N
            N = (N - t * N.dot(t)).normalized()
        out.append((N, t.cross(N)))
    return out


def _sweep(pts, frames, r, sides, buf, off=(0.0, 0.0)):
    """A closed tube of radius r along pts (offset in each frame for a bundle strand) into buf; UVs in metres (u around, v along)."""
    verts, faces, smooth, uvs = buf
    base = len(verts)
    acc, along = 0.0, []
    for i, p in enumerate(pts):
        acc += (p - pts[i - 1]).length if i else 0.0
        along.append(acc)
    for p, (N, B) in zip(pts, frames):
        c = p + N * off[0] + B * off[1]
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(c + (N * math.cos(a) + B * math.sin(a)) * r)
    circ = 2 * math.pi * r
    for i in range(len(pts) - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            faces.append((base + i * sides + k, base + i * sides + k1, base + (i + 1) * sides + k1, base + (i + 1) * sides + k))
            smooth.append(True)
            u0, u1 = circ * k / sides, circ * (k + 1) / sides
            uvs.append([(u0, along[i]), (u1, along[i]), (u1, along[i + 1]), (u0, along[i + 1])])
    last = base + (len(pts) - 1) * sides
    for ring, rev in ((base, True), (last, False)):
        idx = [ring + k for k in range(sides)]
        faces.append(tuple(reversed(idx)) if rev else tuple(idx))
        smooth.append(False)
        uvs.append([(r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides)) for k in (reversed(range(sides)) if rev else range(sides))])


def _pack(n, r):
    """Strand centres of an n-strand bundle in rings around the centre, and the bundle's outer radius."""
    pts, ring, d = [(0.0, 0.0)], 1, 2 * r * 1.05
    while len(pts) < n:
        m = 6 * ring
        pts += [(ring * d * math.cos(2 * math.pi * k / m), ring * d * math.sin(2 * math.pi * k / m)) for k in range(m)]
        ring += 1
    pts = pts[:n]
    return pts, max(math.hypot(x, y) for x, y in pts) + r


def _strap(a, h, kind):
    """A support in its own frame (x across the run, y off the surface, z along the run): a strap of inner radius a over a tube whose
    centre is h off the surface, with a foot on the surface each side. -> (verts, faces)."""
    w, t, foot = STRAP[kind]
    arc = lambda rad: [(rad * math.cos(math.pi * k / 12), h + rad * math.sin(math.pi * k / 12)) for k in range(13)]
    inner = [(a + foot, 0.0), (a, 0.0)] + arc(a) + [(-a, 0.0), (-a - foot, 0.0)]
    outer = [(a + foot, t), (a + t, t)] + arc(a + t) + [(-a - t, t), (-a - foot, t)]
    loop = inner + outer[::-1]
    n = len(loop)
    verts = [(x, y, -w / 2) for x, y in loop] + [(x, y, w / 2) for x, y in loop]
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)] + [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    return verts, faces


def _mesh(name, verts, faces, smooth=None, uvs=None):
    """Get or reuse mesh `name` and fill it (never a .001: a patch runs twice). Normals point out."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if smooth is not None:
        me.polygons.foreach_set("use_smooth", smooth)
    if uvs is not None:
        lay = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        flat = [c for poly in uvs for uv in poly for c in uv]
        lay.data.foreach_set("uv", flat)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def _object(name, data, col, mat, props, matrix=None):
    ob = bpy.data.objects.get(name)
    if ob is not None and ob.data is not data:
        old = ob.data
        ob.data = data
        if old is not None and old.users == 0 and isinstance(old, bpy.types.Mesh):
            bpy.data.meshes.remove(old)
    if ob is None:
        ob = bpy.data.objects.new(name, data)
    if col not in ob.users_collection:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        col.objects.link(ob)
    ob.matrix_world = matrix if matrix is not None else Matrix.Identity(4)
    if mat is not None and getattr(data, "materials", None) is not None:
        if len(data.materials) == 0:
            data.materials.append(mat)
        else:
            data.materials[0] = mat
    for k, v in props.items():
        ob[k] = v
    return ob


def _remove(ob):
    data = ob.data
    bpy.data.objects.remove(ob)
    if isinstance(data, bpy.types.Mesh) and data.users == 0:
        bpy.data.meshes.remove(data)


# ---- build -------------------------------------------------------------------

def _rows(services, runs):
    svc = load(services) if isinstance(services, str) else services
    nodes, rows = {}, []
    for net in (svc or {}).get("networks") or []:
        for n in net.get("nodes") or []:
            nodes[n["id"]] = n
        for r in net.get("runs") or []:
            rows.append(dict(r, network=net.get("id")))
    if runs:
        want = list(runs)
        missing = [r for r in want if r not in {x.get("id") for x in rows}]
        if missing:
            raise RunError(f"runs not in services.yaml: {missing}")
        rows = [r for r in rows if r.get("id") in want]
    return nodes, rows


def build(services, runs=None, metrics=None, collection="COL_P3_Services", phase="P3", materials=None, rules=None, emit="mesh"):
    """Build the given runs (all when None) of a services.yaml (path or dict) into the open file. Conduit, pipe and duct runs go
    first, then cables, each finished run an obstacle for the next. Returns the report dict; nothing is built for a blocked run.
    materials: {kind or "support": existing material name}; a row's `material` / `support_material` wins.
    emit="guide" makes hanging cables a guide curve CBL_<id> with _Start and _End empties (for the user's cable rig) instead of a mesh."""
    nodes, rows = _rows(services, runs)
    met = (load(metrics) if isinstance(metrics, str) else metrics) if metrics else None
    rules = L.load_rules(rules) if isinstance(rules, str) or rules is None else rules
    mats = dict(materials or {})
    ids = {str(r.get("id")) for r in rows}
    own = {ob.name for ob in bpy.data.objects if str(ob.get("lr_run", "")) in ids}
    sc = Scene(rules, own)
    col = bpy.data.collections.get(collection)
    if col is None:
        col = bpy.data.collections.new(collection)
        bpy.context.scene.collection.children.link(col)
    rep = {"ok": True, "built": [], "blocked": [], "errors": [], "warnings": []}
    rows.sort(key=lambda r: (str(r.get("by")) == "cable", str(r.get("id"))))
    made = set()
    for row in rows:
        rid = str(row.get("id"))
        try:
            res = _build_run(sc, row, nodes, met, col, phase, mats, emit)
        except RunError as e:
            rep["errors"].append({"run": rid, "what": str(e)})
            continue
        rep["warnings"] += [{"run": rid, "what": w} for w in res.pop("warnings")]
        if res.get("blocked"):
            rep["blocked"].append(res["blocked"])
        else:
            made |= set(res["objects"])
            rep["built"].append(res)
    rebuilt = {b["run"] for b in rep["built"]}
    for ob in [o for o in bpy.data.objects if o.name in own and o.name not in made and str(o.get("lr_run")) in rebuilt]:
        _remove(ob)   # last build's surplus supports; a blocked run keeps its last good geometry
    rep["ok"] = not rep["blocked"] and not rep["errors"]
    return rep


def _mat(row, key, kind, mats):
    name = row.get(key) or mats.get(kind)
    if not name:
        return None
    m = bpy.data.materials.get(name)
    if m is None:
        raise RunError(f"material {name!r} is not in the file: use an existing material (lanes add none)")
    return m


def _build_run(sc, row, nodes, met, col, phase, mats, emit):
    rid, by = str(row.get("id")), str(row.get("by", "")).lower()
    if by not in KINDS:
        raise RunError(f"by: {by!r} is not built here (one of {', '.join(KINDS)})")
    K = KINDS[by]
    d = _diameter(row, met)
    if by == "cable" and row.get("strands_mm"):   # a bundle of mixed strands, one size each (count follows the list)
        dias = [float(x) / 1000 for x in row["strands_mm"]]
    else:
        dias = [d] * (int(row.get("count") or 1) if by == "cable" else 1)
    count = len(dias)
    offs, R_out = _pack(count, max(dias) / 2)
    A, B = _node(sc, row.get("from"), nodes), _node(sc, row.get("to"), nodes)
    warnings = [n["warn"] for n in (A, B) if n["warn"]]
    hang = by == "cable" and (bool(row.get("hang")) or row.get("sag_m") is not None)
    bend_R = float(row.get("bend_r_m") or K["bend"] * 2 * R_out)
    pitch = float(row.get("clip_m") or K["pitch_m"])
    props = {"lr_run": rid, "inv_id": rid, "phase": phase, "network": str(row.get("network") or "")}
    if row.get("path_m") or hang:
        via = [Vector(p) for p in (row.get("path_m") or [])]
        via = [p for p in via if (p - A["p"]).length > 0.1 and (p - B["p"]).length > 0.1]   # path_m may repeat the two node points
        s_run = None if hang else R_out + GAP
        first, last = (via[0] if via else B["p"]), (via[-1] if via else A["p"])
        toward = lambda v: v.normalized() if hang else _snap(v)   # a hanging cable leaves straight at its next point; a clipped one along an axis
        ea = next((e for dA in ([_axis(A["dir"])] if A.get("dir") else [toward(first - A["p"])] + _dirs(A, first))
                   for e in [_end(A, dA, s_run)] if e), None)
        eb = next((e for dB in ([_axis(B["dir"])] if B.get("dir") else [toward(last - B["p"])] + _dirs(B, last))
                   for e in [_end(B, dB, s_run)] if e), None)
        if not ea or not eb:
            raise RunError(f"cannot start on {A['id'] if not ea else B['id']}'s anchor from this path: set the node's dir")
        corners = _clean([ea[0], ea[1]] + via + [eb[1], eb[0]])
        if corners is None:
            raise RunError("path_m doubles back on itself")
        centre = _hang(corners, row.get("sag_m")) if hang else None
        route = "hang" if hang else "path"
        ia, ib = (A["solid"].name if A["solid"] else None), (B["solid"].name if B["solid"] else None)
        h = _blocked(sc, centre or corners, R_out + 0.0005, ia, ib, INSET + 0.1)
        if h:
            return {"warnings": warnings, "blocked": _blocked_item(rid, h, "move or add path_m points around it" + ("" if hang else ", or drop path_m to let the router find a way"))}
    else:
        s_run = R_out + GAP
        lead = max(bend_R + R_out, 0.04)
        corners, h = _route(sc, A, B, R_out, s_run, lead, row.get("via_z"))
        if corners is None:
            fix = "add path_m points around it, or set via_z to a height that clears it"
            return {"warnings": warnings, "blocked": _blocked_item(rid, h, fix) if h else {"run": rid, "what": "no route: neither anchor can be left along its wall", "fix": "set dir on the nodes, or give path_m"}}
        centre, route = None, "auto"
    if centre is None:
        centre, bends, tight, tl = _fillet(corners, bend_R)
    else:
        bends, tight, tl = len(corners) - 2, [], [0.0] * len(corners)
    frames = _frames(centre)
    mat_run, mat_sup = _mat(row, "material", by, mats), _mat(row, "support_material", "support", mats)
    objects = []
    buf = ([], [], [], [])
    for off, dd in zip(offs, dias):
        _sweep(centre, frames, dd / 2, K["sides"] if count == 1 else 8, buf, off)
    if hang and emit == "guide":
        objects += _guide(rid, centre, col, props)
    else:
        if K["sockets"]:
            for i, t in enumerate(tl):
                if t > 0:
                    for p, u in ((corners[i] - (corners[i] - corners[i - 1]).normalized() * t, (corners[i] - corners[i - 1]).normalized()),
                                 (corners[i] + (corners[i + 1] - corners[i]).normalized() * t, (corners[i + 1] - corners[i]).normalized())):
                        ln = max(0.02, 0.6 * d)
                        seg = [p - u * ln / 2, p + u * ln / 2]
                        _sweep(seg, _frames(seg), d / 2 * 1.12, K["sides"], buf)
        name = f"{K['name']}_{rid}"
        me = _mesh(name, buf[0], buf[1], buf[2], buf[3])
        ob = _object(name, me, col, mat_run, props)
        objects.append(ob.name)
    supports, unsupported = ([], 0.0) if hang else _supports(sc, rid, K, corners, tl, R_out, s_run, pitch, col, mat_sup, props, A, B)
    objects += supports
    sc.extra.append((objects[0], BVHTree.FromPolygons([tuple(v) for v in buf[0]], buf[1])))   # later runs route around this one
    if K["rigid"] and unsupported > 2 * pitch:
        warnings.append(f"{unsupported:.2f} m with no surface for a support: add a bracket or route it closer to a wall")
    if tight:
        warnings.append(f"{len(tight)} bend(s) tighter than {bend_R:.3f} m (corner, radius used): {tight[:4]}")
    length = sum((q - p).length for p, q in zip(centre, centre[1:]))
    return {"run": rid, "by": by, "route": route, "objects": objects, "length_m": round(length, 3), "bends": bends,
            "supports": len(supports), "strands": count, "corners": [[round(x, 4) for x in c] for c in corners], "warnings": warnings}


def _blocked_item(rid, h, fix):
    name, loc = h
    return {"run": rid, "hit": name, "at": [round(x, 3) for x in loc], "fix": fix}


def _guide(rid, pts, col, props):
    """A poly curve CBL_<id> through the hanging cable's points, with empties at its ends, for the user's cable rig (Curve input)."""
    name = f"CBL_{rid}"
    cu = bpy.data.curves.get(name) or bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.splines.clear()
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for pt, p in zip(sp.points, pts):
        pt.co = (p.x, p.y, p.z, 1.0)
    out = [_object(name, cu, col, None, props).name]
    for tag, p in (("Start", pts[0]), ("End", pts[-1])):
        en = bpy.data.objects.get(f"{name}_{tag}") or bpy.data.objects.new(f"{name}_{tag}", None)
        out.append(_object(en.name, None, col, None, props, Matrix.Translation(p)).name)
    return out


def _supports(sc, rid, K, corners, tl, R_out, s_run, pitch, col, mat, props, A, B):
    """Supports on every straight at the run's spacing, one within MARGIN of each end of each straight, each on the surface found
    behind the run; all share one mesh (linked duplicates). -> (names, longest stretch with no support in metres)."""
    kind = K["support"]
    a = R_out + 0.0005
    vs, fs = _strap(a, s_run, kind)
    me = _mesh(f"{kind}_{rid}", vs, fs)
    ignore = {n["solid"].name for n in (A, B) if n["solid"]}
    names, along, done = [], [], 0.0
    for i in range(len(corners) - 1):
        p, q = corners[i], corners[i + 1]
        seg = q - p
        n = seg.length
        t = seg / n
        s0 = tl[i] + (INSET + 0.02 if i == 0 else 0.0)   # the run's ends sit INSET inside their anchors: start past the face
        s1 = n - tl[i + 1] - (INSET + 0.02 if i == len(corners) - 2 else 0.0)
        span = s1 - s0
        if span < STRAP[kind][0] * 2:
            done += n
            continue
        m = min(MARGIN if kind != "Clip" else 0.08, span / 2)
        k = max(1, math.ceil((span - 2 * m) / pitch) + 1) if span > 2 * m else 1
        for j in range(k):
            s = s0 + (m + (span - 2 * m) * j / (k - 1) if k > 1 else span / 2)
            c = p + t * s
            b = _behind(sc, c, t, s_run + 0.01, ignore)
            if not b or abs(b[1] - s_run) > 0.002:
                continue
            nrm = b[0]
            x = nrm.cross(t)
            mw = Matrix((x, nrm, t)).transposed().to_4x4()
            mw.translation = c - nrm * s_run
            nm = f"{kind}_{rid}_{len(names) + 1:02d}"
            names.append(_object(nm, me, col, mat, props, mw).name)
            along.append(done + s)
        done += n
    total = done
    gaps = [b - a for a, b in zip([0.0] + along, along + [total])]
    return names, max(gaps) if gaps else total


# ---- command line ------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(prog="linear_runs.py")
    ap.add_argument("--services", required=True)
    ap.add_argument("--metrics")
    ap.add_argument("--runs", help="comma list of run ids (default: all)")
    ap.add_argument("--collection", default="COL_P3_Services")
    ap.add_argument("--phase", default="P3")
    ap.add_argument("--material", action="append", default=[], help="kind=Material (kind: cable, conduit, pipe, downpipe, duct, support)")
    ap.add_argument("--rules", help="plan/lint_rules.yaml")
    ap.add_argument("--emit", choices=("mesh", "guide"), default="mesh")
    ap.add_argument("--out", help="report.json")
    ap.add_argument("--save", action="store_true", help="save the open file (headless copies only, never the live file)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = build(a.services, a.runs.split(",") if a.runs else None, a.metrics, a.collection, a.phase,
                    dict(m.split("=", 1) for m in a.material), a.rules, a.emit)
    except RunError as e:
        print(f"LINEAR_RUNS error: {e}")
        return 2
    if a.out:
        with open(a.out, "w") as f:
            json.dump(rep, f, indent=1)
    if a.save and rep["built"]:
        bpy.ops.wm.save_mainfile()
    print(f"LINEAR_RUNS {'OK' if rep['ok'] else 'FAIL'} built={len(rep['built'])} blocked={len(rep['blocked'])} "
          f"errors={len(rep['errors'])} warnings={len(rep['warnings'])}" + (f" report={a.out}" if a.out else ""))
    if a.verbose or not a.out:
        for k in ("blocked", "errors", "warnings"):
            for it in rep[k]:
                print(f"  {k[:-1]}: {json.dumps(it)}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    rc = main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    sys.exit(rc)
