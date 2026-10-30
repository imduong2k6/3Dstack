"""Headless self-check for capture.py: a portrait size is kept, a startup compositor and an output colour override
do not spoil captures, and every setting is restored.

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_capture.py -- <repo> <out_dir>
"""
import bpy, sys, os, numpy as np
repo, out = sys.argv[sys.argv.index('--')+1:][:2]
exec(open(os.path.join(repo, '.claude/skills/blender-adapter/scripts/capture.py')).read())
sc = bpy.context.scene
bpy.ops.object.camera_add(location=(6, -6, 4), rotation=(1.1, 0, 0.785)); bpy.context.object.name = 'CAM_A'
sc.render.resolution_x, sc.render.resolution_y = 300, 400
im = sc.render.image_settings
im.media_type = 'MULTI_LAYER_IMAGE'
im.color_management = 'OVERRIDE'
sc.view_settings.view_transform, sc.view_settings.exposure = 'AgX', 5.3
sc.view_settings.use_white_balance, sc.view_settings.white_balance_temperature = True, 2550
tree = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
if hasattr(sc, 'compositing_node_group'): sc.compositing_node_group = tree
tree.nodes.new('CompositorNodeOutputFile')   # empty path, no group output, like the user's startup file
sc.render.use_compositing = True
before = (sc.camera, sc.render.use_compositing, im.media_type, im.file_format, im.color_depth, im.color_management,
          sc.view_settings.view_transform, sc.view_settings.exposure, sc.view_settings.use_white_balance, sc.display.shading.color_type, sc.cycles.samples)
for eng in ('CYCLES', 'BLENDER_WORKBENCH'):
    capture_set(os.path.join(out, eng), ['CAM_A'], engine=eng, samples=4, lint=False)   # the lint gate has its own test (selftest_adapter.py)
    img = bpy.data.images.load(os.path.join(out, eng, 'CAM_A.png'))
    px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
    assert tuple(img.size) == (300, 400), img.size
    assert 0.01 < px.mean() < 0.97, (eng, 'blank or blown out', px.mean())
    after = (sc.camera, sc.render.use_compositing, im.media_type, im.file_format, im.color_depth, im.color_management,
             sc.view_settings.view_transform, sc.view_settings.exposure, sc.view_settings.use_white_balance, sc.display.shading.color_type, sc.cycles.samples)
    assert after == before, (eng, before, after)
    print('capture self-check ok', eng, round(float(px.mean()), 3))
