---
id: ue.pcggeometryscriptinterop
kind: unreal_plugin
name: PCG Geometry Script Interop
version: "0.2"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCGInterops/PCGGeometryScriptInterop/PCGGeometryScriptInterop.uplugin
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/PCGInterops/PCGGeometryScriptInterop/Source/PCGGeometryScriptInterop/Public/Elements (header names and comments)
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview?application_version=5.7
  - https://dev.epicgames.com/documentation/unreal-engine/geometry-scripting-users-guide-in-unreal-engine
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
pipeline_stages: [placement-phases, set-dressing, modular-kit]
routes: [unreal, blender_unreal]
---

# PCG Geometry Script Interop

**What it does:** Adds PCG nodes that read static meshes and build or edit Dynamic Meshes inside a PCG graph, using the Geometry Script plugin. The one the pipeline needs most is Mesh Sampler, which Epic's PCG page says is required to sample points on Static Meshes.

## Use it for
- P7 clutter placed on kit pieces and props (books on a shelf, pipes along a wall): Mesh Sampler on the kit mesh, then spawn on the points.
- Spline-driven shapes built as one mesh (Spline To Mesh) when thousands of spline mesh components are too heavy.
- Merging many small spawned meshes into one Dynamic Mesh, then saving it as an asset.

## How to call it
- Enable both this plugin and Geometry Script (this plugin depends on `PCG` and `GeometryScripting`), restart the editor, then add nodes in a PCG graph. Neither is listed in SkillTest.uproject, and this one is `EnabledByDefault: false`. Enabling is the user's call.
- Mesh Sampler (`UPCGMeshSamplerSettings`) sampling methods from the header: One Point Per Triangle, One Point Per Vertex, Poisson Sampling ("can be expensive", not frame-bound).
- Node titles read from the headers: Mesh Sampler, Primitive Cross-Section, Append Meshes From Points, Boolean Operation, Create Empty Dynamic Mesh, Dynamic Mesh Transform. Also present, known from file names only (titles unverified): Spawn Dynamic Mesh, Spline To Mesh, Merge Dynamic Meshes, Static Mesh To Dynamic Mesh, Get and Set Materials Dynamic Mesh, Save Dynamic Mesh To Asset, Geometry Blueprint element.
- No Python entry point of its own. Drive the graph through `unreal.PCGComponent` as in `ue.pcg`.

## Settings that matter
- Mesh Sampler: prefer One Point Per Triangle or Vertex for speed; Poisson only when even spacing matters and the mesh is small.

## Gotchas
- Beta (`IsBetaVersion: true`, version 0.2). Expect node renames between engine versions.
- Dynamic Mesh output is not a Static Mesh: a Dynamic Mesh Component supports neither Nanite, Mesh Distance Fields, LODs nor instanced rendering (Geometry Script user guide). Save to an asset if the result is a final prop.
- Large Dynamic Meshes bloat the level file; the guide suggests One File Per Actor.
- Sampling a high-poly kit mesh per triangle can create very many points. Sample a proxy mesh instead.

## Don't use it for
- Anything that only needs spline or surface sampling of landscape and volumes; plain `ue.pcg` nodes cover that without a beta dependency.
- Modeling kit pieces: the pipeline models in Blender on every route.

## Version notes
- Plugin 0.2 (beta). 5.8 release notes list "Set Materials On Dynamic Mesh" among new PCG nodes, which matches the plugin's materials elements.
- The 5.8 release notes do not mention this interop plugin by name.
