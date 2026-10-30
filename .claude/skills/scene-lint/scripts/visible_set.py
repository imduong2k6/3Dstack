"""visible_set.json: the objects a player or a review camera can see (tested headless with bpy 5.2.3). Lint, reviewers and fix rounds
check only this set (house rule 9).

    bash bin/blender-bg <copy.blend> --python .claude/skills/scene-lint/scripts/visible_set.py -- \
        --project projects/<slug> [--out plan/visible_set.json] [--cameras light/cameras.json] [--walk plan/walk.json] [--sphere 4000] [--pix 4]

Method: an eye (default 1.6 m) above the floor every 0.5 m along each walk path casts rays over the whole sphere; every review camera
casts one ray per --pix pixels through its real projection (lens shift, sensor fit, clip planes and per-camera resolution included);
a last pass probes each object not hit yet: rays from every eye and camera to up to 64 points on its faces, so thin objects (cables)
are not lost between rays. Limits, also written into the file: it sees the geometry the viewport depsgraph holds, so objects hidden in
the viewport or parked are not in it; glass and alpha are opaque; a sphere ray can miss a thin object that is not probed (the probe
covers it but only through unobstructed lines from an eye point or camera); eye points follow the floor found under the path, so a path
with no floor under it yields no eyes there. Exit 0 ok, 1 on an error.
"""
import json
import math
import os
import sys
import time
import traceback

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lintlib as L  # noqa: E402

MAXD = 80.0


def camera_rays(co, dg, w, h, pix):
    """Origins and directions (world) of one ray per pix pixels through the camera's real projection, from its near plane."""
    pm = np.array(co.calc_matrix_camera(dg, x=w, y=h))
    inv, mw = np.linalg.inv(pm), np.array(co.matrix_world)
    xs, ys = np.meshgrid(np.arange(pix / 2, w, pix) / w * 2 - 1, np.arange(pix / 2, h, pix) / h * 2 - 1)
    n = np.stack([xs.ravel(), ys.ravel(), -np.ones(xs.size), np.ones(xs.size)])
    f = np.stack([xs.ravel(), ys.ravel(), np.ones(xs.size), np.ones(xs.size)])
    near, far = inv @ n, inv @ f
    near, far = (near[:3] / near[3]).T, (far[:3] / far[3]).T
    o, d = near @ mw[:3, :3].T + mw[:3, 3], (far - near) @ mw[:3, :3].T
    return o, d / np.linalg.norm(d, axis=1, keepdims=True)


def depth_in_camera(co, dg, w, h, p, cache={}):
    """Distance in front of the camera plane when the world point p is inside the frame and the clip range, else None."""
    key = (co.name, w, h)
    if key not in cache:
        cache[key] = (np.array(co.calc_matrix_camera(dg, x=w, y=h)), np.linalg.inv(np.array(co.matrix_world)))
    pm, iv = cache[key]
    cam = iv @ np.append(p, 1.0)
    q = pm @ cam
    if q[3] <= 0:
        return None
    ndc = q[:3] / q[3]
    ok = abs(ndc[0]) <= 1 and abs(ndc[1]) <= 1 and co.data.clip_start <= -cam[2] <= co.data.clip_end
    return float(-cam[2]) if ok else None


def sphere_dirs(n):
    ga = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        out.append(Vector((r * math.cos(ga * i), r * math.sin(ga * i), z)))
    return out


