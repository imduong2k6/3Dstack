"""Headless test for props_atlas.py.

    "Z:/SteamLibrary/steamapps/common/Blender/blender.exe" -b --factory-startup [<copy>.blend] --python-exit-code 1 \
        --python .claude/skills/tripo-props/scripts/tests/test_props_atlas.py -- [out_dir]

No .blend (factory scene): 15 Tripo-like fixture props (UV spheres, four packed 1K maps each, the Tripo node
graph, a linked duplicate each) plus traps: SM_Sack with faces one tile off (moved back), SM_CartLoad with a face
across the tile edge and SM_GasCylinder without its Normal Map (both skipped, left alone), SM_Meter_kWh with
512 px maps, an object-linked slot on a JunctionBox duplicate, a plain mesh, an identical and a different file
already in tripo_src. Then the four newest props (Misc_*) arrive and build() extends the atlas 4096 x 4096 ->
4096 x 8192. Writes under <out_dir>/textures, never the project's.
With a .blend (a COPY of a project file; refused inside the project folder): its real props, and it writes the
real textures/props_atlas and textures/tripo_src files. Never saves the .blend. Only the first build is run
there (a built atlas makes it a no-op or an extend with the props that are pending in the copy).
Checks, after every build: atlased and skipped as expected, PNG size W x rows * 1024, gutters = edge extension,
UVs = Tripo UVs * scale + cell offset (no rotation), the atlas sampled through the new UVs matches the source
through the old ones (not for the RETOUCH pairs: basket straw + weave, junction box white, meters desaturated are
checked on their own), M_Props_Atlas wired and set like the Tripo graph, every slot (duplicates too) on it, old
materials and images gone, every source file byte-identical in tripo_src. Extend: the 15 old cells are
byte-identical by position from the top-left, the old UVs follow the new height, layout json has width, height and
src. Then a third build is a no-op (datablocks, UVs, file times), retouch() is a no-op, and a changed RETOUCH entry
is applied by retouch() to that map only (src from the layout, and from the exact file name) and undone again.
Renders SM_Handcart and SM_AC_Split (EEVEE, own scene) before the first and after the last build, prints pixel
differences, writes props_atlas_<prop>_compare.png (before | after | difference x 8) to out_dir.
Exits non-zero on any failed check.
"""
import colorsys
import json
import math
import os
import shutil
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))   # the tripo-props skill folder
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.join(os.environ.get("TEMP", "."), "props_atlas_test")
os.makedirs(OUT, exist_ok=True)
REAL = bool(bpy.data.filepath)
if REAL and os.path.normcase(os.path.abspath(bpy.data.filepath)).startswith(os.path.normcase(ROOT + os.sep)):
    print("REFUSED: run on a copy outside the project folder, never on", bpy.data.filepath)
    raise SystemExit(1)
fails = []
T0 = time.time()


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL:", msg)


def load(rel):
    path = os.path.join(ROOT, *rel.split("/"))
    ns = {"__name__": os.path.basename(rel)[:-3]}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)   # the way the lead runs it
    return ns


def png(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)                     # row 0 = bottom


