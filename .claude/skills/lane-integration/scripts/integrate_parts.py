"""Join frozen lane part files into a copy of the gate file, one lane at a time, headless (tested with bpy 5.2.3).

    bash bin/blender-bg <gate_copy.blend> --python .claude/skills/lane-integration/scripts/integrate_parts.py -- \
        --parts <parts_dir> --lanes north,south --out <joined.blend> [--patches <live_patches.py>] \
        [--backup-dir <backups> --step join_entry] [--report <join.json>] [--mode append|link]
    python integrate_parts.py freeze --parts <parts_dir> --lanes north,south     # writes each part file's hash into its manifest
    bash bin/blender-bg <gate_copy.blend> --python <this file> -- replay --parts <parts_dir> --lanes fix_a,fix_b --out <merged.blend> \
        [--backup-dir <backups> --phase <phase> --step fixes]                    # fix lanes: applies each <lane>/patches.py in order

For each lane, in order: check the part file against the hash the lane froze, remove the lane's collection (and any
object carrying its `lane` property) from the copy, load the collection by name from the part file, point every material
slot at the gate file's material of the same name (never by slot index), place the manifest's instances, and assert.
Then it replays live_patches.py and asserts again. Exit 1 on any failed assert: the report lists them and nothing is saved.
The live worker applies the same fix lanes with replay_lanes(), which saves nothing and refuses a file the merge test didn't run.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

try:
    import bpy
    import numpy as np
    from mathutils import Vector
except ImportError:  # `freeze` needs no Blender
    bpy = None

DUP = re.compile(r"\.\d{3}$")
EPS = 1e-4
GEO = ("MESH", "CURVE", "SURFACE", "FONT")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def manifest_path(parts, lane):
    return os.path.join(parts, lane, "manifest.json")


def read_manifest(parts, lane):
    with open(manifest_path(parts, lane)) as f:
        m = json.load(f)
    m.setdefault("lane", lane)
    m.setdefault("collection", "COL_Lane_" + lane)  # blender-adapter names collections COL_*
    m.setdefault("part", lane + ".blend")
    m.setdefault("instances", [])
    return m


def part_path(parts, m):
    return os.path.join(parts, m["lane"], m["part"])


# ---------- freeze (plain Python) ----------

def freeze(parts, lanes):
    for lane in lanes:
        m = read_manifest(parts, lane)
        p = part_path(parts, m)
        m["frozen"] = {"sha256": sha256(p), "at": now()}
        with open(manifest_path(parts, lane), "w") as f:
            json.dump(m, f, indent=1)
        print(f"frozen {lane}: {m['frozen']['sha256'][:12]} {m['frozen']['at']}")


# ---------- helpers inside Blender ----------

def layer_col(name, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == name:
        return lc
    for c in lc.children:
        r = layer_col(name, c)
        if r:
            return r


def local_col(name):
    return next((c for c in bpy.data.collections if c.name == name and c.library is None), None)


def parents_of(col):
    ps = [c for c in bpy.data.collections if col.name in c.children and c.library is None]
    return ps + ([bpy.context.scene.collection] if col.name in bpy.context.scene.collection.children else [])


def wloc(o):
    """World location without trusting matrix_world, which stays at identity for new objects in a collection excluded from the view layer."""
    return o.location if o.parent is None else o.matrix_world.translation


def lane_objects(lane, col):
    objs = set(col.all_objects) if col else set()
    return objs | {o for o in bpy.data.objects if o.get("lane") == lane and o.library is None}


def remove_lane(lane, m, part):
    """Remove the lane's collection tree, every object tagged with the lane, and the data nothing else uses."""
    col, state = local_col(m["collection"]), {}
    if col:
        lc = layer_col(col.name)
        state = {"parents": [p.name for p in parents_of(col)], "hide_render": col.hide_render, "hide_viewport": col.hide_viewport,
                 "exclude": lc.exclude if lc else False, "lc_hide": lc.hide_viewport if lc else False}
    holders = [o for o in bpy.data.objects if o.get("lane_link") == lane and o.library is None]
    if holders and not state:
        state = {"parents": [c.name for c in holders[0].users_collection] or [bpy.context.scene.collection.name]}
    objs = lane_objects(lane, col) | set(holders)
    datas = {o.data for o in objs if o.data}
    n_obj = len(objs)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    n_col = 0
    for c in ([col] + list(col.children_recursive)) if col else []:
        bpy.data.collections.remove(c)
        n_col += 1
    bpy.data.batch_remove([d for d in datas if d.users == 0])
    for lib in list(bpy.data.libraries):  # a linked lane comes back fresh from the file
        if os.path.normcase(bpy.path.abspath(lib.filepath)) == os.path.normcase(os.path.abspath(part)):
            bpy.data.libraries.remove(lib)
    return {"objects": n_obj, "collections": n_col}, state


