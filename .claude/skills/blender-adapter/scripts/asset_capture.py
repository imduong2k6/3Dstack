"""Capture one asset for review, next to a 1.8 m mannequin and against a photo. Headless, in memory only: the .blend is never saved
(tested headless with bpy 5.2.3 using Workbench and Cycles).

    bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/asset_capture.py -- --object SM_Name --out <dir>
        [--modes solid,matcap,reflect,culling,wire] [--res 800] [--samples 32] [--close name:x,y,z[:distance_m]]...
        [--photo img --photo-kind rectified|ortho --photo-box x0 y0 x1 y1 [--feature name:x0,y0,x1,y1]...] [--photo-mask img]

Exit 0 done, 1 any failure (Blender itself exits 0 when a script raises). Writes <out>/<mode>/<view>.png and <out>/capture_report.json.

Only --object (comma-separated, with all its children) is rendered; every other object and light in the file is switched off for the
render, and a neutral world, light rig and cameras are added. The front looks along +Y (the front faces -Y), orthographic; so do back,
left, right, top and bottom; the two three-quarters are perspective. Close-ups are points in world metres; the camera looks from front,
left and above at `distance` (default half the longest extent).

Modes: solid (Workbench, material colours: a Principled base colour that is not textured is used), matcap (shiny neutral grey matcap, pearl: smears and
edge highlights), reflect (opt-in, the stripe matcap check_reflection_horizontal: a kink, ridge or ripple on a curved face bends the stripes where
matcap shows nothing; the stripes follow the view, so compare two meshes only from the same camera), culling (Workbench with back-face culling on a magenta ground: holes and inside-out faces show through), wire (the edges of
the final mesh, modifiers applied, about one pixel wide over a plain grey surface; edges behind the surface stay hidden), cycles (opt-in,
slow, fixed exposure). Default solid,matcap,culling,wire.

Photo: the overlay is an orthographic front render, so it only means something against a flat image. --photo-kind says which: `rectified`
(modeling/scripts/blueprint.py rectify) or `ortho` (a sheet). A perspective photo is refused: matching it copies the camera into the mesh.
--photo-box is the object's box in photo pixels (x right, y down). The front render is scaled so its height equals the box height and
centred on the box, then written as compare_front_render.png (photo-sized, transparent) with compare_side.png (photo | render),
compare_blend.png (50 %) and compare_edge.png (red render outline, yellow photo box, green photo feature boxes, cyan render feature boxes).
The report holds width/height in both, and for each --feature (photo pixels) the size and position error against the same box projected
from the part named like it: an object of that name, else the faces of a material of that name (not measured when neither exists).
--photo-mask (white = object, or its alpha) gives the silhouette IoU against the render's alpha; without --photo-box the mask's own box is used.
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

MODES = ("cycles", "solid", "matcap", "reflect", "culling", "wire")
GEOM = {"MESH", "CURVE", "SURFACE", "FONT", "META"}
# camera looks along d, image up is u
AXES = {"front": ((0, 1, 0), (0, 0, 1)), "back": ((0, -1, 0), (0, 0, 1)), "left": ((1, 0, 0), (0, 0, 1)),
        "right": ((-1, 0, 0), (0, 0, 1)), "top": ((0, 0, -1), (0, 1, 0)), "bottom": ((0, 0, 1), (0, -1, 0))}
VIEWS = list(AXES) + ["three_quarter_l", "three_quarter_r", "scale"]
NM = "not measured"


# ---- images (raw file values: Non-Color, straight alpha; arrays are float32 H x W x 4, top row first) ----
def load(path):
    im = bpy.data.images.load(os.path.abspath(path))
    im.colorspace_settings.name, im.alpha_mode = "Non-Color", "STRAIGHT"
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()


def save(path, a):
    h, w = a.shape[:2]
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones((h, w, 1), np.float32)], 2)
    im = bpy.data.images.new("ac_out", w, h, alpha=True)
    im.colorspace_settings.name, im.alpha_mode = "Non-Color", "STRAIGHT"
    im.pixels.foreach_set(np.ascontiguousarray(a[::-1], np.float32).ravel())
    im.filepath_raw, im.file_format = os.path.abspath(path), "PNG"
    im.save()
    bpy.data.images.remove(im)


def grow(a):
    g = a.copy()
    g[1:] |= a[:-1]; g[:-1] |= a[1:]; g[:, 1:] |= a[:, :-1]; g[:, :-1] |= a[:, 1:]
    return g


def draw(img, box, col, t=2):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    for k in range(t):
        for ya, yb, xa, xb in ((y0 + k, y0 + k + 1, x0, x1 + 1), (y1 - k, y1 - k + 1, x0, x1 + 1),
                               (y0, y1 + 1, x0 + k, x0 + k + 1), (y0, y1 + 1, x1 - k, x1 - k + 1)):
            img[max(ya, 0):max(yb, 0), max(xa, 0):max(xb, 0)] = col


# ---- geometry (world space, evaluated, so modifiers count) ----
def part_verts(o, dg, mats=None):
    """World vertices of o; with mats (material names), only the corners of the triangles that use one of them."""
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    try:
        if me is None or not len(me.vertices):
            return np.zeros((0, 3))
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if mats is not None:
            me.calc_loop_triangles()
            tv = np.empty(len(me.loop_triangles) * 3, np.int32)
            tm = np.empty(len(me.loop_triangles), np.int32)
            me.loop_triangles.foreach_get("vertices", tv)
            me.loop_triangles.foreach_get("material_index", tm)
            names = [s.material.name if s.material else "" for s in o.material_slots]
            co = co[np.unique(tv.reshape(-1, 3)[np.isin(tm, [i for i, n in enumerate(names) if n in mats])])]
    finally:
        oe.to_mesh_clear()
    M = np.array(o.matrix_world)
    return (co @ M[:3, :3].T + M[:3, 3]).astype(np.float64)


def frame(w, h, res):
    """Ortho scale and pixel size for a w x h metre area with a margin, at most 2:1, long edge res."""
    w, h = w * 1.12, h * 1.12
    w, h = max(w, h / 2), max(h, w / 2)
    k = res / max(w, h)
    return max(w, h), max(int(w * k), 64), max(int(h * k), 64)


def parse_box(s):
    n = [float(v) for v in s.split(",")]
    if len(n) != 4 or n[2] <= n[0] or n[3] <= n[1]:
        raise RuntimeError(f"bad box {s!r}: want x0,y0,x1,y1 with x1>x0 and y1>y0")
    return n


def run(a):
    scene = bpy.context.scene
    r, sh = scene.render, scene.display.shading
    modes = [m for m in a.modes.split(",") if m]
    bad = [m for m in modes if m not in MODES]
    if bad or not modes:
        raise RuntimeError(f"bad --modes {a.modes!r}: choose from {', '.join(MODES)}")
    if (a.photo or a.photo_mask) and not a.photo_kind:
        raise RuntimeError("--photo needs --photo-kind rectified|ortho: rectify a perspective photo first (modeling/scripts/blueprint.py rectify)")
    roots = []
    for n in a.object.split(","):
        o = bpy.data.objects.get(n)
        if o is None:
            raise RuntimeError(f"missing object {n!r}: nothing rendered")
        if n not in bpy.context.view_layer.objects:
            raise RuntimeError(f"object {n!r} is not in the view layer (parked collection?): nothing rendered")
        roots.append(o)
    tree = set(roots) | {k for o in roots for k in o.children_recursive}
    geo = sorted((o for o in tree if o.type in GEOM and not o.hide_render and o.name in bpy.context.view_layer.objects), key=lambda o: o.name)
    for o in scene.objects:
        if o not in tree:
            o.hide_render = True
    for o in tree:  # Workbench shows the viewport colour, so take it from the Principled base colour when that is a plain colour
        for s in o.material_slots:
            nd = next((n for n in s.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if s.material and s.material.node_tree else None
            if nd and not nd.inputs["Base Color"].links:
                s.material.diffuse_color = (*nd.inputs["Base Color"].default_value[:3], s.material.diffuse_color[3])
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    allv = np.vstack([part_verts(o, dg) for o in geo]) if geo else np.zeros((0, 3))
    if not len(allv):
        raise RuntimeError(f"{a.object!r} has no renderable geometry: nothing rendered")
    lo, hi = allv.min(0), allv.max(0)
    ext, c = hi - lo, Vector((lo + hi) / 2)
    R = max(float(np.linalg.norm(ext)) / 2, 1e-3)
    rep["extents_m"], rep["bbox_min"], rep["bbox_max"] = [round(float(v), 5) for v in ext], [round(float(v), 5) for v in lo], [round(float(v), 5) for v in hi]

    # fixed look: same settings every run, so captures compare
    vs = scene.view_settings
    vs.view_transform, vs.look, vs.exposure, vs.gamma, vs.use_white_balance = "Standard", "None", 0.0, 1.0, False
    r.resolution_percentage, r.use_compositing, r.film_transparent = 100, False, False
    r.image_settings.media_type, r.image_settings.file_format = "IMAGE", "PNG"
    r.image_settings.color_mode, r.image_settings.color_depth, r.image_settings.color_management = "RGBA", "8", "FOLLOW_SCENE"
    scene.display.render_aa = "16"
    scene.cycles.samples, scene.cycles.use_denoising = a.samples, True
    world = bpy.data.worlds.new("ac_world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value, bg.inputs[1].default_value = (0.22, 0.22, 0.22, 1), 1.0
    scene.world = world
    try:
        p = bpy.context.preferences.addons["cycles"].preferences
        for t in ("OPTIX", "CUDA"):
            try:
                p.compute_device_type = t
                p.get_devices()
                if any(d.type == t for d in p.devices):
                    for d in p.devices:
                        d.use = d.type == t
                    scene.cycles.device = "GPU"
                    break
            except TypeError:
                pass
    except Exception as e:
        print("cycles on CPU:", e)

    def add_cam(name, loc, d, u, ortho=None, lens=50):
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        scene.collection.objects.link(cam)
        d, u = Vector(d).normalized(), Vector(u).normalized()
        cam.location = loc
        cam.rotation_euler = Matrix((d.cross(u).normalized(), u, -d)).transposed().to_euler()
        cd.clip_start, cd.clip_end = R * 0.01, R * 60 + 10
        if ortho:
            cd.type, cd.ortho_scale = "ORTHO", ortho
        else:
            cd.lens = lens
        return cam

    # neutral rig (Cycles only; Workbench ignores lights), power scaled with distance squared so exposure is the same at any size
    for nm, dirn, w_m, size in (("key", (-0.6, -0.8, 0.7), 4, 0.7), ("fill", (0.8, -0.6, 0.1), 1.5, 1.0), ("rim", (0.2, 0.9, 0.6), 2, 0.5)):
        dv = Vector(dirn).normalized() * R * 4
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy, ld.size = w_m * dv.length ** 2, size * dv.length
        lo_ = bpy.data.objects.new(nm, ld)
        scene.collection.objects.link(lo_)
        lo_.location = c + dv
        lo_.rotation_euler = (-dv).to_track_quat("-Z", "Y").to_euler()

    # 1.8 m mannequin from primitives, feet on the object's lowest point, to the right of it; shown for the scale shot only
    mat = bpy.data.materials.new("ac_mannequin")
    mat.diffuse_color = (0.9, 0.45, 0.15, 1)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = mat.diffuse_color
    mx, mq = hi[0] + 0.5, []
    for kind, rad, depth, x, z in (("c", 0.075, 0.85, -0.09, 0.425), ("c", 0.075, 0.85, 0.09, 0.425), ("c", 0.17, 0.6, 0, 1.15),
                                   ("c", 0.045, 0.62, -0.22, 1.12), ("c", 0.045, 0.62, 0.22, 1.12), ("c", 0.05, 0.2, 0, 1.5), ("s", 0.1, 0, 0, 1.7)):
        loc = (mx + x, c.y, lo[2] + z)
        if kind == "c":
            bpy.ops.mesh.primitive_cylinder_add(radius=rad, depth=depth, location=loc)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, location=loc)
        mq.append(bpy.context.active_object)
        mq[-1].data.materials.append(mat)
        mq[-1].hide_render = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    rep["mannequin_height_m"] = round(float(np.ptp(np.vstack([part_verts(o, dg) for o in mq])[:, 2])), 4)

    # shots: (name, camera, width_px, height_px)
    shots = []
    for nm, (d, u) in AXES.items():
        d, u = Vector(d), Vector(u)
        rv = d.cross(u)
        s_, w, h = frame(sum(abs(rv[i]) * ext[i] for i in range(3)), sum(abs(u[i]) * ext[i] for i in range(3)), a.res)
        shots.append((nm, add_cam(nm, c - d * 3 * R, d, u, ortho=s_), w, h))
    for nm, az in (("three_quarter_l", -40), ("three_quarter_r", 40)):  # tight fit of the vertices at 50 mm
        d = -Vector((math.sin(math.radians(az)) * math.cos(0.35), -math.cos(math.radians(az)) * math.cos(0.35), math.sin(0.35)))
        rv = d.cross(Vector((0, 0, 1))).normalized()
        uv_ = rv.cross(d)
        rel = allv - np.array(c)
        D = 1.06 * float(np.max(np.maximum(abs(rel @ np.array(rv)), abs(rel @ np.array(uv_))) / (18 / 50) - rel @ np.array(d)))
        shots.append((nm, add_cam(nm, c - d * D, d, (0, 0, 1), lens=50), a.res, a.res))
        shots[-1][1]["ac_dist"] = D
    wm = mx + 0.27 - lo[0]
    hm = max(ext[2], 1.8)
    s_, w, h = frame(wm, hm, a.res)
    shots.append(("scale", add_cam("scale", Vector((lo[0] + wm / 2, c.y - 3 * R - 4, lo[2] + hm / 2)), (0, 1, 0), (0, 0, 1), ortho=s_), w, h))
    for spec in a.close:
        parts = spec.split(":")
        try:
            t = Vector([float(v) for v in parts[1].split(",")])
            dist = float(parts[2]) if len(parts) > 2 else max(ext) / 2
            assert len(t) == 3 and dist > 0 and 2 <= len(parts) <= 3 and parts[0]
        except Exception:
            raise RuntimeError(f"bad --close {spec!r}: want name:x,y,z[:distance_m]")
        if parts[0] in VIEWS:
            raise RuntimeError(f"--close name {parts[0]!r} is a view name")
        d = -Vector((-0.35, -1, 0.3)).normalized()
        shots.append((parts[0], add_cam(parts[0], t - d * dist, d, (0, 0, 1), lens=85), a.res, a.res))
        shots[-1][1]["ac_dist"] = dist

    def pixel_m(cam, w, h):
        """How many metres one pixel covers at the object, so wire lines stay the same width in every view."""
        if cam.data.type == "ORTHO":
            return cam.data.ortho_scale / max(w, h)
        return cam["ac_dist"] * 36 / cam.data.lens / max(w, h)

    def render(path, cam, w, h):
        scene.camera, (r.resolution_x, r.resolution_y), r.filepath = cam, (w, h), os.path.abspath(path)
        bpy.ops.render.render(write_still=True)
        if not os.path.exists(path):
            raise RuntimeError(f"render wrote no file: {path}")

    for mode in modes:
        r.engine = "CYCLES" if mode == "cycles" else "BLENDER_WORKBENCH"
        world.color = (1.0, 0.0, 1.0) if mode == "culling" else (0.22, 0.22, 0.22)
        sh.show_backface_culling, sh.show_cavity, sh.show_shadows, sh.show_object_outline = mode == "culling", False, False, False
        sh.light, sh.color_type, sh.show_specular_highlight = "STUDIO", "MATERIAL", True
        if mode in ("matcap", "reflect"):
            sh.light, sh.color_type, sh.single_color = "MATCAP", "SINGLE", (0.6, 0.6, 0.6)
            ml = [s.name for s in bpy.context.preferences.studio_lights if s.type == "MATCAP"]
            want = "pearl.exr" if mode == "matcap" else "check_reflection_horizontal.exr"
            sh.studio_light = want if want in ml else ml[0]
        wires = []
        if mode == "wire":     # Workbench draws no overlays, so the edges are real thin geometry on temporary copies of the final mesh
            sh.color_type = "OBJECT"
            for o in geo:
                o.color = (0.7, 0.7, 0.7, 1)
                w_ob = bpy.data.objects.new("ac_wire_" + o.name, bpy.data.meshes.new_from_object(o.evaluated_get(dg)))
                w_ob.matrix_world, w_ob.color = o.matrix_world, (0.01, 0.01, 0.01, 1)
                scene.collection.objects.link(w_ob)
                m_ = w_ob.modifiers.new("ac_wire", "WIREFRAME")
                m_.use_replace, m_.use_boundary, m_.use_even_offset = True, True, False
                wires.append((w_ob, m_))
        os.makedirs(os.path.join(a.out, mode), exist_ok=True)
        for nm, cam, w, h in shots:
            for o in mq:
                o.hide_render = nm != "scale"
            for w_ob, m_ in wires:
                m_.thickness = 1.3 * pixel_m(cam, w, h) / max(max(w_ob.matrix_world.to_scale()), 1e-6)
            render(os.path.join(a.out, mode, nm + ".png"), cam, w, h)
            rep["files"].setdefault(mode, []).append(os.path.join(a.out, mode, nm + ".png"))
        for w_ob, _ in wires:
            bpy.data.objects.remove(w_ob)
    for o in mq:
        o.hide_render = True

    # ---- photo comparison ----
    photo = load(a.photo) if a.photo else None
    mask = None
    if a.photo_mask:
        m = load(a.photo_mask)
        mask = m[..., 3] > 0.5 if m[..., 3].min() < 0.99 else m[..., :3].mean(-1) > 0.5
    if photo is None and mask is None:
        return
    H, W = (photo if photo is not None else m).shape[:2]
    if a.photo_box:
        box = parse_box(",".join(str(v) for v in a.photo_box))
        src = "given"
    elif mask is not None and mask.any():
        ys, xs = np.nonzero(mask)
        box, src = [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)], "from the mask's own box"
    else:
        raise RuntimeError("--photo needs --photo-box x0 y0 x1 y1 (the object's box in photo pixels)")
    bw, bh = box[2] - box[0], box[3] - box[1]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    s = bh / ext[2]  # photo px per metre
    cam = add_cam("photo_front", Vector((c.x - (cx - W / 2) / s, c.y - 3 * R, c.z + (cy - H / 2) / s)), (0, 1, 0), (0, 0, 1), ortho=max(W, H) / s)
    r.engine, r.film_transparent = "BLENDER_WORKBENCH", True
    sh.light, sh.color_type, sh.show_backface_culling = "STUDIO", "MATERIAL", False
    render(os.path.join(a.out, "compare_front_render.png"), cam, W, H)
    r.film_transparent = False
    rend = load(os.path.join(a.out, "compare_front_render.png"))
    al = rend[..., 3] > 0.5
    proj = lambda v: [float(x) for x in (cx + (v[:, 0].min() - c.x) * s, cy - (v[:, 2].max() - c.z) * s, cx + (v[:, 0].max() - c.x) * s, cy - (v[:, 2].min() - c.z) * s)]
    ph = {"file": a.photo, "mask": a.photo_mask, "kind": a.photo_kind, "size": [W, H], "box": [round(v, 2) for v in box], "box_source": src, "px_per_m": round(s, 3),
          "photo_w_over_h": round(bw / bh, 4), "render_w_over_h": round(float(ext[0] / ext[2]), 4)}
    ph["w_over_h_error_pct"] = round((ph["render_w_over_h"] / ph["photo_w_over_h"] - 1) * 100, 2)
    feats, fb = [], []
    for f in a.feature:
        name, _, nums = f.rpartition(":")
        pb = parse_box(nums)
        low = name.lower()
        objs = [o for o in geo if low == o.name.lower()] or [o for o in geo if low in o.name.lower()]
        if objs:
            v, what = np.vstack([part_verts(o, dg) for o in objs]), "object " + ", ".join(o.name for o in objs)
        else:
            ms = {s_.material.name for o in geo for s_ in o.material_slots if s_.material and low in s_.material.name.lower()}
            ms = {n for n in ms if n.lower() == low} or ms
            v = np.vstack([part_verts(o, dg, ms) for o in geo]) if ms else np.zeros((0, 3))
            what = "material " + ", ".join(sorted(ms))
        if not len(v):
            feats.append({"name": name, "photo_box": pb, "result": f"{NM}: no object or material named like {name!r}"})
            continue
        rb = proj(v)
        pw, phh, rw, rh = pb[2] - pb[0], pb[3] - pb[1], rb[2] - rb[0], rb[3] - rb[1]
        dx, dy = (rb[0] + rb[2]) / 2 - (pb[0] + pb[2]) / 2, (rb[1] + rb[3]) / 2 - (pb[1] + pb[3]) / 2
        feats.append({"name": name, "part": what, "photo_box": pb, "render_box": [round(x, 2) for x in rb],
                      "width_error_pct": round((rw / pw - 1) * 100, 2), "height_error_pct": round((rh / phh - 1) * 100, 2),
                      "centre_dx_px": round(dx, 2), "centre_dy_px": round(dy, 2), "centre_error_pct_of_box_height": round(math.hypot(dx, dy) / bh * 100, 2),
                      "largest_edge_error_px": round(max(abs(x - y) for x, y in zip(rb, pb)), 2)})
        fb.append((pb, rb))
    ph["features"] = feats
    if mask is None:
        ph["iou"] = f"{NM}: no --photo-mask"
    elif mask.shape != al.shape:
        ph["iou"] = f"{NM}: mask is {mask.shape[1]}x{mask.shape[0]}, photo is {W}x{H}"
    else:
        ph["iou"] = round(float((mask & al).sum() / max((mask | al).sum(), 1)), 4)
    rep["photo"] = ph
    if photo is not None:
        rgb, al3 = rend[..., :3], rend[..., 3:4]
        ground = np.array([200, 190, 175], np.float32) / 255
        over = rgb * al3 + ground * (1 - al3)
        save(os.path.join(a.out, "compare_side.png"), np.concatenate([photo[..., :3], np.ones((H, 10, 3), np.float32), over], 1))
        save(os.path.join(a.out, "compare_blend.png"), (photo[..., :3] + over) / 2)
        edge = photo[..., :3].copy()
        edge[grow(grow(al)) ^ al] = (1, 0, 0)
        draw(edge, box, (1, 1, 0))
        for pb, rb in fb:
            draw(edge, pb, (0, 1, 0))
            draw(edge, rb, (0, 1, 1))
        save(os.path.join(a.out, "compare_edge.png"), edge)
    print("photo box", ph["box"], f"({src})", "px/m", ph["px_per_m"])
    print("width/height photo", ph["photo_w_over_h"], "render", ph["render_w_over_h"], "error %", ph["w_over_h_error_pct"])
    for f in feats:
        print("feature", f)
    print("silhouette IoU", ph["iou"])


rep = {"ok": False, "files": {}}


def _main(argv):
    ap = argparse.ArgumentParser(prog="asset_capture.py")
    ap.error = lambda m: (_ for _ in ()).throw(RuntimeError(m))
    ap.add_argument("--object", required=True, help="object name(s), comma-separated; children are included")
    ap.add_argument("--out", required=True)
    ap.add_argument("--modes", default="solid,matcap,culling,wire")
    ap.add_argument("--res", type=int, default=800, help="long edge in pixels")
    ap.add_argument("--samples", type=int, default=32, help="Cycles samples")
    ap.add_argument("--close", action="append", default=[], help="name:x,y,z[:distance_m]")
    ap.add_argument("--photo")
    ap.add_argument("--photo-kind", choices=("rectified", "ortho"), help="the photo or mask is flat: rectified or an orthographic sheet")
    ap.add_argument("--photo-box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--feature", action="append", default=[], help="name:x0,y0,x1,y1 in photo pixels")
    ap.add_argument("--photo-mask")
    a = ap.parse_args(argv)
    a.out = os.path.abspath(a.out)
    os.makedirs(a.out, exist_ok=True)
    rep.update({"blend": bpy.data.filepath, "object": a.object, "modes": a.modes})
    try:
        run(a)
        rep["ok"] = True
    except BaseException as e:
        rep["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        with open(os.path.join(a.out, "capture_report.json"), "w") as f:
            json.dump(rep, f, indent=1)


if any(os.path.basename(x) == "asset_capture.py" for x in sys.argv) and "--" in sys.argv:
    try:
        _main(sys.argv[sys.argv.index("--") + 1:])
        _code = 0
    except Exception:
        import traceback
        traceback.print_exc()
        _code = 1
    sys.exit(_code)
