---
name: generated-asset
description: Generate a 3D prop or image for an asset spec with source generate (Tripo through the tripo-props skill, or Magnific), only in full_cg or a detailed blockout, then hand it to the Modeler for clean-up to the spec. The Generator runs the jobs; the Modeler does the repair. Use it when assets.yaml marks an asset for generation.
---

# Generated assets

## Who does what

- **Generator** (Sonnet): checks, inputs, credits, submits every job in the batch at once, downloads results to `<work_dir>/assets/<asset_id>/source/`, logs the spec additions.
- **Modeler** (Opus): the clean-up below, on its own asset file.

**When:** only in `mode: full_cg`, or when the user asks for a detailed blockout. A blockout's props are simple shapes the Modeler builds. G0 asks the credit budget per service before any spend.

**Services:** `generation_services` in `brief.yaml` sets the order; `gen_tripo` and `gen_magnific_3d` switch each on, Tripo first when both are on. Tripo runs through the `tripo-props` skill (Tripo Studio in the browser, the DCC Bridge into Blender, then its clean-up and atlas scripts).

## Before generating

1. Check the spec has `source: generate`, a camera tier, and at least one `form` reference or a clear text description.
2. **Credits.** Check the balance of the first service in `generation.services` (Magnific: `account_balance`). If it's too low for the batch, move to the next service and log the switch in `log.md`. Ask the user before spending more than the plan's credit budget.
3. **Input image.** Prefer a clean product photo or a Magnific-generated front view on a plain background. Use Magnific `images_remove_background` if needed.
4. **Licence.** Tripo free-plan output is reported as non-commercial; check the plan before using it in paid work.

## Generate

- Tripo: follow `tripo-props` (input image, settings, polycount by complexity, export at 1k, Send to Blender). Record the model version, the input and the credits used.
- Magnific: `models3d_generate` with the same input; `models3d_models_list` shows what's available.
- Generate two or three variants for hero tiers only, and pick by silhouette against the reference.

## Clean up

Hand the mesh to the Modeler with `modeling/references/mesh-repair.md`: keep the source, scale to the spec's bounding box, pivot, clean, strip baked light, then remesh, retopologise or rebuild by tier. Magnific `models3d_remesh`, `models3d_uv_unwrap` and `models3d_segment` can do part of it.

## Spec additions

```yaml
generated:
  service: tripo            # tripo | magnific
  model: "<model version>"
  input: refs/form/chair_front.jpg
  credits: 40
  variants_tried: 2
```

The supervisor checks generated assets like any other. A raw generated mesh never goes in a hero position.
