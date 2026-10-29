"""Props atlas, Blender 5.2: the Tripo placeholder props on one material, to keep a game export under its material cap.
Written and tested on the KWC alley project; BASES and RETOUCH below still hold that project's props.

Live session (the route's Blender worker, through MCP):
    exec(open(r"<repo>/.claude/skills/tripo-props/scripts/props_atlas.py").read())
    BASES = ("Meter_kWh", "JunctionBox")   # this project's props in cell order; append only, never reorder
    build(r"<work_dir>")                   # writes <work_dir>/textures/props_atlas and textures/tripo_src
    retouch(r"<work_dir>")                 # the RETOUCH look fixes on cells that are already in the atlas

The placeholder masters SM_<base> (tripo_cleanup.py) each have a material M_<base>:
Principled BSDF + Normal Map + four packed 1K images T_<base>_BC (sRGB), _N, _R, _M (Non-Color). build() puts
them all on one material, M_Props_Atlas: a copy of the first prop's node graph with its images swapped for
textures/props_atlas/T_Props_Atlas_BC|N|R|M.png: 4 columns of 1024 px cells in BASES order, row by row from the
top-left, unused cells filled with neutral values. Width 4096; height = rows * 1024, rows = the next power of two
>= ceil(n / 4), n = highest cell index in use + 1 (15 props 4096 x 4096, 19 props 4096 x 8192). Each source is
resampled (Lanczos 3) to 1008 px, RETOUCH applied, and edge-extended 8 px on every side, so mips do not mix two
props. Each master's UVMap is scaled and moved into its cell (no rotation, so tangent-space normals stay valid);
the linked duplicates in 04_Dressing share the mesh.
Before any scene change: each prop is checked (the Tripo node graph, one slot, one UV layer UVMap, material
settings equal to the first prop's, UVs in [0, 1]: faces off by whole tiles are moved back, a face across a tile
edge skips the prop), and every source image file is written to textures/tripo_src/<base>/ (never over a
different file) and read back. Then the old materials and their images are removed. Meshes get
props_atlas = cell index and props_atlas_uv = [su, sv, ou, ov] (uv_atlas = uv_tripo * scale + offset).
Extending: when some props are already atlased and new ones (own M_<base>) arrived, build() keeps the old
sheet pixels verbatim (same px from the top-left), adds the new cells, and re-maps the old meshes' UVs when the
height grew. With nothing pending a second run is a no-op. Never opens or saves a .blend.
Test: scripts/tests/test_props_atlas.py (it uses the KWC names in BASES and RETOUCH as fixtures). Notes: ../SKILL.md.
"""
import hashlib
import json
import os
import re

import bpy
import numpy as np

OUT_REL, SRC_REL = ("textures", "props_atlas"), ("textures", "tripo_src")
MAT, TAG, LAYOUT = "M_Props_Atlas", "props_atlas", "props_atlas_layout.json"
# the KWC alley's props (the test's fixtures); set BASES to this project's props after exec
BASES = ("AC_Split", "AC_Window", "BagHeap", "Basket_Rattan", "Bucket_Plastic", "CartLoad", "Crate_Plastic",
         "DistBoard", "GasCylinder", "Handcart", "JunctionBox", "MeterBox_A", "MeterBox_B", "Meter_kWh", "Sack",
         "Misc_BarberChair", "Misc_EarthGodShrine", "Misc_BirdCage", "Misc_GroceryShelf",
         "Slippers", "Thermos", "NewspaperStack", "EnamelSet", "ShirtHanger", "Bicycle", "Radio", "Chair_Plastic",
         "Kettle", "PotPlant")
GRID, PAD, CELL = 4, 8, 1024
W = GRID * CELL                  # 4096; the height is rows_for(n) * CELL
INNER = CELL - 2 * PAD           # 1008 px of content per cell
# suffix: colour space, fill of the unused cell
MAPS = {"BC": ("sRGB", (0.5, 0.5, 0.5)), "N": ("Non-Color", (0.5, 0.5, 1.0)),
        "R": ("Non-Color", (0.5, 0.5, 0.5)), "M": ("Non-Color", (0.0, 0.0, 0.0))}
LINKS = {("BSDF_PRINCIPLED", "Base Color"): "BC", ("NORMAL_MAP", "Color"): "N",
         ("BSDF_PRINCIPLED", "Roughness"): "R", ("BSDF_PRINCIPLED", "Metallic"): "M"}
