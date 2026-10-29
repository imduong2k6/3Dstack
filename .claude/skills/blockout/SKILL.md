---
name: blockout
description: Build the pipeline scene's blockout from the approved layout at real scale on the kit grid, with player or camera checks, the rough light rig and the review camera set that every later gate reuses. Use it in Stage 3 on any route.
---

# Blockout and rough light

Run by the route's worker (see `scene-pipeline/routes.md`), through its adapter skill.

## Steps

1. **Proxies.** One proxy per shape in `layout.json`, kit-sized and on the grid, named with the shape ID (`BLK_W01`). Coloured by legend so captures read like the map.
2. **Checks.** Games: a 1.8 m capsule or mannequin walks the path, with door, stair and ceiling clearances. CG: look through each hero camera and confirm the frame matches the brief.
3. **Rough rig** from `lights.json`: key light at physical units, sky, fog, and exposure locked to the brief's EV100. Placeholder lights only for practicals that drive the composition.
4. **Review cameras.** Create the camera set from `layout.json › cameras`, plus one top view, and save it to `light/cameras.json`. Every later gate reuses these exact cameras.
5. **Capture and stats** with the adapter, then hand over to the supervisor and the Art Director.

Change the scale only when the layout or the metrics change; never fix a capture by moving the camera.

## Exit

G2: the user approves scale, composition and light direction.
