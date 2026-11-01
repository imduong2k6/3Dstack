"""Headless self-check for asset_capture.py: a synthetic asset in a temp folder, every mode and every view written, the .blend's bytes
unchanged, a known ratio, feature and mask IoU measured, and exit 1 on a missing object.

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_asset_capture.py -- <repo> [<work_dir>]
"""
import bpy, bmesh, sys, os, json, hashlib, shutil, subprocess, tempfile, traceback, importlib.util, numpy as np

try:
    argv = sys.argv[sys.argv.index('--') + 1:]
    repo = argv[0]
    work = os.path.abspath(argv[1]) if len(argv) > 1 else tempfile.mkdtemp(prefix='asset_capture_check_')
    script = os.path.join(repo, '.claude/skills/blender-adapter/scripts/asset_capture.py')
    sp = importlib.util.spec_from_file_location('asset_capture', script)
    ac = importlib.util.module_from_spec(sp); sp.loader.exec_module(ac)

    # ---- synthetic asset: body 0.4 x 0.2 x 0.8 with a red front face (material M_front), a child Part_A, and a stray cube that must not render
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    def mat(name, rgb):
        m = bpy.data.materials.new(name); m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1)
        return m
    def box(name, size, loc, mats=()):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for f in bm.faces:
            f.material_index = 1 if f.normal.y < -0.5 else 0
        for v in bm.verts:
            v.co = (v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        for m in mats:
            me.materials.append(m)
        o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.location = loc
        return o
    grey, red = mat('M_body', (0.3, 0.3, 0.3)), mat('M_front', (0.8, 0.05, 0.05))
    body = box('SM_Test', (0.4, 0.2, 0.8), (0, 0, 0), (grey, red))
    part = box('Part_A', (0.1, 0.05, 0.2), (0.05, -0.12, 0.1), (grey,)); part.parent = body
    box('Stray', (0.3, 0.3, 0.3), (3, 0, 0), (grey,))
    asset_dir = os.path.join(work, 'asset'); os.makedirs(asset_dir, exist_ok=True)
    blend = os.path.join(asset_dir, 'asset.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    before = (sha(blend), os.listdir(asset_dir), os.path.getmtime(blend))

    # photo 400 x 700, object box 200 x 600 (ratio 1/3 against the asset's 0.5), masks for IoU
    W, H = 400, 700
    photo = os.path.join(work, 'photo.png'); ac.save(photo, np.tile(np.linspace(0.3, 0.6, W, dtype=np.float32)[None, :, None], (H, 1, 3)))
    def maskfile(name, x0, x1):
        a = np.zeros((H, W, 3), np.float32); a[50:650, x0:x1] = 1
        ac.save(os.path.join(work, name), a); return os.path.join(work, name)
    mask1, mask2 = maskfile('mask1.png', 50, 350), maskfile('mask2.png', 200, 400)

    def go(out, *args):
        p = subprocess.run([bpy.app.binary_path, '--background', '--factory-startup', blend, '--python', script, '--', '--out', out, *args],
                           capture_output=True, text=True, errors='replace')
        rep = json.load(open(os.path.join(out, 'capture_report.json'))) if os.path.exists(os.path.join(out, 'capture_report.json')) else None
        return p.returncode, rep, p.stdout[-1500:] + p.stderr[-1500:]
    near = lambda a, b, t, what: (abs(a - b) <= t) or (_ for _ in ()).throw(AssertionError(f'{what}: {a} not within {t} of {b}'))

    # ---- run 1: all modes, photo, features, mask, a close-up
    out1 = os.path.join(work, 'out1')
    code, rep, log = go(out1, '--object', 'SM_Test', '--modes', 'cycles,solid,matcap,culling', '--res', '200', '--samples', '4', '--close', 'cu:0.2,-0.1,0.4:0.5',
                        '--photo', photo, '--photo-box', '100', '50', '300', '650', '--photo-mask', mask1,
                        '--feature', 'Part_A:190,200,250,350', '--feature', 'M_front:100,50,300,650', '--feature', 'NoSuchPart:0,0,10,10')
    assert code == 0 and rep and rep['ok'], (code, log)
    views = ac.VIEWS + ['cu']
    for mode in ('cycles', 'solid', 'matcap', 'culling'):
        for v in views:
            f = os.path.join(out1, mode, v + '.png')
            assert os.path.exists(f) and os.path.getsize(f) > 100, f
            im = ac.load(f)
            assert im[..., :3].std() > 0.01, ('blank', mode, v)
    for f in ('compare_front_render', 'compare_side', 'compare_blend', 'compare_edge'):
        assert os.path.exists(os.path.join(out1, f + '.png')), f
    near(rep['extents_m'][0], 0.4, 1e-4, 'extent x'); near(rep['extents_m'][2], 0.8, 1e-4, 'extent z')   # the stray cube is left out
    near(rep['mannequin_height_m'], 1.8, 1e-3, 'mannequin height')

    # framing from the bounding box: the object fills 1 / 1.12 of the front view; the front face (red, -Y) is seen from the front, not the back
    fr = ac.load(os.path.join(out1, 'solid', 'front.png'))
    assert fr.shape[:2] == (200, 100), fr.shape
    ys, xs = np.nonzero(np.abs(fr[..., :3] - fr[0, 0, :3]).max(-1) > 0.02)
    near(ys.max() - ys.min() + 1, 200 / 1.12, 3, 'framed height'); near(xs.max() - xs.min() + 1, 200 / 1.12 / 2, 3, 'framed width')
    c = fr[100, 50, :3]; assert c[0] > 2 * c[1], ('front face should be red', c)
    c = ac.load(os.path.join(out1, 'solid', 'back.png'))[100, 50, :3]; assert abs(c[0] - c[1]) < 0.05, ('back face should be grey', c)
    # culling shows its magenta ground, matcap is grey (neutral)
    assert (lambda p: p[0] > 0.9 and p[2] > 0.9 and p[1] < 0.1)(ac.load(os.path.join(out1, 'culling', 'front.png'))[0, 0, :3])
    m = ac.load(os.path.join(out1, 'matcap', 'front.png'))[100, 50, :3]; assert abs(m[0] - m[2]) < 0.1, ('matcap should be neutral', m)

    # known ratios: photo box 200 x 600 (1/3), asset 0.4 x 0.8 (0.5) -> +50 %; 750 px per metre
    ph = rep['photo']
    near(ph['photo_w_over_h'], 1 / 3, 1e-3, 'photo ratio'); near(ph['render_w_over_h'], 0.5, 1e-4, 'render ratio'); near(ph['w_over_h_error_pct'], 50, 0.1, 'ratio error')
    near(ph['px_per_m'], 750, 0.01, 'scale')
    fa, fm, fn = ph['features']
    # Part_A projects to x 200..275, y 200..350: photo box 190..250 x 200..350 -> width +25 %, height 0, centre +17.5 px, worst edge 25 px
    near(fa['width_error_pct'], 25, 0.1, 'Part_A width'); near(fa['height_error_pct'], 0, 0.1, 'Part_A height')
    near(fa['centre_dx_px'], 17.5, 0.1, 'Part_A dx'); near(fa['centre_dy_px'], 0, 0.1, 'Part_A dy'); near(fa['largest_edge_error_px'], 25, 0.1, 'Part_A edge')
    assert 'object Part_A' in fa['part'] and 'material M_front' in fm['part'], (fa, fm)
    near(fm['width_error_pct'], 50, 0.1, 'M_front width'); near(fm['height_error_pct'], 0, 0.1, 'M_front height')   # the red face is the whole front
    assert fn['result'].startswith('not measured'), fn
    # the render's silhouette is exactly x 50..350, y 50..650 = mask1
    assert ph['iou'] > 0.98, ph['iou']

    # ---- run 2: mask only (box from the mask's own box 200..400 x 50..650, so the render is centred on it and clipped at x 400): IoU 200 / 250
    code, rep2, log = go(os.path.join(work, 'out2'), '--object', 'SM_Test', '--modes', 'solid', '--res', '200', '--photo-mask', mask2)
    assert code == 0 and rep2['ok'], (code, log)
    near(rep2['photo']['iou'], 0.8, 0.02, 'IoU'); assert 'from the mask' in rep2['photo']['box_source']
    assert not os.path.exists(os.path.join(work, 'out2', 'compare_side.png'))

    # ---- run 3: missing object, exit 1, nothing rendered
    code, rep3, log = go(os.path.join(work, 'out3'), '--object', 'NoSuchObject')
    assert code == 1 and rep3 and not rep3['ok'] and 'missing object' in rep3['error'], (code, rep3, log)
    assert not any(f.endswith('.png') for _, _, fs in os.walk(os.path.join(work, 'out3')) for f in fs)

    # ---- the source file was never saved
    assert (sha(blend), os.listdir(asset_dir), os.path.getmtime(blend)) == before, 'the .blend changed'
    print('asset_capture self-check ok: 4 modes x', len(views), 'views, ratio error', ph['w_over_h_error_pct'], '%, IoU', ph['iou'], '/', rep2['photo']['iou'], ', missing object exit', code)
    if len(argv) < 2:
        shutil.rmtree(work, ignore_errors=True)
except Exception:
    traceback.print_exc()
    print('asset_capture self-check FAILED')
    sys.exit(1)
