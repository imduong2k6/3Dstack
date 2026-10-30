"""Build fix_cams.json: one camera per review issue, aimed at the issue's objects or location (tested headless with bpy 5.2.3).

    bash bin/blender-bg <before_copy.blend> --python .claude/skills/review-pairs/scripts/fix_cams.py -- \
        --issues <reviews>/fix_issues.json --out <reviews>/fix_cams.json [--cameras light/cameras.json] [--after <new_gate_copy.blend>]

Runs on a copy of the previous round's backup and saves nothing. An issue is one of
  {"id", "caption", "targets": [object names], "boxes": [[[x0,y0,z0],[x1,y1,z1]]], "engine": "WORKBENCH"|"CYCLES", "fill": 0.7,
   "from_camera": "<review camera id>", "loc_m": [..], "aim_m": [..], "lens_mm": 35, "show": [object names], "res_px": [w, h], "source": "review.md item 4"}
  {"id", "kind": "review_cam", "camera": "<review camera id>", "caption", "engine", "before": {"lens_mm", "rot_deg", "clip_m", "note"}}
  {"id", "kind": "plan", "centre_xy": [x, y], "ortho_scale": 20, "cut_z": 1.6, "res_px": [w, h], "caption"}
Without loc_m the camera looks at the targets from the direction of the review camera that sees them best (or the first clear
side), far enough to fit them, then its lens is fitted so the targets fill `fill` of the frame. With --after, a target that only
exists in the new file (a fix that adds something) is read from it, and one that exists in both is framed over both positions, so the
frame still holds the object after the fix moves it. Exit 1 if a target is missing.
"""
import argparse
import json
import math
import sys

import bpy
from mathutils import Vector

SENSOR = 36.0
ENGINES = {"CYCLES": "CYCLES", "WORKBENCH": "BLENDER_WORKBENCH"}


AFTER = {}  # target name -> the same object, linked read-only from the new file


def world_matrix(o):
    """Location, rotation and scale through the parent chain; a saved matrix_world can be stale when a script saved without an update."""
    m = o.matrix_basis.copy()  # shortcut: ignores constraints and bone parents; give loc_m or boxes for such a target
    return world_matrix(o.parent) @ o.matrix_parent_inverse @ m if o.parent else m


