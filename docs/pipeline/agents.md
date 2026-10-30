# Agents

You talk to the manager, through the Claude Code session and the two pages. Only the route's worker changes the live scene; the Modelers and the Asset Tech change only their own asset files, so they can run at the same time ([parallel.md](parallel.md)). Agent files live in `.claude/agents/`, skills in `.claude/skills/`. Every agent preloads `house-rules` (the standing rules in one place); the manager reads it at the start of every session.

| Agent | Job | Model | Edits the scene | Writes |
| --- | --- | --- | --- | --- |
| Manager | Main session. Intake, the Stage 0 interview, routing, gates, your decisions, merged fix lists, save points | The model you start with (Opus recommended) | No | `plan.md`, `log.md`, gate entries |
| Input reviewer | Judges the brief and references, writes the interview questions | Opus | No | `input-review.md`, `questions.yaml` |
| Researchers | Real-world reference; how professionals build this kind of scene; fixes for problems that keep failing; retro input | Sonnet | No | `research.md`, `metrics.yaml`, `workflow-notes.md`, `pro-tips.md` |
| Toolbox scanner | Finds tools, researches only new or changed ones, writes an instruction file per tool | Sonnet | No (read-only) | `toolbox/`, `plan/toolbox.md` |
| Generator | Submits every generation job in a batch at once (Tripo Studio in the browser, or Magnific), downloads results, logs credits | Sonnet | No | `source/` meshes, spec `generated` blocks |
| Modeler (up to 4 at once) | Kit pieces, props, hero assets, generated mesh repair, headless on one asset file each. Also fix lanes: tested patches on copies of the gate (`lane-integration`) | **Opus** | Own asset files only | Meshes, `kit/*.md`, `parts/<lane>/patches.py` |
| Asset Tech (1 or 2) | Collision, LODs where Nanite can't be used, UV and texel checks, FBX export, re-import check | Sonnet | Own asset files only | FBX, `assets/<id>/` checks |
| Unreal worker | Blockout, assembly, PCG, placement, lighting passes, captures, stats on the Unreal routes. Short jobs, a fresh worker per batch of steps | **Opus** | Yes, Unreal | Level, `stats.json` |
| Blender worker | Blockout, placement and transfer on Blender then Unreal; everything including lighting on the CG route. Short jobs, a fresh worker per batch of steps | **Opus** | Yes, Blender | `.blend`, `stats.json`, `transfer/` |
| Pipeline clerk | Scripted round work: before/after pairs and gate posts, from a fix list and gate pack the manager wrote. Judges nothing | Sonnet | No | `reviews/<gate>-r<n>/pairs/`, gate entries |
| Supervisor | Correctness: scale, overlaps, specs, budgets, value ranges. Runs `scene-lint` first | Opus | No | `review.md`, fix list |
| Art Director | Look and believability against real references | Opus | No | `ad-notes.md` |

The reviewers, researchers and input reviewer have the Unreal and Blender MCP servers removed (`disallowedTools: mcp__unreal-mcp, mcp__unreal-mcp-proxy, mcp__blender`), so they can't change the scene even by mistake. The Modelers, the Asset Tech and the Generator lose Unreal and every Blender tool that touches the open session; they keep the Blender API and manual search. The server names come from the repo's `.mcp.json`, so nothing needs renaming on your side.

## Interview: why the manager runs it

Claude Code subagents can't ask you questions (AskUserQuestion is removed from every subagent). So the input reviewer writes the questions, and the manager asks them in multiple-choice rounds of up to four, each with a default. One round is fixed (process and starting point), and after the answers the manager reads the job back in chat before it writes the plan. Without the multiple-choice tool the same questions go in chat as a numbered list; when the session runs unattended, they go on the G0 board entry instead.

## Modeler

New in v4. Runs the `modeling` skill, which starts by choosing a method per asset:

