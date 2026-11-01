"""Re-checks every claim in references/blender-5-api.md on the running Blender (written against 5.2.3).

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_api_notes.py

Prints `CLAIM <id> ok|FAIL <detail>` per claim, then the count. Exit 0 when all hold, 1 when any fails (a crashed claim counts as failed).
The ids match the `id` column of the table in the reference. Each claim builds its own data and touches no file.
"""
import sys

import bmesh
import bpy
import mathutils

CLAIMS = []


def claim(cid):
    def deco(fn):
        CLAIMS.append((cid, fn))
        return fn
    return deco


def cube_mesh(name="m"):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(me)
    bm.free()
    return me


def cube_obj(name="o"):
    ob = bpy.data.objects.new(name, cube_mesh(name))
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    return ob


@claim("removed-edge-props")
def _():
    me = cube_mesh()
    gone = [a for a in ("bevel_weight", "crease") if hasattr(me.edges[0], a)]
    gone += [a for a in ("use_auto_smooth", "auto_smooth_angle", "calc_normals", "calc_normals_split", "face_maps") if hasattr(me, a)]
    bm = bmesh.new()
    bm.from_mesh(me)
    gone += [a for a in ("bevel_weight", "crease") if hasattr(bm.edges.layers, a)]
    bm.free()
    assert not gone, f"still present: {gone}"


@claim("bevel-weight-attribute")
def _():
    # Writing bevel_weight_edge as an attribute is what the Bevel modifier's Weight limit reads.
    ob = cube_obj()
    me = ob.data
    plain = ob.modifiers.new("b", "BEVEL")
    plain.limit_method = "WEIGHT"
    plain.width = 0.1
    dg = bpy.context.evaluated_depsgraph_get()
    n0 = len(ob.evaluated_get(dg).data.vertices)
    attr = me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    attr.data.foreach_set("value", [1.0] * len(me.edges))
    dg.update()
    n1 = len(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices)
    assert n0 == 8 and n1 > 8, (n0, n1)


@claim("bmesh-float-layer")
def _():
    me = cube_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.edges.layers.float.new("bevel_weight_edge")
    for e in bm.edges:
        e[lay] = 1.0
    bm.to_mesh(me)
    bm.free()
    assert "bevel_weight_edge" in me.attributes and me.attributes["bevel_weight_edge"].domain == "EDGE"


@claim("sharp-edge-lazy")
def _():
    me = cube_mesh()
    assert "sharp_edge" not in me.attributes, "attribute exists before any edge is sharp"
    me.edges[0].use_edge_sharp = True
    assert "sharp_edge" in me.attributes and me.attributes["sharp_edge"].domain == "EDGE"
    assert me.edges[0].use_edge_sharp and not me.edges[1].use_edge_sharp


@claim("sharp-face-inverse")
def _():
    me = cube_mesh()
    assert "sharp_face" in me.attributes and not me.polygons[0].use_smooth
    me.polygons[0].use_smooth = True
    assert not me.attributes["sharp_face"].data[0].value
    assert me.attributes["sharp_face"].data[1].value


@claim("corner-normals")
def _():
    me = cube_mesh()
    assert hasattr(me, "corner_normals") and len(me.corner_normals) == len(me.loops)
    assert not hasattr(me, "calc_normals_split") and not hasattr(me, "use_auto_smooth")


@claim("custom-normals-no-autosmooth")
def _():
    me = cube_mesh()
    me.normals_split_custom_set([(0.0, 0.0, 1.0)] * len(me.loops))
    assert me.has_custom_normals
    assert all(abs(n.vector.z - 1.0) < 1e-5 for n in me.corner_normals)


@claim("smooth-by-angle-operator")
def _():
    ob = cube_obj()
    ob.data = bmesh_sphere()
    bpy.ops.object.shade_smooth_by_angle(angle=0.5236)
    assert any(p.use_smooth for p in ob.data.polygons)


