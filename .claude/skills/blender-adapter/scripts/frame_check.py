"""Blank-frame check for review captures: reads a PNG and says whether it is a frame a reviewer can judge.

Stdlib only (zlib, struct), so it runs the same in Blender's Python, Unreal's Python and a plain shell, where numpy and PIL may be
missing. The capture scripts call it right after writing a PNG (blender-adapter/scripts/capture.py, unreal-adapter/scripts/capture.py);
it also works on its own:

    python frame_check.py <a.png> [<b.png> ...] [--json]        exit 0 all fine, 1 a blank frame, 2 a file it could not read

    import frame_check
    frame_check.assert_not_blank("CAM_A.png")     # raises BlankFrame (a RuntimeError) with the reason
    report = frame_check.check_png("CAM_A.png")   # dict: mean_luma, std_luma, clipped_fraction, crushed_fraction, alpha_zero_fraction, ...

A frame is blank when ANY of these holds (THRESHOLDS below; start values chosen so a dark real interior and a frame that is mostly
one plain wall both pass, see selftest_frame_check.py):
  uniform    every colour channel has a standard deviation under 0.01 (0-1 scale): one flat colour, or a camera inside a wall
  clipped    98% or more of the pixels have luma >= 250 (all white)
  crushed    98% or more of the pixels have luma <= 5 (all black)
  no alpha   90% or more of the pixels have alpha 0 (an image viewer shows such a PNG as transparent or black)
Luma is Rec.709 weights on the encoded values, 0-255 (16-bit channels use their high byte). Alpha is judged only when the PNG has one.
A render with a transparent film that leaves under 10% of the frame covered by the subject reads as "no alpha": raise alpha_zero_fraction.

Reads grey, grey+alpha, RGB and RGBA PNGs at 8 or 16 bits with all five scanline filters. Not read (PngError): palette, bit depths under
8, interlaced. Every row has to be unfiltered because a filter refers to the row above, so decoding costs seconds at 1080p when the
writer used Paeth; only a regular grid of at most max_samples pixels is then analysed.
"""
import itertools
import math
import struct
import sys
import zlib

THRESHOLDS = {
    "max_samples": 250000,
    "clip_luma": 250,
    "crush_luma": 5,
    "all_fraction": 0.98,
    "uniform_std": 0.01,
    "alpha_zero_fraction": 0.9,
}


class PngError(ValueError):
    """The file is not a PNG this reader handles."""


class BlankFrame(RuntimeError):
    """The frame is blank; str() says why."""


_M255 = (255).__and__


def _unfilter(raw, h, stride, bpp):
    """Yield each reconstructed scanline (a bytearray, reused as the next row's 'above') from the decompressed IDAT stream."""
    prev = bytearray(stride)
    m7 = int.from_bytes(b"\x7f" * stride, "big")
    m8 = int.from_bytes(b"\x80" * stride, "big")
    pos = 0
    for _ in range(h):
        ft = raw[pos]
        cur = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += stride + 1
        if ft == 0:
            pass
        elif ft == 1:  # Sub: running sum along each channel
            for c in range(bpp):
                cur[c::bpp] = bytes(map(_M255, itertools.accumulate(cur[c::bpp])))
        elif ft == 2:  # Up: bytewise add of the row above, done on one big integer without carries between bytes
            a, b = int.from_bytes(cur, "big"), int.from_bytes(prev, "big")
            cur = bytearray((((a & m7) + (b & m7)) ^ ((a ^ b) & m8)).to_bytes(stride, "big"))
        elif ft == 3:  # Average
            for i in range(min(bpp, stride)):
                cur[i] = (cur[i] + (prev[i] >> 1)) & 255
            for i in range(bpp, stride):
                cur[i] = (cur[i] + ((cur[i - bpp] + prev[i]) >> 1)) & 255
        elif ft == 4:  # Paeth
            for i in range(min(bpp, stride)):
                cur[i] = (cur[i] + prev[i]) & 255
            for i in range(bpp, stride):
                a, b, c = cur[i - bpp], prev[i], prev[i - bpp]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - c - c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        else:
            raise PngError(f"unknown scanline filter {ft}")
        yield cur
        prev = cur


