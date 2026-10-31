---
name: unreal-adapter
description: Unreal Engine 5.8 specifics for the scene pipeline, covering the MCP tools, a digest of the ue5-mcp rules that bite here, content folders, outliner and tag conventions, state rules (parked actors, the step ledger, saves), FBX and transfer import, captures from the review cameras, the stats script, and the lighting path (not built yet). Workers load it before any Unreal step.
---

# Unreal adapter (UE 5.8)

## Tools

- **Server:** Epic's ModelContextProtocol plugin, configured as `unreal-mcp` in the repo's `.mcp.json` (HTTP, `http://127.0.0.1:8000/mcp`; set `UE_MCP_PORT` for another port). With Epic's optional proxy installed it appears as `unreal-mcp-proxy`. The project needs the `ModelContextProtocol` and `AllToolsets` plugins enabled, and the server started (auto-start is set up by `docs/setup-windows.md`).
- **Tool search is on**, so the server shows three tools: `list_toolsets`, `describe_toolset` and `call_tool`. Find the toolset, read its schema with `describe_toolset`, then dispatch with `call_tool` (`toolset_name`, `tool_name`, `arguments`). `ProgrammaticToolset.execute_tool_script` runs Python in the editor for batches. The toolbox scanner records the toolsets it finds in `toolbox/tools/mcp.unreal-mcp.md`.
- **Read first:** Epic's `unreal-mcp` skill from the `unreal-engine-skills-for-claude-code` plugin (enabled in `.claude/settings.json`) for the call flow and safety rules, then the digest below. The `ue5-mcp` field manual is not preloaded (about 14k tokens, mostly about systems this pipeline doesn't use). Load it when a call fails or does something silently different, or when you touch a system the digest doesn't cover, and read only the ranges its Pipeline notes list. Check the project's own Agent Skills with `AgentSkillToolset.ListSkills`.
- **One writer** (`house-rules` rule 2). Only the Unreal worker changes the editor. The server accepts concurrent calls, but Epic warns that conflicting changes from several agents can break things. Imports of finished assets from the asset lane go through the Unreal worker in batches between its own steps.
- **Check every result.** Many tools report failure in the result instead of raising an error. Treat anything that isn't an explicit success as a stop.
- **The pipeline's own tools.** `ProgrammaticToolset.execute_tool_script` runs in a sandbox that can't `import unreal`, so the scripts in `scripts/` are registered as the `pipeline_toolset.PipelineTools` toolset by `scripts/pipeline_toolset.py`, loaded from the project's `Content/Python/init_unreal.py` at editor start. Its tools are `capture_set`, `write_stats` and `place_layout`. Each call re-reads its script, so script fixes apply without a restart. Setup and the tested call shapes are in `toolbox/tools/mcp.unreal-mcp.md`.
- Python runs in the editor (`PythonScriptPlugin` and `EditorScriptingUtilities` enabled). `capture.py`, `stats.py` and `import_layout.py` were tested in UE 5.8.3 on 27 Oct 2026. `lookdev.py` (the pass switch and palette) does not exist yet: see Lighting.

## Digest of the `ue5-mcp` rules that bite here

Section numbers are in `ue5-mcp/SKILL.md`.

1. Read before you write and read the value back after: a success response proves little (§1, §9.3).
2. Save before you read from disk: dump and read tools serialise the saved `.uasset`, so an unsaved change looks undone (§2.4, §9.5). Save the level and dirty assets after every step.
3. Imports, shader compiles and Nanite builds are async: wait until they finish before you capture or judge a material; a material can take 10 to 30 s (§2.3, §5.10).
4. Never delete or modify an asset that actors still reference: it asserts `RegisteredElementType` and takes the editor down with its unsaved work. Swap the references first (§3.1).
5. Don't spawn and then immediately delete actors: the same assertion (§3.2). Move one actor instead, or leave a pause. `place_layout` destroys the old transfer before it spawns; if that ever asserts, make it two calls.
6. Identify actors by full path (`/Game/Maps/L.L:PersistentLevel.Name`), not label: two actors can share one (§4.1). Keep `CAM_<id>` labels unique.
7. Asset paths come in three forms: package `/Game/Foo/Bar`, object `/Game/Foo/Bar.Bar`, Blueprint class `/Game/Foo/Bar.Bar_C`. "Class not found" is usually the missing `_C` (§2.2, §4.2).
8. Enum values: pass the C++ short name (`AEM_Manual`) to MCP tools; the Python form (`unreal.EAutoExposureMethod.AEM_MANUAL`) is for scripts (§2.7).
9. Mobility, hidden flags and relative transforms live on the RootComponent, not the actor: a write aimed at the actor can report success and change nothing. Read it back (§2.8).
10. Lumen only sees Movable lights. A new DirectionalLight is Stationary, so set Mobility to Movable (§5.1).
11. Emissive only blooms above 1.0, and only with Bloom on in the Post Process Volume. Lamp and sign materials need both (§5.8).
12. Python property names: use the `unreal` module's snake_case (`texture_target`). The manual's claim that this silently fails doesn't match this pipeline's tested scripts; read back every write anyway (§2.1, and the note in `ue5-mcp`).
13. Python `print` goes to the editor log, not to the MCP result, and `execute_tool_script` can't `import unreal`. Return a string from a `PipelineTools` tool or write a JSON file in the work folder. Never use Note actors as a data channel (§7, and the note in `ue5-mcp`).
14. An argument error often names the valid values or the schema in its text: read `isError` and the message before you retry (§9.4, §8.1).
15. Sequencer and Movie Render: extending the playback range does not extend track sections, and the sequence package must be saved before a render. Load §5.15 to §5.17 before any sequence work.

