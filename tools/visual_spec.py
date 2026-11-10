"""Write the extraction spec of a scanned statement from a compact Python file.

For a scanned statement every figure is read from the page image. Writing the JSON spec by
hand is error-prone, so the figures are listed in a small Python file and this script expands
it into config/extraction/<company_id>.json:

    COMPANY, COMPANY_ID, UNIT = "CHUBB Life", "chubb-life", "baht"     # or thousand_baht / million_baht
    SOURCE = {"drive_file_id": "...", "original_name": "05_FS_CHUBB_4Q2025.pdf", "sha256": "...",
              "doc_type": "Audited financial statements FY2025 (Thai)", "pages": 106, "text_layer": "no (scanned)"}
    NOTES = "How the statement is laid out, units, sign flips, what is summed."
    HEADINGS = {7: "งบกำไรขาดทุนเบ็ดเสร็จ ...", 94: "27.1 ...", 72: "18.1.2 ..."}   # heading seen on each page used
    ITEMS = {   # code: (page FY, printed FY, page comparative, printed comparative, note[, sign])
      "ra_release": (94, "264,204,810", 94, "247,124,185", "27.1"),
      "other_expense": (7, ["(364,270,285)", "(5,367,241)"], 7, ["(450,614,733)", "(11,284,067)"], "SCI opex + other finance costs"),
      "nb_pv_premium": (74, "(12,550,639,414)", 74, "(12,337,275,752)", "18.1.3 total", -1),
      ...
    }

Where the face statements and the notes use different units (face in Baht, notes in thousand
Baht), UNIT is the default and UNITS = {page: unit} sets the unit of the pages that differ.

A line item the statement does not disclose takes None for the printed figure; the note says
why. Figures printed but not line items go in MEMO = {code: (same tuple)}, e.g. nb_pv_outflows
when acquisition cash flows are not split from other outflows (see pipeline/verify_extract.py).

A quarterly spec (--period 2026Q1, 2026Q2 ...) has one column, the year to date: ITEMS entries are
(page, printed, note[, sign]), and ITEMS_3M holds the profit-or-loss lines for the three months of
the quarter in the same form (pipeline/verify_extract.py PL_3M). The spec records ytd_months.

  python3 tools/visual_spec.py my_spec.py config/extraction/quarterly/2026Q1/chubb-life.json --period 2026Q1

Printed figures are copied exactly as printed (brackets for negatives, "-" for nil); a list is
summed. Every one of the 30 line items in config/line_items.csv needs an entry.

  python3 tools/visual_spec.py my_spec.py config/extraction/chubb-life.json [--period 2025FY]
"""
from __future__ import annotations

import argparse
import json
import re
import runpy


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--period", default="2025FY")
    ap.add_argument("--years", default=None, help="current,comparative (default FY<period year>,FY<year-1>)")
    a = ap.parse_args()
    d = runpy.run_path(a.source)
    year = int(a.period[:4])
    quarter = re.fullmatch(r"\d{4}Q([1-3])", a.period)
    cur, cmp_ = (a.years.split(",") if a.years else (f"FY{year}", f"FY{year - 1}"))
    heads = d["HEADINGS"]
    units = d.get("UNITS", {})

    def rule(p, v, note, sign):
        if v is None:
            return {"page": p, "not_disclosed": note, "heading_seen": heads[p]}
        return {"page": p, "printed": v, "unit": units.get(p, d["UNIT"]), "sign": sign, "note": note,
                "heading_seen": heads[p]}

    def rules(table: dict) -> dict:
        out = {}
        for code, entry in table.items():
            if quarter:  # (page, printed, note[, sign]) for the year to date
                p, v, note, *rest = entry
                out[code] = {a.period: rule(p, v, note, rest[0] if rest else 1)}
            else:        # (page FY, printed FY, page comparative, printed comparative, note[, sign])
                p_cur, v_cur, p_cmp, v_cmp, note, *rest = entry
                sign = rest[0] if rest else 1
                out[code] = {fy: rule(p, v, note, sign) for fy, p, v in ((cur, p_cur, v_cur), (cmp_, p_cmp, v_cmp))}
        return out

    items = rules(d["ITEMS"])
    spec = {"company": d["COMPANY"], "company_id": d["COMPANY_ID"], "period": a.period, "source": d["SOURCE"],
            "notes": d["NOTES"], **({"ytd_months": 3 * int(quarter.group(1))} if quarter else {}), "items": items,
            **({"memo": rules(d["MEMO"])} if d.get("MEMO") else {}),
            **({"items_3m": rules(d["ITEMS_3M"])} if d.get("ITEMS_3M") else {})}
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"spec written: {a.out} ({len(items)} line items)")


if __name__ == "__main__":
    main()
