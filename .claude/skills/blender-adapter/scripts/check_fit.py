"""Headless self-check for fit_check.py: a landmark placed at its projected pixel reads 0 px, one moved 10 px reads
10 px and misses, and the overlay is written.

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_fit.py -- <repo> <out_dir>
"""
import bpy, sys, os, json
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
repo, out = sys.argv[sys.argv.index('--')+1:][:2]
exec(open(os.path.join(repo, '.claude/skills/blender-adapter/scripts/fit_check.py')).read())
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 2400, 3200
bpy.ops.mesh.primitive_cube_add(location=(0.3, 0, 1)); box = bpy.context.object; box.name = 'BOX'
bpy.ops.object.camera_add(location=(0, -6, 1.4), rotation=(1.5708, 0, 0)); cam = bpy.context.object; cam.name = 'CAM_A'
p = world_to_camera_view(sc, cam, box.matrix_world @ Vector((1, -1, 1)))
x, y = p.x * 600, (1 - p.y) * 800
photo = bpy.data.images.new('photo', 300, 400); photo.filepath_raw = os.path.join(out, 'photo.png'); photo.file_format = 'PNG'; photo.save()
spec = {'camera': 'CAM_A', 'res': [600, 800], 'photo': os.path.join(out, 'photo.png'), 'landmarks': [
    {'id': 'corner', 'object': 'BOX', 'local_m': [1, -1, 1], 'photo_px': [x, y], 'tol_px': 5},
    {'id': 'corner_off', 'object': 'BOX', 'local_m': [1, -1, 1], 'photo_px': [x + 6, y + 8], 'tol_px': 5}]}
path = os.path.join(out, 'landmarks.json'); json.dump(spec, open(path, 'w'))
rows = fit_check(path, overlay=os.path.join(out, 'fit.png'))
assert rows[0]['error_px'] < 0.1 and rows[0]['pass'], rows[0]
assert abs(rows[1]['error_px'] - 10) < 0.1 and not rows[1]['pass'], rows[1]
assert os.path.exists(os.path.join(out, 'fit.png'))
print('check_fit: pass')
