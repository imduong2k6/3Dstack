---
id: ue.pythonscriptplugin
kind: unreal_plugin
name: Python Editor Script Plugin
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/*.uplugin (Description, DocsURL)
  - https://docs.unrealengine.com/en-US/Engine/Editor/ScriptingAndAutomation/Python/index.html
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter, placement-phases, lighting-passes]
routes: [unreal, blender_unreal]
---

# Python Editor Script Plugin

**What it does:** Runs Python inside the Unreal Editor; the Unreal MCP toolsets use it to drive the editor.

## Use it for
- Stats scripts, bulk FBX import, outliner and tag setup, capture-camera setup (Unreal worker only).

## How to call it
- Through the Unreal MCP Python toolset (see mcp.unreal-mcp), or Output Log `py <file>`.
- API root: `import unreal`; asset and level helpers are in ue.editorscriptingutilities.

## Settings that matter
- Keep scripts in the work folder, not the repo's third-party content.
- Wrap multi-step edits in `unreal.ScopedEditorTransaction` so undo works.

## Gotchas
- Only the Unreal worker may run it against the live editor (one writer rule).
- Long scripts can hang the editor; chunk big loops.
- Plugin sits under Experimental in 5.8.

## Don't use it for
- Runtime gameplay code.
- Anything Blender-side.

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
