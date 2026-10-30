"""Shared helpers for lint_blender.py and visible_set.py: rules and their defaults, name and tag kinds, the visibility
states, and the rendered geometry of the open file in world space. Import it, never run it:

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import lintlib
"""
import argparse
import copy
import json
import os
import re
import sys

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "blender-adapter", "scripts"))
from step_log import scene_state  # noqa: E402  (the same hashes capture.py and the step ledger use)


class LintError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2 by default; 2 means "blocker" here
        raise LintError(message)


# Every threshold and word list the checks use. A project's plan/lint_rules.yaml overrides single keys.
DEFAULT_RULES = {
    "float_tol_m": 0.02,            # an object farther than this from everything that reaches the ground floats
    "penetration_tol_m": 0.02,      # smallest overlap of two solids' boxes (a depth proxy) that counts as interpenetration
    "origin_tol_m": 0.005, "origin_radius_m": 0.5, "origin_max_size_m": 4.0,   # larger objects are structure, authored around the origin
    "cable_anchor_tol_m": 0.05, "cable_entry_tol_m": 0.02, "cable_sag_max_ratio": 0.2,
    "conduit_end_tol_m": 0.02, "cap_max_m": 0.4, "vent_pocket_min_m": 0.05,
    "door_min_width_m": 0.91, "door_min_height_m": 2.0,   # same limits as layout-2d/check_layout.py
    "passage_min_width_m": 0.91, "head_min_m": 2.1, "capsule_radius_m": 0.35, "capsule_height_m": 1.8, "eye_height_m": 1.6,
    "size_tol_m": 0.005, "riser_max_m": 0.178, "riser_uneven_max_m": 0.01, "tread_min_m": 0.279, "stair_flight_gap_m": 0.5,
    "camera_pos_tol_m": 0.001, "camera_rot_tol_deg": 0.05, "camera_value_tol": 0.001,
    "light_pos_tol_m": 0.01, "light_power_tol_rel": 0.01, "exposure_tol": 0.001,
    "ground_z_m": None,             # None: the lowest large object
    "max_items": 100,               # items listed per check in lint.json; counts stay exact
    "required_tags": ["phase"],
    "severity": {},                 # check name -> blocker | major | minor, to change a default class
    "disable": [],                  # check names to switch off
    "tokens": {                     # a name (or its collection's name) split at _ . - space and camelCase; any token hits
        "cable": ["cable", "cables", "cbl", "wire", "wires"],
        "conduit": ["conduit", "conduits", "elbow", "coupling", "tee", "fitting", "fittings"],   # add pipe or duct in the rules file if they need the same check
        "anchor": ["box", "saddle", "clip", "strap", "clamp", "meter", "board", "junction", "jb", "bracket", "conduit", "elbow", "coupling", "tee", "fitting", "sleeve",
                   "gland", "lamp", "light", "fixture", "tray", "trunking", "coil", "pole", "hanger", "insulator", "socket", "switch",
                   "panel", "ac", "aircon", "sign", "cage", "connector", "plug", "intercom", "riser", "cleat", "hook", "antenna",
                   "bulb", "holder", "batten", "pipe", "duct"],
        "through_wall": ["vent", "louvre", "louver", "fan", "extractor", "grille", "ac", "aircon"],
        "wall": ["wall", "walls", "facade", "partition"],
        "door": ["door", "doors", "doorway"],
        "stair": ["stair", "stairs", "staircase", "step", "steps", "tread"],
        "walkable": ["stair", "stairs", "staircase", "step", "steps", "tread", "floor", "landing", "threshold", "kerb", "curb",
                     "ramp", "nosing", "ground", "pavement", "road", "track"],
        "wear": ["grime", "grimy", "stain", "stains", "drip", "drips", "leak", "leaks", "rust", "rusty", "crack", "cracks", "chip",
                 "chips", "dent", "dents", "peel", "peeling", "decal", "decals", "dirt", "dirty", "mold", "mould", "mildew",
                 "streak", "streaks", "tidemark"],
        "review": ["review", "reviewonly"],
        "parked": ["parked"],
    },
    "exclude_tokens": {"cable": ["tray", "trunking", "duct", "box", "conduit", "bracket", "clip", "hanger", "reel", "label", "tag",
                                 "cover", "gland", "sleeve", "junction", "spool", "coil", "stand"],
                       "conduit": ["cable", "cables", "cbl", "wire", "wires",   # boxes, saddles and clips are anchors a conduit ends at, not pieces with ends
                                   "box", "boxes", "saddle", "saddles", "clip", "clips", "strap", "straps", "clamp", "clamps", "bracket",
                                   "meter", "board", "junction", "jb"],
                       "door": ["hasp", "padlock", "lock", "handle", "knob", "hinge", "bolt", "latch", "sign", "plate", "bell", "mat", "stop",
                                "seal", "number", "peephole", "closer", "frame", "box", "light", "lamp", "step", "sill", "paper", "mailbox", "letterbox",
                                "poster", "sticker", "notice", "label"],
                       "wear": ["pipe", "pipes", "tray", "hose", "pan", "tap", "bracket", "clip", "clips"]},   # a drip pipe or a crack-filler tray is a real part
    "overlap_allow": [],            # [[tokenA, tokenB], ...] pairs of tokens whose objects may overlap
}

