# Fast CG: the Ian Hubert way and how VFX environment teams build for camera

For the Blender-only CG route, and for vistas or set extensions on any route. The goal is the most believable frame for the least modelling.

## Principles

- **Rough every shot end to end first.** Get a crude version of every shot through modelling, lighting and render, then improve only what bothers you when you watch it. This matches the pipeline's gates: the blockout is the rough version.
- **Build only what the camera sees.** Check the hero shots in `cameras.json` before modelling anything. A building seen from one side is one face plus depth where the parallax shows.
- **Mix 2D and 3D.** Full 3D near the camera, 2.5D projections in the middle distance, and a painted or photo backdrop far away. Blend the transitions so the cut doesn't show.
- **Reach 80% fast, then get approval** before polishing. The rest goes where the reviewers point.
- **Constraints help.** A fixed camera, a limited palette, or a time box keeps the work moving.
- **Observe real places closely.** Real places are full of unevenness: wobbly edges, slight bends, stains, repairs, odd additions. Hubert calls these small imperfections "warbles"; they are what makes CG read as real.
- **Be careful with downloaded packs.** Assets everyone uses make a scene look like everyone else's. Use them as filler and make the focal pieces specific to the story.

## Techniques

| Technique | How | Use for |
| --- | --- | --- |
| UV Project from View | Look through the camera (or a camera matched to the photo), select the faces, press U › Project from View, and assign the photo as the texture | Building fronts, shop windows, signs, ground patches |
| Photo-to-building | Start from a cube in the photo's perspective, project the photo, extrude window and door recesses, then add a few real 3D pieces (sills, AC units, cables) | Background buildings in minutes, e.g. a shop front in about 14 minutes |
| Kitbash | Combine existing pieces into new forms | Machinery, rooftops, greebles |
| Camera projection | Project a matte painting or plate from the shot camera onto simple geometry | Set extensions, far vistas |
| Imperfection pass | Add noise displacement, slight random rotation, bent edges, and decals | Only when the user asks for it; otherwise wear is the user's texturing work |

## Limits

- Projections only hold up near the projection camera. If the camera moves a lot, or in a game, use them only for far vistas and cards.
- Photos carry baked light. Pick photos that match the shot's light direction and keep them out of the value and hue passes: tag them `photo_proj` in the asset spec so the pass switch leaves them alone, and the supervisor checks them separately.
- Record the source and licence of every photo in `refs/index.yaml`.

## How VFX environment teams do it

- Bring in survey or LIDAR data as version zero so layout can start before modelling.
- Group shots into masters that set up the environment, and specific shots that only need changes.
- Split the work by asset type, such as buildings, vegetation and ground.
- Texture resolution comes from the closest camera: screen coverage times 2 for safety, mapped onto 4K UDIM tiles. Assets are split into hero, mid and background tiers.

## Sources

- [80.lv: world building in Blender by Ian Hubert](https://80.lv/articles/world-building-in-blender-by-ian-hubert)
- [CG Cookie: worldbuilding with ludicrous energy, ft. Ian Hubert](https://cgcookie.com/posts/worldbuilding-with-ludicrous-energy-ft-ian-hubert)
- [BlenderNation: Lazy Tutorials, custom buildings](https://www.blendernation.com/2019/11/04/create-custom-buildings-in-blender-lazy-tutorials/)
- [BlenderNation: Lazy Tutorials, CG realism with warbles](https://www.blendernation.com/2020/04/10/lazy-tutorials-cg-realism-with-warbles-in-blender/)
- [dbbd.sg: notes on Ian Hubert's methods](https://dbbd.sg/blog/?p=3279)
- [befores & afters: building VFX environments, pro tips from Hybride](https://beforesandafters.com/2021/01/28/building-vfx-environments-get-these-pro-tips-from-hybride/)
- [r/vfx: industry standard texel densities](https://lr.us.psf.lt/r/vfx/comments/1fkpo3n/what_are_the_industry_standard_texel_densities/lnxl15a/?context=3)
