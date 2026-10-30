# Grime, stains, cracks and chips modelled as meshes

**Seen on:** corridor pilot, P8, Oct 2026 · **Modes:** blockout, camera_match · **Routes:** all

**Symptom:** stain and tide-line meshes on the ceiling, rust decal meshes, and jagged chipped edges cut into the wall shell. The user textures the scene, so all of it was rework, and the jagged shell made the walls hard to texture.
**Cause:** P8 ("wear and time") was read as "model the wear".
**Fix:** wear is the user's texturing work (`house-rules` rule 1). P8 places repairs (patched panels, replaced parts); damage that changes the silhouette is built only when the user asks. Grime, stains, leaks, cracks, rust and chips go into `handoff/wear-notes.md` with their location. Wall shells stay simple shapes.
**Test:** `stats.py › flat_dense` flags thin decal meshes; lint's `wear_geometry` check is a blocker at every gate.
