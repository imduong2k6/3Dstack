"""Self-test for blueprint.py (plain Python with Pillow, no Blender):

    python .claude/skills/modeling/scripts/selftest_blueprint.py

Rectifies a synthetic photo of a tilted checker plate and measures that its squares come out square and true to scale. Draws a blueprint
and checks the mirror plane, the shaded half, the view boxes and the marked circle by pixel. Refuses a spec with a bad form block.
"""
import json
import os
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
        test_draw(tmp)
    print("PASS")


if __name__ == "__main__":
    main()
