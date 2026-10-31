"""Kit library: every kit piece in one editable .blend, and a sync that puts the edited pieces back into a scene.

Run inside Blender (headless: bash bin/blender-bg [file.blend] --python this_file -- <command> <args>):

  build --scene <blend> --assets-dir <dir> --out <library.blend> [--families-min 2] [--specs-dir <kit specs>] [--previews]
      One collection per piece in <library.blend>: the master mesh object, its UCX_ proxies, SOCKET_ empties and variants,
      laid out in rows with a text label, every master and variant marked as an asset (spec id as tag and description).
      Sources: (a) every <assets-dir>/<asset>/<asset>.blend; (b) the scene's own instance families, which are the mesh
      datablocks used by --families-min or more rendered objects (one-offs, cable and pipe runs, curves, wear and
      parked objects are skipped). Writes <library.blend>.manifest.json: per piece its source, the scene mesh datablocks
      it maps to, the object counts and a geometry hash per mesh. Re-running keeps every existing piece and its edits and
      appends only the new ones (their hashes are never refreshed, so a pending edit stays pending).

  sync --library <library.blend> --manifest <json> [--apply] [--report <json>] [--save-as <blend>]
      Run on a scene file. Re-hashes the library (in a second background Blender), and for each changed piece swaps the new
      mesh into every scene object that uses the mapped mesh datablock. Transform, name, custom properties and modifiers
      stay; material slots point at the SCENE's materials of the same name (a name the scene lacks is appended and listed).
      Without --apply it only reports. With --apply it also updates the manifest hashes. The sync() function saves nothing;
      --save-as is the caller's save, for a headless run.

Hash of a mesh: vertex positions rounded to 0.1 mm, loop vertex indices and polygon sizes, smooth flags, UV values and
material names per slot. Object transforms do not count (the library layout moves objects freely).
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
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_NAME_PREFIX = ("SM_Pipe_Run_", "CBL_")
WEAR_TOKENS = {"grime", "grimy", "stain", "stains", "drip", "drips", "leak", "leaks", "rust", "rusty", "crack", "cracks", "chip", "chips",
               "dent", "dents", "peel", "peeling", "decal", "decals", "dirt", "dirty", "mold", "mould", "mildew", "streak", "streaks",
               "tidemark"}
WARN_MM = 1.0
ROW_WIDTH_M = 12.0
GAP_M = 0.4


class KitLibraryError(Exception):
    pass


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
        if o.type in {'MESH', 'CURVE', 'FONT'}:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        else:
            pts.append(o.matrix_world.translation.copy())
    if not pts:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (Vector((min(p[i] for p in pts) for i in range(3))), Vector((max(p[i] for p in pts) for i in range(3))))


def _roles(piece, mesh_objs):
    """object name -> master | variant | collision."""
    named = any(o.name == piece for o in mesh_objs)
    out = {}
    for o in mesh_objs:
        if o.name.startswith("UCX_"):
            out[o.name] = "collision"
        elif named and o.name != piece:
            out[o.name] = "variant"
        else:
            out[o.name] = "master"
    return out


def _mark_asset(ob, piece, role, spec_id, spec_file, previews):
    ob["kit_piece"], ob["kit_role"], ob["spec_id"] = piece, role, spec_id
    ob.asset_mark()
    ad = ob.asset_data
    ad.description = "spec %s (%s of %s)" % (spec_id, role, piece)
    ad.tags.new("spec:" + spec_id, skip_if_exists=True)
    ad.tags.new(role, skip_if_exists=True)
    if previews:
        try:
            ob.asset_generate_preview()
        except Exception as e:  # a preview is a convenience
            print("kit_library: no preview for", ob.name, repr(e))


def _add_label(col, piece, bb_min, bb_max):
    width = max(bb_max.x - bb_min.x, 0.05)
    size = min(0.12, max(0.04, width * 0.2))
    cu = bpy.data.curves.new("LBL_" + piece, 'FONT')
    cu.body, cu.size, cu.align_x, cu.align_y = piece, size, 'CENTER', 'TOP'
    ob = bpy.data.objects.new("LBL_" + piece, cu)
    ob.location = ((bb_min.x + bb_max.x) / 2, bb_min.y - 0.05, 0.0)
    ob["kit_role"] = "label"
    col.objects.link(ob)
    return size


class _Layout:
    """Row packing in plan view: rows go down (-Y) from below everything already in the file."""

    def __init__(self):
        bpy.context.view_layer.update()
        ys = []
        for o in bpy.data.objects:
            lo, _ = _world_bbox([o])
            ys.append(lo.y)
        self.row_top = (min(ys) - 1.0) if ys else 0.0
        self.x = 0.0
        self.row_h = 0.0

    def place(self, objs, col, piece):
        bpy.context.view_layer.update()
        mesh_like = [o for o in objs if o.type != 'FONT']
        lo, hi = _world_bbox(mesh_like)
        w, d = hi.x - lo.x, hi.y - lo.y
        band = 0.25
        if self.x > 0 and self.x + w > ROW_WIDTH_M:
            self.row_top -= self.row_h + GAP_M
            self.x, self.row_h = 0.0, 0.0
        shift = Vector((self.x - lo.x, self.row_top - hi.y, 0.0))
        for o in objs:
            if o.parent is None:
                o.location = o.location + shift
        bpy.context.view_layer.update()
        lo, hi = _world_bbox(mesh_like)
        _add_label(col, piece, lo, hi)
        self.x += w + GAP_M
        self.row_h = max(self.row_h, d + band)


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
        if o.name != n:
            raise KitLibraryError("%s: object '%s' clashes with a name already in the library (got '%s')" % (piece, n, o.name))
        objs.append(o)
    if not objs:
        raise KitLibraryError("%s: no objects in %s" % (piece, path))
    return objs


def _new_piece_collection(piece):
    col = bpy.data.collections.new(piece)
    bpy.context.scene.collection.children.link(col)
    return col


def build(scene, assets_dir, out, families_min=2, specs_dir=None, previews=False):
    mpath = out + ".manifest.json"
    man = None
    if os.path.isfile(out):
        if not os.path.isfile(mpath):
            raise KitLibraryError("%s exists but %s does not; restore the manifest or build to a new file" % (out, mpath))
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
    pieces = man["pieces"] if man else {}

    # 1. the scene: instance families and the mapping of asset meshes onto scene meshes
    bpy.ops.wm.open_mainfile(filepath=scene)
    users = scan_scene()
    scene_hash = {}

    def shash(mesh_name):
        if mesh_name not in scene_hash:
            scene_hash[mesh_name] = mesh_info(bpy.data.meshes[mesh_name])
        return scene_hash[mesh_name]

    def scene_map(mesh_name):
        names = scene_matches(users, mesh_name)
        return {"scene_meshes": names, "scene_objects": sum(users[n]["objects"] for n in names),
                "scene_rendered": sum(users[n]["rendered"] for n in names), "_hashes": [shash(n)["hash"] for n in names]}

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

    new_assets = {n: p for n, p in asset_files.items() if n not in pieces}
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
        if mesh_name in pieces:
            continue
        families[mesh_name] = d
    tmp = tempfile.mkdtemp(prefix="kit_library_")
    fam_blend = os.path.join(tmp, "families.blend")
    if families:
        bpy.data.libraries.write(fam_blend, {bpy.data.meshes[n] for n in families}, compress=False)
    fam_info = {n: {"scene_" + k: v for k, v in (("objects", d["objects"]), ("rendered", d["rendered"]))} for n, d in families.items()}
    fam_hash = {n: shash(n)["hash"] for n in families}
    refresh = {p: {m: scene_map(v["mesh"]) for m, v in e["members"].items() if v.get("mesh")} for p, e in pieces.items()}
    scene_maps_cache = {}
    for n in list(new_assets):
        with bpy.data.libraries.load(new_assets[n], link=False) as (src, _):
            for mn in src.meshes:
                scene_maps_cache[mn] = scene_map(mn)

    # 2. the library: open the existing one or start empty
    if man:
        bpy.ops.wm.open_mainfile(filepath=out)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    layout = _Layout()
    added = []

    def finish_piece(piece, source, source_file, objs, col, extra_map):
        mesh_objs = [o for o in objs if o.type == 'MESH']
        roles = _roles(piece, mesh_objs)
        spec_id, spec_file = _read_spec_id(specs_dir, piece)
        layout.place(objs, col, piece)
        members = {}
        for o in sorted(mesh_objs, key=lambda x: x.name):
            info = mesh_info(o.data)
            sm = extra_map(o.data.name)
            members[o.name] = {"role": roles[o.name], "mesh": o.data.name, **info,
                               "scene_meshes": sm["scene_meshes"], "scene_objects": sm["scene_objects"],
                               "scene_rendered": sm["scene_rendered"],
                               "scene_hash_match": bool(sm["_hashes"]) and all(h == info["hash"] for h in sm["_hashes"])}
            if roles[o.name] in {"master", "variant"}:
                _mark_asset(o, piece, roles[o.name], spec_id, spec_file, previews)
        for o in objs:
            if o.type == 'EMPTY':
                members[o.name] = {"role": "socket" if o.name.startswith("SOCKET_") else "empty"}
        in_scene = any(v.get("scene_meshes") for v in members.values())
        entry = {"source": source, "source_file": source_file, "collection": col.name, "spec_id": spec_id, "spec_file": spec_file,
                 "in_scene": in_scene, "members": members}
        if not in_scene:
            entry["note"] = "not placed in the scene yet: maps to no scene mesh, so a sync swaps nothing for it until it is placed"
        pieces[piece] = entry
        added.append(piece)

    for piece, path in new_assets.items():
        snap = _snapshot()
        objs = _load_asset_objects(path, piece)
        col = _new_piece_collection(piece)
        for o in objs:
            col.objects.link(o)
        _dedupe_new(snap)
        finish_piece(piece, "asset", path, objs, col, lambda mn: scene_maps_cache.get(mn) or {"scene_meshes": [], "scene_objects": 0, "scene_rendered": 0, "_hashes": []})

    if families:
        snap = _snapshot()
        with bpy.data.libraries.load(fam_blend, link=False) as (src, dst):
            dst.meshes = [n for n in sorted(families) if n in src.meshes]
        for me in dst.meshes:
            if me is None:
                continue
            if me.name not in families:
                raise KitLibraryError("family mesh '%s' clashes with a name already in the library" % me.name)
        _dedupe_new(snap)
        for me in dst.meshes:
            if me is None:
                continue
            ob = bpy.data.objects.new(me.name, me)
            col = _new_piece_collection(me.name)
            col.objects.link(ob)
            d = families[me.name]
            smap = {"scene_meshes": [me.name], "scene_objects": d["objects"], "scene_rendered": d["rendered"], "_hashes": [fam_hash[me.name]]}
            finish_piece(me.name, "scene_family", scene, [ob], col, lambda mn, smap=smap: smap)
    shutil.rmtree(tmp, ignore_errors=True)

    for p, maps in refresh.items():   # kept pieces: refresh the scene mapping, never the baseline hashes
        for m, sm in maps.items():
            mem = pieces[p]["members"][m]
            mem.update({"scene_meshes": sm["scene_meshes"], "scene_objects": sm["scene_objects"], "scene_rendered": sm["scene_rendered"],
                        "scene_hash_match": bool(sm["_hashes"]) and all(h == mem["hash"] for h in sm["_hashes"])})
        pieces[p]["in_scene"] = any(v.get("scene_meshes") for v in pieces[p]["members"].values())

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    man = {"version": 1, "built": man["built"] if man else now, "updated": now, "scene": scene, "assets_dir": assets_dir,
           "families_min": families_min, "hash": "md5 of vertex positions at 0.1 mm, loops, polygon sizes, smooth flags, UVs, slot material names",
           "skipped_scene_meshes": skipped, "pieces": dict(sorted(pieces.items()))}
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    by_source = {}
    for p in pieces.values():
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
    return {"library": out, "manifest": mpath, "added": added, "pieces": len(pieces), "by_source": by_source,
            "not_in_scene": sorted(p for p, e in pieces.items() if not e["in_scene"]), "skipped_scene_meshes": skipped}


# ---------------------------------------------------------------- hash of a library (second Blender)

def library_hashes(library):
    """object name -> info for every mesh object in the library. Runs in a background Blender, so the caller's file stays clean."""
    fd, out = tempfile.mkstemp(suffix=".json", prefix="kit_hash_")
    os.close(fd)
    try:
        cmd = [bpy.app.binary_path, "--background", "--factory-startup", library, "--python", os.path.join(HERE, "kit_library.py"), "--",
               "hash", "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or os.path.getsize(out) == 0:
            raise KitLibraryError("could not hash the library:\n" + (r.stdout + r.stderr)[-1500:])
        with open(out, encoding="utf-8") as f:
            return json.load(f)
    finally:
        os.unlink(out)


def _cmd_hash(out):
    res = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data is not None:
            res[o.name] = {"mesh": o.data.name, **mesh_info(o.data), "scale": [round(v, 6) for v in o.scale],
                           "rotation": [round(v, 6) for v in o.rotation_euler]}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f)


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


