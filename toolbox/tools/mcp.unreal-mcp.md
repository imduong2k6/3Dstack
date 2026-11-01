---
id: mcp.unreal-mcp
kind: mcp_server
name: Unreal Engine MCP (Epic ModelContextProtocol plugin)
version: "UE 5.8.3, plugin 1.0"
checked: 2026-10-27
sources:
  - live server on the author's PC (SkillTest, UE 5.8.3-58210709), tools/list + list_toolsets + describe_toolset on every toolset
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/ModelContextProtocol (Source/ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h)
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/programmatic.py
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/registration.py
pipeline_stages: [blockout, placement-phases, set-dressing, lighting-passes, gate-board]
routes: [unreal, blender_unreal]
---

# Unreal Engine MCP

**What it does:** Epic's `ModelContextProtocol` plugin runs an HTTP MCP server inside the editor (`http://127.0.0.1:8000/mcp`). `AllToolsets` registers 52 toolsets (830 tools) with it. The repo's `.mcp.json` names it `unreal-mcp`, and the Unreal worker drives the open level through it.

Same plugin set as manifest ids `ue.modelcontextprotocol`, `ue.alltoolsets`, `ue.editortoolset` and `ue.mcpclienttoolset`.

## Setup (verified 2026-10-27)

- `.uproject` plugins: `ModelContextProtocol`, `AllToolsets`, `PythonScriptPlugin`, `EditorScriptingUtilities` (plus `EditorToolset`, `MCPClientToolset`, already on in SkillTest).
- `Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini`: `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]` `bAutoStartServer=True`. Port is `ServerPortNumber` (default 8000) in the same section. Close the editor before editing this file, or it writes its own copy back on exit.
- The log line `LogModelContextProtocol: Tool search enabled: registered 3 meta-tools (N toolsets discoverable via list_toolsets)` means the server is up.
- Claude Code: `.mcp.json` servers stay "Pending approval" until someone trusts the folder in an interactive `claude`. `claude -p ... --mcp-config .mcp.json` loads them for one run without changing any settings.

## How to call it

Tool search is on, so `tools/list` shows only three tools:

- `list_toolsets` returns the toolset names and descriptions.
- `describe_toolset(toolset_name)` returns every tool's input schema and, usually, its output schema. Read it before calling.
- `call_tool(toolset_name, tool_name, arguments)` runs one tool. `tool_name` is the short name, for example `find_actors`.

Object arguments are `{"refPath": "<soft path>"}`, for example `{"refPath": "/Game/Maps/L_X.L_X:PersistentLevel.CineCameraActor_0"}`, and classes are `{"refPath": "/Script/CinematicCamera.CineCameraActor"}`. Transforms are `{"location": {x,y,z}, "rotation": {pitch,yaw,roll}, "scale": {x,y,z}}` in cm and degrees.

### Tools the pipeline uses

| Need | Toolset . tool |
| --- | --- |
| Open, check level | `editor_toolset.toolsets.scene.SceneTools` . `load_level`, `get_current_level` |
| Find, spawn, delete actors | `SceneTools` . `find_actors` (filter by `name`, `tag`, `actor_type`), `add_to_scene_from_asset`, `add_to_scene_from_class`, `remove_from_scene`, `merge_actors` |
| Outliner folders | `SceneTools` . `set_actor_folder`, `get_folders`, `get_actors_in_folder` |
| Transform, label, tags, bounds | `editor_toolset.toolsets.actor.ActorTools` . `set_actor_transform`, `get_actor_transform`, `set_label`, `add_tag`, `get_tags`, `get_actor_bounds` |
| Properties on any object | `editor_toolset.toolsets.object.ObjectTools` . `get_properties`, `set_properties`, `list_properties` |
| Assets and folders | `editor_toolset.toolsets.asset.AssetTools` . `find_assets`, `exists`, `create_folder`, `duplicate`, `save_assets`, `is_dirty`, `read_file`, `write_file` (only under /Game, plugin Content or Saved) |
| Mesh import and checks | `editor_toolset.toolsets.static_mesh.StaticMeshTools` . `import_file`, `get_bounds`, `get_triangle_count`, `get_lod_count`, `is_nanite_enabled`, `set_nanite_enabled`, `get_material_slots`, `generate_lods` |
| Materials | `editor_toolset.toolsets.material.MaterialTools`, `editor_toolset.toolsets.material_instance.MaterialInstanceTools` |
| Viewport | `EditorToolset.EditorAppToolset` . `CaptureViewport` (base64 PNG at viewport size), `SetCameraTransform`, `GetCameraTransform`, `FocusOnActors`, `SearchCVars` |
| Editor log | `EditorToolset.LogsToolset` |
| PCG | `PCGToolset.PCGToolset` (30 tools), `PCGToolset.PCGSpatialToolset` |
| Pipeline scripts | `PipelineTools` (below) |

