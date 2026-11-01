"""Self-test for frame_check.py. Plain Python, stdlib only (no Blender needed):

    python .claude/skills/blender-adapter/scripts/selftest_frame_check.py

Builds PNGs with its own encoder (every scanline filter, grey / RGB / RGBA, 8 and 16 bit), checks the reader returns the exact pixels,
then checks the verdicts on synthetic frames, including the two the thresholds must NOT fire on: a dark but real interior and a frame
that is mostly one plain wall. Ends with FRAME_CHECK SELFTEST OK, or FAILED and exit 1.
"""
import importlib.util
import os
import random
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("frame_check", os.path.join(HERE, "frame_check.py"))
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL", msg)


# ---- a small PNG encoder ------------------------------------------------------------------------------------------------------------
def _filter_row(ft, cur, prev, bpp):
    out = bytearray()
    for i, x in enumerate(cur):
        a = cur[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        if ft == 0:
            p = 0
        elif ft == 1:
            p = a
        elif ft == 2:
            p = b
        elif ft == 3:
            p = (a + b) >> 1
        else:
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - c - c)
            p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
        out.append((x - p) & 255)
    return bytes([ft]) + bytes(out)


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def encode(w, h, ctype, depth, rows, filt="mixed", interlace=0):
    """rows: h lists of w tuples of channel values in 0..(2**depth-1). filt: 0-4 or "mixed"."""
    ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype, 1)
    bd = depth // 8
    bpp = ch * bd
    raw, prev = bytearray(), bytes(w * bpp)
    for y, row in enumerate(rows):
        cur = bytearray()
        for px in row:
            for v in px:
                cur += v.to_bytes(bd, "big")
        ft = (y % 5) if filt == "mixed" else filt
        raw += _filter_row(ft, cur, prev, bpp)
        prev = bytes(cur)
    ihdr = struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, interlace)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


tmp = tempfile.mkdtemp(prefix="frame_check_")
counter = [0]


