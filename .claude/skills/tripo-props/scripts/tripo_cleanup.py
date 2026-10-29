"""Clean up Tripo imports into prop masters at the spec's size and pivot.

Live session (the route's Blender worker), after a backup:
    exec(open(r"<repo>/.claude/skills/tripo-props/scripts/tripo_cleanup.py").read())
    cleanup({"SM_Meter_kWh": (0.14, 0.22, 0.12, "wall", True)})   # name: (W, H, D, mount, collide) from kit/<name>.md

W, H, D in metres: X = W (dims_m[0]), Y = D (dims_m[1]), Z = H (dims_m[2]). Mounts: wall = back-face centre on y=0,
floor = base centre, hang = top centre, inset = give pivot_min. The front is assumed to face -Y (Tripo's convention;
check with qa_views.py). Per prop: optional one-time turns (rot_x, rot_z, degrees, applied only before the tripo_prop
tag exists), per-axis scale to W x D x H, pivot by mount, transforms baked, merge by distance, normals recalculated,
material and textures renamed M_<base> / T_<base>_BC|M|N|R, textures capped at 1K, an optional UCX_ box child (game
routes), and the object moved to the masters collection. Re-running is safe. Meshes already on the props atlas are
skipped, since renaming would rename the atlas material and shrink its maps.
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


def _target_offset(mount, W, H, D):
    # where the bbox min corner goes, given the pivot convention; front faces -Y
    if mount == "wall":
        return Vector((-W / 2, -D, -H / 2))   # back face on y=0, centred in x/z
    if mount == "hang":
        return Vector((-W / 2, -D / 2, -H))
    return Vector((-W / 2, -D / 2, 0.0))     # floor


def _fit_mesh(obj, W, H, D, mount, turns, pivot_min):
    me = obj.data
    me.transform(obj.matrix_basis)            # bake any object transform first
    obj.matrix_basis.identity()
    if not obj.get(TAG):                      # a rerun must not turn the mesh again
        for axis, deg in turns:
            if deg:
                me.transform(Matrix.Rotation(math.radians(deg), 4, axis))
    xs, ys, zs = zip(*(v.co for v in me.vertices))
    mn = Vector((min(xs), min(ys), min(zs)))
    size = Vector((max(xs), max(ys), max(zs))) - mn
    sx, sy, sz = W / size.x, D / size.y, H / size.z
    off = Vector(pivot_min) if pivot_min else _target_offset(mount, W, H, D)
    for v in me.vertices:
        c = v.co - mn
        v.co = Vector((c.x * sx, c.y * sy, c.z * sz)) + off
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


def _ucx(obj, coll):
    name = "UCX_" + obj.name
    old = bpy.data.objects.get(name)
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


def cleanup(props, rot_x=None, rot_z=None, pivot_min=None, masters=MASTERS):
    """props: {name: (W, H, D, mount, collide)}; rot_x, rot_z: {name: degrees}; pivot_min: {name: (x, y, z)}."""
    rot_x, rot_z, pivot_min = rot_x or {}, rot_z or {}, pivot_min or {}
    coll, out = None, []
    for name, (W, H, D, mount, collide) in props.items():
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
        if coll is None:  # created only when a prop is cleaned, so a run that skips everything changes nothing
            coll = bpy.data.collections.get(masters) or bpy.data.collections.new(masters)
            if coll.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(coll)
        base = name[3:] if name.startswith("SM_") else name
        _fit_mesh(obj, W, H, D, mount, (("X", rot_x.get(name)), ("Z", rot_z.get(name))), pivot_min.get(name))
        _clean_topology(obj.data)
        obj.data.name = name
        _rename_material(obj, base)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
        obj[TAG] = True
        obj["mount"] = mount
        if collide:
            _ucx(obj, coll)
        xs, ys, zs = zip(*(v.co for v in obj.data.vertices))
        dims = tuple(round(max(a) - min(a), 3) for a in (xs, ys, zs))
        assert all(abs(a - b) < 0.002 for a, b in zip(dims, (W, D, H))), (name, dims)
        out.append(obj)
        print(f"{name}: {dims} tris={sum(len(p.vertices) - 2 for p in obj.data.polygons)} mount={mount}")
    return out
