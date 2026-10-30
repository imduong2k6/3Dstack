# Stages

Each stage has fixed inputs and outputs, so the manager only routes between them and any stage can be re-run on its own. Paths are relative to `projects/<slug>/`. Which worker runs a stage depends on the route; see [routes.md](routes.md).

The mode and tier in `brief.yaml` decide which checks run, how often the supervisor and the Art Director review, and which gates wait for the user: see `.claude/skills/scene-pipeline/SKILL.md › Mode and tier`. With a tier below L, a stage's "gate" below may be a review attached to the next user gate.

## Stage 0: Intake, interview and plan (gate G0)

Agents: the manager runs the intake and the interview (only the main session can ask you questions); the input reviewer (Opus) judges the references.

- **Inputs:** your chat prompt and any images in it, reference folders or a PureRef board, plans, notes. The Scene Brief form only when the intake finds three or more required gaps, or when you prefer it.
- **Work:**
  - `scene-intake` turns the prompt into a draft `brief.yaml`, recording where each value came from (chat, form, image, default).
  - `input-review` tags every image by role (`measure`, `form`, `material`, `mood`, `composition`, `placement`), builds a coverage matrix, checks scale anchors, conflicts and AI images, rates readiness per area, and writes `plan/questions.yaml`.
  - `scene-interview` asks you multiple-choice rounds of up to four questions, each with a default: goal and deliverables, then the blocking questions, then look and lighting, then follow-ups. Usually 2 to 4 rounds. It doesn't ask what the references already answer.
  - The answers and the brief become `plan/plan.md`: goal, deliverables and route, scope, references, assumptions, stages and gates, budgets, Stage 1 research topics, risks and open questions.
- **Outputs:** `brief.yaml`, `refs/index.yaml`, `plan/input-review.md`, `plan/questions.yaml`, `plan/interview.md`, `plan/plan.md`, board entry G0 with the plan.
- **Exit:** you approve the plan at G0. Nothing else starts before that.

## Stage 1: Research and toolbox scan

Agents: researchers (Sonnet) in parallel, toolbox scanner (Sonnet).

- **Inputs:** approved `plan.md`, `brief.yaml`, `refs/index.yaml`.
- **Work:**
  - Reference research: place, era and construction, real dimensions of every object type, fixtures and colour temperatures, time of day and weather.
  - Workflow research: how professionals build this kind of scene on this route, such as breakdowns, kit and trim strategies, PCG or geometry nodes setups, lighting setups, and tools. Each finding is rated by fit and effort, mapped to a stage and skill, and marked adopt now, test first or later.
  - Toolbox scan: only new or changed tools are researched. Each gets an instruction file in `toolbox/tools/`, and the project gets a shortlist.
- **Outputs:** `plan/research.md`, `plan/metrics.yaml` (every number sourced or flagged as an assumption), `plan/workflow-notes.md`, `plan/toolbox.md`, updated `toolbox/`.
- **Exit:** every metric the layout needs has a source or an assumption flag. The adopt-now workflow findings go to you at G1.

## Stage 2: Layout and lighting brief (gate G1)

Agent: the manager, with a researcher for layout drafts.

