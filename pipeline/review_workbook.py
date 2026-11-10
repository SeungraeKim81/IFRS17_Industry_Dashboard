"""Write the extractions of a period as a workbook in the capture-workbook layout.

One sheet per extracted insurer, laid out like the pilot capture workbook (row 4 header,
rows 5-34 line items with FY / comparative / status / source), so the existing ingest step
reads it unchanged. A "Check" sheet lists, for every value, the pilot figure and the
difference, and a "Reconciliation" sheet the six identities per year.

  python -m pipeline review-workbook --period 2025FY
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

from .common import ROOT, load_line_items
from .verify_extract import compare_pilot, load, reconcile

BOLD = Font(bold=True)
FLAG = PatternFill("solid", fgColor="FCE4D6")


def _source_text(rec: dict) -> str:
    if "not_disclosed" in rec:
        return f"file p.{rec.get('page')} not disclosed: {rec['not_disclosed']}"
    if "evidence" in rec:
        return f"p.{rec.get('page')} {rec['evidence']}"
    how = "read from page image" if rec.get("read") == "visual" else "text layer"
    return f"file p.{rec['page']} {rec.get('note', '')} printed {rec['printed']} ({rec['unit']}, {how})".strip()


def build(period: str, out: Path | None = None) -> Path:
    files = sorted((ROOT / "extract" / period).glob("*.json"))
    if not files:
        raise SystemExit(f"review-workbook: no extractions in extract/{period}/")
    items = load_line_items()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    check = wb.create_sheet("Check")
    check.append(["Company", "Fiscal year", "Line item", "Extracted (THB m)", "Pilot (THB m)", "Difference", "Status",
                  "File page", "Printed", "Pilot source"])
    recs = wb.create_sheet("Reconciliation")
    recs.append(["Company", "Fiscal year", "Check", "Computed", "As printed", "Difference", "Result"])
    for c in check[1] + recs[1]:
        c.font = BOLD
    fy_cur = "FY" + period[:4]
    fy_cmp = "FY" + str(int(period[:4]) - 1)
    for f in files:
        ex = load(f)
        ws = wb.create_sheet(ex["company"][:31], 0)
        src = ex["source"]
        ws["A1"] = f"{ex['company']} - extracted from {src['original_name']} (THB million)"
        ws["A1"].font = BOLD
        ws["A2"] = (f"Drive file {src.get('drive_file_id', '')} · SHA-256 {src['sha256']} · {src.get('pages', '')} pages · "
                    f"text layer: {src.get('text_layer', '')}")
        ws.append([])
        ws.append(["#", "Line item", f"31 Dec {period[:4]}", f"31 Dec {int(period[:4]) - 1}", "Status", "Source (file page)"])
        for c in ws[4]:
            c.font = BOLD
        for i, it in enumerate(items, start=1):
            v = ex["items"][it["code"]]
            how = {v[fy].get("read") for fy in (fy_cur, fy_cmp)}
            ws.append([i, it["workbook_label"], v[fy_cur]["value"], v[fy_cmp]["value"],
                       "Extracted (visual)" if "visual" in how else "Extracted",
                       _source_text(v[fy_cur]) + " | " + _source_text(v[fy_cmp])])
        ws.column_dimensions["B"].width = 34
        ws.column_dimensions["F"].width = 90
        for r in compare_pilot(ex):
            check.append([ex["company"], r["fiscal_year"], r["code"], r["extracted"], r["pilot"], r["difference"],
                          r["status"], r["page"], str(r["printed"]), r["pilot_source"]])
            if r["status"] == "DIFFERENT":
                for c in check[check.max_row]:
                    c.fill = FLAG
        for r in reconcile(ex):
            recs.append([ex["company"], r["fiscal_year"], r["check"], r["computed"], r["printed"], r["difference"],
                         "OK" if r["ok"] else "FAIL"])
    out = out or ROOT / "extract" / period / f"review_{period}.xlsx"
    wb.save(out)
    print(f"review-workbook: {len(files)} insurers -> {out.relative_to(ROOT)}")
    return out
