---
id: ue.editorscriptingutilities
kind: unreal_plugin
name: Editor Scripting Utilities
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Editor/EditorScriptingUtilities/*.uplugin
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter, placement-phases, set-dressing]
routes: [unreal, blender_unreal]
---

# Editor Scripting Utilities

**What it does:** Blueprint and Python helper libraries for editor automation: asset listing, rename, duplicate, actor spawn and select.

## Use it for
- Spawning and naming kit actors, setting tags and folders, batch material assignment.

## How to call it
- Python: `unreal.EditorAssetLibrary.list_assets(path)`, `.rename_asset`, `.save_loaded_asset`; `unreal.EditorLevelLibrary.spawn_actor_from_object`.

## Settings that matter
- Confirm the plugin is enabled in the project.

## Gotchas
- Some EditorLevelLibrary functions are deprecated in favour of EditorActorSubsystem and LevelEditorSubsystem; prefer the subsystems.
- Descriptor has an empty DocsURL; use the Python API reference.

## Don't use it for
- Bulk placement of thousands of instances (use PCG, ue.pcg).

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