def load_lane(m, part, link, state):
    cname = m["collection"]
    with bpy.data.libraries.load(part, link=link) as (src, dst):
        if cname in src.collections:
            dst.collections = [cname]
    col = dst.collections[0] if dst.collections else None
    if col is None or col.name != cname:
        return None, None
    parent = state.get("parents") or ([m["parent"]] if m.get("parent") else [])
    targets = [local_col(n) or bpy.context.scene.collection for n in parent] or [bpy.context.scene.collection]
    home = targets[0]
    if link:  # a linked collection is shown through an instancing empty
        holder = bpy.data.objects.new("LINK_" + cname, None)
        holder.instance_type, holder.instance_collection = "COLLECTION", col
        holder["lane_link"] = m["lane"]
        home.objects.link(holder)
    else:
        home.children.link(col)
        home = col
        lc = layer_col(cname)
        if state.get("exclude") is not None and lc:
            col.hide_render, col.hide_viewport = state["hide_render"], state["hide_viewport"]
            lc.exclude, lc.hide_viewport = state["exclude"], state["lc_hide"]
    return col, home


def base_color(mat):
    p = mat.node_tree and next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return tuple(round(v, 3) for v in (p.inputs["Base Color"].default_value if p else mat.diffuse_color)[:3])


def remap_materials(before):
    """Point every new material at the gate file's material of the same base name. Returns remapped, new, drift."""
    remapped, new, drift = {}, [], []
    for mat in [x for x in bpy.data.materials if x.name not in before]:
        base = DUP.sub("", mat.name)
        keep = bpy.data.materials.get(base)
        if keep is not None and keep is not mat and keep.library is None and base in before:
            if base_color(keep) != base_color(mat):
                drift.append({"material": base, "gate": base_color(keep), "part": base_color(mat)})
            mat.user_remap(keep)
            remapped[mat.name] = base
            bpy.data.materials.remove(mat)
        else:
            new.append(mat.name)
    return remapped, new, drift


def slot_problems(objs):
    bad = {"empty_slot": [], "no_slot": [], "index_out_of_range": []}
    for o in sorted(objs, key=lambda x: x.name):
        if o.type not in GEO or o.hide_render:
            continue
        if any(s.material is None for s in o.material_slots):
            bad["empty_slot"].append(o.name)
        elif o.type == "MESH" and o.data.polygons:
            if not o.material_slots:
                bad["no_slot"].append(o.name)
                continue
            idx = np.empty(len(o.data.polygons), np.int32)
            o.data.polygons.foreach_get("material_index", idx)
            if idx.max() >= len(o.material_slots):
                bad["index_out_of_range"].append(o.name)
    return {k: v for k, v in bad.items() if v}


