"""Flat references for the Modeler. Plain Python with Pillow, no Blender; selftest_blueprint.py tests it.

Take the perspective out of a photo, using a rectangle on the object whose real size is known (a front plate, the body's face). The
result is true to scale on that plane only; parts standing off it keep some parallax, so size those from dims_m or a second view:

    python blueprint.py rectify <photo> --corners x0,y0 x1,y1 x2,y2 x3,y3 --size-m W H --out ref/front_rect.png [--px-per-m 2000]

Corners run top left, top right, bottom right, bottom left, in photo pixels.

With no rectangle of known size, use two pairs of edges parallel on the object and points round one true circle, all on one plane:

    python blueprint.py rectify-pairs <photo> --pair-a x,y x,y x,y x,y --pair-b x,y x,y x,y x,y --circle x,y x,y x,y x,y x,y [...] --out ref/front_rect.png

Each pair is four points, two along each edge. Pair A comes out level, running from its first point to its second. The result gives true
proportions on that plane and no scale, so size it from dims_m. It stays true at any lens and on a crop cut from a bigger picture.

Draw the blueprint from the spec's `form` block: front, side and top at one real scale, with the outline, sections, features, circles and
their sectors, mirror planes, the half to model shaded, repeat counts and hatched true asymmetries. --mark also rings each circle that has
`photo_px` on the reference photo:

    python blueprint.py draw kit/SM_X.md --out kit/SM_X_blueprint.png [--underlay ref/front_rect.png] [--mark ref/photo.png --mark-out kit/SM_X_marked.png]

It writes <out>.json beside the image: each view's pixel box and metres per pixel, for loading the image as a reference plane. Frame: X
right, Y back (the front faces -Y), Z up, in metres, with the origin at the spec's pivot. Exit 1 on bad input.
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "modular-kit", "scripts"))
import check_spec as cs  # noqa: E402

PAPER, INK, GRID, PLANE, CIRCLE, ASYM, SHADE = (250, 250, 247), (30, 30, 34), (225, 225, 220), (200, 30, 40), (20, 90, 200), (210, 110, 0), (222, 234, 248)
VIEWS = {"front": (0, 2), "side": (1, 2), "top": (0, 1)}      # view -> (axis across, axis up)
AXIS = "xyz"


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _solve(a, b):
    """Gaussian elimination with pivoting; the shell's Python has no numpy."""
    n = len(b)
    m = [list(r) + [v] for r, v in zip(a, b)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        if abs(m[p][i]) < 1e-12:
            raise ValueError("the corners do not form a rectangle: three of them lie on one line")
        m[i], m[p] = m[p], m[i]
        for r in range(n):
            if r != i:
                k = m[r][i] / m[i][i]
                m[r] = [x - k * y for x, y in zip(m[r], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def rectify(photo, corners, size_m, out, px_per_m=None):
    """Warp the rectangle at `corners` (TL, TR, BR, BL in photo pixels) to a flat image at a true scale."""
    im = Image.open(photo).convert("RGB")
    w_m, h_m = size_m
    if w_m <= 0 or h_m <= 0:
        raise ValueError("--size-m must be two positive numbers")
    if px_per_m is None:      # keep about the detail the photo has along its longest corner edge
        edge = max(math.dist(corners[i], corners[(i + 1) % 4]) for i in range(4))
        px_per_m = edge / max(w_m, h_m)
    W, H = max(int(round(w_m * px_per_m)), 2), max(int(round(h_m * px_per_m)), 2)
    dst = [(0, 0), (W, 0), (W, H), (0, H)]
    a, b = [], []
    for (x, y), (u, v) in zip(dst, corners):   # PIL maps output pixels to input pixels
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    im.transform((W, H), Image.PERSPECTIVE, _solve(a, b), Image.BICUBIC).save(out)
    meta = {"from": os.path.abspath(photo), "corners_px": corners, "size_m": [w_m, h_m], "px_per_m": round(px_per_m, 3), "image_px": [W, H],
            "note": "true to scale on the plane of those corners only"}
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return meta


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _apply(h, p):
    x, y, w = (h[i][0] * p[0] + h[i][1] * p[1] + h[i][2] for i in range(3))
    return x / w, y / w


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _circle_stretch(pts):
    """The 2 x 2 map that turns the ellipse through pts into a circle, and major / minor. Least squares on a x^2 + b xy + c y^2 + d x + e y = 1, about the points' centre."""
    n = len(pts)
    cx, cy = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    s = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts) or 1.0
    rows = [[x * x, x * y, y * y, x, y] for x, y in (((p[0] - cx) / s, (p[1] - cy) / s) for p in pts)]
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(5)] for i in range(5)]
    atb = [sum(r[i] for r in rows) for i in range(5)]
    try:
        a, b, c = _solve(ata, atb)[:3]
    except ValueError:
        raise ValueError("the circle points don't fix an ellipse: pick them spread round it") from None
    if a * c - b * b / 4 <= 0 or a <= 0:
        raise ValueError("the circle points don't make an ellipse: check them")
    mid, diff = (a + c) / 2, math.hypot((a - c) / 2, b / 2)
    lo, hi = mid - diff, mid + diff
    k = math.sqrt(hi / lo)      # stretch by k along the eigenvector of hi, the ellipse's minor axis
    t = 0.5 * math.atan2(b, a - c)
    ux, uy = math.cos(t), math.sin(t)
    return [[1 + (k - 1) * ux * ux, (k - 1) * ux * uy], [(k - 1) * ux * uy, 1 + (k - 1) * uy * uy]], k


