# Facades from modules and patterns (PCG)

For a scene with many walls of a few heights, build the walls from a small set of modules and give each wall a pattern (a list of modules along its run), instead of one whole-height piece per wall. An Unreal PCG graph or Blender Geometry Nodes places the modules from the patterns. Measure the set from the approved blockout; do not design it first. Specs, ports and sockets follow the rest of the `modular-kit` skill.

## What the kit holds

- **Storey classes.** Measure every blockout wall (rays on a grid snapped to its vertices): bottom and top z, length, thickness, outline and the rectangular openings along the run. Group the heights into a few classes (for example a base storey, a base storey on lower ground, a double-height ground storey, an upper storey, a parapet band), each with one height. Before grouping heights, merge blockout objects of one frame that touch in Z into one rectangle: paint lines and trim bands left as separate objects read as storeys and make false classes. A taller wall is a stack of classes. A wall that fits no class or stack, is not a rectangle, or has an odd thickness is listed as not patterned, with the reason, and stays a one-off. Ask the user before adding a class for a few walls.
- **z = 0 and the pivot.** `z = 0` of every module is the underside of its own storey's slab, so a stack adds the class heights. The pivot is the bottom-left corner of the outer face, with the outer face looking along -Y: `pivot: bottom-left-front` in the spec, which `validate_mesh.py` can check. A module placed along a wall is rotated so its -Y is the wall's outer normal.
- **Plain modules and a filler.** Plain wall 0.5, 1.0 and 2.0 m wide per class (any run is a sum of them), and one scalable filler (`scalable: true`, 1.0 m at rest) stretched along the run to take up what the plain modules cannot. A stretched filler stretches its UVs, so keep the stretch small, and project the wall material in world space where seams between modules would show.
- **Corners and end caps.** Outside corner, inside corner and end cap, as wide as the wall is thick. The ends of a run are `CornerOut`, `CornerIn`, `EndCap`, or `Butt` (it meets another wall: no module).
- **Bays.** A bay is a wall module with an opening cut in it: a standard 1.4 m width with the opening centred between piers of 0.2 to 0.25 m of wall (`piers_m`), plus a narrow variant where a measured opening needs it, one bay per opening kind (door, narrow door, window, door with a vent). A bay carries `SOCKET_` empties for what fills the opening: `SOCKET_frame`, `SOCKET_door_set` (door), `SOCKET_glass`, `SOCKET_grille`, `SOCKET_sill` (window), a `SOCKET_ac` where a unit hangs. The door or window is an inset piece fitted to the opening (`kit_joint_test.py`, Openings and insets).

## Module CSV and patterns

`kit/facade_modules.csv`, one row per module and class:

```text
symbol,mesh,role,storey,width_m,height_m,depth_m,scalable,weight,uses_in_patterns,openings,piers_m,sockets
Plain_100_A,SM_Wall_Plain_100_B1_A,Plain,B1,1.0,3.2,0.3,false,0.004,7,,,
Filler_100_A,SM_Wall_Filler_100_B1_A,Filler,B1,1.0,3.2,0.3,true,0.009,15,,,
BayWin_140_A,SM_Wall_BayWin_140_B1_A,BayWin,B1,1.4,3.2,0.3,false,0.001,1,Win 0.9x1.2 @u0.25 z1.1,0.25,SOCKET_frame SOCKET_glass SOCKET_grille SOCKET_sill
```

`symbol` is the class-free name patterns use; `weight` is the module's share of all uses; `openings` gives kind, size and offset (`@u` along the run, `z` up) of the opening in the bay.

`plan/facade_patterns.yaml`, one line per patterned wall (each line a flow mapping, so JSON reads it too):

```text
{"wall": "Wall_A", "objects": ["Wall_A"], "origin_world_m": [0, -7.5, -0.2], "run_dir": [0, 1, 0], "outer_normal": [1, 0, 0], "length_m": 4.2, "thickness_m": 0.3, "ends": {"left": "EndCap", "right": "Butt"}, "storeys": [{"class": "B1", "z0_m": 0.0, "height_m": 3.2, "sequence": [{"s": "EndCap_A"}, {"s": "Plain_200_A"}, {"s": "BayWin_140_A"}, {"s": "Filler_100_A", "w": 0.5}]}]}
```

Sequences run left to right seen from outside, from `origin_world_m` (the bottom-left of the outer face) along `run_dir`; each storey row starts at its `z0_m`. A token is `{s: symbol}`, `{s: filler, w: width}`, or `{gap: g}`: an empty stretch of `g` metres along the run for a full-height opening, with the end caps either side as its jambs. In Unreal the wall run is a spline: Subdivide Segment walks the token widths and a spawner picks the mesh by symbol. That graph is not built or tested yet (the editor was not available); build it on the first wall and write the settings into `toolbox/tools/`.

Two stretches besides the filler's, both read from the pattern and the CSV:

- **Z:** a storey row whose `height_m` differs from its module's `height_m` stretches that module in Z. Only the filler and the end posts stretch this way, never a bay (its opening would move).
- **Y:** a wall whose `thickness_m` differs from its module's `depth_m` stretches the module in Y. A bay's reveals and sockets scale with it.

The PCG graph (or Geometry Nodes group) must read the gap token and both stretches, or it builds the wrong walls.

## Fit check

Before a pattern is trusted, rebuild its wall on a copy of the blockout from the CSV and the pattern, measure the rebuilt wall with the same rays as the measure step, and compare the outline and every opening corner with the blockout wall (within 10 mm). Compare blind pockets by position and depth as well as the openings that go through: a check that only sees through openings passes a wall that hides a recessed pocket. Measure the rebuilt wall's opening edges so they do not snap to a module seam, and do not fail a notch that the blockout wall has too; both gave false failures. The module widths plus the filler must add up to `length_m` with no gap and no overlap. A wall that fails is re-patterned or stays unpatterned, with the reason kept beside the measurements (`kit/facade_measure.json`). No script for the measure, plan and fit steps ships with the pipeline yet; write them from this page and keep them with the project.
