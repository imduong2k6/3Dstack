---
name: set-dressing
description: Dress the scene with story clusters, controlled clutter and readable density for phases P5 to P8, keeping player and camera paths clear and repeats instanced. Use it during placement phases P5 to P8 on any route.
---

# Set dressing

Adapted from arjun988/blender-skills `set-dressing` (MIT), extended for this pipeline's phases and reviews.

Tell the story through placement: controlled clutter in readable clusters.

## Order

Layout locked, then hero narrative props (P5), story clusters (P6), small clutter inside clusters (P7), wear (P8: texturing notes; silhouette damage only when the user asks), then a lighting check with the rough rig.

## Density by zone

| Zone | Density |
| --- | --- |
| Hero or interaction zone | High intent, low noise |
| Midground | Supporting story clusters |
| Background | Sparse, silhouette only |
| Player path or camera path | Keep it clear |

## Cluster method

1. Pick a story beat: a meal left behind, a workbench in use, a hurried escape. Take it from the brief's context and the research's wear-and-story notes.
2. Place 3 to 7 props that sell that beat. Real placement: things sit where hands put them, against walls and on surfaces, at the heights from the metrics.
3. Note 1 or 2 wear cues in `handoff/wear-notes.md` for the user's texturing; don't model them.
4. Stop. Don't fill every surface.

## Rules

- Dress only after navigation works (games) or the hero cameras are locked (CG).
- Instance repeated meshes. Vary rotation and scale slightly, within what a real object allows.
- Don't block doors or windows without a story reason, or wallpaper uniform clutter.
- Fewer props with more meaning for sparse or horror moods; leave negative space on purpose.
- Every cluster gets an ID and a one-line story in `phases.md`, so the Art Director can judge it against the intent.
