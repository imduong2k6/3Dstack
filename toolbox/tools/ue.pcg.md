---
id: ue.pcg
kind: unreal_plugin
name: Procedural Content Generation Framework (PCG)
version: "1.0"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCG/PCG.uplugin
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCG/Content/GraphTemplates (template names)
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCG/Content/Python/test_pcg_manage_asset.py
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGSpawnSplineMesh.h
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview?application_version=5.7
  - https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine?application_version=5.7
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/PCGComponent
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
  - https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274
  - https://forums.unrealengine.com/t/generate-pcg-through-python-script/2053107
pipeline_stages: [placement-phases, set-dressing]
routes: [unreal, blender_unreal]
---

# Procedural Content Generation Framework (PCG)

**What it does:** A node-graph framework that samples points from spatial data (surfaces, splines, volumes, landscape), filters and transforms them, then spawns meshes or actors at the points, in the editor or at runtime. Epic's plugin is on by default (`EnabledByDefault: true`, not beta), but is not listed in SkillTest.uproject.

## Use it for
- P3 services and P4 railings: Spline Sampler into Spawn Spline Mesh (header: "Create a USplineMeshComponent for each segment along a given spline").
- P6/P7 clutter and P9 life: Surface Sampler into Transform Points into Static Mesh Spawner (Mesh Entries with a Descriptor and a Weight per entry).
- Large areas: partitioned and hierarchical generation. Engine templates to copy: `TPL_Sampler_Spline`, `TPL_Sampler_SplineInterior`, `TPL_Showcase_SimpleForest`, `TPL_Showcase_HierarchicalGenerationForest`, `TPL_Showcase_RuntimeGrassGPU`.

## How to call it
- Editor: Content Browser, Create Advanced Asset > PCG > PCG Graph; double-click to edit. Put a PCG Component on an actor (or use a PCG Volume), pick the Graph, press Generate in Details. Node keys: D debug view, E enable/disable, A inspect.
- Python (`unreal`, PythonScriptPlugin is on in SkillTest): create the asset with `unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, path, unreal.PCGGraph, None)` (as in the engine test script). On a `unreal.PCGComponent`: `set_graph(graph)`, `generate(force)`, `cleanup(remove_components)`, `get_generated_graph_output()`. `generate_local` and `cleanup_local` skip replication and run delayed.
- I found no documented Python API for adding nodes or wiring pins. Author graphs in the editor, then drive them from Python or MCP by setting the graph, `seed` and `is_component_partitioned`, then calling `generate`.
- A forum post reports `generate(True)` creating the PCG world actor but producing nothing; no answer in the thread. Verify on the pilot project before relying on it.

## Settings that matter
- Component `seed`; Point Generator default seed became 42 in 5.8.1 (was 0), so older graphs may re-roll.
- `Is Partitioned` for large areas; cell size is `Partition Grid Size` on the PCGWorldActor. After changing it, Cleanup then Generate every PCG asset.
- Graph Settings: `Use Hierarchical Generation` (needs Partitioned) and `HiGen Default Grid Size`; Grid Size node per branch. Big meshes on large grids, small clutter on small grids.
- Generation Trigger `Generate at Runtime` only for gameplay streaming; not needed for stills.

## Gotchas
- Sampling points on a Static Mesh needs the PCG Geometry Script Interop plugin (see `ue.pcggeometryscriptinterop`).
- Live updates only happen after the graph has generated on a component; attribute types must match when overriding settings.
- Large-grid sampler over a big volume without `Unbounded` runs once per cell and slows down; data passed from big to small grids can duplicate points, so use Cull Points Outside Actor Bounds.
- With World Partition, generated actors take the PCG asset's Data Layer and HLOD layer.
- Forum advice (unverified): interior sampling of a closed spline may need `Unbounded` on the Spline Sampler.

## Don't use it for
- One-off hero placement: place by hand. Blender routes build scatter and pipes with geometry nodes (`geometry-nodes` skill), not PCG.
- Animated or simulated cables: use `ue.cablecomponent`.

## Version notes
- 5.8: non-destructive manual editing of PCG output, complex attributes (arrays, structs, sets, maps), embedded subgraphs, Graph Parameters editor, GPU runtime scatter, actor- and component-less runtime generation, new nodes (Align Points, Apply Spline to Component, Set Materials On Dynamic Mesh). Procedural Vegetation Editor is a separate experimental plugin.
- Hotfixes: 5.8.1 seed default and rotation crashes; 5.8.2 grid linkage race; 5.8.3 (installed) integer attribute drift when interpolating spline metadata.
- Release notes carry no production-ready or beta label for PCG itself.
