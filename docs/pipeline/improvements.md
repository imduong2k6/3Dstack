# Changes, feedback and suggestions

## v5

### What you asked for and what v5 does

| You asked for | v5 | Where |
| --- | --- | --- |
| A horizontal flow that's easier to read on a phone | The flow is a row of stage cards grouped by phase. You swipe sideways through it, and the text stays full size instead of shrinking with one wide diagram | Review page |
| More specialised agents in parallel, based on the studio research | Yes for volume work: an asset lane with up to 4 Modelers, an Asset Tech and a Generator runs alongside the level lane. No for anything that writes to the live Unreal editor or the open Blender | [parallel.md](parallel.md), `.claude/agents/` |
| Install the suggested repos except Tripo | Epic's Claude Code plugin (project settings), the Blender Lab MCP server (`.mcp.json`), and 8 skills copied with their licences | [CREDITS.md](../../.claude/skills/CREDITS.md), [setup-windows.md](../setup-windows.md) |
| Use it from other Claude accounts and from Code | The repo is the package. A table says what works on your PC, through Remote Control from your phone, and in a cloud session | [setup-windows.md](../setup-windows.md#use-it-from-any-claude-code-session) |
| Check every change against the research first | Written into the repo's `CLAUDE.md`, so any Claude working in the repo follows it | [CLAUDE.md](../../CLAUDE.md) |
| Merge finished work into main | PR #1 (v4) and PR #2 (installs) are merged; this work goes in the next PR | GitHub |

### Conflicts I found, and what I did

- **Horizontal replaces your v3 request for vertical.** Held upright, a phone shows a horizontal flow one part at a time, so each phase is a card that snaps into place as you swipe. Turned sideways, the phone shows two or three cards at once.
- **The reviewers' Unreal guard never worked.** It blocked a server called `unreal`, but Epic's server is `unreal-mcp`. The agents now block `unreal-mcp`, `unreal-mcp-proxy` and `blender`.
- **"Never launch another Blender" blocked parallel work.** The rule is now one writer per live session. Headless Blender on a separate asset file is allowed, which is what lets several Modelers work at once.
- **Opus for scene work.** The Modelers and both workers stay on Opus as you asked. The new Asset Tech and Generator start on Sonnet because their work is scripted and checked by numbers. Change one line in their agent files if you want Opus from the start.
- **Reference photos in a public repo.** Photos, `.blend` and FBX files now stay in the work folder outside git, and only each photo's source link is kept in `refs/index.yaml`.
- **Copied skills competing with ours.** Their descriptions were narrowed so they don't trigger instead of the pipeline's own skills, and each has notes where it disagrees with our rules: Nanite first, collection names, one master material.
- **Tripo** stays an empty slot in `generated-asset` until you add your own workflow. Magnific is the only generation service for now.

### Suggestions

1. **Finish the pilot on the SkillTest corridor before a real project.** The setup runs on your PC now; the pilot follows.
2. **Start with 3 Modelers** and watch memory with Unreal open. Drop to 2 if the PC slows down.
3. **Take gate K seriously.** The pilots set the bar for the whole batch, so a fix there saves the same fix on every asset.
4. **Use Remote Control from your phone** for real projects. A cloud session can only plan, because it can't reach Unreal or Blender.

### Test on the first project (v5)

- [ ] Epic's plugin installs when the folder is trusted, and `/mcp` shows `unreal-mcp` and `blender` connected
- [ ] `bin/blender-bg` runs Blender headless from Git Bash on Windows
- [ ] The `blender-image-to-3d` scripts run in Blender 5.2 on Windows
- [ ] Three Modelers at once with Unreal open, without running out of memory
- [ ] Gate K shows on the board and blocks the batch until approved

## v4

### Your feedback and what v4 does

| You asked for | v4 | Where |
| --- | --- | --- |
| No project name or deadline in the form | Removed. The title comes from your text, a deadline goes in the prompt, and Duplicate copies a brief for another project | Form, `scene-intake` |
| Short project picks | Three short choices: Making (scene, object), For (game, CG, not sure), Built in (Unreal; Blender then Unreal; Blender only) | Form |
| A prompt box with images instead of chips | Project, Context and Lighting each switch between quick options and "Describe with images" (text plus up to 12 images, by drop, paste or upload) | Form |
| Chat prompt is enough | The intake reads your chat message and images. The form is sent only when three or more required things are missing | `scene-intake` |
| Opus for the Unreal and Blender workers | Both workers, the new Modeler and both reviewers run on Opus | `.claude/agents/` |
| Toolbox scanner researches docs and only scans new tools | A script with signatures and a manifest per machine; one instruction file per tool from local and online docs; only new or changed tools are researched | `toolbox-scan`, `toolbox/` |
| Researchers learn from professionals and suggest improvements | Workflow research at Stage 1, problem research when a step fails twice, and a retro at the end with up to 10 ranked suggestions | `workflow-research`, `retro` |
| Stage 0 interview and a plan to approve | Multiple-choice rounds until nothing important is unclear, then `plan.md`, approved at G0 | `input-review`, `scene-interview` |
| Stage 1 pro workflows and tricks | Rated findings, adopt now, test first or later; adopt-now items come to you at G1 | `workflow-research` |
| Blender then Unreal, or Blender only for CG | Three routes, with a transfer stage and gate T for Blender then Unreal | [routes.md](routes.md) |
| Build the skills from online skills and tune them | 25 skills, four adapted from arjun988/blender-skills (MIT) with credits, plus a feedback loop per skill | `.claude/skills/` |
| A Modeler agent, plus SubD, game and Ian Hubert-style research | Modeler on Opus with a modelling skill and five references | `modeling` |
| Research real game and CG environment teams | Roles, team sizes, creative vs repetitive work, technical requirements per step, and eight changes made because of it | [studio-workflows.md](studio-workflows.md) |

### Where I went a different way

- **The interview runs in the main session.** Claude Code subagents can't ask you questions, so the input reviewer writes them and the manager asks.
- **The toolbox scanner is on Sonnet, not Haiku.** It now reads docs and writes instructions. The scanning itself is a script, so it costs almost nothing.
- **Modelling skill.** The modelling skill is an English paraphrase with credit, keeping the principles and methods and dropping the exercise logs (exact measurements of the mouse button, cosmetics bottles and so on). The original Vietnamese files are not in the repo. If you want them stored too, say so.
- **Bevels on the game route.** The course's default is holding loops and no Bevel modifier, which the SubD route keeps. Game mid-poly assets use bevels with weighted normals instead, because that's the standard way to get clean shading without a baked normal map.
- **Rough light on the Blender then Unreal route** is judged for direction only at G2, because the final light is built in Unreal after the transfer.

### Suggestions

Ranked by how much time I expect each to save.

1. **Run a small pilot first.** One room on the Unreal route, about half a day. It checks the Unreal script sketches, the MCP tool names, the FBX settings and the board round trip before a real project depends on them. If you plan to use Blender then Unreal, add the arrow test for the axis conversion.
2. **Keep a kit and trim library across projects.** After each project, move the approved kit pieces, trim sheets and their specs into a shared library, and let the toolbox scan list it. Studios reuse kits across levels; this is the biggest long-term speed-up.
3. **Approve phases in batches,** for example P0 to P2, P3 and P4, P5 to P7, P8 and P9. Fewer waits, same reviews.
4. ~~Name the MCP servers.~~ Done in v5: `.mcp.json` in the repo names them `unreal-mcp` and `blender`.
5. **Script repetitive steps rather than downgrading models.** Opus on every worker is the most capable and the most expensive setup. Exports, renames, stats and captures are now scripts, which saves more than switching models would.
6. **Shoot references with a scale anchor:** a person, a door, a tape measure. Missing scale anchors are the input review's most common blocker.
7. **Keep large reference sets in your folder** and point to it. Form images are fine for a few key shots (up to 20 MB each), but the folder is easier to manage.
8. **Look at the retro numbers after two or three projects.** `feedback/projects.md` will show which stage takes the longest; target that one first.
9. **For CG shots later,** add a compositing hand-off (AOV list and naming). Compositing is the last step in VFX pipelines and is out of scope today.

### Test on the first project (v4 list)

- [ ] Toolbox scan records the Unreal and Blender MCP tool names
- [ ] Unreal `capture.py`, `stats.py` and `import_layout.py` run in 5.8
- [ ] FBX round trip: a 1 m cube imports as 100 units, custom normals survive
- [ ] Arrow test for the Blender to Unreal transfer (route `blender_unreal`)
- [ ] Workbench and EEVEE captures in your Blender (tested here with Cycles only, headless)
- [ ] The interview's multiple-choice rounds in your Claude Code version
- [ ] Board: uploads, decisions, `pickedUp`
- [ ] Form: images uploaded in "Describe with images" are downloaded into `refs/inbox/`