## Conventions

| What | Convention |
| --- | --- |
| Content | `/Game/<Slug>/Maps`, `Meshes`, `Materials`, `Textures`, `PCG`, `Blueprints` |
| Level | `/Game/<Slug>/Maps/L_<Slug>` |
| Outliner | One folder per phase (`P0_Site` to `P9_Life`), plus `Lights`, `Cameras`, `Blockout`, `Parked` |
| Actor tags | `phase:P3`, `map:W01`, `cluster:C04`, `src:generate` (the stats script reads them) |
| Cameras | `CineCameraActor` named `CAM_<id>` from `light/cameras.json` |
| Materials | Planned, built by `lookdev.py` (not written yet): `M_Env_Master`, `MI_<Group>` per material group, child instances per asset; `MPC_LookDev` holds `PassMode` |

## State rules

- **Three visibility states, never delete to hide** (`house-rules` rule 5). Parked: the actor sits in the outliner folder `Parked`, Hidden In Game on and hidden in the editor. Review-only: the same flags, cleared only for a review capture's shot and set again after. Live: visible. This mapping is untested in UE 5.8: try it on three actors the first time the editor is open and write the result in `toolbox/tools/mcp.unreal-mcp.md`. Known gap: `stats.py` counts every level actor today, hidden ones included; fix it with the capture gaps below.
- **Save per step** (`house-rules` rule 4). After every step the worker saves the level and dirty assets, then copies the level's `.umap` (and its `__ExternalActors__` and `__ExternalObjects__` folders when the level uses One File Per Actor) to `<phase folder>/backups/<level>_<phase>_<nn>_<step>/`. Backups are never deleted.
- **Step ledger.** Each step adds an entry to `plan/steps.json` with the same fields as the Blender one: the backup path, the actor count and a hash of the actor labels, and a hash of the cameras and of the lights. `step_log.py` (in `blender-adapter`) reads a Blender file and can't log Unreal steps. Known gap: until an Unreal variant exists, the worker fills the entry from `write_stats` and appends it with a small editor script.
- **At session start** compare the open level with the last ledger entry. An actor that is gone with no logged step is the user's change: report it to the manager, don't undo it and don't count it as a worker mistake.

## Import

- FBX goes through Interchange in UE 5.x. Keep normals from the file (don't recompute) so custom normals survive, turn off generated collision when `UCX_` meshes exist, and enable Nanite for opaque static meshes. Save the working import settings in `toolbox/tools/transfer.blender-unreal.md` after the first test.
- Check every import: a known edge measured in centimetres, collision shown in wireframe, LODs detected, material slots matching `material_group`, sockets matching the spec's `sockets` (the FBX carries them as `SOCKET_` nulls under the mesh; the Unreal side is untested, see `toolbox/tools/transfer.blender-unreal.md`).
- Transfer route: `scripts/import_layout.py` spawns actors from `transfer/layout.json` and replaces the previous transfer on a re-run.

## Captures

`scripts/capture.py` (`PipelineTools.capture_set`) renders each review camera at 1920 × 1080 through a temporary SceneCapture2D, with the camera's lens and the locked exposure, so it works with the editor in the background. Only Lit is possible this way: Lighting Only is a viewport setting that scene captures ignore. The gray pass for the L1 read doesn't exist yet (see Lighting). Check exposure with the HDR (Eye Adaptation) visualisation in the editor viewport. Never move a review camera to fix a shot.

**Known gaps in `capture.py`, to fix the next time the editor is open** (a script change can't be tested without it):

- It reads only each camera's horizontal FOV and renders every camera at one size. It should read each camera's resolution, lens shift, portrait and ortho settings from `light/cameras.json`.
- It spawns and destroys a SceneCapture2D per camera, which is a listed crash pattern (digest 5). It should spawn one capture actor, move it to each camera, and remove it once at the end.

Until then a portrait, shifted or orthographic camera is not captured correctly in Unreal: say so on the gate instead of posting its image as a true capture.

## Stats

`scripts/stats.py` writes `stats.json`: actors by phase and source, unique meshes, triangles (Nanite and fallback), material instances by group, lights by type and shadow casting, and at L3 texture sets and memory.

## Frame time (game routes)

No pipeline tool measures it yet. The user measures it at L3, with `stat unit` and `stat gpu` in a standalone or PIE session on the target machine. The worker doesn't report a frame time and the supervisor doesn't check one until a tool is added to `PipelineTools`.

## Lighting

**The Unreal pass switch is not built.** `scripts/lookdev.py` doesn't exist. It is to create `MPC_LookDev` (scalar `PassMode`: 0 gray, 1 value, 2 hue, 3 textured), the master material `M_Env_Master`, one `MI_<Group>` per material group and the gray pass (every base colour 0.216 linear), and later set the group values and hues; `docs/pipeline/lighting.md` holds the sketch. Until it exists and has run once in UE 5.8, the Unreal lighting passes L1 to L3 can't run: stop and tell the manager, who plans it as its own step (editor open, one writer).

What can be built today is the neutral rig (`house-rules` rule 7): Directional light, Sky Atmosphere, Sky Light with real-time capture, Exponential Height Fog, Lumen, and a Post Process Volume with Min EV100 = Max EV100 = `light/exposure.json › ev100` (`house-rules` rule 8).
