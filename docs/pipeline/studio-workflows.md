# How studios build environments: game and CG

Research for v4: which roles a real game or VFX environment team has, who does creative work and who does repetitive work, and the technical requirements of each step. The last two sections map this onto the pipeline and list what v4 changed because of it.

## The short version

- Both kinds of team split the work the same way. A few people own the creative decisions (art direction, layout, hero assets, lighting), and many people produce volume against those decisions (kit pieces, props, dressing, optimisation, shot variations).
- Game studios formalise that split when they outsource. Gameplay-critical spaces and creative direction stay in-house. Volume work with a locked brief and measurable acceptance criteria (modular kits, props, secondary areas) goes out.
- That is the pipeline's split too. You keep the creative decisions at the gates, and the agents take the volume work. Agent tasks should therefore be briefed like outsourced work: references with callouts, technical specs, scope and a definition of done.

## Game environment

### Stages, roles and kind of work

| # | Stage | Main roles | Kind of work | Technical requirements |
| --- | --- | --- | --- | --- |
| 1 | Level brief | Game or narrative designer, art director | Creative | Gameplay goals, platform and frame rate, camera type, budgets |
| 2 | Key art and map layout | Concept artist, level designer | Creative | Scale callouts, paint-overs, a top-down map |
| 3 | Blockout or greybox | Level designer | Creative, iterative | Player metrics (height, jump, door and corridor widths), grid, playable with collision |
| 4 | Art blockout or proxy | Level artist, environment artist | Mixed | Kit grid, proxies replace greybox, composition and light direction |
| 5 | Production concepts and callouts | Concept artist | Creative | Material and prop callout sheets |
| 6 | Modular kit and trim sheets | Environment artists | Design is creative; the 50 or more pieces that follow are repetitive | Grid snap, pivots, texel density, trim sheets, Nanite or LODs, collision, naming |
| 7 | Props | Prop artists, often outsourced | Hero props creative; the rest is volume | Triangle budget per tier, LODs, collision, material IDs |
| 8 | Materials and textures | Material or texture artist | Mixed | PBR value ranges, tiling, masks, texture memory budget |
| 9 | Assembly and set dressing | Level artist | Storytelling is creative; filler is repetitive | Instancing, PCG, streaming (World Partition), HLODs |
| 10 | Lighting | Lighting artist, in passes | Creative | Exposure, light and shadow budgets, Lumen or baked settings |
| 11 | Optimisation and QA | Technical artist, QA | Repetitive, technical | Profiling on target hardware, draw calls, memory, collision checks |
| 12 | Polish | Everyone | Mixed | Fixes from playtests |

Level designers own the greybox and the gameplay. Level artists take over from the greybox, assemble the space, add micro-stories, do first optimisation and sometimes lighting. Environment artists make the blockout assets, models and placement, and a material artist may own materials.

### Team size

The sources describe roles, not fixed headcounts. As a rough guide (my estimate from the role descriptions, not survey data):

| Team | One level or biome |
| --- | --- |
| AAA | Level designer 1 to 2, level artist 1 to 2, environment artists 3 to 8 plus outsourced kits and props, lighting artist 1 (often shared), technical artist 1 (shared), concept artist 1 (shared), art director and lead shared across levels |
| Mid-size or AA | 3 to 6 people, each covering two or three roles |
| Indie | 1 to 3 generalists covering everything |

About 10 to 12 distinct roles exist in a full team: art director, lead environment artist, level designer, level artist, environment artist, prop artist, material or texture artist, technical artist, lighting artist, concept artist, VFX artist, QA, plus a producer or outsourcing manager.

### What studios keep and what they outsource

- **Keep in-house:** gameplay-critical spaces, areas that change daily, and creative direction.
- **Outsource:** volume work with a locked brief and measurable criteria, such as modular kits, props and secondary levels.
- **Start with a paid test asset** before a batch.
- **The brief:** references with callouts, technical specs, scope, timeline and a definition of done.
- **Reviews:** two or three structured rounds, at blockout, first pass and polish. One owner merges all feedback into one list.
- **Done** means it performs in the engine on the target hardware, not that it looks right in a render.

## CG and VFX environment

### Stages, roles and kind of work

