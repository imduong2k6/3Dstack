---
name: generated-asset
description: Generate a 3D prop or image for an asset spec with source generate, on one of two paths - a Tripo stand-in (the Generator drives Studio, a script cleans it, through the tripo-props skill) or a Magnific or hero mesh (the Modeler repairs it) - only when brief.yaml's detail is detailed or final. Use it when assets.yaml marks an asset for generation.
---

# Generated assets

## Two paths

| | Tripo stand-in | Magnific or hero |
| --- | --- | --- |
| For | Placeholder props below hero tier, when `tripo` is in `generation_services` | Hero tier, Magnific-only runs, or when Tripo credits ran out |
| Generator (Sonnet) | Prepares the input, drives Studio in the browser, exports (GLB download or Send to Blender), logs the spec additions | Prepares the input, submits every job in the batch at once, downloads to `<work_dir>/assets/<asset_id>/source/`, logs the spec additions |
| Clean-up | `tripo_cleanup.py` fits it to the spec (`tripo-props`). The live worker only imports and runs it; it never drives Studio | The Modeler repairs it on its own asset file (`modeling`, `modeling/references/mesh-repair.md`) |

**When:** only when `brief.yaml › detail` is `detailed` or `final` (defined in `scene-pipeline`'s mode table). With `massing`, the props are simple shapes the Modeler builds. G0 asks the credit budget per service and the pre-approvals (browser with Tripo signed in, GLB downloads into the work folder, headless Blender) once, before any spend (`house-rules` rule 11). Don't ask again per batch.

**Services:** `generation_services` in `brief.yaml` sets the order (`gen_tripo` and `gen_magnific_3d` switch each on; Tripo first when both are on). Tripo runs through the `tripo-props` skill.

## Before generating

1. Check the spec has `source: generate`, a camera tier, at least one `form` reference or a clear text description, and a `dims_source`. The size comes from `dims_source` (a sourced `metrics.yaml` row or a measured crop). A generated image or mesh never sets it (`house-rules` rule 11).
2. **Credits.** Check the balance of the first service in `generation_services` (Magnific: `account_balance`; Tripo: the number Studio shows). Price the whole batch before the first job: on Magnific, `simulate_cost` with each job's tool and arguments (read-only, never charges); Tripo has no quote, so use the credits Studio shows per job. If the spend so far plus the quote is over the balance, move to the next service and log the switch in `log.md`. Ask the user before going over the plan's credit budget. The quote only checks the budget: never pick a model, a polycount or a variant count because it is cheaper (`house-rules` 6).
3. **Rubric.** Before the first job, write `generated.rubric` in the spec: three to six pass or fail lines the result must meet, taken from the spec and its references. Cover part counts and how parts attach, part-to-whole proportions, and each item the reference shows.
4. **Input image.** Prefer a clean product photo or a Magnific-generated front view on a plain background. Use Magnific `images_remove_background` if needed. Mark every generated image as AI in the spec.
5. **Licence.** Tripo free-plan output is reported as non-commercial; check the plan before using it in paid work.

## Generate

- Tripo stand-in: follow `tripo-props` (input image, settings, polycount by complexity, export at 1k, stall budget). Record the model version, the input and the credits used.
- Magnific: `models3d_generate` with the same input; `models3d_models_list` shows what's available.
- Generate two or three variants for hero tiers only, and pick by silhouette against the reference.

## Judge and regenerate

This applies to input images, turnarounds and meshes, before anything goes on to the next step.

1. **Judge against the rubric, one line at a time,** with the reference open beside the result. A generator's look is convincing, and a quick look misses wrong counts, parts that don't attach and proportions that drift. Judge the whole unit you would reject: a turnaround is one unit, not its best view.
2. **Change one thing per round.** Start from the last good image, say what stays and what changes, and state each reference's role (shape, material, scale). Start over only when no baseline is worth keeping.
3. **A line that fails twice under different fixes means the approach is wrong.** Change the references, the view or the crop. Concept images stay on Flux.2 with the user's references (`house-rules` 11): changing the model is the user's decision, so ask.
4. **Three rounds per asset.** If a line still fails, stop and show the user the best result and the failing lines. Don't pass it on as good enough, and don't lower the rubric to pass it.

Record `rounds` and each failing line in the `generated` block.

## Clean up

- **Tripo stand-in:** the script does it. No Modeler build.
- **Magnific or hero:** hand the mesh to the Modeler with `modeling/references/mesh-repair.md`: keep the source, scale uniformly to the spec, pivot, clean, strip baked light, then remesh, retopologise or rebuild by tier. Magnific `models3d_remesh`, `models3d_uv_unwrap` and `models3d_segment` can do part of it.

## Spec additions

```yaml
dims_source: metrics.conduit_od   # required; never the AI input
generated:
  service: tripo            # tripo | magnific
  model: "<model version>"
  input: refs/form/chair_front.jpg
  route: bridge             # bridge | glb
  credits: 40
  variants_tried: 2
  rubric:
    - four legs, each joined to the seat at a corner
    - seat height about 45 % of the overall height
  rounds: 2
  failing: []               # rubric lines still failing when it stopped
```

The supervisor checks generated assets like any other. A raw generated mesh never goes in a hero position.
