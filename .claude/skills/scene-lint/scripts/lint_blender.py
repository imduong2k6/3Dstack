"""scene-lint for Blender: every countable defect in one run, written to lint.json (tested headless with bpy 5.2.3).

    bash bin/blender-bg <copy.blend> --python .claude/skills/scene-lint/scripts/lint_blender.py -- \
        --project projects/<slug> --out projects/<slug>/reviews/<gate>-r<n> [--expect-file <gate copy>] [--baseline <earlier lint.json>] [--only a,b] [--skip a,b]

Exit 0: no blocker. Exit 2: at least one blocker (lint.json is written). Exit 1: the script itself failed or a check crashed.
Inputs are read from --project when present (light/cameras.json, light/lights.json, light/exposure.json, plan/steps.json,
plan/lint_rules.yaml, plan/walk.json, plan/visible_set.json); every one can be given with its own flag. A check without its input is
reported as skipped, and a check with nothing to check as no_subjects: neither is a pass.

In the live Blender (capture.py does this): exec the file, then run_lint(project=..., out_dir=...) returns the report.
"""
import json
import math
import os
import re
import sys
import time
import traceback
from collections import Counter

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None
if HERE:
    sys.path.insert(0, HERE)
import lintlib as L  # noqa: E402

VERSION = 1
CLASSES = ("blocker", "major", "minor")
MEASURE = re.compile(r"(?<![A-Za-z_])-?\d+(\.\d+)?")


def item_key(it):
    """A problem's identity between runs: its object and its text with the measured numbers taken out, so one that moved 2 mm is not new."""
    return f"{it['object']}|{MEASURE.sub('#', it.get('what', ''))}"
LIGHT_TYPES = {"point": "POINT", "area": "AREA", "spot": "SPOT", "sun": "SUN", "directional": "SUN"}
DEFAULT_NAMES = re.compile(r"^(Cube|Plane|Sphere|Cylinder|Cone|Torus|Circle|Grid|Monkey|Suzanne|Icosphere|Empty|Mesh|Curve|Text|"
                           r"Light|Camera|Point|Sun|Spot|Area|Lamp|Bezier\w*|Nurbs\w*|Path)(\.\d+)?$", re.I)
UCX_NAME = re.compile(r"^UCX_SM_[A-Za-z0-9]+(_[A-Za-z0-9]+)*_\d\d$")
EXEMPT_FROM_PHASE = ("COL_Kit", "COL_Ref", "COL_Collision", "COL_Parked", "COL_Lights", "COL_Cameras")


class Ctx:
    def __init__(self, scene, rules, paths):
        self.scene, self.rules, self.paths = scene, rules, paths
        self.view_layer = bpy.context.view_layer
        self.dg = bpy.context.evaluated_depsgraph_get()
        self.geo = L.Geo(scene, rules, self.dg)
        self.off = L.render_off_collections(scene)
        self.vs = L.load_json(paths["visible"]) if paths.get("visible") and os.path.exists(paths["visible"]) else None
        tested = set(self.vs["tested"]) if self.vs else set()
        self.visible = set(self.vs["visible"]) if self.vs else set()
        self.new_since_visible = sorted(n for n in self.geo.names if self.vs and n not in tested)
        self.slist = [s for s in self.geo.solids.values() if len(s.tris)]
        self.lo, self.hi = (np.array([s.lo for s in self.slist]), np.array([s.hi for s in self.slist])) if self.slist else (np.zeros((0, 3)), np.zeros((0, 3)))
        self.checks = {}
        self.all_items = {}

    def containing(self, p, exclude=()):
        """Solids that enclose the point p (box first, then ray parity)."""
        q = np.array(p)
        idx = np.where(np.all((self.lo <= q) & (self.hi >= q), axis=1))[0]
        return [s for s in (self.slist[i] for i in idx) if s.name not in exclude and "cable" not in s.kinds and s.inside(p)]

    def scoped(self, name):
        """Geometric checks look only at what the walk paths and review cameras see; objects added since the set was written count."""
        return self.vs is None or name in self.visible or name in self.new_since_visible

    def seen_by(self, name):
        return sorted(self.vs["visible"].get(name, {}).get("cams", [])) if self.vs else None

    def sev(self, check, default):
        return self.rules["severity"].get(check, default)

    def add(self, check, cls, checked, items, status=None, note=None, extra=None):
        for it in items:
            it.setdefault("class", self.sev(check, cls))
        counts = {c: sum(1 for it in items if it["class"] == c) for c in CLASSES}
        status = status or ("fail" if counts["blocker"] or counts["major"] else "warn" if items else ("pass" if checked else "no_subjects"))
        cap = self.rules["max_items"]
        self.all_items[check] = items
        self.checks[check] = {"status": status, "class": self.sev(check, cls), "checked": checked, "count": len(items), "counts": counts, "items": items[:cap],
                              **({"items_truncated": len(items) - cap, "keys": [item_key(it) for it in items]} if len(items) > cap else {}),
                              **({"note": note} if note else {}), **(extra or {})}

    def skip(self, check, reason):
        self.checks[check] = {"status": "skipped", "reason": reason, "count": 0, "counts": {c: 0 for c in CLASSES}, "items": []}


def v3(p):
    return [round(float(x), 3) for x in p]


# ---- data checks (not scoped: a defect in the file is a defect wherever it is) --------------------------------

def check_file_path(c):
    expect, cur = c.paths.get("expect_file"), bpy.data.filepath
    if not expect:
        return c.skip("file_path", "no --expect-file given")
    norm = lambda p: os.path.normcase(os.path.realpath(p)) if p else ""
    items = [] if norm(cur) == norm(expect) else [{"object": cur or "(unsaved file)", "what": f"open file is not the expected gate copy {expect}"}]
    c.add("file_path", "blocker", 1, items)


def check_faces_no_material(c):
    items, n = [], 0
    for ob in c.scene.objects:
        if ob.type != "MESH" or not L.is_rendered(ob, c.off) or not len(ob.data.polygons):
            continue
        n += 1
        ok = np.array([bool(s.material) for s in ob.material_slots] + [False])
        idx = np.empty(len(ob.data.polygons), np.int32)
        ob.data.polygons.foreach_get("material_index", idx)
        bad_mask = ~ok[np.minimum(idx, len(ok) - 1)] | (idx >= len(ok) - 1)
        bad = int(bad_mask.sum())
        if bad:
            empty = sorted({int(i) for i in idx[bad_mask]})
            items.append({"object": ob.name, "faces": bad, "slots": empty, "what": f"{bad} faces on empty or missing material slots {empty}"})
    c.add("faces_no_material", "blocker", n, items, extra={"faces_total": sum(i["faces"] for i in items)})


