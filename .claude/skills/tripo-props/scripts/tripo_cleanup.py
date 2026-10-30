"""Clean up Tripo imports into prop masters at the spec's size and pivot.

Live session (the route's Blender worker), after a backup:
    exec(open(r"<repo>/.claude/skills/tripo-props/scripts/tripo_cleanup.py").read())
    cleanup({"SM_Meter_kWh": ((0.14, 0.12, 0.22), "wall", True)})   # name: (dims_m, mount, collide[, opts]) from kit/<name>.md

dims_m is the spec's [W, D, H] in metres, in that order: X = W, Y = D (off the wall), Z = H. Paste the spec's triple as it
is. (The old call took (W, H, D, mount, collide), so a pasted triple swapped D and H; that form now raises.) Mounts:
wall = back-face centre on y=0, floor = base centre, hang = top centre, inset = give pivot_min. The front is assumed to
face -Y (Tripo's convention; check with qa_views.py).

Scale. Uniform by default, so the generated proportions survive: one factor, taken from the governing axis (opts
"governing": "W", "D" or "H"; default the axis the spec gives the most length), is applied to all three axes. If the
factors the three axes would need differ by more than 8 % (max / min - 1), cleanup raises before it changes anything:
fix dims_m, regenerate, or pass scale="per_axis" (the old behaviour: the mesh is stretched to W x D x H).
Tubes: opts {"kind": "tube", "diameter_m": 0.045} scales uniformly so the mean cross-section equals the diameter
(default: the spec's two cross-section sizes, which must then agree within 2 mm). The tube runs along opts "axis"
("W", "D" or "H"; default the longest spec size). It raises if the cross-section is not round within 2 mm after scaling,
and warns when the length ends up more than 8 % off the spec.
Materials. materials="textured" (default) renames M_<base> / T_<base>_BC|M|N|R and caps textures at 1K.
materials="palette" is for props that stay out of the atlas: every slot becomes one flat Principled material
M_<material_group> (opts "material_group", a name or a one-item list, from the spec), shared by all props of the group
and coloured later by the lighting passes; the Tripo materials and their images are removed.

Per prop: optional one-time turns (rot_x, rot_z, degrees, applied only before the tripo_prop tag exists), pivot by
mount, transforms baked, merge by distance, normals recalculated, an optional UCX_SM_<Name>_01 box child (game routes), and the
object moved to the masters collection. Re-running is safe. Meshes already on the props atlas are skipped, since
renaming would rename the atlas material and shrink its maps.
Self-check: scripts/tests/check_tripo_cleanup.py.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

TEX_SUFFIX = {"basecolor": "BC", "metallic": "M", "normal": "N", "roughness": "R"}
MAX_TEX = 1024
MASTERS = "COL_Props_Masters"
TAG, ATLAS_TAG = "tripo_prop", "props_atlas"
AXES = {"W": 0, "X": 0, "D": 1, "Y": 1, "H": 2, "Z": 2}
OPTS = {"kind", "governing", "axis", "diameter_m", "materials", "material_group"}
UNIFORM_TOL = 0.08   # most the three axes may disagree before a uniform scale is refused
ROUND_TOL = 0.002    # tube cross-section, metres


def _target_offset(mount, W, D, H):
    # where the bbox min corner goes, given the pivot convention; front faces -Y
    if mount == "wall":
        return Vector((-W / 2, -D, -H / 2))   # back face on y=0, centred in x/z
    if mount == "hang":
        return Vector((-W / 2, -D / 2, -H))
    return Vector((-W / 2, -D / 2, 0.0))     # floor


def _unpack(name, spec):
    ok = isinstance(spec, (tuple, list)) and len(spec) in (3, 4) and isinstance(spec[0], (tuple, list)) and len(spec[0]) == 3
    if not ok:
        raise ValueError(f"{name}: expected (dims_m [W, D, H], mount, collide[, opts]); the old (W, H, D, mount, collide) form is gone")
    dims, mount, collide, *rest = spec
    opts = rest[0] if rest else {}
    if set(opts) - OPTS:
        raise ValueError(f"{name}: unknown opts {sorted(set(opts) - OPTS)}; allowed {sorted(OPTS)}")
    return tuple(float(d) for d in dims), mount, collide, opts


def _turn_matrix(obj, rot_x, rot_z):
    M = obj.matrix_basis.copy()               # the object transform is baked first
    if not obj.get(TAG):                      # a rerun must not turn the mesh again
        for axis, deg in (("X", rot_x), ("Z", rot_z)):
            if deg:
                M = Matrix.Rotation(math.radians(deg), 4, axis) @ M
    return M


def _plan(name, size, dims, opts, scale):
    """-> (scale factors, {axis: metres the result must match}). Raises before anything in the scene changes."""
    if min(size) < 1e-6:
        raise ValueError(f"{name}: the mesh is flat on one axis (size {tuple(round(v, 5) for v in size)})")
    if opts.get("kind", "box") == "tube":
        ax = AXES[opts["axis"]] if "axis" in opts else dims.index(max(dims))
        a, b = [i for i in range(3) if i != ax]
        d = opts.get("diameter_m")
        if d is None:
            if abs(dims[a] - dims[b]) > ROUND_TOL:
                raise ValueError(f"{name}: the spec's tube cross-section is {dims[a]} x {dims[b]} m; give diameter_m")
            d = (dims[a] + dims[b]) / 2
        s = d / ((size[a] + size[b]) / 2)
        if abs(size[a] - size[b]) * s > ROUND_TOL:
            raise ValueError(f"{name}: the tube would be oval, {size[a] * s:.4f} x {size[b] * s:.4f} m (limit 2 mm); regenerate it or fix the mesh")
        if abs(size[ax] * s - dims[ax]) > UNIFORM_TOL * dims[ax]:
            print(f"WARN {name}: tube length {size[ax] * s:.3f} m at diameter {d} m, the spec says {dims[ax]} m")
        return Vector((s, s, s)), {a: d, b: d}
    r = [dims[i] / size[i] for i in range(3)]
    if scale == "per_axis":
        return Vector(r), dict(enumerate(dims))
    if max(r) / min(r) - 1 > UNIFORM_TOL:
        raise ValueError(f"{name}: a uniform scale does not fit: W, D, H would need factors {r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f}, "
                         "which differ by more than 8 %. Fix dims_m, regenerate, or pass scale='per_axis'")
    g = AXES[opts["governing"]] if "governing" in opts else dims.index(max(dims))
    return Vector((r[g],) * 3), {g: dims[g]}


def _fit_mesh(obj, M, s, final, mount, pivot_min):
    me = obj.data
    me.transform(M)
    obj.matrix_basis.identity()
    mn = Vector(map(min, zip(*(v.co for v in me.vertices))))
    off = Vector(pivot_min) if pivot_min else _target_offset(mount, *final)
    for v in me.vertices:
        c = v.co - mn
        v.co = Vector((c.x * s.x, c.y * s.y, c.z * s.z)) + off
    me.update()


def _clean_topology(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


def _rename_material(obj, base):
    for slot in obj.material_slots:
        mat = slot.material
        if not mat:
            continue
        mat.name = "M_" + base
        if not mat.node_tree:
            continue
        for n in mat.node_tree.nodes:
            img = getattr(n, "image", None)
            if not img:
                continue
            key = next((k for k in TEX_SUFFIX if k in img.name.lower()), None)
            if key:
                img.name = f"T_{base}_{TEX_SUFFIX[key]}"
            if max(img.size) > MAX_TEX:
                img.scale(MAX_TEX, MAX_TEX)
                img.pack()


def _palette_material(obj, group):
    name = "M_" + group
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)   # Blender 5.2 gives it a Principled node tree already
    mat["material_group"] = group
    old = [m for m in obj.data.materials if m]
    imgs = {n.image for m in old if m.node_tree for n in m.node_tree.nodes if getattr(n, "image", None)}
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    for m in old:
        if m is not mat and m.users == 0:
            bpy.data.materials.remove(m)
    for img in imgs:
        if img.users == 0:
            bpy.data.images.remove(img)


def _ucx(obj, coll):
    name = f"UCX_{obj.name}_01"   # the pipeline's one collider name, UCX_SM_<Name>_NN
    for old in (bpy.data.objects.get(name), bpy.data.objects.get("UCX_" + obj.name)):   # the second is the name before 30 Oct 2026
        if old:
            bpy.data.objects.remove(old)
    xs, ys, zs = zip(*(v.co for v in obj.data.vertices))
    mn = Vector((min(xs), min(ys), min(zs))); mx = Vector((max(xs), max(ys), max(zs)))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=mx - mn, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(mn + mx) / 2, verts=bm.verts)
    bm.to_mesh(me); bm.free()
    col = bpy.data.objects.new(name, me)
    coll.objects.link(col)
    col.parent = obj
    col.display_type = "WIRE"
    col.hide_render = True
    col[TAG] = True


def cleanup(props, rot_x=None, rot_z=None, pivot_min=None, masters=MASTERS, scale="uniform", materials="textured"):
    """props: {name: (dims_m [W, D, H], mount, collide[, opts])}; rot_x, rot_z: {name: degrees}; pivot_min: {name: (x, y, z)}.
    scale: "uniform" or "per_axis"; materials: "textured" or "palette". opts can set kind, governing, axis, diameter_m,
    materials and material_group per prop (see the module docstring)."""
    assert scale in ("uniform", "per_axis") and materials in ("textured", "palette"), (scale, materials)
    rot_x, rot_z, pivot_min = rot_x or {}, rot_z or {}, pivot_min or {}
    todo = []
    for name, spec in props.items():   # plan every prop first, so one bad spec stops the batch before any change
        dims, mount, collide, opts = _unpack(name, spec)
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            print("skip (missing or not a mesh; a Tripo root can be an Empty):", name)
            continue
        if obj.data.get(ATLAS_TAG) is not None:
            print("skip (on the props atlas):", name)
            continue
        if mount == "inset" and name not in pivot_min:
            print("skip (inset needs pivot_min):", name)
            continue
        mats = opts.get("materials", materials)
        group = opts.get("material_group")
        group = group[0] if isinstance(group, (list, tuple)) and len(group) == 1 else group
        if mats == "palette" and not (isinstance(group, str) and group):
            raise ValueError(f"{name}: materials='palette' needs opts material_group (one name) from the spec")
        M = _turn_matrix(obj, rot_x.get(name), rot_z.get(name))
        co = [M @ v.co for v in obj.data.vertices]
        size = Vector(map(max, zip(*co))) - Vector(map(min, zip(*co)))
        s, exact = _plan(name, size, dims, opts, scale)
        todo.append((name, obj, M, s, exact, Vector(size[i] * s[i] for i in range(3)), mount, collide, mats, group))

    coll, out = None, []
    for name, obj, M, s, exact, final, mount, collide, mats, group in todo:
        if coll is None:  # created only when a prop is cleaned, so a run that skips everything changes nothing
            coll = bpy.data.collections.get(masters) or bpy.data.collections.new(masters)
            if coll.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(coll)
        base = name[3:] if name.startswith("SM_") else name
        _fit_mesh(obj, M, s, final, mount, pivot_min.get(name))
        _clean_topology(obj.data)
        obj.data.name = name
        if mats == "palette":
            _palette_material(obj, group)
        else:
            _rename_material(obj, base)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
        obj[TAG] = True
        obj["mount"] = mount
        if collide:
            _ucx(obj, coll)
        xs, ys, zs = zip(*(v.co for v in obj.data.vertices))
        dims_out = tuple(round(max(a) - min(a), 3) for a in (xs, ys, zs))
        assert all(abs(dims_out[i] - m) < 0.002 for i, m in exact.items()), (name, dims_out, exact)
        out.append(obj)
        print(f"{name}: {dims_out} scale={tuple(round(v, 4) for v in s)} tris={sum(len(p.vertices) - 2 for p in obj.data.polygons)} mount={mount}")
    return out
