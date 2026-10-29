"""Before L1: test the measuring tools on a chart rendered through the project's locked view transform.
Headless on the project file, which it never saves:

    bash bin/blender-bg <work_dir>/<slug>.blend --python .claude/skills/blender-adapter/scripts/selftest_light.py -- <repo> <out_dir> [palette.json] [bulb_k]

The chart: a 0.216 gray patch, and for each colour (the palette's hue_hex groups, or three test colours) a gray patch at
its L2 value beside the colour, lit by a uniform world at the bulb's colour temperature. For each colour it reports the
drift from its gray by luminance, then solves a hex that renders on its gray through the view transform (solved_hex) and
asserts the solve lands within 5 levels. It also asserts that a masked bright light leaves a region's level unchanged,
that erode() shrinks a mask as it should, and that stats.py skips objects hidden from render. Results go to selftest.json.
"""
import bpy, sys, os, json
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
repo, out = args[:2]
pal_path = args[2] if len(args) > 2 and args[2] else None
bulb_k = float(args[3]) if len(args) > 3 else 2550.0
for f in ('palette.py', 'measure.py', 'stats.py'):
    exec(open(os.path.join(repo, '.claude/skills/blender-adapter/scripts', f)).read())
os.makedirs(out, exist_ok=True)

src = bpy.context.scene
sc = bpy.data.scenes.new('SELFTEST')
for k in ('view_transform', 'look', 'exposure', 'gamma', 'use_white_balance', 'white_balance_temperature', 'white_balance_tint'):
    if hasattr(src.view_settings, k):
        setattr(sc.view_settings, k, getattr(src.view_settings, k))
sc.display_settings.display_device = src.display_settings.display_device
sc.render.engine, sc.cycles.samples, sc.cycles.use_denoising = 'CYCLES', 32, False
sc.render.resolution_x, sc.render.resolution_y, sc.render.use_compositing = 960, 320, False
im = sc.render.image_settings
im.media_type, im.file_format, im.color_depth, im.color_management = 'IMAGE', 'PNG', '8', 'FOLLOW_SCENE'

# uniform world at the bulb's colour; a flat diffuse patch then renders albedo x world, about 0.18 for the gray
w = bpy.data.worlds.new('SELFTEST_world'); w.use_nodes = True; sc.world = w
bg = w.node_tree.nodes['Background']
bb = w.node_tree.nodes.new('ShaderNodeBlackbody'); bb.inputs['Temperature'].default_value = bulb_k
w.node_tree.links.new(bb.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 0.18 / (0.216 * 2 ** sc.view_settings.exposure)

colours = [(g['group'], g['hue_hex'], g['value_srgb']) for g in json.load(open(pal_path))['groups']
           if 'hue_hex' in g] if pal_path else [(n, solve_hex(h, v), v) for n, h, v in
                                                (('red', '#9a4a40', 115), ('teal', '#1f3d40', 50), ('olive', '#8f9a70', 150))]


def patch(name, x, y, rgb=None, emit=0.0):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, 0))
    ob = bpy.context.object; ob.name = name
    for c in ob.users_collection: c.objects.unlink(ob)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new('M_' + name); m.use_nodes = True
    p = principled(m)
    p.inputs['Base Color'].default_value = (*rgb, 1) if rgb else (0, 0, 0, 1)
    if emit:
        p.inputs['Emission Color'].default_value, p.inputs['Emission Strength'].default_value = (1, 1, 1, 1), emit
    ob.data.materials.append(m)
    return ob


cols = len(colours) + 2
gray = patch('gray_0216', 0, 0, (0.216,) * 3)
pairs = []
for i, (n, h, v) in enumerate(colours, 1):
    pairs.append((n, h, v, patch(f'v_{n}', i * 1.5, 0.75, (srgb_to_linear(v),) * 3), patch(f'h_{n}', i * 1.5, -0.75, hex_to_linear(h))))
flare_gray = patch('flare_gray', cols * 1.5, 0, (0.216,) * 3)
bulb = patch('flare_bulb', cols * 1.5, 0, emit=50.0)
bulb.scale = (0.7, 0.7, 1); bulb.location.z = 0.01           # over half the box, so an unmasked median moves
bulb.visible_diffuse = bulb.visible_glossy = bulb.visible_transmission = bulb.visible_shadow = False  # seen, lights nothing
hidden = patch('hidden_cutter', 0, 1.5, (0.5,) * 3); hidden.hide_render = True
bpy.ops.object.camera_add(location=(cols * 0.75, 0, 10)); cam = bpy.context.object
for c in cam.users_collection: c.objects.unlink(cam)
sc.collection.objects.link(cam); sc.camera = cam
cam.data.type, cam.data.ortho_scale = 'ORTHO', cols * 1.5 + 1

