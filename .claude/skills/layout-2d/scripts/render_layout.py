"""Render plan/layout.json as a floor plan PNG: metre grid with axes, zones in the legend colours with IDs and
Z heights, numbered red callouts, a key, a scale bar and handwritten notes.

    bash bin/blender-bg --python .claude/skills/layout-2d/scripts/render_layout.py -- <layout.json> <layout.png>

Shapes: {"id", "legend", "poly_m": [[x, y], ...]} or {"id", "legend", "point_m": [x, y]}; "outline": true draws
the edge only (for services over a floor); "label_at": [x, y] moves a crowded label; "z_m": floor height, or
[bottom, top], printed under the ID. Cameras: {"id", "pos_m", "aim_m", "lens_mm", "sensor_mm"} as a view wedge.
Callouts: {"n", "at_m": [x, y], "text"} drawn as red numbers, their text listed in the notes box.
Notes: {"at_m": [x, y], "text"} in a handwritten font (LAYOUT_HAND_FONT, else Ink Free on Windows).
Top level: "title", "grid_m". Later shapes draw on top.
"""
import json
import math
import os
import sys

import bpy

LEGEND = {"white": (0.95, 0.95, 0.95), "red": (0.85, 0.15, 0.12), "grey": (0.5, 0.5, 0.5), "yellow": (0.98, 0.85, 0.1),
          "orange": (0.98, 0.55, 0.1), "purple": (0.6, 0.3, 0.85), "green": (0.2, 0.7, 0.25), "blue": (0.2, 0.45, 0.95),
          "cyan": (0.1, 0.85, 0.9), "black": (0.02, 0.02, 0.02)}
KEY = {"white": "Architecture", "red": "Animated or interactive", "grey": "Terrain and ground", "yellow": "Hero or focal",
       "orange": "Dressing cluster", "purple": "Procedural: cables, pipes", "green": "Foliage", "blue": "Water and glass",
       "cyan": "Light source", "black": "Blocked or collision"}
INK, PAPER, GRID, CALLOUT = (0.12, 0.12, 0.14), (0.86, 0.86, 0.84), (0.74, 0.74, 0.72), (0.85, 0.1, 0.08)
FONTS = {}


def font(hand):
    if hand not in FONTS:
        path = os.environ.get("LAYOUT_HAND_FONT", r"C:\Windows\Fonts\Inkfree.ttf") if hand else None
        FONTS[hand] = bpy.data.fonts.load(path) if path and os.path.exists(path) else None
    return FONTS[hand]


def add(name, verts, faces, color, z, outline=False, edge=0.01):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x, y in verts], [], faces)
    ob = bpy.data.objects.new(name, me)
    ob.color = (*color, 1)
    bpy.context.scene.collection.objects.link(ob)
    if outline:
        ob.modifiers.new("edge", "WIREFRAME").thickness = edge
    elif len(verts) > 2:  # dark edge so neighbouring shapes of one colour stay apart
        add(name + "_edge", verts, faces, INK, z + 0.005, outline=True, edge=edge * 0.6)
    return ob


def rect(name, x0, y0, x1, y1, color, z, edge=0):
    return add(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [[0, 1, 2, 3]], color, z, edge=edge)


def circle(name, x, y, r, color, z, n=16):
    return add(name, [(x + r * math.cos(a / n * math.tau), y + r * math.sin(a / n * math.tau)) for a in range(n)],
               [list(range(n))], color, z, edge=r * 0.15)


