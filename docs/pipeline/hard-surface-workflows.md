# Hard-surface workflows: research, November 2026

What practitioners and official docs say about hard-surface modelling, set against what our own blind tests measured. Use it when a change touches `modeling`. The measured rules themselves are in `.claude/skills/modeling/references/subd-recipes.md`.

**How strong this is.** Most of it is practitioner opinion. Polycount blocks automated reading, so its threads are known only from search summaries, and those are marked. I read Frank Polygon's own tutorials and Pixar's OpenSubdiv notes in full. I found no census of studios, no GDC or studio talk on choosing a workflow, no numeric acceptance limit, and no published limit for how much normal error shows.

## The claim that most game assets are SubD baked to the same mesh

**Not supported as stated.** No named source says it.

- For high-to-low being the norm: Polycount posters say so (summaries, small self-selected sample).
- For "low = the same cage at a lower level": examples only, such as a pepperbox pistol breakdown on gamesartist.co.uk (search summary, date unseen). Frank Polygon says a cage can look decent without SubD but may then need a higher segment count.
- Against it as the only way: Armstrong [stripped the modifier stack](https://marmoset.co/posts/baking-a-hard-surface-weapon-in-toolbag/) of a 3ds Max high poly rather than use a level (Dec 2025). The Hard-Surface Lead at Angelic [ships mid-poly with no bake](https://80.lv/articles/creating-assets-within-the-mid-poly-workflow-in-ue5/) (Sep 2022). Artists credited on shipped games [bake from a mid-poly with a bevel shader](https://marmoset.co/posts/toolbags-bevel-shader-in-action-3-artists-weigh-in/).

So SubD is one common way to make the high, and a lower level of the same cage is one of several ways to get the low. `game_midpoly` stays the default on the game route.

## Where sources and our tests meet

| Topic | Sources | Measured here | Decision |
| --- | --- | --- | --- |
| Booleans under SubD | Frank Polygon: calling them incompatible with SubD is a misconception, given a prepared base. A Blender Artists poster: careful modelling beats fixing a cut. Split | All three solvers leave n-gons on a simple cut. One scripted run on a drawn plate, the user's order: 0 folds, poor flow with script-picked split lines. One bracket from a photo: shape and sizes held, 68 n-gons and 9 folded edges failed | "No Boolean" becomes "only on a prepared base". Flat and prismatic parts take the user's blockout route (`subd-blockout.md`). Curved faces still end in quads |
| 6-poles | Pixar: avoid high valence, one 5-pole turns three loops into five. shootfirst.art: about 6 gets unwieldy. Polycount reply (summary): always avoidable | The sources were right. A three-quad 4 to 2 has no 6-poles, uses fewer faces and halves the raw error of the six-face cell (4.52 against 8.16), 2 to 5 times less with rings scaled. Our test 05 hadn't tried it; a control agent found it | Three-quad on smooth halvings. 6-poles stay only where a six-face cell is needed for a hard edge on the dense ring or a whole dense loop |
| N-gons and tris on flat faces | Frank Polygon, shootfirst.art, CG Cookie: fine if nothing shows. Polycount: divided | With a support row a 16-gon cap dips 0.0001, without one 0.052. A half ring wrapped round a hole folds across it, quarter rings don't | The user allowed n-gons on flat faces, 1 Nov 2026. Conditions from the measurements: a support row all round and a centre that sees every edge |
| Support loops | Frank Polygon: topology first, loops last, from a live bevel modifier. Pixar: creases are cheaper than loops. Polycount (summary): creases may not export and still need support | Bevel with 2 segments, profile 1, Loop Slide off, is a plain loop inserter. Cut = w / 6 | Loops by bevel are allowed. No edge crease |
| Matching segments at an intersection | Frank Polygon: raise the count until edges line up, match out to 45 degrees on a perpendicular cylinder, use wall edges as support. Polycount (summary) agrees | Not run | In `hard-surface-topology.md`, marked as his method |
| Shrinkage | Frank Polygon: move the pinched vertex along the edge normal, in subdivision preview | Fit cuts normal error 2 to 4 times | Agrees |
| Spreading an error | Frank Polygon: confine it to a small area or spread it wide | Round the ring, spreading helps three times. Along rows it doesn't | Both stay, each with its direction |
| Diagonal in a plate | Frank Polygon: triangulate toward the inner vertices so loops don't collapse | The same diagonal holds rims at 0.12 %, but costs the border corner | Agrees, with the corner fix |
| Spans on a circle | Pixar: about 6 for accuracy, 4 in the background | 6 shrinks a ring 17 %, and 8 shrinks it 10 % unless scaled | Multiples of 4 stay for the mirrors. Add the factor table |

## Workflow comparison

| Workflow | Low comes from | Bake | Evidence | Native Blender |
| --- | --- | --- | --- | --- |
| SubD high, separate low | Built or decimated separately | Yes | Testimony, many | Subsurf, Cycles bake |
| SubD high, low from the same cage | Loops dissolved, a level, or a stripped stack | Yes | Few examples | Subsurf, Dissolve Edges |
| Mid-poly, bevels and weighted normals | The one mesh | Support maps only | One named studio, plus Epic's docs | Bevel, Weighted Normal, Smooth by Angle |
| Boolean plus modifiers as the base | The base, or a remesh | Often | Frank Polygon, in detail | Boolean, Bevel, Merge |
| CAD first | CAD mesh exported twice | Yes, or bevel shader | Several artists | None |
| Bevel-shader bake | Mid-poly | Yes | Three named artists | Toolbag is paid; a Cycles Bevel node is a partial stand-in, untested |
| Nanite, no low | None | No form bake | Epic's docs, no shipped numbers | Mid-poly with custom normals |

## Findings

```yaml
- finding: Treat a lower SubD level of the same cage as one way to get the low, not the pipeline default
  source: https://marmoset.co/posts/baking-a-hard-surface-weapon-in-toolbag/
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "keeps the game route honest; no default built on an unsourced claim"
  recommend: adopt_now
- finding: Booleans work on a prepared base with matched segments, stray edges cleaned and room for loops
  source: https://frankpolygon.artstation.com/blog/oebM/boolean-sub-d-hard-surface-modeling-123-blocks-exercise-tutorial
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "drops a blanket ban that practice contradicts; one artist's tutorials, not measured here"
  recommend: test_first
- finding: Match wall segments to the opening, out to 45 degrees on a perpendicular cylinder, and use wall edges as support loops
  source: https://frankpolygon.artstation.com/blog/e72b/sub-d-modeling-cylinder-to-cylinder-intersections
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "the one numeric rule found for intersections; test 06 did not check it, because its branch spans only about 20 degrees either side"
  recommend: test_first
- finding: Land a rectangle between two wall edges, with a gap left for a fillet
  source: https://frankpolygon.artstation.com/blog/o7Pg/sub-d-modeling-cylinder-and-rectangle-intersections-fillets
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "less pinching at bases without a denser cylinder"
  recommend: test_first
- finding: Topology first, support loops last, from a live Bevel modifier
  source: https://frankpolygon.artstation.com/blog/oebM/boolean-sub-d-hard-surface-modeling-123-blocks-exercise-tutorial
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "width stays adjustable and the cage stays simple; matches our Big, Medium, Small order"
  recommend: adopt_now
- finding: Stripe matcap as a capture mode, and read it from the same camera only
  source: asset_capture.py run on test 05 meshes, Blender 5.2.3
  stage: 4 review
  skill: blender-adapter
  fit: high
  effort: low
  gain: "kinks show that matcap misses"
  recommend: adopt_now
- finding: Replace LoopTools with space_edge_loops_evenly and circularize; a wire ring with no faces is left unchanged
  source: https://developer.blender.org/docs/release_notes/5.2/modeling/
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "no third-party add-on in the rules; run on 5.2.3"
  recommend: adopt_now
- finding: Build the low by stripping the live modifier stack of the high
  source: https://marmoset.co/posts/baking-a-hard-surface-weapon-in-toolbag/
  stage: 4 modelling
  skill: modeling
  fit: medium
  effort: medium
  gain: "low stays tied to the form; one artist, not tested here"
  recommend: test_first
- finding: Split UVs at every hard edge, keep a tight cage and one tangent basis
  source: https://polycount.com/discussion/comment/2323188
  stage: 4 modelling
  skill: modeling
  fit: high
  effort: low
  gain: "the commonest bake errors; search summary only"
  recommend: adopt_now
- finding: After a Boolean, subdivide and shrinkwrap onto an uncut copy
  source: https://blenderartists.org/t/questions-regarding-hard-surface-modeling/1207286
  stage: 4 modelling
  skill: modeling
  fit: medium
  effort: medium
  gain: "native; one poster's trick; test 08 replaced the patch instead, so this is still untested"
  recommend: test_first
- finding: A Cycles Bevel node as a stand-in for a bevel-shader bake
  source: https://marmoset.co/posts/toolbags-bevel-shader-in-action-3-artists-weigh-in/
  stage: 4 modelling
  skill: modeling
  fit: low
  effort: medium
  gain: "edge highlights without a high poly; native version untested"
  recommend: later
```

## Other sources

- [OpenSubdiv: modeling tips](https://graphics.pixar.com/opensubdiv/docs/mod_notes.html), official, undated
- [Frank Polygon: lathe chuck key](https://frankpolygon.artstation.com/blog/8Qlv/sub-d-hard-surface-modeling-lathe-chuck-key-exercise-tutorial), [V block](https://www.artstation.com/frankpolygon/blog/M7w7/sub-d-hard-surface-modeling-v-block-exercise-amp-tutorial), 2020
- [shootfirst.art: topology](https://www.shootfirst.art/toplogy)
- [Epic: Nanite](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- [Blender 5.2 modelling notes](https://developer.blender.org/docs/release_notes/5.2/modeling/)