def write(name, data):
    p = os.path.join(tmp, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


def frame(w, h, fn, ctype=2, depth=8):
    """Encode fn(x, y) -> (r, g, b, a) 0..255 as a PNG of the given type and depth; return its path."""
    sc = (lambda v: v * 257) if depth == 16 else (lambda v: v)
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b, a = fn(x, y)
            px = {0: (g,), 2: (r, g, b), 4: (g, a), 6: (r, g, b, a)}[ctype]
            row.append(tuple(sc(v) for v in px))
        rows.append(row)
    counter[0] += 1
    return write(f"f{counter[0]}.png", encode(w, h, ctype, depth, rows))


# ---- 1. the reader returns the exact pixels for every filter and format -----------------------------------------------------------------
rng = random.Random(7)
for ctype in (0, 2, 4, 6):
    for depth in (8, 16):
        ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        w, h = 13, 11
        top = 2 ** depth - 1
        rows = [[tuple(rng.randint(0, top) for _ in range(ch)) for _ in range(w)] for _ in range(h)]
        for filt in (0, 1, 2, 3, 4, "mixed"):
            p = write("rt.png", encode(w, h, ctype, depth, rows, filt))
            rw, rh, has_a, px = fc.read_png(p, max_samples=10 ** 6)
            sh = 8 if depth == 16 else 0
            exp = []
            for row in rows:
                for v in row:
                    v = [c >> sh for c in v]
                    if ctype == 0:
                        v = [v[0]] * 3 + [255]
                    elif ctype == 4:
                        v = [v[0]] * 3 + [v[1]]
                    elif ctype == 2:
                        v = v + [255]
                    exp.append(tuple(v))
            check((rw, rh) == (w, h) and has_a == (ctype in (4, 6)), f"size or alpha flag wrong: type {ctype} depth {depth} filter {filt}")
            check(px == exp, f"pixels differ: type {ctype} depth {depth} filter {filt}")

# downsampling: a grid of about max_samples pixels, each equal to the source pixel at that grid position
w, h = 120, 90
src = [[(x, y, (x + y) % 256) for x in range(w)] for y in range(h)]
p = write("grid.png", encode(w, h, 2, 8, src, "mixed"))
_, _, _, px = fc.read_png(p, max_samples=500)
step = 5  # ceil(sqrt(120 * 90 / 500))
exp = [src[y][x] + (255,) for y in range(step // 2, h, step) for x in range(step // 2, w, step)]
check(px == exp, "downsampled grid differs from the source pixels")
check(len(px) <= 700, f"too many samples: {len(px)}")

# ---- 2. verdicts ----------------------------------------------------------------------------------------------------------------------
W, H = 160, 90
noise = random.Random(3)


def scene(x, y):  # an ordinary lit frame: gradient wall, a floor, a bright and a dark object
    if y > 60:
        return (90 + x // 4, 80, 70, 255)
    if 40 < x < 70 and 20 < y < 55:
        return (220, 200, 40, 255)
    if 100 < x < 130 and 25 < y < 60:
        return (30, 40, 120, 255)
    return (150 + y // 3, 150, 140 - x // 8, 255)


def dark_interior(x, y):  # night room: wall 10..40, black corner (30%), one lamp, a few lit objects
    if x < 48:
        return (2, 2, 3, 255)
    if 90 < x < 100 and 10 < y < 18:
        return (250, 235, 190, 255)
    if 110 < x < 140 and 50 < y < 85:
        return (60 + (x - 110), 48, 40, 255)
    return (12 + x // 6, 10 + y // 6, 14 + x // 8, 255)


def mostly_black_interior(x, y):  # 90% crushed, a lit table in the remaining 10%
    return (70 + x // 4, 60, 40, 255) if (60 < x < 120 and 70 < y < 85) else (3, 3, 4, 255)


def plain_wall(x, y):  # 85% one flat wall colour, furniture along one side
    if x > 136:
        return (40 + (y * 3) % 90, 60 + (x * 5) % 80, 80 + (x + y) % 50, 255)
    return (178, 170, 155, 255)


def wall_with_small_object(x, y):  # 97% flat wall, a small contrasting object
    return (40, 50, 60, 255) if (70 < x < 78 and 40 < y < 52) else (178, 170, 155, 255)


def white(x, y):
    return (255, 255, 255, 255)


def nearly_white(x, y):  # 99% white, a dark speck
    return (20, 20, 20, 255) if (x < 10 and y < 14 and (x + y) % 2 == 0) else (255, 254, 255, 255)


def black(x, y):
    return (0, 0, 0, 255)


def nearly_black(x, y):
    return (90, 80, 60, 255) if (x < 10 and y < 14 and (x + y) % 2 == 0) else (1, 1, 2, 255)


def flat_grey(x, y):  # one colour with a little noise, as a render of a camera inside a wall looks
    return (128 + noise.randint(-1, 1),) * 3 + (255,)


def flat_dark(x, y):  # dark, flat and not crushed (value 9)
    return (9, 9, 9, 255)


def transparent_mostly(x, y):  # real colours, alpha 0 on 95% of the frame
    r, g, b, _ = scene(x, y)
    return (r, g, b, 255 if (x < 20 and y < 20) else 0)


def asset_on_transparent(x, y):  # an asset covering 55% of a transparent frame
    r, g, b, _ = scene(x, y)
    return (r, g, b, 255 if x > 72 else 0)


def blank_for(fn, ctype=2, depth=8):
    return fc.check_png(frame(W, H, fn, ctype, depth))


for name, fn, want in [("lit scene", scene, False), ("dark real interior", dark_interior, False),
                       ("90% crushed interior with a lit table", mostly_black_interior, False),
                       ("85% plain wall", plain_wall, False), ("97% plain wall with a small object", wall_with_small_object, False),
                       ("white", white, True), ("99% white", nearly_white, True), ("black", black, True), ("99% black", nearly_black, True),
                       ("flat grey with noise", flat_grey, True), ("flat dark grey", flat_dark, True)]:
    for ctype, depth in ((2, 8), (6, 8), (2, 16), (0, 8)):
        rep = blank_for(fn, ctype, depth)
        check(rep["blank"] == want, f"{name} (type {ctype}, {depth} bit): blank={rep['blank']}, wanted {want}: {rep}")

rep = blank_for(transparent_mostly, 6)
check(rep["blank"] and rep["alpha_zero_fraction"] > 0.9 and any("transparent" in r for r in rep["reasons"]), f"95% zero alpha not caught: {rep}")
check(not blank_for(asset_on_transparent, 6)["blank"], "an asset on a half-transparent frame was called blank")
check(not blank_for(scene, 4)["blank"], "grey + alpha scene was called blank")
check(blank_for(transparent_mostly, 6, 16)["blank"], "16-bit zero alpha not caught")

# the numbers behind the verdicts
rep = blank_for(dark_interior)
check(0.01 < rep["mean_luma"] < 0.2 and 0.2 < rep["crushed_fraction"] < 0.5, f"dark interior numbers moved: {rep}")
rep = blank_for(plain_wall)
check(rep["std_luma"] > 0.05, f"plain wall std moved: {rep}")

# ---- 3. API and errors ----------------------------------------------------------------------------------------------------------------
try:
    fc.assert_not_blank(frame(W, H, white))
    check(False, "assert_not_blank accepted a white frame")
except fc.BlankFrame as e:
    check(isinstance(e, RuntimeError) and "all white" in str(e), f"BlankFrame message: {e}")
check(fc.assert_not_blank(frame(W, H, scene))["blank"] is False, "assert_not_blank rejected a good frame")

good = frame(W, H, scene)
good_bytes = open(good, "rb").read()
bad_inputs = {"not a png": b"hello", "interlaced": encode(4, 4, 2, 8, [[(1, 2, 3)] * 4] * 4, 0, interlace=1),
              "palette": encode(4, 4, 3, 8, [[(1,)] * 4] * 4, 0), "header only": good_bytes[:40],
              "truncated": good_bytes[:-40], "corrupt data": good_bytes[:60] + b"\x00" * 30 + good_bytes[90:]}
for name, data in bad_inputs.items():
    try:
        fc.check_png(write("bad.png", data))
        check(False, f"{name}: no PngError")
    except fc.PngError:
        pass
    except Exception as e:
        check(False, f"{name}: raised {type(e).__name__} not PngError: {e}")

# ---- 4. command line: exit 0 fine, 1 blank, 2 unreadable ------------------------------------------------------------------------------
script = os.path.join(HERE, "frame_check.py")


def run(*a):
    return subprocess.run([sys.executable, script, *a], capture_output=True, text=True)


check(run(good).returncode == 0, "cli: good frame should exit 0")
r = run(frame(W, H, white))
check(r.returncode == 1 and "BLANK" in r.stdout, f"cli: white frame should exit 1: {r.returncode} {r.stdout}")
check(run(good, write("bad.png", b"nope")).returncode == 2, "cli: unreadable file should exit 2")
check(run(os.path.join(tmp, "missing.png")).returncode == 2, "cli: missing file should exit 2")

print("FRAME_CHECK SELFTEST", "FAILED: %d" % len(fails) if fails else "OK")
sys.exit(1 if fails else 0)
