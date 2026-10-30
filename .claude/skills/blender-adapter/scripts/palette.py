"""Value and hue passes for the Blender route (tested headless with bpy 5.2.3; check_palette.py is the self-check).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/palette.py").read())
    split_group(bpy.data.materials["M_plaster_wall"], "plaster_end", [end_wall])   # optional group changes, recorded
    assign(knob, bpy.data.materials["M_metal_rust"])                              # whole object, or faces=[...] on a mesh
    unassign(mesh_or_object)                                                      # undo one assign()
    gray_on(); gray_off()  # gray pass (L1): every view layer's Material Override, then back to what was there
    skipped = apply(r"<project>/light/palette.json", mode="value")   # or "hue"; [name, reason] for each skip
    restore()              # back to the original colours, roughness and links (the gray at L2)
    restore(groups=True)   # also undo split_group, rename_group and assign: back to the original groups
    solve_hex("#9a6a60", 115)   # scale a picked colour so its luminance equals the group's L2 value

palette.json groups: {"group", "value_srgb", "hue_hex"}, optional "roughness", and for a vertical ramp in world Z
"z_range_m": [z_bottom, z_top] with "value_bottom_srgb" (value mode) and "hue_bottom_hex" (hue mode); value_srgb and
hue_hex are the top.
"""
import json

import bpy


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    h = h.lstrip("#")
    return [srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4)]


def linear_to_srgb(v):
    s = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return max(0, min(255, round(s * 255)))


def solve_hex(h, value_srgb):
    """Keep the hue and saturation of h, scaled so its Rec.709 luminance (on linear values, not luma on encoded ones)
    equals the L2 value. A starting point only: AgX moves saturated warm colours (a red solved here rendered +12.5
    levels under a 2,550 K bulb), so take the final hex from selftest_light.py's solved_hex."""
    rgb = hex_to_linear(h)
    k = srgb_to_linear(value_srgb) / (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
    if max(rgb) * k > 1:
        raise ValueError(f"{h} can't reach value {value_srgb} without clipping; pick a less saturated colour")
    return "#" + "".join(f"{linear_to_srgb(c * k):02x}" for c in rgb)


def principled(mat):
    if not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _drop_ramp(mat):
    for n in [n for n in mat.node_tree.nodes if n.name.startswith("PAL_")]:
        mat.node_tree.nodes.remove(n)


def _ramp(mat, inp, bottom, top, z_range):
    """Base Color = bottom colour at z_range[0] and below, top colour at z_range[1] and above, mixed linearly in world Z."""
    nt = mat.node_tree
    geo, sep, mr, mix = (nt.nodes.new(t) for t in ("ShaderNodeNewGeometry", "ShaderNodeSeparateXYZ", "ShaderNodeMapRange", "ShaderNodeMix"))
    geo.name, sep.name, mr.name, mix.name = "PAL_geo", "PAL_sep", "PAL_ramp", "PAL_mix"
    mr.clamp = True
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = z_range
    mix.data_type = "RGBA"
    sock = {s.identifier: s for s in list(mix.inputs) + list(mix.outputs)}
    sock["A_Color"].default_value, sock["B_Color"].default_value = (*bottom, 1.0), (*top, 1.0)
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], sock["Factor_Float"])
    nt.links.new(sock["Result_Color"], inp)


def gray_on(value=0.216):
    """Gray pass: one Principled BSDF at this linear value (0.216 is sRGB 128) as every view layer's Material Override.
    The override grays emissive meshes too, so the light comes from each emitter's light in COL_Lights (house-rules 7)."""
    sc = bpy.context.scene
    gray = bpy.data.materials.get("PAL_Gray") or bpy.data.materials.new("PAL_Gray")
    gray.use_nodes = True
    principled(gray).inputs["Base Color"].default_value = (value, value, value, 1.0)
    if "pal_orig_override" not in sc:
        sc["pal_orig_override"] = {vl.name: vl.material_override.name if vl.material_override else "" for vl in sc.view_layers}
    for vl in sc.view_layers:
        vl.material_override = gray


def gray_off():
    sc = bpy.context.scene
    orig = sc.get("pal_orig_override")
    if orig is None:
        return
    for vl in sc.view_layers:
        vl.material_override = bpy.data.materials.get(orig.get(vl.name, ""))
    del sc["pal_orig_override"]
    gray = bpy.data.materials.get("PAL_Gray")
    if gray and not gray.users:
        bpy.data.materials.remove(gray)


def _skip_reason(mat, g, node):
    if not g:
        return "group not in the palette"
    if not node:
        return "no Principled BSDF"
    if mat.get("photo_proj"):
        return "photo_proj"
    s, c, t = (node.inputs.get(k) for k in ("Emission Strength", "Emission Color", "Transmission Weight"))
    if s and c and s.default_value > 0 and (c.is_linked or max(c.default_value[:3]) > 0):
        return "emissive"
    if t and (t.is_linked or t.default_value > 0):
        return "glass"
    return None


