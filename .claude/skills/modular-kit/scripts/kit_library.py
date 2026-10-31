"""Kit library: every kit piece as a collection in one editable .blend, and a sync that puts the edited pieces back into a scene.

Run inside Blender (headless: bash bin/blender-bg [file.blend] --python this_file -- <command> <args>):

  build --scene <blend> --assets-dir <dir> --out <library.blend> [--families-min 2] [--specs-dir <kit specs>] [--migrate-from <old.blend>]
      Layout of <library.blend>: section collections (SECTIONS below), and in each one a collection per piece, named after the piece.
      A piece collection holds the piece's mesh object(s), its UCX_ collision and its SOCKET_ empties. Its instance_offset is the
      piece origin. Pieces are laid out in plan view, one block of rows per section; the collections are marked as assets
      (spec id as tag). Sources: (a) every <assets-dir>/<asset>/<asset>.blend, one piece per mesh object in it; (b) the scene's own
      instance families, which are mesh datablocks used by --families-min or more rendered objects (one-offs, cable and pipe runs,
      wear and parked objects are skipped). Writes <library.blend>.manifest.json. Re-running only adds pieces that are not in the
      manifest and never touches a collection that exists (the user's edits win). A library that exists is copied to
      <library>_backups first. --migrate-from takes the edited meshes of an old (one object per piece) library into the new one.

  sync --library <library.blend> --manifest <json> [--apply --backup <scene backup .blend>] [--report <json>] [--save-as <blend>]
      Run on a scene file. For each piece collection it joins every visible mesh object (UCX_ and SOCKET_ objects excluded) into one
      mesh, with world transforms relative to the collection's instance_offset, in a second background Blender, so the library is
      never touched. A piece whose joined hash differs from the manifest is swapped into every scene object that uses a mapped mesh
      datablock; transform, name, custom properties and modifiers stay, material slots point at the SCENE's materials of the same
      name. A collection that is deleted or has no visible mesh is reported and never applied. Without --apply it only reports.
      --apply needs --backup (a path that does not exist yet): it saves a copy of the open scene there, copies the library to
      <library>_backups/<name>_<stamp>.blend (with the manifest) and then swaps; the manifest keeps each swapped piece's
      previous hash (prev_hash), so syncing an older library copy swaps the old meshes back. The sync() function saves nothing
      else; --save-as is the caller's save, for a headless run.

Hash of a mesh: vertex positions rounded to 0.1 mm, loop vertex indices and polygon sizes, smooth flags, UV values and
material names per slot.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_NAME_PREFIX = ("SM_Pipe_Run_", "CBL_")
PROXY_PREFIX = ("UCX_", "SOCKET_")
WEAR_TOKENS = {"grime", "grimy", "stain", "stains", "drip", "drips", "leak", "leaks", "rust", "rusty", "crack", "cracks", "chip", "chips",
               "dent", "dents", "peel", "peeling", "decal", "decals", "dirt", "dirty", "mold", "mould", "mildew", "streak", "streaks",
               "tidemark"}
WARN_MM = 1.0
ROW_WIDTH_M = 12.0
GAP_M = 0.4
VERSION = 2

# Section of a piece: the first pattern that matches the start of the piece name wins; anything else goes to FALLBACK_SECTION.
SECTIONS = [
    ("Walls", r"SM_Wall_|SM_Trim_|SM_Slab|SM_Dado|SM_Window"),
    ("Stairs", r"SM_Stair|SM_TreadPlate|KP_TreadPlate|SM_Nosing|SM_StringSkirt|SM_Step|SM_Threshold|SM_Handrail"),
    ("Doors", r"SM_Door_|SM_Gate|SM_Shutter|KP_Lattice|GTA_|XB_Door|SM_Mailbox"),
    ("Electrical", r"SM_SwitchPlate|SM_Intercom|SM_PhoneTerminal|SM_TVSplitter|SM_ServiceHead|SM_CutOut|SM_FuseBase|SM_Payphone"),
    ("Conduit", r"SM_Conduit"),
    ("Cable hardware", r"SM_Cable|SM_Cleat|SM_InsulatorRack"),
    ("Pipes and fittings", r"SM_Pipe|SM_Valve|SM_WaterMeter|SM_Downpipe|SM_Flange"),
    ("AC", r"SM_AC_|SM_Louvre"),
    ("Meters and boxes", r"SM_Meter|SM_DoorBox|SM_DistBoard|SM_JunctionBox"),
    ("Signs", r"SM_ExitSign|SM_Sign|C_Poster"),
    ("Lamps", r"SM_Lamp|SM_Tube_Batten|L_Fluo"),
    ("Floor", r"DV_Gully|SP_Gully|X1_Gully|SM_Gully|SM_GAL_DeckSlat|SM_Floor"),
]
FALLBACK_SECTION = "Props"
SECTION_ORDER = [s for s, _ in SECTIONS] + [FALLBACK_SECTION]


class KitLibraryError(Exception):
    pass


def section_of(piece):
    for sec, rx in SECTIONS:
        if re.match(rx, piece):
            return sec, True
    return FALLBACK_SECTION, False


# ---------------------------------------------------------------- geometry hash

def mesh_info(me):
    """Hash, counts, local bbox and material names of one mesh datablock."""
    nv, npoly, nl = len(me.vertices), len(me.polygons), len(me.loops)
    co = np.zeros(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    lv = np.zeros(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    lt = np.zeros(npoly, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    sm = np.zeros(npoly, np.bool_)
    me.polygons.foreach_get("use_smooth", sm)
    h = hashlib.md5()
    h.update(np.round(co.astype(np.float64) * 1e4).astype(np.int64).tobytes())
    for a in (lv, lt, sm):
        h.update(a.tobytes())
    for layer in me.uv_layers:
        uv = np.zeros(nl * 2, np.float32)
        layer.uv.foreach_get("vector", uv)
        h.update(np.round(uv.astype(np.float64) * 1e4).astype(np.int64).tobytes())
    mats = [m.name if m else "" for m in me.materials]
    h.update("|".join(mats).encode())
    pts = co.reshape(-1, 3)
    bb = [pts.min(axis=0).tolist(), pts.max(axis=0).tolist()] if nv else [[0, 0, 0], [0, 0, 0]]
    return {"hash": h.hexdigest(), "verts": nv, "polys": npoly, "tris": int(np.clip(lt - 2, 0, None).sum()),
            "bbox_m": [[round(v, 6) for v in c] for c in bb], "materials": mats, "uv_layers": len(me.uv_layers)}


def _tokens(name):
    return {t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)}


def _skip_family(mesh_name, objs):
    if mesh_name.startswith(SKIP_NAME_PREFIX) or any(o.name.startswith(SKIP_NAME_PREFIX) for o in objs):
        return "cable or pipe run"
    if _tokens(mesh_name) & WEAR_TOKENS:
        return "wear"
    return None


def _render_off_collections(scene):
    off = set()

    def walk(c, hidden):
        hidden = hidden or c.hide_render
        if hidden:
            off.add(c.name)
        for ch in c.children:
            walk(ch, hidden)
    walk(scene.collection, False)
    return off


def scan_scene():
    """mesh datablock name -> {'objects': n, 'rendered': n, 'objs': [rendered objects]} for the open scene."""
    scene = bpy.context.scene
    vl = scene.view_layers[0]
    in_layer = set(vl.objects.keys())
    off = _render_off_collections(scene)
    out = {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.data is None:
            continue
        d = out.setdefault(o.data.name, {"objects": 0, "rendered": 0, "objs": []})
        d["objects"] += 1
        if (not o.hide_render) and o.name in in_layer and not all(c.name in off for c in o.users_collection):
            d["rendered"] += 1
            d["objs"].append(o)
    return out


def scene_matches(users, mesh_name):
    """Scene mesh datablocks that a library mesh maps to: the same name, with or without a .001 style suffix."""
    rx = re.compile(re.escape(mesh_name) + r"(\.\d{3})?$")
    return sorted(n for n in users if rx.match(n))


# ---------------------------------------------------------------- helpers

def _read_spec_id(specs_dir, piece):
    if specs_dir:
        p = os.path.join(specs_dir, piece + ".md")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"asset:\s*([^\s#]+)", line)
                    if m:
                        return m.group(1), p
            return piece, p
    return piece, None


_ID_KINDS = ("materials", "images", "node_groups")


def _snapshot():
    return {k: {i.name for i in getattr(bpy.data, k)} for k in _ID_KINDS}


def _dedupe_new(snap):
    """A datablock that arrived with a .001 suffix next to an older one of the same name collapses onto the older one."""
    for k in _ID_KINDS:
        coll = getattr(bpy.data, k)
        for idb in list(coll):
            if idb.name in snap[k]:
                continue
            m = re.match(r"(.+)\.\d{3}$", idb.name)
            if m and m.group(1) in coll and coll[m.group(1)] is not idb:
                idb.user_remap(coll[m.group(1)])
                coll.remove(idb)


def _world_bbox(objs):
    pts = []
    for o in objs:
        if o.type == 'MESH':
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        else:
            pts.append(o.matrix_world.translation.copy())
    if not pts:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (Vector((min(p[i] for p in pts) for i in range(3))), Vector((max(p[i] for p in pts) for i in range(3))))


def backup_library(library, manifest=None):
    """Copy the library (and its manifest) to <library>_backups/<name>_<stamp>.blend. Returns the copy's path."""
    stem = os.path.splitext(library)[0]
    d = stem + "_backups"
    os.makedirs(d, exist_ok=True)
    base = "%s_%s" % (os.path.basename(stem), datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    dst, i = os.path.join(d, base + ".blend"), 1
    while os.path.exists(dst):
        i += 1
        dst = os.path.join(d, "%s_%d.blend" % (base, i))
    shutil.copy2(library, dst)
    if manifest and os.path.isfile(manifest):
        shutil.copy2(manifest, dst + ".manifest.json")
    return dst


# ---------------------------------------------------------------- the render mesh of a piece collection

def _visible(o, vl):
    if o.hide_viewport or o.hide_render:
        return False
    try:
        return not o.hide_get(view_layer=vl)
    except RuntimeError:   # not in the view layer (collection excluded): count it as visible
        return True


def render_objects(col, vl):
    """Visible mesh objects of a piece collection (child collections included); collision and socket objects are not render geometry."""
    return [o for o in col.all_objects if o.type == 'MESH' and o.data is not None and not o.name.startswith(PROXY_PREFIX) and _visible(o, vl)]


def join_piece(col):
    """One new mesh (named KJ_<piece>, fake user) from every visible mesh object of the collection, with world transforms relative to
    col.instance_offset and modifiers applied. Works on copies; the library objects stay as they are. None when nothing is visible.
    Mutates the open file (temporary objects, which are removed), so run it in a throwaway Blender or a file you will not save."""
    scene, vl = bpy.context.scene, bpy.context.view_layer
    vl.update()
    objs = render_objects(col, vl)
    if not objs:
        return None, [], []
    inv = Matrix.Translation(-Vector(col.instance_offset))
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in objs:
        rel = inv @ o.matrix_world
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        for i, s in enumerate(o.material_slots):   # object-linked slots count; clearing the list would reset the face indices
            if i < len(me.materials):
                me.materials[i] = s.material
            else:
                me.materials.append(s.material)
        # order by position, not by name, so renaming an object does not change the result
        parts.append(((tuple(round(v, 4) for v in rel.translation), len(me.vertices), o.name), rel, me))
    parts.sort(key=lambda p: p[0])
    fallback = next((m for _, _, me in parts for m in me.materials if m), None)
    filled = []
    for key, _, me in parts:   # an object added by hand has no material; without one its faces would sit on an empty slot
        if fallback is not None and not len(me.materials):
            me.materials.append(fallback)
            filled.append(key[2])
    # the first part is the join target (an empty target would add an empty material slot); its transform is baked into the mesh
    tmp = bpy.data.collections.new("_kit_join")
    scene.collection.children.link(tmp)
    pobjs = []
    for i, (_, rel, me) in enumerate(parts):
        if i == 0:
            me.transform(rel)
        po = bpy.data.objects.new("_kit_part", me)
        tmp.objects.link(po)
        if i:
            po.matrix_world = rel
        pobjs.append(po)
    res = pobjs[0].data
    pnames = [o.name for o in pobjs]
    if len(pobjs) > 1:
        vl.update()
        for o in list(vl.objects):
            if o.select_get():
                o.select_set(False)
        for o in pobjs:
            o.select_set(True)
        vl.objects.active = pobjs[0]
        bpy.ops.object.join()
    res.name = "KJ_" + col.name
    res.use_fake_user = True
    for n in pnames:   # join consumed all but the first
        if n in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[n])
    bpy.data.collections.remove(tmp)
    for _, _, me in parts:
        if me is not res and me.users == 0:
            bpy.data.meshes.remove(me)
    return res, [o.name for o in objs], filled