def check_cameras(c):
    path = c.paths.get("cameras")
    if not path or not os.path.exists(path):
        return c.skip("cameras_match", "no light/cameras.json")
    data = L.load_json(path)
    rows = data.get("cameras", data) if isinstance(data, dict) else data
    r, items = c.rules, []
    for row in rows:
        ob = bpy.data.objects.get(row["id"])
        if not ob or ob.type != "CAMERA":
            items.append({"object": row["id"], "what": "camera in cameras.json is missing from the file"})
            continue
        d, bad = ob.data, []
        pos = max(abs(a - b) for a, b in zip(ob.matrix_world.translation, row["pos_m"])) if row.get("pos_m") else 0
        if pos > r["camera_pos_tol_m"]:
            bad.append(f"position off by {pos:.4f} m")
        q = ob.matrix_world.to_quaternion()
        if row.get("rot_deg"):
            ang = math.degrees(q.rotation_difference(Euler([math.radians(x) for x in row["rot_deg"]], "XYZ").to_quaternion()).angle)
            ang = min(ang, 360 - ang)  # q and -q are one rotation, and rotation_difference can read that pair as 360
        elif row.get("aim_m") and row.get("pos_m"):
            want = (Vector(row["aim_m"]) - Vector(row["pos_m"])).normalized()
            ang = math.degrees((q @ Vector((0, 0, -1))).angle(want))
        else:
            ang = 0
        if ang > r["camera_rot_tol_deg"]:
            bad.append(f"rotation off by {ang:.3f} deg")
        tol = r["camera_value_tol"]
        for key, val in (("lens_mm", d.lens), ("sensor_mm", d.sensor_width), ("ortho_scale", d.ortho_scale)):
            if row.get(key) is not None and abs(val - row[key]) > tol * max(1, abs(row[key])):
                bad.append(f"{key} {val:.4g} vs {row[key]}")
        if row.get("shift") and max(abs(d.shift_x - row["shift"][0]), abs(d.shift_y - row["shift"][1])) > tol:
            bad.append(f"shift ({d.shift_x:.4f}, {d.shift_y:.4f}) vs {row['shift']}")
        if row.get("sensor_fit") and d.sensor_fit != row["sensor_fit"]:
            bad.append(f"sensor_fit {d.sensor_fit} vs {row['sensor_fit']}")
        if row.get("type") and d.type != {"persp": "PERSP", "ortho": "ORTHO", "pano": "PANO"}.get(row["type"], row["type"]):
            bad.append(f"type {d.type} vs {row['type']}")
        if bad:
            items.append({"object": row["id"], "what": "; ".join(bad)})
    listed = {row["id"] for row in rows}
    extra = [o.name for o in c.scene.objects if o.type == "CAMERA" and o.name not in listed]
    items += [{"object": n, "class": "minor", "what": "camera in the file is not listed in cameras.json"} for n in extra]
    c.add("cameras_match", "blocker", len(rows), items)


def check_lights(c):
    path = c.paths.get("lights")
    if not path or not os.path.exists(path):
        return c.skip("lights_match", "no light/lights.json")
    data = L.load_json(path)
    rows = data.get("lights", data) if isinstance(data, dict) else data
    r, items, n = c.rules, [], 0
    for row in rows:
        if row.get("off") or row.get("fixture_off") or row.get("parked"):
            continue
        n += 1
        if row.get("object"):  # an emissive mesh stands in for the light
            if row["object"] not in bpy.data.objects:
                items.append({"object": row["id"], "what": f"emissive object {row['object']} named in lights.json is missing from the file"})
            continue
        ob = bpy.data.objects.get(row["id"])
        if not ob or ob.type != "LIGHT":
            items.append({"object": row["id"], "what": "light in lights.json is missing from the file"})
            continue
        bad = []
        want = LIGHT_TYPES.get(str(row.get("type", "")).lower())
        if want and ob.data.type != want:
            bad.append(f"type {ob.data.type} vs {row['type']}")
        if "pos_m" in row:
            off = max(abs(a - b) for a, b in zip(ob.matrix_world.translation, row["pos_m"]))
            if off > r["light_pos_tol_m"]:
                bad.append(f"position off by {off:.3f} m")
        watts = next((row[k] for k in ("energy_w", "blender_w_set", "power_w", "watts") if k in row), None)
        if watts is not None and abs(ob.data.energy - watts) > r["light_power_tol_rel"] * max(1e-6, abs(watts)):
            bad.append(f"power {ob.data.energy:.4g} W vs {watts} W")
        if bad:
            items.append({"object": row["id"], "what": "; ".join(bad)})
    listed = {row["id"] for row in rows}
    items += [{"object": o.name, "class": "minor", "what": "light in the file is not listed in lights.json"}
              for o in c.scene.objects if o.type == "LIGHT" and o.name not in listed]
    c.add("lights_match", "major", n, items)


def check_exposure(c):
    path = c.paths.get("exposure")
    if not path or not os.path.exists(path):
        return c.skip("exposure_match", "no light/exposure.json")
    want, vs, ds = L.load_json(path), c.scene.view_settings, c.scene.display_settings
    items = []

    def cmp(key, now, rec, tol=None):
        if rec is None:
            return
        same = abs(now - rec) <= tol if tol is not None else (now or "None") == (rec or "None")
        if not same:
            items.append({"object": "scene.view_settings." + key, "what": f"{key} is {now} but exposure.json says {rec}"})
    cmp("exposure", vs.exposure, want.get("exposure"), c.rules["exposure_tol"])
    cmp("view_transform", vs.view_transform, want.get("view_transform"))
    cmp("look", vs.look, want.get("look"))
    cmp("display_device", ds.display_device, want.get("display"))
    if want.get("gamma") is not None:
        cmp("gamma", vs.gamma, want["gamma"], c.rules["exposure_tol"])
    if want.get("white_balance") is not None and bool(want["white_balance"]) != vs.use_white_balance:
        items.append({"object": "scene.view_settings.use_white_balance", "what": f"white balance is {vs.use_white_balance} but exposure.json says {want['white_balance']}"})
    if want.get("curves") is not None and bool(want["curves"]) != vs.use_curve_mapping:
        items.append({"object": "scene.view_settings.use_curve_mapping", "what": f"curves are {vs.use_curve_mapping} but exposure.json says {want['curves']}"})
    c.add("exposure_match", "blocker", 1, items)


