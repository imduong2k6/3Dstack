# Files, data and commits

## Project folder

Text files are the source of truth. Projects stay local: nothing under `projects/` is ever committed or pushed (`house-rules` 3). The form and the board hold copies that the manager syncs.

```text
projects/<slug>/
  brief.yaml                  # from chat, interview and form; each value records where it came from
  refs/index.yaml             # PureRef group, role tags, AI flag, source link and work-folder path per image
  plan/  plan.md  interview.md  questions.yaml  input-review.md
         research.md  metrics.yaml  workflow-notes.md  pro-tips.md  toolbox.md
         inventory.yaml  services.yaml       # per zone and wall: what is visible; the connected services network
         lighting-brief.md  layout.json  layout.png  assets.yaml  phases.md  budget.yaml
         steps.json                          # step ledger: backup, counts and hashes per step (step_log.py)
         walk.json  visible_set.json  lint_rules.yaml  inventory-check.json   # scene-lint and detail-inventory files
  kit/<asset>.md              # one spec per asset, with method, batch and done_when
  assets/<asset_id>/          # review sheets, validate.json, roundtrip.json per asset
  light/ lights.json  palette.json  cameras.json  exposure.json
  transfer/layout.json        # Blender then Unreal route only
  reviews/<gate>-r<n>/        # G2-r1, P3-r2, T-r1, L2-r1 ...
         contact.png  stats.json  lint.json  inventory-count.json  review.md  ad-notes.md  feedback.json
         fix_issues.json  fix_cams.json  pairs/      # the before/after pairs (review-pairs)
  handoff/texturing-brief.md  handoff/wear-notes.md  handoff/improvements.md
  backlog.md  log.md          # log lines: YYYY-MM-DD HH:MM <who> <what>
```

In `work_dir` (recorded in `log.md`; default `PipelineWork/<slug>` next to the Unreal project), for the large files:

```text
<work_dir>/refs/                     # reference photos from chat, form and your folders
<work_dir>/assets/<asset_id>/        # <asset_id>.blend, build/, exports/, source/ (generated meshes)
<work_dir>/<slug>.blend              # Blender scene file on the Blender routes
<work_dir>/parts/<lane>/             # lane part .blend, manifest.json, report.json (lane-integration)
<work_dir>/<phase folder>/backups/   # a .blend copy after every step: <file>_<phase>_<nn>_<step>.blend, never deleted
```

`.gitignore` ignores `projects/` whole, and `.blend`, `.fbx`, `.uasset` and `.umap` files everywhere. Reference photos stay in `work_dir`; `refs/index.yaml` keeps each photo's source link.

### brief.yaml keys the pipeline adds

Each value records where it came from (chat, form, image, interview, board, default or assumed). Schema: [schemas/brief.schema.json](schemas/brief.schema.json).

| Key | Meaning |
| --- | --- |
| `detail` | `massing`, `detailed` or `final`, defined in `scene-pipeline` |
| `fidelity` | `faithful` (hero pieces and variants, not the fewest pieces) or `inspired` (free on pieces); the form's older `replica` counts as `faithful` |
| `standing_rules` | `{date, rule, from}` list; quoted into every lane brief and reviewer prompt |
| `lighting_focus` | `deferred` freezes colour, contrast and light until the user sends lighting references |
| `light_depth` | `direction`, `mood` or `measured` |
| `starting_point`, `gate_pacing`, `review_scope`, `concept_model`, `generation_preapproved`, `walk` | The answers from the interview's process round and the walkable-scene constraints |
| `board_url` | The Gate Review Board artifact; published before G0 if empty |

Shared across projects, at the repo root:

```text
toolbox/manifest.<machine>.json   # tools found per machine, with signatures
toolbox/tools/<tool-id>.md        # instruction file per tool
feedback/<skill>.md               # lessons per skill; ideas.md, projects.md, CHANGELOG.md (committed; project lessons only with your OK and private names removed)
```

## Scene Brief form

Optional. A chat prompt is enough to start; the manager sends the form only when three or more required fields are missing, or when you ask for it.

Stored in the form's database at `briefs/{id}` as `{ title, status: "draft" | "submitted", updatedAt, modes, fields, schema: 2 }`. Schema: [schemas/brief.schema.json](schemas/brief.schema.json).

