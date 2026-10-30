# parts/live_patches.py: fixes made in the live file after a join, replayed by integrate_parts.py after every rebuild.
# One function per fix. Find objects by name and SET values; never add to them (loc.x += 0.1 fails the repeat test).
# `patch` and `bpy` are provided by the join. lane=None runs on every join; lane="id" only when that lane was rebuilt.
# Delete a patch once the lane's own file contains the fix and has been frozen again.


@patch("p001", lane="north", note="vent 2 sits 4 cm higher than the first, as in the reference")
def _(bpy):
    ob = bpy.data.objects.get("NO_Vent_02")
    if ob:
        ob.location.z = 2.14