png = os.path.join(out, 'selftest_chart.png')
sc.render.filepath = png


def render():
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=True, scene=sc.name)
    return load_display(png)


px = render()
H, W = px.shape[:2]

def box(ob, half=0.3):
    """Pixel box around a patch centre; half is in metres."""
    pts = [world_to_camera_view(sc, cam, ob.matrix_world.translation + d) for d in
           (ob.matrix_world.to_3x3() @ Vector((-half, -half, 0)),
            ob.matrix_world.to_3x3() @ Vector((half, half, 0)))]
    xs = sorted(int(p.x * W) for p in pts); ys = sorted(int((1 - p.y) * H) for p in pts)
    return xs[0], ys[0], xs[1], ys[1]


res = {'view': {'transform': sc.view_settings.view_transform, 'look': sc.view_settings.look,
                'exposure': sc.view_settings.exposure}, 'gray_0216_level': level(px, region_mask(px.shape, box(gray))),
       'colours': [], 'failures': []}


def drifts(px):
    return [(level(px, region_mask(px.shape, box(gp))), level(px, region_mask(px.shape, box(hp)))) for *_, gp, hp in pairs]


first = drifts(px)
# solve each colour through the view transform: scale its linear RGB by the luminance ratio and render again
for _ in range(3):
    now = drifts(px)
    if all(abs(lh - lg) <= 1 for lg, lh in now):
        break
    for (n, h, v, gp, hp), (lg, lh) in zip(pairs, now):
        k = float(decode(lg / 255) / decode(lh / 255))
        inp = principled(hp.active_material).inputs['Base Color']
        inp.default_value = (*[min(1.0, c * k) for c in inp.default_value[:3]], 1)
    px = render()
for (n, h, v, gp, hp), (lg0, lh0), (lg, lh) in zip(pairs, first, drifts(px)):
    solved = '#' + ''.join(f'{linear_to_srgb(c):02x}' for c in principled(hp.active_material).inputs['Base Color'].default_value[:3])
    res['colours'].append({'group': n, 'hex': h, 'value_srgb': v, 'drift': round(lh0 - lg0, 1),
                           'solved_hex': solved, 'solved_drift': round(lh - lg, 1)})
    if abs(lh - lg) > 5:
        res['failures'].append(f'{n} {h}: could not solve within 5 levels ({lh - lg:+.1f})')

# a box over the gray patch and the bright light: masked, the level is the gray's; unmasked, the light pulls it up
fb = box(flare_gray, half=0.45)
alone = level(px, region_mask(px.shape, box(gray)))   # the same 0.216 gray, on its own
bx0, by0, bx1, by1 = box(bulb, half=0.5)
cx, cy, r = (bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) / 2 * 1.45
masked = level(px, region_mask(px.shape, fb) & ~ellipse_mask(px.shape, (cx, cy), (r, r)))
unmasked = level(px, region_mask(px.shape, fb))
res['flare'] = {'alone': alone, 'masked': masked, 'unmasked': unmasked}
if abs(masked - alone) > 1 or unmasked - alone < 3:
    res['failures'].append(f'flare mask: alone {alone:.1f}, masked {masked:.1f}, unmasked {unmasked:.1f}')

m = region_mask((100, 100), (10, 10, 50, 40))
if erode(m, 9).sum() != (40 - 18) * (30 - 18):
    res['failures'].append('erode(9) does not shrink a box by 9 px per side')

with bpy.context.temp_override(scene=sc, view_layer=sc.view_layers[0]):
    write_stats(os.path.join(out, 'selftest_stats.json'))
counted = sum(json.load(open(os.path.join(out, 'selftest_stats.json')))['objects_by_phase'].values())
expected = 3 + 2 * len(pairs)
res['stats'] = {'counted': counted, 'expected': expected}
if counted != expected:
    res['failures'].append(f'stats counted {counted} objects, {expected} render (hidden objects counted?)')

json.dump(res, open(os.path.join(out, 'selftest.json'), 'w'), indent=2)
assert not res['failures'], res['failures']
print('selftest_light: pass', json.dumps(res['colours']))