- There is no project name or deadline. The title is the first line of your project or context text, and a deadline goes in the prompt if there is one. Duplicate copies a brief into a new draft for reuse in another project.
- Project, Context and Lighting each have two modes: quick options, or **describe with images**, where `<section>_prompt` holds your text and `<section>_images` holds up to 12 uploaded images as `{id, name}`. Images are stored as assets of the form artifact; the manager downloads them by id into `<work_dir>/refs/`.
- `route` is `unreal`, `blender_unreal` or `blender` (see [routes.md](routes.md)). Old schema 1 briefs map `destination` to `route`.

Copy YAML on the form gives the same data as text when the pipeline can't reach the page.

## Gate Review Board

| Collection | Document id | Written by | Schema |
| --- | --- | --- | --- |
| `gates` | `<slug>-<gate>-r<round>` | Manager (`gate-board` skill) | [gate.schema.json](schemas/gate.schema.json) |
| `feedback` | same as the gate | The board, when you send a decision | [feedback.schema.json](schemas/feedback.schema.json) |

The board is private and may show project captures. Its URL is `brief.yaml › board_url`; if empty, the manager publishes the board before posting G0. Gate order on the board: G0, G1, G2, K, P0 to P9, T (Blender then Unreal route only), L1, L2, L3, G3. G0 carries the plan and G3 the improvement suggestions as free `sections`; every gate carries sections for what is locked and since when and a "Please check" list of at most 8 items, and the before/after pairs as captures.

1. The manager writes `reviews/<gate>-r<n>/` locally, uploads the contact sheet and captures as assets of the board artifact, and writes the gate entry with their URLs.
2. You answer questions, mark Art Director notes, and send approve, approve with notes, or request changes. Notes are required unless you approve.
3. When you tell the session to continue (or a `/loop 10m` check runs), the manager reads `feedback/<id>`, sets `pickedUp: true`, saves it as `feedback.json` (a decision given in the thread gets the real time), and moves on or starts the next round. A gate passes only with a supervisor PASS plus your approval; "approved" on a FIX verdict runs the next round on the defaults. Later and Skip notes go to `backlog.md`, wear items to `handoff/wear-notes.md`.

This uses Claude Code's Artifact tools. Without them, gate packs go to `reviews/` as markdown and you reply in the session.

Examples: [examples/gate.L2.hotel-corridor.json](examples/gate.L2.hotel-corridor.json), [examples/feedback.G2.hotel-corridor.json](examples/feedback.G2.hotel-corridor.json).

## Palette

`light/palette.json` drives the pass switch in L2 and L3 and becomes the texturing brief. Schema: [schemas/palette.schema.json](schemas/palette.schema.json). Example: [examples/palette.hotel-corridor.json](examples/palette.hotel-corridor.json), where each hue was computed to match its group's value exactly.

## Asset spec fields added in v3 and v4

```yaml
material_group: [upper_wall, trim, door_frames]   # v3: palette groups used
texture_set: TS_Office_Walls                       # v3: shared trim sheet
texel_density_px_m: 512                            # v3
camera_tier: mid                                   # v4: hero | mid | far, drives the modelling method
method: game_midpoly                               # v4: filled in by the Modeler
done_when:                                         # v4: measurable acceptance criteria
  - door leaf opening 0.90 x 2.04 m within 1 cm
generated: {service: tripo, model: "...", input: refs/form/chair.jpg, credits: 40}   # v4, generated assets only
```

Full template: `.claude/skills/modular-kit/SKILL.md`.

## Save points and commits

Two kinds, never mixed (`checkpoint`).

- **Project save point:** end of each phase, each lighting pass and each decision you send. A `log.md` line, the step backup and a `plan/steps.json` entry. No git: projects, captures and engine files stay local.
- **Pipeline commit:** a changed skill, doc, `knowledge/` note, `feedback/` file or `toolbox/` file (raw scans stay local). Message `[pipeline] <what changed>`, on the working branch, pushed after every commit. Never force-push. A failed push stays local and is reported in chat.
- **Engine files:** Unreal and Blender files are large binaries and never go in this repo. Keep the Unreal project in its own repo with Git LFS and file locking, or under Perforce or Diversion, and record its commit or changelist in `log.md`.
