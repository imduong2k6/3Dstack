---
name: tripo-props
description: Make detailed placeholder props with Tripo for a pipeline scene - a Magnific turnaround or 3/4 image, re-cropped views, Tripo Studio image-to-3D driven in the user's browser by the Generator, "Send to Blender" over the DCC Bridge (GLB download as the fallback), then clean-up to the spec's size and pivot, an orientation check and the props atlas. Use it when an asset spec has source generate and Tripo is in brief.yaml's generation_services, which happens only when detail is detailed or final.
---

# Tripo props

Image to 3D placeholder prop, cleaned to its spec and placed. Tripo meshes are **stand-ins**: 1K textures, light clean-up, no baking, no decimation. The user may re-model them later.

**When:** only when `brief.yaml › detail` is `detailed` or `final` (`generated-asset`; the mode table is in `scene-pipeline`). With `massing`, the props are simple shapes.

**Who does what.** The Generator drives Studio and does the downloads: one browser tab, one generation set-up at a time (Studio itself can run queued jobs). The route's Blender worker only imports: it receives the result in the open Blender and runs the scripts (sections 5 to 7). It never opens Studio and never spends credits. Sections 1 to 4 are the Generator's, sections 5 to 7 the live worker's. Nobody else touches the Tripo tab or the credit spend; other agents can write specs and prompts. Browser, GLB downloads into the work folder and headless Blender are approved once at G0 (`house-rules` rule 11).

**The user's:** Tripo sign-in, buying credits, plan changes, anything on an account page. Read the balance Studio shows; never click purchase or upgrade. G0 sets the credit budget (`brief.yaml › budgets.credits_tripo`); plan the polycount and retries before clicking Generate. On an earlier project 19 props cost 915 credits (3,200 to 2,285).

## 0. Before you start

- **Blender (the live worker):** the scene open, with the Tripo DCC Bridge add-on (`Tripo3d_Blender_Bridge` v1.0.34) running its WebSocket server on `127.0.0.1:60600`, connected before the batch starts. Only one Blender instance can hold the port.
- **Browser (the Generator):** the user signed in to `https://studio.tripo3d.ai/workspace/generate` in **one** tab, in Claude in Chrome (load the `anthropic-skills:chrome-browser` skill, then every Chrome tool you need in one `ToolSearch`, `file_upload`, `find` and `javascript_tool` included). The bridge keeps only the newest client, so a second Studio tab disconnects the first.
- **Spec:** `kit/<asset>.md` with `dims_m`, `dims_source` (the real size, never the AI image), `pivot` (or mount), collision, and the input prompt.

## 1. Make the input image (Magnific)

- **Route A, multi-view:** a Seedream 5 Pro 2k orthographic turnaround, about 100 credits. Either a 1×4 strip (front, left, back, right) or a 2×2 grid (top-left front, top-right left, bottom-left back, bottom-right right).
- **Route B, single image:** one Flux 2 Pro 3/4 product shot, about 50 credits for 2 variants. The whole object, uncropped, on a plain light-grey background, no cast shadows, no readable text. Use B whenever the route A sheet comes back in perspective, inconsistent, clipped or not a clean grid.
- Save images to `<work_dir>/assets/<asset_id>/source/NN_round/`, never loose in a shared folder.

## 2. Re-crop the views (route A only)

Magnific's grid split clips wide views, and per-view padding gives each view a different object scale, so Tripo returns **shards**, even at 10k polygons. Re-crop every view to one shared square size:

```
bash bin/blender-bg --python-exit-code 1 --python .claude/skills/tripo-props/scripts/recrop_turns.py -- <folder with *_turn.png> <out folder>
```

- It reads every `*_turn.png` in the folder, so copy only the sheets you want into a temp folder.
- Expect 4 objects per sheet. If shadows merge two views, rerun with `RECROP_THR=0.6 RECROP_COL=0.03`.
- Grids give `<name>_front|left|back|right.png`; strips give `_v0` to `_v3` (v0 front, v1 left, v2 back, v3 right). Look at the crops before you upload them.

## 3. Generate in Tripo Studio

