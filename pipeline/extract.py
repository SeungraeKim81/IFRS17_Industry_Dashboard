"""Extract the captured line items from an insurer's published statement.

An extraction spec (config/extraction/<company_id>.json) names the statement's tables and,
for every line item and year, the table, row, numeric column, unit and sign.

Tables are found by their content, not by page number. A table is described by text that
must appear on its page ("all"), text that must not ("none"), and optionally the table it
follows ("after": the first matching page after that table, e.g. the comparative-year page
of a note). A table found on no page or on more than one page stops the run, so a statement
whose layout changed is caught rather than misread. A page number in the spec ("hint") is
documentation only and is never used to choose a page.

Rows are found within the table's pages by a label pattern. Labels are matched on text with
whitespace removed and the Thai sara am (U+0E33) folded into sara aa (U+0E32), because
pdftotext inserts spaces inside Thai words and some fonts emit one vowel for the other.
Numbers are read from the unmodified line, counting columns from the right.

For a scanned statement (no text layer) the rule carries the printed figure as transcribed
from the page image ("printed", recorded as read: visual), with the page where it was read and
the heading seen on that page. A list of printed figures is summed.

A line item the statement does not disclose is a rule with "not_disclosed" (the reason) instead
of a figure; its value is None. Figures that are printed but are not line items (e.g. the total
of future cash outflows when the statement does not split acquisition cash flows from other
outflows) go in the spec's "memo" section, read the same way, and land in the result's "memo".

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


class Document:
    """The text layer of a PDF, page by page."""

    def __init__(self, pdf: Path):
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        pages = out.split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        self.lines = [[ln for ln in p.splitlines() if ln.strip()] for p in pages]
        self.norm = [_norm(p) for p in pages]

    def find_table(self, name: str, tables: dict, found: dict) -> int:
        """1-based page where the table starts."""
        if name in found:
            return found[name]
        t = tables[name]
        after = self.find_table(t["after"], tables, found) if t.get("after") else 0
        rx_all = [re.compile(_norm(x)) for x in t.get("all", [])]
        rx_none = [re.compile(_norm(x)) for x in t.get("none", [])]
        cands = [i + 1 for i, txt in enumerate(self.norm)
                 if i + 1 > after and all(r.search(txt) for r in rx_all) and not any(r.search(txt) for r in rx_none)]
        if not cands:
            raise ExtractError(f"table {name}: no page matches {t.get('all')} / not {t.get('none', [])}"
                               + (f" after p.{after}" if after else ""))
        if not after and len(cands) > 1:
            raise ExtractError(f"table {name}: {len(cands)} pages match ({cands[:8]}); add anchors to make it unique")
        found[name] = cands[0]
        return cands[0]

    def find_row(self, start: int, span: int, pattern: str, occurrence: int) -> tuple[int, str, list[str]]:
        rx = re.compile(_norm(pattern))
        n = 0
        for page in range(start, min(start + span, len(self.lines) + 1)):
            lines = self.lines[page - 1]
            for i, ln in enumerate(lines):
                if not rx.search(_norm(ln)):
                    continue
                n += 1
                if n < occurrence:
                    continue
                toks, text = NUM.findall(ln), ln
                if not toks and i + 1 < len(lines):  # label wrapped: figures on the next line
                    toks, text = NUM.findall(lines[i + 1]), ln + " / " + lines[i + 1]
                return page, text.strip(), toks
        raise ExtractError(f"row /{pattern}/ occurrence {occurrence} not found on p.{start}-{start + span - 1} ({n} found)")


def extract(spec_path: Path, pdf: Path | None) -> dict:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest() if pdf else spec["source"]["sha256"]
    if spec["source"].get("sha256") and spec["source"]["sha256"] != digest:
        raise ExtractError(f"{Path(pdf).name}: SHA-256 {digest[:12]}… does not match the registered source "
                           f"{spec['source']['sha256'][:12]}…")
    tables, found = spec.get("tables", {}), {}
    doc = None
    items, memo, errors = {}, {}, []
    codes = [("items", it["code"]) for it in load_line_items()] + [("memo", c) for c in spec.get("memo", {})]
    for section, code in codes:
        rule = spec[section].get(code)
        if rule is None:
            errors.append(f"{code}: no rule in spec")
            continue
        out = {}
        for fy, r in rule.items():
            if "not_disclosed" in r:
                out[fy] = {"value": None, "not_disclosed": r["not_disclosed"], "page": r.get("page"),
                           "heading_seen": r.get("heading_seen", "")}
                continue
            if "const" in r:
                out[fy] = {"value": float(r["const"]), "page": r.get("page"), "evidence": r["evidence"]}
                continue
            if "printed" in r:
                parts = r["printed"] if isinstance(r["printed"], list) else [r["printed"]]
                val = sum(_num(x) for x in parts) / DIVISOR[r["unit"]] * r.get("sign", 1)
                out[fy] = {"value": round(val, 9), "printed": r["printed"], "unit": r["unit"], "sign": r.get("sign", 1),
                           "page": r["page"], "note": r.get("note", ""), "read": "visual",
                           "heading_seen": r.get("heading_seen", tables.get(r.get("table"), {}).get("heading_seen", ""))}
                continue
            if pdf is None:
                errors.append(f"{code} {fy}: rule reads the text layer; pass --pdf")
                continue
            doc = doc or Document(Path(pdf))
            try:
                start = doc.find_table(r["table"], tables, found)
                page, line, toks = doc.find_row(start, tables[r["table"]].get("span", 1), r["row"], r.get("occurrence", 1))
                printed = toks[r.get("col", -1)]
            except ExtractError as e:
                errors.append(f"{code} {fy}: {e}")
                continue
            except IndexError:
                errors.append(f"{code} {fy}: column {r.get('col', -1)} missing on row /{r['row']}/")
                continue
            val = _num(printed) / DIVISOR[r["unit"]] * r.get("sign", 1)
            out[fy] = {"value": round(val, 9), "printed": printed, "unit": r["unit"], "sign": r.get("sign", 1),
                       "page": page, "table": r["table"], "note": r.get("note", tables[r["table"]].get("note", "")),
                       "line": line}
        (items if section == "items" else memo)[code] = out
    if errors:
        raise ExtractError(f"{spec['company']}: extraction failed:\n  - " + "\n  - ".join(errors))
    return {"company": spec["company"], "company_id": spec["company_id"], "period": spec["period"],
            "source": {**spec["source"], "sha256": digest}, "tables_found": found, "items": items,
            **({"memo": memo} if memo else {})}


def run(spec: str, pdf: str | None, out: str | None = None) -> Path:
    res = extract(Path(spec), Path(pdf) if pdf else None)
    dest = Path(out) if out else ROOT / "extract" / res["period"] / f"{res['company_id']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(v) for v in res["items"].values())
    pages = ", ".join(f"{k} p.{v}" for k, v in res["tables_found"].items())
    print(f"extract: {res['company']} {n} values -> {dest.relative_to(ROOT)}" + (f" (tables: {pages})" if pages else ""))
    return dest
