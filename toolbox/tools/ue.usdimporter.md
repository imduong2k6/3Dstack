---
id: ue.usdimporter
kind: unreal_plugin
name: USD Importer
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Importers/USDImporter/*.uplugin
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter]
routes: [unreal, blender_unreal]
---

# USD Importer

**What it does:** Imports USD files into Unreal. Alternative transfer path from Blender (USD export).

## Use it for
- Whole-scene transfer from Blender when instancing matters; default stays FBX (see transfer.blender-unreal).

## How to call it
- Content Browser > Import a .usd/.usda/.usdc, or use the USD Stage window.

## Settings that matter
- Match up-axis and metersPerUnit (Blender Z-up, 1 m).

## Gotchas
- Material translation is limited; rebuild materials from the pass-switch groups.
- Descriptor has no DocsURL.

## Don't use it for
- Single props: FBX via better_fbx is the established route.

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
