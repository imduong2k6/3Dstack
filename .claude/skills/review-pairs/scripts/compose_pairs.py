"""Compose captioned before/after pairs and a framing contact sheet, headless, no .blend needed (tested with bpy 5.2.3).

    bash bin/blender-bg --python .claude/skills/review-pairs/scripts/compose_pairs.py -- pairs \
        --cams <reviews>/fix_cams.json --dir <reviews>/pairs --before-label "r2" --after-label "r3"
    bash bin/blender-bg --python .../compose_pairs.py -- contact --cams <reviews>/fix_cams.json --dir <reviews>/pairs/before --out <reviews>/pairs/framing.png
    bash bin/blender-bg --python .../compose_pairs.py -- contact --dir <reviews> --out <reviews>/contact.png --title "G2 r1"   # the gate's contact sheet

`pairs` reads <dir>/before/<id>.png and <dir>/after/<id>.png (with their _meta.json) and writes <dir>/<id>_pair.png, before on
the left, after on the right, with the issue's caption and a note line (engine, exposure, camera source), plus <dir>/pairs.json
for the gate board. `contact` lays one side's frames out in fix_cams order with id and caption, to check the framing before
the expensive render. Pillow is not in Blender's Python, so this uses numpy, imbuf and blf.
"""
import argparse
import json
import os
import sys

import bpy
import imbuf
import blf
import numpy as np

D = bpy.data
WHITE, GREY = (1, 1, 1), (0.75, 0.75, 0.75)
TMP = None


def load(p, width=None):
    """Image as float RGBA, row 0 at the top, optionally resized to a width."""
    if width:
        ib = imbuf.load(p)
        w, h = ib.size
        if w != width:
            ib.resize((width, round(h * width / w)), method="BILINEAR")
        imbuf.write(ib, filepath=TMP)
        ib.free()
        p = TMP
    im = D.images.load(p, check_existing=False)
    im.colorspace_settings.name = "Non-Color"  # keep the stored display values
    w, h = im.size
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    D.images.remove(im)
    px[..., 3] = 1
    return px


def wrap(text, size, maxw):
    blf.size(0, size)
    lines, cur = [], ""
    for wd in text.split():
        t = (cur + " " + wd).strip()
        if blf.dimensions(0, t)[0] > maxw and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = t
    return lines + [cur]


def save(arr, p, labels):
    h, w = arr.shape[:2]
    im = D.images.new("sheet", w, h)
    im.colorspace_settings.name = "Non-Color"
    im.pixels = arr[::-1].ravel()
    im.filepath_raw, im.file_format = p, "PNG"
    im.save()
    D.images.remove(im)
    ib = imbuf.load(p)
    with blf.bind_imbuf(0, ib):
        for x, y, size, text, col in labels:
            blf.size(0, size)
            blf.color(0, *col, 1)
            blf.position(0, x, h - y - size, 0)
            blf.draw_buffer(0, text)
    imbuf.write(ib, filepath=p)
    ib.free()
    if os.path.exists(TMP):
        os.remove(TMP)


def pair(left, right, labels2, caption, notes, out, cw):
    L, R = load(left, cw), load(right, cw)
    ch = max(L.shape[0], R.shape[0])
    M, BAR, FS, CS = 16, 44, 26, 22
    cap, nts = wrap(caption, CS, 2 * cw + M - 8), [ln for n in notes for ln in wrap(n, 18, 2 * cw + M - 8)]
    H, W = M + BAR + ch + 12 + len(cap) * (CS + 8) + len(nts) * 26 + M, 3 * M + 2 * cw
    s = np.zeros((H, W, 4), np.float32)
    s[..., :3], s[..., 3] = 0.08, 1
    y0 = M + BAR
    s[y0:y0 + L.shape[0], M:M + cw] = L
    s[y0:y0 + R.shape[0], 2 * M + cw:2 * M + 2 * cw] = R
    lab = [(M + 4, M + 8, FS, labels2[0], WHITE), (2 * M + cw + 4, M + 8, FS, labels2[1], WHITE)]
    y = y0 + ch + 12
    for ln in cap:
        lab.append((M + 4, y, CS, ln, WHITE))
        y += CS + 8
    for ln in nts:
        lab.append((M + 4, y, 18, ln, GREY))
        y += 26
    save(s, out, lab)


def engine_label(c, meta):
    return "Workbench material" if c["engine"] == "BLENDER_WORKBENCH" else f"Cycles {meta.get('cycles_spp', '?')} spp"


def exposure_note(c, mb, ma):
    if c["engine"] == "BLENDER_WORKBENCH":
        return ""
    eb, ea = mb["view"].get("exposure"), ma["view"].get("exposure")
    d = ma.get("file_differs")
    txt = f"Exposure {eb:.2f} both sides" if eb == ea else f"Exposure before {eb:.2f}, after {ea:.2f}"
    return txt + (f" (the new file's own is {ma['file_view']['exposure']:.2f}; matched to the before side)" if d and "exposure" in d else "")


