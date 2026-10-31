# Credits

## Skills adapted into pipeline skills

| Skill | Based on | Licence |
| --- | --- | --- |
| `set-dressing` | arjun988/blender-skills `set-dressing` | MIT |
| `supervisor` | arjun988/blender-skills `qa-review` | MIT |
| `blender-adapter` (collections) | arjun988/blender-skills `scene-assembly` | MIT |
| `blender-adapter`, `modeling` (export, budgets, naming) | arjun988/blender-skills `unreal-export`, `references/polycount-budgets.md`, `realistic-style/references/scan-cleanup.md` | MIT |
| `blender-adapter` (CG route camera and light facts, 30 Oct 2026) | arjun988/blender-skills `archviz` | MIT |

Upstream for the arjun988 skills: https://github.com/arjun988/blender-skills at commit `8f778d2405a214b508d4c7d80742be8e43acdd52` (v1.3.0, MIT, copyright 2026 blender-skills contributors). The adapted skills were rewritten for this pipeline's phases, gates and the official Blender and Unreal MCP servers; tuning notes go in `feedback/<skill>.md`.

Web sources for each skill are listed at the end of the skill or its reference files.

## Installed third-party skills

Copied with their licence files. Each one has a "Pipeline notes" section at the top that says what was changed; the rest is the upstream text.

| Skill | Upstream | Commit | Licence | Changes |
| --- | --- | --- | --- | --- |
| `ue5-mcp` | [ibrews/ue5-mcp](https://github.com/ibrews/ue5-mcp) `SKILL.md` (v3.3.0) | `116234bb0d5a8f59f9738cfe1e5ff76c03272e31` | MIT, copyright 2026 Alex Coulombe Presents | Pipeline notes added (a correction to section 10.1, October 2026). 30 Oct 2026: description narrowed (loaded on demand, no longer preloaded by the Unreal worker); notes gained read, skip and load-on-demand lists with line ranges and two flagged contradictions (section 7 Note actors, section 2.1 snake_case) |
| `blender-image-to-3d` | [majidmanzarpour/blender-game-skills](https://github.com/majidmanzarpour/blender-game-skills) `skills/blender-image-to-3d` (without `evals/`) | `f0ef29385a03de139957e6f700b801cdc00b7e29` | MIT, copyright 2026 Majid Manzarpour | Description narrowed, pipeline notes added (including a warning not to use its FBX export settings for Unreal). 30 Oct 2026: notes gained the tolerance order, an environment-asset path and on-demand loading; `scripts/validate.py` and `scripts/export_delivery.py` patched to accept `UCX_` colliders skip UV and material checks on colliders, and exit 1 when nothing was validated or on an exception (each change marked `# Pipeline patch 30 Oct 2026`), with `scripts/selftest_pipeline_patch.py`; `scripts/review_render.py`, `roundtrip.py` and `world_gate.py` make the render path absolute (Blender writes a relative one under the drive root); `scripts/export_delivery.py` converts text objects (FONT) to mesh in its own run so exports keep them (marked `# Pipeline patch 30 Oct 2026`, covered by `selftest_pipeline_patch.py`) |
| `environment-artist`, `geometry-nodes`, `collision-proxy`, `lod-pipeline` | [arjun988/blender-skills](https://github.com/arjun988/blender-skills) (v1.3.0) | `8f778d2405a214b508d4c7d80742be8e43acdd52` | MIT, copyright 2026 blender-skills contributors | Descriptions narrowed, metadata blocks removed, pipeline notes added. `geometry-nodes`: a cables note (the user's cable generator, guide curves), 29 Oct 2026. 30 Oct 2026 notes: `geometry-nodes` (GN_ names are examples; conduit uses the kit, cables the user's rig; service runs from `plan/services.yaml` use `linear-runs`), `collision-proxy` (one name `UCX_SM_<Name>_NN`; authoring rule 5 replaced), `environment-artist` (wear, damage and decal rows ignored in every mode; minimum viable kit only when fidelity is inspired) |
| `level-design` | [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) `skills/disciplines/level-design` | `19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9` | Apache-2.0, copyright 2026 Abhishek Barali and contributors (`LICENSE`, `NOTICE`) | Description narrowed, pipeline notes added (October 2026). 30 Oct 2026: description corrected (layout-2d reads it, and blockout on walkable scenes); notes list what to read and what to skip |

Retired: `archviz` (arjun988/blender-skills, MIT) was deleted on 30 Oct 2026 because nothing loaded it; its lens, vertical correction and HDRI facts moved into `blender-adapter`, credited above.

## Installed tools (configured, not copied)

| Tool | Where it's set up | Licence |
| --- | --- | --- |
| Epic Games, Unreal Engine Skills for Claude Code (`unreal-engine-skills-for-claude-code`, v3.1.2 at commit `0e27bde2b55c5d3f6948532f4296aaa3654d8f4b`) | `.claude/settings.json`, from the `claude-plugins-official` marketplace | MIT |
| Blender Lab MCP server v1.0.3 (`2cea8d566dde07fbac28a61d698909d69724e853`) | `.mcp.json`, started with `uvx`; the add-on is installed in Blender | GPL-3.0-or-later |

Not installed: the community Unreal and Blender servers (only needed below UE 5.8 or Blender 5.1). Tripo has no MCP server here: the `tripo-props` skill drives Tripo Studio in the browser and its DCC Bridge add-on in Blender, from the user's own workflow.
