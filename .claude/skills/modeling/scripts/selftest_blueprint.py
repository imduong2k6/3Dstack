"""Self-test for blueprint.py (plain Python with Pillow, no Blender):

    python .claude/skills/modeling/scripts/selftest_blueprint.py

Rectifies a synthetic photo of a tilted checker plate and measures that its squares come out square and true to scale. Rectifies from two
pairs of parallel edges and a circle at several lenses, tilts and crops, exactly and with pick noise. Draws a blueprint and checks the
mirror plane, the shaded half, the view boxes and the marked circle by pixel. Refuses a spec with a bad form block.
"""
import json
import math
import os
import random
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blueprint as bp  # noqa: E402

SPEC = """---
asset: SM_Test
type: prop
source: model
form:
  measured_from: ref/front_rect.png
  sections:
    - name: body
      box_m: [[-0.1, 0, 0], [0.1, 0.05, 0.3]]
      symmetry: [x]
      features:
        - {name: window, box_m: [[-0.05, 0, 0.15], [0.05, 0.01, 0.25]]}
      circles:
        - {name: gland, kind: full, center_m: [0, 0, 0.07], axis: y, diameter_m: 0.04, segments: 24, repeat: 6, photo_px: {center: [50, 60], size: [30, 20]}}
        - {name: arch, kind: half, center_m: [0, 0, 0.3], axis: y, diameter_m: 0.06, segments: 16}
      repeats:
        - {name: lugs, count: 4, pitch_m: [0.02, 0, 0]}
      asymmetries:
        - {what: seal, evidence: real lead seal on the right, box_m: [[0.07, 0, 0.02], [0.09, 0.01, 0.05]]}
---
"""


def check(ok, what):
    if not ok:
        raise AssertionError(what)
    print("ok  ", what)


def near(c, ref, tol=12):
    return all(abs(a - b) <= tol for a, b in zip(c, ref))


def test_rectify(tmp):
    # true plate: 200 x 100 mm, drawn in perspective; four known corners and a black square of 50 mm in its middle
    corners = [(120, 60), (520, 110), (500, 330), (140, 300)]
    W, H = 800, 400
    src = Image.new("RGB", (W, H), (255, 255, 255))
    flat = Image.new("RGB", (400, 200), (230, 230, 230))
    ImageDraw.Draw(flat).rectangle([150, 50, 250, 150], fill=(0, 0, 0))     # 100 px = 50 mm at 2000 px/m
    a, b = [], []
    for (x, y), (u, v) in zip(corners, [(0, 0), (400, 0), (400, 200), (0, 200)]):      # photo to flat
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    warped = flat.transform((W, H), Image.PERSPECTIVE, bp._solve(a, b), Image.BICUBIC)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(corners, fill=255)
    src.paste(warped, (0, 0), mask)
    photo = os.path.join(tmp, "photo.png")
    src.save(photo)
    out = os.path.join(tmp, "rect.png")
    meta = bp.rectify(photo, corners, (0.2, 0.1), out, px_per_m=2000)
    check(meta["image_px"] == [400, 200], "rectified image is 200 x 100 mm at 2000 px/m")
    im = Image.open(out).convert("L")
    dark = [(x, y) for y in range(10, 190) for x in range(10, 390) if im.getpixel((x, y)) < 80]     # the test photo's own mask edge is left out
    xs, ys = [p[0] for p in dark], [p[1] for p in dark]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    check(abs(w - 100) <= 3 and abs(h - 100) <= 3, f"the 50 mm square comes out square and to scale ({w} x {h} px)")
    check(abs(min(xs) - 150) <= 3 and abs(min(ys) - 50) <= 3, "and in the right place")
    check(os.path.exists(out + ".json"), "scale written beside it")
    try:
        bp.rectify(photo, [(0, 0), (10, 10), (20, 20), (30, 30)], (0.2, 0.1), os.path.join(tmp, "bad.png"))
        check(False, "corners on one line are refused")
    except ValueError:
        check(True, "corners on one line are refused")


def camera(focal_mm, tilt, turn, shift=0):
    """World plane z = 0 to pixels: a 1200 x 1000 image on a 36 mm sensor, tilted and turned, the 200 mm panel filling about 60 % of the frame."""
    f = focal_mm / 36 * 1200
    dist = 0.2 * f / (0.6 * 1200)
    ct, st, cu, su = math.cos(tilt), math.sin(tilt), math.cos(turn), math.sin(turn)
    r = [[cu, -su], [ct * su, ct * cu], [st * su, st * cu]]
    def project(x, y):
        X, Y, Z = (r[i][0] * x + r[i][1] * y + (dist if i == 2 else 0) for i in range(3))
        return f * X / Z + 600 + shift, f * Y / Z + 500 - shift
    return project


