"""Extract the captured line items from an insurer's published statement (PDF with a text layer).

An extraction spec (config/extraction/<company_id>.json) says, for every line item and year,
which page, which row (a label pattern), which numeric column, which unit and which sign.
For a scanned statement (no text layer) the spec carries the printed figure as transcribed
from the page image instead of a row pattern ("printed", marked read: visual); a list of
printed figures is summed (e.g. operating expenses + other finance costs).
The extractor reads the PDF's text layer, finds each row, records what was printed and
converts it to THB million. Every value keeps its provenance, so a reviewer can go straight
to the page.

Row labels are matched on text with whitespace removed and the Thai sara am (U+0E33)
folded into sara aa (U+0E32): several statements' fonts emit one for the other, and
pdftotext inserts spaces inside Thai words. Numbers are read from the unmodified line.

  python -m pipeline extract --spec config/extraction/samsung-life.json --pdf <statement.pdf>
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from .common import ROOT, load_line_items

NUM = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?|(?<=\s)-(?=\s|$)")
DIVISOR = {"baht": 1_000_000, "thousand_baht": 1_000, "million_baht": 1}


class ExtractError(Exception):
    pass


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.replace("ำ", "า"))


def _num(tok: str) -> float:
    if tok == "-":
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def page_lines(pdf: Path, page: int, _cache: dict = {}) -> list[str]:
    key = (str(pdf), page)
    if key not in _cache:
        out = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
                             capture_output=True, text=True).stdout
        _cache[key] = [ln for ln in out.splitlines() if ln.strip()]
    return _cache[key]


def find_row(pdf: Path, page: int, pattern: str, occurrence: int = 1) -> tuple[str, list[str]]:
    """Return (printed line, numeric tokens) for the n-th line on the page matching the pattern.
    If the matching line carries no numbers (a label wrapped onto the next line), the numbers
    are taken from the following line."""
    rx = re.compile(_norm(pattern))
    lines = page_lines(pdf, page)
    hits = [i for i, ln in enumerate(lines) if rx.search(_norm(ln))]
    if len(hits) < occurrence:
        raise ExtractError(f"p.{page}: row /{pattern}/ occurrence {occurrence} not found ({len(hits)} found)")
    i = hits[occurrence - 1]
    toks = NUM.findall(lines[i][max(len(lines[i]) - len(lines[i].lstrip()), 0):])
    # Drop digits that belong to the label (e.g. a note number) by keeping only the trailing run of tokens.
    line_text = lines[i]
    if not toks and i + 1 < len(lines):
        line_text = lines[i] + " / " + lines[i + 1]
        toks = NUM.findall(lines[i + 1])
    return line_text.strip(), toks


def extract(spec_path: Path, pdf: Path) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest() if pdf else spec["source"]["sha256"]
    if spec["source"].get("sha256") and spec["source"]["sha256"] != digest:
        raise ExtractError(f"{pdf.name}: SHA-256 {digest[:12]}… does not match the registered source "
                           f"{spec['source']['sha256'][:12]}…")
    codes = [it["code"] for it in load_line_items()]
    items, errors = {}, []
    for code in codes:
        rule = spec["items"].get(code)
        if rule is None:
            errors.append(f"{code}: no rule in spec")
            continue
        out = {}
        for fy, r in rule.items():
            if "const" in r:
                out[fy] = {"value": float(r["const"]), "page": r.get("page"), "evidence": r["evidence"]}
                continue
            if "printed" in r:
                # Transcribed from the page image (scanned statements): one printed figure, or a list summed.
                parts = r["printed"] if isinstance(r["printed"], list) else [r["printed"]]
                val = sum(_num(x) for x in parts) / DIVISOR[r["unit"]] * r.get("sign", 1)
                out[fy] = {"value": round(val, 9), "printed": r["printed"], "unit": r["unit"], "sign": r.get("sign", 1),
                           "page": r["page"], "note": r.get("note", ""), "read": "visual"}
                continue
            try:
                line, toks = find_row(pdf, r["page"], r["row"], r.get("occurrence", 1))
                col = r.get("col", -1)
                printed = toks[col]
            except (ExtractError, IndexError) as e:
                errors.append(f"{code} {fy}: {e if isinstance(e, ExtractError) else 'column ' + str(r.get('col', -1)) + ' missing'}")
                continue
            val = _num(printed) / DIVISOR[r["unit"]] * r.get("sign", 1)
            out[fy] = {"value": round(val, 9), "printed": printed, "unit": r["unit"], "sign": r.get("sign", 1),
                       "page": r["page"], "note": r.get("note", ""), "line": line}
        items[code] = out
    if errors:
        raise ExtractError(f"{spec['company']}: extraction failed:\n  - " + "\n  - ".join(errors))
    return {"company": spec["company"], "company_id": spec["company_id"], "period": spec["period"],
            "source": {**spec["source"], "sha256": digest}, "items": items}


def run(spec: str, pdf: str | None, out: str | None = None) -> Path:
    res = extract(Path(spec), Path(pdf) if pdf else None)
    dest = Path(out) if out else ROOT / "extract" / res["period"] / f"{res['company_id']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(v) for v in res["items"].values())
    print(f"extract: {res['company']} {n} values -> {dest.relative_to(ROOT)}")
    return dest
