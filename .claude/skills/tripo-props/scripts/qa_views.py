"""Orientation QA for imported props: Workbench ortho renders (front = looking +Y from -Y, top) in a
throwaway scene QA_Props (removed afterwards), saved as <out_dir>/<name>_front.png / _top.png.
Usage in the live session (Blender MCP execute_blender_code; it needs a window, so not headless):
    exec(open(r"<repo>/.claude/skills/tripo-props/scripts/qa_views.py").read())
    qa(["SM_Handcart", ...], r"<absolute out_dir>", res=360)
Expect the prop's front in every _front.png (front faces -Y). The printed size comes from bound_box, which is
stale for objects in an excluded collection (COL_Props_Masters): measure mesh vertices for real sizes.
Leaves no objects behind unless a "QA_Cam" already exists (then the cleanup removes the wrong one).
"""
import bpy
import math
import os
from mathutils import Vector


def qa(names, out_dir, res=360):
    src = bpy.context.window.scene
    sc = bpy.data.scenes.new("QA_Props")
    try:
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.display.shading.light = "STUDIO"
        sc.display.shading.color_type = "TEXTURE"
        sc.render.resolution_x = sc.render.resolution_y = res
        sc.render.image_settings.file_format = "PNG"
        sc.render.film_transparent = False
        cam_data = bpy.data.cameras.new("QA_Cam")
        cam_data.type = "ORTHO"
        cam = bpy.data.objects.new("QA_Cam", cam_data)
        sc.collection.objects.link(cam)
        sc.camera = cam
        for n in names:
            ob = bpy.data.objects.get(n)
            if not ob:
                print("missing", n)
                continue
            sc.collection.objects.link(ob)
            ws = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            mn = Vector([min(v[i] for v in ws) for i in range(3)])
            mx = Vector([max(v[i] for v in ws) for i in range(3)])
            ctr, size = (mn + mx) / 2, mx - mn
            for view, rot, off, scale in (
                ("front", (math.radians(90), 0, 0), Vector((0, -10, 0)), max(size.x, size.z)),
                ("top", (0, 0, 0), Vector((0, 0, 10)), max(size.x, size.y)),
            ):
                cam.rotation_euler = rot
                cam.location = ctr + off
                cam_data.ortho_scale = scale * 1.15
                cam_data.clip_end = 100
                sc.render.filepath = os.path.abspath(f"{out_dir}/{n}_{view}.png")  # Blender reads a relative path from the drive root
                bpy.ops.render.render(write_still=True, scene=sc.name)
            sc.collection.objects.unlink(ob)
            print(n, "size", tuple(round(s, 3) for s in size))
    finally:
        bpy.data.objects.remove(bpy.data.objects["QA_Cam"])
        bpy.data.cameras.remove(bpy.data.cameras["QA_Cam"])
        bpy.data.scenes.remove(sc)
        bpy.context.window.scene = src