def png8(path):
    """(h, w, 3) uint8, row 0 = bottom; in row chunks so a 4096 x 8192 sheet does not need a second float copy."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)
    out = np.empty((h, w, 3), np.uint8)
    for y in range(0, h, 512):
        out[y:y + 512] = np.floor(px[y:y + 512, :, :3] * 255 + 0.5)
    return out


def uvs(me):
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", a)
    return a.reshape(-1, 2).astype(np.float64)


def bilinear(img, uv):
    """img (h, w, c) bottom-up, uv (n, 2) -> (n, c), edges clamped."""
    h, w = img.shape[:2]
    x, y = np.clip(uv[:, 0] * w - 0.5, 0, w - 1), np.clip(uv[:, 1] * h - 0.5, 0, h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) +
            img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


GEO = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME"}


def n_mats(scene):
    """Materials on export geometry, as scripts/export/validate.py counts them (all but 00_Ref and UCX_)."""
    ref = bpy.data.collections.get("00_Ref")
    refobs = set(ref.all_objects) if ref else set()
    return len({s.material for o in scene.objects if o.type in GEO and o not in refobs
                and not o.name.startswith("UCX_") for s in o.material_slots if s.material})


PA = load("scripts/props_atlas.py")
BASES, W, CELL, PAD, INNER, MAT, TAG = (PA[k] for k in ("BASES", "W", "CELL", "PAD", "INNER", "MAT", "TAG"))
OLD, NEW = BASES[:15], BASES[15:]
RT = {(b, k) for b, m in PA["RETOUCH"].items() for k in m}       # the retouched (base, map) pairs
STRAW, WHITE = (0xB4, 0x9A, 0x62), (0xE8, 0xE6, 0xDE)
scene = bpy.context.scene
want_uv, src, packed, uv_before = {}, {}, {}, {}
tsig = None


# ------------------------------------------------------------------ fixture (factory scene only)
def tripo_mat(name, imgs, normal=True):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out, bsdf = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    socks = {"BC": bsdf.inputs["Base Color"], "R": bsdf.inputs["Roughness"], "M": bsdf.inputs["Metallic"]}
    if normal:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        socks["N"] = nm.inputs["Color"]
    for k, img in imgs.items():
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        if k in socks:
            nt.links.new(t.outputs["Color"], socks[k])
    return mat


def make_props(names):
    masters, dress = bpy.data.collections["03_Props_Masters"], bpy.data.collections["04_Dressing"]
    for b in names:
        i = BASES.index(b)
        n = 512 if b == "Meter_kWh" else 1024
        v, u = (np.mgrid[0:n, 0:n] + 0.5) / n
        wave = 0.5 + 0.5 * np.sin(2 * np.pi * (3 * u + 2 * v + i / 5))
        maps = {"BC": np.array(colorsys.hsv_to_rgb(i / 15, 0.6, 0.8)) * (0.55 + 0.45 * wave)[..., None],
                "N": np.stack([0.5 + 0.15 * np.sin(2 * np.pi * 4 * u), 0.5 + 0.15 * np.cos(2 * np.pi * 3 * v),
                               np.ones_like(u)], -1),
                "R": np.repeat((0.2 + 0.6 * u * wave)[..., None], 3, 2),
                "M": np.repeat((0.5 + 0.5 * np.sin(2 * np.pi * (v + i / 15)))[..., None], 3, 2)}
        imgs = {}
        for k, a in maps.items():
            img = bpy.data.images.new(f"T_{b}_{k}", n, n, alpha=False)
            img.colorspace_settings.name = PA["MAPS"][k][0]
            px = np.ones((n, n, 4), np.float32)
            px[..., :3] = a
            img.pixels.foreach_set(px.ravel())
            img.pack()
            imgs[k] = img
        mat = tripo_mat("M_" + b, imgs, normal=b != "GasCylinder")
        bm = bmesh.new()
        bm.loops.layers.uv.new("UVMap")
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.3, calc_uvs=True)
        me = bpy.data.meshes.new("SM_" + b)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        want_uv[b] = uvs(me)
        lay = me.uv_layers["UVMap"].data
        if b == "Sack":         # faces on the left half one tile to the right: same texels under REPEAT
            for p in me.polygons:
                if np.mean([want_uv[b][li, 0] for li in p.loop_indices]) < 0.5:
                    for li in p.loop_indices:
                        lay[li].uv = (want_uv[b][li, 0] + 1.0, want_uv[b][li, 1])
        if b == "CartLoad":     # one face across u = 1: an atlas cell cannot repeat it
            for j, li in enumerate(me.polygons[30].loop_indices):
                lay[li].uv = (0.95 + 0.1 * j, 0.5 + 0.02 * j)
        ob = bpy.data.objects.new("SM_" + b, me)
        masters.objects.link(ob)
        dup = bpy.data.objects.new(f"SM_{b}_F_001", me)
        dup.location = (i * 0.8, 0, 0)
        dress.objects.link(dup)
        if b == "JunctionBox":
            dup.material_slots[0].link = "OBJECT"
            dup.material_slots[0].material = mat


def fixture():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    masters, dress = bpy.data.collections.new("03_Props_Masters"), bpy.data.collections.new("04_Dressing")
    scene.collection.children.link(masters)
    scene.collection.children.link(dress)
    bpy.context.view_layer.layer_collection.children["03_Props_Masters"].exclude = True
    make_props(OLD)
    pm = bpy.data.meshes.new("TEST_Plain")
    pm.from_pydata([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [], [(0, 1, 2, 3)])
    pm.uv_layers.new(name="UVMap")
    pm.materials.append(bpy.data.materials.new("TEST_Mat"))
    dress.objects.link(bpy.data.objects.new("TEST_Plain", pm))
    tex = os.path.join(OUT, "textures")
    if os.path.isdir(tex):
        shutil.rmtree(tex)
    d = os.path.join(tex, "tripo_src", "AC_Split")
    os.makedirs(d)
    with open(os.path.join(d, "T_AC_Split_BC.png"), "wb") as fh:      # identical: must be left as "same"
        fh.write(bytes(bpy.data.images["T_AC_Split_BC"].packed_file.data))
    with open(os.path.join(d, "T_AC_Split_N.png"), "wb") as fh:       # different: must not be overwritten
        fh.write(b"not the normal map")


if not REAL:
    fixture()
root = OUT   # never the project's textures
expect_skip = {} if REAL else {"CartLoad": "span a tile edge", "GasCylinder": "not the Tripo graph"}
print(f"mode: {'COPY ' + bpy.data.filepath if REAL else 'fixture (factory scene)'}; writes under {root}")


def snap(names):
    """The look of each prop before it is atlased: UVs, source bytes, 8-bit BC and N."""
    global tsig
    for b in names:
        me, mat = bpy.data.meshes.get("SM_" + b), bpy.data.materials.get("M_" + b)
        roles = PA["_roles"](mat) if mat else "missing"
        if me is None or isinstance(roles, str):
            continue
        want_uv.setdefault(b, uvs(me))
        tsig = tsig or PA["_sig"](mat)
        packed[b] = {k: bytes(n.image.packed_file.data) for k, n in roles.items() if n.image.packed_file}
        src[b] = {k: np.round(PA["_pixels"](roles[k].image) * 255).astype(np.uint8) for k in ("BC", "N")}
    uv_before.update({b: uvs(bpy.data.meshes["SM_" + b]) for b in names if bpy.data.meshes.get("SM_" + b)})


snap(BASES)
mats_before = n_mats(scene)
plain_before = uvs(bpy.data.meshes["TEST_Plain"]) if not REAL else None
present = {b for b in BASES if bpy.data.meshes.get("SM_" + b) or bpy.data.materials.get("M_" + b)}

RENDER = ["SM_Handcart", "SM_AC_Split"]          # not retouched: their look must survive the atlas and the extend


def render(tag):
    sc = bpy.data.scenes.get("TEST_Render")
    if sc is None:
        sc = bpy.data.scenes.new("TEST_Render")
        for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try:
                sc.render.engine = eng
                break
            except TypeError:
                continue
        sc.render.resolution_x = sc.render.resolution_y = 640
        sc.render.resolution_percentage = 100
        sc.render.film_transparent = True
        try:
            sc.render.image_settings.media_type = "IMAGE"     # 5.2: set before a PNG file_format
        except (AttributeError, TypeError):
            pass
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        sc.view_settings.view_transform = "Standard"
        sc.eevee.taa_render_samples = 32
        sc.world = bpy.data.worlds.new("TEST_World")
        try:
            sc.world.use_nodes = True
        except AttributeError:
            pass
        bg = next((n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND"), None) if sc.world.node_tree else None
        if bg:
            bg.inputs["Color"].default_value, bg.inputs["Strength"].default_value = (0.3, 0.3, 0.32, 1), 1.0
        sun = bpy.data.objects.new("TEST_Sun", bpy.data.lights.new("TEST_Sun", "SUN"))
        sun.data.energy, sun.rotation_euler = 3.0, (math.radians(50), 0, math.radians(-35))
        sc.collection.objects.link(sun)
        cam = bpy.data.objects.new("TEST_Cam", bpy.data.cameras.new("TEST_Cam"))
        cam.data.clip_start = 0.01
        sc.collection.objects.link(cam)
        sc.camera = cam
        for n in RENDER:
            sc.collection.objects.link(bpy.data.objects.new("TEST_R_" + n, bpy.data.meshes[n]))
    out = {}
    for n in RENDER:
        for o in sc.collection.objects:
            if o.name.startswith("TEST_R_"):
                o.hide_render = o.name != "TEST_R_" + n
        me = bpy.data.meshes[n]
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(0), co.max(0)
        d = Vector((-0.55, -1.0, 0.45)).normalized()
        cam = sc.camera
        cam.location = Vector((lo + hi) / 2) + d * (np.linalg.norm(hi - lo) / 2 / math.tan(cam.data.angle / 2) * 1.1)
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, f"props_atlas_{n}_{tag}.png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        out[n] = png(sc.render.filepath)
    return out


def stats(a, b):
    m = (a[..., 3] > 0) | (b[..., 3] > 0)
    d = np.abs(a[..., :3] - b[..., :3]).mean(-1)[m] * 255
    mse = ((a[..., :3] - b[..., :3]) ** 2)[m].mean()
    return dict(px=int(m.sum()), mean=float(d.mean()), p99=float(np.percentile(d, 99)), max=float(d.max()),
                over8=float((d > 8).mean() * 100), psnr=float(10 * np.log10(1 / max(mse, 1e-12))))


fmt = lambda s: (f"{s['px']} px, mean {s['mean']:.2f}, p99 {s['p99']:.1f}, max {s['max']:.0f} (0-255 levels), "
                 f"{s['over8']:.2f} % px > 8 levels, PSNR {s['psnr']:.1f} dB")
before = render("before")
again = render("before_repeat")
for n in RENDER:
    print(f"noise floor {n} (before vs before): {fmt(stats(before[n], again[n]))}")


# ------------------------------------------------------------------ checks shared by every build
def hp(a):
    """Std of the 5-point Laplacian of the channel mean (8-bit levels): how much fine detail a cell has."""
    g = a.astype(np.float32).mean(-1)
    return float((4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]).std())


def sat_median(a):
    a = a.astype(np.float32) / 255
    mx, mn = a.max(-1), a.min(-1)
    ok = mx > 0.05
    return float(np.median((mx - mn)[ok] / mx[ok]))


def retouch_checks(b, k, cell):
    """cell: the INNER x INNER content of a RETOUCH pair, 8-bit."""
    m = cell.reshape(-1, 3).mean(0)
    if (b, k) == ("Basket_Rattan", "BC"):
        h1, h0 = hp(cell), hp(src[b]["BC"])
        sat = sat_median(cell)
        check(np.abs(m - STRAW).max() <= 12, f"{b} BC mean {m.round(1)} not within 12 of #B49A62")
        check(h1 > 3 * h0 and h1 > 5, f"{b} BC weave not visible: high-pass std {h1:.1f} vs source {h0:.1f}")
        check(sat < 0.55, f"{b} BC saturation {sat:.2f} is not straw")
        print(f"   {b} BC: mean {m.round(1)} (straw {STRAW}), weave high-pass std {h1:.1f} (source {h0:.1f}), sat {sat:.2f}")
    elif (b, k) == ("Basket_Rattan", "N"):
        h1, h0 = hp(cell), hp(src[b]["N"])
        check(h1 > 3 * h0 and h1 > 2, f"{b} N weave not visible: high-pass std {h1:.1f} vs source {h0:.1f}")
        print(f"   {b} N: high-pass std {h1:.1f} (source {h0:.1f})")
    elif b == "Basket_Rattan":                          # R = 0.75, M = 0
        want = round(0.75 * 255) if k == "R" else 0
        check(np.abs(cell.astype(int) - want).max() <= 1, f"{b} {k} not constant {want}: {cell.min()}..{cell.max()}")
    elif (b, k) == ("JunctionBox", "BC"):
        L = src[b]["BC"].astype(np.float32) @ PA["LUM"]
        want = np.array(WHITE) * (0.82 + 0.12 * np.clip(L / np.median(L), 0, 1.5)).mean()      # the formula's own mean
        check(np.abs(m - want).max() <= 4 and np.abs(m - WHITE).max() <= 16, f"{b} BC mean {m.round(1)}, formula {want.round(1)}")
        print(f"   {b} BC: mean {m.round(1)}; #E8E6DE x formula mean = {want.round(1)}; vs #E8E6DE {(m - WHITE).round(1)}")
    elif b == "JunctionBox":
        want = 0.45 * 255 if k == "R" else 0
        check(abs(m - want).max() <= 1.5 and cell.std() < 1, f"{b} {k} not constant {want:.1f}: {m.round(1)}")
    elif (b, k) == ("NewspaperStack", "BC"):            # newsprint: saturation x 0.3
        r = sat_median(cell) / sat_median(src[b]["BC"])
        check(0.25 <= r <= 0.35, f"{b} BC median saturation x{r:.3f}, want ~0.3")
        print(f"   {b} BC: median saturation x{r:.3f} of the source")
    elif k == "BC":                                     # the meters: saturation x 0.6
        r = sat_median(cell) / sat_median(src[b]["BC"])
        check(0.55 <= r <= 0.65, f"{b} BC median saturation x{r:.3f}, want ~0.6")
        print(f"   {b} BC: median saturation x{r:.3f} of the source")


def verify(done, H, hook=None):
    """Everything about the sheets, UVs, material, slots and removals after a build; done = atlased bases."""
    rows, s = H // CELL, np.array([INNER / W, INNER / H])
    files = {k: os.path.join(root, "textures", "props_atlas", f"T_Props_Atlas_{k}.png") for k in PA["MAPS"]}
    for k, p in files.items():
        if not os.path.exists(p):
            check(False, f"{p} missing")
            continue
        px = png8(p)
        check(px.shape[:2] == (H, W), f"{k}: {px.shape[:2]}, want {(H, W)}")
        print(f"T_Props_Atlas_{k}.png: {px.shape[1]} x {px.shape[0]}, {os.path.getsize(p) / 1e6:.1f} MB")
        for b in sorted(done):
            x, y = PA["cell_xy"](BASES.index(b), rows)
            X0, X1, Y1 = x - PAD, x + INNER + PAD, y + INNER
            ok = ((px[y:Y1, X0:x] == px[y:Y1, x:x + 1]).all() and (px[y:Y1, x + INNER:X1] == px[y:Y1, x + INNER - 1:x + INNER]).all()
                  and (px[y - PAD:y, X0:X1] == px[y:y + 1, X0:X1]).all() and (px[Y1:Y1 + PAD, X0:X1] == px[Y1 - 1:Y1, X0:X1]).all())
            check(ok, f"{b} {k}: gutter is not the edge extended {PAD} px")
            if b not in src:  # a cell from an earlier build has no source here (extend is byte-checked in build 2)
                pass
            elif (b, k) in RT:
                retouch_checks(b, k, px[y:Y1, x:x + INNER])
            elif k in ("BC", "N"):
                rng = np.random.default_rng(BASES.index(b))
                me = bpy.data.meshes["SM_" + b]
                pick = rng.choice(len(me.loops), min(4000, len(me.loops)), replace=False)
                a = bilinear(src[b][k] / 255.0, want_uv[b][pick])
                uv = uvs(me)[pick] * [W, H]
                cx, cy = x - PAD, y - PAD
                crop = lambda dx: px[cy:cy + CELL, cx + dx:cx + dx + CELL] / 255.0       # the cell, or its neighbour
                e = np.abs(a - bilinear(crop(0), (uv - [cx, cy]) / CELL)).mean()
                wrong = np.abs(a - bilinear(crop(CELL if cx < 3 * CELL else -CELL), (uv - [cx, cy]) / CELL)).mean()
                check(e < (0.03 if REAL else 0.004), f"{b} {k}: atlas through new UVs vs source through old UVs off by {e:.4f}")
                print(f"   {b:19s} {k:2s}: sampled diff {e:.4f} (neighbour cell would be {wrong:.4f})")
        if hook:
            hook(k, px)
        del px

    # UVs, tags, material, slots, removals
    mat = bpy.data.materials.get(MAT)
    roles = PA["_roles"](mat) if mat else "missing"
    check(not isinstance(roles, str), f"{MAT}: {roles}")
    if not isinstance(roles, str):
        for k, n in roles.items():
            im = n.image
            check(im.name == f"T_Props_Atlas_{k}" and tuple(im.size) == (W, H) and not im.packed_file
                  and os.path.normcase(bpy.path.abspath(im.filepath)) == os.path.normcase(files[k])
                  and im.colorspace_settings.name == PA["MAPS"][k][0],
                  f"{MAT} {k}: {im.name} {tuple(im.size)} {im.filepath} {im.colorspace_settings.name}")
        sig = PA["_sig"](mat)
        check(sig == tsig, f"{MAT} settings differ from the Tripo graph: {sorted(k for k in sig if sig[k] != tsig.get(k))}")
    for b in BASES:
        me = bpy.data.meshes.get("SM_" + b)
        if me is None:
            continue
        users = [o for o in bpy.data.objects if o.data == me]
        if b in done and b not in want_uv:  # atlased by an earlier build (REAL copy): no Tripo UVs to compare
            check(me.get(TAG) == BASES.index(b) and all(sl.material == mat for o in users for sl in o.material_slots),
                  f"{b}: earlier atlased prop lost its tag or slot")
        elif b in done:
            x, y = PA["cell_xy"](BASES.index(b), rows)
            err = np.abs(uvs(me) - (want_uv[b] * s + [x / W, y / H])).max()
            check(err < 2e-6, f"{b}: UVs not Tripo * {s} + cell offset (max error {err:.2e})")
            check(np.allclose(list(me[TAG + "_uv"]), [s[0], s[1], x / W, y / H], rtol=0, atol=1e-9), f"{b}: {TAG}_uv {list(me[TAG + '_uv'])}")
            check(me.get(TAG) == BASES.index(b), f"{b}: tag {me.get(TAG)}")
            check(all(sl.material == mat for o in users for sl in o.material_slots), f"{b}: a slot is not on {MAT}")
            check(bpy.data.materials.get("M_" + b) is None, f"M_{b} not removed")
            check(not [k for k in PA["MAPS"] if bpy.data.images.get(f"T_{b}_{k}")], f"T_{b}_* not removed")
            d = os.path.join(root, "textures", "tripo_src", b)
            on_disk = [open(os.path.join(d, f), "rb").read() for f in os.listdir(d)] if os.path.isdir(d) else []
            lost = [k for k, data in packed[b].items() if data not in on_disk]
            check(not lost and len(packed[b]) == 4, f"{b}: sources not kept byte-identical: {lost or 'not packed'}")
        else:
            check(np.array_equal(uvs(me), uv_before[b]) and me.materials[0].name == "M_" + b and me.get(TAG) is None,
                  f"{b}: skipped prop was changed")
    if not REAL:
        check(np.array_equal(uvs(bpy.data.meshes["TEST_Plain"]), plain_before) and
              bpy.data.meshes["TEST_Plain"].materials[0].name == "TEST_Mat", "plain mesh touched")
    # layout json: size, rows, every atlased prop with its cell, transform and source files
    lp = os.path.join(root, "textures", "props_atlas", PA["LAYOUT"])
    doc = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {}
    check(doc.get("width") == W and doc.get("height") == H and doc.get("rows") == rows, f"layout size {doc.get('width')} x {doc.get('height')}")
    check(set(doc.get("props", {})) == set(done), f"layout props {sorted(doc.get('props', {}))}")
    for b, e in doc.get("props", {}).items():
        x, y = PA["cell_xy"](BASES.index(b), rows)
        check(e["cell"] == BASES.index(b) and e["x"] == x and e["y"] == H - y - INNER and e["size"] == INNER
              and np.allclose(e["scale"], s, atol=1e-9) and np.allclose(e["offset"], [x / W, y / H], atol=1e-9)
              and np.allclose(e["uv"], [x / W, y / H, x / W + s[0], y / H + s[1]], atol=1e-9), f"layout {b}: {e}")
        files_ok = set(e.get("src", {})) == set(PA["MAPS"]) and all(os.path.isfile(os.path.join(root, p)) for p in e["src"].values())
        check(files_ok, f"layout {b}: src {e.get('src')}")
        if files_ok and b in packed:
            check(all(open(os.path.join(root, e["src"][k]), "rb").read() == data for k, data in packed[b].items()),
                  f"layout {b}: src files are not the original sources")
    return files


def check_report(r, present_now):
    done = set(r["atlased"])
    check(set(r["skipped"]) == present_now - done, f"skipped {sorted(r['skipped'])}, want {sorted(present_now - done)}")
    check(set(r["absent"]) == set(BASES) - present_now, f"absent {r['absent']}")
    for b, why in expect_skip.items():
        if b in present_now:
            check(why in r["skipped"].get(b, ""), f"{b}: skip reason {r['skipped'].get(b)!r}, want '{why}'")
    return done


# ------------------------------------------------------------------ build 1: the first 15 -> 4096 x 4096
prior = {b for b in BASES if bpy.data.meshes.get("SM_" + b) and any(m and m.name == MAT for m in bpy.data.meshes["SM_" + b].materials)}  # a copy whose atlas exists: build 1 extends it
r1 = PA["build"](root)
done1 = check_report(r1, present)
check(done1 - prior == set(packed) - set(expect_skip), f"atlased {sorted(done1 - prior)}, want {sorted(set(packed) - set(expect_skip))}")
check(set(r1["added"]) == done1 - prior, f"added {r1['added']}")
if not REAL:
    check(r1["folded"].get("Sack", 0) > 0 and set(r1["folded"]) == {"Sack"}, f"folded {r1['folded']}")
want = (0 if prior else 1) - len(done1 - prior)
check(n_mats(scene) - mats_before == want, f"materials {mats_before} -> {n_mats(scene)}, want {want:+d}")
print(f"materials on export geometry: {mats_before} -> {n_mats(scene)}")
H1 = PA["rows_for"](max(BASES.index(b) for b in done1) + 1) * CELL
check(REAL or H1 == 4096, f"first sheet height {H1}")
files = verify(done1, H1)
check(r1["files"] == list(files.values()), f"files {r1['files']}")
print(f"{len(done1)} props on {MAT}; {len(r1['removed'])} datablocks removed, kept {r1['kept']}; {time.time() - T0:.0f} s")
if not REAL:
    d = os.path.join(OUT, "textures", "tripo_src", "AC_Split")
    check(open(os.path.join(d, "T_AC_Split_N.png"), "rb").read() == b"not the normal map", "a different file was overwritten")
    check(r1["sources"]["T_AC_Split_BC"][1] == "same", f"identical file not reused: {r1['sources']['T_AC_Split_BC']}")
    check(os.path.basename(r1["sources"]["T_AC_Split_N"][0]).startswith("T_AC_Split_N_"), "clash not renamed")
    p, other = PA["_find_src"](root, "AC_Split", "N")
    check(os.path.basename(p) == "T_AC_Split_N.png" and len(other) == 1, f"_find_src exact name / variants: {p} {other}")
check(os.path.exists(os.path.join(root, "textures", "props_atlas", PA["LAYOUT"])), "layout json missing")

if not REAL:
    # ------------------------------------------------------------------ build 2: the Misc props arrive -> 4096 x 8192
    old8 = {k: png8(p) for k, p in files.items()}                    # the 4096 x 4096 sheets of build 1
    t_src = {p: os.stat(p).st_mtime_ns for p, _ in r1["sources"].values()}
    make_props(NEW)
    snap(NEW)
    mats2 = n_mats(scene)
    present2 = present | set(NEW)
    uv_old1 = {b: uvs(bpy.data.meshes["SM_" + b]) for b in done1}
    r2 = PA["build"](root)
    done2 = check_report(r2, present2)
    check(not r2["noop"] and set(r2["added"]) == set(NEW) and done2 == done1 | set(NEW), f"extend: added {r2['added']}, atlased {sorted(done2)}")
    check(sorted(r2["remapped"]) == sorted(done1), f"re-mapped {r2['remapped']}")
    check(n_mats(scene) - mats2 == -len(NEW), f"materials {mats2} -> {n_mats(scene)}, want {-len(NEW):+d}")
    check(all(os.stat(p).st_mtime_ns == t for p, t in t_src.items()), "extend rewrote old source files")
    H2 = PA["rows_for"](len(BASES)) * CELL
    check(H2 == 8192, f"second sheet height {H2}")

    def old_cells_same(k, px):
        for idx in range(15):                                        # by position from the top-left; unused cells too
            (x1, y1), (x2, y2) = PA["cell_xy"](idx, H1 // CELL), PA["cell_xy"](idx, H2 // CELL)
            check(np.array_equal(old8[k][y1 - PAD:y1 - PAD + CELL, x1 - PAD:x1 - PAD + CELL],
                                 px[y2 - PAD:y2 - PAD + CELL, x2 - PAD:x2 - PAD + CELL]),
                  f"{k}: old cell {idx} ({BASES[idx]}) changed in the extend")
        (x1, y1), (x2, y2) = PA["cell_xy"](15, H1 // CELL), PA["cell_xy"](15, H2 // CELL)      # the unused cell got a prop
        check(not np.array_equal(old8[k][y1 - PAD:y1 - PAD + CELL, x1 - PAD:x1 - PAD + CELL],
                                 px[y2 - PAD:y2 - PAD + CELL, x2 - PAD:x2 - PAD + CELL]), f"{k}: cell 15 still empty")

    files = verify(done2, H2, old_cells_same)
    check(r2["files"] == list(files.values()), f"files {r2['files']}")
    del old8
    for b in done1:
        me = bpy.data.meshes["SM_" + b]
        check(me.get(TAG) == BASES.index(b) and not np.array_equal(uvs(me), uv_old1[b]), f"{b}: UVs not re-mapped")
    print(f"extend: {len(r2['added'])} props added, {len(done2)} in all; {time.time() - T0:.0f} s")
else:
    done2, H2, r2 = done1, H1, r1

# ------------------------------------------------------------------ build 3: a no-op
counts = lambda: tuple(len(c) for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images,
                                        bpy.data.collections, bpy.data.scenes))
lay_path = os.path.join(root, "textures", "props_atlas", PA["LAYOUT"])
watch = list(files.values()) + [lay_path] + [p for r in (r1, r2) for p, _ in r["sources"].values()]
mt = lambda: {p: os.stat(p).st_mtime_ns for p in watch}
c1, u1, t1 = counts(), {b: uvs(bpy.data.meshes["SM_" + b]) for b in done2}, mt()
r3 = PA["build"](root)
check(r3["noop"] and set(r3["atlased"]) == done2, f"rerun not a no-op: {r3}")
check(counts() == c1, f"rerun changed datablock counts {c1} -> {counts()}")
check(all(np.array_equal(uvs(bpy.data.meshes["SM_" + b]), u1[b]) for b in done2), "rerun changed UVs")
check(mt() == t1, "rerun rewrote files")

# retouch() on a built atlas: a no-op; a changed table entry changes that map only; undone, a no-op again
rt = PA["retouch"](root)
check(not rt["changed"] and not rt["files"] and mt() == t1 and counts() == c1, f"retouch after build not a no-op: {rt}")
if not REAL:
    rtab, orig = PA["RETOUCH"]["Basket_Rattan"], PA["RETOUCH"]["Basket_Rattan"]["R"]
    cx, cy = PA["cell_xy"](BASES.index("Basket_Rattan"), H2 // CELL)
    pr = files["R"]
    rtab["R"] = PA["_const"](0.5)
    rt = PA["retouch"](root)
    t2 = mt()
    im = bpy.data.images["T_Props_Atlas_R"]
    check(rt["changed"] == {"Basket_Rattan": ["R"]} and rt["files"] == [pr], f"retouch changed {rt['changed']} {rt['files']}")
    check(all(t2[p] == t1[p] for p in t1 if p != pr) and t2[pr] != t1[pr], "retouch wrote more than the R map")
    check(tuple(im.size) == (W, H2) and os.path.normcase(bpy.path.abspath(im.filepath)) == os.path.normcase(pr), "retouch: R image not reloaded")
    c8 = png8(pr)[cy - PAD:cy - PAD + CELL, cx - PAD:cx - PAD + CELL]
    check((c8 == 128).all(), f"retouched R cell not 0.5: {c8.min()}..{c8.max()}")
    check(np.abs(np.array(PA["_pixels"](im)[cy:cy + INNER, cx:cx + INNER]) - 128 / 255).max() < 1e-3, "scene R image does not show the retouch")
    t1 = t2
    rt = PA["retouch"](root)
    check(not rt["changed"] and mt() == t1, f"second retouch not idempotent: {rt['changed']}")
    # undone, and from the exact file names (the layout without src)
    rtab["R"] = orig
    lay_text = open(lay_path, encoding="utf-8").read()
    doc = json.loads(lay_text)
    for e in doc["props"].values():
        e.pop("src")
    json.dump(doc, open(lay_path, "w", encoding="utf-8"))
    rt = PA["retouch"](root)
    open(lay_path, "w", encoding="utf-8").write(lay_text)
    c8 = png8(pr)[cy - PAD:cy - PAD + CELL, cx - PAD:cx - PAD + CELL]
    check(rt["changed"] == {"Basket_Rattan": ["R"]} and (c8 == round(0.75 * 255)).all(), f"retouch back: {rt['changed']} {c8.min()}..{c8.max()}")
    t1 = mt()
    rt = PA["retouch"](root)
    check(not rt["changed"] and not rt["files"] and mt() == t1 and counts() == c1, f"retouch after undo not a no-op: {rt}")
    del c8

load("scripts/tripo_cleanup.py")["cleanup"]({"SM_Handcart": (0.95, 1.00, 2.10, "floor", True)})   # must leave an atlased prop alone
check(bpy.data.materials.get(MAT) and bpy.data.meshes["SM_Handcart"].materials[0].name == MAT
      and tuple(bpy.data.images["T_Props_Atlas_BC"].size) == (W, H2) and counts() == c1,
      "tripo_cleanup changed an atlased prop")

# ------------------------------------------------------------------ renders after
after = render("after")
for n in RENDER:
    st = stats(before[n], after[n])
    print(f"render {n} before vs after: {fmt(st)}")
    if n[3:] in done2:
        check(st["mean"] < 1.5 and st["over8"] < 2.0, f"{n}: look changed ({fmt(st)})")
    a, b_ = before[n], after[n]
    over = lambda p: p[..., :3] * p[..., 3:] + 0.18 * (1 - p[..., 3:])
    strip = np.concatenate([over(a), np.full((a.shape[0], 8, 3), 1.0), over(b_), np.full((a.shape[0], 8, 3), 1.0),
                            np.clip(np.abs(a[..., :3] - b_[..., :3]) * 8, 0, 1)], 1)
    PA["_save"](os.path.join(OUT, f"props_atlas_{n}_compare.png"), strip)

print(f"total {time.time() - T0:.0f} s")
if fails:
    print(f"\nFAILED CHECKS ({len(fails)}):")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL CHECKS PASSED")
