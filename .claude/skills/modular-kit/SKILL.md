---
name: modular-kit
description: Plan and spec the scene's modular kit (grid, piece list, pivots, ports, trim sheets, material groups, collision and LODs) and write one asset spec per piece for the Modeler. Use it in Stage 4, after the blockout is approved.
---

# Modular kit

The kit plan comes first; the Modeler builds pieces from the specs with the `modeling` skill.

## Plan the kit

1. **Count the repeats** in the blockout. Pieces that repeat become kit pieces; one-offs become props. Read `brief.yaml › fidelity` first. With `faithful`, the list follows the references: hero pieces and every variant they show (each fitting, each door type), not the fewest pieces that cover the blockout (`house-rules` rule 6). A minimal kit is for `inspired` only.
2. **Source the scale-setters.** A piece that sets a family's scale (the conduit diameter, the door leaf, anything repeated 10 or more times) needs a sourced row in `plan/metrics.yaml` and a `dims_source` in its spec before any Modeler starts. An AI image or a generated mesh never sets a size (`house-rules` rule 11).
3. **Grid:** pick it from the blockout (for example 0.5 m snapping, with 1, 2 and 4 m wall widths). Pivots go on a grid corner.
4. **Trim sheet first.** Design one trim sheet (mouldings, frames, skirting, panel edges) and the tiling materials before modelling, so pieces are UV'd once. Assign each surface a `material_group` from the palette groups.
5. **Piece list:** straight, corner, T-junction, end, door, window, transitions, and floor and ceiling tiles. Recesses for doors and windows are part of the wall piece. Wear: see `house-rules` rule 1. Add a broken variant only when the user asks for one.
6. **Collision and LOD plan** per piece type (see `modeling/references/game-models.md`).
7. **Batches for the asset lane.** In `plan/assets.yaml`, give each asset a `batch` (pilot, kit, props, generated, hero) so the manager can split the work across Modelers by type. Hero assets get a Modeler to themselves.

For piece roles and counts, grid starting points and storytelling details, read the `environment-artist` skill (its pipeline notes say what to ignore).

## Asset spec (`kit/<asset>.md`)

One format for every piece. Check it before the spec goes to a Modeler (it exits 1 on any error; `--migrate` renames the old `id`, `source: build` and `material` keys in place and leaves `ends_local` for a person):

```
python .claude/skills/modular-kit/scripts/check_spec.py projects/<slug>/kit/*.md [--metrics projects/<slug>/plan/metrics.yaml] [--services projects/<slug>/plan/services.yaml] [--json] [--out report.json]
```

`collision: none` needs its reason in a comment after it or in `collision_reason`.

```yaml
---
asset: SM_Office_Wall_Door_A   # same as the file name and the object name
type: kit                      # kit | prop | hero
kit: Office                    # null for a prop
phase: 2                       # first placement phase it appears in
source: model                  # model | library | generate | unreal_modeling
priority: 2                    # 1 is built first
count_in_scene: 12             # a number, or a range and how it is set
photos: [C05]                  # the reference crops it is read from
dims_m: [4.00, 0.15, 3.00]     # W (X), D (Y, off the wall), H (Z)
dims_source: metrics.wall_module   # required: the plan/metrics.yaml row or a measured crop
mount: floor                   # floor | wall | hang | inset
pivot: bottom-center
snap_grid_m: 0.5               # kit pieces
ports:                         # kit pieces: every joint, in the piece's local frame
  - {name: end_a, pos_m: [-2, 0, 1.5], dir: [-1, 0, 0], kind: wall_4m, size_m: [0.15, 3.0]}
  - {name: end_b, pos_m: [2, 0, 1.5], dir: [1, 0, 0], kind: wall_4m, size_m: [0.15, 3.0]}
sockets:                       # where other things attach; kind: wire for a cable anchor
  - {name: hinge_L, pos_m: [-0.45, 0, 0]}
clearance_m:
  door_swing: {radius: 0.9, side: +y}
material_group: [upper_wall, trim, door_frames]
texture_set: TS_Office_Walls
texel_density_px_m: 512
camera_tier: mid               # hero | mid | far
budget_tris: 800
collision: UCX_SM_Office_Wall_Door_A_01   # or none, with the reason
service_id: null               # the id in plan/services.yaml, for electrical, cable and pipe parts
landmarks: kit/SM_Office_Wall_Door_A.landmarks.json   # camera_match and full_cg: read by fit_check.py
generated: null                # source generate: the block in generated-asset
done_when:                     # measurable acceptance, like an outsourcing brief
  - every landmark in landmarks.json within 5 px at CAM_A, 600 x 800
  - snaps to the 0.5 m grid with no gaps against SM_Office_Wall_Plain_A
  - door leaf opening 0.90 x 2.04 m within 1 cm
  - one material slot per material_group, texel density 512 px/m within 10%
# the Modeler fills in the rest
method: null                   # see modeling
why: null
expected_tris: null
classification: null
file: null                     # <work_dir>/assets/<asset>/<asset>.blend
validation: null               # the validate_mesh.py result
---
The photo crop first, with its landmarks labelled, then notes, reference images and what makes this piece specific.
```

