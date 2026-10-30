# Parallel work

New in v5. The short answer to "should more agents work at once?" is yes, but only for the volume work. Studios split work the same way: several artists build kit pieces and props side by side, while one person owns the level, the light rig and the reviews ([studio-workflows.md](studio-workflows.md)).

## What runs at the same time

| Lane | Agents | Runs alongside | Why they don't collide |
| --- | --- | --- | --- |
| Research (Stage 1) | 2 or 3 researchers, one topic each, plus the toolbox scanner | Each other | Separate output files |
| Reviews (every review point) | Up to 4 supervisors, one aspect each (the aspects are listed in `supervisor`), and the Art Director (look and mood) | Each other | All read-only, one review file each, on the same captures, after `scene-lint` has run |
| Blockout lanes (Stage 3) | Headless agents, each building its own part file under a lane brief | Each other | Owned ID prefixes and seam owners; `lane-integration` joins them headless on a copy |
| Asset lane (Stage 4) | Generator, up to 4 Modelers (default 3), 1 or 2 Asset Techs | The level lane | One asset per `.blend`, headless Blender, never the live session |
| Level lane (Stage 5) | Unreal worker, or the Blender worker on the Blender routes | The asset lane | The only writer in the live editor |

## What stays single, and why

- **The live Unreal editor has one writer.** Epic's MCP server accepts concurrent calls, but Epic's own skill warns that conflicting changes from several agents can break things and asks for mutations to be serialised. A second editor on the same project would fight over the same assets.
- **The open Blender session has one writer.** The Blender MCP add-on serves one socket on one port, and the Blender worker owns it. It gets short jobs: a fresh live worker for each batch of steps, handed `plan/steps.json`, with joining and probing moved to headless agents (`lane-integration`).
- **Creative calls have one owner:** layout, kit design, the pilots, the lighting passes and art direction. In studios these stay with one person or a lead.
- **GPU renders.** One GPU renders one thing at a time well, so parallel renders don't finish sooner.

## The asset lane

1. **Kit plan and trim sheet** (manager, `modular-kit`). `plan/assets.yaml` lists every asset with its source and a batch.
2. **Generation starts at once.** The Generator submits every `source: generate` job in one go (Tripo Studio in the browser, or Magnific; only when `detail` is `detailed` or `final`) and drops the results in each asset's work folder.
3. **Pilots, gate K.** One kit piece and one prop: one Modeler builds them, the Asset Tech finishes them, the supervisor and the Art Director review them, and you approve them at K. Nothing is batched before K, the same way studios start with a paid test asset.
4. **Batch.** The manager splits the remaining assets across up to `parallel_modelers` Modelers by type (kit pieces, props, generated repairs), as VFX teams split work by asset type. A hero asset gets a Modeler to itself.
5. **Finish.** The Asset Tech picks up each mesh as it passes review: collision, LODs where Nanite can't be used, export, and a re-import check.
6. **Review.** The supervisor reviews finished assets in groups of up to five, one contact sheet each.
7. **Hand-over.** The level lane imports finished assets in batches between its own steps and swaps them in for their proxies.

## The level lane

- After G2 the worker places P0 to P4 with the blockout's kit-sized proxies. The grid is locked at G1, so proxies and final pieces share sizes and pivots.
- P5 to P7 use proxies with the spec's bounding box and clearance zone until the final asset arrives.
- Placement gates judge position, clearance and story. The look is judged once the final assets are in, and the lighting passes start only when every asset in P0 to P7 is final (`house-rules` 7).

## Settings

In `brief.yaml`, set in the interview:

```yaml
parallel_modelers: 3       # 1 to 4
parallel_asset_tech: 1     # 1 or 2
generation_services: [magnific]   # add tripo for detailed props
work_dir: "D:/.../PipelineWork/<slug>"   # .blend and FBX files, outside git
```

## Costs and limits

- **Tokens:** the same assets get built either way, so the total work is about the same. Each extra agent adds its own start-up context (skills, spec, references), so a few parallel agents cost a little more than one doing everything in turn.
- **Time:** Stage 4 shortens roughly with the number of Modelers until your review time or the PC becomes the limit.
- **The PC:** each headless Blender takes memory and CPU while Unreal is open. Start with 3 Modelers and drop to 2 if the PC slows down.
- **Your time:** more assets arrive at once. The pilots at K set the bar so the batch needs fewer rounds.
- **Permission prompts:** background agents send their prompts to your main session. Approve `bash bin/blender-bg` for the session once.
- **Claude Code's limit** is 20 subagents running at once by default. The pipeline stays well below it.

## Agents I didn't add

- **A separate set dresser or level artist.** It would share the live editor with the worker.
- **A separate lighting agent.** The passes run in order, and one owner keeps the rig consistent.
- **Supervisors split by asset.** One supervisor per aspect keeps the bar the same for every asset. Splitting by aspect does the same job, since each aspect has one owner across the whole scene and every round. One supervisor on a 1,200-object scene reviewed it too thinly (user, 29 Oct 2026).
- **Agent teams mode.** Live messaging between agents is experimental and costs more tokens. File hand-offs and the manager's merged fix list do the same job here. The user chose subagents for now (29 Oct 2026) and will revisit Agent Teams when the feature is out of experimental: the likely first uses are Modelers splitting a batch and the supervisor and Art Director settling a disagreement directly.

## Sources

- Epic Games, [Unreal Engine Skills for Claude Code](https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin): `unreal-mcp` safety rules on concurrent calls, and running several editors.
- Blender Lab, [MCP server](https://projects.blender.org/lab/blender_mcp): one add-on socket per Blender, host and port in its preferences.
- Claude Code docs, [subagents](https://code.claude.com/docs/en/sub-agents): background subagents keep MCP tools and Bash, prompts go to the main session, 20 running at once by default.
- Studio staffing and outsourcing: [studio-workflows.md](studio-workflows.md).
