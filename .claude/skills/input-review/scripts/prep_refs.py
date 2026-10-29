"""Prepare reference images for viewing: drop broken files, write clean downscaled copies and contact sheets.

The Read tool sends images to the API, which rejects any file it can't decode ("Could not process image").
One corrupt file wastes a call, so check and re-encode every reference before an agent looks at it.

    uv run --no-project --with pillow python -I prep_refs.py <refs_dir> [--out DIR] [--per-sheet 9]
    uv run --no-project --with pillow python -I prep_refs.py --selftest

Writes to <refs_dir>/_view/ by default: one clean JPEG per image (long edge <= 1568 px, the API's useful
maximum), sheet_NN.jpg contact sheets labelled with file names, and prep.json listing kept and rejected files.
Subfolder names are kept in the copy's name (alleys/01.jpg -> alleys__01.jpg), so PureRef groups survive.
"""
import argparse, json, math, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
LONG_EDGE = 1568
SHEET = 1568


def prep(src: Path, out: Path, per_sheet: int = 9) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    kept, rejected = [], []
    for f in sorted(p for p in src.rglob('*') if p.suffix.lower() in EXTS and out not in p.parents):
        try:
            with Image.open(f) as im:
                im.load()
                im = ImageOps.exif_transpose(im).convert('RGB')
        except Exception as e:
            rejected.append({'file': str(f.relative_to(src)), 'reason': str(e)[:120]})
            continue
        size = im.size
        im.thumbnail((LONG_EDGE, LONG_EDGE))
        name = '__'.join(f.relative_to(src).parts)
        if f.suffix.lower() != '.jpg':
            name += '.jpg'  # keep the old extension so a.png and a.jpeg don't collide
        im.save(out / name, quality=88)
        kept.append({'file': str(f.relative_to(src)), 'view': name, 'size': size})
    cols = math.ceil(math.sqrt(per_sheet))
    cell = SHEET // cols
    sheets = []
    for k in range(0, len(kept), per_sheet):
        batch = kept[k:k + per_sheet]
        rows = math.ceil(len(batch) / cols)
        sheet = Image.new('RGB', (SHEET, cell * rows), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        for i, item in enumerate(batch):
            with Image.open(out / item['view']) as im:
                im.thumbnail((cell - 8, cell - 28))
                x, y = (i % cols) * cell, (i // cols) * cell
                sheet.paste(im, (x + 4, y + 24))
            draw.text((x + 6, y + 6), item['view'], fill=(255, 220, 0))
        name = f'sheet_{k // per_sheet + 1:02d}.jpg'
        sheet.save(out / name, quality=85)
        sheets.append({'sheet': name, 'images': [b['view'] for b in batch]})
    report = {'kept': kept, 'rejected': rejected, 'sheets': sheets}
    (out / 'prep.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    return report


def selftest():
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / 'refs'
        (src / 'alleys').mkdir(parents=True)
        Image.new('RGB', (3000, 2000), (90, 120, 160)).save(src / 'alleys' / 'good.jpg')
        data = (src / 'alleys' / 'good.jpg').read_bytes()
        (src / 'bad.jpg').write_bytes(data[:len(data) // 3])  # truncated
        Image.new('RGB', (64, 64)).save(src / 'alleys' / 'good.png')
        r = prep(src, src / '_view')
        assert [k['view'] for k in r['kept']] == ['alleys__good.jpg', 'alleys__good.png.jpg'], r
        assert [b['file'] for b in r['rejected']] == ['bad.jpg'], r
        with Image.open(src / '_view' / 'alleys__good.jpg') as im:
            assert max(im.size) == LONG_EDGE, im.size
        assert (src / '_view' / 'sheet_01.jpg').exists()
    print('selftest ok')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('refs', nargs='?')
    ap.add_argument('--out')
    ap.add_argument('--per-sheet', type=int, default=9)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest(); sys.exit()
    src = Path(a.refs)
    r = prep(src, Path(a.out) if a.out else src / '_view', a.per_sheet)
    print(f"kept {len(r['kept'])}, rejected {len(r['rejected'])}, sheets {len(r['sheets'])}")
    for b in r['rejected']:
        print('  rejected', b['file'], '-', b['reason'])