| Situation | Method |
| --- | --- |
| CG close-up, products, hero props | SubD with quads and holding loops, no Boolean |
| Game hero or mid-distance prop | Mid-poly: bevels with weighted or custom normals, or low poly with a high-poly bake for sculpted detail |
| Game kit piece | Grid, trim sheet, custom normals, Nanite or LODs |
| Far or background | Ultra low poly, hard edges, cards |
| CG background, set extension | Fast CG: simple geometry with photo projection, built only for the camera (the Ian Hubert way) |
| Tripo or Magnific output | Repair, then retopologise or rebuild by camera tier |

When a spec has reference views, it loads `blender-image-to-3d` then, not at start-up. It writes the chosen method into the asset spec, classifies the shape (axial, symmetric, asymmetric or multi-volume, each with its own construction method), builds at real scale, runs the validation script, and logs one lesson per review in `feedback/modeling.md`.

## Asset Tech, Generator and pipeline clerk

New in v5 (the clerk came later), for the repetitive half of the work that studios give to technical artists and outsourcing:

- **Asset Tech** finishes each mesh after the Modeler: collision (`collision-proxy`), LODs only where Nanite can't be used (`lod-pipeline`), UV, texel density and naming checks, FBX export, then `validate.py` and `roundtrip.py` from `blender-image-to-3d`. It sends shape problems back to the Modeler instead of fixing form itself.
- **Pipeline clerk** runs `review-pairs` and `gate-board` posts, the scripted part of every round. On one round these took 51 active minutes and 640,000 output tokens on the default model. The manager still merges the fix list and `review.md`, and reads the user's decisions.
- **Generator** runs generation for `source: generate` specs: inputs, credit check, every job submitted at once, downloads to `<work_dir>/assets/<id>/source/`, and the `generated` block in the spec. Tripo stand-ins and Magnific go through `generated-asset`.

All three run on Sonnet because their work is scripted and checked by numbers. That's a deliberate exception to Opus for scene work; change `model:` in their agent files if you'd rather have Opus.

## Toolbox scanner

New behaviour in v4:

1. A script lists Unreal plugins (project, Fab and Marketplace, and pipeline-relevant engine plugins), Blender add-ons and extensions, asset libraries, MCP servers and CLIs, each with a signature.
2. It diffs against `toolbox/manifest.<machine>.json`. Only new, changed or undocumented tools are researched: local docs first, then the official docs online.
3. Each tool gets `toolbox/tools/<tool-id>.md`: what it does, which stage uses it, how to call it, settings, gotchas, and version notes.
4. The project gets `plan/toolbox.md`, a shortlist by stage, plus tools worth installing (your decision).

## Researchers

Four kinds of topic:

| Topic | When | Output |
| --- | --- | --- |
| Reference | Stage 1 | `research.md`, `metrics.yaml` with a source or an assumption flag per number |
| Workflow | Stage 1 | `workflow-notes.md`: how professionals build this kind of scene on this route, each finding rated by fit and effort and marked adopt now, test first or later |
| Problem | When a step fails review twice for the same reason, or a worker is blocked | `pro-tips.md`: one to three fixes with sources, one recommended |
| Retro | Stage 9, run from `retro` | Research into the slowest steps for `improvements.md` |

At the end of every project, `retro` sends you up to 10 ranked suggestions for the next phase or project, each with the evidence, the expected gain and effort, and the skill it would change. Nothing changes a skill until you approve it.

## Supervisor

Looks, measures and reports. No scene tools.

- **Capture set:** the review cameras from `cameras.json`, a top view, and a close-up of what changed. Single objects: front, side, back, top, and a three-quarter view next to a 1.8 m mannequin. One contact sheet at about 1600 px, shared with the Art Director and uploaded to the board.
- **Lint first:** `scene-lint` writes `lint.json` (blocker, major, minor) and the capture set is refused on a blocker, so reviews spend their time on judgement.
- **Numbers:** `stats.json` from the adapter's stats script: actors, unique meshes, triangles, material instances by group, lights by type and shadow casting, and on game routes the frame time the user measured at L3 (`unreal-adapter`).
- **Output:** `review.md` with pass or fix and issues ranked blocker, major or minor, each tied to object IDs. Several supervisors review at once, one aspect each; the aspect list, the round rules and the merge format live in `supervisor`. After `max_rounds` without a pass it stops and asks you.