def check_names_tags(c):
    items, n = [], 0
    r = c.rules
    for ob in c.scene.objects:
        n += 1
        cols = L.parent_collections(ob)
        if DEFAULT_NAMES.match(ob.name):
            items.append({"object": ob.name, "what": "Blender default name"})
        elif re.search(r"\.\d{3,}$", ob.name):
            items.append({"object": ob.name, "class": "minor", "what": "duplicate suffix in the name"})
        if " " in ob.name:
            items.append({"object": ob.name, "what": "space in the name"})
        if ob.type == "CAMERA" and not ob.name.startswith("CAM_"):
            items.append({"object": ob.name, "what": "camera not named CAM_<id>"})
        if (ob.name.startswith("UCX") or "COL_Collision" in cols) and not UCX_NAME.match(ob.name):
            items.append({"object": ob.name, "what": "collision mesh not named UCX_SM_<Name>_NN"})
        if ob.type != "MESH" or not L.is_rendered(ob, c.off) or cols & set(EXEMPT_FROM_PHASE):
            continue
        phase = ob.get("phase") or any(re.match(r"COL_P\d", x) for x in cols)
        if "phase" in r["required_tags"] and not phase:
            items.append({"object": ob.name, "what": "no phase tag (custom property phase, or a COL_P<n> collection)"})
        for tag in r["required_tags"]:
            if tag != "phase" and not ob.get(tag):
                items.append({"object": ob.name, "what": f"no {tag} tag"})
        if "COL_Blockout" in cols and not ob.get("map_id"):
            items.append({"object": ob.name, "what": "blockout object without a map_id tag"})
    used = {s.material for ob in c.scene.objects if ob.type == "MESH" and L.is_rendered(ob, c.off) for s in ob.material_slots if s.material}
    items += [{"object": m.name, "class": "minor", "what": "material without a material_group property"} for m in sorted(used, key=lambda m: m.name) if not m.get("material_group")]
    c.add("names_tags", "major", n, items)


def check_origin(c):
    r, items, n = c.rules, [], 0
    for ob in c.scene.objects:
        if ob.type not in ("MESH", "CURVE", "EMPTY") or not L.is_rendered(ob, c.off) or not ob.name in c.view_layer.objects:
            continue
        if ob.type == "EMPTY" and not ob.instance_collection:
            continue
        n += 1
        if ob.get("origin_ok") or ob.matrix_world.translation.length > r["origin_tol_m"]:
            continue
        s = c.geo.solids.get(ob.name)
        corners = np.array([tuple(ob.matrix_world @ Vector(k)) for k in ob.bound_box]) if s is None else np.array([s.lo, s.hi])
        centre, size = corners.mean(0), np.ptp(corners, axis=0).max()
        if np.linalg.norm(centre) <= r["origin_radius_m"] and size <= r["origin_max_size_m"]:
            items.append({"object": ob.name, "what": "sits at the world origin (a join or append that was never placed); set origin_ok if it belongs there"})
    c.add("origin_objects", "blocker", n, items)


def check_visibility(c):
    r, vl = c.rules, c.view_layer
    lcs = L.layer_collections(vl)
    rev, park = set(r["tokens"]["review"]), set(r["tokens"]["parked"])
    items, states, n = [], {"live": 0, "review-only": 0, "parked": 0}, 0
    for ob in c.scene.objects:
        if ob.type in ("CAMERA",):
            continue
        n += 1
        cols = L.parent_collections(ob)
        toks = L.tokens(ob.name).union(*[L.tokens(x) for x in cols])
        tag = str(ob.get("visibility") or next((col.get("visibility") for col in ob.users_collection if col.get("visibility")), "")).lower()
        is_rev = bool(toks & rev) or tag.replace("_", "-") in ("review-only", "review")
        is_park = bool(toks & park) or tag == "parked" or bool(cols & set(L.PARKED_NAMES))
        in_layer = ob.name in vl.objects
        rendered, shown = L.is_rendered(ob, c.off), (in_layer and L.viewport_visible(ob, vl))
        states["parked" if not in_layer else "review-only" if (is_rev and not rendered and not shown) else "live"] += 1
        if is_rev and in_layer and (rendered or shown):
            where = " and ".join(w for w, on in (("render", rendered), ("viewport", shown)) if on)
            items.append({"object": ob.name, "what": f"review-only object is visible in {where} (it needs hide_render and hide_viewport both on)"})
        elif is_park and not is_rev and in_layer:
            items.append({"object": ob.name, "class": c.sev("visibility_states", "major"),
                          "what": "parked object is still in the view layer (park it by excluding its collection, e.g. COL_Parked)"})
        elif not is_rev and not is_park and in_layer and ob.type in ("MESH", "CURVE") and ob.display_type in ("TEXTURED", "SOLID"):
            if rendered and not shown:
                items.append({"object": ob.name, "class": "major", "what": "renders but is hidden in the viewport: no visibility state allows that"})
            elif not rendered and shown:
                items.append({"object": ob.name, "class": "minor", "what": "visible in the viewport but off for render, and not tagged review-only or parked"})
    c.add("visibility_states", "blocker", n, items, extra={"states": states, "lc_excluded": sorted(k for k, v in lcs.items() if v.exclude)})


def check_wear(c):
    wear, items, n = set(c.rules["tokens"]["wear"]), [], 0
    for ob in c.scene.objects:
        if ob.type in ("CAMERA", "LIGHT") or ob.name not in c.view_layer.objects:
            continue
        n += 1
        if ob.get("wear_ok"):
            continue
        if "wear" in L.kinds_of(ob, c.rules):
            hit = sorted((L.tokens(ob.name).union(*[L.tokens(col.name) for col in ob.users_collection])) & wear) or ["kind=wear"]
            items.append({"object": ob.name, "what": f"wear as geometry ({', '.join(hit)}): house rule 1; write it to handoff/wear-notes.md and remove the object (wear_ok on repairs)"})
    c.add("wear_geometry", "blocker", n, items)


def check_steps(c):
    path = c.paths.get("steps")
    if not path or not os.path.exists(path):
        return c.skip("step_backup", "no plan/steps.json")
    try:
        steps = L.load_json(path).get("steps", [])
    except (L.LintError, AttributeError) as e:
        return c.add("step_backup", "major", 1, [{"object": path, "what": f"the step ledger cannot be read: {e}"}])
    if not steps:
        return c.skip("step_backup", "the ledger has no step yet")
    items = []
    for s in steps:
        b = s.get("backup")
        if not b or not os.path.exists(b) or os.path.getsize(b) == 0:
            items.append({"object": f"step {s.get('n')}", "what": f"backup not on disk: {b}" + (" (the latest step)" if s is steps[-1] else "")})
    c.add("step_backup", "major", len(steps), items)


# ---- geometric checks (scoped to the visible set) ------------------------------------------------------------

def _big_islands(bm, W, share=0.3):
    """Vertex indices of the mesh islands whose box diagonal is at least `share` of the largest one's (drops screws, nuts, tabs)."""
    seen, isl = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, idx = [v], []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            idx.append(x.index)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        pts = np.array([tuple(W(bm.verts[i])) for i in idx])
        isl.append((float(np.linalg.norm(np.ptp(pts, axis=0))), idx))
    top = max(d for d, _ in isl)
    return {i for d, idx in isl if d >= share * top for i in idx}


def _ordered(elems):
    """BMesh elements hash by memory address: a float sum over a set of them would change with every run."""
    return sorted(elems, key=lambda x: x.index)