def _cmd_join(pieces_file, out, blend):
    with open(pieces_file, encoding="utf-8") as f:
        names = json.load(f)
    def include(lc):   # throwaway process: make every collection evaluable
        lc.exclude = False
        for ch in lc.children:
            include(ch)
    include(bpy.context.view_layer.layer_collection)
    res, meshes = {}, []
    for n in names:
        col = bpy.data.collections.get(n)
        if col is None:
            res[n] = {"status": "missing_collection"}
            continue
        me, parts, filled = join_piece(col)
        if me is None or len(me.polygons) == 0:
            res[n] = {"status": "empty_collection"}
            continue
        res[n] = {**mesh_info(me), "parts": sorted(parts), "no_material": sorted(filled), "mesh": me.name}
        meshes.append(me)
    bpy.data.libraries.write(blend, set(meshes), compress=False)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f)


def library_join(library, names, tmpdir):
    """piece name -> info for the library, plus <tmpdir>/joined.blend with the joined meshes. Runs in a background Blender, so the
    caller's file and the library stay clean."""
    pf, out, blend = (os.path.join(tmpdir, n) for n in ("pieces.json", "info.json", "joined.blend"))
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(list(names), f)
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", library, "--python", os.path.join(HERE, "kit_library.py"), "--",
           "join", "--pieces-file", pf, "--out", out, "--blend", blend]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        raise KitLibraryError("could not join the library pieces:\n" + (r.stdout + r.stderr)[-1500:])
    with open(out, encoding="utf-8") as f:
        return json.load(f), blend