- **Inputs:** research, metrics, workflow notes, toolbox shortlist, lighting answers from the brief and the interview.
- **Work:**
  - Top-down map in the colour legend, each shape with an ID.
  - Player path, hero cameras, focal points.
  - Lighting brief (L0), see [lighting.md](lighting.md#l0-lighting-brief).
  - Asset list with `source: build | library | generate`, phase plan, budgets.
- **Outputs:** `plan/layout.json`, `plan/layout.png`, `plan/lighting-brief.md`, `light/lights.json`, `plan/assets.yaml`, `phases.md`, `budget.yaml`.
- **Exit:** you approve the map, the lighting plan and the adopt-now workflow findings together at G1. On the CG route the map is laid out camera first.

## Stage 3: Blockout and rough light (gate G2)

Agent: the route's worker on Opus (Unreal worker on `unreal`, Blender worker on `blender_unreal` and `blender`).

- **Inputs:** `layout.json`, metrics, kit grid, lighting brief.
- **Work:**
  - Kit-sized proxies at real scale on the grid.
  - Player checks: 1.8 m capsule, door and stair clearances.
  - Rough rig: key light, sky, fog, exposure locked to the brief.
  - Create the review camera set (`light/cameras.json`) that every later gate reuses.
- **Outputs:** blockout level, `cameras.json`, walkthrough capture, board entry G2 with stats.
- **Exit:** you approve scale, composition and light direction at G2, after the supervisor and Art Director review.

## Stage 4: Asset lane (gate K, then per asset)

Agents: Generator (Sonnet), Modelers (Opus, up to `parallel.modelers` at once after K), Asset Tech (Sonnet), on every route. Runs alongside Stage 5. See [parallel.md](parallel.md).

- **Inputs:** approved blockout, asset list and specs.
- **Work:**
  - Kit plan and trim sheet first. `plan/assets.yaml` gives every asset a source and a batch (pilot, kit, props, generated, hero).
  - The Generator submits every `source: generate` job at once (Magnific for now; your Tripo workflow later) and drops results in each asset's work folder.
  - **Pilots:** one kit piece and one prop, built by one Modeler and finished by the Asset Tech. The supervisor and the Art Director review them, and you approve them at **gate K**. Nothing is batched before K.
  - **Batch:** the manager splits the rest across up to `parallel.modelers` Modelers by type. Each works headless on its own `.blend` in `work_dir`, never in the open Blender. A hero asset gets a Modeler to itself.
  - The Modeler picks a method per asset from the camera distance and route (SubD quads, game mid-poly or bake, ultra low poly, or fast photo-projected CG) and uses the measured gates of `blender-image-to-3d`.
  - On the game routes the Asset Tech adds collision, LODs only where Nanite can't be used, checks UVs, texel density and names, exports FBX and re-imports it to prove it.
  - The supervisor reviews finished assets in groups of up to five.
- **Outputs:** `kit/<asset>.md` per piece, `assets/<asset_id>/` review sheets and check results, meshes and FBX files in `work_dir`.
- **Exit:** you approve the pilots at K; after that the supervisor passes each asset against its spec (size within 1 cm, pivot, naming, `done_when`). Finished assets go to the level lane in batches.

## Stage 5: Level lane, placement phases P0 to P9 (board entry per phase)

Agent: the route's worker on Opus, the only agent that writes to the live editor. Runs alongside Stage 4.

- From G2 the worker places P0 to P4 with the blockout's kit-sized proxies; P5 to P7 use proxies with the spec's bounding box and clearance zone. Finished assets from the asset lane are imported in batches between steps and swapped in.
- Placement gates judge position, clearance and story; the look is judged once final assets are in. The lighting passes start only when every asset in P0 to P7 is final.

| Phase | What goes in |
| --- | --- |
| P0 | Site and ground |
| P1 | Structure: floors, walls, columns, stairs, roof |
| P2 | Envelope and openings |
| P3 | Services: pipes, ducts, cable trays, conduits |
| P4 | Fixed fit-out: light fittings, cabinetry, signage, railings |
| P5 | Anchor props and the hero piece |
| P6 | Story clusters of 3 to 7 props |
| P7 | Small clutter, inside clusters |
| P8 | Wear and time: repairs. Grime, stains, drips, rust, cracks and chips are wear notes for the user's texturing, never meshes or decals |
| P9 | Life and nature: foliage, animated assets |

- Place only what the phase allows. Services follow the structure they hang from; fixtures only go where services reach; clutter only goes inside a cluster that explains it.
- PCG and splines for cables, pipes and railings in Unreal.
- One save, one review with the camera set, one board entry and one commit per phase.
- **Exit:** supervisor pass within 3 rounds (`max_rounds` in the form). You can approve several phases at once, for example P0 to P2.

## Stage T: Transfer (gate T, route `blender_unreal` only)

Agents: Blender worker exports, Unreal worker imports.

- **Work:** one FBX per unique mesh, `transfer/layout.json` with every placed instance, materials rebuilt in Unreal from `material_group`, then the same review cameras captured in both programs.
- **Exit:** the supervisor finds the same scale, positions and instance counts in both, with nothing missing. The first project also runs the arrow test for the axis conversion.

## Stages 6 to 8: Lighting passes L1, L2, L3

Gray, value and hue, each a gate with its own checks and captures, in Unreal on the game routes and in Blender Cycles on the CG route. See [lighting.md](lighting.md).

## Stage 9: Hand-off, retro and sign-off (gate G3)

Agents: manager, with a researcher for the retro.

- **Inputs:** approved hue palette, material instance map, Art Director notes marked Later.
- **Work:** texturing brief per material group, texture set list and texel density, final stats. Then the retro: rounds and time per stage, top repeat issues and credits used, combined with research into the slowest steps, as up to 10 ranked suggestions for the next phase or project. Tag the commit.
- **Outputs:** `handoff/texturing-brief.md`, `light/palette.json`, `handoff/improvements.md`, board entry G3.
- **Exit:** you sign off and the pipeline stops. Your textures plug into the same material instances with the pass switch set to Textured.
