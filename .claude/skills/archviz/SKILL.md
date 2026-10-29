---
name: archviz
description: "Architectural visualization camera and lighting guidance in Blender: real-world scale checks, interior and exterior lenses, vertical correction, HDRI and practical lights. In the scene pipeline the Blender worker uses it on the Blender-only CG route for cameras and the lighting passes."
license: MIT
---

# Archviz

## Pipeline notes

Modified for the 3Dstack pipeline: the description is narrowed, the metadata block is removed and this section is added. The rest is the upstream text. Upstream source and commit: `.claude/skills/CREDITS.md`. Where these notes and the upstream text differ, these notes win.

- Applies to route `blender` only.
- The pipeline's lighting passes still apply: gray, value and hue, then stop. Compositing and final grading are yours.
- Lenses and camera positions come from `light/cameras.json`, approved at G2. Never move a review camera to fix a shot.
- The links to `camera-cinematography`, `rendering` and `compositing` point at upstream skills that aren't installed here.

Real-world scale architecture. Clean cameras. Believable materials. Delivery stills.

## When to Use

- Interior/exterior architectural presentations
- Real-estate style stills and simple walkthroughs
- Material/lighting lookdev for spaces

## Workflow

```
CAD/scale check → Greybox → Final modeling → Materials
  → Cameras → Lighting (HDRI + practicals) → Render → Comp
```

## Scale & Modeling

- Millimeter–meter accuracy where specs exist
- Straight verticals; controlled bevels on visible edges
- Separate glass, frames, furniture collections

## Cameras

- Verticals corrected (shift) for exteriors when needed
- 24–35mm interiors common; avoid extreme wide unless intentional
- Use `camera-cinematography`

## Lighting

- HDRI for exteriors / window light
- Practical lamps as mesh lights
- Soft GI; avoid game-style single harsh key unless styled

## Delivery

- High-res stills; optional depth/mist for comp
- `compositing` for exposure polish
- Keep layered EXR for revisions

## Constraints

### MUST DO
- Verify real-world scale early
- Lock cameras before heavy grade
- Keep glass/IOR plausible

### MUST NOT DO
- Game lowpoly shortcuts on hero archviz plates
- Over-saturate materials

## Reference Guide

| Topic | Reference | Load When |
|-------|-----------|----------|
| Archviz Camera | `references/archviz-camera.md` | When needed |
| Archviz Lighting | `references/archviz-lighting.md` | When needed |