# ---------------------------------------------------------------- build

def _load_asset_objects(path, piece):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = list(src.objects)
        dst.objects = list(names)
    objs = []
    for n, o in zip(names, dst.objects):
        if o is None:
            continue
        if o.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(o)
            continue
        if o.name != n and (o.type == 'MESH' or o.name.split(".")[0] != n):   # sockets repeat across assets: Blender's .001 suffix is fine
            raise KitLibraryError("%s: object '%s' clashes with a name already in the library (got '%s')" % (piece, n, o.name))
        objs.append(o)
    if not objs:
        raise KitLibraryError("%s: no objects in %s" % (piece, path))
    return objs


def _split_asset(asset, objs):
    """Objects of one asset file -> {piece: [objects]}. Each render mesh object is a piece (a variant is its own piece); collision follows
    the piece its name carries, a socket its parent or its name suffix, anything else the main piece (the one named like the asset)."""
    meshes = [o for o in objs if o.type == 'MESH' and not o.name.startswith(PROXY_PREFIX)]
    if not meshes:
        raise KitLibraryError("%s: no render mesh in the asset file" % asset)
    main = next((o.name for o in meshes if o.name == asset), sorted(o.name for o in meshes)[0])
    groups = {o.name: [o] for o in meshes}
    for o in objs:
        if o in meshes:
            continue
        m = re.match(r"UCX_(.+?)(_\d+)?$", o.name)
        target = m.group(1) if m and m.group(1) in groups else None
        if target is None and o.parent is not None and o.parent.name in groups:
            target = o.parent.name
        if target is None:
            sfx = [(len(n) - len(asset), n) for n in groups if n != asset and n.startswith(asset) and o.name.endswith(n[len(asset):])]
            target = max(sfx)[1] if sfx else main
        groups[target].append(o)
    return groups