def bmesh_sphere():
    me = bpy.data.meshes.new("sph")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    return me


@claim("bevel-material-slot0")
def _():
    # Each cube face gets its own slot 1..6; bevelled edges make new faces. Without material= they land in slot 0.
    def run(**kw):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        for i, f in enumerate(bm.faces):
            f.material_index = i + 1
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.1, segments=1, affect="EDGES", **kw)
        out = sorted(f.material_index for f in bm.faces)
        bm.free()
        return out
    default = run()
    fixed = run(material=3)
    # 12 edge strips + 8 corner patches = 20 new faces; the 6 originals keep slots 1..6
    assert default.count(0) == 20 and sorted(set(default) - {0}) == [1, 2, 3, 4, 5, 6], f"default: {default}"
    assert fixed.count(3) == 21 and 0 not in fixed, f"material=3 did not move them: {fixed}"


@claim("bevel-material-minus-one")
def _():
    # The sibling trap: material=-1 is accepted and means "take the neighbouring face's slot".
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    for f in bm.faces:
        f.material_index = 2
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.1, segments=1, affect="EDGES", material=-1)
    got = {f.material_index for f in bm.faces}
    bm.free()
    assert got == {2}, got


@claim("rename-while-iterating")
def _():
    for o in bpy.data.objects[:]:
        bpy.data.objects.remove(o)
    for n in "abcde":
        bpy.data.objects.new(n, None)
    visits = 0
    for o in bpy.data.objects:
        visits += 1
        if visits > 40:
            break
        o.name = "z" + o.name
    assert visits != 5, "iteration visited each object exactly once; the trap did not appear"
    visits = 0
    for o in bpy.data.objects[:]:
        visits += 1
        o.name = "y" + o.name
    assert visits == 5


@claim("name-not-requested")
def _():
    a = bpy.data.objects.new("dup_name_test", None)
    b = bpy.data.objects.new("dup_name_test", None)
    assert a.name == "dup_name_test" and b.name == "dup_name_test.001" and bpy.data.objects["dup_name_test"] is a


@claim("stale-bmesh-after-mode-set")
def _():
    ob = cube_obj()
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(ob.data)
    assert len(bm.verts) == 8
    bpy.ops.object.mode_set(mode="OBJECT")
    assert not bm.is_valid, "bmesh still reports valid after leaving Edit Mode"
    try:
        len(bm.verts)
        raise AssertionError("bmesh still readable")
    except ReferenceError:
        pass
    bm2 = bmesh.new()
    bm2.from_mesh(ob.data)
    assert len(bm2.verts) == 8
    bm2.free()


@claim("update-from-editmode")
def _():
    ob = cube_obj()
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bm.verts[0].co.z += 5.0
    z_before = ob.data.vertices[0].co.z
    ob.update_from_editmode()
    z_after = ob.data.vertices[0].co.z
    bpy.ops.object.mode_set(mode="OBJECT")
    assert abs(z_after - z_before - 5.0) < 1e-5, (z_before, z_after)


@claim("matrix-world-stale")
def _():
    parent = bpy.data.objects.new("p", None)
    child = bpy.data.objects.new("c", None)
    bpy.context.scene.collection.objects.link(parent)
    bpy.context.scene.collection.objects.link(child)
    child.parent = parent
    bpy.context.view_layer.update()
    parent.location.x = 5.0
    stale = child.matrix_world.translation.x
    bpy.context.view_layer.update()
    fresh = child.matrix_world.translation.x
    assert stale == 0.0 and abs(fresh - 5.0) < 1e-6, (stale, fresh)