def label(text, x, y, z, size, color=INK, align="CENTER", hand=False):
    cu = bpy.data.curves.new("T", "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y = text, size, align, "CENTER"
    if font(hand):
        cu.font = font(hand)
    ob = bpy.data.objects.new("T_" + text[:20], cu)
    ob.location, ob.color = (x, y, z), (*color, 1)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def tint(c, k=0.35):  # floor-plan fills: the legend colour lifted toward white
    return tuple(v + (1 - v) * k for v in c)


def zone_text(s):
    z = s.get("z_m")
    if z is None:
        return s.get("label", s["id"])
    z = f"Z {z[0]:+.2f} to {z[1]:+.2f}" if isinstance(z, list) else f"Z {z:+.2f}"
    return f"{s.get('label', s['id'])}\n{z}"


def main(src, out):
    lay = json.load(open(src, encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pts = [v for s in lay.get("shapes", []) for v in s.get("poly_m", [s.get("point_m")]) if v]
    pts += [c["pos_m"][:2] for c in lay.get("cameras", [])] + lay.get("path", [])
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    u = max(x1 - x0, y1 - y0) / 40  # one text unit, so labels scale with the map
    used = []
    for i, s in enumerate(lay.get("shapes", [])):
        z, col = 0.01 * (i + 1), LEGEND[s["legend"]]
        used += [s["legend"]] if s["legend"] not in used else []
        if "poly_m" in s:
            p = s["poly_m"]
            add(s["id"], p, [list(range(len(p)))], col if s.get("outline") else tint(col), z, s.get("outline", False), u * 0.12)
            cx, cy = sum(v[0] for v in p) / len(p), sum(v[1] for v in p) / len(p)
        else:
            cx, cy = s["point_m"]
            circle(s["id"], cx, cy, u * 0.5, col, z)
            cy -= u * 1.1
        cx, cy = s.get("label_at", (cx, cy))
        label(zone_text(s), cx, cy, 2.0, u * 0.75)
    for c in lay.get("cameras", []):
        (px, py, _), (ax, ay, _) = c["pos_m"], c["aim_m"]
        yaw, half = math.atan2(ay - py, ax - px), math.atan(c.get("sensor_mm", 36) / 2 / c["lens_mm"])
        d = math.hypot(ax - px, ay - py)
        wedge = [(px, py)] + [(px + d * math.cos(yaw + k * half), py + d * math.sin(yaw + k * half)) for k in (-1, 1)]
        add(c["id"], wedge, [[0, 1, 2]], INK, 1.5, outline=True, edge=u * 0.08)
        label(c["id"], px, py - u * 1.2, 2.0, u * 0.75)
    path = lay.get("path", [])
    for k, (a, b) in enumerate(zip(path, path[1:])):  # player path: a thin ink strip, S and E at its ends
        d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
        nx, ny = -(b[1] - a[1]) / d * u * 0.1, (b[0] - a[0]) / d * u * 0.1
        add(f"path{k}", [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)],
            [[0, 1, 2, 3]], INK, 1.6)
    for tag, p in (("S", path[:1]), ("E", path[-1:])):
        for px, py in p:
            circle("path" + tag, px, py, u * 0.5, INK, 1.7)
            label(tag, px, py, 1.75, u * 0.6, (1, 1, 1))
    path_len = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))
    for c in lay.get("callouts", []):
        cx, cy = c["at_m"]
        circle(f"CO{c['n']}", cx, cy, u * 0.65, CALLOUT, 1.8)
        label(str(c["n"]), cx, cy, 1.9, u * 0.8, (1, 1, 1))
    for n in lay.get("notes", []):
        label(n["text"], *n["at_m"], 2.0, u * 1.1, INK, "LEFT", hand=True)

    # metre grid and axes, under everything
    gx0, gx1, gy0, gy1 = math.floor(x0) - 1, math.ceil(x1) + 1, math.floor(y0) - 1, math.ceil(y1) + 1
    step = 1 if gx1 - gx0 <= 30 and gy1 - gy0 <= 30 else 5
    for x in range(gx0, gx1 + 1, step):
        rect(f"gx{x}", x - u * 0.02, gy0, x + u * 0.02, gy1, GRID, 0.0)
        label(f"{x}", x, gy0 - u * 0.8, 2.0, u * 0.6)
    for y in range(gy0, gy1 + 1, step):
        rect(f"gy{y}", gx0, y - u * 0.02, gx1, y + u * 0.02, GRID, 0.0)
        label(f"{y}", gx0 - u * 0.5, y, 2.0, u * 0.6, align="RIGHT")
    label("m", gx1 + u * 0.6, gy0 - u * 0.8, 2.0, u * 0.6)

    # scale bar: two cells, black and white, below the axis labels
    sb, by = step, gy0 - u * 2.2
    rect("sb0", gx0, by, gx0 + sb, by + u * 0.4, INK, 1.0)
    rect("sb1", gx0 + sb, by, gx0 + 2 * sb, by + u * 0.4, (1, 1, 1), 1.0)
    add("sb_edge", [(gx0, by), (gx0 + 2 * sb, by), (gx0 + 2 * sb, by + u * 0.4), (gx0, by + u * 0.4)], [[0, 1, 2, 3]],
        INK, 1.01, outline=True, edge=u * 0.06)
    for k in range(3):
        label(f"{k * sb} m", gx0 + k * sb, by - u * 0.7, 2.0, u * 0.55)

    # key box to the right of the grid: zone categories in use, then the callout texts
    kx, ky = gx1 + u * 2, gy1
    rows = [(LEGEND[k], KEY[k]) for k in used] + ([(INK, f"Player path, {path_len:.0f} m")] if path else [])
    rows += [(None, "")] + [(CALLOUT, f"{c['n']}  {c['text']}") for c in lay.get("callouts", [])]
    kw = u * 16
    rect("key_bg", kx - u * 0.6, ky - u * (len(rows) + 2.2), kx + kw, ky + u * 0.6, (0.97, 0.97, 0.95), 0.5)
    label("KEY", kx, ky - u * 0.4, 2.0, u * 0.8, align="LEFT")
    for r, (col, text) in enumerate(rows):
        yy = ky - u * (r + 1.8)
        if col:
            rect(f"key{r}", kx, yy - u * 0.3, kx + u * 0.9, yy + u * 0.3, col if col in (CALLOUT, INK) else tint(col), 1.0, u * 0.08)
        label(text, kx + u * 1.4, yy, 2.0, u * 0.6, align="LEFT")
    if lay.get("title"):
        label(lay["title"], gx0, gy1 + u * 1.5, 2.0, u * 1.1, align="LEFT")

    sc = bpy.context.scene
    bx0, bx1, by0, by1 = gx0 - u * 2.5, kx + kw + u, by - u * 2, gy1 + u * 3
    w, h = bx1 - bx0, by1 - by0
    cam = bpy.data.objects.new("TOP", bpy.data.cameras.new("TOP"))
    cam.data.type, cam.data.ortho_scale, cam.data.clip_end = "ORTHO", max(w, h), 100
    cam.location = ((bx0 + bx1) / 2, (by0 + by1) / 2, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    long_px = 1800
    sc.render.resolution_x, sc.render.resolution_y = (long_px, round(long_px * h / w)) if w >= h else (round(long_px * w / h), long_px)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light, sc.display.shading.color_type = "FLAT", "OBJECT"
    sc.world = bpy.data.worlds.new("bg")
    sc.world.color = PAPER
    sc.view_settings.view_transform = "Standard"
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("layout rendered", out, sc.render.resolution_x, sc.render.resolution_y)


if __name__ == "__main__":
    main(*sys.argv[sys.argv.index("--") + 1:][:2])
