"""Look at statement pages without reading the whole PDF.

Two commands, both writing a PNG to look at:

  sheet  - the top band of a range of pages side by side, numbered, to find a note by its heading
           (sideways pages are turned upright first):
           python3 tools/pdf_pages.py sheet <pdf> 60 92 /tmp/sheet.png [--top 0.06 --bottom 0.16]

  page   - one page at reading resolution, optionally cropped and turned:
           python3 tools/pdf_pages.py page <pdf> 72 /tmp/p72.png [--dpi 120 --top 0 --bottom 1 --rotate -90]

Locate every table by the heading on its page, never by a page number from an earlier year
or another file: page numbers drift, and the same note can sit on a different page in another
edition of the same statement.

Needs poppler (pdftoppm) and Pillow: brew install poppler; pip install pillow
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def render(pdf: Path, page: int, dpi: int) -> Image.Image:
    tmp = Path(tempfile.mkdtemp()) / "p"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-f", str(page), "-l", str(page), "-singlefile",
                    "-png", str(pdf), str(tmp)], check=True)
    return Image.open(str(tmp) + ".png")


def sheet(pdf: Path, first: int, last: int, out: Path, top: float, bottom: float, cols: int = 3) -> None:
    crops = []
    for p in range(first, last + 1):
        im = render(pdf, p, 55)
        w, h = im.size
        if w > h:
            im = im.rotate(-90, expand=True)
            w, h = im.size
        crops.append((p, im.crop((0, int(h * top), w, int(h * bottom)))))
    cw = max(c.size[0] for _, c in crops)
    ch = max(c.size[1] for _, c in crops)
    rows = (len(crops) + cols - 1) // cols
    canvas = Image.new("L", (cw * cols, ch * rows), 255)
    d = ImageDraw.Draw(canvas)
    for i, (p, c) in enumerate(crops):
        x, y = (i % cols) * cw, (i // cols) * ch
        canvas.paste(c, (x, y))
        d.rectangle([x, y, x + 34, y + 14], fill=255)
        d.text((x + 3, y + 2), str(p), fill=0)
    canvas.save(out)
    print(f"{out} {canvas.size}")


def page(pdf: Path, p: int, out: Path, dpi: int, top: float, bottom: float, rotate: int) -> None:
    im = render(pdf, p, dpi)
    if rotate:
        im = im.rotate(rotate, expand=True)
    w, h = im.size
    im.crop((0, int(h * top), w, int(h * bottom))).save(out)
    print(f"{out} {im.size}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("pdf", type=Path); s.add_argument("first", type=int); s.add_argument("last", type=int)
    s.add_argument("out", type=Path); s.add_argument("--top", type=float, default=0.06); s.add_argument("--bottom", type=float, default=0.18)
    g = sub.add_parser("page")
    g.add_argument("pdf", type=Path); g.add_argument("page", type=int); g.add_argument("out", type=Path)
    g.add_argument("--dpi", type=int, default=115); g.add_argument("--top", type=float, default=0)
    g.add_argument("--bottom", type=float, default=1); g.add_argument("--rotate", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "sheet":
        sheet(a.pdf, a.first, a.last, a.out, a.top, a.bottom)
    else:
        page(a.pdf, a.page, a.out, a.dpi, a.top, a.bottom, a.rotate)


if __name__ == "__main__":
    main()
