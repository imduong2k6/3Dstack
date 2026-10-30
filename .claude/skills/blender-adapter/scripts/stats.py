"""Write stats.json for a gate (tested headless with bpy 5.2.3; verify in your Blender on the first project).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/stats.py").read())
    write_stats(r"<project>/reviews/P3-r1/stats.json", expect_file=r"<the gate copy>")

Headless: bash bin/blender-bg <gate copy> --python stats.py -- --out stats.json --expect-file <gate copy>

Errors (stats.json still gets written, with an `errors` list): faces on empty or missing material slots, and an open file that is not the
expected gate copy (stats must never come from a backup). write_stats raises StatsError for them; the headless run exits 1.
"""
import json
import os
import sys
from collections import Counter

import bpy
import numpy as np

FLAT_TRIS_PER_M2 = 20000  # a 20 x 20 subdivided A4 card is about 12,800; the pilot's dense cards were 45,000 to 780,000


class StatsError(Exception):
    pass


def _unrendered_collections(scene):
    """Names of collections switched off for render, directly or through a parent."""
    off = set()

    def walk(c, hidden):
        hidden = hidden or c.hide_render
        if hidden:
            off.add(c.name)
        for ch in c.children:
            walk(ch, hidden)
    walk(scene.collection, False)
    return off


def faces_without_material(scene=None):
    """{object name: face count} for rendered meshes with faces on an empty or missing material slot."""
    sc = scene or bpy.context.scene
    off, vl, bad = _unrendered_collections(sc), bpy.context.view_layer, {}
    for ob in sc.objects:
        if ob.type != "MESH" or ob.hide_render or all(c.name in off for c in ob.users_collection) or ob.name not in vl.objects or not len(ob.data.polygons):
            continue
        ok = np.array([bool(s.material) for s in ob.material_slots] + [False])
        idx = np.empty(len(ob.data.polygons), np.int32)
        ob.data.polygons.foreach_get("material_index", idx)
        n = int((~ok[np.minimum(idx, len(ok) - 1)] | (idx >= len(ok) - 1)).sum())
        if n:
            bad[ob.name] = n
    return bad


def write_stats(path, expect_file=None, strict=True):
    dg = bpy.context.evaluated_depsgraph_get()
    off = _unrendered_collections(bpy.context.scene)
    by_phase, by_source, lights, groups = Counter(), Counter(), Counter(), Counter()
    meshes, tris, flat_dense = set(), 0, {}
    for inst in dg.object_instances:
        ob = inst.object
        src = inst.parent.original if inst.is_instance and inst.parent is not None else ob.original
        # count what renders: skip hidden cutters, guides and collections off for render
        # (collections excluded from the view layer never reach the depsgraph)
        if src.hide_render or all(c.name in off for c in src.users_collection):
            continue
        if ob.type == "LIGHT":
            lights[ob.data.type] += 1
            continue
        if ob.type != "MESH":
            continue
        phase = src.get("phase") or next((c.name[4:].split("_")[0] for c in src.users_collection
                                          if c.name.startswith("COL_P")), "untagged")
        by_phase[phase] += 1
        by_source[src.get("src", "build")] += 1
        meshes.add(ob.data.original.name if hasattr(ob.data, "original") else ob.data.name)
        me = ob.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        n = len(me.loop_triangles)
        if n > 100 and ob.original.name not in flat_dense:  # paper, posters, signs: a plane with alpha, not a dense mesh (no upper triangle limit)
            m = np.array(inst.matrix_world)
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            d = np.sort(np.ptp(co, axis=0))
            if d[0] < 0.03 and d[0] < 0.1 * d[1]:  # thin and wide: only then is the area worth measuring
                tr = np.empty(n * 3, np.int32)
                me.loop_triangles.foreach_get("vertices", tr)
                tr = tr.reshape(-1, 3)
                cr = np.cross(co[tr[:, 1]] - co[tr[:, 0]], co[tr[:, 2]] - co[tr[:, 0]])
                a2 = np.linalg.norm(cr, axis=1)
                area = float(a2.sum() / 2)
                thin = int(np.argmin(np.ptp(co, axis=0)))
                facing = float(a2[np.abs(cr[:, thin]) > 0.87 * a2].sum() / 2) / area if area else 0.0  # a sheet faces its thin axis; cables lying on a wall don't
                if area and n / area > FLAT_TRIS_PER_M2 and facing > 0.6:
                    flat_dense[ob.original.name] = {"tris": n, "tris_per_m2": round(n / area)}
        ob.to_mesh_clear()
        for slot in ob.material_slots:
            if slot.material:
                groups[slot.material.get("material_group", "none")] += 1
    nomat = faces_without_material()
    cur, errors, warnings = bpy.data.filepath, [], []
    if nomat:
        errors.append(f"{sum(nomat.values())} faces on empty or missing material slots in {len(nomat)} objects")
    norm = lambda p: os.path.normcase(os.path.realpath(p)) if p else ""
    if expect_file and norm(cur) != norm(expect_file):
        errors.append(f"open file is {cur or '(unsaved)'}, not the expected gate copy {expect_file}")
    if not expect_file and "backups" in {p.lower() for p in os.path.normpath(cur).split(os.sep)}:
        warnings.append("the open file is in a backups folder; pass expect_file so stats are never taken from a backup")
    stats = {"file": cur, "expected_file": expect_file, "objects_by_phase": by_phase, "objects_by_source": by_source, "unique_meshes": len(meshes),
             "triangles_evaluated": tris, "lights_by_type": lights, "material_groups": groups, "flat_dense": flat_dense,
             "faces_without_material": sum(nomat.values()), "faces_without_material_by_object": dict(list(nomat.items())[:100]),
             "errors": errors, "warnings": warnings}
    with open(path, "w") as f:
        json.dump(stats, f, indent=2, default=dict)
    print(f"stats written to {path}" + (f" with {len(errors)} error(s): {errors}" if errors else ""))
    if errors and strict:
        raise StatsError("; ".join(errors))
    return stats


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="stats.py")
    ap.error = lambda m: (_ for _ in ()).throw(StatsError(m))
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-file")
    a = ap.parse_args(argv)
    write_stats(a.out, expect_file=a.expect_file)


if any(os.path.basename(x) == "stats.py" for x in sys.argv) and "--" in sys.argv:
    try:
        _main(sys.argv[sys.argv.index("--") + 1:])
        _code = 0
    except StatsError as e:
        print("STATS ERROR:", e)
        _code = 1
    except Exception:
        import traceback
        traceback.print_exc()
        _code = 1
    sys.exit(_code)
