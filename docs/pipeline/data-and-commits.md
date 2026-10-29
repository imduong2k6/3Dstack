# Files, data and commits

## Project folder

Text files are the source of truth and are committed. The form and the board hold copies that the manager syncs.

```text
projects/<slug>/
  brief.yaml                  # from chat, interview and form; each value records where it came from
  refs/index.yaml             # role tags, AI flag, source link and work-folder path per image
  plan/  plan.md  interview.md  questions.yaml  input-review.md
         research.md  metrics.yaml  workflow-notes.md  pro-tips.md  toolbox.md
         lighting-brief.md  layout.json  layout.png  assets.yaml  phases.md  budget.yaml
  kit/<asset>.md              # one spec per asset, with method, batch and done_when
  assets/<asset_id>/          # review sheets, validate.json, roundtrip.json per asset (v5)
  light/ lights.json  palette.json  cameras.json
  transfer/layout.json        # Blender then Unreal route only
  reviews/<gate>-r<n>/        # G2-r1, P3-r2, T-r1, L2-r1 ...
         contact.png  stats.json  review.md  ad-notes.md  feedback.json
  handoff/texturing-brief.md  handoff/improvements.md
  backlog.md  routing.yaml  log.md
```

Outside git, in `work_dir` (recorded in `log.md`; default `PipelineWork/<slug>` next to the Unreal project):

```text
<work_dir>/refs/                     # reference photos from chat, form and your folders
<work_dir>/assets/<asset_id>/        # <asset_id>.blend, build/, exports/, source/ (generated meshes)
<work_dir>/<slug>.blend              # Blender scene file on the Blender routes
```

The repo is public, so reference photos and engine files stay in `work_dir`. `.gitignore` blocks images under `projects/*/refs/` and `.blend`, `.fbx`, `.uasset` and `.umap` files everywhere.

Shared across projects, at the repo root:

```text
toolbox/manifest.<machine>.json   # tools found per machine, with signatures
toolbox/tools/<tool-id>.md        # instruction file per tool
feedback/<skill>.md               # lessons per skill; ideas.md, projects.md, CHANGELOG.md
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

Gate order on the board: G0, G1, G2, P0 to P9, T (Blender then Unreal route only), L1, L2, L3, G3. G0 carries the plan and G3 the improvement suggestions as free `sections`.

1. The manager writes `reviews/<gate>-r<n>/` locally, uploads the contact sheet and captures as assets of the board artifact, and writes the gate entry with their URLs.
2. You answer questions, mark Art Director notes, and send approve, approve with notes, or request changes. Notes are required unless you approve.
3. When you tell the session to continue (or a `/loop 10m` check runs), the manager reads `feedback/<id>`, sets `pickedUp: true`, saves it as `feedback.json`, and moves on or starts the next round.

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

## Auto-commit and push

On by default (`auto_commit` in the form).

- **Save points:** end of each phase, each lighting pass, and each decision you send.
- **Branch:** one per project, `scene/<slug>`. Approved gates get a tag such as `hotel-corridor/G2`.
- **Message:** `[hotel-corridor] L2 r1 changes_requested: value pass`.
- **Push** after every commit. Never force-push. A failed push stays local and shows on the board.
- **What goes here:** skills, docs, `toolbox/`, `feedback/`, and the project folder, with captures as compressed PNG or JPEG. Raw toolbox scans stay local.
- **Engine files:** Unreal and Blender files are large binaries. Keep the Unreal project in its own repo with Git LFS and file locking, or under Perforce or Diversion, and record its commit or changelist in `log.md`. If binaries do go in this repo, add LFS rules first:

```gitattributes
*.uasset filter=lfs diff=lfs merge=lfs -text lockable
*.umap   filter=lfs diff=lfs merge=lfs -text lockable
*.blend  filter=lfs diff=lfs merge=lfs -text lockable
*.fbx    filter=lfs diff=lfs merge=lfs -text lockable
*.exr    filter=lfs diff=lfs merge=lfs -text lockable
```

GitHub limits LFS storage and bandwidth per account, so check the quota before the first large push.