def pairs_homography(pair_a, pair_b, circle):
    """Photo pixels to a true-shape plane, from two pairs of parallel edges and a circle. The plane's rotation is set so pair A runs along +x."""
    if len(pair_a) != 4 or len(pair_b) != 4:
        raise ValueError("each pair is four points, two along each edge")
    if len(circle) < 5:
        raise ValueError("the circle needs at least 5 points; 8 or more spread round it is better")
    def vanish(q):
        return _cross(_cross([*q[0], 1], [*q[1], 1]), _cross([*q[2], 1], [*q[3], 1]))
    picks = [*pair_a, *pair_b, *circle]
    mx, my = sum(p[0] for p in picks) / len(picks), sum(p[1] for p in picks) / len(picks)
    span = max(math.hypot(p[0] - mx, p[1] - my) for p in picks) or 1.0
    norm = lambda q: [((p[0] - mx) / span, (p[1] - my) / span) for p in q]      # centred, so the numbers stay well scaled at any lens
    na, nb, nc = norm(pair_a), norm(pair_b), norm(circle)
    va, vb = vanish(na), vanish(nb)
    va, vb = [v / (math.hypot(*va) or 1.0) for v in va], [v / (math.hypot(*vb) or 1.0) for v in vb]
    line = _cross(va, vb)
    if math.hypot(*line) < 1e-9 or abs(line[2]) < 1e-9:
        raise ValueError("the two pairs must run in different directions on the object, and the vanishing line must miss your picks")
    line = [v / line[2] for v in line]      # w = 1 at the picks' centre
    hp = [[1, 0, 0], [0, 1, 0], line]
    if any(line[0] * x + line[1] * y + 1 <= 0 for x, y in na + nb + nc):
        raise ValueError("the vanishing line runs through your picks: check the pairs are parallel on the object")
    stretch, ratio = _circle_stretch([_apply(hp, p) for p in nc])
    affine = [[*stretch[0], 0], [*stretch[1], 0], [0, 0, 1]]
    h = _matmul(affine, hp)
    (x0, y0), (x1, y1) = _apply(h, na[0]), _apply(h, na[1])
    t = -math.atan2(y1 - y0, x1 - x0)
    h = _matmul([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]], h)
    to_norm = [[1 / span, 0, -mx / span], [0, 1 / span, -my / span], [0, 0, 1]]
    return _matmul(h, to_norm), ratio


