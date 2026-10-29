---
id: ue.datasmithimporter
kind: unreal_plugin
name: Datasmith Importer
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Enterprise/DatasmithImporter/*.uplugin
  - https://docs.unrealengine.com/en-US/WorkingWithContent/Importing/Datasmith/
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter]
routes: [unreal, blender_unreal]
---

# Datasmith Importer

**What it does:** Imports CAD and DCC scenes (.udatasmith) with hierarchy and materials.

## Use it for
- Fallback for bringing a full CAD scene in one go; not the default.

## How to call it
- Content Browser > Add > Datasmith; needs a Datasmith exporter in the source app (none found for Blender).

## Settings that matter
- None for this pipeline.

## Gotchas
- No Blender Datasmith exporter in the scan; use FBX or USD.

## Don't use it for
- Normal kit-piece export (use FBX).

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