def object_ends(s, dg, cap_max, strict=False):
    """Real ends of a cable or conduit object, from its structure: spline end points, open boundary loops, planar end caps, or
    wire end vertices. Never from vertex extremes (those pick corners of a bent run). Returns [(point, outward unit vector)], method.
    strict (conduit fittings): ignore small hardware islands (screws, nuts, tabs), open loops under 6 vertices (holes, not tube
    ends) and caps that are not round; a round cap may be as wide as the piece (couplings, short stubs)."""
    ob, mw = s.ob, s.ob.matrix_world
    if ob.type == "CURVE":
        ends = []
        for sp in ob.data.splines:
            if sp.use_cyclic_u:
                continue
            pts = [mw @ (p.co.xyz if hasattr(p.co, "xyz") else Vector(p.co)) for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)]
            if len(pts) >= 2:
                ends += [(pts[0], (pts[0] - pts[1]).normalized()), (pts[-1], (pts[-1] - pts[-2]).normalized())]
        return ends, "spline"
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    W = lambda v: mw @ v.co
    ends = []
    if not bm.faces:  # a wire: vertices with one edge
        for v in bm.verts:
            if len(v.link_edges) == 1:
                o = v.link_edges[0].other_vert(v)
                ends.append((W(v), (W(v) - W(o)).normalized()))
        bm.free()
        return ends, "wire"
    centre = sum((W(v) for v in bm.verts), Vector()) / len(bm.verts)
    diag = max(1e-6, (np.ptp([tuple(W(v)) for v in bm.verts], axis=0)).max())
    big = _big_islands(bm, W) if strict else None
    # open tube ends: loops of boundary edges
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    seen = set()
    for e0 in bnd:
        if e0.index in seen:
            continue
        loop, stack = set(), [e0]
        while stack:
            e = stack.pop()
            if e.index in seen:
                continue
            seen.add(e.index)
            loop.add(e)
            for v in e.verts:
                stack += [x for x in v.link_edges if len(x.link_faces) == 1 and x.index not in seen]
        vs = {v for e in loop for v in e.verts}
        if strict and (len(vs) < 6 or any(v.index not in big for v in vs)):
            continue
        p = sum((W(v) for v in _ordered(vs)), Vector()) / len(vs)
        inner = [W(o) for v in _ordered(vs) for e in v.link_edges for o in [e.other_vert(v)] if o not in vs]
        back = sum(inner, Vector()) / len(inner) if inner else centre
        ends.append((p, (p - back).normalized() if (p - back).length > 1e-9 else Vector((0, 0, 1))))
    # capped tube ends: a planar cluster of faces whose neighbours all meet it at a steep angle
    done = set()
    for f in bm.faces:
        if f.index in done:
            continue
        cl, stack, n0 = {f}, [f], f.normal.copy()
        done.add(f.index)
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in done and h.normal.dot(n0) > 0.9995:
                        done.add(h.index)
                        cl.add(h)
                        stack.append(h)
        edges = {e for g in cl for e in g.edges if any(h not in cl for h in e.link_faces) or len(e.link_faces) == 1}
        if len(edges) < 3 or any(len(e.link_faces) == 1 for e in edges):
            continue
        outside = [h for e in _ordered(edges) for h in e.link_faces if h not in cl]
        bv = {v for e in edges for v in e.verts}
        pts = [W(v) for v in _ordered(bv)]
        ext = max((a - b).length for a in pts for b in pts)
        p = sum(pts, Vector()) / len(pts)
        if strict:
            rs = [(q - p).length for q in pts]
            if ext > cap_max or len(bv) < 8 or max(rs) - min(rs) > 0.2 * max(rs) or any(v.index not in big for v in bv):
                continue
        elif ext > cap_max or ext > 0.6 * diag:
            continue
        nw = (mw.to_3x3() @ n0).normalized()
        radial = 0  # at a tube's end the faces beyond the boundary point radially outward from the cap's centre
        for e in edges:
            r = (W(e.verts[0]) + W(e.verts[1])) / 2 - p
            r -= nw * r.dot(nw)
            h = next(h for h in e.link_faces if h not in cl)
            if r.length > 1e-9 and (mw.to_3x3() @ h.normal).normalized().dot(r.normalized()) > 0.7:
                radial += 1
        if radial < 0.8 * len(edges):
            continue
        behind = [W(v) for h in outside for v in h.verts if v not in bv]
        back = sum(behind, Vector()) / len(behind) if behind else centre
        ends.append((p, (p - back).normalized() if (p - back).length > 1e-9 else Vector((0, 0, 1))))
    bm.free()
    return ends, "mesh"


def classify_end(c, owner, e, out, anchor_kinds, tol, entry_tol, join_cables=False, own=None):
    """-> (class, via, joint_names): attached (touches an anchor), terminated (enters a surface head-on), dead_end (a tail along a
    surface, or floating). With join_cables, a touch on another cable comes back as class 'joint' for the caller to settle. With
    own (the object's Solid), an end that runs into another part of its own mesh (merged fittings) is attached too."""
    near = c.geo.near(e, max(tol, 0.05), exclude={owner})
    sol = c.geo.solids
    anchors = sorted((d, n) for n, (d, _, _) in near.items() if d <= tol and (sol[n].kinds & anchor_kinds) and "cable" not in sol[n].kinds)
    if anchors:
        return "attached", "anchor:" + anchors[0][1], []
    if own is not None and own.inside(e + out * 0.004):
        return "attached", "own part", []
    buried = c.containing(e, {owner})  # an end sunk into a box or a wall disappears into it, as an entry does
    if buried:
        host = next((s for s in buried if s.kinds & anchor_kinds), buried[0])
        return ("attached", "inside:" + host.name, []) if host.kinds & anchor_kinds else ("terminated", "buried in " + host.name, [])
    joints = sorted(n for n, (d, _, _) in near.items() if d <= tol and "cable" in sol[n].kinds) if join_cables else []
    surf = sorted((d, n) for n, (d, _, _) in near.items() if "cable" not in sol[n].kinds)
    if surf:
        d, n = surf[0]
        nrm = near[n][2]
        if d <= entry_tol and (abs(out.dot(nrm.normalized())) >= 0.707 or sol[n].inside(e)):
            return "terminated", "entry:" + n, joints
        if joints:
            return "joint", "joint", joints
        return "dead_end", "tail along " + n, []
    if joints:
        return "joint", "joint", joints
    return "dead_end", "float", []


