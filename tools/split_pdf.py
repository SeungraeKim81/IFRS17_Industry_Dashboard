"""Split a statement PDF into parts small enough for the Google Drive connector.

The connector in the cloud session only transfers files up to about 5.5 MB. This script cuts
a larger PDF into consecutive page ranges, each below --max-mb, without re-compressing
anything (scanned pages keep their full quality). Each part's name carries the original page
range, so figures read from a part are still recorded against the original page numbers:

    18_FS_SE_4Q2025.pdf  ->  18_FS_SE_4Q2025__p001-064.pdf, 18_FS_SE_4Q2025__p065-130.pdf, ...

Run it on your own computer (needs Python 3 and pypdf: pip install pypdf):

    python3 tools/split_pdf.py ~/Downloads/18_FS_SE_4Q2025.pdf
    python3 tools/split_pdf.py big.pdf --max-mb 5 --out ~/Desktop/parts

Upload the parts to the same Drive folder as the original (keep the original there too).
A single page larger than the limit is written on its own and reported.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def _size(reader: PdfReader, first: int, last: int) -> int:
    w = PdfWriter()
    for i in range(first, last + 1):
        w.add_page(reader.pages[i])
    buf = io.BytesIO()
    w.write(buf)
    return buf.tell()


def split(src: Path, max_bytes: int, out_dir: Path) -> list[Path]:
    reader = PdfReader(str(src))
    n = len(reader.pages)
    width = max(3, len(str(n)))
    parts, start = [], 0
    while start < n:
        end = start
        # grow the range one page at a time while it stays under the limit
        while end + 1 < n and _size(reader, start, end + 1) <= max_bytes:
            end += 1
        w = PdfWriter()
        for i in range(start, end + 1):
            w.add_page(reader.pages[i])
        name = f"{src.stem}__p{start + 1:0{width}d}-{end + 1:0{width}d}.pdf"
        dest = out_dir / name
        with open(dest, "wb") as f:
            w.write(f)
        size = dest.stat().st_size
        flag = "  (single page above the limit)" if size > max_bytes else ""
        print(f"{name}  pages {start + 1}-{end + 1}  {size / 1e6:.1f} MB{flag}")
        parts.append(dest)
        start = end + 1
    return parts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--max-mb", type=float, default=5.0, help="largest part in MB (default 5.0)")
    ap.add_argument("--out", type=Path, help="output folder (default: next to the PDF)")
    a = ap.parse_args()
    out = a.out or a.pdf.parent
    out.mkdir(parents=True, exist_ok=True)
    if a.pdf.stat().st_size <= a.max_mb * 1e6:
        print(f"{a.pdf.name} is already {a.pdf.stat().st_size / 1e6:.1f} MB; no split needed")
        sys.exit(0)
    split(a.pdf, int(a.max_mb * 1e6), out)


if __name__ == "__main__":
    main()