### PipelineTools (the adapter scripts)

`ProgrammaticToolset.execute_tool_script` is **not** general Python. It runs a sandbox that can import only `json`, `math`, `re`, `time`, `datetime` and `copy`, can call other tools through `execute_tool(name, json)`, and can open files read-only. It cannot `import unreal`. Use it to batch toolset calls, never for the adapter scripts.

The adapter scripts run through a project toolset instead. `.claude/skills/unreal-adapter/scripts/pipeline_toolset.py` registers `PipelineTools` with Epic's toolset registry, and the project loads it at editor start from `<Project>/Content/Python/init_unreal.py`. On SkillTest it's listed as `PythonTypes.PipelineTools_0xA0B6CD3A`; the suffix is Unreal's, so find it with `list_toolsets`.

| Tool | Script | Arguments |
| --- | --- | --- |
| `capture_set` | `capture.py` | `out_dir`, `labels` (camera labels), `view_modes` (`["lit"]`), `width`, `height` |
| `write_stats` | `stats.py` | `path` |
| `place_layout` | `import_layout.py` | `layout_path`, `mesh_root`, `folder` |

Each call re-reads the script, so script fixes apply without a restart. A change to `pipeline_toolset.py` needs an editor restart.

### Plain HTTP client (tested 2026-11-01)

When the MCP client won't connect but the server answers: POST JSON-RPC to `/mcp` with `Content-Type: application/json` and `Accept: application/json, text/event-stream`. Send `initialize`, keep the `Mcp-Session-Id` response header on every later request, send `notifications/initialized`, then `tools/call` with `name` `call_tool` and `arguments` `{toolset_name, tool_name, arguments}`. A response may be an event stream; the JSON is on the last `data:` line. About 40 lines of standard-library Python.

### Without PipelineTools (tested 2026-11-01)

A project without the `init_unreal.py` hook has no `PipelineTools`, and no way to run editor Python over MCP. `list_toolsets` also shows fewer toolsets without `AllToolsets` (about 26). Everything below worked with `EditorToolset` alone:

- **New level:** `AssetTools.duplicate` from `/Engine/Maps/Templates/Template_Default`, `save_assets`, `load_level`. The template brings a floor, sky sphere, clouds, fog and a PlayerStart. Its DirectionalLight and SkyLight are already Movable, with real-time capture on.
- **Spawning:** `add_to_scene_from_asset` with `xform`; `name` becomes the label. Batch it with `set_actor_folder` and `add_tag` through `execute_tool_script`.
- **Rotations:** work out the rotator on the client (`FQuat::Rotator`); read-back matched the request.
- **Captures:** `EditorAppToolset.CaptureViewport` with `captureTransform` renders that pose without moving the user's viewport or spawning an actor. The image is at the viewport's size and the result reports `cameraFOV` (90 on a default viewport). No tool sets the FOV, so a longer lens is a centre crop, and anything wider than the viewport, a portrait frame or a lens shift can't be matched. No tool exports a render target or runs a SceneCapture. Light and brush gizmos and the engine's red warning text draw into the image even with `bShowUI` false, so park those actors away from the frame. A capture uses the viewport's current view mode, and no tool reads or sets it: a viewport left in Unlit gives flat colours whatever the lights and exposure are, so read the mode with `CaptureEditorImage` first. Behind other windows the editor ticks at 3 fps, and Lumen barely converged over 5 minutes, so an exposure read there isn't a settled one.
- **Exposure:** with `AEM_Manual` and `autoExposureApplyPhysicalCameraExposure` false, EV100 is minus the bias. Outside the safe range -8 to 12 the engine warns (`r.EyeAdaptation.CachedLightingPreExposure`) and prints the warning into captures.
- **A capture can stop the editor.** On 2026-11-01 a `CaptureViewport`, one every 15 s or so on a level of about 7,500 Nanite actors with Lumen, failed with D3D12 `E_OUTOFMEMORY` in `D3D12TransientResourceAllocator`. The log ended in a render-target pool dump, the frame counter stopped, MCP stopped answering `initialize`, and no crash dialog appeared. `dwm.exe` died with `0xc00001ad` in the same second and restarted 10 s later. GPU memory read 7.4 of 32 GB afterwards, so the cause isn't proven. Save before a run of captures, and check that a hung editor's level and assets are on disk before anyone ends the process.
- **Stats:** no console tool, so `stat unit` can't be read. The log's `[frame]` field gives real frame rate between two log lines, modulo 1000.