def pts_of(t, dg, missing):
    """World bounding-box corners of an object name (here and in the new file) or an explicit [[min], [max]] box."""
    if isinstance(t, str):
        o, pts = bpy.data.objects.get(t), []
        if o is not None:
            try:
                box = o.evaluated_get(dg).bound_box
            except ValueError:
                box = o.bound_box
            pts = [o.matrix_world @ Vector(c) for c in box]
        if t in AFTER:
            pts += [world_matrix(AFTER[t]) @ Vector(c) for c in AFTER[t].bound_box]
        if not pts:
            missing.append(t)
        return pts
    (x0, y0, z0), (x1, y1, z1) = t
    return [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def review_cam(cid, table):
    """A review camera as a dict, from cameras.json or the camera object of the same name."""
    if cid in table:
        c = table[cid]
        rot = c.get("rot_deg") or [math.degrees(v) for v in (Vector(c["aim_m"]) - Vector(c["pos_m"])).to_track_quat("-Z", "Y").to_euler()]
        return {"loc_m": c["pos_m"], "rot_deg": rot, "lens_mm": c.get("lens_mm"), "sensor_fit": c.get("sensor_fit", "AUTO"),
                "shift": list(c.get("shift", [0.0, 0.0])), "res_px": c.get("res_px"),
                "ortho_scale": c.get("ortho_scale") if c.get("type") == "ortho" else None, "clip_m": c.get("clip_m")}
    o = bpy.data.objects.get(cid)
    if o is None or o.type != "CAMERA":
        return None
    r, d = bpy.context.scene.render, o.data
    return {"loc_m": list(o.matrix_world.translation), "rot_deg": [math.degrees(v) for v in o.matrix_world.to_euler()], "lens_mm": d.lens,
            "sensor_fit": d.sensor_fit, "shift": [d.shift_x, d.shift_y], "res_px": [r.resolution_x, r.resolution_y],
            "ortho_scale": d.ortho_scale if d.type == "ORTHO" else None, "clip_m": [d.clip_start, d.clip_end]}


def fit_lens(pts, lo, aim, fill, W, H):
    """Lens (mm) that makes the points fill `fill` of the frame, plus the camera rotation looking at aim."""
    q = (aim - lo).to_track_quat("-Z", "Y")
    rinv = q.to_matrix().inverted()
    tx = ty = 1e-6
    for p in pts:
        v = rinv @ (p - lo)
        if v.z >= 0:
            return None, q  # a target point is behind the camera
        tx, ty = max(tx, abs(v.x / -v.z)), max(ty, abs(v.y / -v.z))
    return round(max(12.0, min(100.0, min(fill * SENSOR / 2 / tx, fill * SENSOR * H / W / 2 / ty))), 1), q


def off_render():
    """Names of collections switched off for render, directly or through a parent."""
    off = set()

    def walk(c, hidden):
        hidden = hidden or c.hide_render
        if hidden:
            off.add(c.name)
        for ch in c.children:
            walk(ch, hidden)
    walk(bpy.context.scene.collection, False)
    return off


def blocked(dg, origin, p, own, off, tol):
    """True when something that renders, and is not a target, stands between origin and p, stopping tol short of p
    (a wall-mounted target's box corners sit inside the wall it hangs on)."""
    d = p - origin
    dirn, left, o = d.normalized(), d.length - tol, origin.copy()
    for _ in range(8):  # rays pass through objects that don't render (guides, masters)
        hit, loc, _, _, obj, _ = bpy.context.scene.ray_cast(dg, o, dirn, distance=left)
        if not hit:
            return False
        ob = obj.original
        if ob.name in own:
            return False
        if not ob.hide_render and not all(c.name in off for c in ob.users_collection):
            return True
        left -= (loc - o).length + 1e-3
        o = loc + dirn * 1e-3
        if left <= 0:
            return False
    return False


def visible_fraction(dg, origin, samples, own, off, tol):
    """Share of the sample points a ray from `origin` reaches without hitting anything that renders and is not a target."""
    return sum(not blocked(dg, origin, p, own, off, tol) for p in samples if (p - origin).length > tol) / len(samples)


def place(dg, pts, own, fill, W, H, from_cam, cams):
    """Pick a camera position: the first direction and distance from which the targets are mostly visible."""
    off = off_render()
    c = sum(pts, Vector()) / len(pts)
    r = max((p - c).length for p in pts) or 0.1
    dist = max(r / (fill * min(18 / 35, 18 * H / W / 35)), r * 1.5 + 0.3)  # a 35 mm lens would fill `fill` from here
    dirs = []
    if from_cam:
        dirs.append((c - Vector(from_cam["loc_m"])).normalized())
    for cam in sorted(cams, key=lambda k: (Vector(k["loc_m"]) - c).length):
        dirs.append((c - Vector(cam["loc_m"])).normalized())
    dirs += [Vector((-math.cos(math.radians(k * 45)), -math.sin(math.radians(k * 45)), z)).normalized() for z in (-0.2, 0.0, -0.45) for k in range(8)]
    samples = [c] + pts
    best = (-1, None)
    for d in dirs:
        for f in (1.0, 0.75, 0.55, 0.4, 0.3):
            pos = c - d * dist * f
            vf = visible_fraction(dg, pos, samples, own, off, 0.12 + 0.1 * r)
            if vf > best[0]:
                best = (vf, pos)
            if vf >= 0.75:
                return pos, vf
    return best[1], best[0]


def build(issue, dg, table, allcams, res, missing):
    cid, eng = issue["id"], ENGINES[issue.get("engine", "WORKBENCH")]
    out = {"id": cid, "engine": eng, "caption": issue.get("caption", ""), "source": issue.get("source", "")}
    if issue.get("kind") == "review_cam":
        c = review_cam(issue["camera"], table)
        if c is None:
            missing.append(issue["camera"])
            return None
        out.update(loc_m=[round(v, 3) for v in c["loc_m"]], rot_deg=[round(v, 3) for v in c["rot_deg"]], lens_mm=c["lens_mm"], sensor_fit=c["sensor_fit"],
                   shift=c["shift"], review_cam=issue["camera"], targets=[])
        out["res_px"] = c["res_px"] or res
        out.update({k: c[k] for k in ("ortho_scale", "clip_m") if c[k]})  # a plan camera renders ortho, cut where the review camera cuts
        if issue.get("before"):
            out["before"] = issue["before"]
        return out
    if issue.get("kind") == "plan":
        zmax = max((o.matrix_world.translation.z + o.dimensions.z for o in bpy.context.scene.objects if o.type == "MESH"), default=10.0)
        z = round(zmax + 2.0, 1)
        cx, cy = issue["centre_xy"]
        out.update(loc_m=[cx, cy, z], rot_deg=[0.0, 0.0, 0.0], lens_mm=50.0, sensor_fit="VERTICAL", shift=[0.0, 0.0], ortho_scale=issue["ortho_scale"],
                   clip_m=[round(z - issue["cut_z"], 2), 1000.0], res_px=issue.get("res_px", res), targets=[])
        return out
    tl = issue.get("targets", [])
    pts = [p for t in tl + issue.get("boxes", []) for p in pts_of(t, dg, missing)]
    if not pts:
        missing.append(cid + ": no targets found")
        return None
    W, H = issue.get("res_px", res)
    fill = issue.get("fill", 0.7)
    aim = Vector(issue["aim_m"]) if issue.get("aim_m") else sum(pts, Vector()) / len(pts)
    vf = None
    if issue.get("loc_m"):
        lo = Vector(issue["loc_m"])
    else:
        fc = review_cam(issue["from_camera"], table) if issue.get("from_camera") else None
        lo, vf = place(dg, pts, set(tl), fill, W, H, fc, allcams)
    lens, q = fit_lens(pts, lo, aim, fill, W, H)
    if lens is None:
        missing.append(cid + ": camera ends up behind a target; give loc_m")
        return None
    if issue.get("lens_mm"):  # a pinned lens (an eye-height view) skips the fit
        lens = issue["lens_mm"]
    e = q.to_euler()
    out.update(loc_m=[round(v, 3) for v in lo], rot_deg=[round(math.degrees(v), 2) for v in e], lens_mm=lens, sensor_fit="HORIZONTAL", shift=[0.0, 0.0],
               targets=[t for t in tl if isinstance(t, str)], res_px=[W, H])
    if issue.get("show"):  # objects in render-hidden collections, drawn for this camera only
        out["show"] = issue["show"]
    if vf is not None:
        out["visible_fraction"] = round(vf, 2)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issues", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cameras", help="light/cameras.json; without it the camera objects in the file are used")
    ap.add_argument("--after", help="the new gate copy: targets it adds or moves are framed there too")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = json.load(open(a.issues))
    res = spec.get("res_px", [960, 720])
    rows = json.load(open(a.cameras)) if a.cameras else []
    table = {c["id"]: c for c in (rows.get("cameras", []) if isinstance(rows, dict) else rows)}
    if a.after:
        names = sorted({t for i in spec["issues"] for t in i.get("targets", [])})
        with bpy.data.libraries.load(a.after, link=True) as (src, dst):
            dst.objects = [n for n in names if n in src.objects]
        AFTER.update({o.name: o for o in dst.objects if o.library})
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    allcams = [c for c in (review_cam(k, table) for k in (table or [o.name for o in bpy.data.objects if o.type == "CAMERA"])) if c]
    missing, out = [], []
    ids = [i["id"] for i in spec["issues"]]
    assert len(ids) == len(set(ids)), "issue ids must be unique"
    for issue in spec["issues"]:
        c = build(issue, dg, table, allcams, res, missing)
        if c:
            out.append(c)
            print("CAM", c["id"], c["lens_mm"], "visible", c.get("visible_fraction", "-"), "fixed" if issue.get("loc_m") else "")
            if c.get("visible_fraction", 1) < 0.5:
                print("  WARN", c["id"], "is mostly hidden from the chosen position; set loc_m")
    for lib in list(bpy.data.libraries):
        bpy.data.libraries.remove(lib)
    json.dump({"res_px": res, "source_before": bpy.data.filepath, "cams": out, "missing": sorted(set(missing))}, open(a.out, "w"), indent=1)
    print("FIX_CAMS", len(out), "of", len(ids), "missing", sorted(set(missing)))
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:  # under --python an exception would exit 0
        import traceback
        traceback.print_exc()
        print("fix_cams error:", repr(e))
        sys.exit(1)
