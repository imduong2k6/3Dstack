---
id: ue.modelingtoolseditormode
kind: unreal_plugin
name: Modeling Tools Editor Mode
version: "0.1"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Editor/ModelingToolsEditorMode/ModelingToolsEditorMode.uplugin
  - <your project>.uproject
  - https://dev.epicgames.com/documentation/unreal-engine/modeling-mode-in-unreal-engine
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
  - https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274
pipeline_stages: [blockout, modular-kit, collision-proxy, lod-pipeline]
routes: [unreal, blender_unreal]
---

# Modeling Tools Editor Mode

**What it does:** An interactive editor mode with tools to create and edit meshes in the Unreal viewport (primitives, PolyGroup editing, deform, UVs, bake, LOD and volume utilities). Epic marks it Beta ("use caution when shipping"); the .uplugin has `IsBetaVersion: true`. It is enabled (Editor target only) in the pilot project SkillTest.

## Use it for
- Stage 3 blockout on route `unreal`: kit-sized proxies at real scale on the grid. The repo's `level-design` skill already names the Cube Grid tool for this.
- Quick fixes to an imported kit mesh when a Blender round trip is not worth it: pivots, a missing face, PolyGroup selection, a UV tweak.
- LOD and collision touch-ups on a single hero mesh by hand (LOD management sits under the Misc category). For many meshes use `ue.geometryscripting`.

## How to call it
- Editor only. Switch with the Select Mode dropdown or Shift+5. If Modeling is missing from the dropdown, enable Edit > Plugins > Modeling Tools Editor Mode.
- Tool categories on the page: Faves, Create, Select, XForm, Deform, Model, Mesh, Voxel, Bake, UVs, Attributes, Misc.
- I found no documented Python or MCP entry point for the interactive tools; they need a person at the viewport. Scripted mesh work goes through Geometry Script.

## Settings that matter
- Output type when creating: Static Mesh (asset in the Content Browser plus a level instance), Dynamic Mesh (level only) or Volume (level only). Choose Static Mesh for anything the pipeline keeps, with the kit naming (`SM_<Name>`).
- PolyGroup Mode on primitive creation controls the quad-like groups you can edit later.
- Grid: Ctrl+Click repositions the grid to the hit normal; Shift+Ctrl+Click to the hit surface keeping orientation; Q toggles orientation lock (local space).

## Gotchas
- Most tools preview and only apply on Accept; Cancel or leaving the mode discards the edit. After Accept, undo treats the whole tool session as one step.
- Use Duplicate before editing a high-resolution asset.
- Dynamic Mesh and Volume outputs are saved in the level only, not as Content Browser assets, so nothing else can reference them.
- 5.8.4 fixed a MeshSelectionTool crash when a hotkey is pressed during a brush stroke; the installed 5.8.3 still has it, so avoid hotkeys mid-stroke.
- PolyGroups are triangle collections that mimic quads; extended PolyGroup layers are not supported by every tool.

## Don't use it for
- Kit pieces and props to spec: the Modeler builds those in Blender on every route (pivots, UVs, sockets, collision names).
- Landscape-style terrain: Mesh Terrain in 5.8 is a separate experimental system.

## Version notes
- 5.8 changes to Modeling Mode named in the notes are skeletal-mesh tools (Bake Vertex Color port, Edit Skin Weights, Edit Skeleton, Mask Morph Target), not static-mesh ones. Plugin version stays 0.1.
