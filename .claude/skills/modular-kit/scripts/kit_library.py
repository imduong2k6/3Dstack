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
      --exclude <name ...> / --exclude-from <file> (json list, json with an "assets" object, or one name per line) keep those assets
      and pieces out of the library (a piece already in it is left alone). --dry-run prints what would be added, replaced and kept and writes nothing.
      --refresh [<piece> ...] (no names: every piece) replaces stale pieces with a fresh copy of their asset, in place in the same section.
      A piece is stale when its asset file was saved after the recorded build time (source_mtime) and its joined shape differs (an entry without
      source_mtime is compared by shape alone), or it came from the scene's own mesh and an asset of that name exists now. A piece is replaced only if
      the library still holds what the manifest says: the joined hash equals the manifest's and the collection holds the same object names; any other
      piece is kept and listed as kept_user_edit, never overwritten (collision and socket objects are compared by name only, not by shape).
      The manifest takes the new hash as the baseline (prev_hash = the old one), so `sync` reads a refreshed piece as unchanged and swaps nothing
      into scene meshes; `join-rows` places and swaps from the library as before.

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

  join-rows --library <library.blend> --manifest <json> --rows <rows.json> [--apply --backup <scene backup .blend>] [--report <json>] [--save-as <blend>]
            [--skip-lanes A,B] [--skip-no-uv] [--parent <collection>] [--phase <tag>] [--no-swap]
      Run on a scene file. Joins a project's placement rows (a rows file written by the project's own tool, which is what reads the lane maps) the way
      sync cannot: per row one object of the library piece (joined as sync joins it, so the user's edits count) at the row's loc, rot and scale, in
      COL_Lane_<lane> (under --parent), identical masters sharing one mesh, `slots` overrides as per-object material slots; every gate object in
      `gate_hidden` is hidden (hide_render and hide_viewport on, never deleted, marked kit_join_hidden) unless every lane that names it is left out;
      gate meshes named like a built asset the rows file lists under `swapped` take the library mesh when a shown object uses them (sync's swap; --no-swap leaves
      them); `host_cuts` run only when their object is
      shown, on a copy of its mesh that keeps the old one as <name>.pre_cut. Rows with placed false, a status superseded/parked, a piece that is not
      in the library, or the world origin as location are skipped with the reason. Rows are matched to objects by lane|gate|master|count (custom
      property kit_row), so a rerun places nothing twice and a regenerated file moves what changed; objects of rows that are gone are listed as
      orphans and left. Without --apply it only writes the report (every add, move, keep, hide, swap and skip, with reasons). --apply needs
      --backup and checks afterwards (placed count equals the rows', no empty slot, no .001 material, cameras, lights, render and view settings and
      collection exclusion unchanged); a failed check exits 1 and --save-as does not save. The library and manifest are only read.

Hash of a mesh: vertex positions rounded to 0.1 mm, loop vertex indices and polygon sizes, smooth flags, UV values and
material names per slot.
"""
import argparse
import datetime
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

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
    ("Doors", r"SM_Door_|SM_Gate|SM_Shutter|KP_Lattice|GTA_|XB_Door|SM_Mail"),
    ("Electrical", r"SM_SwitchPlate|SM_Intercom|SM_PhoneTerminal|SM_TVSplitter|SM_ServiceHead|SM_CutOut|SM_FuseBase|SM_Payphone"),
    ("Conduit", r"SM_Conduit"),
    ("Cable hardware", r"SM_Cable|SM_Cleat|SM_InsulatorRack"),
    ("Pipes and fittings", r"SM_Pipe|SM_Valve|SM_Water_?Meter|SM_Downpipe|SM_Flange"),
    ("AC", r"SM_AC_|SM_Louvre"),
    ("Meters and boxes", r"SM_Meter|SM_DoorBox|SM_DistBoard|SM_JunctionBox"),
    ("Signs", r"SM_ExitSign|SM_Sign|C_Poster"),
    ("Lamps", r"SM_Lamp|SM_Tube|SM_Bulb|L_Fluo"),
    ("Floor", r"DV_Gully|SP_Gully|X1_Gully|SM_Gully|SM_GAL_DeckSlat|SM_Floor"),
    ("Slabs and roofs", r"SM_Ceiling|SM_Soffit|SM_Beam|SM_Roof"),
    ("Far facades", r"SM_Facade"),
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
        res[n] = {**mesh_info(me), "parts": sorted(parts), "no_material": sorted(filled), "mesh": me.name, "objects": sorted(o.name for o in col.all_objects)}
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

def read_names(path):
    """Names from a json list, a json object (its "assets" keys, else its keys) or a text file with one name per line."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        d = json.loads(text)
    except ValueError:
        return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    return list(d.get("assets", d)) if isinstance(d, dict) else list(d)


def _load_asset_objects(path, piece, only=None):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = [n for n in src.objects if only is None or n in only]
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


# ---------------------------------------------------------------- refresh

def _shape_diff(a, b, tol=2e-4):
    """None when two meshes are the same shape (positions and UVs within tol, same topology, smooth flags, slot assignment and slot materials), else why.
    Not the hash: a piece laid out far from the origin carries float noise that can cross a 0.1 mm rounding step."""
    if (len(a.vertices), len(a.polygons), len(a.loops), len(a.uv_layers)) != (len(b.vertices), len(b.polygons), len(b.loops), len(b.uv_layers)):
        return "vertex, face, loop or UV layer counts differ"
    if [re.sub(r"\.\d{3}$", "", m.name) if m else "" for m in a.materials] != [re.sub(r"\.\d{3}$", "", m.name) if m else "" for m in b.materials]:
        return "slot materials differ"   # a .001 suffix is only the clash of the two files' names in this session

    def get(coll, attr, n, dt):
        buf = np.zeros(n * (3 if attr == "co" else 2 if attr == "vector" else 1), dt)
        coll.foreach_get(attr, buf)
        return buf
    for kind, attr, dt in (("vertices", "co", np.float32), ("loops", "vertex_index", np.int32), ("polygons", "loop_total", np.int32),
                           ("polygons", "use_smooth", np.bool_), ("polygons", "material_index", np.int32)):
        x, y = (get(getattr(me, kind), attr, len(getattr(me, kind)), dt) for me in (a, b))
        if dt is np.float32:
            if np.abs(x - y).max(initial=0) > tol:
                return "vertex positions differ by up to %.2f mm" % (np.abs(x - y).max() * 1000)
        elif not np.array_equal(x, y):
            return "topology, smooth flags or slot assignment differ"
    for la, lb in zip(a.uv_layers, b.uv_layers):
        x, y = (get(l.uv, "vector", len(me.loops), np.float32) for l, me in ((la, a), (lb, b)))
        if np.abs(x - y).max(initial=0) > tol:
            return "UVs differ"
    return None


def _cmd_fresh(spec_file, out, joined):
    """Child process of refresh. For each {piece, asset, file}: load the asset file into a clean session, build the piece the way build does
    (no layout shift) and compare it with KJ_<piece> in `joined` (the library's own join)."""
    with open(spec_file, encoding="utf-8") as f:
        items = json.load(f)
    by_file, res = {}, {}
    for it in items:
        by_file.setdefault((it["asset"], it["file"]), []).append(it["piece"])
    for (asset, path), wanted in by_file.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        try:
            groups = _split_asset(asset, _load_asset_objects(path, asset))
        except KitLibraryError as e:
            res.update({p: {"status": str(e)} for p in wanted})
            continue
        for p in wanted:
            if p not in groups:
                res[p] = {"status": "the asset file has no mesh object named %s" % p}
                continue
            col = bpy.data.collections.new("_fresh_" + p)
            bpy.context.scene.collection.children.link(col)
            for o in groups[p]:
                col.objects.link(o)
            bpy.context.view_layer.update()
            main = next(o for o in groups[p] if o.type == 'MESH' and not o.name.startswith(PROXY_PREFIX))
            col.instance_offset = main.matrix_world.translation
            me, _, _ = join_piece(col)
            if me is None or len(me.polygons) == 0:
                res[p] = {"status": "the asset piece has no visible mesh"}
                continue
            with bpy.data.libraries.load(joined, link=False) as (src, dst):
                dst.meshes = ["KJ_" + p]
            res[p] = {"src_mesh": main.data.name, "objects": sorted(o.name for o in groups[p]), "diff": _shape_diff(dst.meshes[0], me)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f)


def fresh_join(items, joined, tmpdir):
    pf, out = os.path.join(tmpdir, "fresh_items.json"), os.path.join(tmpdir, "fresh_info.json")
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(items, f)
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", "--python", os.path.join(HERE, "kit_library.py"), "--",
           "fresh", "--spec", pf, "--out", out, "--joined", joined]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        raise KitLibraryError("could not read the asset files:\n" + (r.stdout + r.stderr)[-1500:])
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def refresh_plan(library, man, asset_files, names, exclude, tmpdir):
    """Which pieces a refresh replaces. Reads the library and the asset files, changes nothing. Returns
    {"replace": {piece: {why, asset, file, src_mesh, objects}}, "kept_user_edit": {piece: why}, "current": [piece], "unchecked": {piece: why}}."""
    pieces = man["pieces"]
    names = list(names) or list(pieces)
    for n in names:
        if n not in pieces:
            raise KitLibraryError("--refresh: '%s' is not a piece of this library" % n)
    plan = {"replace": {}, "kept_user_edit": {}, "current": [], "unchecked": {}, "same_shape_newer_file": {}}
    cand = {}   # piece -> (asset, file, why it may be stale)
    for p in names:
        e = pieces[p]
        if p in exclude or e.get("asset") in exclude:
            plan["unchecked"][p] = "excluded"
        elif e.get("source") == "asset":
            f = asset_files.get(e.get("asset")) or e.get("source_file")
            mt = e.get("source_mtime")
            if not f or not os.path.isfile(f):
                plan["unchecked"][p] = "the asset file is gone"
            elif mt and os.path.getmtime(f) <= mt + 2:
                plan["current"].append(p)
            else:
                cand[p] = (e["asset"], f, "the asset file was saved after the build" if mt else "the asset's shape differs from the piece (no recorded file time)")
        elif p in asset_files:
            cand[p] = (p, asset_files[p], "the piece is the scene's own mesh and an asset of that name exists now")
    if not cand:
        return plan
    lib, joined = library_join(library, list(cand), tmpdir)
    for p in list(cand):   # the user's edits win: the library must still hold what the manifest says
        info, e = lib[p], pieces[p]
        if "hash" not in info:
            plan["kept_user_edit"][p] = "the collection is %s in the library" % ("gone" if info["status"] == "missing_collection" else "empty")
        elif info["hash"] != e["hash"]:
            plan["kept_user_edit"][p] = "its mesh differs from the manifest (edited in the library)"
        elif sorted(info["objects"]) != sorted(e.get("objects", [])):
            plan["kept_user_edit"][p] = "its objects differ from the build (added, removed or renamed in the library)"
        else:
            continue
        del cand[p]
    if cand:
        fresh = fresh_join([{"piece": p, "asset": a, "file": f} for p, (a, f, _) in cand.items()], joined, tmpdir)
        for p, (a, f, why) in cand.items():
            fr = fresh[p]
            if "diff" not in fr:
                plan["unchecked"][p] = fr["status"]
            elif pieces[p].get("source") == "asset" and fr["diff"] is None:
                plan["current"].append(p)   # saved again, same shape
                plan["same_shape_newer_file"][p] = os.path.getmtime(f)
            else:
                plan["replace"][p] = {"why": why + ("" if fr["diff"] is None else "; " + fr["diff"]), "asset": a, "file": f,
                                      "src_mesh": fr["src_mesh"], "objects": fr["objects"]}
    plan["current"].sort()
    return plan