# Collections the adapter parks (excluded from the view layer): the exclusion is the test, the name is a convention.
PARKED_NAMES = ("COL_Kit", "COL_Parked", "COL_Ref")
GEOM_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def _scalar(v):
    v = v.strip()
    if v in ("", "~", "null"):
        return None
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def parse_yaml(text):
    """The subset a rules file needs: nested mappings by indent, `- item` lists, [a, b] lists, scalars, # comments."""
    rows = []
    for raw in text.splitlines():
        s = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if s.strip():
            rows.append((len(s) - len(s.lstrip(" ")), s.strip()))

    def block(i, indent):
        if rows[i][1].startswith("- "):
            out = []
            while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
                out.append(_scalar(rows[i][1][2:]))
                i += 1
            return out, i
        out = {}
        while i < len(rows) and rows[i][0] == indent and not rows[i][1].startswith("- "):
            k, sep, v = rows[i][1].partition(":")
            if not sep:
                raise LintError(f"cannot parse rules line: {rows[i][1]}")
            i += 1
            if v.strip():
                out[k.strip()] = _scalar(v)
            elif i < len(rows) and (rows[i][0] > indent or (rows[i][0] == indent and rows[i][1].startswith("- "))):
                out[k.strip()], i = block(i, rows[i][0])
            else:
                out[k.strip()] = None
        return out, i

    if not rows:
        return {}
    val, i = block(0, rows[0][0])
    if i != len(rows):
        raise LintError(f"cannot parse rules line: {rows[i][1]}")
    return val


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise LintError(f"cannot read {path}: {e}")


def load_rules(path=None):
    if not path:
        return copy.deepcopy(DEFAULT_RULES)
    if not os.path.exists(path):
        raise LintError(f"rules file not found: {path}")
    text = open(path).read()
    return deep_merge(DEFAULT_RULES, json.loads(text) if text.lstrip().startswith("{") else parse_yaml(text))


# ---- names, kinds, visibility ------------------------------------------------

def tokens(name):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {t.lower() for t in re.split(r"[_.\-\s]+", s) if t}


def kinds_of(ob, rules):
    """The kinds of an object: its `kind` property (comma list) when set, else the kinds whose words appear in its name or its
    collections' names."""
    k = ob.get("kind")
    if k:
        return {x.strip().lower() for x in str(k).split(",") if x.strip()}
    own = tokens(ob.name)  # exclusions read the object's own name, so a collection called Boxes cannot hide its conduits
    toks = set(own)
    for c in ob.users_collection:
        toks |= tokens(c.name)
    return {kind for kind, words in rules["tokens"].items()
            if toks & set(words) and not own & set(rules["exclude_tokens"].get(kind, ()))}


def render_off_collections(scene):
    """Names of collections switched off for render, directly or through a parent (as stats.py does)."""
    off = set()

    def walk(c, hidden):
        hidden = hidden or c.hide_render
        if hidden:
            off.add(c.name)
        for ch in c.children:
            walk(ch, hidden)
    walk(scene.collection, False)
    return off


def is_rendered(ob, off):
    return not ob.hide_render and not all(c.name in off for c in ob.users_collection)


