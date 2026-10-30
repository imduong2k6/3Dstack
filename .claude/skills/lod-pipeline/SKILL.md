---
name: lod-pipeline
description: "Classic LOD chains for game meshes that can't use Nanite (skeletal, translucent or otherwise unsupported meshes): generation, naming, screen sizes and checks. In the scene pipeline the Asset Tech uses it on the Unreal routes after checking the Nanite rule in modeling/references/game-models.md."
license: MIT
---

# LOD Pipeline

## Pipeline notes

Modified for the 3Dstack pipeline: the description is narrowed, the metadata block is removed and this section is added. The rest is the upstream text. Upstream source and commit: `.claude/skills/CREDITS.md`. Where these notes and the upstream text differ, these notes win.

- **Nanite first.** On Unreal 5.8, opaque static meshes use Nanite and get no hand-made LODs. This skill applies only to meshes Nanite doesn't support.
- **Starting ratios:** LOD0 100%, then about 50%, 25% and 12.5%, as in `modeling/references/game-models.md`. LOD3 at 12.5% sits just above the 5 to 10% range below; go lower when the silhouette holds.
- **CG route (`blender`):** no LODs.

Intentional LOD chains. Preserve silhouette. Validate reductions.

## When to Use

- Game assets needing LOD0–N
- Batch LOD for modular kits
- Before Unity/Unreal/Godot export

## Workflow

```
Approve LOD0 → Generate LOD1..N → Fix silhouette breaks
  → Naming → Screen-size table → Export verify
```

## Typical Budgets (guide)

| LOD | Tris vs LOD0 | Keep |
|-----|--------------|------|
| LOD0 | 100% | Full detail |
| LOD1 | 40–60% | Major forms |
| LOD2 | 15–30% | Silhouette |
| LOD3 | 5–10% | Blob / impostor candidate |

Tune per asset importance and camera.

## Generation Methods

1. **Decimate (planar/collapse)** — fast props
2. **Manual retopo low** — hero characters/vehicles
3. **Delete interiors / small parts** — vehicles, buildings
4. **Bake normals from LOD0 → low** — when detail must move to texture

## Naming

```
SM_Asset_LOD0
SM_Asset_LOD1
SM_Asset_LOD2
```

Collection: `COL_LODs_[Asset]`

## Validation Checklist

- [ ] Silhouette matches at intended distance
- [ ] No major holes / inverted normals
- [ ] UVs still valid (or rebaked)
- [ ] Materials slots consistent across LODs
- [ ] Vertex colors/UVs needed by shader preserved
- [ ] LOD transitions planned (screen size %)

## Screen Size Starters

| LOD | Screen size (UE-like guide) |
|-----|-----------------------------|
| LOD0 | 1.0 – 0.5 |
| LOD1 | 0.5 – 0.25 |
| LOD2 | 0.25 – 0.1 |
| LOD3 | 0.1 – 0.0 |

## Constraints

### MUST DO
- Protect silhouette before poly reduction
- Keep LOD0 as source of truth
- Document budgets in production brief

### MUST NOT DO
- Blind decimate until unrecognizable
- Different material slot counts across LODs without reason

## Reference Guide

| Topic | Reference | Load When |
|-------|-----------|----------|
| Lod Budgets | `references/lod-budgets.md` | When needed |
| Lod Validation | `references/lod-validation.md` | When needed |