def _replace_piece(piece, asset, path, names):
    """Swap the objects of a library piece collection for a fresh copy from the asset file. The collection stays (section, asset data, tags);
    the new objects start where the old piece's footprint began. Returns the new object names."""
    col = bpy.data.collections[piece]
    bpy.context.view_layer.update()
    old = list(col.all_objects)
    lo0, hi0 = _world_bbox(old)
    meshes = {o.data for o in old if o.type == 'MESH'}
    for o in old:
        bpy.data.objects.remove(o)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    snap = _snapshot()
    group = _split_asset(asset, _load_asset_objects(path, asset, set(names)))[piece]   # only this piece's objects: the asset's other pieces are collections of their own
    _dedupe_new(snap)
    for o in group:
        col.objects.link(o)
    bpy.context.view_layer.update()
    lo, hi = _world_bbox(group)
    shift = Vector((lo0.x - lo.x, hi0.y - hi.y, 0.0))
    for o in group:
        if o.parent is None:
            o.location = o.location + shift
    bpy.context.view_layer.update()
    main = next(o for o in group if o.type == 'MESH' and not o.name.startswith(PROXY_PREFIX))
    col.instance_offset = main.matrix_world.translation
    return sorted(o.name for o in group)


def build(scene, assets_dir, out, families_min=2, specs_dir=None, migrate_from=None, refresh=None, dry_run=False, exclude=()):
    mpath = out + ".manifest.json"
    exclude = set(exclude)
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
    asset_files = {}
    for d in sorted(glob.glob(os.path.join(assets_dir, "*", "*.blend"))):
        n = os.path.basename(os.path.dirname(d))
        if os.path.basename(d) == n + ".blend" and not n.startswith("_"):
            asset_files[n] = d
    plan = None   # --refresh: read the library and the asset files first, in other processes, before anything is opened here
    if refresh is not None:
        if not man:
            raise KitLibraryError("--refresh needs an existing library with its manifest")
        rt = tempfile.mkdtemp(prefix="kit_refresh_")
        try:
            plan = refresh_plan(out, man, asset_files, refresh, exclude, rt)
        finally:
            shutil.rmtree(rt, ignore_errors=True)

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

    asset_mesh_names = set(asset_files)
    for n, p in asset_files.items():
        with bpy.data.libraries.load(p, link=False) as (src, _):
            asset_mesh_names |= set(src.meshes)
    mapped_by_assets = {m for n in asset_mesh_names for m in scene_matches(users, n)}

    have_assets = {e.get("asset") for e in pieces.values()}
    new_assets = {n: p for n, p in asset_files.items() if n not in have_assets and n not in pieces and n not in exclude}
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
        if mesh_name not in known and mesh_name not in exclude:
            families[mesh_name] = d
    tmp = tempfile.mkdtemp(prefix="kit_library_")
    fam_blend = os.path.join(tmp, "families.blend")
    if families:
        bpy.data.libraries.write(fam_blend, {bpy.data.meshes[n] for n in families}, compress=False)
    kept_maps = {p: scene_map(e.get("src_meshes", [])) for p, e in pieces.items()}
    replace_maps = {p: scene_map([r["src_mesh"]]) for p, r in plan["replace"].items()} if plan else {}
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
    replaced = {}
    if plan and not dry_run:   # in place, before the new pieces are laid out; nothing is saved until the end
        for p, r in sorted(plan["replace"].items()):
            replaced[p] = _replace_piece(p, r["asset"], r["file"], r["objects"])
    staged = []   # (section index, piece, source, source file, asset, objects, source mesh names, scene map)
    for asset, path in new_assets.items():
        snap = _snapshot()
        objs = _load_asset_objects(path, asset)
        _dedupe_new(snap)
        for piece, group in _split_asset(asset, objs).items():
            if piece in exclude:
                continue
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
        entry = {"section": sec, "source": source, "source_file": source_file, "source_mtime": os.path.getmtime(source_file) if source == "asset" else None,
                 "asset": asset, "spec_id": spec_id, "spec_file": spec_file,
                 "src_meshes": src_meshes, "objects": sorted(o.name for o in group), "scene_meshes": smap["scene_meshes"],
                 "scene_objects": smap["scene_objects"], "scene_rendered": smap["scene_rendered"],
                 "in_scene": bool(smap["scene_meshes"])}
        if not entry["in_scene"]:
            entry["note"] = "not placed in the scene yet: maps to no scene mesh, so a sync swaps nothing for it until it is placed"
        new_entries[piece] = (entry, smap["_hashes"])
        added.append(piece)

    for p, sm in kept_maps.items():   # kept pieces: refresh the scene mapping, never the baseline hashes
        e = pieces[p]
        e.update({"scene_meshes": sm["scene_meshes"], "scene_objects": sm["scene_objects"], "scene_rendered": sm["scene_rendered"],
                  "in_scene": bool(sm["scene_meshes"]), "scene_hash_match": bool(sm["_hashes"]) and all(h == e.get("hash") for h in sm["_hashes"])})
        if e["in_scene"]:
            e.pop("note", None)

    report = {"added": added, "excluded": sorted(n for n in exclude if n in asset_files and n not in pieces)}
    if plan:
        report["refresh"] = {"replace": {p: r["why"] for p, r in plan["replace"].items()}, "kept_user_edit": plan["kept_user_edit"],
                             "current": len(plan["current"]), "unchecked": plan["unchecked"]}
    if dry_run:   # everything above happened in memory: nothing is saved, backed up or written
        return {"dry_run": True, "library": out, **report, "pieces": len(pieces) + len(added)}

    # 3. save, then take the baseline hashes of the new pieces from the saved file in a second Blender (the same path a sync takes)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fresh = not man
    old_copy = backup_library(out, mpath) if os.path.isfile(out) and (added or fresh or replaced) else None
    migrated = []
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
    if added or replaced:
        jt = tempfile.mkdtemp(prefix="kit_library_")
        try:
            info, _ = library_join(out, added + sorted(replaced), jt)
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
        for p, names in replaced.items():   # the manifest's baseline becomes the refreshed piece; the old hash stays as prev_hash
            e, r, now, sm = pieces[p], plan["replace"][p], info[p], replace_maps[p]
            if "hash" not in now:
                raise KitLibraryError("%s: %s after the refresh" % (p, now["status"]))
            e.update({"source": "asset", "source_file": r["file"], "source_mtime": os.path.getmtime(r["file"]), "asset": r["asset"], "src_meshes": [r["src_mesh"]],
                      "objects": names, "scene_meshes": sm["scene_meshes"], "scene_objects": sm["scene_objects"], "scene_rendered": sm["scene_rendered"],
                      "in_scene": bool(sm["scene_meshes"]), "prev_hash": e["hash"], "refreshed": {"at": datetime.datetime.now().isoformat(timespec="seconds"), "why": r["why"]}})
            e.update({k: now[k] for k in ("hash", "verts", "polys", "tris", "bbox_m", "materials")})
            e["scene_hash_match"] = bool(sm["_hashes"]) and all(h == now["hash"] for h in sm["_hashes"])
            if e["in_scene"]:
                e.pop("note", None)
            else:
                e["note"] = "not placed in the scene yet: maps to no scene mesh, so a sync swaps nothing for it until it is placed"
    for p, mt in (plan["same_shape_newer_file"] if plan else {}).items():   # saved again with the same shape: remember the time, so the next run skips the shape compare
        pieces[p]["source_mtime"] = mt
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
    return {"library": out, "manifest": mpath, **report, "pieces": len(pieces), "by_section": by_section,
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


def _append_mesh(lib_path, lib_mesh, lib_mats, first=None):
    """Append the library mesh (or a copy of the one already appended); its slots point at the scene's materials of the same name.
    Returns (mesh, names of the materials that came with it)."""
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
    return new, new_mats


def _swap_mesh(old, lib_path, lib_mesh, lib_mats, first):
    """Append the library mesh (or a copy of the one already appended) and put it under every user of `old`."""
    new, new_mats = _append_mesh(lib_path, lib_mesh, lib_mats, first)
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


# ---------------------------------------------------------------- join rows

SKIP_STATUS = {"superseded", "parked", "park", "tile_only"}
IDENT = re.compile(r"^[A-Za-z0-9_.:#\-]+$")


def _row_trs(row):
    s = row.get("scale")
    s = (s, s, s) if isinstance(s, (int, float)) else tuple(s or (1, 1, 1))
    return tuple(row["loc"]), Euler([math.radians(a) for a in (row.get("rot") or [0, 0, 0])], "XYZ"), s


def _row_matrix(row):
    loc, eul, s = _row_trs(row)
    return Matrix.Translation(loc) @ eul.to_matrix().to_4x4() @ Matrix.Diagonal((*s, 1))


def _same_matrix(a, b, tol=1e-4):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4)) < tol