def read_png(path, max_samples=THRESHOLDS["max_samples"]):
    """Return (width, height, has_alpha, pixels): pixels is a list of (r, g, b, a) 0-255 tuples on a regular grid of about max_samples.
    Grey is returned as r=g=b; a is 255 when the PNG has no alpha."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PngError("not a PNG file")
    pos, idat, ihdr = 8, [], None
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if ihdr is None or not idat:
        raise PngError("no IHDR or no image data")
    w, h, depth, ctype, _, _, interlace = ihdr
    if interlace:
        raise PngError("interlaced PNG not supported")
    if depth not in (8, 16) or ctype not in (0, 2, 4, 6):
        raise PngError(f"PNG colour type {ctype} at {depth} bits not supported (need grey, RGB, with or without alpha, at 8 or 16 bits)")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    bd = depth // 8
    bpp, stride = channels * bd, w * channels * bd
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise PngError(f"image data corrupt: {e}")
    if len(raw) < h * (stride + 1):
        raise PngError("image data truncated")
    step = max(1, math.ceil(math.sqrt(w * h / float(max_samples))))
    x0 = step // 2
    ys = set(range(step // 2, h, step))
    has_alpha = ctype in (4, 6)
    a_idx = channels - 1
    rgb_idx = (0, 1, 2) if channels >= 3 else (0, 0, 0)
    px = []
    for y, row in enumerate(_unfilter(raw, h, stride, bpp)):
        if y not in ys:
            continue
        # byte offset of a channel's high byte, then every step-th pixel across the row
        r, g, b = (row[x0 * bpp + c * bd::step * bpp] for c in rgb_idx)
        a = row[x0 * bpp + a_idx * bd::step * bpp] if has_alpha else b"\xff" * len(r)
        px.extend(zip(r, g, b, a))
    return w, h, has_alpha, px


def analyse(pixels, has_alpha, thresholds=None):
    """Statistics and verdict for a list of (r, g, b, a) samples; see the module text for the rules."""
    t = dict(THRESHOLDS, **(thresholds or {}))
    n = len(pixels)
    if not n:
        raise PngError("no pixels sampled")
    luma = [(54 * r + 183 * g + 19 * b) >> 8 for r, g, b, _ in pixels]
    mean = sum(luma) / n
    std = math.sqrt(max(0.0, sum(v * v for v in luma) / n - mean * mean)) / 255.0
    chan_std = []
    for c in range(3):
        s1 = sum(p[c] for p in pixels)
        s2 = sum(p[c] * p[c] for p in pixels)
        m = s1 / n
        chan_std.append(math.sqrt(max(0.0, s2 / n - m * m)) / 255.0)
    clipped = sum(1 for v in luma if v >= t["clip_luma"]) / n
    crushed = sum(1 for v in luma if v <= t["crush_luma"]) / n
    zero_a = sum(1 for p in pixels if p[3] == 0) / n if has_alpha else None
    reasons = []
    if max(chan_std) < t["uniform_std"]:
        reasons.append(f"uniform: one flat colour (channel std {max(chan_std):.4f}, limit {t['uniform_std']})")
    if clipped >= t["all_fraction"]:
        reasons.append(f"all white: {clipped:.1%} of pixels clipped")
    if crushed >= t["all_fraction"]:
        reasons.append(f"all black: {crushed:.1%} of pixels crushed")
    if zero_a is not None and zero_a >= t["alpha_zero_fraction"]:
        reasons.append(f"transparent: {zero_a:.1%} of pixels have alpha 0")
    return {"samples": n, "mean_luma": round(mean / 255.0, 4), "std_luma": round(std, 4), "max_channel_std": round(max(chan_std), 4),
            "clipped_fraction": round(clipped, 4), "crushed_fraction": round(crushed, 4),
            "alpha_zero_fraction": None if zero_a is None else round(zero_a, 4), "blank": bool(reasons), "reasons": reasons}


def check_png(path, thresholds=None):
    """Read one PNG and return analyse() plus path, width and height. Raises PngError when the file cannot be read."""
    t = dict(THRESHOLDS, **(thresholds or {}))
    w, h, has_alpha, px = read_png(path, t["max_samples"])
    rep = analyse(px, has_alpha, t)
    rep.update(path=str(path), width=w, height=h)
    return rep


def assert_not_blank(path, thresholds=None):
    """Return the report for a frame that is fine; raise BlankFrame (a RuntimeError) naming the file and the reasons for a blank one."""
    rep = check_png(path, thresholds)
    if rep["blank"]:
        raise BlankFrame(f"blank frame {rep['path']}: {'; '.join(rep['reasons'])} (mean luma {rep['mean_luma']}, std {rep['std_luma']})")
    return rep


def main(argv):
    import json
    as_json = "--json" in argv
    files = [a for a in argv if a != "--json"]
    if not files:
        print(__doc__.split("\n\n")[0])
        return 2
    code, out = 0, []
    for f in files:
        try:
            rep = check_png(f)
        except (PngError, OSError) as e:
            rep = {"path": f, "error": str(e)}
            code = max(code, 2)
        else:
            if rep["blank"]:
                code = max(code, 1)
        out.append(rep)
        if not as_json:
            if "error" in rep:
                print(f"UNREADABLE {f}: {rep['error']}")
            else:
                print(f"{'BLANK' if rep['blank'] else 'ok'} {f}: mean {rep['mean_luma']} std {rep['std_luma']} clipped {rep['clipped_fraction']} "
                      f"crushed {rep['crushed_fraction']} alpha0 {rep['alpha_zero_fraction']}" + "".join(f"\n  - {r}" for r in rep["reasons"]))
    if as_json:
        print(json.dumps(out, indent=1))
    return code


if __name__ == "__main__":
    # Blender passes its own arguments before "--"; a plain shell has none.
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
