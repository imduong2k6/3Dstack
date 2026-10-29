"""Re-crop turnaround grids into per-view tiles by object bounds (the grid split cuts wide views).
Usage: [RECROP_THR=0.6 RECROP_COL=0.03] bash bin/blender-bg --python-exit-code 1 \
    --python .claude/skills/tripo-props/scripts/recrop_turns.py -- <dir_with_*_turn.png> <out_dir>
Processes EVERY *_turn.png in the folder: copy only the sheets you want into a temp folder first.
Rows are found by white bands, objects in a row by white column gaps; 2-row grids -> front,left,back,right
(TL,TR,BL,BR), single strips -> v0..vN. Every view is padded onto one square size (same scale across views) and saved 1024 PNG.
RECROP_THR (default 0.25) = ink threshold, RECROP_COL (default 0) = min column occupancy; raise both when cast shadows
merge the views of a strip into one object. Check the printed bounds: objs must equal the number of views."""
import os, sys
import numpy as np
import bpy

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)

def runs(occ, min_gap):
    idx = np.flatnonzero(occ)
    if not len(idx):
        return []
    res, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            res.append((s, p + 1)); s = i
        p = i
    res.append((s, p + 1))
    return res

report = []
for f in sorted(os.listdir(src)):
    if not f.endswith("_turn.png"):
        continue
    base = f[:-9]
    img = bpy.data.images.load(os.path.join(src, f))
    W, H = img.size
    px = np.empty(W * H * 4, np.float32); img.pixels.foreach_get(px)
    a = px.reshape(H, W, 4)[::-1]                       # top-down rows
    mask = (3.0 - a[..., :3].sum(2)) > float(os.environ.get("RECROP_THR", "0.25"))
    rows = [r for r in runs(mask.sum(1) > W * 0.002, H // 40) if r[1] - r[0] > H // 20]
    objs = []
    for r0, r1 in rows:
        cols = [c for c in runs(mask[r0:r1].sum(0) > max(2, (r1 - r0) * float(os.environ.get("RECROP_COL", "0"))), W // 60) if c[1] - c[0] > W // 30]
        for c0, c1 in cols:
            ys = np.flatnonzero(mask[r0:r1, c0:c1].any(1))
            objs.append((c0, r0 + ys[0], c1, r0 + ys[-1] + 1))
    names = ["front", "left", "back", "right"] if len(rows) == 2 else [f"v{i}" for i in range(len(objs))]
    side = int(max(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in objs) * 1.12)   # one scale for every view of a sheet
    for name, (x0, y0, x1, y1) in zip(names, objs):
        w, h = x1 - x0, y1 - y0
        canvas = np.ones((side, side, 4), np.float32)
        oy, ox = (side - h) // 2, (side - w) // 2
        canvas[oy:oy + h, ox:ox + w] = a[y0:y1, x0:x1]
        canvas[..., 3] = 1.0
        im = bpy.data.images.new(f"{base}_{name}", side, side)
        im.pixels.foreach_set(canvas[::-1].ravel())
        im.scale(1024, 1024)
        im.filepath_raw = os.path.join(out, f"{base}_{name}.png")
        im.file_format = "PNG"
        im.save()
    report.append(f"{base}: rows={len(rows)} objs={len(objs)} " + " ".join(f"[{x0},{y0},{x1},{y1}]" for x0, y0, x1, y1 in objs))
print("RECROP\n" + "\n".join(report))
