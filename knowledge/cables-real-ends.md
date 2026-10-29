# Cables that end in mid-air

**Seen on:** corridor pilot, P3, Oct 2026 · **Modes:** all · **Routes:** all

**Symptom:** some cables started or stopped in mid-air instead of at a box, a meter or a conduit.
**Cause:** cables were drawn as free curves for the look in the camera, with no source and destination.
**Fix:** the layout lists every cable run with its source and destination (`layout.json › runs`). Each run starts and ends at a real object or past the frame edge. With `brief.yaml › cables: rig`, the worker uses the cable generator in the toolbox (one rig per run, its Start and End objects on the end points). With `guides`, it leaves one curve per run with marked end points for the user's own cable tool.
**Test:** the supervisor checks each run's two ends against the run list at P3.

Notes on the user's geometry-nodes cable rig (toolbox entry `bl.cable_generator`): use its Curve mode, one guide curve per run (what worked in the corridor fix, FIX-r1: 7 runs, 90 ends all inside their anchors). The cloth sag needs colliders and a baked cache per run; without colliders the cables hang through cabinets. The rig is metre-scale, so scale each run object down (0.25) for wire thickness, and render with the pipeline's cable material, since the rig's own material reads pink and translucent at real scale. In Blender 5.2, `modifier.keys()` on a geometry-nodes modifier raised a TypeError; read the inputs through `modifier.node_group.interface.items_tree` instead.
