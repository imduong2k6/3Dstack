---
id: blx.looptools
kind: blender_extension
name: LoopTools
version: "4.7.7"
checked: 2026-10-29
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org/looptools/blender_manifest.toml
  - https://docs.blender.org/manual/en/latest/addons/mesh/looptools.html
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [modeling]
routes: [blender, blender_unreal]
---

# LoopTools

**What it does:** Edit-mode tools: Circle, Bridge, Flatten, Relax, Space, Gstretch and Curve for cleaning topology.

## Use it for
- Cleaning round holes, bridging loops, relaxing generated or photo-projected meshes.

## How to call it
- Edit mode: right-click > LoopTools, or the sidebar Edit tab.

## Settings that matter
- Use Space and Relax lightly on hard-surface pieces to protect silhouette IoU.

## Gotchas
- Does not preserve UV seams by default; re-check UVs for the Asset Tech.

## Don't use it for
- Object-level scatter or placement.

## Version notes
- Checked against 4.7.7 on the author's PC (2026-10-29).