def compute(project=None, cameras=None, walk=None, layout=None, rules_path=None, sphere=4000, pix=4, spacing=0.5):
    t0 = time.time()
    d = lambda *p: os.path.join(project, *p) if project else None
    cameras = cameras or d("light", "cameras.json")
    walk = walk or d("plan", "walk.json")
    layout = layout or d("plan", "layout.json")
    rules = L.load_rules(rules_path or (d("plan", "lint_rules.yaml") if project and os.path.exists(d("plan", "lint_rules.yaml")) else None))
    sc, dg = bpy.context.scene, bpy.context.evaluated_depsgraph_get()
    geo = L.Geo(sc, rules, dg)
    if not geo.solids:
        raise L.LintError("no rendered geometry in the file")
    tree = geo.tree
    names = geo.names

    # eye points along the walk paths
    paths, _ = L.read_paths(walk, layout)
    eyes = []
    for pname, pts in (paths or {}).items():
        smp = [s for s in L.walk_samples(geo, pts, 0.1) if s[4] is not None]
        every = max(1, int(round(spacing / 0.1)))
        for s in smp[::every] + smp[-1:]:
            e = Vector((s[0], s[1], s[4] + rules["eye_height_m"]))
            if all((e - q).length > 0.25 for _, q in eyes):
                eyes.append((pname, e))

    # review cameras
    cams = []
    if cameras and os.path.exists(cameras):
        data = L.load_json(cameras)
        for row in (data.get("cameras", data) if isinstance(data, dict) else data):
            co = bpy.data.objects.get(row["id"])
            if co is not None and co.type == "CAMERA":
                w, h = row.get("res_px") or (sc.render.resolution_x, sc.render.resolution_y)
                cams.append((row["id"], co, int(w), int(h)))
    if not eyes and not cams:
        raise L.LintError("nothing to see from: no walk path with a floor under it and no camera from cameras.json in the file")

    seen = {}

    def mark(i, src):
        s = seen.setdefault(names[tree_owner[i]], {"eye_rays": 0, "cams": set()})
        if src is None:
            s["eye_rays"] += 1
        else:
            s["cams"].add(src)
    tree_owner = geo.owner

    for _, e in eyes:
        for dv in sphere_dirs(sphere):
            h = tree.ray_cast(e, dv, MAXD)
            if h[2] is not None:
                mark(h[2], None)
    cam_info, cam_rays = {}, {}
    for cid, co, w, h in cams:
        o, dr = camera_rays(co, dg, w, h, pix)
        cam_info[cid] = (co, w, h)
        reach = (co.data.clip_end - co.data.clip_start) if co.data.type == "ORTHO" else co.data.clip_end
        n = 0
        for oi, di in zip(o.tolist(), dr.tolist()):
            hit = tree.ray_cast(Vector(oi), Vector(di), min(reach, MAXD * 4))
            if hit[2] is not None:
                mark(hit[2], cid)
                n += 1
        cam_rays[cid] = {"res_px": [w, h], "rays": len(o), "hits": n}

    # probe pass: objects not hit yet, through unobstructed lines from an eye point or a camera
    probed = 0
    for name, s in geo.solids.items():
        if name in seen or not len(s.tris):
            continue
        probed += 1
        tri = s.verts[s.tris]
        nm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nm /= np.maximum(np.linalg.norm(nm, axis=1, keepdims=True), 1e-12)
        pick = np.arange(0, len(tri), max(1, len(tri) // 64))
        hit = None
        for p in tri[pick].mean(1) + nm[pick] * 0.003:
            pv = Vector(p)
            for _, e in eyes:
                dv = pv - e
                ln = dv.length
                if ln <= MAXD:
                    h = tree.ray_cast(e, dv / ln, ln + 0.002)
                    if h[2] is None or names[tree_owner[h[2]]] == name or h[3] >= ln - 0.004:
                        seen.setdefault(name, {"eye_rays": 0, "cams": set(), "probe": True})["eye_rays"] += 1
                        hit = "eye"
                        break
            if hit:
                break
            for cid, (co, w, h) in cam_info.items():
                depth = depth_in_camera(co, dg, w, h, p)
                if depth is None:
                    continue
                if co.data.type == "ORTHO":  # the ray runs along the view axis
                    fwd = co.matrix_world.to_3x3() @ Vector((0, 0, -1))
                    o, ln, dv = pv - fwd * depth, depth, fwd
                else:
                    o = co.matrix_world.translation
                    ln = (pv - o).length
                    dv = (pv - o) / ln
                r = tree.ray_cast(o, dv, ln + 0.002)
                if r[2] is None or names[tree_owner[r[2]]] == name or r[3] >= ln - 0.004:
                    seen.setdefault(name, {"eye_rays": 0, "cams": set(), "probe": True})["cams"].add(cid)
                    hit = cid
                    break
            if hit:
                break

    state = L.scene_state()
    visible = {n: {"eye_rays": v["eye_rays"], "cams": sorted(v["cams"]), **({"probe": True} if v.get("probe") else {})} for n, v in sorted(seen.items())}
    return {"tool": "visible_set", "version": 1, "file": bpy.data.filepath, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scene": {k: state[k] for k in ("objects", "name_hash")},
            "method": f"eye {rules['eye_height_m']} m above the floor every {spacing} m on {list(paths or {})}; {sphere} sphere rays per eye; "
                      f"cameras one ray per {pix} px through the real projection; probe of up to 64 face points per unseen object",
            "limits": ["objects hidden in the viewport or parked are not tested", "glass and alpha count as opaque",
                       "a thin object is found by the probe only through an unobstructed line from an eye point or a camera",
                       "no eye points where no floor is found under a path"],
            "params": {"sphere": sphere, "pix": pix, "spacing_m": spacing, "eye_height_m": rules["eye_height_m"]},
            "eye_points": len(eyes), "eyes": [[p, [round(x, 3) for x in e]] for p, e in eyes][:2000], "cameras": cam_rays,
            "tested": sorted(names), "visible": visible, "hidden": sorted(n for n in names if n not in visible),
            "counts": {"tested": len(names), "visible": len(visible), "hidden": len(names) - len(visible), "probed": probed,
                       "eye_only": sum(1 for v in visible.values() if v["eye_rays"] and not v["cams"]),
                       "camera_only": sum(1 for v in visible.values() if not v["eye_rays"] and v["cams"])},
            "seconds": round(time.time() - t0, 1)}


def main(argv):
    ap = L.Parser(prog="visible_set.py")
    ap.add_argument("--project")
    ap.add_argument("--out")
    for k in ("cameras", "walk", "layout", "rules"):
        ap.add_argument("--" + k)
    ap.add_argument("--sphere", type=int, default=4000)
    ap.add_argument("--pix", type=int, default=4)
    ap.add_argument("--spacing", type=float, default=0.5)
    a = ap.parse_args(argv)
    out = a.out or (os.path.join(a.project, "plan", "visible_set.json") if a.project else None)
    if not out:
        raise L.LintError("give --out or --project")
    res = compute(a.project, a.cameras, a.walk, a.layout, a.rules, a.sphere, a.pix, a.spacing)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, "w"), indent=1)
    print(f"VISIBLE_SET {res['counts']} eyes={res['eye_points']} seconds={res['seconds']} -> {out}")
    return 0


if any(os.path.basename(x) == "visible_set.py" for x in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except L.LintError as e:
        print("VISIBLE_SET ERROR:", e)
        code = 1
    except Exception:
        traceback.print_exc()
        code = 1
    sys.exit(code)