def layer_collections(view_layer):
    """name -> LayerCollection, for the whole tree."""
    out = {}

    def walk(lc):
        out[lc.collection.name] = lc
        for ch in lc.children:
            walk(ch)
    walk(view_layer.layer_collection)
    return out


def parent_collections(ob):
    """Every collection an object sits in and all their parents, by name."""
    seen, stack = set(), list(ob.users_collection)
    while stack:
        c = stack.pop()
        if c.name in seen:
            continue
        seen.add(c.name)
        stack += [p for p in bpy.data.collections if c.name in p.children]
    return seen


def viewport_visible(ob, view_layer):
    try:
        return ob.visible_get(view_layer=view_layer) and not ob.hide_viewport
    except RuntimeError:  # object not in this view layer
        return False


# ---- geometry ----------------------------------------------------------------

class Solid:
    """One rendered object (an instancer counts as one) in world space."""

    def __init__(self, name, ob, verts, tris, kinds):
        self.name, self.ob, self.verts, self.tris, self.kinds = name, ob, verts, tris, kinds
        self.lo, self.hi = (verts.min(0), verts.max(0)) if len(verts) else (np.zeros(3), np.zeros(3))
        self._bvh = None

    def samples(self, n_verts=24, n_tris=40):
        """Vertices and triangle centres, evenly spread: points to test contact from (corners alone miss a face lying against another)."""
        v = self.verts[::max(1, len(self.verts) // n_verts)]
        if not len(self.tris):
            return v
        t = self.tris[::max(1, len(self.tris) // n_tris)]
        return np.concatenate([v, self.verts[t].mean(1)])

    @property
    def bvh(self):
        if self._bvh is None and len(self.tris):
            self._bvh = BVHTree.FromPolygons(self.verts.tolist(), self.tris.tolist(), all_triangles=True)
        return self._bvh

    def inside(self, p):
        """Ray parity along three axes, majority vote (a back-facing nearest face on an open mesh is not 'inside')."""
        if self.bvh is None:
            return False
        from mathutils import Vector
        odd = 0
        for dv in (Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))):
            n, q = 0, Vector(p)
            while n < 64:
                h = self.bvh.ray_cast(q, dv)
                if h[0] is None:
                    break
                n += 1
                q = h[0] + dv * 1e-4
            odd += n % 2
        return odd >= 2


class Geo:
    """The rendered, viewport-live solids of the open file with one combined BVH (built on first use)."""

    def __init__(self, scene, rules, depsgraph=None):
        self.scene, self.rules = scene, rules
        dg = depsgraph or bpy.context.evaluated_depsgraph_get()
        off = render_off_collections(scene)
        parts = {}
        for inst in dg.object_instances:
            ob = inst.object
            if ob.type not in GEOM_TYPES:
                continue
            src = inst.parent.original if inst.is_instance and inst.parent is not None else ob.original
            if not is_rendered(src, off):  # a parked collection never reaches the depsgraph
                continue
            try:
                me = ob.to_mesh()
            except RuntimeError:
                continue
            if len(me.vertices):
                m = np.array(inst.matrix_world)
                co = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get("co", co)
                co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
                me.calc_loop_triangles()
                tr = np.empty(len(me.loop_triangles) * 3, np.int32)
                me.loop_triangles.foreach_get("vertices", tr)
                parts.setdefault(src.name, (src, []))[1].append((co, tr.reshape(-1, 3)))
            ob.to_mesh_clear()
        self.solids = {}
        for name, (src, plist) in parts.items():
            base, vs, ts = 0, [], []
            for co, tr in plist:
                vs.append(co)
                ts.append(tr + base)
                base += len(co)
            self.solids[name] = Solid(name, src, np.concatenate(vs), np.concatenate(ts), kinds_of(src, rules))
        self.names = list(self.solids)
        self._tree = None

    def of_kind(self, kind):
        return [s for s in self.solids.values() if kind in s.kinds]

    @property
    def tree(self):
        if self._tree is None:
            vs, ts, owner, base = [], [], [], 0
            for i, s in enumerate(self.solids.values()):
                if not len(s.tris):
                    continue
                vs.append(s.verts)
                ts.append(s.tris + base)
                owner.append(np.full(len(s.tris), i, np.int32))
                base += len(s.verts)
            if not vs:
                raise LintError("no rendered triangles in the scene")
            self.owner = np.concatenate(owner)
            self._tree = BVHTree.FromPolygons(np.concatenate(vs).tolist(), np.concatenate(ts).tolist(), all_triangles=True)
        return self._tree

    def owner_name(self, tri_index):
        return self.names[self.owner[tri_index]]

    def near(self, p, r, exclude=()):
        """{object name: (distance, location, normal)} for the nearest face of every object within r of p."""
        self.tree  # noqa: B018  (builds self.owner)
        res = {}
        for loc, nrm, idx, d in self.tree.find_nearest_range(p, r):
            n = self.owner_name(idx)
            if n not in exclude and (n not in res or d < res[n][0]):
                res[n] = (d, loc, nrm)
        return res

    def ray(self, origin, direction, dist=1.0e4):
        """(location, normal, object name, distance) of the first hit, or None."""
        loc, nrm, idx, d = self.tree.ray_cast(origin, direction, dist)
        return None if loc is None else (loc, nrm, self.owner_name(idx), d)


def read_paths(walk_path, layout_path=None):
    """Walk paths as {name: [[x, y], ...]} from walk.json ({"paths": {...}}, a bare list, or a layout's "path") or layout.json."""
    src = walk_path if walk_path and os.path.exists(walk_path) else (layout_path if layout_path and os.path.exists(layout_path) else None)
    if not src:
        return None, None
    data = load_json(src)
    if isinstance(data, list):
        return {"main": data}, data
    paths = data.get("paths") or ({"main": data["path"]} if data.get("path") else None)
    return paths, data


def ground_z(geo, rules):
    """Floor level of the scene: rules.ground_z_m, else the lowest large (>= 1 m2) object, else the lowest object."""
    if rules["ground_z_m"] is not None:
        return float(rules["ground_z_m"])
    big = [s.lo[2] for s in geo.solids.values() if len(s.tris) and (s.hi[0] - s.lo[0]) * (s.hi[1] - s.lo[1]) >= 1.0]
    return float(min(big) if big else min(s.lo[2] for s in geo.solids.values() if len(s.verts)))


def find_floor(geo, x, y):
    """Lowest walkable surface under (x, y): an upward-facing face with 1.8 m of free headroom. None when there is none."""
    from mathutils import Vector
    top = max(s.hi[2] for s in geo.solids.values() if len(s.verts)) + 1.0
    org, floors = Vector((x, y, top)), []
    for _ in range(40):
        h = geo.ray(org, Vector((0, 0, -1)), top + 1000)
        if h is None:
            break
        if abs(h[1].z) > 0.7 and geo.ray(h[0] + Vector((0, 0, 0.01)), Vector((0, 0, 1)), 1.8) is None:
            floors.append(h[0].z)
        org = h[0] + Vector((0, 0, -1e-3))
    return min(floors) if floors else None


def walk_samples(geo, pts, step):
    """Points every `step` m along a path [[x, y(, z)], ...] as (x, y, dir_x, dir_y, floor_z); floor_z is None where no floor was
    found. The floor is followed from sample to sample (stairs); where it is lost or not known yet, the lowest walkable surface
    under the point is taken (or the first point's z, if the path gives one)."""
    from mathutils import Vector
    floor = float(pts[0][2]) if len(pts[0]) > 2 else None
    out, marks = [], []
    for (x0, y0, *_), (x1, y1, *_) in zip(pts, pts[1:]):
        ln = np.hypot(x1 - x0, y1 - y0)
        if ln < 1e-9:
            continue
        k = max(1, int(ln / step))
        marks += [(x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k, (x1 - x0) / ln, (y1 - y0) / ln) for t in range(k)]
    if marks:
        marks.append((pts[-1][0], pts[-1][1], marks[-1][2], marks[-1][3]))
    for x, y, dx, dy in marks:
        f = None
        if floor is not None:
            h = geo.ray(Vector((x, y, floor + 0.45)), Vector((0, 0, -1)), 1.05)
            f = h[0].z if h is not None and h[0].z >= floor - 0.6 else None
        if f is None:
            f = find_floor(geo, x, y)
        floor = f
        out.append((x, y, dx, dy, f))
    return out