| Pass | Checks (starting thresholds) |
| --- | --- |
| L1 Gray (`full_cg`; the fast path in `supervisor` checks less) | Every base colour 0.216, no stray textures. Key to fill within half a stop. No large clipped areas. No light leaks. Light budget |
| L2 Value | 8 to 10 lighting groups. Non-metals inside sRGB 60 to 240, or a floor exception listed in the L0 brief. Every material instance in a group. Squint test keeps the focal area |
| L3 Hue | Each colour within 5 sRGB levels of its value. Large surfaces low in saturation. Light temperatures match the brief. On game routes, the frame time the user measured |

## Art Director

Asks "does it look like the real thing, and does it carry the mood?". Reads the same contact sheet as the supervisor and never edits the scene. At most five ranked notes per gate, each with 1 to 3 reference images. You pick Do it, Later or Skip per note; skipped notes are never suggested again.

| | Supervisor | Art Director |
| --- | --- | --- |
| Looks at | Contact sheet, specs, metrics, stats | Same contact sheet, mood references, palette |
| Finds | Wrong scale, overlaps, spec and budget breaks, values out of range | Missing real-world detail, wear to note for texturing (never built), weak composition, look and mood |
| Blocks a gate | Yes, blockers | No |

## One fix list per round

The manager merges the supervisor's issues, the Art Director notes you marked Do it, and your own notes into one numbered list for the worker, removing duplicates. If two notes conflict, it asks you. Studios do the same: one owner merges feedback, so the artist isn't working from three lists.

## Models and effort

Set per agent in `.claude/agents/*.md` (`house-rules` 13).

| Agents | Model | Effort |
| --- | --- | --- |
| Unreal worker, Blender worker, Modeler, supervisor, Art Director, input reviewer | Opus | High for the two workers, the agent default for the rest |
| Asset Tech, pipeline clerk, Generator | Sonnet | Medium, medium, low |
| Researcher, toolbox scanner | Sonnet | Medium, low |

Check that `CLAUDE_CODE_EFFORT_LEVEL` isn't set on your PC: it silently overrides every agent's `effort`.

## Skills

All in `.claude/skills/`. Credits for adapted skills: `.claude/skills/CREDITS.md`.

| Stage | Skills |
| --- | --- |
| Manager | `house-rules`, `scene-pipeline` (with `docs/pipeline/routes.md`), `gate-board` (the clerk posts, the manager reads decisions), `checkpoint` |
| 0 | `scene-intake`, `input-review`, `scene-interview` |
| 1 | `reference-research`, `workflow-research`, `detail-inventory`, `toolbox-scan` |
| 2 | `layout-2d`, `lighting-brief`, `level-design` (walkable game scenes) |
| 3 | `blockout`, `lane-integration`, `scene-lint` |
| 4 | `modular-kit`, `modeling`, `blender-image-to-3d`, `generated-asset`, `collision-proxy`, `lod-pipeline`, `environment-artist` |
| 5 | `placement-phases`, `set-dressing`, `geometry-nodes` (Blender routes), `scene-lint` |
| 6–8 | `lighting-passes` |
| Reviews | `scene-lint`, `supervisor`, `art-director`, `review-pairs` (the clerk runs it) |
| 9 | `texturing-handoff`, `retro` |
| Adapters | `unreal-adapter`, `blender-adapter` (tool names, conventions, captures, stats, validation, palette, transfer), `ue5-mcp` (Unreal gotchas; the Unreal worker reads the digest in `unreal-adapter` and loads `ue5-mcp` only when it needs more), plus Epic's `unreal-mcp` plugin skill |