def _slot_map(v):
    """{slot index: material name} from a row's `slots`: {"1": m}, [m, m] (by position) or "m" (slot 0)."""
    if not v:
        return {}
    if isinstance(v, str):
        return {0: v}
    if isinstance(v, list):
        return {i: m for i, m in enumerate(v) if m}
    return {int(k): m for k, m in v.items() if m}


def _counts():
    """Object, rendered mesh object and rendered triangle counts of the open scene (mesh data; modifiers are not counted)."""
    scene = bpy.context.scene
    in_layer = set(scene.view_layers[0].objects.keys())
    off = _render_off_collections(scene)
    cache, n, tris = {}, 0, 0
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.data is None or o.hide_render or o.name not in in_layer or all(c.name in off for c in o.users_collection):
            continue
        k = o.data.as_pointer()
        if k not in cache:
            lt = np.zeros(len(o.data.polygons), np.int32)
            o.data.polygons.foreach_get("loop_total", lt)
            cache[k] = int(np.clip(lt - 2, 0, None).sum())
        n += 1
        tris += cache[k]
    return {"objects": len(bpy.data.objects), "rendered_mesh_objects": n, "rendered_tris": tris, "meshes": len(bpy.data.meshes), "materials": len(bpy.data.materials)}


def _guard_digest(skip_collections):
    """Hash of everything a join must not touch: cameras, lights, render and view settings, which collections are excluded or hidden."""
    sc, vl = bpy.context.scene, bpy.context.view_layer
    parts = []
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type not in ("CAMERA", "LIGHT"):
            continue
        d = o.data
        data = (d.lens, d.sensor_width, d.shift_x, d.shift_y, d.clip_start, d.clip_end, d.type) if o.type == "CAMERA" else (d.type, d.energy, tuple(d.color))
        parts.append((o.name, d.name, [round(x, 6) for r in o.matrix_world for x in r], o.hide_render, o.hide_viewport,
                      o.hide_get() if o.name in vl.objects else None, sorted(c.name for c in o.users_collection), [round(x, 6) if isinstance(x, float) else x for x in data]))
    r, vs = sc.render, sc.view_settings
    parts.append((r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.film_transparent, vs.view_transform, vs.look, vs.exposure, vs.gamma,
                  sc.display_settings.display_device, sc.camera.name if sc.camera else None, sc.world.name if sc.world else None,
                  sc.frame_start, sc.frame_end, getattr(getattr(sc, "cycles", None), "samples", None)))

    def walk(lc):
        if lc.name not in skip_collections:
            parts.append((lc.name, lc.exclude, lc.hide_viewport, lc.collection.hide_viewport, lc.collection.hide_render))
        for ch in lc.children:
            walk(ch)
    walk(vl.layer_collection)
    return hashlib.md5(repr(parts).encode()).hexdigest()


