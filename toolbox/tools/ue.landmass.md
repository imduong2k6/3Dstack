---
id: ue.landmass
kind: unreal_plugin
name: Landmass
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/Landmass (descriptor has empty Description and DocsURL)
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/landmass-in-unreal-engine
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [placement-phases, blockout]
routes: [unreal, blender_unreal]
---

# Landmass

**What it does:** Landscape blueprint brushes (terrain, rivers, roads, splines) for large outdoor landscapes.

## Use it for
- P0 site and terrain for outdoor scenes.

## How to call it
- Place Landmass brush blueprints from Place Actors on a Landscape with Edit Layers enabled.

## Settings that matter
- Needs Landscape Edit Layers; make plugin content visible in the Content Browser.

## Gotchas
- Experimental; alley or interior scenes do not need it.

## Don't use it for
- Interior or street-level scenes: use blockout kit or Blender-made ground.

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