| # | Stage | Main roles | Kind of work | Technical requirements |
| --- | --- | --- | --- | --- |
| 1 | Brief and art department | VFX supervisor, art director, concept artist | Creative | Shot list, lens and camera data, look references |
| 2 | Survey and version zero | Layout, data wrangler | Repetitive | LIDAR or photogrammetry ingested as a first version so layout can start early |
| 3 | Layout | Layout artist | Creative | Cameras, rough sets, rough light. Shots grouped into masters and specifics |
| 4 | Modelling | Modeller | Hero creative, rest volume | SubD, displacement, render-time subdivision, naming |
| 5 | Texturing and lookdev | Texture artist, lookdev artist | Creative | UDIMs, resolution from screen coverage, turntable approval |
| 6 | Environment assembly | Environment TD or generalist | Mixed | Scattering, instancing, Houdini or geometry nodes tools, USD layers |
| 7 | Matte painting and 2.5D | Matte painter | Creative | Camera projections, mixing 2D and 3D in transition areas |
| 8 | Lighting | Lighting artist or TD | Master light creative; shot variations repetitive | Physically based light, render time budget, AOVs for compositing |
| 9 | Rendering | Render wrangler | Repetitive | Farm management, versioned outputs |
| 10 | Compositing | Compositor | Creative | Plate integration, colour pipeline (ACES or OCIO) |

