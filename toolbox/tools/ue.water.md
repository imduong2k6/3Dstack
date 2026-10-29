---
id: ue.water
kind: unreal_plugin
name: Water
version: "0.1"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/Water/Water.uplugin
  - https://dev.epicgames.com/documentation/unreal-engine/water-system-in-unreal-engine
  - https://dev.epicgames.com/documentation/unreal-engine/water-body-actors-in-unreal-engine
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
  - https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274
pipeline_stages: [placement-phases, set-dressing]
routes: [unreal, blender_unreal]
---

# Water

**What it does:** Spline-based water bodies (ocean, lake, river, custom) with a shared water mesh, wave and flow data, a Single Layer Water shading model, underwater post-processing, buoyancy, and landscape carving. The .uplugin marks it experimental (`IsExperimentalVersion: true`, `EnabledByDefault: false`); it depends on Landmass, Niagara, GeometryProcessing and BlueprintMaterialTextureNodes. It is not listed in SkillTest.uproject.

## Use it for
- P0 site and ground: a lake, river or shoreline that has to read as water and carve the terrain, on a Landscape.
- P9 life and nature: rivers with flow, ocean far-distance mesh, buoyant props.
- Not a priority for interiors or small ponds (see below).

## How to call it
- Enable: Edit > Plugins, search "Water", tick it, restart. Plugin content shows under Water Content when Show Engine Content and Show Plugin Content are on (caustics, fluid simulation and buoyancy examples).
- Place: Place Actors panel, drag a water body into the level, edit its spline points in Details (Selected Points). River points also expose Depth, River Width, Velocity and Audio Intensity. Global scale: Project Settings > Plugins > Water Editor.
- Types: Ocean and Lake use a closed spline with all points at one height; River is an open spline with per-point height and flow velocity; Custom uses a Static Mesh for the shape and does not use the Water Mesh Actor; Island raises land above water; Exclusion Volume cuts dry cavities.
- I found no documented Python or Blueprint recipe in the pages read; drive it through the editor, or spawn water body actors by class and set spline points through the generic `unreal` actor API (untested).

## Settings that matter
- Landscape carving needs Enable Edit Layers on the Landscape. On the water body, Affects Landscape plus a blend mode: Alpha Blend, Min (lowers only), Max (raises only), Additive. Use Min or Max where a river meets a lake.
- Match the `Water_FarMesh` material to the ocean material or the horizon will not blend. Ocean is capped by its maximum Extent Size.
- Exclusion Volumes only work with Exclude All Overlapping Water Bodies on, or an explicit list.

## Gotchas
- Experimental plugin (per the .uplugin): no stability promise between engine versions.
- Custom water bodies do not carve terrain.
- Unverified forum claim for 5.8: Water and Advanced Water do not work with Mesh Terrain (no river or lake modifiers, no underwater effects). Treat Mesh Terrain scenes as unsupported until tested.
- The Water System page does not state a Water Zone requirement; the Water Zone controls the Far Distance Mesh (on by default).

## Don't use it for
- Interior pools, fountains, puddles, or a still water plane with no flow or carving: a plain mesh with a water material (or a Custom water body) is lighter and avoids the experimental plugin.
- Blender-only (CG) scenes: use Blender's own tools.

## Version notes
- The UE 5.8 release notes do not mention the Water plugin. Version stays 0.1.
