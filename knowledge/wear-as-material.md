# Grime, stains, cracks and chips modelled as meshes

**Seen on:** corridor pilot, P8, Oct 2026 · **Modes:** blockout, camera_match · **Routes:** all

**Symptom:** stain and tide-line meshes on the ceiling, rust decal meshes, and jagged chipped edges cut into the wall shell. The user textures the scene, so all of it was rework, and the jagged shell made the walls hard to texture.
**Cause:** P8 ("wear and time") was read as "model the wear".
**Fix:** wear is material work. P8 places only damage that changes the silhouette (a broken board, fallen debris). Grime, stains, leaks, cracks, rust and chips go into the texturing brief as notes with their location. Wall shells stay simple shapes. Detailed damage comes from generation (`tripo-props`) only in full CG or a detailed blockout.
**Test:** `stats.py › flat_dense` flags thin decal meshes; the supervisor flags wear geometry in the blockout modes.
