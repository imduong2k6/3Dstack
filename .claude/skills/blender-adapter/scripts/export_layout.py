"""Write transfer/layout.json for the Blender-then-Unreal route (tested headless with bpy 5.2.3; verify in your Blender on the first project).

One row per placed mesh instance in the COL_P* collections. The asset id is the mesh data
name, which matches the FBX exported once per unique mesh.

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/export_layout.py").read())
    export(r"<project>/transfer/layout.json")
"""
import json

import bpy


def export(path):
    rows = []
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH":
            continue
        instanced = inst.is_instance and inst.parent is not None
        holder = inst.parent.original if instanced else ob.original
        cols = [c.name for c in holder.users_collection]
        phase = next((c[len("COL_"):] for c in cols if c.startswith("COL_P")), None)
        if not phase:
            continue
        loc, rot, scale = inst.matrix_world.decompose()
        rows.append({
            "name": f"{holder.name}/{ob.name}" if instanced else holder.name,
            "asset": ob.data.original.name if hasattr(ob.data, "original") else ob.data.name,
            "phase": phase.split("_")[0],
            "map_id": holder.get("map_id", ""),
            "loc_m": [round(v, 5) for v in loc],
            "rot_quat_wxyz": [round(v, 6) for v in rot],
            "scale": [round(v, 5) for v in scale],
        })
    with open(path, "w") as f:
        json.dump({"units": "m", "up": "Z", "handedness": "right", "instances": rows}, f, indent=1)
    print(f"{len(rows)} instances written to {path}")