def rectify_pairs(photo, pair_a, pair_b, circle, out, margin=0.25):
    """Warp a photo to true proportions on one plane. No size is known, so the long side keeps the photo's long side in pixels."""
    h, ratio = pairs_homography(pair_a, pair_b, circle)
    im = Image.open(photo).convert("RGB")
    picks = [_apply(h, p) for p in [*pair_a, *pair_b, *circle]]
    xs, ys = [p[0] for p in picks], [p[1] for p in picks]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    k = max(im.size) / max(x1 - x0, y1 - y0)
    to_px = [[k, 0, -x0 * k], [0, k, -y0 * k], [0, 0, 1]]
    full = _matmul(to_px, h)
    W, H = max(int(round((x1 - x0) * k)), 2), max(int(round((y1 - y0) * k)), 2)
    # PIL maps output pixels to input pixels, so solve full's inverse from four output corners
    a, b = [], []
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    inv = _invert3(full)
    for x, y in corners:
        u, v = _apply(inv, (x, y))
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    im.transform((W, H), Image.PERSPECTIVE, _solve(a, b), Image.BICUBIC).save(out)
    ring = [_apply(full, p) for p in circle]
    cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    rs = [math.hypot(p[0] - cx, p[1] - cy) for p in ring]
    meta = {"from": os.path.abspath(photo), "pair_a_px": pair_a, "pair_b_px": pair_b, "circle_px": circle, "image_px": [W, H], "photo_to_image": full,
            "circle_major_over_minor": round(ratio, 4), "circle_spread_pct": round((max(rs) - min(rs)) / (sum(rs) / len(rs)) * 100, 2),
            "note": "true proportions on that plane only, no scale: size it from dims_m. A large circle_spread_pct means the picks disagree"}
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return meta


def _invert3(m):
    c = [_cross(m[1], m[2]), _cross(m[2], m[0]), _cross(m[0], m[1])]
    det = sum(m[0][i] * c[0][i] for i in range(3))
    return [[c[j][i] / det for j in range(3)] for i in range(3)]


class Panel:
    """One orthographic view: real metres to image pixels."""

    def __init__(self, name, lo, hi, x, y, s):
        self.name, self.lo, self.hi, self.x, self.y, self.s = name, lo, hi, x, y, s
        self.a, self.b = VIEWS[name]

    def pt(self, p):
        return self.x + (p[self.a] - self.lo[self.a]) * self.s, self.y + (self.hi[self.b] - p[self.b]) * self.s

    def rect(self, box):
        (x0, y0), (x1, y1) = self.pt(box[0]), self.pt(box[1])
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

    def px_box(self):
        return [round(v, 2) for v in self.rect([self.lo, self.hi])]


def _dash(d, a, b, col, on=12, off=6, width=2):
    L = math.dist(a, b)
    t = 0.0
    while t < L:
        e = min(t + on, L)
        d.line([(a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L), (a[0] + (b[0] - a[0]) * e / L, a[1] + (b[1] - a[1]) * e / L)], fill=col, width=width)
        t = e + off


def _hatch(d, r, col, step=8):
    x0, y0, x1, y1 = r
    w, h = x1 - x0, y1 - y0
    for k in range(0, int(w + h), step):
        ax, ay = (x0 + k, y0) if k <= w else (x1, y0 + k - w)
        bx, by = (x0, y0 + k) if k <= h else (x0 + k - h, y1)
        d.line([(ax, ay), (bx, by)], fill=col, width=1)
    d.rectangle(r, outline=col, width=2)


def _circle(d, p, c, font):
    """A circle seen along its axis is drawn round, with sector lines; from the side it is a bar."""
    i = AXIS.index(c["axis"])
    r = c["diameter_m"] / 2
    rep = c.get("repeat", 1)
    if i in (p.a, p.b):      # edge on
        lo = list(c["center_m"])
        hi = list(c["center_m"])
        o = p.a if i == p.b else p.b
        lo[o] -= r
        hi[o] += r
        d.line([p.pt(lo), p.pt(hi)], fill=CIRCLE, width=3)
        return
    cx, cy = p.pt(c["center_m"])
    R = r * p.s
    box = [cx - R, cy - R, cx + R, cy + R]
    if c["kind"] == "half":   # `half` names the side kept: top, bottom, left or right, default top
        start = {"top": 180, "bottom": 0, "left": 90, "right": 270}.get(c.get("half", "top"), 180)
        d.arc(box, start, start + 180, fill=CIRCLE, width=3)
    else:
        d.ellipse(box, outline=CIRCLE, width=3)
    d.line([(cx - 6, cy), (cx + 6, cy)], fill=CIRCLE, width=2)
    d.line([(cx, cy - 6), (cx, cy + 6)], fill=CIRCLE, width=2)
    if rep > 1:
        for k in range(rep):
            t = 2 * math.pi * k / rep - math.pi / 2
            d.line([(cx, cy), (cx + R * math.cos(t), cy + R * math.sin(t))], fill=CIRCLE, width=1)
        t0 = -math.pi / 2
        d.pieslice(box, math.degrees(t0), math.degrees(t0 + 2 * math.pi / rep), outline=PLANE, width=3)
    label = f"{c['name']} d{c['diameter_m'] * 1000:g} mm, {c.get('segments', '?')} seg" + (f", x{rep} model 1 sector" if rep > 1 else "")
    d.text((cx + R + 6, cy - 8), label, fill=CIRCLE, font=font)