def ratio_error_pct(h, project):
    """Worst error of the ratios between known distances on the panel, after the map, in %."""
    pts = [(-0.1, -0.06), (0.1, -0.06), (0.1, 0.06), (-0.1, 0.06), (-0.04, 0.0), (0.05, 0.03), (0.07, -0.04), (-0.07, 0.04)]
    pairs = [(0, 1), (1, 2), (0, 2), (4, 5), (5, 6), (6, 7), (4, 7), (2, 7)]
    got = [bp._apply(h, project(*p)) for p in pts]
    ratios = sorted(math.dist(got[i], got[j]) / math.dist(pts[i], pts[j]) for i, j in pairs)
    k = ratios[len(ratios) // 2]
    return max(abs(r / k - 1) * 100 for r in ratios)


def test_rectify_pairs(tmp):
    corners = [(-0.1, -0.06), (0.1, -0.06), (0.1, 0.06), (-0.1, 0.06)]
    ring = [(-0.04 + 0.02 * math.cos(2 * math.pi * i / 16), 0.02 * math.sin(2 * math.pi * i / 16)) for i in range(16)]
    def picks(project, jitter=lambda: (0, 0)):
        def at(p):
            x, y = project(*p)
            dx, dy = jitter()
            return x + dx, y + dy
        c = [at(p) for p in corners]
        # at the same picks a rectangle's corners serve both pairs: each edge is one pair member
        return [c[0], c[1], c[3], c[2]], [c[0], c[3], c[1], c[2]], [at(p) for p in ring]
    for focal, tilt, shift in ((24, 40, 0), (50, 60, 0), (300, 60, 0), (300, 40, 150), (24, 40, 150), (135, 20, 150)):
        project = camera(focal, math.radians(tilt), math.radians(30), shift)
        h, _ = bp.pairs_homography(*picks(project))
        err = ratio_error_pct(h, project)
        check(err < 0.5, f"exact picks at {focal} mm, tilt {tilt}, crop {shift}: within {err:.3f} %")
    rng = random.Random(7)
    worst = []
    for focal, tilt, shift in ((24, 40, 0), (300, 60, 0), (50, 40, 150)):
        project = camera(focal, math.radians(tilt), math.radians(30), shift)
        errs = sorted(ratio_error_pct(bp.pairs_homography(*picks(project, lambda: (rng.gauss(0, 1), rng.gauss(0, 1))))[0], project) for _ in range(200))
        worst.append(errs[int(len(errs) * 0.95)])
    check(max(worst) < 8, f"1 px of pick noise: worst ratio p95 {max(worst):.2f} % at three cameras")

    # a real image: a tilted panel with a black disc; it should come out round
    project = camera(50, math.radians(40), math.radians(30))
    src = Image.new("RGB", (1200, 1000), (255, 255, 255))
    d = ImageDraw.Draw(src)
    d.polygon([project(*p) for p in corners], fill=(230, 230, 230))
    d.polygon([project(*p) for p in [(-0.04 + 0.02 * math.cos(2 * math.pi * i / 90), 0.02 * math.sin(2 * math.pi * i / 90)) for i in range(90)]], fill=(0, 0, 0))
    photo = os.path.join(tmp, "pairs.png")
    src.save(photo)
    out = os.path.join(tmp, "pairs_rect.png")
    a, b, c = picks(project)
    meta = bp.rectify_pairs(photo, a, b, c, out)
    im = Image.open(out).convert("L")
    rim = [bp._apply(meta["photo_to_image"], p) for p in c]     # look round the disc only: what lies off the photo comes out black too
    cx, cy = sum(p[0] for p in rim) / len(rim), sum(p[1] for p in rim) / len(rim)
    r = int(max(math.dist(p, (cx, cy)) for p in rim) * 1.4)
    dark = [(x, y) for y in range(int(cy) - r, int(cy) + r) for x in range(int(cx) - r, int(cx) + r) if im.getpixel((x, y)) < 80]
    w, h = max(p[0] for p in dark) - min(p[0] for p in dark) + 1, max(p[1] for p in dark) - min(p[1] for p in dark) + 1
    check(abs(w - h) <= 3, f"the disc comes out round ({w} x {h} px)")
    check(meta["circle_spread_pct"] < 1, "and the report says the picks agree")
    panel = [bp._apply(meta["photo_to_image"], p) for p in a[:2]]
    check(abs(panel[0][1] - panel[1][1]) < 0.5 and panel[1][0] > panel[0][0], "pair A runs level, first point to second")
    check(bp.main(["rectify-pairs", photo, "--pair-a", *[f"{x},{y}" for x, y in a], "--pair-b", *[f"{x},{y}" for x, y in b], "--circle", *[f"{x},{y}" for x, y in c], "--out", os.path.join(tmp, "p.png")]) == 0, "it runs from the command line")
    for why, args in (("the same pair twice", (a, a, c)), ("too few circle points", (a, b, c[:4])), ("a pair with three points", (a[:3], b, c)), ("a circle in a line", (a, b, [(i * 10.0, i * 10.0) for i in range(8)]))):
        try:
            bp.pairs_homography(*args)
            check(False, f"{why} is refused")
        except ValueError:
            check(True, f"{why} is refused")


def test_draw(tmp):
    spec = os.path.join(tmp, "SM_Test.md")
    with open(spec, "w", encoding="utf-8") as f:
        f.write(SPEC)
    out = os.path.join(tmp, "bp.png")
    meta = bp.draw(spec, out, width=1500)
    im = Image.open(out).convert("RGB")
    front = meta["views"]["front"]["box_px"]
    side = meta["views"]["side"]["box_px"]
    top = meta["views"]["top"]["box_px"]
    s = 1 / meta["metres_per_px"]
    check(abs((front[2] - front[0]) / s - 0.2) < 1e-3 and abs((front[3] - front[1]) / s - 0.3) < 1e-3, "front view is 0.2 x 0.3 m at the scale in the json")
    check(abs((side[2] - side[0]) / s - 0.05) < 1e-3, "side view has the depth at the same scale")
    check(abs((top[2] - top[0]) - (front[2] - front[0])) < 1 and top[1] > front[3], "top view sits under the front at the same width")
    mid = (front[0] + front[2]) / 2
    ys = range(int(front[1]) + 5, int(front[3]) - 5)
    check(sum(near(im.getpixel((int(mid), y)), bp.PLANE, 25) for y in ys) > len(ys) / 3, "a dashed mirror plane runs up the middle of the front")
    y = int(front[1] + (front[3] - front[1]) * 0.08)
    check(near(im.getpixel((int(mid - s * 0.09), y)), bp.SHADE), "the half to model is shaded on the left")
    check(near(im.getpixel((int(mid + s * 0.09), y)), bp.PAPER), "the other half is not")
    r = s * 0.02
    cy = front[3] - s * 0.07
    check(any(near(im.getpixel((int(mid + r * dx), int(cy + dy))), bp.CIRCLE, 40) for dx in (-1, 1) for dy in range(-3, 4)), "the circle is drawn at its centre and size")
    check(os.path.exists(out + ".json"), "view boxes written beside it")

    photo = os.path.join(tmp, "ref.png")
    Image.new("RGB", (120, 120), (255, 255, 255)).save(photo)
    marked = os.path.join(tmp, "marked.png")
    rep = bp.mark(spec, photo, marked)
    check(rep == {"marked": ["gland"], "no_photo_px": ["arch"]}, "marked the circle with photo_px and listed the one without")
    m = Image.open(marked).convert("RGB")
    check(near(m.getpixel((50 - 15, 60)), bp.CIRCLE, 60), "the ring sits on the photo")

    bad = os.path.join(tmp, "SM_Bad.md")
    with open(bad, "w", encoding="utf-8") as f:
        f.write(SPEC.replace("segments: 24, repeat: 6", "segments: 26, repeat: 6"))
    check(bp.main(["draw", bad, "--out", os.path.join(tmp, "bad.png")]) == 1, "a bad form block is refused with exit 1")
    none = os.path.join(tmp, "SM_None.md")
    with open(none, "w", encoding="utf-8") as f:
        f.write("---\nasset: SM_None\n---\n")
    check(bp.main(["draw", none, "--out", os.path.join(tmp, "n.png")]) == 1, "no form block is refused with exit 1")
    check(bp.main(["rectify", photo, "--corners", "0,0", "10,0", "10,10", "0,10", "--size-m", "0.1", "0.1", "--out", os.path.join(tmp, "r.png")]) == 0, "rectify runs from the command line")
    json.load(open(os.path.join(tmp, "r.png.json")))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_rectify(tmp)
        test_rectify_pairs(tmp)
        test_draw(tmp)
    print("PASS")


if __name__ == "__main__":
    main()