def _lane_collection(lane, parent):
    """COL_Lane_<lane> (lane-integration), a child of the collection `parent` (default: the scene collection)."""
    name = "COL_Lane_" + str(lane)
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        par = bpy.context.scene.collection
        if parent:
            par = bpy.data.collections.get(parent)
            if par is None:
                par = bpy.data.collections.new(parent)
                bpy.context.scene.collection.children.link(par)
        par.children.link(c)
    return c


def _material(name, joined_mats, joined):
    """The scene's material of that name, else the library's (appended once), else None."""
    m = bpy.data.materials.get(name)
    if m is None and name in joined_mats:
        with bpy.data.libraries.load(joined, link=False) as (src, dst):
            dst.materials = [name]
        m = dst.materials[0]
    return m


def _set_slots(ob, wanted, joined_mats, joined):
    """Per-object material overrides: slot link OBJECT, so objects keep sharing the mesh. Returns the problems."""
    problems = []
    for idx, name in wanted.items():
        if idx >= len(ob.material_slots):
            problems.append("slot %d: the piece has only %d slots" % (idx, len(ob.material_slots)))
            continue
        sl = ob.material_slots[idx]
        base = ob.data.materials[idx]
        if sl.link == 'DATA' and base is not None and base.name == name:
            continue
        if sl.link == 'OBJECT' and sl.material is not None and sl.material.name == name:
            continue
        m = _material(name, joined_mats, joined)
        if m is None:
            problems.append("slot %d: material '%s' is neither in the scene nor in the library" % (idx, name))
            continue
        sl.link = 'OBJECT'
        sl.material = m
    return problems


def _faces_on(ob, spec):
    """Polygons of ob whose vertices all lie on the plane {axis, at, tol} and inside the ranges in `between` ({axis: [lo, hi]})."""
    ax, tol = "xyz".index(spec["axis"]), spec.get("tol", 1e-3)
    rng = {"xyz".index(k): v for k, v in (spec.get("between") or {}).items()}
    mw, me = ob.matrix_world, ob.data
    out = []
    for p in me.polygons:
        pts = [mw @ me.vertices[v].co for v in p.vertices]
        if all(abs(q[ax] - spec["at"]) < tol for q in pts) and all(lo - 1e-6 <= q[i] <= hi + 1e-6 for q in pts for i, (lo, hi) in rng.items()):
            out.append(p.index)
    return out