@claim("pack-islands-operator")
def _():
    # Props are the 5.x ones; it packs only the selected UVs of the Edit Mode mesh, so select first.
    props = set(bpy.ops.uv.pack_islands.get_rna_type().properties.keys())
    assert {"margin", "margin_method", "rotate", "rotate_method", "shape_method", "scale", "merge_overlap", "pin"} <= props, props

    def span(uv_selected):
        ob = cube_obj()
        me = ob.data
        uv = me.uv_layers.new(name="UVMap")
        for i, d in enumerate(uv.data):  # one small overlapping island
            d.uv = [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)][i % 4]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT" if uv_selected else "DESELECT")
        bpy.ops.uv.pack_islands(margin=0.01, rotate=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        xs = [d.uv.x for d in me.uv_layers[0].data]
        ys = [d.uv.y for d in me.uv_layers[0].data]
        assert min(xs) >= -1e-4 and max(xs) <= 1.0001 and min(ys) >= -1e-4 and max(ys) <= 1.0001
        return max(xs) - min(xs)
    assert span(True) > 0.5, "selected island not scaled up to fill the tile"
    assert abs(span(False) - 0.1) < 1e-3, "UVs without a UV selection moved"


@claim("vertex-colors-alias")
def _():
    # mesh.vertex_colors is still there in 5.2 but is the old byte-colour view: new colours come from color_attributes.
    me = cube_mesh()
    ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    assert ca.name == "Col" and len(me.color_attributes) == 1
    assert not hasattr(me, "sculpt_vertex_colors")


@claim("principled-socket-names")
def _():
    m = bpy.data.materials.new("pbr")
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    names = {s.name for s in p.inputs}
    new = {"Specular IOR Level", "Emission Color", "Emission Strength", "Coat Weight", "Transmission Weight", "Subsurface Weight"}
    old = {"Specular", "Emission", "Clearcoat", "Transmission", "Subsurface"}
    assert new <= names and not (old & names), (new - names, old & names)


@claim("boolean-solver-enum")
def _():
    ob = cube_obj()
    md = ob.modifiers.new("b", "BOOLEAN")
    items = {i.identifier for i in md.bl_rna.properties["solver"].enum_items}
    assert items == {"EXACT", "FLOAT", "MANIFOLD"} or ({"EXACT", "FLOAT"} <= items and "FAST" not in items), items


@claim("obj-fbx-operators")
def _():
    # hasattr() is True for any name on bpy.ops (it hands back a stub), so list the module instead
    assert {"obj_import", "obj_export"} <= set(dir(bpy.ops.wm))
    assert "obj" not in dir(bpy.ops.import_scene) and "obj" not in dir(bpy.ops.export_scene)
    assert "fbx" in dir(bpy.ops.import_scene) and "fbx" in dir(bpy.ops.export_scene)


@claim("light-shadow-prop")
def _():
    li = bpy.data.lights.new("l", "POINT")
    assert hasattr(li, "use_shadow") and not hasattr(li.cycles, "cast_shadow")


@claim("media-type-before-format")
def _():
    im = bpy.context.scene.render.image_settings
    im.media_type = "MULTI_LAYER_IMAGE"
    try:
        im.file_format = "PNG"
        accepted = True
    except TypeError:
        accepted = False
    assert not accepted, "PNG accepted while media_type is MULTI_LAYER_IMAGE"
    im.media_type = "IMAGE"
    im.file_format = "PNG"
    assert im.file_format == "PNG"


@claim("operator-context-dict")
def _():
    ob = cube_obj()
    try:
        bpy.ops.object.mode_set({"object": ob}, mode="EDIT")
        raise AssertionError("a context dict was accepted")
    except (TypeError, ValueError):
        pass
    with bpy.context.temp_override(object=ob, active_object=ob):
        assert bpy.ops.object.mode_set.poll()


def main():
    print("blender", bpy.app.version_string)
    bad = 0
    for cid, fn in CLAIMS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        try:
            fn()
            print(f"CLAIM {cid} ok")
        except Exception as e:  # a crashed claim is a failed claim
            bad += 1
            print(f"CLAIM {cid} FAIL {type(e).__name__}: {e}")
    print(f"API NOTES: {len(CLAIMS) - bad} of {len(CLAIMS)} claims hold")
    sys.stdout.flush()
    sys.exit(1 if bad else 0)


main()