## Gotchas

- Inputs marked as defaults can still be required: `find_assets` needs `name`, `find_actors` needs `name`, `tag` and `collision_channels`, and `CaptureViewport` needs `captureTransform` and `annotations` with all its fields (`classFilter` may be null). The error prints the schema.
- `ObjectTools` property names are the camelCase ones from `list_properties` (`overrideMaterials`, `staticMaterials`). `get_properties` fails the whole call if one name is unknown.
- A failing tool inside `execute_tool_script` ended the script even inside `try`/`except`, with the error as the result. Filter inputs first: `find_assets` also returns `__ExternalObjects__` paths, which `is_dirty` rejects.
- Each tool call inside a script takes about one editor tick or more. An editor in the background runs about 3 frames a second, so speed swung from about 60 calls a second to about 5 in the same run. Keep batches small, because the editor is held between them.
- Spawning raises "Cannot create actors while PIE is active" if the user presses Play. Check `IsPIERunning` before each batch, and make long runs resumable.
- Results report failure with `isError: true` and a message (for example `load_level` on an unsaved level: "the level has unsaved changes"). Check every result.
- `load_level` refuses a dirty level. A level made with `AssetTools.duplicate` is dirty until `save_assets` saves it.
- `StaticMeshTools.import_file` uses the legacy FBX importer with defaults: Nanite off, no materials. Turn Nanite on afterwards with `set_nanite_enabled`. Tested results are in `transfer.blender-unreal.md`.
- No console-command tool and no high-res screenshot tool. Review captures go through `PipelineTools.capture_set`.
- Epic warns against several agents writing at once. Keep one writer (the Unreal worker).

## Don't use it for

- Arbitrary editor Python. Add a tool to `PipelineTools` instead.
- Blender-side work; that goes to `mcp.blender`.

## Version notes

- UE 5.8.3: 52 Epic toolsets / 830 tools with `AllToolsets` on. Tool search shows 3 meta-tools.

## All toolsets on SkillTest (2026-10-27)