def _migrate_edits(old_lib, old_manifest):
    """Meshes the user edited in an old (one object per piece) library: {object name: mesh appended into this file}."""
    with open(old_manifest, encoding="utf-8") as f:
        oldm = json.load(f)["pieces"]
    want = {n: mem["mesh"] for e in oldm.values() for n, mem in e["members"].items() if mem.get("role") in {"master", "variant"} and mem.get("mesh")}
    snap = _snapshot()
    names = sorted({m for m in want.values()})
    with bpy.data.libraries.load(old_lib, link=False) as (src, dst):
        names = [n for n in names if n in src.meshes]
        dst.meshes = names
    got = dict(zip(names, dst.meshes))
    old_hash = {n: mem["hash"] for e in oldm.values() for n, mem in e["members"].items() if n in want}
    edited = {o: got[m] for o, m in want.items() if m in got and mesh_info(got[m])["hash"] != old_hash[o]}
    for m in got.values():
        if m not in edited.values():
            bpy.data.meshes.remove(m)
    _dedupe_new(snap)
    return edited


def build(scene, assets_dir, out, families_min=2, specs_dir=None, migrate_from=None):
    mpath = out + ".manifest.json"
    man = None
    if os.path.isfile(out):
        if not os.path.isfile(mpath):
            raise KitLibraryError("%s exists but %s does not; restore the manifest or build to a new file" % (out, mpath))
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
        if man.get("version") != VERSION:
            if not migrate_from:
                raise KitLibraryError("%s is an old-layout library (one object per piece); pass --migrate-from <a copy of it> to rebuild it" % out)
            old_man, man = man, None
    pieces = man["pieces"] if man else {}
    migrate_man = (migrate_from + ".manifest.json") if migrate_from else None
    if migrate_from and not os.path.isfile(migrate_man):
        raise KitLibraryError("--migrate-from needs %s" % migrate_man)

    # 1. the scene: instance families and the mapping of asset meshes onto scene meshes
    bpy.ops.wm.open_mainfile(filepath=scene)
    users = scan_scene()
    scene_hash = {}

    def shash(mesh_name):
        if mesh_name not in scene_hash:
            scene_hash[mesh_name] = mesh_info(bpy.data.meshes[mesh_name])["hash"]
        return scene_hash[mesh_name]

    def scene_map(mesh_names):
        names = sorted({n for m in mesh_names for n in scene_matches(users, m)})
        return {"scene_meshes": names, "scene_objects": sum(users[n]["objects"] for n in names),
                "scene_rendered": sum(users[n]["rendered"] for n in names), "_hashes": [shash(n) for n in names]}

    asset_files = {}
    for d in sorted(glob.glob(os.path.join(assets_dir, "*", "*.blend"))):
        n = os.path.basename(os.path.dirname(d))
        if os.path.basename(d) == n + ".blend" and not n.startswith("_"):
            asset_files[n] = d
    asset_mesh_names = set(asset_files)
    for n, p in asset_files.items():
        with bpy.data.libraries.load(p, link=False) as (src, _):
            asset_mesh_names |= set(src.meshes)
    mapped_by_assets = {m for n in asset_mesh_names for m in scene_matches(users, n)}

    have_assets = {e.get("asset") for e in pieces.values()}
    new_assets = {n: p for n, p in asset_files.items() if n not in have_assets and n not in pieces}
    known = set(pieces) | {m for e in pieces.values() for m in e.get("src_meshes", [])}
    families, skipped = {}, {"one_off": 0, "cable or pipe run": 0, "wear": 0, "mapped to an asset piece": 0}
    for mesh_name, d in users.items():
        if d["rendered"] < families_min:
            if d["rendered"] >= 1:
                skipped["one_off"] += 1
            continue
        if mesh_name in mapped_by_assets:
            skipped["mapped to an asset piece"] += 1
            continue
        why = _skip_family(mesh_name, d["objs"])
        if why:
            skipped[why] += 1
            continue
        if mesh_name not in known:
            families[mesh_name] = d
    tmp = tempfile.mkdtemp(prefix="kit_library_")
    fam_blend = os.path.join(tmp, "families.blend")
    if families:
        bpy.data.libraries.write(fam_blend, {bpy.data.meshes[n] for n in families}, compress=False)
    refresh = {p: scene_map(e.get("src_meshes", [])) for p, e in pieces.items()}
    asset_scene_maps = {}
    for n in new_assets:
        with bpy.data.libraries.load(new_assets[n], link=False) as (src, _):
            for mn in src.meshes:
                asset_scene_maps[mn] = scene_map([mn])
    fam_maps = {n: scene_map([n]) for n in families}

    # 2. the library: open the existing one or start empty
    if man:
        bpy.ops.wm.open_mainfile(filepath=out)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.view_layer.update()
    staged = []   # (section index, piece, source, source file, asset, objects, source mesh names, scene map)
    for asset, path in new_assets.items():
        snap = _snapshot()
        objs = _load_asset_objects(path, asset)
        _dedupe_new(snap)
        for piece, group in _split_asset(asset, objs).items():
            main = next(o for o in group if o.type == 'MESH' and not o.name.startswith(PROXY_PREFIX))
            smap = asset_scene_maps.get(main.data.name) or scene_map([])
            staged.append((piece, "asset", path, asset, group, [main.data.name], smap))
    if families:
        snap = _snapshot()
        with bpy.data.libraries.load(fam_blend, link=False) as (src, dst):
            dst.meshes = [n for n in sorted(families) if n in src.meshes]
        for me in dst.meshes:
            if me is not None and me.name not in families:
                raise KitLibraryError("family mesh '%s' clashes with a name already in the library" % me.name)
        _dedupe_new(snap)
        for me in dst.meshes:
            if me is not None:
                staged.append((me.name, "scene_family", scene, None, [bpy.data.objects.new(me.name, me)], [me.name], fam_maps[me.name]))
    shutil.rmtree(tmp, ignore_errors=True)

    sections = {}
    fallback = []
    layout_y = {"top": None, "x": 0.0, "h": 0.0}
    ys = [_world_bbox([o])[0].y for o in bpy.data.objects]
    layout_y["top"] = (min(ys) - 1.0) if ys else 0.0
    new_entries, added = {}, []
    last_section = None
    for piece, source, source_file, asset, group, src_meshes, smap in sorted(staged, key=lambda s: (SECTION_ORDER.index(section_of(s[0])[0]), s[0])):
        if bpy.data.collections.get(piece) is not None:
            print("kit_library: collection '%s' already exists; left as it is" % piece)
            continue
        sec, matched = section_of(piece)
        if not matched:
            fallback.append(piece)
        if sec not in sections:
            sections[sec] = bpy.data.collections.get(sec) or bpy.data.collections.new(sec)
            if sections[sec].name not in [c.name for c in bpy.context.scene.collection.children]:
                bpy.context.scene.collection.children.link(sections[sec])
        col = bpy.data.collections.new(piece)
        sections[sec].children.link(col)
        for o in group:
            col.objects.link(o)
        bpy.context.view_layer.update()
        lo, hi = _world_bbox(group)
        w, d = hi.x - lo.x, hi.y - lo.y
        if sec != last_section and layout_y["x"] > 0:
            layout_y["top"] -= layout_y["h"] + 2 * GAP_M
            layout_y["x"], layout_y["h"] = 0.0, 0.0
        elif layout_y["x"] > 0 and layout_y["x"] + w > ROW_WIDTH_M:
            layout_y["top"] -= layout_y["h"] + GAP_M
            layout_y["x"], layout_y["h"] = 0.0, 0.0
        last_section = sec
        shift = Vector((layout_y["x"] - lo.x, layout_y["top"] - hi.y, 0.0))
        for o in group:
            if o.parent is None:
                o.location = o.location + shift
        layout_y["x"] += w + GAP_M
        layout_y["h"] = max(layout_y["h"], d + 0.25)
        bpy.context.view_layer.update()
        main = next(o for o in group if o.type == 'MESH' and not o.name.startswith(PROXY_PREFIX))
        col.instance_offset = main.matrix_world.translation
        spec_id, spec_file = _read_spec_id(specs_dir, piece)
        col.asset_mark()
        col.asset_data.description = "spec %s (%s)" % (spec_id, sec)
        col.asset_data.tags.new("spec:" + spec_id, skip_if_exists=True)
        col.asset_data.tags.new(sec, skip_if_exists=True)
        entry = {"section": sec, "source": source, "source_file": source_file, "asset": asset, "spec_id": spec_id, "spec_file": spec_file,
                 "src_meshes": src_meshes, "objects": sorted(o.name for o in group), "scene_meshes": smap["scene_meshes"],
                 "scene_objects": smap["scene_objects"], "scene_rendered": smap["scene_rendered"],
                 "in_scene": bool(smap["scene_meshes"])}
        if not entry["in_scene"]:
            entry["note"] = "not placed in the scene yet: maps to no scene mesh, so a sync swaps nothing for it until it is placed"
        new_entries[piece] = (entry, smap["_hashes"])
        added.append(piece)

    for p, sm in refresh.items():   # kept pieces: refresh the scene mapping, never the baseline hashes
        e = pieces[p]
        e.update({"scene_meshes": sm["scene_meshes"], "scene_objects": sm["scene_objects"], "scene_rendered": sm["scene_rendered"],
                  "in_scene": bool(sm["scene_meshes"]), "scene_hash_match": bool(sm["_hashes"]) and all(h == e.get("hash") for h in sm["_hashes"])})
        if e["in_scene"]:
            e.pop("note", None)

    # 3. save, then take the baseline hashes of the new pieces from the saved file in a second Blender (the same path a sync takes)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fresh = not man
    old_copy = backup_library(out, mpath) if os.path.isfile(out) and (added or fresh) else None
    migrated = []
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
    if added:
        jt = tempfile.mkdtemp(prefix="kit_library_")
        try:
            info, _ = library_join(out, added, jt)
        finally:
            shutil.rmtree(jt, ignore_errors=True)
        for p in added:
            entry, shashes = new_entries[p]
            if "hash" not in info[p]:
                raise KitLibraryError("%s: %s after the build" % (p, info[p]["status"]))
            now = info[p]
            entry.update({k: now[k] for k in ("hash", "verts", "polys", "tris", "bbox_m", "materials")})
            entry["prev_hash"] = None
            entry["scene_hash_match"] = bool(shashes) and all(h == now["hash"] for h in shashes)
            pieces[p] = entry
    if migrate_from and added:   # the user's edits in the old library win over the sources; their baseline stays the source hash
        edited = _migrate_edits(migrate_from, migrate_man)
        for oname, nm in edited.items():
            ob = bpy.data.objects.get(oname)
            if ob is None or ob.type != 'MESH':
                print("kit_library: edited mesh of '%s' has no object in the new library; not migrated" % oname)
                continue
            old = ob.data
            ob.data = nm
            keep = old.name
            if old.users == 0:
                bpy.data.meshes.remove(old)
            nm.name = keep
            migrated.append(oname)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
    first_copy = backup_library(out, None) if fresh and added else None

    now_s = datetime.datetime.now().isoformat(timespec="seconds")
    man = {"version": VERSION, "built": man["built"] if man else now_s, "updated": now_s, "scene": scene, "assets_dir": assets_dir,
           "families_min": families_min, "sections": SECTION_ORDER,
           "hash": "md5 of the joined render mesh: vertex positions at 0.1 mm, loops, polygon sizes, smooth flags, UVs, slot material names",
           "skipped_scene_meshes": skipped, "pieces": dict(sorted(pieces.items()))}
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    if first_copy:
        shutil.copy2(mpath, first_copy + ".manifest.json")
    by_section = {}
    for e in pieces.values():
        by_section[e["section"]] = by_section.get(e["section"], 0) + 1
    return {"library": out, "manifest": mpath, "added": added, "pieces": len(pieces), "by_section": by_section,
            "not_in_scene": sorted(p for p, e in pieces.items() if not e["in_scene"]), "to_props_by_default": fallback,
            "migrated_edits": migrated, "previous_library_copy": old_copy, "skipped_scene_meshes": skipped}


