---
id: ue.geometryscripting
kind: unreal_plugin
name: Geometry Script
version: "0.1"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Runtime/GeometryScripting/GeometryScripting.uplugin
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Runtime/GeometryScripting/Source/GeometryScriptingCore/Public/GeometryScript (MeshAssetFunctions.h, CollisionFunctions.h, MeshSimplifyFunctions.h, MeshPrimitiveFunctions.h)
  - https://dev.epicgames.com/documentation/unreal-engine/geometry-scripting-users-guide-in-unreal-engine
  - https://dev.epicgames.com/documentation/unreal-engine/geometry-scripting-reference-in-unreal-engine
  - https://forums.unrealengine.com/t/geometry-script-crash-append-triangulated-polygon-3d/2322755
pipeline_stages: [blockout, collision-proxy, lod-pipeline, modeling]
routes: [unreal, blender_unreal]
---

# Geometry Script

**What it does:** Function libraries that create and edit meshes (`UDynamicMesh`) from Blueprints and Python: primitives, booleans, simplify, UVs, normals, collision generation, and copy to and from Static Mesh assets. Epic labels it Beta ("use caution when shipping"); the .uplugin says version 0.1, no DocsURL.

## Use it for
- Collision proxies in bulk (`collision-proxy`): `GenerateCollisionFromMesh` and `SetStaticMeshCollisionFromMesh` (writes simple collision onto a Static Mesh asset).
- LOD or budget passes on meshes that can't use Nanite (`lod-pipeline`): `ApplySimplifyToTriangleCount` (also tolerance and planar variants), written back with `CopyMeshToStaticMesh` and a target LOD.
- Fast blockout proxies from code (`blockout`): `AppendBox` and other primitive appenders, at real scale from the metrics.
- Batch fixes on imported meshes (normals recompute, tangents, box-projection UVs), in an Editor Utility or Python script.

## How to call it
- Python via the `unreal` module (PythonScriptPlugin is on in SkillTest). Library classes carry a Python `ScriptName`, for example `unreal.GeometryScript_Primitives`, `GeometryScript_MeshSimplification`, `GeometryScript_Collision`, `GeometryScript_AssetUtils`, `GeometryScript_MeshBooleans`, `GeometryScript_UVs`, `GeometryScript_Normals`, `GeometryScript_Remeshing`. Python names are the snake_case of the C++ names.
- Header signature to copy from: `CopyMeshToStaticMesh(FromDynamicMesh, ToStaticMeshAsset, Options, TargetLOD, Outcome, bUseSectionMaterials=true, Debug)`; `CopyMeshFromStaticMesh(FromStaticMeshAsset, ToDynamicMesh, AssetOptions, RequestedLOD, Outcome, Debug)`. Functions marked `ScriptMethod` in the headers (for example `AppendBox`, `ApplySimplifyToTriangleCount`) may also be callable as methods on the mesh. I read the headers; I did not run any of this.
- Blueprint: enable the plugin (Edit > Plugins, search "geometry script", restart), then use a Generated Dynamic Mesh Actor subclass (On Rebuild Generated Mesh) or an Editor Utility.
- The plugin is not listed in SkillTest.uproject and has no `EnabledByDefault`; enabling is the user's call.

## Settings that matter
- `CopyMeshToStaticMesh` options include `bApplyNaniteSettings` (default false) and `bEnableRecomputeNormals/Tangents` (default false): set them explicitly, or Nanite and normals stay as-is.
- Use the `Debug` pin/arg (`UGeometryScriptDebug`) to capture failure messages.

## Gotchas
- Editor-only functions: Create New Static Mesh Asset From Mesh, Apply Editor Simplify nodes, PolyGroup Catmull Clark and Triangle Loop SubD. Callable only from editor contexts.
- A Dynamic Mesh Component has no Nanite, LODs, distance fields or instanced rendering. Convert to a Static Mesh asset for anything that ships.
- Low-level per-triangle loops in Blueprint or Python are slow. Deleting elements leaves ID gaps (Compact Mesh fixes it). BVH objects go invalid after any mesh edit.
- One forum report: Copy Mesh to Static Mesh crashed on a mesh with holes after Append Triangulated Polygon. Unconfirmed; test on a copy.

## Don't use it for
- Modeling kit pieces or props. The Modeler works in Blender on every route and hands over FBX.
- Interactive editing: use `ue.modelingtoolseditormode`.

## Version notes
- No Geometry Script entry in the UE 5.8 release notes; a 5.8.1 Geometry Core fix covers a UV packer crash on an invalid texture resolution. Plugin version stays 0.1.