| Setting | Value |
| --- | --- |
| Mode | HD Model, H3.1 |
| Ultra Mesh Quality | **Off**: 30 credits instead of 45, no visible difference at these polycounts |
| AI Complete | Off |
| Remove Lighting | On |
| PBR | On |
| Topology | Triangle |
| Texture | 2K, the lowest offered; 1K is chosen at export |

**Polycount by complexity, never under about 5k** (thin or boxy props shattered at 436 to 2,500 triangles): a plain box about 5k, a small electrical box 8 to 12k, a medium prop 10 to 20k, grilles, piles and shelves of goods 30 to 60k.

1. **Pick the upload mode.** The first three icons in the Generate panel are single image, multi-view and **Batch**. Batch makes a separate model per image at N times the cost; check a screenshot before you generate.
2. **Upload.** `find` the file input, then `file_upload`. Multi-view: one image per slot. Grid: Front = front, Left = left, Right = right, Back = back. Strip: Front = v0, Left = v1, Right = v3, Back = v2. If the result comes out mirrored, swap Left and Right.
3. **Polycount.** Open Geometry & Texture, triple-click the polycount field, type the number, press **Tab**, then `find` it to read it back.
4. **Generate.** Small props take about 95 s, bigger ones 2.5 to 4 min. For the next prop meanwhile: scroll the left panel up, hover the image, click its trash icon, and upload the next one.

Details, the JavaScript send and failure modes: [references/tripo-studio.md](references/tripo-studio.md).

## 4. Check, export, send to Blender (the Generator)

1. **Look at the result in the viewer**, not the thumbnail, and judge it against the spec's rubric (`generated-asset`, Judge and regenerate: one change per round, three rounds per asset). Shards or lumps: regenerate with a higher polycount, views re-cropped at one scale, or a single 3/4 image.
2. **Export:** set File Name to the spec's id (`SM_<Name>`, or `SM_<Name>_v2` when a master of that name exists). The name **resets every time the panel closes**. Set Texture Resolution to **1k**.
3. **Hover "Send to"**, then click **"Send to Blender"** in its submenu. Clicking "Send to" itself does nothing.
4. **Wait 25 to 40 s**; Studio shows no progress. Never resend while a big model is still transferring, or you get `.001` duplicates. Watch the bridge log (`%TEMP%\tripo3d_blender_bridge.log`, readable as a file) for "Successfully imported".
5. **Stall budget.** No import 90 s after the click: toggle top bar **DCC Bridge** (switch **Blender** off and on; it can turn itself off between sends) and resend once. Still nothing after another 90 s: switch to **GLB** for the rest of the batch. Export as GLB at 1k and download it to `<work_dir>/assets/<asset_id>/source/` (approved once at G0), and the live worker imports the file. Log the switch in `log.md`. GLB is the fallback, not the default: the next batch tries the bridge first, and making GLB the default needs the user's OK.
6. **Check the name in Blender** (the live worker). One import arrived under Tripo's own title instead.

## 5. Clean up in Blender (the live worker; back up first)

The live worker takes a step backup (`house-rules` rule 4), then runs the script. An import lands in the active collection, scaled so its largest side is about 1 m, front on −Y, with a material `tripo_mat_<hash>` and packed 1K images. The root may be an Empty with children rather than a mesh.

```python
exec(open(r"<repo>/.claude/skills/tripo-props/scripts/tripo_cleanup.py").read())
cleanup({"SM_<Name>": (dims_m, "wall", True)})   # dims_m = the spec's [W, D, H], pasted as it is
```

`dims_m` is one triple in the spec's order: X = W, Y = D (off the wall), Z = H. Corrected 30 Oct 2026: the old call took `(W, H, D, mount, collide)`, so a pasted triple swapped depth and height, and the self-check asserted the same swap. The old form now raises; fix any call written before that date.

