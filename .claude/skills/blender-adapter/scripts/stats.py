"""Write stats.json for a gate (tested headless with bpy 5.2.3; verify in your Blender on the first project).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/stats.py").read())
    write_stats(r"<project>/reviews/P3-r1/stats.json")
"""
import json
from collections import Counter

import bpy

FLAT_TRIS_PER_M2 = 20000  # a 20 x 20 subdivided A4 card is about 12,800; the pilot's dense cards were 45,000 to 780,000


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


def write_stats(path):
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
        if 100 < n <= 5000 and ob.original.name not in flat_dense:  # paper, posters, signs: a plane with alpha, not a dense mesh
            mw = inst.matrix_world
            co = [mw @ v.co for v in me.vertices]
            d = sorted(max(c[i] for c in co) - min(c[i] for c in co) for i in range(3))
            area = sum(((co[t.vertices[1]] - co[t.vertices[0]]).cross(co[t.vertices[2]] - co[t.vertices[0]])).length / 2
                       for t in me.loop_triangles)
            if d[0] < 0.03 and d[0] < 0.1 * d[1] and area and n / area > FLAT_TRIS_PER_M2:
                flat_dense[ob.original.name] = {"tris": n, "tris_per_m2": round(n / area)}
        ob.to_mesh_clear()
        for slot in ob.material_slots:
            if slot.material:
                groups[slot.material.get("material_group", "none")] += 1
    stats = {"objects_by_phase": by_phase, "objects_by_source": by_source, "unique_meshes": len(meshes),
             "triangles_evaluated": tris, "lights_by_type": lights, "material_groups": groups,
             "flat_dense": flat_dense}
    with open(path, "w") as f:
        json.dump(stats, f, indent=2, default=dict)
    print(f"stats written to {path}")
