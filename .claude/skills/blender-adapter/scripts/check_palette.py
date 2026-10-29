"""Headless self-check for palette.py: value, ramp and roughness apply and restore; split_group, rename_group and
assign (object and faces) undo with restore(groups=True); face assigns on shared meshes are refused; solve_hex.

    bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_palette.py -- <repo> <out_dir>
"""
import bpy, sys, os, json
repo, out = sys.argv[sys.argv.index('--')+1:][:2]
exec(open(os.path.join(repo, '.claude/skills/blender-adapter/scripts/palette.py')).read())
os.makedirs(out, exist_ok=True)


def mat(name, group):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m['material_group'] = group
    p = principled(m)
    p.inputs['Base Color'].default_value = (0.2158, 0.2158, 0.2158, 1)
    p.inputs['Roughness'].default_value = 0.5
    return m


wall, cab, rust, grey = mat('M_wall', 'wall'), mat('M_cable', 'cables'), mat('M_rust', 'rust'), mat('M_grey', 'grey')
obs = []
for i in range(3):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 0, 1))
    ob = bpy.context.object
    ob.data.materials.append(wall)
    obs.append(ob)
box = obs[2].data
pal = os.path.join(out, 'palette.json')
json.dump({'groups': [{'group': 'wall_end', 'value_srgb': 127, 'value_bottom_srgb': 73, 'z_range_m': [0.6, 1.9]},
                      {'group': 'wall_near', 'value_srgb': 92}, {'group': 'cables', 'value_srgb': 50, 'roughness': 0.75},
                      {'group': 'rust', 'value_srgb': 60}, {'group': 'grey', 'value_srgb': 125}]}, open(pal, 'w'))

end = split_group(wall, 'wall_end', [obs[0]])
rename_group(wall, 'wall_near')
assign(obs[1], rust)
assign(box, grey, faces=[0, 1])
apply(pal, mode='value')
inp = principled(end).inputs['Base Color']
assert inp.is_linked
mix = {s.identifier: s for s in end.node_tree.nodes['PAL_mix'].inputs}
assert inp.links[0].from_node.name == 'PAL_mix', 'ramp not wired'
assert abs(mix['A_Color'].default_value[0] - srgb_to_linear(73)) < 1e-6 and abs(mix['B_Color'].default_value[0] - srgb_to_linear(127)) < 1e-6
assert abs(principled(wall).inputs['Base Color'].default_value[0] - srgb_to_linear(92)) < 1e-6
assert abs(principled(cab).inputs['Roughness'].default_value - 0.75) < 1e-6
assert obs[0].material_slots[0].material == end and obs[1].material_slots[0].material == rust
assert [p.material_index for p in box.polygons][:3] == [1, 1, 0] and box.materials[1] == grey
apply(pal, mode='value')                                  # a second apply keeps one ramp
assert sum(n.name.startswith('PAL_') for n in end.node_tree.nodes) == 4

bpy.ops.mesh.primitive_cube_add(location=(9, 0, 1))      # unassign() undoes one face assign and drops the added slot
solo = bpy.context.object.data
solo.materials.append(wall)
assign(solo, grey, faces=[2])
unassign(solo)
assert len(solo.materials) == 1 and all(p.material_index == 0 for p in solo.polygons) and 'pal_orig_face_mats' not in solo

bpy.ops.object.duplicate(linked=True)                    # a face assign on a shared mesh is refused
shared = bpy.context.object.data
try:
    assign(shared, grey, faces=[0])
    raise AssertionError('face assign on a shared mesh was allowed')
except ValueError:
    pass
assert len(shared.materials) == 1

for h, v in (('#9a6a60', 115), ('#253536', 50), ('#919986', 150)):   # solve_hex hits the value by luminance
    lin = hex_to_linear(solve_hex(h, v))
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    assert abs(linear_to_srgb(y) - v) <= 1, (h, v, linear_to_srgb(y))
try:
    solve_hex('#ff0000', 200)
    raise AssertionError('clipping hex was allowed')
except ValueError:
    pass

hpal = os.path.join(out, 'palette_hue.json')             # hue mode: hue_hex on top, hue_bottom_hex at the bottom of the ramp
json.dump({'groups': [{'group': 'wall_end', 'value_srgb': 127, 'hue_hex': '#807f78', 'hue_bottom_hex': '#4f4843', 'z_range_m': [0.6, 1.9]},
                      {'group': 'wall_near', 'value_srgb': 92, 'hue_hex': '#65595a'}]}, open(hpal, 'w'))
apply(hpal, mode='hue')
mix = {s.identifier: s for s in end.node_tree.nodes['PAL_mix'].inputs}
assert all(abs(a - b) < 1e-6 for a, b in zip(mix['A_Color'].default_value[:3], hex_to_linear('#4f4843')))
assert all(abs(a - b) < 1e-6 for a, b in zip(mix['B_Color'].default_value[:3], hex_to_linear('#807f78')))
assert all(abs(a - b) < 1e-6 for a, b in zip(principled(wall).inputs['Base Color'].default_value[:3], hex_to_linear('#65595a')))
assert sum(n.name.startswith('PAL_') for n in end.node_tree.nodes) == 4

restore()                                                 # values back, groups kept
assert all(abs(principled(m).inputs['Base Color'].default_value[0] - 0.2158) < 1e-6 for m in (wall, cab, rust, grey, end))
assert not principled(end).inputs['Base Color'].is_linked and not any(n.name.startswith('PAL_') for n in end.node_tree.nodes)
assert abs(principled(cab).inputs['Roughness'].default_value - 0.5) < 1e-6
assert end.name in bpy.data.materials and wall['material_group'] == 'wall_near'

restore(groups=True)                                      # back to the original groups
assert 'M_wall_end' not in bpy.data.materials and wall['material_group'] == 'wall'
assert all(o.material_slots[0].link == 'DATA' and o.material_slots[0].material == wall for o in obs)
assert len(box.materials) == 1 and all(p.material_index == 0 for p in box.polygons)
assert not any(k.startswith(('orig_', 'pal_')) for m in bpy.data.materials for k in m.keys())
print('check_palette: pass')