def check_cables(c):
    r, g = c.rules, c.geo
    cables = [s for s in g.of_kind("cable") if s.ob.type in ("MESH", "CURVE")]
    if not cables:
        c.skip("cable_ends", "no object is a cable (tag kind=cable or name one)")
        return c.skip("cable_sag", "no cables")
    rows = {}
    anchor_kinds = {"anchor"}
    for s in cables:
        ends, method = object_ends(s, c.dg, r["cap_max_m"])
        rows[s.name] = {"method": method, "ends": []}
        if len(ends) < 2 or len(ends) % 2 or len(ends) > 16:  # a generated or damaged mesh: its ends cannot be read, so none is guessed
            rows[s.name]["unresolved"] = len(ends)
            continue
        for p, out in ends:
            if s.ob.get("ends_ok"):
                cls, via, joints = "terminated", "ends_ok", []
            else:
                cls, via, joints = classify_end(c, s.name, p, out, anchor_kinds, r["cable_anchor_tol_m"], r["cable_entry_tol_m"], join_cables=True)
            rows[s.name]["ends"].append({"at": v3(p), "class": cls, "via": via, "joints": joints})
    # a joint to another cable only counts when that cable reaches an anchor or a surface itself (floating cables must not vouch for each other)
    grounded = {n for n, row in rows.items() if any(e["class"] in ("attached", "terminated") for e in row["ends"])}
    changed = True
    while changed:
        changed = False
        for n, row in rows.items():
            for e in row["ends"]:
                if e["class"] == "joint" and any(j in grounded for j in e["joints"]):
                    e["class"], e["via"] = "attached", "joint:" + next(j for j in e["joints"] if j in grounded)
                    if n not in grounded:
                        grounded.add(n)
                        changed = True
    for row in rows.values():
        for e in row["ends"]:
            if e["class"] == "joint":
                e["class"], e["via"] = "dead_end", "joint to an ungrounded cable: " + ", ".join(e["joints"])
    items, tally, sag_items, unresolved = [], {"attached": 0, "terminated": 0, "dead_end": 0}, [], []
    for s in cables:
        row = rows[s.name]
        if not c.scoped(s.name):
            continue
        for e in row["ends"]:
            tally[e["class"]] += 1
        if "unresolved" in row:
            items.append({"object": s.name, "class": "minor", "what": f"found {row['unresolved']} ends in the mesh, so none could be classified: check it by eye (a pass would be a guess)"})
            unresolved.append(s.name)
            continue
        dead = [e for e in row["ends"] if e["class"] == "dead_end"]
        if dead:
            items.append({"object": s.name, "what": "dead end: " + "; ".join(f"{e['via']} at {e['at']}" for e in dead), "ends": row["ends"], "seen_by": c.seen_by(s.name)})
        a, b = np.array(row["ends"][0]["at"]), np.array(max(row["ends"], key=lambda e: np.linalg.norm(np.array(e["at"]) - np.array(row["ends"][0]["at"])))["at"])
        span = float(np.linalg.norm(b - a))
        if span > 0.3:
            t = ((s.verts - a) @ (b - a)) / span ** 2
            mid = (t > 0.3) & (t < 0.7)
            if mid.any():
                sag = float((a[2] + (b[2] - a[2]) * t[mid] - s.verts[mid, 2]).max())
                if sag / span > r["cable_sag_max_ratio"]:
                    sag_items.append({"object": s.name, "what": f"sags {sag:.2f} m over a {span:.2f} m span ({sag / span:.0%}; limit {r['cable_sag_max_ratio']:.0%})"})
    checked = sum(1 for s in cables if c.scoped(s.name))
    c.add("cable_ends", "major", checked, items, extra={"ends": tally, "cables_total": len(cables), "unresolved": len(unresolved)})
    c.add("cable_sag", "minor", checked, sag_items)


def check_conduit_ends(c):
    r, g = c.rules, c.geo
    conduits = [s for s in g.of_kind("conduit") if s.ob.type in ("MESH", "CURVE") and c.scoped(s.name) and not s.ob.get("ends_ok")]
    if not conduits:
        return c.skip("conduit_open_ends", "no object is a conduit or fitting (tag kind=conduit or name one)")
    items, ends_n, unresolved = [], 0, 0
    for s in conduits:
        ends, _ = object_ends(s, c.dg, r["cap_max_m"], strict=True)
        if not 1 <= len(ends) <= 16:  # a piece or a merged run; more means a generated or damaged mesh whose ends cannot be read
            items.append({"object": s.name, "class": "minor", "what": f"found {len(ends)} ends in the mesh, so none could be classified: check it by eye (a pass would be a guess)"})
            unresolved += 1
            continue
        bad = []
        for p, out in ends:
            ends_n += 1
            cls, via, _ = classify_end(c, s.name, p, out, {"anchor", "conduit"}, r["conduit_end_tol_m"], r["conduit_end_tol_m"], own=s)
            if cls == "dead_end":
                bad.append(v3(p))
        if bad:
            items.append({"object": s.name, "what": f"{len(bad)} open end(s) at {bad}: meets no conduit, fitting, box, meter, fixture or wall", "seen_by": c.seen_by(s.name)})
    c.add("conduit_open_ends", "major", len(conduits), items, extra={"ends_checked": ends_n, "unresolved": unresolved})


def _touching(a, b, tol, cache):
    key = (a.name, b.name)
    if key in cache:
        return cache[key]
    res = False
    if a.bvh is not None and b.bvh is not None:
        res = bool(a.bvh.overlap(b.bvh))
        if not res:
            for x, y in ((a, b), (b, a)):
                for p in x.samples():
                    h = y.bvh.find_nearest(Vector(p), tol)
                    if h[0] is not None:
                        res = True
                        break
                if res:
                    break
    cache[key] = cache[(b.name, a.name)] = res
    return res