# ---------------------------------------------------------------- sync

def _delta(old_bb, new_bb):
    omin, omax, nmin, nmax = (Vector(c) for c in (old_bb[0], old_bb[1], new_bb[0], new_bb[1]))
    dmin, dmax = (nmin - omin) * 1000, (nmax - omax) * 1000
    worst = max(max(abs(v) for v in dmin), max(abs(v) for v in dmax))
    same_size = ((nmax - nmin) - (omax - omin)).length * 1000 < 0.1
    return {"delta_min_mm": [round(v, 3) for v in dmin], "delta_max_mm": [round(v, 3) for v in dmax], "worst_mm": round(worst, 3),
            "pure_shift": bool(same_size and worst > 0.05)}


def _swap_mesh(old, lib_path, lib_mesh, lib_mats, first):
    """Append the library mesh (or a copy of the one already appended) and put it under every user of `old`."""
    snap = _snapshot()
    if first is None:
        with bpy.data.libraries.load(lib_path, link=False) as (src, dst):
            if lib_mesh not in src.meshes:
                raise KitLibraryError("mesh '%s' is not in %s" % (lib_mesh, lib_path))
            dst.meshes = [lib_mesh]
        new = dst.meshes[0]
        new.use_fake_user = False
    else:
        new = first.copy()
    new_mats = []
    for i, name in enumerate(lib_mats):
        if not name:
            continue
        got = new.materials[i]
        if name in snap["materials"]:
            scene_mat = bpy.data.materials[name]
            new.materials[i] = scene_mat
            if got is not scene_mat and got is not None and got.users == 0:
                bpy.data.materials.remove(got)
        elif got is not None:
            if got.name != name:
                got.name = name
            new_mats.append(name)
    for k in _ID_KINDS:
        coll = getattr(bpy.data, k)
        for idb in list(coll):
            if idb.name not in snap[k] and idb.users == 0:
                coll.remove(idb)
    for k in old.keys():
        if k not in new.keys():
            new[k] = old[k]
    name = old.name
    old.user_remap(new)
    old.use_fake_user = False
    if old.users == 0:
        bpy.data.meshes.remove(old)
        new.name = name
    return new, new_mats