def apply(palette_path, mode="value"):
    """Returns [name, reason] for every tagged material it left alone and every palette group no material carries."""
    groups = {g["group"]: g for g in json.load(open(palette_path))["groups"]}
    skipped, tagged = [], set()
    for mat in bpy.data.materials:
        if mat.get("material_group") is None:
            continue
        tagged.add(mat["material_group"])
        g = groups.get(mat["material_group"])
        node = principled(mat)
        why = _skip_reason(mat, g, node)
        if why:
            skipped.append([mat.name, why])
            continue
        inp = node.inputs["Base Color"]
        if "orig_base_color" not in mat:
            mat["orig_base_color"] = list(inp.default_value)
            for link in list(inp.links):  # remember textures plugged into Base Color
                mat["orig_base_link"] = link.from_node.name + "|" + link.from_socket.identifier
                mat.node_tree.links.remove(link)
        _drop_ramp(mat)                   # apply() can run again with new values
        if "roughness" in g:
            if "orig_roughness" not in mat:
                mat["orig_roughness"] = node.inputs["Roughness"].default_value
            node.inputs["Roughness"].default_value = g["roughness"]
        if mode == "value":
            v = srgb_to_linear(g["value_srgb"])
            inp.default_value = (v, v, v, 1.0)
            if "value_bottom_srgb" in g:
                b = srgb_to_linear(g["value_bottom_srgb"])
                _ramp(mat, inp, (b, b, b), (v, v, v), g["z_range_m"])
        else:
            inp.default_value = (*hex_to_linear(g["hue_hex"]), 1.0)
            if "hue_bottom_hex" in g:
                _ramp(mat, inp, hex_to_linear(g["hue_bottom_hex"]), hex_to_linear(g["hue_hex"]), g["z_range_m"])
    return skipped + [[name, "no material has this group"] for name in groups if name not in tagged]


def rename_group(mat, group):
    if "orig_material_group" not in mat:
        mat["orig_material_group"] = mat.get("material_group", "")
    mat["material_group"] = group


def assign(target, mat, faces=None):
    """Object: every slot points at mat through an object link.
    Mesh with faces: those faces take mat, added to the mesh's materials if needed. restore(groups=True) undoes both.
    Faces only on a mesh with one user: on a shared kit mesh it would change every instance and the kit source."""
    if faces is not None and target.users > 1:
        raise ValueError(f"mesh {target.name} has {target.users} users; assign by object, or make it single-user first")
    if faces is None:
        if "pal_orig_slots" not in target:
            target["pal_orig_slots"] = [[s.link, s.material.name if s.link == "OBJECT" and s.material else ""]
                                        for s in target.material_slots]
        for s in target.material_slots:
            s.link, s.material = "OBJECT", mat
        return
    if "pal_orig_face_mats" not in target:
        target["pal_orig_face_mats"] = [p.material_index for p in target.polygons]
        target["pal_orig_n_mats"] = len(target.materials)
    if mat.name not in target.materials:
        target.materials.append(mat)
    i = list(target.materials).index(mat)
    for f in faces:
        target.polygons[f].material_index = i


def unassign(target):
    """Undo assign() on one object or mesh; extra materials it added to a mesh are dropped."""
    if "pal_orig_slots" in target:
        for s, (link, name) in zip(target.material_slots, target["pal_orig_slots"]):
            s.material = None              # clear the object-level material before going back to the mesh's
            s.link = link
            if link == "OBJECT":
                s.material = bpy.data.materials.get(name)
        del target["pal_orig_slots"]
    if "pal_orig_face_mats" in target:
        for p, i in zip(target.polygons, target["pal_orig_face_mats"]):
            p.material_index = i
        while len(target.materials) > target["pal_orig_n_mats"]:
            target.materials.pop()
        del target["pal_orig_face_mats"], target["pal_orig_n_mats"]


def split_group(mat, group, objects):
    """Give objects their own copy of mat, tagged with a new material_group."""
    new = mat.copy()
    new.name = mat.name.replace(mat.get("material_group", ""), group) if mat.get("material_group") else mat.name + "_" + group
    new["material_group"], new["pal_split_of"] = group, mat.name
    for k in ("orig_base_color", "orig_base_link", "orig_roughness", "orig_material_group"):
        if k in new:
            del new[k]
    for ob in objects:
        assign(ob, new)
    return new


def restore(groups=False):
    for mat in bpy.data.materials:
        node = principled(mat)
        if not node:
            continue
        if mat.node_tree:
            _drop_ramp(mat)
        if "orig_roughness" in mat:
            node.inputs["Roughness"].default_value = mat["orig_roughness"]
            del mat["orig_roughness"]
        if "orig_base_color" not in mat:
            continue
        inp = node.inputs["Base Color"]
        inp.default_value = tuple(mat["orig_base_color"])
        if "orig_base_link" in mat:
            name, ident = mat["orig_base_link"].split("|", 1)
            src = mat.node_tree.nodes.get(name)
            out = next((s for s in src.outputs if s.identifier == ident), None) if src else None
            if out:
                mat.node_tree.links.new(out, inp)
            del mat["orig_base_link"]
        del mat["orig_base_color"]
    if not groups:
        return
    for t in list(bpy.data.objects) + list(bpy.data.meshes):
        unassign(t)
    for mat in [m for m in bpy.data.materials if "pal_split_of" in m]:
        bpy.data.materials.remove(mat)
    for mat in bpy.data.materials:
        if "orig_material_group" in mat:
            mat["material_group"] = mat["orig_material_group"]
            del mat["orig_material_group"]