def _section(d, p, s, font):
    box = s["box_m"]
    for ax in s.get("symmetry") or []:       # shade the half to model first, so the planes and lines sit on top
        i = AXIS.index(ax)
        if i in (p.a, p.b):
            at = (s.get("plane_m") or {}).get(ax, 0)
            half = [list(box[0]), list(box[1])]
            half[1][i] = at
            d.rectangle(p.rect(half), fill=SHADE)
    d.rectangle(p.rect(box), outline=INK, width=2)
    for f in s.get("features") or []:
        r = p.rect(f["box_m"])
        d.rectangle(r, outline=INK, width=1)
        d.text((r[0] + 3, r[1] + 2), f["name"], fill=INK, font=font)
    for c in s.get("circles") or []:
        _circle(d, p, c, font)
    for a in s.get("asymmetries") or []:
        r = p.rect(a["box_m"])
        _hatch(d, r, ASYM)
        d.text((r[0], r[3] + 2), "keep: " + a["what"], fill=ASYM, font=font)
    for ax in s.get("symmetry") or []:
        i = AXIS.index(ax)
        if i in (p.a, p.b):
            at = (s.get("plane_m") or {}).get(ax, 0)
            lo, hi = list(box[0]), list(box[1])
            lo[i] = hi[i] = at
            _dash(d, p.pt(lo), p.pt(hi), PLANE)


def draw(spec_path, out, underlay=None, width=2000):
    data = cs.load_spec(spec_path)
    errors = []
    form = data.get("form")
    if form is None:
        raise ValueError("the spec has no form block: write it first (modeling step 2)")
    cs._check_form(form, lambda code, key, msg, **kw: errors.append(f"{key}: {msg}"))
    if errors:
        raise ValueError("form block has errors:\n  " + "\n  ".join(errors))
    secs = form["sections"]
    lo = [min(s["box_m"][0][i] for s in secs) for i in range(3)]
    hi = [max(s["box_m"][1][i] for s in secs) for i in range(3)]
    ext = [h - l for l, h in zip(lo, hi)]
    # front and side on the top row, top view under the front; one scale for all three
    margin = 70
    gap = 90
    scale = (width - 2 * margin - gap) / (ext[0] + ext[1])
    H = int(margin + 40 + ext[2] * scale + gap + ext[1] * scale + margin + 40 + 22 * sum(len(s.get("repeats") or []) for s in secs))
    im = Image.new("RGB", (width, H), PAPER)
    d = ImageDraw.Draw(im, "RGB")
    font, head = _font(18), _font(24)
    top = margin + 40
    panels = {"front": Panel("front", lo, hi, margin, top, scale),
              "side": Panel("side", lo, hi, margin + ext[0] * scale + gap, top, scale),
              "top": Panel("top", lo, hi, margin, top + ext[2] * scale + gap, scale)}
    if underlay:
        u = Image.open(underlay).convert("RGB")
        r = panels["front"].rect([lo, hi])
        u = u.resize((max(int(r[2] - r[0]), 1), max(int(r[3] - r[1]), 1)))
        im.paste(Image.blend(Image.new("RGB", u.size, PAPER), u, 0.45), (int(r[0]), int(r[1])))
    for name, p in panels.items():
        for s in secs:
            _section(d, p, s, font)
        r = p.rect([lo, hi])
        d.rectangle(r, outline=GRID, width=1)
        size = f"{(hi[p.a] - lo[p.a]) * 1000:g} x {(hi[p.b] - lo[p.b]) * 1000:g} mm"
        d.text((r[0], r[1] - 34), f"{name.upper()}  {size}", fill=INK, font=head)
    y = H - margin - 22 * sum(len(s.get("repeats") or []) for s in secs)
    d.text((margin, y), "Shaded: the half to model. Red dashes: mirror plane. Blue: round details. Orange hatch: real asymmetry, kept.", fill=INK, font=font)
    for s in secs:
        for r in s.get("repeats") or []:
            y += 22
            d.text((margin, y), f"{s['name']}: {r['name']}, {r['count']} in a row" + (f", pitch {r['pitch_m']} m" if r.get("pitch_m") else "") + ": model 1, Array the rest", fill=INK, font=font)
    im.save(out)
    meta = {"spec": os.path.abspath(spec_path), "image": os.path.abspath(out), "metres_per_px": round(1 / scale, 7),
            "views": {n: {"box_px": p.px_box(), "across": AXIS[p.a], "up": AXIS[p.b]} for n, p in panels.items()},
            "bounds_m": [lo, hi], "underlay": underlay}
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return meta


