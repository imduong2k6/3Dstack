"""Write stats.json for a gate (tested in UE 5.8.3 through PipelineTools.write_stats).

Over MCP: PipelineTools.write_stats(path=r"<project>/reviews/P3-r1/stats.json").
In the editor's Python console:
    exec(open(r"<repo>/.claude/skills/unreal-adapter/scripts/stats.py").read())
    write_stats(r"<project>/reviews/P3-r1/stats.json")
"""
import json
import os
from collections import Counter

import unreal


def tag_value(actor, key):
    for t in actor.tags:
        t = str(t)
        if t.startswith(key + ":"):
            return t.split(":", 1)[1]
    return None


def write_stats(path):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_phase, by_source, lights, shadow = Counter(), Counter(), Counter(), 0
    meshes, tris, groups = set(), 0, Counter()
    for a in actors:
        by_phase[tag_value(a, "phase") or "untagged"] += 1
        by_source[tag_value(a, "src") or "build"] += 1
        if isinstance(a, (unreal.Light, unreal.SkyLight)):  # SkyLight is not a Light subclass
            lights[type(a).__name__] += 1
            comp = a.get_component_by_class(unreal.LightComponentBase)
            if comp and comp.get_editor_property("cast_shadows"):
                shadow += 1
            continue
        for comp in a.get_components_by_class(unreal.StaticMeshComponent):
            sm = comp.get_editor_property("static_mesh")
            if not sm:
                continue
            meshes.add(sm.get_path_name())
            count = comp.get_instance_count() if isinstance(comp, unreal.InstancedStaticMeshComponent) else 1
            tris += sm.get_num_triangles(0) * count  # Nanite meshes report the fallback LOD
            for m in comp.get_materials():
                if m:
                    groups[m.get_name()] += 1
    stats = {"actors_by_phase": by_phase, "actors_by_source": by_source, "unique_meshes": len(meshes),
             "triangles_lod0": tris, "lights_by_type": lights, "shadow_casting_lights": shadow,
             "material_instances": groups}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(stats, f, indent=2, default=dict)
    msg = f"stats written to {path}: {len(actors)} actors, {len(meshes)} meshes, {tris} triangles, {sum(lights.values())} lights"
    unreal.log(msg)
    return msg