def sync(library, manifest, apply=False, report=None, backup=None):
    """Compare the library with the manifest and swap changed pieces into the open scene. Saves nothing but the backups (the caller
    saves the scene). apply=True needs backup=<path>: a copy of the open scene is saved there before anything changes."""
    if apply and not backup:
        raise KitLibraryError("apply needs backup=<path for a copy of this scene file>; nothing was changed")
    with open(manifest, encoding="utf-8") as f:
        man = json.load(f)
    if man.get("version") != VERSION:
        raise KitLibraryError("%s is an old-layout manifest; rebuild the library with build --migrate-from" % manifest)
    rep = {"library": library, "manifest": manifest, "apply": bool(apply), "pieces": [], "summary": {}}
    jt = tempfile.mkdtemp(prefix="kit_sync_")
    try:
        lib, joined = library_join(library, list(man["pieces"]), jt)
        unchanged = 0
        todo = []
        for piece, entry in man["pieces"].items():
            now = lib[piece]
            if "hash" not in now:
                rep["pieces"].append({"piece": piece, "status": now["status"], "objects": 0, "warnings": [
                    ("the collection is gone from the library" if now["status"] == "missing_collection" else "the collection has no visible mesh object")
                    + "; nothing changed in the scene"], "could_not_swap": []})
                continue
            if now["hash"] == entry["hash"]:
                unchanged += 1
                continue
            row = {"piece": piece, "section": entry.get("section"), "scene_meshes": [], "objects": 0, "objects_sample": [], "parts": now["parts"],
                   "tris_before": entry["tris"], "tris_after": now["tris"], "bbox_before_m": entry["bbox_m"], "bbox_after_m": now["bbox_m"],
                   "warnings": [], "new_materials": [], "could_not_swap": []}
            for n in now.get("no_material", []):
                row["warnings"].append("%s has no material: its faces got the piece's first material" % n)
            if entry.get("prev_hash") == now["hash"]:
                row["warnings"].append("this library copy holds the previous version of the piece: applying it undoes the last sync")
            meshes = [bpy.data.meshes[n] for n in entry.get("scene_meshes", []) if n in bpy.data.meshes]
            for n in entry.get("scene_meshes", []):
                if n not in bpy.data.meshes:
                    row["could_not_swap"].append({"mesh": n, "reason": "mesh datablock is not in this scene file"})
            ok = []
            objs = []
            for me in meshes:
                if me.library is not None or me.shape_keys is not None:
                    row["could_not_swap"].append({"mesh": me.name, "reason": "linked from another file" if me.library else "has shape keys"})
                    continue
                ok.append(me)
                objs += [o for o in bpy.data.objects if o.type == 'MESH' and o.data is me]
            row["scene_meshes"] = [m.name for m in ok]
            row["objects"] = len(objs)
            row["objects_sample"] = [o.name for o in objs[:20]]
            if meshes:
                cur = mesh_info(meshes[0])
                row.update({"tris_before": cur["tris"], "bbox_before_m": cur["bbox_m"]})
            row["status"] = "would_swap" if objs else "changed_not_in_scene"
            row.update(_delta(row["bbox_before_m"], now["bbox_m"]))
            if row["worst_mm"] > WARN_MM:
                if row["pure_shift"]:
                    row["warnings"].append("origin moved: the whole mesh shifts %.1f mm against the pivot, so every instance moves (above %.0f mm)" % (row["worst_mm"], WARN_MM))
                else:
                    row["warnings"].append("bbox changes by up to %.1f mm (above %.0f mm): every instance changes" % (row["worst_mm"], WARN_MM))
            row["new_materials"] = sorted({m for m in now["materials"] if m and m not in bpy.data.materials})
            for o in objs:
                if any(s.link == 'OBJECT' for s in o.material_slots):
                    row["warnings"].append("%s has object-linked material slots; check them after the swap" % o.name)
                    break
            rep["pieces"].append(row)
            if objs:
                todo.append((piece, row, ok, now))
        if apply and todo:
            if os.path.exists(backup):
                raise KitLibraryError("backup %s exists already; give a new path. Nothing was changed" % backup)
            os.makedirs(os.path.dirname(os.path.abspath(backup)), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(backup), copy=True, compress=False)
            rep["scene_backup"] = os.path.abspath(backup)
            if "_backups" not in os.path.basename(os.path.dirname(library)):
                rep["library_backup"] = backup_library(library, manifest)
            first_new = {}
            for piece, row, ok, now in todo:
                added = []
                for me in ok:
                    new, nm = _swap_mesh(me, joined, now["mesh"], now["materials"], first_new.get(piece))
                    first_new.setdefault(piece, new)
                    added += nm
                row["status"] = "swapped"
                row["new_materials"] = sorted(set(added))
                e = man["pieces"][piece]
                e["prev_hash"] = e["hash"]
                e.update({k: now[k] for k in ("hash", "verts", "polys", "tris", "bbox_m", "materials")})
                e["scene_hash_match"] = True
    finally:
        shutil.rmtree(jt, ignore_errors=True)
    swapped = [r for r in rep["pieces"] if r["status"] in {"swapped", "would_swap"}]
    rep["summary"] = {"pieces_changed": len([r for r in rep["pieces"] if r["status"] in {"swapped", "would_swap", "changed_not_in_scene"}]),
                      "not_applied": len([r for r in rep["pieces"] if r["status"] in {"missing_collection", "empty_collection"}]),
                      "unchanged_pieces": unchanged, "objects": sum(r["objects"] for r in swapped),
                      "warnings": sum(len(r["warnings"]) for r in rep["pieces"]),
                      "could_not_swap": sum(len(r["could_not_swap"]) for r in rep["pieces"])}
    if apply and any(r["status"] == "swapped" for r in rep["pieces"]):
        man["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(man, f, indent=1)
        rep["manifest_updated"] = True
    if report:
        with open(report, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    return rep


def _lines(rep):
    out = []
    for r in rep["pieces"]:
        out.append("%s %s: %s objects, tris %s -> %s, new materials %s" % (
            r["status"], r["piece"], r.get("objects", 0), r.get("tris_before"), r.get("tris_after"), r.get("new_materials", [])))
        out += ["  warn " + w for w in r["warnings"]]
        out += ["  could not swap %s: %s" % (c.get("object") or c.get("mesh"), c["reason"]) for c in r.get("could_not_swap", [])]
    for k in ("scene_backup", "library_backup"):
        if rep.get(k):
            out.append("%s %s" % (k, rep[k]))
    return out


# ---------------------------------------------------------------- command line

def main(argv):
    ap = argparse.ArgumentParser(prog="kit_library.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--scene", required=True)
    b.add_argument("--assets-dir", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--families-min", type=int, default=2)
    b.add_argument("--specs-dir")
    b.add_argument("--migrate-from", help="an old-layout library (with its manifest beside it) whose edited meshes are carried over")
    s = sub.add_parser("sync")
    s.add_argument("--library", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--apply", action="store_true")
    s.add_argument("--backup", help="path for a copy of the open scene, saved before --apply changes anything (required with --apply)")
    s.add_argument("--report")
    s.add_argument("--save-as", help="save the scene here after --apply (the caller's save, for a headless run)")
    j = sub.add_parser("join")
    j.add_argument("--pieces-file", required=True)
    j.add_argument("--out", required=True)
    j.add_argument("--blend", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "join":
        _cmd_join(a.pieces_file, a.out, a.blend)
        return 0
    if a.cmd == "build":
        res = build(os.path.abspath(a.scene), os.path.abspath(a.assets_dir), os.path.abspath(a.out), a.families_min,
                    os.path.abspath(a.specs_dir) if a.specs_dir else None, os.path.abspath(a.migrate_from) if a.migrate_from else None)
        print("KIT_LIBRARY", json.dumps(res))
        return 0
    rep = sync(os.path.abspath(a.library), os.path.abspath(a.manifest), a.apply, os.path.abspath(a.report) if a.report else None,
               os.path.abspath(a.backup) if a.backup else None)
    for line in _lines(rep):
        print(line)
    if a.apply and a.save_as:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save_as), compress=False)
    print("KIT_SYNC", json.dumps({"apply": rep["apply"], **rep["summary"]}))
    return 0


if any(os.path.basename(x) == "kit_library.py" for x in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except Exception as e:   # Blender exits 0 after an exception under --python
        import traceback
        traceback.print_exc()
        print("KIT_LIBRARY ERROR:", repr(e))
        code = 1
    sys.exit(code)