def place_instances(m, home):
    made, errs = [], []
    for row in m["instances"]:
        master = bpy.data.objects.get(row["master"])
        if master is None or master.data is None:
            errs.append(f"{row['name']}: master {row['master']} missing or has no data")
            continue
        if bpy.data.objects.get(row["name"]) is not None:
            errs.append(f"{row['name']}: name already used outside this lane")
            continue
        # shortcut: instances are unparented and share the master's mesh or curve data; add parenting when a lane needs it
        ob = bpy.data.objects.new(row["name"], master.data)
        ob.location = row["loc"]
        ob.rotation_euler = [x * 3.141592653589793 / 180 for x in row.get("rot_deg", [0, 0, 0])]
        ob.scale = row.get("scale", [1, 1, 1])
        tgt = local_col(row["collection"]) if row.get("collection") else home
        if tgt is None:
            tgt = bpy.context.scene.collection
            errs.append(f"{row['name']}: collection {row.get('collection')} not found")
        tgt.objects.link(ob)
        ob["lane"], ob["master"] = m["lane"], row["master"]
        for k, v in row.get("props", {}).items():
            ob[k] = v
        made.append(ob)
    return made, errs


def verify_lane(m, col, stage, rep, dups0=(), gate_mats=()):
    """Asserts that hold after the rebuild and again after the live patches."""
    lane, pre = m["lane"], m.get("id_prefix")
    bpy.context.view_layer.update()
    own = lane_objects(lane, col)
    ok = True

    def chk(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        rep["checks"].append({"stage": stage, "check": name, "ok": bool(passed), "detail": detail})

    names = sorted(o.name for o in own)
    chk("owns_objects", len(own) > 0, f"{len(own)} objects")
    if pre:
        chk("id_prefix", all(n.startswith(pre) for n in names), [n for n in names if not n.startswith(pre)][:10])
        chk("no_foreign_ids", not [o.name for o in bpy.data.objects if o.name.startswith(pre) and o not in own],
            [o.name for o in bpy.data.objects if o.name.startswith(pre) and o not in own][:10])
    chk("no_dup_suffix", not [n for n in names if DUP.search(n)], [n for n in names if DUP.search(n)][:10])
    dups = [x.name for x in bpy.data.materials if DUP.search(x.name) and x.library is None and x.name not in dups0]
    chk("no_new_dup_materials", not dups, dups[:10])  # names that were already suffixed before the join are not this lane's fault
    sp = slot_problems(own)
    chk("material_slots_filled", not sp, sp)
    # allowed: the manifest's own list, else the gate's materials plus the ones the manifest declares as new (the lane brief names them)
    allowed = set(m["materials"]) if m.get("materials") else {DUP.sub("", n) for n in gate_mats} | set(m.get("new_materials", []))
    used = {s.material.name for o in own if o.type in GEO for s in o.material_slots if s.material}
    chk("materials_allowed", used <= allowed, sorted(used - allowed))
    listed = {r["name"]: r for r in m["instances"]}
    missing = [n for n in listed if n not in bpy.data.objects]
    chk("instances_present", not missing, missing[:10])
    unlisted = [o.name for o in own if o.get("master") and o.name not in listed]
    chk("no_unlisted_instances", not unlisted, unlisted[:10])
    org = [o.name for o in own if o.get("master") and wloc(o).length < EPS and not listed.get(o.name, {}).get("at_origin")]
    chk("none_at_origin", not org, org[:10])
    if stage == "rebuilt":
        off = [n for n, r in listed.items() if n in bpy.data.objects
               and (Vector(wloc(bpy.data.objects[n])) - Vector(r["loc"])).length > EPS]
        chk("instances_at_manifest_loc", not off, off[:10])
        shared = [n for n, r in listed.items() if n in bpy.data.objects and bpy.data.objects.get(r["master"])
                  and bpy.data.objects[n].data is not bpy.data.objects[r["master"]].data]
        chk("instances_share_master_data", not shared, shared[:10])
    return ok


def geometry_hash(o, memo):
    """Mesh or curve points, shared data hashed once: a patch can move vertices by an offset as easily as an object."""
    if o.type not in ("MESH", "CURVE"):
        return None
    d = o.data
    if d.as_pointer() not in memo:
        seqs = [(d.vertices, 3)] if o.type == "MESH" else [(x.points, 4) for x in d.splines] + [(x.bezier_points, 3) for x in d.splines]
        h = hashlib.sha256()
        for seq, n in seqs:
            co = np.empty(len(seq) * n, np.float32)
            seq.foreach_get("co", co)
            h.update(co.tobytes())
        memo[d.as_pointer()] = h.hexdigest()
    return memo[d.as_pointer()]


def state_rows(objs):
    """What a patch can change, per object. Two of these make the repeat test; the difference from before is the patch's `changed` list."""
    memo = {}
    return {o.name: (tuple(round(v, 5) for row in o.matrix_basis for v in row), o.parent.name if o.parent else None,
                     tuple(s.material.name if s.material else None for s in o.material_slots), o.hide_render, o.hide_viewport,
                     sorted(c.name for c in o.users_collection), sorted((k, repr(o[k])) for k in o.keys()),
                     [(m.name, m.type) for m in o.modifiers], geometry_hash(o, memo)) for o in objs}


def replay_patches(path, lanes, objs, linked=()):
    """Replay a patch file in file order, each patch checked for repeatability. lanes=None runs all of it."""
    out, ns, patches = [], {"bpy": bpy}, []

    def patch(pid, lane=None, note=""):
        def deco(fn):
            patches.append({"id": pid, "lane": lane, "note": note, "fn": fn})
            return fn
        return deco
    ns["patch"] = patch
    with open(path, encoding="utf-8") as f:
        exec(compile(f.read(), path, "exec"), ns)
    ids = [p["id"] for p in patches]
    for p in [p for p in patches if lanes is None or p["lane"] is None or p["lane"] in lanes]:
        if p["lane"] in linked:  # edits to linked data are not saved
            out.append({"id": p["id"], "lane": p["lane"], "ok": False, "detail": "lane is joined by link; patches only persist on appended lanes"})
            continue
        try:  # run it twice in a row: the second run must change nothing
            before = state_rows(objs())
            p["fn"](bpy)
            first = state_rows(objs())
            p["fn"](bpy)
            same = first == state_rows(objs())
            changed = sorted(k for k in before.keys() | first.keys() if before.get(k) != first.get(k))
            out.append({"id": p["id"], "lane": p["lane"], "ok": same, "changed": changed,
                        "detail": "" if same else "not repeatable: a second run changed the objects (set values, don't add to them)"})
        except Exception as e:  # a failed patch fails the join
            out.append({"id": p["id"], "lane": p["lane"], "ok": False, "error": repr(e)})
    out.append({"id": "_unique_ids", "ok": len(ids) == len(set(ids)), "detail": ids})
    return out


def dup_names():
    return {x.name for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves, bpy.data.materials) for x in coll if DUP.search(x.name)}


