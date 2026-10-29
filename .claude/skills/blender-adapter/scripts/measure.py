"""Measuring helpers for the lighting passes, so every check uses the same method (selftest_light.py tests them).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/measure.py").read())
    px = load_display(r"<review>/CAM_A.png")          # display-encoded RGB, 0..1, row 0 at the top
    m = region_mask(px.shape, box=(x0, y0, x1, y1)) & ~ellipse_mask(px.shape, (cx, cy), (rx, ry))   # mask the flare
    level(px, erode(m, 9))                             # median luminance as an sRGB level

Decode path: render against photo, decode both from display (PNG and the photo) with these helpers; render against
render, compare the EXRs. Luminance is Rec.709 on linear values, re-encoded; luma on encoded values reads saturated
colours wrong (+3.5 for a real +7.5 at L3 on the corridor pilot).
"""
import numpy as np


def decode(s):
    s = np.asarray(s, dtype=np.float64)
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def encode(v):
    v = np.clip(np.asarray(v, dtype=np.float64), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def luminance_level(px):
    """Per-pixel luminance of display-encoded RGB, as an sRGB level 0..255."""
    lin = decode(px[..., :3])
    return encode(lin @ np.array([0.2126, 0.7152, 0.0722])) * 255


def load_display(path):
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color"           # keep the stored display values; no decode on load
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)[::-1]  # Blender stores the bottom row first
    bpy.data.images.remove(img)
    return px


def region_mask(shape, box):
    m = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = True
    return m


def ellipse_mask(shape, center, radii):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return ((xx - center[0]) / radii[0]) ** 2 + ((yy - center[1]) / radii[1]) ** 2 <= 1


def erode(mask, px):
    """Shrink a mask by px pixels so thin groups don't pick up their neighbours' edges."""
    m = mask
    for _ in range(px):
        s = m.copy()
        s[1:] &= m[:-1]; s[:-1] &= m[1:]; s[:, 1:] &= m[:, :-1]; s[:, :-1] &= m[:, 1:]
        s[0] = s[-1] = False; s[:, 0] = s[:, -1] = False
        m = s
    return m


def level(px, mask):
    """Median luminance level of the masked pixels; a split group needs one mask per part, not one median."""
    if not mask.any():
        raise ValueError("empty mask")
    return float(np.median(luminance_level(px)[mask]))
