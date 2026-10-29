# Cables that end in mid-air

**Seen on:** corridor pilot, P3, Oct 2026 · **Modes:** all · **Routes:** all

**Symptom:** some cables started or stopped in mid-air instead of at a box, a meter or a conduit.
**Cause:** cables were drawn as free curves for the look in the camera, with no source and destination.
**Fix:** the layout lists every cable run with its source and destination (`layout.json › runs`). Each run starts and ends at a real object or past the frame edge. With `brief.yaml › cables: rig`, the worker uses the cable generator in the toolbox (one rig per run, its Start and End objects on the end points). With `guides`, it leaves one curve per run with marked end points for the user's own cable tool.
**Test:** the supervisor checks each run's two ends against the run list at P3.

Notes on the user's geometry-nodes cable rig (toolbox entry `bl.cable_generator`): the sag comes from a Cloth modifier pinned at the ends, so it shows only after frames are simulated. Bake the cloth cache and keep the scene on a fixed frame, or switch the rig to its Curve mode. In Blender 5.2, `modifier.keys()` on a geometry-nodes modifier raised a TypeError; read the inputs through `modifier.node_group.interface.items_tree` instead.
