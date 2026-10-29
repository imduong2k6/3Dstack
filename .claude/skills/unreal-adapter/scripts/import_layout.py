"""Place the Blender layout in Unreal from transfer/layout.json (tested in UE 5.8.3 through PipelineTools.place_layout).

Over MCP: PipelineTools.place_layout(layout_path=r"<project>/transfer/layout.json").

Blender: Z-up, right-handed, metres. Unreal: Z-up, left-handed, centimetres.
Location: (x, -y, z) * 100. Rotation quaternion (w, x, y, z) -> (w, -x, y, -z),
the mirror across the XZ plane. FBX meshes exported with the settings in
toolbox/tools/transfer.blender-unreal.md import with the same Y mirror and no extra
axis rotation (checked with a corner-pivot 1 x 2 x 3 m probe).

Every placement is a StaticMeshActor of the same imported mesh, so repeats share one
asset and Unreal instances them at draw time. To turn a large group into one instanced
component, select it and use Tools > Merge Actors > Instance.
Re-running replaces the previous transfer: actors tagged src:transfer are deleted first.
"""
import json

import unreal


def to_ue(row):
    x, y, z = row["loc_m"]
    w, qx, qy, qz = row["rot_quat_wxyz"]
    loc = unreal.Vector(x * 100.0, -y * 100.0, z * 100.0)
    rot = unreal.Quat(-qx, qy, -qz, w).rotator()
    return loc, rot, unreal.Vector(*row["scale"])


def place(layout_path, mesh_root="/Game/Transfer/Meshes", folder="Transfer"):
    rows = json.load(open(layout_path))["instances"]
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    old = [a for a in eas.get_all_level_actors() if "src:transfer" in [str(t) for t in a.tags]]
    if old:
        eas.destroy_actors(old)
    cache, placed = {}, 0
    for r in rows:
        mesh = cache.get(r["asset"]) or unreal.load_asset(f"{mesh_root}/{r['asset']}")
        if not mesh:
            unreal.log_warning(f"missing mesh {r['asset']}")
            continue
        cache[r["asset"]] = mesh
        loc, rot, scale = to_ue(r)
        a = eas.spawn_actor_from_object(mesh, loc, rot)
        a.set_actor_scale3d(scale)
        a.set_actor_label(r.get("name", r["asset"]))
        phase = r.get("phase", "untagged")
        a.tags = [f"phase:{phase}", f"map:{r.get('map_id', '')}", "src:transfer"]
        a.set_folder_path(f"{folder}/{phase}")
        placed += 1
    msg = f"placed {placed} of {len(rows)} instances using {len(cache)} meshes"
    unreal.log(msg)
    return msg