- Mounts: `wall` = back-face centre on y = 0, `floor` = base centre, `hang` = top centre, `inset` = pass `pivot_min={name: (x, y, z)}`.
- Pass `rot_x` or `rot_z` (`{name: degrees}`) when the front isn't on −Y; they apply once.
- `collide` is True on the game routes (it adds a `UCX_SM_<Name>_01` box child, the one name in `collision-proxy`; a rerun removes an old `UCX_SM_<Name>`) and False on `blender`.
- **Scale is uniform by default**: one factor from the governing axis (`"governing": "W"`, `"D"` or `"H"` in the opts; default the axis the spec gives the most length). If the three axes would need factors more than 8 % apart, it raises before it changes anything: the generation has the wrong proportions. Regenerate (higher polycount, views re-cropped at one scale, or a single 3/4 image). Correct `dims_m` only from a sourced measurement (`dims_source`), never from the generated mesh. `scale="per_axis"` (the old stretch) needs a reason written in the spec.
- **Tubes** (conduit, pipes, poles): add opts as a fourth item, `(dims_m, "wall", False, {"kind": "tube", "diameter_m": 0.045})`. It scales uniformly so the cross-section equals the diameter (default: the spec's two cross-section sizes, which must agree within 2 mm), and it raises unless the result is round within 2 mm. It warns when the length ends up more than 8 % off the spec. Never stretch a tube to a box that includes clips or lips.
- **`materials="palette"`** (no textures, no atlas): `cleanup(props, materials="palette")` with `{"material_group": "<group>"}` in each prop's opts. Every slot becomes one flat material `M_<group>`, shared by all props of the group, and the Tripo materials and images are removed. Use it when the pipeline stops before texturing, so the value and hue passes get clean groups. The default, `materials="textured"`, keeps the 1K textures.
- It merges by distance, recalculates normals, moves the prop to `COL_Props_Masters`, and asserts the size. In textured mode it also renames to `M_<base>` and `T_<base>_BC|M|N|R` and caps textures at 1024.
- Give each material its `material_group` so the lighting passes reach it.
- Replacing a master: send the new one as `SM_<Name>_v2`, delete the old object, its `UCX_` and its data once nothing uses them, rename, run `cleanup()`, and rebuild the atlas if the old one was on it ([references/blender-side.md](references/blender-side.md)).

Self-check: `bash bin/blender-bg --python .claude/skills/tripo-props/scripts/tests/check_tripo_cleanup.py`.

## 6. Orientation check (live session)

```python
exec(open(r"<repo>/.claude/skills/tripo-props/scripts/qa_views.py").read())
qa(["SM_<Name>"], r"<scratch folder>/qa", res=360)
```

The side that faces the camera or the path must be in each `_front.png`. If the pictures are ambiguous, count the vertices in the front and back 20 % of the depth: the detail sits on the front. Read sizes from mesh vertices, not `bound_box`, for objects in an excluded collection.

## 7. Props atlas (game routes, when materials are capped)

Every import adds a material. When `budgets` caps materials or texture sets, fold the props into one atlas (not with `materials="palette"`, which keeps no textures):

```python
exec(open(r"<repo>/.claude/skills/tripo-props/scripts/props_atlas.py").read())
BASES = ("Meter_kWh", "JunctionBox")   # base names in cell order; append only, never reorder
build(r"<work_dir>")
```

It writes `<work_dir>/textures/props_atlas/` (4 columns of 1024 px cells), copies each original texture to `textures/tripo_src/<base>/` first, keeps existing cells pixel for pixel when it grows, and does nothing on a rerun. `RETOUCH` holds per-prop look fixes; the ones in the file belong to an earlier project's props. Test first, headless: `bash bin/blender-bg --python-exit-code 1 --python .claude/skills/tripo-props/scripts/tests/test_props_atlas.py -- <out folder>`.

## Costs per prop

| Step | Credits |
| --- | --- |
| Magnific turnaround (Seedream 2k) | about 100 |
| Magnific 3/4 shot (Flux 2, 2 variants) | about 50 to 100 |
| Tripo HD H3.1, Ultra Mesh off | 30 |
| Tripo with Ultra Mesh on | 45 |

## Report per prop

In the spec's `generated` block and the log: the input route, how it reached Blender (bridge or GLB, and any stall), the polycount asked and the triangles that came back, the final size and mount, UCX or not, the credits spent (Tripo and Magnific), and anything not checked (for example no lit render).