NODES = sorted(["BSDF_PRINCIPLED", "NORMAL_MAP", "OUTPUT_MATERIAL"] + ["TEX_IMAGE"] * 4)
OTHER_LINKS = [("BSDF_PRINCIPLED", "OUTPUT_MATERIAL", "Surface"), ("NORMAL_MAP", "BSDF_PRINCIPLED", "Normal")]
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)
STRAW, WHITE = (np.array(c, np.float32) / 255 for c in ((0xB4, 0x9A, 0x62), (0xE8, 0xE6, 0xDE)))


def _root(root=None):
    if root:
        return str(root)
    if not bpy.data.filepath:
        raise ValueError("pass root (the project's work_dir) for an unsaved file")
    return os.path.dirname(bpy.data.filepath)


def rows_for(n):
    """Rows of cells for n cells (highest cell index + 1): ceil(n / GRID) up to the next power of two."""
    return 1 << max(0, -(-n // GRID) - 1).bit_length()


def cell_xy(i, rows):
    """Content corner of cell i in px from the atlas bottom-left (Blender pixel order, row 0 at the bottom) of a
    sheet with `rows` rows; cells are numbered row by row from the top-left."""
    return (i % GRID) * CELL + PAD, (rows - 1 - i // GRID) * CELL + PAD


def _roles(mat):
    """{suffix: image node} when mat is the Tripo graph, else the reason it is not."""
    nt = mat.node_tree if mat else None
    if nt is None:
        return "no node tree"
    types = sorted(n.type for n in nt.nodes)
    if types != NODES:
        return f"nodes {types}"
    roles = {}
    for lk in nt.links:
        if lk.from_node.type == "TEX_IMAGE":
            k = LINKS.get((lk.to_node.type, lk.to_socket.identifier))
            if k is None or k in roles or lk.from_socket.identifier != "Color":
                return f"link {lk.from_node.name}.{lk.from_socket.identifier} -> {lk.to_socket.identifier}"
            roles[k] = lk.from_node
    other = sorted((lk.from_node.type, lk.to_node.type, lk.to_socket.identifier)
                   for lk in nt.links if lk.from_node.type != "TEX_IMAGE")
    if other != OTHER_LINKS:
        return f"links {other}"
    if len(roles) != 4 or any(n.image is None for n in roles.values()):
        return f"images wired: {sorted(k for k, n in roles.items() if n.image)}"
    return roles


def _sig(mat):
    """Everything besides the images that shapes the look; must match across the props sharing the atlas."""
    nodes = mat.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    nm = next(n for n in nodes if n.type == "NORMAL_MAP")
    r = lambda v: tuple(round(x, 4) for x in v) if hasattr(v, "__len__") else round(v, 4) if isinstance(v, float) else v
    s = {f"{n.type}.{i.identifier}": r(i.default_value) for n in (bsdf, nm) for i in n.inputs
         if not i.is_linked and hasattr(i, "default_value")}
    s.update(distribution=bsdf.distribution, subsurface=bsdf.subsurface_method, space=nm.space, uv_map=nm.uv_map,
             render_method=mat.surface_render_method, backface=mat.use_backface_culling)
    s.update({"tex_" + k: (n.interpolation, n.extension, n.projection) for k, n in _roles(mat).items()})
    return s


def _uvs(me):
    raw = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", raw)
    return raw.reshape(-1, 2).astype(np.float64)


def _fold(me, uv):
    """UVs moved into [0, 1] face by face by whole tiles (the same texels under REPEAT): (uv, faces moved), or
    (None, faces) when faces span a tile edge, which an atlas cell cannot repeat."""
    eps = 1e-5
    start = np.empty(len(me.polygons), np.int32)
    total = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", start)
    me.polygons.foreach_get("loop_total", total)
    off = np.cumsum(total) - total
    loops = np.repeat(start, total) + np.arange(total.sum()) - np.repeat(off, total)   # loop ids, face by face
    k = np.floor(np.minimum.reduceat(uv[loops], off, axis=0) + eps)                    # whole tiles per face
    out = uv.copy()
    out[loops] -= np.repeat(k, total, axis=0)
    span = (np.maximum.reduceat(out[loops], off, axis=0) > 1 + eps).any(1)
    if span.any():
        return None, int(span.sum())
    return np.clip(out, 0.0, 1.0), int((k != 0).any(1).sum())


def _taps(n_out, n_in, a=3):
    """Lanczos-a resampling from n_in to n_out px, pixel centres aligned, edges clamped: (index, weight) per
    output px and tap, both (n_out, taps). Taps instead of a dense matrix: a dense matmul takes ~11 s a map."""
    s = n_in / n_out
    c = (np.arange(n_out) + 0.5) * s - 0.5
    f = max(s, 1.0)
    r = int(np.ceil(a * f))
    i = np.floor(c).astype(int)[:, None] + np.arange(-r, r + 1)
    x = (i - c[:, None]) / f
    w = np.sinc(x) * np.sinc(x / a) * (np.abs(x) < a)
    return np.clip(i, 0, n_in - 1), (w / w.sum(1, keepdims=True)).astype(np.float32)


def _pixels(img):
    w, h = img.size
    if not w:
        raise RuntimeError(f"props atlas: {img.name} has no pixels; nothing changed")
    ch = img.channels
    px = np.empty(w * h * ch, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, ch)
    return px[..., :3] if ch >= 3 else np.repeat(px[..., :1], 3, 2)


def _file_px(path):
    img = bpy.data.images.load(path, check_existing=False)
    try:
        return _pixels(img)
    finally:
        bpy.data.images.remove(img)


# ---- Phase-2 retouches: arrays are the INNER x INNER content (rows bottom-up), BC as stored (sRGB-encoded)
def _detail(a):
    """Luminance of a relative to its median (1 = typical)."""
    L = a @ LUM
    return L / max(float(np.median(L)), 1e-3)


def _weave():
    """Over-under basket weave in cell px: 6 px strands in a checker of 6 px squares whose direction alternates
    (period 12 px); strand top 1.1, edge 0.8, gap 0.55."""
    prof = np.array([0.55, 0.8, 1.1, 1.1, 0.8, 0.55], np.float32)
    y, x = np.mgrid[0:INNER, 0:INNER]
    return np.where(((x // 6 + y // 6) & 1) == 0, prof[y % 6], prof[x % 6])


def _basket_bc(a):
    """Straw #B49A62 x source luminance detail (0.75..1.25) x weave; mean kept on straw despite clipping."""
    out = STRAW * ((1 + 0.5 * np.clip(_detail(a) - 1, -0.5, 0.5)) * _weave())[..., None]
    for _ in range(3):
        out = np.clip(out * (STRAW / out.mean((0, 1))), 0.0, 1.0)
    return out.astype(np.float32)


def _basket_n(a):
    """Source normal + weave slopes (peak 0.3) on XY, renormalised, re-encoded."""
    gy, gx = np.gradient(_weave())
    k = 0.3 / max(np.abs(gx).max(), np.abs(gy).max())
    n = a * 2 - 1
    n[..., 0] -= gx * k                      # tangent space, +Y up: n = (-dh/du, -dh/dv, 1)
    n[..., 1] -= gy * k
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    return (n * 0.5 + 0.5).astype(np.float32)


def _junction_bc(a):
    """Clean white plastic #E8E6DE with faint shading from the source luminance, no rust colour."""
    return np.clip(WHITE * (0.88 + 0.12 * np.clip(_detail(a), 0, 1.5) - 0.06)[..., None], 0, 1).astype(np.float32)


def _desat(a):
    """HSV saturation x 0.6, hue and value unchanged (each channel moves 40 % of the way to the pixel's max)."""
    mx = a.max(-1, keepdims=True)
    return mx - 0.6 * (mx - a)


def _newsprint(a):
    """HSV saturation x 0.3: Tripo baked the newspaper stack deep orange; the Flux images show grey-yellow newsprint."""
    mx = a.max(-1, keepdims=True)
    return mx - 0.3 * (mx - a)


def _const(v):
    return lambda a: np.full_like(a, v)


RETOUCH = {"Basket_Rattan": {"BC": _basket_bc, "N": _basket_n, "R": _const(0.75), "M": _const(0.0)},
           "JunctionBox": {"BC": _junction_bc, "R": _const(0.45), "M": _const(0.0)},
           "Meter_kWh": {"BC": _desat}, "MeterBox_B": {"BC": _desat}, "NewspaperStack": {"BC": _newsprint}}


def _cell(px, base=None, k=None):
    """One full 1024 px cell from px (h, w, 3): resampled to INNER px, RETOUCH[base][k] applied, edges extended PAD px."""
    iy, wy = _taps(INNER, px.shape[0])
    ix, wx = _taps(INNER, px.shape[1])
    out = sum(px[iy[:, t]] * wy[:, t, None, None] for t in range(iy.shape[1]))          # rows
    out = np.clip(sum(out[:, ix[:, t]] * wx[None, :, t, None] for t in range(ix.shape[1])), 0.0, 1.0)   # columns
    fix = RETOUCH.get(base, {}).get(k)
    if fix:
        out = np.clip(fix(out), 0.0, 1.0)
    return np.pad(out, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")


def _save(path, rgb):
    """8-bit RGB PNG of rgb (h, w, 3), rows bottom-up as Blender stores pixels."""
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("TMP_PropsAtlasSave", w, h, alpha=False)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)
    if not os.path.exists(path):
        raise OSError(f"props atlas: could not write {path}")


def _keep(img, base, k, src_dir):
    """Write img's source file (packed bytes, else its file) to src_dir/<base>/T_<base>_<k>.<ext>, never over a
    different file (that one gets a hash suffix). Returns (path, 'written' | 'same')."""
    if img.packed_file:
        data = bytes(img.packed_file.data)
    else:
        p = bpy.path.abspath(img.filepath)
        if not os.path.isfile(p):
            raise RuntimeError(f"props atlas: {img.name} is neither packed nor on disk ({p}); nothing changed")
        with open(p, "rb") as fh:
            data = fh.read()
    ext = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else \
        "." + img.file_format.lower()
    d = os.path.join(src_dir, base)
    os.makedirs(d, exist_ok=True)
    read = lambda p: open(p, "rb").read() if os.path.exists(p) else None
    path = os.path.join(d, f"T_{base}_{k}{ext}")
    if read(path) not in (None, data):
        path = os.path.join(d, f"T_{base}_{k}_{hashlib.sha1(data).hexdigest()[:8]}{ext}")
    if read(path) == data:
        return path, "same"
    with open(path, "wb") as fh:
        fh.write(data)
    if read(path) != data:
        raise OSError(f"props atlas: {path} did not read back identical; nothing changed")
    return path, "written"


def _find_src(root, base, k):
    """(path, others): textures/tripo_src/<base>/T_<base>_<k>.<ext> by exactly that name (None when absent), and
    the other variants next to it (hash-suffixed from a clash in _keep, or a second extension)."""
    d = os.path.join(root, *SRC_REL, base)
    names = sorted(os.listdir(d)) if os.path.isdir(d) else []
    exact = [n for n in names if os.path.splitext(n)[0] == f"T_{base}_{k}"]
    hashed = [n for n in names if re.fullmatch(rf"T_{re.escape(base)}_{k}_[0-9a-f]{{8}}\.\w+", n)]
    return (os.path.join(d, exact[0]) if exact else None), exact[1:] + hashed


def _layout(root):
    p = os.path.join(root, *OUT_REL, LAYOUT)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _rel(root, p):
    return os.path.relpath(p, root).replace("\\", "/")


def build(root=None):
    """Build the atlas, or extend it with the props that arrived since, and move the Tripo props onto M_Props_Atlas.
    Idempotent: a no-op when nothing is pending. Returns a report dict."""
    root = _root(root)
    meshes = {b: bpy.data.meshes.get("SM_" + b) for b in BASES}
    done = [b for b, me in meshes.items() if me is not None and me.get(TAG) is not None]
    atlas_mat = bpy.data.materials.get(MAT) if done else None
    cur = {k: bpy.data.images.get(f"T_Props_Atlas_{k}") for k in MAPS}
    tsig, old_h = None, 0
    if done:                                 # extending: the atlas material is the reference, the old sheets stay
        roles = _roles(atlas_mat)
        sizes = {tuple(im.size) if im is not None else None for im in cur.values()}
        bad = [b for b in done if len(meshes[b].get(TAG + "_uv", ())) != 4 or "UVMap" not in meshes[b].uv_layers]
        if isinstance(roles, str) or bad or len(sizes) != 1 or None in sizes:
            raise RuntimeError(f"props atlas: cannot extend: {MAT} {roles if isinstance(roles, str) else 'ok'}, "
                               f"meshes without {TAG}_uv/UVMap {bad}, T_Props_Atlas_* sizes {sizes}; nothing changed")
        ow, old_h = sizes.pop()
        if ow != W or old_h % CELL or not old_h:
            raise RuntimeError(f"props atlas: cannot extend a {ow} x {old_h} sheet; nothing changed")
        tsig = _sig(atlas_mat)

    rep = dict(noop=False, atlased=list(done), added=[], remapped=[], skipped={}, absent=[], folded={}, sources={},
               files=[], removed=[], kept=[])
    todo = []
    for i, b in enumerate(BASES):
        if b in done:
            continue
        me, mat = meshes[b], bpy.data.materials.get("M_" + b)
        if me is None and mat is None:       # not imported yet
            rep["absent"].append(b)
            continue
        why, roles, uv = None, None, None
        if me is None or mat is None:
            why = "no mesh SM_ or material M_"
        elif list(me.materials) != [mat]:
            why = f"material slots {[m.name if m else None for m in me.materials]}"
        elif [lay.name for lay in me.uv_layers] != ["UVMap"]:
            why = f"UV layers {[lay.name for lay in me.uv_layers]}"
        else:
            others = [m.name for m in bpy.data.meshes if m != me and any(x == mat for x in m.materials)]
            others += [o.name for o in bpy.data.objects if o.data != me and any(s.material == mat for s in o.material_slots)]
            roles = _roles(mat)
            if others:
                why = f"material also used by {', '.join(others[:4])}"
            elif isinstance(roles, str):
                why = "not the Tripo graph: " + roles
            else:
                sig = _sig(mat)
                tsig = tsig or sig
                diff = sorted(k for k in set(sig) | set(tsig) if sig.get(k) != tsig.get(k))
                if diff:
                    why = "settings differ from the " + ("atlas" if done else "first prop") + ": " + ", ".join(diff[:6])
        if why is None:
            raw = _uvs(me)
            uv, n = _fold(me, raw)
            lo, hi = raw.min(0).round(4).tolist(), raw.max(0).round(4).tolist()
            if uv is None:
                why = f"UVs {lo}..{hi}: {n} faces span a tile edge (an atlas cell cannot repeat)"
            else:
                if n:
                    rep["folded"][b] = n
                print(f"   UV check SM_{b}: {lo}..{hi}" + (f", {n} faces moved by whole tiles into [0, 1]" if n else " ok"))
        if why:
            rep["skipped"][b] = why
            print(f"   SKIP SM_{b}: {why}")
            continue
        todo.append((i, b, me, mat, roles, uv))
    if not todo:
        if done:
            print(f"== props atlas: {len(done)} props already on {MAT}; nothing pending" +
                  (f" (not atlased: {rep['skipped']})" if rep["skipped"] else ""))
            rep.update(noop=True, pending=list(rep["skipped"]))
        else:
            print("== props atlas: no prop to atlas")
        return rep

    rows = rows_for(max([BASES.index(b) for b in done] + [t[0] for t in todo]) + 1)
    H = rows * CELL
    if old_h > H:
        raise RuntimeError(f"props atlas: the sheet is {old_h} px high, more than {H} for these props; nothing changed")

    # files first (no scene change yet): sources kept on disk, then the four atlas sheets one map at a time
    src_dir, out_dir = os.path.join(root, *SRC_REL), os.path.join(root, *OUT_REL)
    for i, b, me, mat, roles, uv in todo:
        for k, n in sorted(roles.items()):
            rep["sources"][n.image.name] = _keep(n.image, b, k, src_dir)
    os.makedirs(out_dir, exist_ok=True)
    for k, (cs, fill) in MAPS.items():
        atlas = np.empty((H, W, 3), np.float32)
        atlas[:] = fill
        if done:                             # the old sheet verbatim, at the same px from the top-left
            old = _pixels(cur[k])
            atlas[H - old_h:] = old
            del old
        for i, b, me, mat, roles, uv in todo:
            x, y = cell_xy(i, rows)
            atlas[y - PAD:y - PAD + CELL, x - PAD:x - PAD + CELL] = _cell(_pixels(roles[k].image), b, k)
        rep["files"].append(os.path.join(out_dir, f"T_Props_Atlas_{k}.png"))
        _save(rep["files"][-1], atlas)
        del atlas

    # scene: atlas images, the material (a copy of the first prop's), UVs, slots, tags
    for (k, (cs, fill)), path in zip(MAPS.items(), rep["files"]):
        img = cur[k]
        if img is None:
            img = bpy.data.images.load(path, check_existing=False)
            img.name = f"T_Props_Atlas_{k}"
        else:
            img.filepath = path
            img.reload()
        img.colorspace_settings.name = cs
        cur[k] = img
    if not done:
        if bpy.data.materials.get(MAT):      # left by an interrupted run (no mesh is tagged)
            bpy.data.materials.remove(bpy.data.materials[MAT])
        atlas_mat = todo[0][3].copy()
        atlas_mat.name = MAT
        for k, n in _roles(atlas_mat).items():
            n.image = cur[k]
    su, sv = INNER / W, INNER / H
    old_props = _layout(root).get("props", {})
    olds, layout = {}, {}

    def entry(i, folded, src):
        x, y = cell_xy(i, rows)
        return dict(cell=i, x=x, y=H - y - INNER, size=INNER, scale=[su, sv], offset=[x / W, y / H],
                    uv=[x / W, y / H, x / W + su, y / H + sv], faces_folded=folded, src=src)

    for b in done:                           # already atlased: new transform when the height changed
        me, i = meshes[b], meshes[b][TAG]
        x, y = cell_xy(i, rows)
        tag = [su, sv, x / W, y / H]
        was = np.array(list(me[TAG + "_uv"]), np.float64)
        if not np.allclose(was, tag, rtol=0, atol=1e-9):
            new = (_uvs(me) - was[2:]) / was[:2] * [su, sv] + tag[2:]       # uv_tripo, then the new transform
            me.uv_layers["UVMap"].data.foreach_set("uv", new.astype(np.float32).ravel())
            me[TAG + "_uv"] = tag
            me.update()
            rep["remapped"].append(b)
        prev = old_props.get(b, {})
        src = prev.get("src")
        if not src:                          # recorded earlier? else the exact file names, when unambiguous
            found = {k: _find_src(root, b, k) for k in MAPS}
            src = {k: _rel(root, p) for k, (p, other) in found.items() if p and not other}
        layout[b] = entry(i, prev.get("faces_folded", 0), src)
    for i, b, me, mat, roles, uv in todo:
        x, y = cell_xy(i, rows)
        new = uv * [su, sv] + np.array([x / W, y / H])
        me.uv_layers["UVMap"].data.foreach_set("uv", new.astype(np.float32).ravel())
        me.materials[0] = atlas_mat
        me[TAG] = i
        me[TAG + "_uv"] = [su, sv, x / W, y / H]      # uv_atlas = uv_tripo * scale + offset, (u, v)
        me.update()
        olds[mat] = [n.image for n in roles.values()]
        rep["added"].append(b)
        layout[b] = entry(i, rep["folded"].get(b, 0), {k: _rel(root, rep["sources"][roles[k].image.name][0]) for k in roles})
    rep["atlased"] = done + rep["added"]
    for o in bpy.data.objects:               # object-linked slots on linked duplicates
        for sl in o.material_slots:
            if sl.link == "OBJECT" and sl.material in olds:
                sl.material = atlas_mat
    for mat, images in olds.items():
        if mat.users - mat.use_fake_user:
            rep["kept"].append(mat.name)
            continue
        rep["removed"].append(mat.name)
        bpy.data.materials.remove(mat)
        for img in images:
            if img.users - img.use_fake_user:
                rep["kept"].append(img.name)
            else:
                rep["removed"].append(img.name)
                bpy.data.images.remove(img)
    doc = dict(width=W, height=H, rows=rows, grid=GRID, cell=CELL, pad=PAD, material=MAT,
               files=[os.path.basename(p) for p in rep["files"]],
               note="cell i: column i % 4, row i // 4 from the top-left; x, y: content top-left in px from the atlas "
                    "top-left; uv_atlas = uv_tripo * scale + offset, scale = [u, v]; uv: u0 v0 u1 v1; src: source "
                    "files per map, relative to the project root (textures/tripo_src)",
               props=layout, skipped=rep["skipped"])
    with open(os.path.join(out_dir, LAYOUT), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)

    n_mat = sum(1 for x in rep["removed"] if x.startswith("M_"))
    states = [v[1] for v in rep["sources"].values()]
    print(f"== props atlas: {'+' if done else ''}{len(rep['added'])} props -> {MAT}, {len(rep['atlased'])} in all "
          f"({W} x {H} px, {GRID} x {rows} cells of {CELL} px, {INNER} px + {PAD} px gutter) in {out_dir}")
    print(f"   materials: -{n_mat} +{0 if done else 1} (net {(0 if done else 1) - n_mat:+d}); images removed: "
          f"{len(rep['removed']) - n_mat}; sources in {src_dir}: {states.count('written')} written, "
          f"{states.count('same')} already there")
    rt = [f"{b} {'/'.join(RETOUCH[b])}" for b in rep["added"] if b in RETOUCH]
    if rt:
        print(f"   retouched while building: {', '.join(rt)}")
    if rep["remapped"]:
        print(f"   UVs re-mapped to the {W} x {H} sheet: {', '.join(rep['remapped'])}")
    for p in rep["files"]:
        print(f"   {os.path.basename(p)}: {os.path.getsize(p) / 1e6:.1f} MB")
    for k in ("skipped", "folded", "kept"):
        if rep[k]:
            print(f"   {k}: {rep[k]}")
    return rep


def retouch(root=None, out_dir=None):
    """Apply RETOUCH to the atlased props' cells in the current atlas, rebuilt from their source files (the
    layout's src, else textures/tripo_src/<base>/T_<base>_<k>.<ext> by exact name). A map is written only when
    its 8-bit pixels change (else a rerun writes nothing); written maps are saved to out_dir (default
    textures/props_atlas) and the scene images are pointed at them and reloaded. Returns a report dict."""
    root = _root(root)
    out_dir = out_dir or os.path.join(root, *OUT_REL)
    rep = dict(changed={}, files=[], skipped={})
    meshes = {b: bpy.data.meshes.get("SM_" + b) for b in RETOUCH}
    bases = [b for b, me in meshes.items() if me is not None and me.get(TAG) is not None]
    rep["skipped"] = {b: "not on the atlas" for b in RETOUCH if b not in bases}
    if not bases:
        print(f"== props atlas retouch: none of {', '.join(RETOUCH)} is atlased")
        return rep
    cur = {k: bpy.data.images.get(f"T_Props_Atlas_{k}") for k in MAPS}
    sizes = {tuple(im.size) if im is not None else None for im in cur.values()}
    if len(sizes) != 1 or None in sizes:
        raise RuntimeError(f"props atlas: T_Props_Atlas_* missing or of different sizes ({sizes}); nothing changed")
    (w, h), = sizes
    if w != W or h % CELL:
        raise RuntimeError(f"props atlas: cannot retouch a {w} x {h} sheet; nothing changed")
    rows, props = h // CELL, _layout(root).get("props", {})
    srcs = {}                                # every source resolved before anything is written
    for b in bases:
        for k in RETOUCH[b]:
            p = os.path.join(root, props.get(b, {}).get("src", {}).get(k, ""))
            if not os.path.isfile(p):
                p, other = _find_src(root, b, k)
                if p is None:
                    raise RuntimeError(f"props atlas: no source file T_{b}_{k}.* in {os.path.join(root, *SRC_REL, b)}; nothing changed")
                if other:
                    print(f"   WARN {b} {k}: {other} next to the exact name; using {os.path.basename(p)}")
            srcs[b, k] = p
    q = lambda a: np.floor(a * 255 + 0.5)    # float -> 8-bit the way Blender stores it
    for k in MAPS:
        path = os.path.join(out_dir, f"T_Props_Atlas_{k}.png")
        todo = [b for b in bases if k in RETOUCH[b]]
        atlas, changed = _pixels(cur[k]), []
        for b in todo:
            x, y = cell_xy(meshes[b][TAG], rows)
            sl = (slice(y - PAD, y - PAD + CELL), slice(x - PAD, x - PAD + CELL))
            new = _cell(_file_px(srcs[b, k]), b, k)
            d = np.abs(q(new) - q(atlas[sl]))
            if d.any():
                atlas[sl] = new
                changed.append(b)
                rep["changed"].setdefault(b, []).append(k)
                print(f"   retouch {b} {k}: cell {meshes[b][TAG]}, {int((d > 0).any(-1).sum())} px changed, mean {d.mean():.2f} levels")
        if changed or not os.path.isfile(path):
            os.makedirs(out_dir, exist_ok=True)
            _save(path, atlas)
            cur[k].filepath = path
            cur[k].reload()
            rep["files"].append(path)
        del atlas
    print(f"== props atlas retouch: {sum(map(len, rep['changed'].values()))} cell maps changed in {len(rep['files'])} "
          f"files ({W} x {h} px)" + ("" if rep["files"] else "; nothing to write"))
    return rep
