---
id: ue.cablecomponent
kind: unreal_plugin
name: Cable Component
version: "1.0"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Runtime/CableComponent/CableComponent.uplugin
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Runtime/CableComponent/Source/CableComponent/Classes/CableComponent.h
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/cable-components-in-unreal-engine
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/CableComponent
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
pipeline_stages: [placement-phases, set-dressing]
routes: [unreal, blender_unreal]
---

# Cable Component

**What it does:** A simulated rope-like cable (Verlet particles with optional stiffness and collision) rendered as a tube between two attach points, as a component or as the `Cable Actor`. Plugin 1.0, `EnabledByDefault: true`, not beta.

## Use it for
- P4 and P5 hanging or sagging wires: a lamp cord, a power line drooping between poles, a cable dangling from a prop, or anything that must move.
- Nothing that needs to be a fixed, instanced run. P3 services (pipes, ducts, conduits, trays) and static cables follow the structure with PCG, using Sampler plus Spawn Spline Mesh (`ue.pcg`).

## How to call it
- Place Actors panel, search "Cable", drag a Cable Actor into the level. Or add a Cable component to an Actor Blueprint.
- Attach an object to the end: make it Movable, drag it onto the Cable Actor in the Outliner, choose Cable End, then untick Attach End so it swings. Sockets work as attach points.
- C++/Blueprint API (header): `SetAttachEndToComponent(Component, SocketName)`, `SetAttachEndTo(Actor, ComponentProperty, SocketName)`, `GetCableParticleLocations(out Locations)`. Python: `unreal.CableComponent` exists in Epic's Python API; use `set_editor_property` with the snake_case property names (for example `cable_length`, `num_segments`, `solver_iterations`, `cable_width`). I did not run it.

## Settings that matter
- Cable section: `Attach Start`, `Attach End`, `End Location` (relative to the attach target), `Cable Length` (rest length; UI max 1000 but only clamped at 0), `Num Segments` (UI 1-20; more is smoother and dearer), `Solver Iterations` (1-16, higher is stiffer).
- Advanced: `Substep Time` (0.005-0.1), `Use Substepping` (default on), `Enable Stiffness`, `Enable Collision` plus `Collision Friction` (collision uses the component's Collision Preset), `Skip Cable Update When Not Visible`.
- Forces: `Cable Force`, `Cable Gravity Scale`. Rendering: `Cable Width` (0.01-50), `Num Sides` (1-16), `Tile Material` (material repeat along the length).
- Teleport options (`Reset After Teleport`, `Teleport Distance Threshold` 500) prevent the cable snapping when its end is moved far.

## Gotchas
- Epic: enabling Collision and Stiffness "greatly" increases cost; keep them off unless needed. Collision is documented as Experimental.
- It simulates at runtime and ticks like any component. For stills, check that the cable has settled before capture and that sag matches the reference; I have not tested that behaviour in the editor.
- Many cables across a set: each is its own simulated component; PCG-spawned spline meshes are the cheap route.
- The tube is generated at render time by a scene proxy, not a Static Mesh asset, so there is no mesh to export or to list in `transfer/layout.json`.

## Don't use it for
- Static pipes, trays, railings, fences or any run along a surface: use PCG splines or, on Blender routes, curves with a bevel object.
- Anything needing real physics: it is a simple Verlet particle chain with optional sweep collision, nothing more.

## Version notes
- No Cable Component entry in the UE 5.8 release notes. Plugin version stays 1.0.
