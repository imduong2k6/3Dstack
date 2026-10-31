---
name: linear-runs
description: Build service runs (conduit, cables and cable bundles, pipes, downpipes, round ducts) in Blender from plan/services.yaml rows with one tested script that routes each run along the walls, refuses anything that would pass through a solid, bends it at a real radius, ends it inside its anchors and puts saddles, clips or clamps at a set spacing. Use it in P3 and in any lane or fix lane that builds or repairs services on the Blender routes, instead of typing path points.
---

# Linear runs

Lanes that typed service paths by hand spent most of their time working out coordinates, and every cable through a solid and every dead end came from those hand-written points. Here the agent writes or picks a row in `plan/services.yaml`, and `scripts/linear_runs.py` turns it into geometry the same way every time. A run that would hit something is not built: the report names what it hit and where, and the row gets a `path_m` or `via_z`, never a hand-placed mesh.

Blender routes only. On the Unreal route, services stay PCG and splines (`placement-phases`).

## Use it

In a lane's build script, or in a patch (it runs twice and gives the same objects; nothing is ever named `.001`):

```python
import sys; sys.path.insert(0, r"<repo>/.claude/skills/linear-runs/scripts"); import linear_runs as LR
rep = LR.build(P + "/plan/services.yaml", runs=["R02", "R04"], metrics=P + "/plan/metrics.yaml",
               materials={"conduit": "M_PVC_Grey", "cable": "M_Cable_Black", "support": "M_Steel"})
assert rep["ok"], rep["blocked"] + rep["errors"]
```

Headless on a copy, never on the live file (`house-rules`, one writer per live editor):

```bash
bash bin/blender-bg <copy.blend> --python .claude/skills/linear-runs/scripts/linear_runs.py -- --services $P/plan/services.yaml \
  --metrics $P/plan/metrics.yaml --runs R02,R04 --material conduit=M_PVC_Grey --material support=M_Steel --out lr.json --save
```

It prints one line (`LINEAR_RUNS OK|FAIL built= blocked= errors= warnings=`); the details are in the JSON. Materials must already be in the file: a missing one is an error, never a new material.

## The row

The `detail-inventory` row as it is (`from`, `to`, `by`, `metric` or `dia_mm` with `source`, `count`, `sag_m`, `path_m`), plus optional fields this script reads:

| Field | On | Meaning |
| --- | --- | --- |
| `object` | node | The scene object the run ends in, when `asset` names a spec rather than the object. Default: `asset`. |
| `dir` | node | The way the run leaves the node: `+x`, `-z` and so on. Default: along the node's wall, toward the other end. |
| `strands_mm` | cable run | One size per strand of a bundle, for mixed strands (`placement-phases`: bundles vary). `dia_mm` stays the checked size. |
| `hang` | cable run | The run hangs between its ends. A `sag_m` also makes it hang. |
| `clip_m` | run | Support spacing, from a sourced metrics row when the references show one. |
| `bend_r_m` | run | Centreline bend radius, from the data sheet. |
| `via_z` | run | A height to try when both straight ways are blocked (over a door, under a window). |
| `material`, `support_material` | run | Override the `materials` given to `build`. |

`path_m` turns the router off: the run follows those points, with only its two end directions snapped to an axis. Leave it out unless a row needs a route the references show.

## What it does

- **Routes** a run along its wall, ceiling or floor on straight axis moves, offset from the surface by its radius plus 2 mm. It picks the shortest route with the fewest bends that keeps a surface behind it, and tries over or under whatever blocks it. Rigid runs first, then cables, so each cable goes around the conduit already built.
- **Refuses** a run that would touch any solid outside its two anchors (five rays along every segment, corners tested for being inside), or a run already built.
- **Bends** at the radius (default 4 times the outside diameter for conduit and cable, 1.5 for pipes, 1 for ducts; at least 12 segments a bend, no facet over 8 degrees). A bend squeezed by a short straight is built tighter and listed in the warnings.
- **Ends** each run 8 mm inside its anchor, so lint reads it as attached.
- **Supports**: saddles on conduit, clips on cable, clamps on pipes and ducts, one within 0.15 m of each end of each straight (0.08 m for clips) and at the spacing between, each one on the surface found behind the run. All supports of a run share one mesh. Default spacing: conduit 0.9 m (`placement-phases`), cable 0.3 m, pipe 1.2 m, downpipe and duct 1.5 m. Change them with `clip_m` from a sourced metrics row.
- **Hangs** cable runs with `hang` or `sag_m` as catenaries between their points. The longest span sags `sag_m` (default 3 % of it) and shorter spans less, as at equal tension. Hanging runs get no supports.
- **Names and tags**: `Conduit_<id>`, `Cable_<id>`, `Pipe_<id>`, `Saddle_<id>_01` and so on, with `lr_run`, `inv_id`, `phase` and `network`. The report lists each run's objects, length, bends, supports and corner points.

## Hanging cables and the cable rig

With `brief.yaml › cables: rig` or `guides`, build hanging runs with `emit="guide"` (`--emit guide`): each becomes a poly curve `CBL_<id>` along the checked catenary, with empties `CBL_<id>_Start` and `_End`. With `guides`, that is the delivery. With `rig`, feed the curve to the rig's Curve input (`toolbox/tools/bl.cable_generator.md`) and vary Seed, Spread and Messiness per run. The rig's spread widens the bundle past the checked curve, so run `scene-lint` after it. The mesh this script makes for a hanging run is for single wires and tests.

## Checks

`scripts/selftest_linear_runs.py` builds a wall corner with a window, two boxes, two brackets and a valve pair, then checks that:
- the window blocks a straight pipe;
- a conduit and a four-strand bundle route around the window and each other;
- every saddle and clip sits on a wall;
- the hanging span sags to its target;
- a repeat build and the command line give the same vertices;
- lint finds nothing on the result (`cable_ends`, `cable_in_rigid`, `conduit_open_ends`, `floating`).

```bash
bash bin/blender-bg --python-exit-code 1 --python .claude/skills/linear-runs/scripts/selftest_linear_runs.py -- <out_dir>
```

Run it after any change to the script or to `scene-lint`'s geometry code (`lintlib.Geo` and `Solid`), which it shares.

## Not built yet

- **Conduit from kit pieces.** The script sweeps conduit as one mesh with saddles; `geometry-nodes` notes say conduit uses the `modular-kit` straights, elbows and couplings. Until a kit mode places those pieces on the report's corners, the manager decides per project which applies.
- Cable trays, gutters, rails and fences; fittings (tees, couplings, sockets on conduit); Unreal.