The CG supervisor oversees all of it. Environment TDs (Framestore's job description is a good example) assemble models, matte paintings, textures, projections and lights, build Houdini tools, script, and match the plate photography together with compositing.

### How VFX teams save time

- Bring in survey or LIDAR data as version zero so layout starts before modelling.
- Group shots into masters that build the environment and specifics that only adjust it.
- Split work by asset type: buildings, vegetation, ground.
- Build only what the camera needs, and mix 2D and 3D where the camera can't tell.
- Reach 80% quickly, get approval, then polish.
- Texture resolution comes from the closest camera: screen coverage times 2, mapped onto 4K UDIM tiles, with hero, mid and background tiers. Procedural shading fills in where no texture is needed.

### Team size

A feature or series environment typically has a CG or environment supervisor, a lead, 1 to 3 modellers, 1 or 2 texture and lookdev artists, 1 or 2 environment TDs or generalists, a matte painter, 1 to 3 lighters, and compositors per shot count. As with games, this is a guide from role descriptions, not survey data.

## Technical requirements by step

| Step | Game (Unreal) | CG (Blender) |
| --- | --- | --- |
| Brief | Platform, frame rate, camera type, player metrics, budgets | Shots, lenses, resolution, frame count, render budget, delivery format |
| Reference | Measurable references with scale anchors | Plates or camera data, survey data when it exists |
| Layout | Grid, player path, metrics, collision | Camera first; only what is seen |
| Modelling | Budget per tier, Nanite or LODs, collision, trim sheets, texel density, custom normals | SubD, displacement, UDIMs, render-time subdivision; no LODs or collision |
| UVs and textures | One texel density, trims and tiling, memory budget | Screen coverage times 2 decides the UDIM count |
| Materials | One master material and instances, few unique materials | Per asset, approved on a turntable |
| Assembly | Instancing, PCG, World Partition streaming, HLODs | Instancing, geometry nodes scatter, holdouts, render layers |
| Lighting | Lumen, light and shadow budgets, locked exposure, frame time | Physically based, render time per frame, AOVs |
| Validation | Profiling on target hardware, collision tests | Render tests per shot, turntables, consistency across shots |
| Delivery | A level that runs at the target frame rate | Frames (EXR) with AOVs |

Shared on both: manifold geometry, consistent naming, correct normals, texel density within tolerance, and automated validation before anything is called done. Film pipelines add a canonical USD layer and deterministic builds.

## Mapping onto this pipeline

| Studio role | Who does it here | Kind | Notes |
| --- | --- | --- | --- |
| Art director | You at every gate; the Art Director agent proposes | Creative | You pick Do it, Later or Skip per note |
| Producer, lead, outsourcing manager | Manager | Coordination | Interview and plan at G0; specs as outsourcing briefs |
| Level designer, layout artist | `layout-2d` and `blockout`, approved by you at G1 and G2 | Creative | CG route lays out camera first |
| Concept artist | Magnific paint-overs and mood references | Creative support | Marked AI, never measured |
| Environment and prop artist | Modeler agents, up to 4 at once after the pilots | Hero creative, kit repetitive | Method chosen per asset and camera distance; split by asset type, as VFX teams do |
| Level artist | Unreal or Blender worker in placement phases | Mixed | Every cluster carries a one-line story |
| Material and texture artist | You | Creative | The pipeline stops at the texturing brief |
| Technical artist | Asset Tech, toolbox scanner, adapters | Technical, repetitive | Collision, LODs, export and re-import checks per asset; instruction files and scripts |
| Outsourcing and generation | Generator | Repetitive | Every generation job in a batch at once, credits logged |
| Lighting artist | Route's worker in the passes, approved by you | Creative | Gray, value, hue, then stop |
| QA | Supervisor | Repetitive | Explicit verdicts, capture-backed |
| Pipeline TD | `checkpoint`, `toolbox-scan` | Repetitive | Commits, tags, tool docs |
| Matte painter (CG) | Modeler with `fast-cg`, Magnific | Creative | `blender` route |
| Compositor (CG) | You | Creative | Out of scope |

## What v4 changed because of this research

1. **Specs read like outsourcing briefs.** Asset specs gain `done_when`: the measurable acceptance criteria for that asset.
2. **Pilot assets first.** In Stage 4 the Modeler builds one representative kit piece and one prop and gets them reviewed before the batch, the same way studios start with a test asset.
3. **One merged fix list.** The manager merges the supervisor's issues, the Art Director notes you accepted, and your notes into one list per round.
4. **Done means it runs.** On game routes the L3 gate adds a performance capture (frame time at the review cameras) next to the triangle and light stats.
5. **Camera first for CG**, build only what the camera sees, and reach 80% before polish (Hybride, Ian Hubert).
6. **Masters and specifics** for multi-shot CG projects: the plan groups shots so lighting is set once per master.
7. **Kit and trim sheet before modelling**, so dozens of pieces share a few texture sets.
8. **Rough version first.** The blockout already plays this role; the CG route treats every hero shot as a rough render at G2.

## What v5 changed because of this research

1. **Two lanes after G2.** Studios build kit pieces and props in parallel with level work, using proxies until finals arrive. The asset lane and the level lane now run at the same time ([parallel.md](parallel.md)).
2. **Volume work in parallel, creative work single.** Several Modelers split the kit and props by type; layout, pilots, lighting and art direction keep one owner.
3. **A technical artist role.** The Asset Tech takes the repetitive engine prep (collision, LODs, export, re-import check) off the Modeler.
4. **A test asset gate.** The pilots now have their own gate, K, before any batch starts.

## Sources

- [80.lv: the stages of environment art in gamedev](https://80.lv/articles/the-stages-of-environment-art-in-gamedev)
- [VG Entertainment: level design vs level art vs environment art](https://vgentertainment.com/our-news/level-environment-art-design-difference/)
- [Lemonsky Studios: game art outsourcing](https://www.lemonskystudios.com/insights/game-art-outsourcing)
- [Skyroid: in-house vs outsourced game environment art](https://skyroidwebsite.vercel.app/insights/in-house-vs-outsourced-game-environment-art)
- [ScreenSkills: VFX job roles (PDF)](https://www.screenskills.com/media/4381/vfx-cmyk-2021-master-inclusive-web.pdf)
- [Framestore: Environment TD job description](https://framestore.recruitee.com/o/environment-td-3)
- [Wētā FX: Matte painter and environment generalist](https://careers.wetafx.co.nz/jobs/1635)
- [ILM: Technical environment artist](https://karriere.disneycareers.com/stellenbeschreibung/london/technical-environment-artist-all-levels-ilm-london/391/82499511520)
- [befores & afters: building VFX environments, pro tips from Hybride](https://beforesandafters.com/2021/01/28/building-vfx-environments-get-these-pro-tips-from-hybride/)
- [geometryos: what studios expect from a shippable 3D model](https://geometryos-com.pages.dev/blog/what-studios-expect-from-a-shippable-3d-model)
- [r/vfx: industry standard texel densities](https://lr.us.psf.lt/r/vfx/comments/1fkpo3n/what_are_the_industry_standard_texel_densities/lnxl15a/?context=3)
- [80.lv: 70s office modular environment in UE5](https://80.lv/articles/setting-up-a-70s-office-modular-environment-with-unreal-engine-5)