def replay_lanes(parts, lanes, tested=None):
    """Apply fix lanes' patches.py to the open file in queue order, stopping at the first lane that fails. Saves nothing: the `replay`
    command saves a tested copy, the live worker saves its own backup. tested is the merge test's report: a file it didn't run is refused."""
    rep = {"ok": False, "at": now(), "input": bpy.data.filepath, "lanes": [], "noop": []}
    files = {lane: os.path.join(parts, lane, "patches.py") for lane in lanes}
    rep["failures"] = [f"{lane}: {f} not found" for lane, f in files.items() if not os.path.exists(f)]
    if tested and not rep["failures"]:
        with open(tested) as f:
            ran = {x["lane"]: x["sha256"] for x in json.load(f)["lanes"]}
        rep["failures"] = [f"{lane}: patches.py differs from the merge test" for lane in lanes if ran.get(lane) != sha256(files[lane])]
    if rep["failures"]:
        return rep
    dups0, owner = dup_names(), {}
    for lane in lanes:
        try:
            rows = replay_patches(files[lane], None, lambda: bpy.data.objects)
        except Exception as e:  # a patch file that doesn't load fails its lane like a patch that fails
            rows = [{"id": "_load", "ok": False, "error": repr(e)}]
        changed = sorted({n for r in rows for n in r.get("changed", [])})
        rep["lanes"].append({"lane": lane, "patches": files[lane], "sha256": sha256(files[lane]), "changed": changed, "rows": rows})
        rep["noop"] += [f"{lane}/{r['id']}" for r in rows if "changed" in r and not r["changed"]]
        rep["failures"] += [f"{lane}/{r['id']}: {r.get('error') or r.get('detail')}" for r in rows if not r["ok"]]
        rep["failures"] += [f"{lane}: {n} was already changed by {owner[n]}; give it one seam owner" for n in changed if n in owner]
        owner.update((n, lane) for n in changed)
        if rep["failures"]:
            break
    new = sorted(dup_names() - dups0)
    if new:
        rep["failures"].append(f"new .001 names (a patch creates data on every run; get or create by name): {new[:10]}")
    rep["ok"] = not rep["failures"]
    return rep


