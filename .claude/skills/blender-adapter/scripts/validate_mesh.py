"""Validate one mesh object for the modeling checklist (tested headless with bpy 5.2.3; verify in your Blender on the first project).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/validate_mesh.py").read())
    print(validate("SM_Office_Wall_Door_A", budget_tris=800))
"""
import bmesh
import bpy


def validate(name, budget_tris=None, merge_dist=0.0001):
    ob = bpy.data.objects[name]
    out = {"object": name}
    out["transforms_applied"] = (all(abs(s - 1) < 1e-6 for s in ob.scale)
                                 and all(abs(a) < 1e-6 for a in ob.rotation_euler))
    out["dimensions_m"] = [round(d, 4) for d in ob.dimensions]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out["non_manifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    out["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
    out["duplicate_verts"] = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=merge_dist)["targetmap"])
    has_subd = any(m.type == "SUBSURF" for m in ob.modifiers)
    out["ngons"] = sum(1 for f in bm.faces if len(f.verts) > 4)
    out["ngons_under_subd"] = out["ngons"] if has_subd else 0
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out["flipped_faces"] = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0)
    bm.free()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg).to_mesh()
    ev.calc_loop_triangles()
    out["tris_evaluated"] = len(ev.loop_triangles)
    ob.evaluated_get(dg).to_mesh_clear()
    out["uv_layers"] = [uv.name for uv in ob.data.uv_layers]
    out["materials"] = [s.material.name if s.material else None for s in ob.material_slots]
    checks = [out["transforms_applied"], out["non_manifold_edges"] == 0, out["duplicate_verts"] == 0,
              out["ngons_under_subd"] == 0, out["flipped_faces"] == 0, bool(out["uv_layers"])]
    if budget_tris:
        out["within_budget"] = out["tris_evaluated"] <= budget_tris
        checks.append(out["within_budget"])
    out["pass"] = all(checks)
    return out