def mark(spec_path, photo, out):
    """Ring every circle that has photo_px: {center: [x, y], size: [w, h]} on the reference, and report how many were marked."""
    form = cs.load_spec(spec_path).get("form") or {}
    im = Image.open(photo).convert("RGB")
    d = ImageDraw.Draw(im)
    font = _font(max(14, im.size[1] // 60))
    marked, missing = [], []
    for s in form.get("sections", []):
        for c in s.get("circles") or []:
            px = c.get("photo_px")
            if not px:
                missing.append(c["name"])
                continue
            x, y = px["center"]
            w, h = px["size"]
            d.ellipse([x - w / 2, y - h / 2, x + w / 2, y + h / 2], outline=CIRCLE, width=3)
            d.text((x + w / 2 + 5, y - 9), f"{c['name']} ({c['kind']})" + (f" x{c['repeat']}" if c.get("repeat", 1) > 1 else ""), fill=CIRCLE, font=font)
            marked.append(c["name"])
    im.save(out)
    return {"marked": marked, "no_photo_px": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="blueprint.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rectify")
    r.add_argument("photo")
    r.add_argument("--corners", nargs=4, required=True, metavar="X,Y", help="top left, top right, bottom right, bottom left")
    r.add_argument("--size-m", nargs=2, type=float, required=True, metavar=("W", "H"))
    r.add_argument("--px-per-m", type=float)
    r.add_argument("--out", required=True)
    q = sub.add_parser("rectify-pairs")
    q.add_argument("photo")
    q.add_argument("--pair-a", nargs=4, required=True, metavar="X,Y", help="two along one edge, two along an edge parallel to it on the object")
    q.add_argument("--pair-b", nargs=4, required=True, metavar="X,Y", help="the same, for edges running another way")
    q.add_argument("--circle", nargs="+", required=True, metavar="X,Y", help="points round one true circle on the same plane")
    q.add_argument("--out", required=True)
    b = sub.add_parser("draw")
    b.add_argument("spec")
    b.add_argument("--out", required=True)
    b.add_argument("--underlay")
    b.add_argument("--width", type=int, default=2000)
    b.add_argument("--mark")
    b.add_argument("--mark-out")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "rectify":
            corners = [tuple(float(v) for v in c.split(",")) for c in a.corners]
            if any(len(c) != 2 for c in corners):
                raise ValueError("each corner is x,y")
            print(json.dumps(rectify(a.photo, corners, a.size_m, a.out, a.px_per_m)))
        elif a.cmd == "rectify-pairs":
            pts = lambda items: [tuple(float(v) for v in c.split(",")) for c in items]
            print(json.dumps(rectify_pairs(a.photo, pts(a.pair_a), pts(a.pair_b), pts(a.circle), a.out)))
        else:
            rep = draw(a.spec, a.out, a.underlay, a.width)
            if a.mark:
                rep["marks"] = mark(a.spec, a.mark, a.mark_out or os.path.splitext(a.out)[0] + "_marked.png")
            print(json.dumps(rep))
    except (ValueError, OSError, cs.SpecError) as e:
        print("blueprint:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