def sync(library, manifest, apply=False, report=None):
    """Compare the library with the manifest and swap changed pieces into the open scene. Saves nothing (the caller saves)."""
    with open(manifest, encoding="utf-8") as f:
        man = json.load(f)
    lib = library_hashes(library)
    rep = {"library": library, "manifest": manifest, "apply": bool(apply), "pieces": [], "summary": {}}
    unchanged = 0
    first_new = {}   # (piece, member) -> mesh already appended
    for piece, entry in man["pieces"].items():
        for member, mem in entry["members"].items():
            if "hash" not in mem:
                continue
            now = lib.get(member)
            if now is None:
                rep["pieces"].append({"piece": piece, "member": member, "status": "missing_in_library", "warnings": ["object is gone from the library; nothing changed in the scene"]})
                continue
            if now["hash"] == mem["hash"]:
                unchanged += 1
                continue
            row = {"piece": piece, "member": member, "role": mem["role"], "scene_meshes": [], "objects": 0, "objects_sample": [],
                   "tris_before": mem["tris"], "tris_after": now["tris"], "bbox_before_m": mem["bbox_m"], "bbox_after_m": now["bbox_m"],
                   "warnings": [], "new_materials": [], "could_not_swap": []}
            if mem["role"] == "collision":
                row["status"] = "collision_changed"
                row["warnings"].append("collision proxy changed; it is not synced into the scene")
            else:
                meshes = [bpy.data.meshes[n] for n in mem.get("scene_meshes", []) if n in bpy.data.meshes]
                for n in mem.get("scene_meshes", []):
                    if n not in bpy.data.meshes:
                        row["could_not_swap"].append({"mesh": n, "reason": "mesh datablock is not in this scene file"})
                row["scene_meshes"] = [m.name for m in meshes]
                objs = []
                for me in meshes:
                    if me.library is not None or me.shape_keys is not None:
                        row["could_not_swap"].append({"mesh": me.name, "reason": "linked from another file" if me.library else "has shape keys"})
                        continue
                    objs += [o for o in bpy.data.objects if o.type == 'MESH' and o.data is me]
                row["objects"] = len(objs)
                row["objects_sample"] = [o.name for o in objs[:20]]
                if meshes:
                    cur = mesh_info(meshes[0])
                    row.update({"tris_before": cur["tris"], "bbox_before_m": cur["bbox_m"]})
                row["status"] = "would_swap" if objs else "changed_not_in_scene"
                d = _delta(row["bbox_before_m"], now["bbox_m"])
                row.update(d)
                if d["worst_mm"] > WARN_MM:
                    if d["pure_shift"]:
                        row["warnings"].append("origin moved: the whole mesh shifts %.1f mm against the pivot, so every instance moves (above %.0f mm)" % (d["worst_mm"], WARN_MM))
                    else:
                        row["warnings"].append("bbox changes by up to %.1f mm (above %.0f mm): every instance changes" % (d["worst_mm"], WARN_MM))
                if any(abs(v - 1) > 1e-6 for v in now["scale"]) or any(abs(v) > 1e-6 for v in now["rotation"]):
                    row["warnings"].append("the library object has a scale or rotation; only its mesh is synced, so that transform is ignored")
                row["new_materials"] = sorted({m for m in now["materials"] if m and m not in bpy.data.materials})
                for o in objs:
                    if any(s.link == 'OBJECT' for s in o.material_slots):
                        row["warnings"].append("%s has object-linked material slots; check them after the swap" % o.name)
                        break
                if apply and meshes and objs:
                    added = []
                    for me in meshes:
                        if me.library is not None or me.shape_keys is not None:
                            continue
                        new, nm = _swap_mesh(me, library, now["mesh"], now["materials"], first_new.get((piece, member)))
                        first_new.setdefault((piece, member), new)
                        added += nm
                    row["status"] = "swapped"
                    row["new_materials"] = sorted(set(added))
            if apply and (row["status"] in {"swapped", "changed_not_in_scene", "collision_changed"}):
                mem.update({k: now[k] for k in ("hash", "verts", "polys", "tris", "bbox_m", "materials")})
                if row["status"] == "swapped":
                    mem["scene_hash_match"] = True
            rep["pieces"].append(row)
    swapped = [r for r in rep["pieces"] if r["status"] in {"swapped", "would_swap"}]
    rep["summary"] = {"pieces_changed": len(rep["pieces"]), "unchanged_members": unchanged,
                      "objects": sum(r["objects"] for r in swapped), "warnings": sum(len(r["warnings"]) for r in rep["pieces"]),
                      "could_not_swap": sum(len(r["could_not_swap"]) for r in rep["pieces"] if "could_not_swap" in r)}
    if apply:
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
        out.append("%s %s/%s: %s objects, tris %s -> %s, new materials %s" % (
            r["status"], r["piece"], r["member"], r.get("objects", 0), r.get("tris_before"), r.get("tris_after"), r.get("new_materials", [])))
        out += ["  warn " + w for w in r["warnings"]]
        out += ["  could not swap %s: %s" % (c.get("object") or c.get("mesh"), c["reason"]) for c in r.get("could_not_swap", [])]
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
    b.add_argument("--previews", action="store_true", help="render asset-browser previews (slow)")
    s = sub.add_parser("sync")
    s.add_argument("--library", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--apply", action="store_true")
    s.add_argument("--report")
    s.add_argument("--save-as", help="save the scene here after --apply (the caller's save, for a headless run)")
    h = sub.add_parser("hash")
    h.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "hash":
        _cmd_hash(a.out)
        return 0
    if a.cmd == "build":
        res = build(os.path.abspath(a.scene), os.path.abspath(a.assets_dir), os.path.abspath(a.out), a.families_min,
                    os.path.abspath(a.specs_dir) if a.specs_dir else None, a.previews)
        print("KIT_LIBRARY", json.dumps(res))
        return 0
    rep = sync(os.path.abspath(a.library), os.path.abspath(a.manifest), a.apply, os.path.abspath(a.report) if a.report else None)
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