def penetration(a, b, hits):
    """How deep two solids cross: for every crossing triangle pair, the smaller of how far each triangle reaches to both sides of
    the other's plane; the largest over all pairs, and where. (A box overlap is no measure for merged meshes.)"""
    ia, ib = np.array([h[0] for h in hits]), np.array([h[1] for h in hits])
    ta, tb = a.verts[a.tris[ia]], b.verts[b.tris[ib]]

    def poke(t, u):
        n = np.cross(u[:, 1] - u[:, 0], u[:, 2] - u[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        sd = np.einsum("nvk,nk->nv", t - u[:, :1], n)
        return np.minimum(np.maximum(sd.max(1), 0), np.maximum(-sd.min(1), 0))
    d = np.minimum(poke(ta, tb), poke(tb, ta))
    k = int(d.argmax())
    return float(d[k]), ta[k].mean(0)


def check_float_and_overlap(c):
    r, g = c.rules, c.geo
    solids = [s for s in g.solids.values() if len(s.tris)]
    if not solids:
        c.skip("floating", "no rendered mesh")
        return c.skip("interpenetration", "no rendered mesh")
    lo, hi = np.array([s.lo for s in solids]), np.array([s.hi for s in solids])
    tol, cache = r["float_tol_m"], {}
    gz = L.ground_z(g, r)
    seen = {i for i, s in enumerate(solids) if lo[i][2] <= gz + tol or ("walkable" in s.kinds and (s.hi[0] - s.lo[0]) * (s.hi[1] - s.lo[1]) >= 1.0)}
    queue = list(seen)
    while queue:  # grow the set of objects that reach the ground through touching neighbours
        u = queue.pop()
        cand = np.where(np.all((lo <= hi[u] + tol) & (hi >= lo[u] - tol), axis=1))[0]
        for v in cand:
            if v not in seen and _touching(solids[u], solids[v], tol, cache):
                seen.add(v)
                queue.append(v)
    subjects = [i for i, s in enumerate(solids) if "cable" not in s.kinds and not s.ob.get("float_ok") and c.scoped(s.name)]
    c.add("floating", "major", len(subjects),
          [{"object": solids[i].name, "at": v3((lo[i] + hi[i]) / 2), "what": f"floats: no chain of touching objects (within {tol} m) reaches the ground"}
           for i in subjects if i not in seen], extra={"ground_z_m": round(float(gz), 3)})
    # interpenetration: boxes overlap by more than the tolerance on every axis AND surfaces cross
    pen, items, checked = r["penetration_tol_m"], [], 0
    allow = [(str(x).lower(), str(y).lower()) for x, y in r["overlap_allow"]]
    idx = [i for i, s in enumerate(solids) if "cable" not in s.kinds and not s.ob.get("overlap_ok") and c.scoped(s.name)]
    for k, i in enumerate(idx):
        a, rest = solids[i], np.array(idx[k + 1:], int)
        if not len(rest):
            break
        ovs = np.minimum(hi[i], hi[rest]) - np.maximum(lo[i], lo[rest])
        for j, ov in zip(rest[ovs.min(1) > pen], ovs[ovs.min(1) > pen]):
            b = solids[j]
            if a.ob.parent == b.ob or b.ob.parent == a.ob:
                continue
            ta, tb = L.tokens(a.name), L.tokens(b.name)
            if any((x in ta and y in tb) or (y in ta and x in tb) for x, y in allow):
                continue
            checked += 1
            hits = a.bvh.overlap(b.bvh)
            if hits:
                depth, at = penetration(a, b, hits)
                if depth > pen:
                    items.append({"object": f"{a.name} x {b.name}", "faces": len(hits), "depth_m": round(depth, 3), "at": v3(at),
                                  "what": f"surfaces cross {depth:.3f} m deep near {v3(at)} (limit {pen} m)"})
    items.sort(key=lambda it: -it["depth_m"])
    c.add("interpenetration", "major", len(idx), items, extra={"pairs_tested": checked})


def check_through_wall(c):
    g, r = c.geo, c.rules
    things = [s for s in g.of_kind("through_wall") if c.scoped(s.name) and len(s.tris)]
    walls = [s for s in g.of_kind("wall") if len(s.tris)]
    if not things:
        return c.skip("through_wall_openings", "no through-wall item (vent, louvre, fan, AC unit: tag kind=through_wall or name it)")
    items = []
    for it in things:
        best = None
        for w in walls:
            ov = np.minimum(it.hi, w.hi) - np.maximum(it.lo, w.lo)
            if w.name == it.name or ov.min() <= 0.005:
                continue
            ev, vec = np.linalg.eigh(np.cov((w.verts - w.verts.mean(0)).T))
            if ev[0] > 0.25 * ev[1]:
                continue  # not a thin slab: its normal is unclear
            n = vec[:, 0] / np.linalg.norm(vec[:, 0])
            a, b = (w.verts @ n).min(), (w.verts @ n).max()
            ip = it.verts @ n
            lap = min(b, ip.max()) - max(a, ip.min())
            if lap > 0.01 and (best is None or lap > best[0]):
                best = (lap, w, n, a, b)
        if not best:
            continue
        _, w, n, a, b = best
        t1 = np.cross(n, [0, 0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0, 0])
        t1 /= np.linalg.norm(t1)
        t2 = np.cross(n, t1)
        ctr = (it.lo + it.hi) / 2
        if abs(ctr @ n - b) < abs(ctr @ n - a):  # probe from the face the item sits on
            n, a, b = -n, -b, -a
        ext = [np.ptp(it.verts @ t1), np.ptp(it.verts @ t2)]
        offs = [(0, 0), (.3, 0), (-.3, 0), (0, .3), (0, -.3), (.2, .2), (.2, -.2), (-.2, .2), (-.2, -.2)]  # the middle of the footprint, so a round hole passes
        depths = []  # free depth into the wall behind each probe, None when the ray gets through
        for ox, oy in offs:
            q = ctr + t1 * ox * ext[0] + t2 * oy * ext[1]
            q = q - n * (q @ n) + n * (a - 0.05)
            hit = w.bvh.ray_cast(Vector(q), Vector(n), (b - a) + 0.1)
            depths.append(None if hit[0] is None else max(0.0, hit[3] - 0.05))
        solid = sorted(d for d in depths if d is not None)
        if len(solid) <= len(offs) // 2:
            continue  # cut through
        pocket = solid[len(solid) // 2]
        where = {"object": it.name, "wall": w.name, "at": v3(ctr), "through_probes": f"{len(offs) - len(solid)}/{len(offs)}", "pocket_m": round(pocket, 3)}
        if pocket >= r["vent_pocket_min_m"]:
            items.append({**where, "class": "minor", "what": f"sits in a blind pocket {pocket:.2f} m deep in {w.name}, not cut through: fine while the far side is never seen"})
        else:
            items.append({**where, "what": f"sits on solid {w.name}: {pocket:.3f} m of free depth behind it; cut the opening with an applied boolean (through, where the far side can be seen), or a pocket at least {r['vent_pocket_min_m']} m deep"})
    c.add("through_wall_openings", "major", len(things), items)


def _oriented_dims(s):
    R = np.array(s.ob.matrix_world.to_3x3().normalized())
    return sorted(np.ptp(s.verts @ R, axis=0))


def check_doors(c):
    r = c.rules
    doors = [s for s in c.geo.of_kind("door") if c.scoped(s.name) and len(s.verts)]
    if not doors:
        return c.skip("door_sizes", "no door (tag kind=door or name it)")
    items = []
    for s in doors:
        t, w, h = _oriented_dims(s)
        w = s.ob.get("clear_width_m", w)
        if w < r["door_min_width_m"] - r["size_tol_m"]:
            items.append({"object": s.name, "width_m": round(float(w), 3), "what": f"door width {w:.3f} m is under {r['door_min_width_m']} m"})
        if h < r["door_min_height_m"] - r["size_tol_m"]:
            items.append({"object": s.name, "height_m": round(float(h), 3), "what": f"door height {h:.3f} m is under {r['door_min_height_m']} m"})
    c.add("door_sizes", "major", len(doors), items)


def check_stairs(c):
    r = c.rules
    stairs = [s for s in c.geo.of_kind("stair") if c.scoped(s.name) and len(s.tris)]
    if not stairs:
        return c.skip("stair_risers", "no stairs (tag kind=stair or name them)")
    groups = {}
    for s in stairs:
        groups.setdefault(str(s.ob.get("stair_id") or re.sub(r"(?:[_.\- ]+[A-Za-z]|[_.\- ]*\d+)$", "", s.name)), []).append(s)
    items = []
    for gid, ss in groups.items():
        zs, tops = [], []
        for s in ss:  # upward-facing triangles: their height is a tread level, their corners give the tread's size
            tri = s.verts[s.tris]
            n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            ln = np.linalg.norm(n, axis=1)
            up = (n[:, 2] / np.maximum(ln, 1e-12) > 0.95) & (ln / 2 > 1e-4)
            zs += list(tri[up].mean(1)[:, 2])
            tops += list(tri[up])
        if not zs:
            items.append({"object": gid, "class": "minor", "what": "stairs have no upward-facing faces to measure"})
            continue
        zs, tops = np.array(zs), np.array(tops)
        order = np.argsort(zs)
        levels, cur = [], [order[0]]
        for i in order[1:]:
            if zs[i] - zs[cur[-1]] <= 0.006:
                cur.append(i)
            else:
                levels.append(cur)
                cur = [i]
        levels.append(cur)
        lv = [float(np.mean(zs[k])) for k in levels]
        risers = [b - a for a, b in zip(lv, lv[1:]) if 0.03 < b - a <= r["stair_flight_gap_m"]]
        depths = []
        for k in levels:
            pts = tops[k].reshape(-1, 3)
            depths.append(float(min(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))))
        if risers and max(risers) > r["riser_max_m"] + 5e-4:
            items.append({"object": gid, "riser_max_m": round(max(risers), 3), "risers": [round(x, 3) for x in risers],
                          "what": f"riser {max(risers):.3f} m is over {r['riser_max_m']} m"})
        if len(risers) > 1 and max(risers) - min(risers) > r["riser_uneven_max_m"]:
            items.append({"object": gid, "class": "minor", "what": f"uneven risers: {min(risers):.3f} to {max(risers):.3f} m"})
        if len(levels) > 2 and min(depths[1:-1] or depths) < r["tread_min_m"] - 5e-4:
            items.append({"object": gid, "tread_min_m": round(min(depths[1:-1] or depths), 3), "what": f"tread {min(depths[1:-1] or depths):.3f} m is under {r['tread_min_m']} m"})
    c.add("stair_risers", "major", len(groups), items)


def _clearance(g, loc, f, hcap):
    """Height of a hit over the walker's floor f. Above the capsule, over the floor under the hit if that is lower: over a stair or
    landing edge a sphere or side ray reaches past the walker's own floor, and an object can clear the floor below it."""
    clear = loc.z - f
    if clear > hcap:
        under = L.floor_under(g, loc.x, loc.y, loc.z)
        clear = loc.z - (f if under is None else min(f, under))
    return clear


def _sphere_hit(g, p, f, rad, hcap, head, isw):
    """The nearest object in the sphere at p that breaks clearance, as (kind, name, clearance), or None."""
    for _, n, loc in sorted((d, n, loc) for n, (d, loc, _) in g.near(p, rad).items() if not isw(n)):
        clear = _clearance(g, loc, f, hcap)
        if clear < head:
            return ("head" if clear > hcap else "capsule"), n, round(clear, 2)
    return None


def check_path_clearance(c):
    r, g = c.rules, c.geo
    paths, _ = L.read_paths(c.paths.get("walk"), c.paths.get("layout"))
    if not paths:
        return c.skip("path_clearance", "no walk.json (and no path in plan/layout.json)")
    rad, hcap, head = r["capsule_radius_m"], r["capsule_height_m"], r["head_min_m"]
    sweep = [0.60 + 0.05 * i for i in range(round((head - rad - 0.60) / 0.05) + 1)]  # sphere centres: the top sphere reaches head_min
    stairish = set(r["tokens"]["walkable"])
    isw = lambda n: bool(L.tokens(n) & stairish)
    items, summary, checked = [], {}, 0
    for pname, pts in paths.items():
        samples = L.walk_samples(g, pts, 0.1)
        found, minw, minh = {}, [9, None], [9, None]
        for (x, y, dx, dy, f) in samples:
            checked += 1
            if f is None:
                found.setdefault(("floor", "no floor under the path"), []).append((x, y, None))
                continue
            side = Vector((-dy, dx, 0))
            for hh in sweep:
                hit = _sphere_hit(g, Vector((x, y, f + hh)), f, rad, hcap, head, isw)
                if hit:
                    found.setdefault(hit[:2], []).append((x, y, hit[2]))
                    break
            for hh in (0.15, 0.30):
                for a in range(8):
                    h = g.ray(Vector((x, y, f + hh)), Vector((math.cos(a * math.pi / 4), math.sin(a * math.pi / 4), 0)), rad)
                    if h and not isw(h[2]):
                        found.setdefault(("low", h[2]), []).append((x, y, hh))
                        break
            for hh in (0.35, 0.5, 1.0, 1.7, 1.95):  # shin-height clutter and wall fittings in the headroom narrow the path too
                w, who = 0.0, []
                for sgn in (1, -1):
                    h = g.ray(Vector((x, y, f + hh)), side * sgn, 1.0)
                    if h and hh > hcap and h[1].dot(side * sgn) > 0:
                        h = None  # a back face above the capsule: the ray starts inside something overhead, a headroom item
                    w += h[3] if h else 1.0
                    who.append(h[2] if h else None)
                if w < minw[0]:
                    minw = [w, (x, y, hh, who)]
                if w < r["passage_min_width_m"]:
                    found.setdefault(("width", "|".join(str(q) for q in who)), []).append((x, y, round(w, 2)))
                    break
            for off in (0.0, 0.3, -0.3):
                h = g.ray(Vector((x, y, f + 0.9)) + side * off, Vector((0, 0, 1)), head - 0.9)
                clear = _clearance(g, h[0], f, hcap) if h else head
                if clear < head:
                    minh = min(minh, [clear, (x, y, off, h[2])], key=lambda q: q[0])
                    found.setdefault(("head", h[2]), []).append((x, y, round(clear, 2)))
                    break
        for (kind, who), pos in found.items():
            what = {"floor": "no floor under the path", "capsule": f"{who} is inside the player capsule",
                    "low": f"{who} blocks at knee height", "width": f"clear width under {r['passage_min_width_m']} m between {who}",
                    "head": f"{who} is under {r['head_min_m']} m overhead"}[kind]
            items.append({"object": who if kind != "floor" else pname, "path": pname, "type": kind, "samples": len(pos), "first_at": v3(pos[0][:2]),
                          "worst": min(p[2] for p in pos) if kind in ("width", "head") else None, "what": f"path {pname}: {what} ({len(pos)} samples)"})
        summary[pname] = {"samples": len(samples), "min_width_m": round(minw[0], 3) if minw[1] else None,
                          "lowest_head_m": round(minh[0], 3) if minh[1] else None}
    c.add("path_clearance", "major", checked, items, extra={"paths": summary})


CHECKS = [("file_path", check_file_path), ("faces_no_material", check_faces_no_material), ("cameras_match", check_cameras),
          ("lights_match", check_lights), ("exposure_match", check_exposure), ("names_tags", check_names_tags),
          ("origin_objects", check_origin), ("visibility_states", check_visibility), ("wear_geometry", check_wear),
          ("step_backup", check_steps), ("cable_ends", check_cables), ("conduit_open_ends", check_conduit_ends),
          ("floating", check_float_and_overlap), ("through_wall_openings", check_through_wall), ("door_sizes", check_doors),
          ("stair_risers", check_stairs), ("path_clearance", check_path_clearance)]
# a function may write several checks (cable_ends + cable_sag, floating + interpenetration); the key is what --only/--skip name


def resolve_paths(project, **given):
    d = lambda *p: os.path.join(project, *p) if project else None
    paths = {"cameras": d("light", "cameras.json"), "lights": d("light", "lights.json"), "exposure": d("light", "exposure.json"),
             "steps": d("plan", "steps.json"), "rules": d("plan", "lint_rules.yaml"), "walk": d("plan", "walk.json"),
             "layout": d("plan", "layout.json"), "visible": d("plan", "visible_set.json")}
    for k, v in given.items():
        if v == "none":  # --visible none: the whole scene (review_scope: whole_scene)
            paths[k] = None
        elif v:
            if not os.path.exists(v) and k != "expect_file":
                raise L.LintError(f"--{k.replace('_', '-')} file not found: {v}")
            paths[k] = v
        elif k == "expect_file":
            paths[k] = None
    return paths


def load_baseline(path):
    try:
        with open(path) as f:
            old = json.load(f)
    except (OSError, ValueError) as e:
        raise L.LintError(f"--baseline {path}: {e}")
    if not isinstance(old, dict) or old.get("tool") != "scene-lint" or "checks" not in old:
        raise L.LintError(f"--baseline {path} is not a lint.json")
    return old


def diff_baseline(old, path, c):
    """What this run found that the baseline run did not, per check. A check that didn't run here says nothing either way."""
    new, gone, partial = {}, 0, []
    for name, items in c.all_items.items():
        och = old["checks"].get(name, {})
        if och.get("items_truncated") and "keys" not in och:
            partial.append(name)   # an older lint.json lists only its first items, so the rest read as new
        left = Counter(och.get("keys") or [item_key(it) for it in och.get("items", [])])
        fresh = []
        for it in items:
            k = item_key(it)
            if left[k] > 0:
                left[k] -= 1
            else:
                fresh.append(it)
        if fresh:
            new[name] = fresh
        gone += sum(left.values())
    counts = {k: sum(1 for items in new.values() for it in items if it["class"] == k) for k in CLASSES}
    return {"baseline": {"file": path, "created": old.get("created"), "new": counts, "gone": gone, "partial": sorted(partial)}, "new": new}


def run_lint(project=None, out_dir=None, expect_file=None, only=None, skip=None, baseline=None, **files):
    """Run the checks on the open file, write <out_dir>/lint.json and return the report."""
    t0 = time.time()
    old = load_baseline(baseline) if baseline else None
    paths = resolve_paths(project, expect_file=expect_file, **files)
    rules = L.load_rules(paths["rules"] if paths["rules"] and os.path.exists(paths["rules"]) else None)
    c = Ctx(bpy.context.scene, rules, paths)
    names = [n for n, _ in CHECKS]
    for n in (only or []) + (skip or []):
        if n not in names:
            raise L.LintError(f"unknown check {n}; known: {', '.join(names)}")
    errors = []
    for name, fn in CHECKS:
        if (only and name not in only) or name in (skip or []) or name in rules["disable"]:
            continue
        t1 = time.time()
        try:
            fn(c)
        except Exception as e:  # a crashed check must never read as a pass
            errors.append(name)
            c.checks[name] = {"status": "error", "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-900:], "count": 0,
                              "counts": {k: 0 for k in CLASSES}, "items": []}
        for k in (name, "cable_sag", "interpenetration"):
            if k in c.checks and "seconds" not in c.checks[k]:
                c.checks[k]["seconds"] = round(time.time() - t1, 2)
    totals = {k: sum(ch["counts"][k] for ch in c.checks.values()) for k in CLASSES}
    blockers = [{"check": n, "object": it["object"], "what": it["what"]} for n, ch in c.checks.items() for it in ch["items"] if it["class"] == "blocker"]
    state = L.scene_state()
    rep = {"tool": "scene-lint", "version": VERSION, "file": bpy.data.filepath, "expected_file": expect_file, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
           "command": sys.argv, "project": project, "inputs": paths,   # so two runs that disagree can be traced to their inputs
           "seconds": round(time.time() - t0, 1), "blender": bpy.app.version_string,
           "scene": {k: state[k] for k in ("objects", "name_hash", "cam_light_hash")},
           "scope": {"visible_set": paths["visible"] if c.vs else None, "solids": len(c.geo.solids),
                     "in_scope": sum(1 for n in c.geo.names if c.scoped(n)), "added_since_visible_set": len(c.new_since_visible)},
           "rules": {k: v for k, v in rules.items() if k not in ("tokens", "exclude_tokens")},
           "summary": {"blocker": totals["blocker"], "major": totals["major"], "minor": totals["minor"], "pass": totals["blocker"] == 0 and not errors,
                       "skipped": {n: ch["reason"] for n, ch in c.checks.items() if ch["status"] == "skipped"},
                       "no_subjects": sorted(n for n, ch in c.checks.items() if ch["status"] == "no_subjects"), "errors": errors},
           "blockers": blockers[:200], "checks": c.checks}
    if old:
        rep.update(diff_baseline(old, baseline, c))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "lint.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
    return rep


def main(argv):
    ap = L.Parser(prog="lint_blender.py")
    ap.add_argument("--project")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-file")
    ap.add_argument("--baseline")
    for k in ("cameras", "lights", "exposure", "steps", "rules", "walk", "layout", "visible"):
        ap.add_argument("--" + k)
    ap.add_argument("--only")
    ap.add_argument("--skip")
    a = ap.parse_args(argv)
    split = lambda s: [x for x in (s or "").split(",") if x]
    rep = run_lint(a.project, a.out, a.expect_file, split(a.only), split(a.skip), a.baseline,
                   **{k: getattr(a, k) for k in ("cameras", "lights", "exposure", "steps", "rules", "walk", "layout", "visible")})
    s = rep["summary"]
    print(f"LINT blocker={s['blocker']} major={s['major']} minor={s['minor']} errors={s['errors']} skipped={list(s['skipped'])} "
          f"no_subjects={s['no_subjects']} seconds={rep['seconds']} -> {os.path.join(a.out, 'lint.json')}")
    if a.baseline:
        b = rep["baseline"]
        print(f"NEW blocker={b['new']['blocker']} major={b['new']['major']} minor={b['new']['minor']} gone={b['gone']} against {b['file']}"
              + (f" (older baseline, unlisted items read as new: {b['partial']})" if b["partial"] else ""))
        rows = sorted(((it["class"], n, it) for n, items in rep["new"].items() for it in items if it["class"] != "minor"), key=lambda r: (CLASSES.index(r[0]), r[1]))
        for cls, n, it in rows[:30]:
            print(f"  {cls} {n} {it['object']}: {it.get('what', '')}")
        if len(rows) > 30:
            print(f"  ... {len(rows) - 30} more under `new` in lint.json")
    return 1 if s["errors"] else (2 if s["blocker"] else 0)


if any(os.path.basename(x) == "lint_blender.py" for x in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except L.LintError as e:
        print("LINT ERROR:", e)
        code = 1
    except Exception:
        traceback.print_exc()
        code = 1
    sys.exit(code)
