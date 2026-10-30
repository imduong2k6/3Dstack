---
name: collision-proxy
description: "Collision proxies for game assets in Blender: UCX naming, convex pieces, capsules and checks. In the scene pipeline the Asset Tech and the Modeler use it on the Unreal routes; it does not apply to the Blender-only CG route."
license: MIT
---

# Collision Proxy

## Pipeline notes

Modified for the 3Dstack pipeline: the description is narrowed, the metadata block is removed and this section is added (updated 30 Oct 2026). The rest is the upstream text. Upstream source and commit: `.claude/skills/CREDITS.md`. Where these notes and the upstream text differ, these notes win.

- **One name:** `UCX_SM_<Name>_NN` (`_01`, `_02` and so on), where `SM_<Name>` is the render mesh, as in `modeling/references/game-models.md`. No other collider names: no `UCX_<Name>` without the number, no `COL_` meshes.
- **Authoring rule 5 is replaced.** The collection is `COL_Collision` inside the asset's own `.blend` (one asset per file), not `COL_Collision_[Asset]`.
- Props the player can't reach get no collision. Use complex-as-simple only when the spec asks for it.
- The Unity notes don't apply here.

Simple, stable colliders. Prefer primitives and convex pieces over render mesh.

## When to Use

- Game physics / blocking volumes
- Unreal UCX export
- Unity mesh or primitive colliders
- Hitboxes for interactables

## Workflow

```
Identify collision needs → Build proxies → Name correctly
  → Test overlaps → Export with render mesh
```

## Collider Types

| Type | Use |
|------|-----|
| Box | Crates, walls, simple props |
| Capsule | Characters, poles |
| Sphere | Balls, soft approximates |
| Convex hull | Organic / irregular single body |
| Multiple convex (UCX) | Vehicles, complex props |

## Unreal Naming

```
UCX_SM_Asset_01
UCX_SM_Asset_02
```

- Must match associated mesh naming rules for auto-association
- Convex only for UCX

## Unity Notes

- Prefer engine primitives when possible
- Mesh colliders: convex toggle for dynamic rigidbodies
- Keep proxy collection exportable

## Authoring Rules

1. Slightly smaller than visual mesh to reduce snagging (project-dependent)
2. No holes; watertight convex pieces
3. Apply scale
4. Origin aligned with render mesh
5. Collection: `COL_Collision_[Asset]`

## Validation

- [ ] Player cannot fall through intended blockers
- [ ] No huge invisible walls beyond mesh
- [ ] Wheel/character capsules oriented correctly
- [ ] Named for target engine

## Constraints

### MUST DO
- Prefer few simple shapes over one complex mesh
- Match engine naming conventions
- Keep proxies in dedicated collection

### MUST NOT DO
- Use render LOD0 as physics mesh by default
- Non-convex UCX for Unreal auto-convex workflows

## Reference Guide

| Topic | Reference | Load When |
|-------|-----------|----------|
| Collider Recipes | `references/collider-recipes.md` | When needed |
| Engine Naming | `references/engine-naming.md` | When needed |