**Ports.** `pos_m` is the centre of the open end, `dir` the outward unit normal, `kind` the family it may join (two ports mate only when the kinds are equal), `size_m` the section (`[d]` for round, `[w, h]` for rectangular). Two ports mate when their positions meet within 1 mm, their directions oppose and their sections match within 1 mm. `scripts/kit_joint_test.py` joins the built pieces at their ports and fails on any other result; the supervisor reads its output:

```
bash bin/blender-bg [scene.blend] --python .claude/skills/modular-kit/scripts/kit_joint_test.py -- --specs projects/<slug>/kit/*.md [--assets-dir <work_dir>/assets] [--kinds wall_4m] [--tol-mm 1] [--out joints.json]
```

It reads each mesh from the open file, from `<assets-dir>/<asset>/<asset>.blend` or from the spec's `file`, and writes nothing to them.

**`camera_match` and `full_cg`: the crop comes before research.** Write each spec from the photo crop of that piece, with its landmarks (corners, lid edges, the cell it sits in) labelled and measured in pixels at the review camera. Research text fills only what the crop can't show, such as depth behind a face. On the corridor pilot, 7 spec items written from research text were overridden at K. The landmarks go in `landmarks.json` (format in `blender-adapter/scripts/fit_check.py`); the worker runs `fit_check()` before posting and the supervisor reads its output instead of re-measuring.

## Pilot first

Before the batch, one Modeler builds one representative kit piece and one prop, and the Asset Tech finishes them. The supervisor and the Art Director review them, and you approve them at gate K. Post K only once both reviews are in, with their merged fix list, so that approving K accepts that list. Lessons go into the specs before the batch starts, the same way studios start an outsourcing partner with a paid test asset. Only then does the manager run several Modelers at once (see `docs/pipeline/parallel.md`).

## Exit

The supervisor passes each piece against its spec: size within 1 cm, pivot, naming, grid snap, material groups and ports (`kit_joint_test.py`). Finished pieces go to the level lane in batches and replace their proxies.

## Kit library (user edits)

All kit pieces and the scene's instance families live in one editable file, `<work_dir>/assets/<Project>_Kit.blend`, with `<library>.blend.manifest.json` beside it. `scripts/kit_library.py` builds it and syncs edits back; `scripts/selftest_kit_library.py` tests both (headless, no project files).

- **Build** (manager, headless; reads the scene, never saves it): `bash bin/blender-bg --python .claude/skills/modular-kit/scripts/kit_library.py -- build --scene <gate copy> --assets-dir <work_dir>/assets --out <library.blend> [--families-min 2] [--specs-dir projects/<slug>/kit]`. One collection per piece, laid out in rows with a text label; masters and variants are assets in the asset browser (tags: spec id, role). Sources: every `<assets-dir>/<asset>/<asset>.blend`, and every mesh datablock the scene shares across `--families-min` or more rendered objects (cable and pipe runs, wear names, one-offs and parked objects are skipped). The manifest holds each piece's source, the scene mesh names it maps to, object counts, and a geometry hash per mesh. A piece that is not in the scene yet says so there and maps to nothing until it is placed. Re-running is safe: existing pieces keep their edits and their baseline hashes, new pieces are appended.
- **User edits**: the user opens the library in a **second** Blender instance, never by switching files in the live Blender (the worker drives it, `house-rules` rule 2). They edit the master meshes in place, **without renaming them and without moving their origin** unless they mean every instance to move, save, and tell the manager. Edit mesh, UVs, shading and material slots; a material the scene lacks is appended by name. Object-level transforms in the library are ignored by the sync.
- **Sync** (live worker, after `step_log.py diff`): load it (`import importlib.util as u; sp = u.spec_from_file_location('kl', r'<repo>/.claude/skills/modular-kit/scripts/kit_library.py'); kl = u.module_from_spec(sp); sp.loader.exec_module(kl)`) and call `kl.sync(library, manifest)` on the open scene, which is a dry run and saves nothing. Show the manager its report (per piece: objects swapped, bbox and origin change with a warning above 1 mm, tris before and after, new materials, objects it could not swap). On the OK, call `kl.sync(library, manifest, apply=True, report=<json>)`, save, save the step backup and log the step (`house-rules` rule 4). Apply swaps each changed piece's mesh into every object that uses the mapped mesh datablock: transform, name, custom properties and modifiers stay, slots point at the scene's own materials (`lane-integration`: the scene keeps its materials), the datablock keeps its name, and the manifest hashes are updated, so a second sync does nothing. Headless on a copy: `bash bin/blender-bg <copy.blend> --python .../kit_library.py -- sync --library <library.blend> --manifest <json> [--apply] [--report <json>] [--save-as <next.blend>]`.
- Then run `scene-lint` and capture as after any change; the sync does not move objects, but a bigger or smaller piece can cross a neighbour.