def _is_shown(ob, vl):
    return ob.name in vl.objects and not ob.hide_render and not ob.hide_viewport and not ob.hide_get(view_layer=vl)


def join_rows(library, manifest, rows_file, apply=False, backup=None, report=None, skip_lanes=(), skip_no_uv=False, parent=None, phase=None, swap=True):
    """Join the placement rows of a rows file into the open scene. rows_file is json {"rows": [{lane, gate, master, loc, rot, scale, placed,
    why?, slots?, at_origin?, object?}], "gate_hidden": {gate object: [lanes]}, "gate_not_found": {name: [lanes]}, "swapped": {piece: n} or [pieces], "host_cuts": [...]}; a lane's
    own placement maps are read by the project's tool, never here. Per row a piece of the library (joined as sync does, so the user's edits count)
    is placed at the row's transform: one object per row, identical masters sharing one mesh. A gate object a row replaces is hidden
    (hide_render and hide_viewport, never deleted); gate meshes named like a built asset listed under `swapped` take the library mesh (sync's swap, `swap=False`
    leaves them). Without apply nothing changes. apply=True needs backup=<path>: a copy of the open scene saved there first. Saves nothing
    else; the caller saves. A rerun on the result changes nothing. Raises KitLibraryError, so the caller does not save, if a check fails."""
    if apply and not backup:
        raise KitLibraryError("apply needs backup=<path for a copy of this scene file>; nothing was changed")
    with open(manifest, encoding="utf-8") as f:
        man = json.load(f)
    if man.get("version") != VERSION:
        raise KitLibraryError("%s is an old-layout manifest; rebuild the library with build --migrate-from" % manifest)
    with open(rows_file, encoding="utf-8") as f:
        rj = json.load(f)
    rows, gate_hidden, host_cuts = rj["rows"], rj.get("gate_hidden") or {}, rj.get("host_cuts") or []
    swap_names = set(rj.get("swapped") or []) if swap else set()   # the project says which built assets replace the gate meshes of the same name
    skip_lanes = set(skip_lanes)
    vl = bpy.context.view_layer
    seen = {}
    for i, r in enumerate(rows):   # a row's key survives a regenerated file: lane, gate, master and how many equal rows came before it
        k = "%s|%s|%s" % (r.get("lane"), r.get("gate"), r.get("master"))
        seen[k] = seen.get(k, 0) + 1
        r["_key"], r["_n"] = "%s|%d" % (k, seen[k]), i + 1
    rep = {"library": library, "manifest": manifest, "rows_file": rows_file, "apply": bool(apply), "skip_lanes": sorted(skip_lanes), "rows": [], "pieces": {},
           "hides": [], "swaps": [], "host_cuts": [], "flags": [], "orphans": [], "summary": {}}
    jt = tempfile.mkdtemp(prefix="kit_rows_")
    try:
        lib, joined = library_join(library, list(man["pieces"]), jt)
        with bpy.data.libraries.load(joined, link=False) as (src, _):
            joined_mats = set(src.materials)
        have = {o["kit_row"]: o for o in bpy.data.objects if "kit_row" in o}
        pmesh = {m["kit_piece"]: m for m in bpy.data.meshes if "kit_piece" in m}
        users = scan_scene()
        hashes = {}

        def shash(me):
            if me.name not in hashes:
                hashes[me.name] = mesh_info(me)["hash"]
            return hashes[me.name]

        # ---- rows
        todo, counts = [], {}
        for r in rows:
            e = {"key": r["_key"], "lane": r.get("lane"), "gate": r.get("gate"), "master": r.get("master"), "piece": None}
            m, why = r.get("master"), None
            if not r.get("placed"):
                e["action"], why = "skip", r.get("why") or "the row is not placed"
            elif str(r.get("status") or "").lower() in SKIP_STATUS:
                e["action"], why = "skip", "row status is %s" % r["status"]
            elif r.get("lane") in skip_lanes:
                e["action"], why = "skip", "lane left out (--skip-lanes)"
            elif m not in man["pieces"]:
                e["action"], why = "skip", "piece '%s' is not in the library: build it first" % m
            elif "hash" not in lib[m]:
                e["action"], why = "skip", "library piece '%s': %s" % (m, lib[m]["status"])
            elif skip_no_uv and lib[m]["uv_layers"] == 0:
                e["action"], why = "skip", "piece has no UV map (--skip-no-uv)"
            elif r.get("loc") is None:
                e["action"], why = "skip", "no location in the row"
            elif max(abs(c) for c in r["loc"]) < 1e-3 and not r.get("at_origin"):
                e["action"], why = "skip", "location is the world origin and the row does not say at_origin"
            else:
                M, wanted, o = _row_matrix(r), _slot_map(r.get("slots")), have.get(r["_key"])
                warn = ["slot %d: the piece has only %d slots, the override is left out" % (i, len(lib[m]["materials"])) for i in sorted(wanted) if i >= len(lib[m]["materials"])]
                warn += ["slot %d: material '%s' is neither in the scene nor in the library, the override is left out" % (i, n) for i, n in sorted(wanted.items())
                         if i < len(lib[m]["materials"]) and n not in bpy.data.materials and n not in joined_mats]
                wanted = {i: n for i, n in wanted.items() if i < len(lib[m]["materials"]) and (n in bpy.data.materials or n in joined_mats)}
                if warn:
                    e["warnings"] = warn
                if o is None:
                    e["action"] = "add"
                else:
                    ok = _same_matrix(o.matrix_world, M) and o.data is pmesh.get(m) and o.get("kit_piece") == m
                    for i, n in wanted.items():
                        if i < len(o.material_slots):
                            sl, base = o.material_slots[i], o.data.materials[i]
                            ok = ok and ((sl.link == 'OBJECT' and sl.material is not None and sl.material.name == n) or (sl.link == 'DATA' and base is not None and base.name == n))
                    e["action"] = "keep" if ok else "move"
                if wanted:
                    e["slots"] = {str(i): n for i, n in wanted.items()}
                todo.append((r, e, M, wanted))
                e["piece"] = m
            if why:
                e["why"] = why
            counts[e["action"]] = counts.get(e["action"], 0) + 1
            rep["rows"].append(e)
        planned = [e for e in rep["rows"] if e["action"] != "skip"]
        keys = {e["key"] for e in planned}
        rep["orphans"] = sorted(o.name for k, o in have.items() if k not in keys)   # placed by an earlier run, no longer wanted: left as they are
        # ---- gate objects to hide
        for g, lanes in sorted(gate_hidden.items()):
            ob = bpy.data.objects.get(g)
            h = {"gate": g, "lanes": lanes, "action": "hide"}
            if all(l in skip_lanes for l in lanes):
                h["action"], h["why"] = "skip", "every lane that replaces it is left out"
            elif ob is None:
                h["action"], h["why"] = "skip", "no such object in this file"
            elif "kit_row" in ob:
                h["action"], h["why"] = "skip", "it is a placed kit object"
            elif ob.name not in vl.objects:
                h["action"], h["why"] = "skip", "already out of the view layer (parked)"
            elif ob.hide_render and ob.hide_viewport:
                h["action"], h["why"] = "skip", "already hidden"
            rep["hides"].append(h)
        hide_set = {h["gate"] for h in rep["hides"] if h["action"] == "hide"}
        # ---- pieces: the library mesh in the scene (reused while its hash is current); gate meshes named like an asset take it
        try:   # an entry without source_mtime (an older library) is compared with the time the library was first built
            first_built = datetime.datetime.fromisoformat(man.get("built", "")).timestamp()
        except ValueError:
            first_built = 0.0
        needed = {e["piece"] for e in planned}
        shadowed = []
        for p, ent in man["pieces"].items():
            is_asset = ent.get("source") == "asset"
            if not is_asset and os.path.isfile(os.path.join(man.get("assets_dir") or "", p, p + ".blend")):   # build never replaces a piece
                shadowed.append("%s (%d objects%s)" % (p, sum(users.get(n, {}).get("objects", 0) for sm in ent.get("src_meshes", []) for n in scene_matches(users, sm)),
                                                     ", edited in the library" if "hash" in lib[p] and lib[p]["hash"] != ent["hash"] else ""))
            if "hash" not in lib[p] or not (is_asset or p in needed):
                continue
            pm = pmesh.get(p)
            mapped = [bpy.data.meshes[n] for sm in ent.get("src_meshes", []) for n in scene_matches(users, sm)]
            others, blocked = [], []
            for me in {m.name: m for m in mapped}.values():
                if me is not pm and is_asset and p in swap_names and shash(me) != lib[p]["hash"] and any(_is_shown(o, vl) and o.name not in hide_set for o in users.get(me.name, {}).get("objs", [])):
                    (blocked if (me.library is not None or me.shape_keys is not None) else others).append(me)   # a mesh only hidden objects use is left as it is
            adopt = next((me for me in mapped if me is not pm and shash(me) == lib[p]["hash"]), None) if pm is None else None
            act = ("keep" if pm.get("kit_hash") == lib[p]["hash"] else "update") if pm is not None else "adopt" if adopt is not None else "swap" if others else "append"
            if act == "keep" and not others:
                continue
            if act == "append" and p not in needed:
                continue
            rec = {"action": act, "rows": sum(1 for e in planned if e["piece"] == p), "tris": lib[p]["tris"], "uv_layers": lib[p]["uv_layers"], "library_edited": lib[p]["hash"] != ent["hash"],
                   "scene_meshes": sorted(m.name for m in others), "scene_objects": sum(users.get(m.name, {}).get("objects", 0) for m in others), "warnings": []}
            for b in blocked:
                rec["warnings"].append("scene mesh %s is %s: not swapped" % (b.name, "linked from another file" if b.library else "has shape keys"))
            if is_asset and ent.get("source_file") and os.path.isfile(ent["source_file"]) and os.path.getmtime(ent["source_file"]) > (ent.get("source_mtime") or first_built) + 2:
                rec["warnings"].append("the asset file was saved after this piece was built from it: the library holds the older shape (build never replaces a piece)")
            if p in needed and lib[p]["uv_layers"] == 0:
                rec["warnings"].append("the piece has no UV map")
            rep["pieces"][p] = rec
            rep["swaps"] += [{"piece": p, "mesh": m.name, "objects": users.get(m.name, {}).get("objects", 0)} for m in others]
        if shadowed:
            rep["flags"].append("%d pieces are the scene's own mesh and an asset file of the same name exists; build never replaces a piece, so a newer asset is not in the library "
                                "(compare them): %s" % (len(shadowed), ", ".join(shadowed)))
        # ---- gate names no object carries: new pieces are expected, anything else is flagged
        placed_gates = {str(e["gate"]) for e in planned}
        nf = {"total": 0, "new_piece": 0, "own_id_row": 0}
        for g, lanes in sorted((rj.get("gate_not_found") or {}).items()):
            nf["total"] += 1
            if g.startswith("new:"):
                nf["new_piece"] += 1
            elif g in placed_gates and IDENT.match(g):
                nf["own_id_row"] += 1
            else:
                rep["flags"].append("gate '%s' (%s) is no object in the source file and no clean row id: check the name" % (g, ", ".join(lanes)))
        rep["gate_not_found"] = nf
        claimed = {}
        for e in planned:
            if e["gate"]:
                claimed.setdefault(str(e["gate"]), set()).add(e["lane"])
        rep["claimed_by_two_lanes"] = {g: {"lanes": sorted(ls), "rows": sum(1 for e in planned if str(e["gate"]) == g), "hide": next((h["action"] for h in rep["hides"] if h["gate"] == g), "no hide listed")}
                                       for g, ls in claimed.items() if len(ls) > 1}
        # ---- host cuts: only on an object that stays shown
        for c in host_cuts:
            ob = bpy.data.objects.get(c["object"])
            hid = any(h["gate"] == c["object"] and h["action"] == "hide" for h in rep["hides"])
            shown = ob is not None and _is_shown(ob, vl) and not hid
            faces = len(_faces_on(ob, c["faces"])) if ob is not None and ob.type == 'MESH' else 0
            rec = {"object": c["object"], "faces": faces, "shown": shown, "why": c.get("why"), "action": "cut"}
            if c.get("only_if") not in (None, "object_shown"):
                rec["action"], rec["reason"] = "skip", "unsupported only_if %r" % c["only_if"]
            elif ob is None:
                rec["action"], rec["reason"] = "skip", "no such object in this file"
            elif c.get("only_if") == "object_shown" and not shown:
                rec["action"], rec["reason"] = "skip", "the object is hidden, so the cut would change nothing anyone sees"
            elif not faces:
                rec["action"], rec["reason"] = "skip", "no face matches (already cut, or the object changed)"
            rep["host_cuts"].append(rec)
        rep["before"] = _counts()
        lane_cols = {"COL_Lane_" + str(e["lane"]) for e in planned} | ({parent} if parent else set())
        guard = _guard_digest(lane_cols)
        # ---- apply
        if apply:
            if os.path.exists(backup):
                raise KitLibraryError("backup %s exists already; give a new path. Nothing was changed" % backup)
            os.makedirs(os.path.dirname(os.path.abspath(backup)), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(backup), copy=True, compress=False)
            rep["scene_backup"] = os.path.abspath(backup)
            for p, rec in rep["pieces"].items():
                now, ent, pm = lib[p], man["pieces"][p], pmesh.get(p)
                olds = [bpy.data.meshes[n] for n in rec["scene_meshes"] if n in bpy.data.meshes]
                if rec["action"] == "update":
                    pm, rec["new_materials"] = _swap_mesh(pm, joined, now["mesh"], now["materials"], None)
                elif rec["action"] == "adopt":
                    pm = next(bpy.data.meshes[n] for sm in ent.get("src_meshes", []) for n in scene_matches(users, sm) if shash(bpy.data.meshes[n]) == now["hash"])
                elif rec["action"] in ("swap", "append"):
                    pm, rec["new_materials"] = _append_mesh(joined, now["mesh"], now["materials"])
                for old in olds:   # gate meshes named like the asset: every user takes the library mesh
                    for k in old.keys():
                        if k not in pm.keys():
                            pm[k] = old[k]
                    old.user_remap(pm)
                    old.use_fake_user = False
                    if old.users == 0:
                        bpy.data.meshes.remove(old)
                if rec["action"] != "update" and pm.name != p:
                    pm.name = p if p not in bpy.data.meshes else "KP_" + p
                pm.use_fake_user = False
                pm["kit_piece"], pm["kit_hash"] = p, now["hash"]
                pmesh[p] = pm
            for r, e, M, wanted in todo:
                p, o = e["piece"], have.get(r["_key"])
                if o is None:
                    name = r.get("object") if r.get("object") and r["object"] not in bpy.data.objects else "%s.%s.%04d" % (p, r.get("lane"), r["_n"])
                    o = bpy.data.objects.new(name, pmesh[p])
                    _lane_collection(r.get("lane"), parent).objects.link(o)
                    o["kit_row"], o["kit_lane"], o["kit_gate"] = r["_key"], str(r.get("lane")), str(r.get("gate"))
                    if phase:
                        o["phase"] = phase
                    have[r["_key"]] = o
                if o.data is not pmesh[p]:
                    o.data = pmesh[p]
                o["kit_piece"] = p
                o.location, o.rotation_euler, o.scale = _row_trs(r)
                if wanted:
                    e.setdefault("warnings", []).extend(_set_slots(o, wanted, joined_mats, joined))
            bpy.context.view_layer.update()
            for h in rep["hides"]:
                if h["action"] == "hide":
                    ob = bpy.data.objects[h["gate"]]
                    ob.hide_render = ob.hide_viewport = True
                    ob["kit_join_hidden"] = ",".join(h["lanes"])
            for c in rep["host_cuts"]:
                if c["action"] == "cut":
                    import bmesh
                    ob = bpy.data.objects[c["object"]]
                    kill = _faces_on(ob, next(x for x in host_cuts if x["object"] == c["object"])["faces"])
                    old = ob.data
                    new = old.copy()
                    bm = bmesh.new()
                    bm.from_mesh(new)
                    bm.faces.ensure_lookup_table()
                    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in kill], context="FACES")
                    bm.to_mesh(new)
                    bm.free()
                    base = old.name
                    old.name, old.use_fake_user = base + ".pre_cut", True   # the faces come back by putting this mesh under the object again
                    new.name = base
                    ob.data = new
                    ob["kit_cut_from"] = old.name
                    c["cut_faces"] = len(kill)
            rep["after"] = _counts()
            # ---- checks: a failure raises, so the caller does not save
            bad = []
            mine = [have[r["_key"]] for r, _, _, _ in todo]
            if len(mine) != len(planned) or len({o.name for o in mine}) != len(planned):
                bad.append("placed objects (%d) are not the rows' placed count (%d)" % (len(mine), len(planned)))
            for (r, e, M, w), o in zip(todo, mine):
                if (not _same_matrix(o.matrix_world, M)) or (o.matrix_world.translation.length < 1e-3 and not r.get("at_origin")):
                    bad.append("%s is not at its row's transform" % o.name)
                if any(s.material is None for s in o.material_slots) or (len(o.data.polygons) and max(p.material_index for p in o.data.polygons) >= len(o.material_slots)):
                    bad.append("%s has an empty or missing material slot" % o.name)
            dup = [m.name for m in bpy.data.materials if re.search(r"\.\d{3}$", m.name) and re.sub(r"\.\d{3}$", "", m.name) in bpy.data.materials]
            if dup:
                bad.append("duplicate materials: %s" % dup[:10])
            if _guard_digest(lane_cols) != guard:
                bad.append("cameras, lights, render or view settings or a collection's exclusion changed")
            rep["checks"] = {"rows_placed": len(planned), "objects_placed": len(mine), "failures": bad}
            if bad:
                raise KitLibraryError("join checks failed, do not save:\n  " + "\n  ".join(bad[:20]))
    finally:
        shutil.rmtree(jt, ignore_errors=True)
    rep["summary"] = {"rows": len(rows), **{"rows_" + k: v for k, v in sorted(counts.items())}, "orphans": len(rep["orphans"]),
                      "pieces_new_in_scene": sum(1 for r in rep["pieces"].values() if r["action"] in ("append", "swap", "adopt")),
                      "pieces_updated": sum(1 for r in rep["pieces"].values() if r["action"] == "update"), "pieces_edited_in_library": sum(1 for r in rep["pieces"].values() if r["library_edited"]),
                      "gate_meshes_swapped": len(rep["swaps"]), "gate_objects_swapped": sum(s["objects"] for s in rep["swaps"]),
                      "hide": sum(1 for h in rep["hides"] if h["action"] == "hide"), "hide_skipped": sum(1 for h in rep["hides"] if h["action"] == "skip"),
                      "slot_overrides": sum(1 for e in rep["rows"] if e.get("slots") and e["action"] != "skip"),
                      "host_cuts": sum(1 for c in rep["host_cuts"] if c["action"] == "cut"), "flags": len(rep["flags"]),
                      "warnings": sum(len(r["warnings"]) for r in rep["pieces"].values()) + sum(len(e.get("warnings", [])) for e in rep["rows"])}
    if report:
        with open(report, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    return rep


def _rows_lines(rep):
    out, why = [], {}
    for e in rep["rows"]:
        if e["action"] == "skip":
            why.setdefault((str(e["lane"]), e["why"]), []).append(e["key"])
    out += ["skip %s: %d rows: %s" % (lane, len(k), w) for (lane, w), k in sorted(why.items())]
    out += ["swap %s: mesh %s, %d objects" % (s["piece"], s["mesh"], s["objects"]) for s in rep["swaps"]]
    out += ["hide skipped %s: %s" % (h["gate"], h["why"]) for h in rep["hides"] if h["action"] == "skip"][:40]
    out += ["claimed by %s: %s, %d rows, hide: %s" % (" and ".join(v["lanes"]), g, v["rows"], v["hide"]) for g, v in rep["claimed_by_two_lanes"].items()]
    out += ["host cut %s: %d faces, shown %s: %s" % (c["object"], c["faces"], c["shown"], c.get("reason") or c["action"]) for c in rep["host_cuts"]]
    out += ["warn piece %s: %s" % (p, w) for p, r in rep["pieces"].items() for w in r["warnings"]]
    out += ["warn row %s: %s" % (e["key"], w) for e in rep["rows"] for w in e.get("warnings", [])]
    out += ["orphan " + o for o in rep["orphans"]]
    out += ["FLAG " + f for f in rep["flags"]]
    out.append("gate_not_found %s" % json.dumps(rep["gate_not_found"]))
    out.append("objects before %(objects)d, rendered %(rendered_mesh_objects)d, tris %(rendered_tris)d" % rep["before"])
    if rep.get("after"):
        out.append("objects after  %(objects)d, rendered %(rendered_mesh_objects)d, tris %(rendered_tris)d" % rep["after"])
        out.append("checks " + json.dumps(rep["checks"]))
    if rep.get("scene_backup"):
        out.append("scene_backup " + rep["scene_backup"])
    return out


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
    b.add_argument("--refresh", nargs="*", metavar="PIECE", help="replace stale, unedited pieces with a fresh copy of their asset (no names: every piece); pieces the user edited are kept")
    b.add_argument("--dry-run", action="store_true", help="print what would be added, replaced and kept; write nothing")
    b.add_argument("--exclude", nargs="*", default=[], metavar="NAME", help="assets or pieces to keep out of the library")
    b.add_argument("--exclude-from", help="a file of names to keep out: a json list, a json object with an \"assets\" object (a batch report), or one name per line")
    s = sub.add_parser("sync")
    s.add_argument("--library", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--apply", action="store_true")
    s.add_argument("--backup", help="path for a copy of the open scene, saved before --apply changes anything (required with --apply)")
    s.add_argument("--report")
    s.add_argument("--save-as", help="save the scene here after --apply (the caller's save, for a headless run)")
    jr = sub.add_parser("join-rows")
    jr.add_argument("--library", required=True)
    jr.add_argument("--manifest", required=True)
    jr.add_argument("--rows", required=True, help="a rows file: rows with lane, gate, master, loc, rot, scale, placed; gate_hidden; host_cuts")
    jr.add_argument("--apply", action="store_true")
    jr.add_argument("--backup", help="path for a copy of the open scene, saved before --apply changes anything (required with --apply)")
    jr.add_argument("--report")
    jr.add_argument("--save-as", help="save the scene here after --apply (the caller's save, for a headless run)")
    jr.add_argument("--skip-lanes", default="", help="comma list of lanes to leave out (their rows are skipped and the gate objects only they replace stay)")
    jr.add_argument("--skip-no-uv", action="store_true", help="leave out rows whose piece has no UV map")
    jr.add_argument("--parent", help="collection that holds the COL_Lane_<lane> collections (created if missing; default the scene collection)")
    jr.add_argument("--phase", help="value for the `phase` custom property of every object it creates")
    jr.add_argument("--no-swap", action="store_true", help="do not give gate meshes named like a built asset the library mesh")
    f = sub.add_parser("fresh")
    f.add_argument("--spec", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--joined", required=True)
    j = sub.add_parser("join")
    j.add_argument("--pieces-file", required=True)
    j.add_argument("--out", required=True)
    j.add_argument("--blend", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "join":
        _cmd_join(a.pieces_file, a.out, a.blend)
        return 0
    if a.cmd == "fresh":
        _cmd_fresh(a.spec, a.out, a.joined)
        return 0
    if a.cmd == "build":
        res = build(os.path.abspath(a.scene), os.path.abspath(a.assets_dir), os.path.abspath(a.out), a.families_min,
                    os.path.abspath(a.specs_dir) if a.specs_dir else None, os.path.abspath(a.migrate_from) if a.migrate_from else None,
                    a.refresh, a.dry_run, list(a.exclude) + (read_names(a.exclude_from) if a.exclude_from else []))
        rf = res.get("refresh")
        if rf:
            print(chr(10).join(["replace %s: %s" % kv for kv in sorted(rf["replace"].items())] + ["kept_user_edit %s: %s" % kv for kv in sorted(rf["kept_user_edit"].items())]
                             + ["unchecked %s: %s" % kv for kv in sorted(rf["unchecked"].items())]))
            print("KIT_REFRESH", json.dumps({"dry_run": bool(a.dry_run), "replace": len(rf["replace"]), "kept_user_edit": len(rf["kept_user_edit"]), "current": rf["current"],
                                             "unchecked": len(rf["unchecked"]), "add": len(res["added"])}))
        print("KIT_LIBRARY", json.dumps(res))
        return 0
    if a.cmd == "join-rows":
        rep = join_rows(os.path.abspath(a.library), os.path.abspath(a.manifest), os.path.abspath(a.rows), a.apply, os.path.abspath(a.backup) if a.backup else None,
                        os.path.abspath(a.report) if a.report else None, [x for x in a.skip_lanes.split(",") if x], a.skip_no_uv, a.parent, a.phase, not a.no_swap)
        for line in _rows_lines(rep):
            print(line)
        if a.apply and a.save_as:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save_as), compress=False)
        print("KIT_JOIN", json.dumps({"apply": rep["apply"], **rep["summary"]}))
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
