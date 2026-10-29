---
id: ue.fab
kind: unreal_plugin
name: Fab
version: "0.0.21"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Fab/Fab.uplugin
  - https://dev.epicgames.com/documentation/unreal-engine/fab-window-in-unreal-engine?lang=en-US
  - https://forums.unrealengine.com/t/fabs-integrations-for-unreal-engine-5-and-uefn-are-live/2083702
  - https://forums.unrealengine.com/t/quixel-to-fab-transition-faqs/2033839
  - https://forums.unrealengine.com/t/add-to-project-no-longer-works-for-plugins-not-registered-as-5-7-compatible/2676230
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
pipeline_stages: [modular-kit, set-dressing]
routes: [unreal, blender_unreal]
---

# Fab

**What it does:** The in-editor Fab marketplace window: search Fab listings, add free or owned products to your library, and download them straight into the open project. It is the successor to the old Quixel Bridge and Marketplace tab, and is how Megascans now reaches Unreal. Plugin is editor-only, `EngineVersion: 5.8.0`, `EnabledByDefault: true`.

## Use it for
- Stage 4 library pulls on route `unreal`: props, materials and foliage that the asset list marks `source: library`. Prefer free or already-owned listings.
- Megascans surfaces and 3D assets for set dressing (P5 to P9), with the quality tier chosen in Fab Settings.
- Not for assets the Modeler must build to spec (kit pieces, pivots, sockets).

## How to call it
- Open: Window > Get Content > Fab, or the Fab button next to Add+ in the Content Drawer. If missing, tick Edit > Plugins > Fab and restart.
- Search with Boolean operators (AND, OR); filter by product type, Style, Compatibility, Technical features, Licenses and Price. "Include 3D compatible formats" also lists GLB, glTF and FBX.
- In My Library, the + icon on a tile downloads the product and adds it to the current project. Free listings can be added from the preview. Drag-and-drop from My Library was unavailable at launch (forum); use the + button.
- No Python or MCP interface for Fab is documented. It is a human-driven window that needs an Epic sign-in; agents must not sign in or buy.

## Settings that matter
- Fab Settings: Preferred Quality Tier for Megascans, Low, Medium (default), High or Raw. Pick the tier per asset against its budget; the page gives no triangle or texture sizes per tier.
- Fab cache location (default under AppData/Local/Temp/FabLibrary) can be changed in Fab Settings; put it on the big drive.
- Licence: check the product's licence tile before use. Free Megascans claimed during the promotion fall under the Fab Standard License (usable in any tool or engine per Epic's FAQ).

## Gotchas
- Only products usable in Unreal appear in the window; others need the Fab website.
- Paid items: Buy now needs a licence choice and checkout. Never complete a purchase for the user without their confirmation of item and total.
- Forum report (5.7): "Add to Project" can be disabled for plugin listings not registered as compatible with the running engine; the workaround is downloading the plugin into the project's Plugins folder.
- Fab has no one-click export to DCC tools. For Blender routes, download from Fab.com and import the files, or use `blx.megascans_bridge` for assets already held in Quixel Bridge.
- This repo is public: do not commit downloaded Fab, Megascans or Marketplace content (CLAUDE.md rule).

## Don't use it for
- Route `blender` (CG) work: assets go in through Blender add-ons or files.
- Anything whose size matters: verify scale against `plan/metrics.yaml` after import.

## Version notes
- Fab plugin 0.0.21 targets engine 5.8.0. I found no Fab-window changes in the 5.8 release notes (the only Fab mention is MetaHuman Animator Markerless Motion Capture, a separate plugin distributed on Fab).
