---
name: unreal-adapter
description: Unreal Engine 5.8 specifics for the scene pipeline, covering the MCP tools, content folders, outliner and tag conventions, FBX and transfer import, captures from the review cameras, the stats script and the pass switch. Workers load it before any Unreal step.
---

# Unreal adapter (UE 5.8)

## Tools

- **Server:** Epic's ModelContextProtocol plugin, configured as `unreal-mcp` in the repo's `.mcp.json` (HTTP, `http://127.0.0.1:8000/mcp`; set `UE_MCP_PORT` for another port). With Epic's optional proxy installed it appears as `unreal-mcp-proxy`. The project needs the `ModelContextProtocol` and `AllToolsets` plugins enabled, and the server started (auto-start is set up by `docs/setup-windows.md`).
- **Tool search is on**, so the server shows three tools: `list_toolsets`, `describe_toolset` and `call_tool`. Find the toolset, read its schema with `describe_toolset`, then dispatch with `call_tool` (`toolset_name`, `tool_name`, `arguments`). `ProgrammaticToolset.execute_tool_script` runs Python in the editor for batches. The toolbox scanner records the toolsets it finds in `toolbox/tools/mcp.unreal-mcp.md`.
- **Read first:** Epic's `unreal-mcp` skill from the `unreal-engine-skills-for-claude-code` plugin (enabled in `.claude/settings.json`) for the call flow and safety rules, and the `ue5-mcp` field manual for engine gotchas and crash patterns. Check the project's own Agent Skills with `AgentSkillToolset.ListSkills`.
- **One writer.** Only the Unreal worker changes the editor. The server accepts concurrent calls, but Epic warns that conflicting changes from several agents can break things. Imports of finished assets from the asset lane go through the Unreal worker in batches between its own steps.
- **Check every result.** Many tools report failure in the result instead of raising an error. Treat anything that isn't an explicit success as a stop.
- **The pipeline's own tools.** `ProgrammaticToolset.execute_tool_script` runs in a sandbox that can't `import unreal`, so the scripts in `scripts/` are registered as the `pipeline_toolset.PipelineTools` toolset by `scripts/pipeline_toolset.py`, loaded from the project's `Content/Python/init_unreal.py` at editor start. Its tools are `capture_set`, `write_stats` and `place_layout`. Each call re-reads its script, so script fixes apply without a restart. Setup and the tested call shapes are in `toolbox/tools/mcp.unreal-mcp.md`.
- Python runs in the editor (`PythonScriptPlugin` and `EditorScriptingUtilities` enabled). `capture.py`, `stats.py` and `import_layout.py` were tested in UE 5.8.3 on 27 Oct 2026; `apply_palette.py` still needs its first run.

## Conventions

| What | Convention |
| --- | --- |
| Content | `/Game/<Slug>/Maps`, `Meshes`, `Materials`, `Textures`, `PCG`, `Blueprints` |
| Level | `/Game/<Slug>/Maps/L_<Slug>` |
| Outliner | One folder per phase (`P0_Site` to `P9_Life`), plus `Lights`, `Cameras`, `Blockout` |
| Actor tags | `phase:P3`, `map:W01`, `cluster:C04`, `src:generate` (the stats script reads them) |
| Cameras | `CineCameraActor` named `CAM_<id>` from `light/cameras.json` |
| Materials | `M_Env_Master`, `MI_<Group>` per material group, child instances per asset; `MPC_LookDev` holds `PassMode` |

## Import

- FBX goes through Interchange in UE 5.x. Keep normals from the file (don't recompute) so custom normals survive, turn off generated collision when `UCX_` meshes exist, and enable Nanite for opaque static meshes. Save the working import settings in `toolbox/tools/transfer.blender-unreal.md` after the first test.
- Check every import: a known edge measured in centimetres, collision shown in wireframe, LODs detected, material slots matching `material_group`.
- Transfer route: `scripts/import_layout.py` spawns actors from `transfer/layout.json` and replaces the previous transfer on a re-run.

## Captures

`scripts/capture.py` (`PipelineTools.capture_set`) renders each review camera at 1920 × 1080 through a temporary SceneCapture2D, with the camera's lens and the locked exposure, so it works with the editor in the background. Only Lit is possible this way: Lighting Only is a viewport setting that scene captures ignore. For the L1 read, set `MPC_LookDev.PassMode` to the gray pass and capture Lit. Check exposure with the HDR (Eye Adaptation) visualisation in the editor viewport. Never move a review camera to fix a shot.

## Stats

`scripts/stats.py` writes `stats.json`: actors by phase and source, unique meshes, triangles (Nanite and fallback), material instances by group, lights by type and shadow casting, and at L3 texture sets and memory.

## Performance (game routes, from P5 and at L3)

At each review camera, record the frame time with `stat unit` (game, draw, GPU) and `stat gpu` in a standalone or PIE session on the target machine, and add it to `stats.json`. Treat it as a guide; the editor adds its own cost.

## Lighting

Directional light in lux, Sky Atmosphere, Sky Light with real-time capture, Exponential Height Fog, Lumen. A Post Process Volume with Min EV100 = Max EV100 = the brief's target. Pass switch: `MPC_LookDev.PassMode`, palette through `apply_palette.py` (see `docs/pipeline/lighting.md`).