def make_pairs(a):
    spec = json.load(open(a.cams))
    mb, ma = (json.load(open(os.path.join(a.dir, s, "_meta.json"))) for s in ("before", "after"))
    labels = (f"Before ({a.before_label})", f"After ({a.after_label})")
    made = []
    for c in spec["cams"]:
        f1, f2 = (os.path.join(a.dir, s, c["id"] + ".png") for s in ("before", "after"))
        if not (os.path.exists(f1) and os.path.exists(f2)):
            print("skip", c["id"], "(a side is missing)")
            continue
        notes = [" | ".join(x for x in [engine_label(c, mb), exposure_note(c, mb, ma),
                                         f"From {c['review_cam']}'s transform" if c.get("review_cam") else "Same camera both sides"] if x)]
        if c.get("before"):
            b = c["before"]
            notes.append(b.get("note") or f"Before camera: {b.get('lens_mm', c['lens_mm'])} mm.")
        tf = ma.get("frames", {}).get(c["id"], {}).get("targets_in_frame")
        if tf is not None and tf < 0.5:
            notes.append("Check: the fixed objects are mostly outside this frame after the change.")
        out = os.path.join(a.dir, c["id"] + "_pair.png")
        pair(f1, f2, labels, c["caption"], notes, out, a.cell_width)
        made.append({"id": c["id"], "file": out, "caption": c["caption"], "engine": c["engine"], "notes": notes, "source": c.get("source", "")})
    json.dump({"before": a.before_label, "after": a.after_label, "pairs": made}, open(os.path.join(a.dir, "pairs.json"), "w"), indent=1)
    print("PAIRS COMPOSED", len(made))
    for m in made:
        print(" ", m["file"])
    return len(made)


def make_contact(a):
    cols, cw, chh, M, FS, CS, ncap = 4, 560, 420, 12, 24, 15, 5
    if a.cams:
        spec, meta = json.load(open(a.cams)), json.load(open(os.path.join(a.dir, "_meta.json")))
        cells = [c for c in spec["cams"] if os.path.exists(os.path.join(a.dir, c["id"] + ".png"))]
    else:  # the gate's contact sheet: every capture in --dir, by file name, without captions
        meta, ncap = {}, 0
        cells = [{"id": f[:-4], "caption": ""} for f in sorted(os.listdir(a.dir))
                 if f.endswith(".png") and not f.startswith(("_", "contact"))]
    rows = -(-len(cells) // cols)
    TOP = 56
    cellh = FS + 6 + chh + 6 + ncap * (CS + 5) + M
    s = np.zeros((TOP + rows * cellh + M, cols * (cw + M) + M, 4), np.float32)
    s[..., :3], s[..., 3] = 0.08, 1
    lab = [(M + 4, 14, 30, a.title, WHITE)]
    for k, c in enumerate(cells):
        r, cc = divmod(k, cols)
        x0, y0 = M + cc * (cw + M), TOP + r * cellh
        f = os.path.join(a.dir, c["id"] + ".png")
        ib = imbuf.load(f)
        w0, h0 = ib.size
        ib.free()
        px = load(f, round(w0 * min(cw / w0, chh / h0)))
        y1 = y0 + FS + 6
        s[y1:y1 + px.shape[0], x0:x0 + px.shape[1]] = px
        lab.append((x0 + 2, y0, FS, c["id"] + ("  " + engine_label(c, meta) if a.cams else ""), WHITE))
        for j, ln in enumerate(wrap(c["caption"], CS, cw)[:ncap]):
            lab.append((x0 + 2, y1 + chh + 6 + j * (CS + 5), CS, ln, GREY))
    save(s, a.out, lab)
    print("CONTACT", len(cells), a.out)
    return len(cells)


def main():
    global TMP
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["pairs", "contact"])
    ap.add_argument("--cams", help="fix_cams.json; required for pairs, optional for contact")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", help="contact: the sheet to write")
    ap.add_argument("--before-label", default="previous round")
    ap.add_argument("--after-label", default="this round")
    ap.add_argument("--title", default="Framing preview")
    ap.add_argument("--cell-width", type=int, default=960)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if a.mode == "pairs" and not a.cams:
        ap.error("pairs needs --cams")
    TMP = os.path.join(a.dir, "_compose_tmp.png")
    n = make_pairs(a) if a.mode == "pairs" else make_contact(a)
    if not n:
        print("nothing composed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:  # under --python an exception would exit 0
        import traceback
        traceback.print_exc()
        print("compose_pairs error:", repr(e))
        sys.exit(1)
