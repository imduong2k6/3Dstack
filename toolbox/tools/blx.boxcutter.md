---
id: blx.boxcutter
kind: blender_extension
name: BoxCutter
version: "7.20.6"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/BoxCutter/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/BoxCutter/release_log.md
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/BoxCutter/addon (keymap.py, toolbar.py, operator ids)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - https://superhivemarket.com/products/boxcutter
  - https://boxcutter-manual.readthedocs.io/en/latest/boxcutter_page/
  - https://80.lv/articles/boxcutter-a-blender-modeling-add-on
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [blockout, modeling, modular-kit]
routes: [blender, blender_unreal]
---

# BoxCutter

**What it does:** An interactive hard-surface modeling tool by Team C: draw a box, circle, n-gon or custom shape on a surface and cut, slice, inset, join, knife, extract or make from it. Shapes stay live as non-destructive boolean cutters until applied. The manifest has no description beyond the name.

## Use it for
- Stage 3 blockout and Stage 4 kit pieces on the Blender routes: window and door openings in wall proxies, panel cuts, bevelled hard-surface detail on props, all at real scale on the kit grid.
- Cutting trim and recess details into the pilot kit piece before the batch.

## How to call it
- UI only. In the 3D View press Alt+W (`bc.tool_activate` in the add-on's keymap) or pick the BoxCutter tool in the toolbar (`bc.shape_draw`), click and drag a shape, then pick the cut type. Dots adjust the shape after drawing; Ctrl gives dot snapping; `bc.smart_apply` applies the cutters. Sidebar tab "BoxCutter" holds the options (tab name is a preference).
- It is a modal, mouse-driven operator (`bc.box`, `bc.circle`, `bc.ngon`, `bc.custom`), not a scripting API. Headless or MCP-driven work should use plain Boolean modifiers or bmesh for the same cuts. I did not test it through `execute_blender_code`.
- Not loaded in `bin/blender-bg` (it runs `--factory-startup`).

## Settings that matter
- Cutter origin options (7.1): mouse position, initial centre, bounding-box centre, active object. Choose one before cutting if pivots must follow the spec.
- Keep the cutter modifiers non-destructive while iterating, then apply (Smart Apply) before export and before checking sizes within 1 cm.

## Gotchas
- Until applied, cuts stay live as boolean-style cutter shapes. Apply them and export only the selected final meshes so no cutter geometry reaches the FBX; with Better FBX, modifier application is skipped on meshes with shape keys.
- Boolean cuts can leave n-gons and triangles; clean up before the UV and LOD steps if the spec asks for quads.
- Version labels differ: the installed manifest says 7.20.6, while Superhive lists "BoxCutter 26: Stiletto" (Blender 3.5 to 5.2, $20, GPL, updates free). I could not map one to the other.
- One reviewer on the Hard Ops and BoxCutter bundle page reported breakage on Blender 5.0; I found no report for 5.2 and did not test it.
- Local check: BoxCutter is installed but not enabled; Hard Ops (`hardops`) is enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)).

## Don't use it for
- Organic or sculpted shapes (use sculpt tools), UVs, or anything needing a reproducible script (use modifiers via bpy).
- Route `unreal` in-engine work: kit pieces are modeled in Blender anyway; see `ue.modelingtoolseditormode` for in-editor proxies.

## Version notes
- The shipped `release_log.md` stops at 7.1: cutter origin options, G and R transform re-entry, Alt+D dot toggle, a Release Lock mode for touch, Recut, Slice adjustment. I found no log for 7.20, and the extensions.blender.org slug I tried returned 404; it is sold on Superhive and Gumroad.