def replay(a):
    assert bpy.data.filepath, "open a fresh copy of the gate: blender-bg <gate_copy.blend> --python integrate_parts.py -- replay ..."
    assert os.path.abspath(bpy.data.filepath) != os.path.abspath(a.out), "--out must be a different file from the open gate copy"
    rep = replay_lanes(a.parts, [x for x in a.lanes.split(",") if x])
    rep["output"] = a.out
    if rep["ok"]:
        save_out(a, rep)
    return rep


def save_out(a, rep):
    """Save --out, a backup copy under the house-rule name, and record the new file's hash."""
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    if a.backup_dir:
        os.makedirs(a.backup_dir, exist_ok=True)
        pre = f"{os.path.splitext(os.path.basename(a.out))[0]}_{getattr(a, 'phase', 'blockout')}_"   # house rule 4: <file>_<phase>_<nn>_<step>
        nn = 1 + sum(1 for f in os.listdir(a.backup_dir) if f.startswith(pre) and f.endswith(".blend"))
        rep["backup"] = os.path.join(a.backup_dir, f"{pre}{nn:02d}_{a.step}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=rep["backup"], copy=True)
    rep["output_sha256"] = sha256(a.out)


# ---------- join ----------

def join(a):
    lanes = [x for x in a.lanes.split(",") if x]
    gate = bpy.data.filepath
    assert gate, "open the gate copy: blender-bg <gate_copy.blend> --python integrate_parts.py -- ..."
    assert os.path.abspath(gate) != os.path.abspath(a.out), "--out must be a different file from the open gate copy"
    rep = {"ok": True, "at": now(), "input": gate, "input_sha256": sha256(gate), "output": a.out, "lanes": [], "patches": []}
    mans, cols = {}, {}
    dups0 = {x.name for x in bpy.data.materials if DUP.search(x.name)}
    used0 = {x.name for x in bpy.data.materials if x.users}
    gate_mats = {x.name for x in bpy.data.materials}
    for lane in lanes:
        m = mans[lane] = read_manifest(a.parts, lane)
        lr = {"lane": lane, "checks": []}
        rep["lanes"].append(lr)
        part = part_path(a.parts, m)
        lr["part"] = part
        if not os.path.exists(part):
            lr["checks"].append({"stage": "start", "check": "part_file", "ok": False, "detail": part})
            continue
        frozen, now_hash = m.get("frozen", {}).get("sha256"), sha256(part)
        lr["checks"].append({"stage": "start", "check": "frozen_hash_matches", "ok": frozen == now_hash,
                             "detail": "never frozen" if not frozen else "part file changed after the freeze" if frozen != now_hash else ""})
        if not lr["checks"][-1]["ok"]:
            continue
        link = (m.get("mode") or a.mode) == "link"
        mats_before = {x.name for x in bpy.data.materials}
        lr["removed"], state = remove_lane(lane, m, part)
        col, home = load_lane(m, part, link, state)
        if col is None:
            lr["checks"].append({"stage": "rebuilt", "check": "collection_loaded", "ok": False, "detail": m["collection"] + " not in the part file"})
            continue
        lr["mode"] = "link" if link else "append"
        if not link:
            lr["materials"] = dict(zip(("remapped", "new", "drift"), remap_materials(mats_before)))
            lr["materials"]["remapped"] = len(lr["materials"]["remapped"])
        cols[lane] = col
        made, errs = place_instances(m, home)
        lr["instances"] = {"listed": len(m["instances"]), "placed": len(made)}
        lr["checks"].append({"stage": "rebuilt", "check": "instances_placed", "ok": not errs, "detail": errs[:10]})
        verify_lane(m, col, "rebuilt", lr, dups0, mats_before)
    if a.patches and os.path.exists(a.patches) and all(c["ok"] for lr in rep["lanes"] for c in lr["checks"]):
        rep["patches"] = replay_patches(a.patches, lanes, lambda: set().union(*[lane_objects(l, cols[l]) for l in lanes]),
                                     {lr["lane"] for lr in rep["lanes"] if lr.get("mode") == "link"})
        for lr in rep["lanes"]:
            verify_lane(mans[lr["lane"]], cols[lr["lane"]], "patched", lr, dups0, gate_mats)
    elif a.patches and not os.path.exists(a.patches):
        rep["patches"] = [{"id": "_patch_file", "ok": False, "detail": "not found: " + a.patches}]
    # a palette material only the rebuilt lane used would be dropped at save: say so, the lane brief or the palette must keep it
    rep["warnings"] = {"materials_orphaned": sorted(n for n in used0 if n in bpy.data.materials and not bpy.data.materials[n].users and not bpy.data.materials[n].use_fake_user)}
    rep["failures"] = [f"{lr['lane']}: {c['stage']}/{c['check']} {c['detail']}" for lr in rep["lanes"] for c in lr["checks"] if not c["ok"]] + \
                      [f"patch {p['id']}: {p.get('error') or p.get('detail')}" for p in rep["patches"] if not p["ok"]]
    rep["ok"] = not rep["failures"]
    if rep["ok"]:
        save_out(a, rep)
    return rep


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", choices=["join", "freeze", "replay"], default="join")
    ap.add_argument("--parts", required=True, help="folder holding <lane>/manifest.json and <lane>/<lane>.blend")
    ap.add_argument("--lanes", required=True, help="comma list, in merge-queue order")
    ap.add_argument("--out", help="joined file to write (must differ from the open gate copy)")
    ap.add_argument("--patches", help="live_patches.py to replay after the rebuild")
    ap.add_argument("--backup-dir", help="also save a backup copy here (house rule 4)")
    ap.add_argument("--step", default="join", help="step name in the backup file name")
    ap.add_argument("--phase", default="blockout", help="phase in the backup file name")
    ap.add_argument("--report", help="JSON report path (default: next to --out)")
    ap.add_argument("--mode", choices=["append", "link"], default="append", help="default; a manifest may set its own")
    a = ap.parse_args(argv)
    if a.cmd == "freeze":
        return freeze(a.parts, [x for x in a.lanes.split(",") if x])
    assert bpy and a.out, "join and replay run inside Blender and need --out"
    rep = join(a) if a.cmd == "join" else replay(a)
    path = a.report or f"{os.path.splitext(a.out)[0]}_{a.cmd}.json"
    with open(path, "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print(a.cmd.upper(), "OK" if rep["ok"] else "FAILED", path)
    for x in rep["failures"]:
        print("  FAIL", x)
    for x in rep.get("noop", []):
        print("  NOOP", x)
    if not rep["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:  # under --python an exception would exit 0
        import traceback
        traceback.print_exc()
        print("integrate_parts error:", repr(e))
        sys.exit(1)
