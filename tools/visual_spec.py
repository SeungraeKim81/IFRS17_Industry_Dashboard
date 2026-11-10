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

Printed figures are copied exactly as printed (brackets for negatives, "-" for nil); a list is
summed. Every one of the 30 line items in config/line_items.csv needs an entry.

  python3 tools/visual_spec.py my_spec.py config/extraction/chubb-life.json [--period 2025FY]
"""
from __future__ import annotations

import argparse
import json
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
    cur, cmp_ = (a.years.split(",") if a.years else (f"FY{year}", f"FY{year - 1}"))
    heads = d["HEADINGS"]
    units = d.get("UNITS", {})
    items = {}
    for code, (p_cur, v_cur, p_cmp, v_cmp, note, *rest) in d["ITEMS"].items():
        sign = rest[0] if rest else 1
        items[code] = {fy: {"page": p, "printed": v, "unit": units.get(p, d["UNIT"]), "sign": sign, "note": note, "heading_seen": heads[p]}
                       for fy, p, v in ((cur, p_cur, v_cur), (cmp_, p_cmp, v_cmp))}
    spec = {"company": d["COMPANY"], "company_id": d["COMPANY_ID"], "period": a.period, "source": d["SOURCE"],
            "notes": d["NOTES"], "items": items}
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"spec written: {a.out} ({len(items)} line items)")


if __name__ == "__main__":
    main()