| Toolset | Tools | Description |
| --- | --- | --- |
| `aimodule_toolset.toolsets.behavior_tree.BehaviorTreeTools` | 7 | Inspect BehaviorTree (BT) assets. |
| `animation_toolset.toolsets.conditions.SequencerConditionTools` | 9 | Runtime conditions on Sequencer tracks and sections |
| `animation_toolset.toolsets.controlrig.ControlRigTools` | 44 | Create and edit Control Rig assets |
| `animation_toolset.toolsets.controlrig_sequencer.SequencerControlRigTools` | 72 | Animate with Control Rig inside Sequencer |
| `animation_toolset.toolsets.custom_bindings.SequencerCustomBindingTools` | 8 | Convert and manage custom binding types in Sequencer |
| `animation_toolset.toolsets.import_export.SequencerImportExportTools` | 6 | Import and export animation data to and from Sequencer |
| `animation_toolset.toolsets.keyframing.SequencerKeyframingTools` | 22 | Keyframe properties in Sequencer |
| `animation_toolset.toolsets.outliner.SequencerOutlinerTools` | 18 | Inspect and manage the Sequencer outliner tree |
| `animation_toolset.toolsets.sequencer.SequencerTools` | 140 | Create and edit Level Sequences |
| `AutomationTestToolset.AutomationTestToolset` | 7 | Automation test discovery and execution |
| `ConfigSettingsToolset.ConfigSettingsToolset` | 8 | List, inspect and edit Config Settings sections |
| `conversation_toolset.toolsets.conversation.ConversationTools` | 7 | Inspect Conversation Graph dialogue assets |
| `DataflowAgent.DataflowAgentToolset` | 22 | Dataflow graph editing |
| `DataRegistryToolset.DataRegistryTools` | 7 | Query and inspect Data Registries |
| `editor_toolset.toolsets.actor.ActorTools` | 17 | Inspect and modify actors |
| `editor_toolset.toolsets.asset.AssetTools` | 21 | Assets in the project and files on disk |
| `editor_toolset.toolsets.blueprint.BlueprintTools` | 53 | Blueprints |
| `editor_toolset.toolsets.curve_table.CurveTableTools` | 9 | CurveTable assets |
| `editor_toolset.toolsets.data_asset.DataAssetTools` | 1 | Data Assets |
| `editor_toolset.toolsets.data_table.DataTableTools` | 10 | DataTable assets |
| `editor_toolset.toolsets.material.MaterialTools` | 22 | Material and MaterialFunction assets |
| `editor_toolset.toolsets.material_instance.MaterialInstanceTools` | 13 | MaterialInstanceConstant assets |
| `editor_toolset.toolsets.object.ObjectTools` | 6 | Object properties |
| `editor_toolset.toolsets.primitive.PrimitiveTools` | 4 | Add primitive geometry components to actors |
| `editor_toolset.toolsets.programmatic.ProgrammaticToolset` | 2 | Sandboxed Python that batches tool calls |
| `editor_toolset.toolsets.scene.SceneTools` | 20 | The loaded level: load, place, remove, folders, traces |
| `editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools` | 22 | Skeletal mesh assets |
| `editor_toolset.toolsets.static_mesh.StaticMeshTools` | 16 | Static mesh assets |
| `editor_toolset.toolsets.string_table.StringTableTools` | 8 | StringTable assets |
| `editor_toolset.toolsets.texture.TextureTools` | 2 | Texture assets |
| `EditorToolset.EditorAppToolset` | 21 | Editor state: cvars, asset images, selection, viewport camera, content browser, PIE |
| `EditorToolset.LogsToolset` | 4 | Read the output log, set log verbosity |
| `GameFeaturesToolset.GameFeaturesToolset` | 7 | Game Feature Plugins |
| `GameplayTagsToolset.GameplayTagsToolset` | 6 | Gameplay tags |
| `GASToolsets.AbilitySystemInspectorToolset` | 4 | AbilitySystemComponent runtime state |
| `GASToolsets.AttributeSetToolset` | 2 | AttributeSet classes |
| `GASToolsets.GameplayCueToolset` | 8 | Gameplay cues |
| `NiagaraToolsets.NiagaraToolset_Assets` | 3 | Niagara script asset discovery |
| `NiagaraToolsets.NiagaraToolset_Blueprint` | 2 | Niagara and Blueprint integration |
| `NiagaraToolsets.NiagaraToolset_Component` | 4 | Niagara Components on actors |
| `NiagaraToolsets.NiagaraToolset_Info` | 1 | Niagara guidance |
| `NiagaraToolsets.NiagaraToolset_System` | 46 | Niagara Systems, emitters, modules |
| `PCGToolset.PCGSpatialToolset` | 1 | PCG spatial (instant graphs) |
| `PCGToolset.PCGToolset` | 30 | Build and modify PCG graphs |
| `PhysicsToolsets.PhysicsAssetToolset` | 17 | Physics Assets |
| `PluginToolset.PluginToolset` | 17 | Create, edit, enable and query plugins |
| `PythonTypes.PipelineTools_0xA0B6CD3A` | 3 | The pipeline's adapter scripts (this repo) |
| `SemanticSearchToolset.SemanticSearchToolset` | 2 | Hybrid vector + BM25 asset search |
| `SlateInspectorToolset.SlateInspectorToolset` | 14 | Editor UI automation |
| `state_tree_toolset.toolsets.state_tree.StateTreeTools` | 9 | Inspect StateTree assets |
| `ToolsetRegistry.AgentSkillToolset` | 4 | List, read, create and update Agent Skills |
| `UMGToolSet.UMGToolSet` | 23 | UMG widgets |
| `WorldConditionsToolset.WorldConditionTools` | 2 | WorldCondition structs |
