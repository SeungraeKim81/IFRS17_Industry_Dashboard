"""Step 1 - read the analyst capture workbook into tidy, reviewable CSV.

The capture workbook has one sheet per insurer with a fixed layout:
column B = line item label, C = current year, D = comparative year,
E = status, F = source reference. Rows are matched by label (not by row
number) against config/line_items.csv, so a moved row is still read and an
unknown or missing label stops the run.

Output (data/<period>/):
  line_items.csv     one row per company x fiscal year x line item
  company_notes.csv  the analyst's extraction notes per company
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl

from .common import ROOT, fmt_num, load_companies, load_line_items, load_settings, period_dir, write_csv

HEADER_ROW = 4
FIRST_ROW, LAST_ROW = 5, 34  # input block; reconciliation formulas start below
LABEL_COL, CUR_COL, CMP_COL, STATUS_COL, SOURCE_COL = 2, 3, 4, 5, 6


class IngestError(Exception):
    pass


def _norm(label: str) -> str:
    return re.sub(r"\s+", " ", str(label).replace("—", "-").replace("–", "-")).strip().lower()


def _label_index(items: list[dict]) -> dict[str, str]:
    idx = {}
    for it in items:
        for lab in [it["workbook_label"], *filter(None, it["aliases"].split("|"))]:
            idx[_norm(lab)] = it["code"]
    return idx


def _fiscal_year(header) -> str:
    m = re.search(r"(20\d\d)", str(header or ""))
    if not m:
        raise IngestError(f"cannot read a year from column header {header!r}")
    return "FY" + m.group(1)


def _number(cached, raw, where: str) -> float:
    for v in (cached, raw):
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v)
    raise IngestError(f"{where}: not a number (value {raw!r}). Enter a number, or open and save "
                      "the workbook in Excel so formula results are cached.")


def ingest(workbook: Path, period: str) -> tuple[list[dict], list[dict]]:
    wb_raw = openpyxl.load_workbook(workbook, data_only=False)
    wb_val = openpyxl.load_workbook(workbook, data_only=True)
    items = load_line_items()
    labels = _label_index(items)
    rows, notes, errors = [], [], []

    for co in load_companies():
        sheet = co["sheet"]
        if sheet not in wb_raw.sheetnames:
            errors.append(f"{co['company']}: sheet {sheet!r} not found in workbook")
            continue
        ws, wv = wb_raw[sheet], wb_val[sheet]
        fy_cur = _fiscal_year(ws.cell(HEADER_ROW, CUR_COL).value)
        fy_cmp = _fiscal_year(ws.cell(HEADER_ROW, CMP_COL).value)
        if fy_cur != period:
            errors.append(f"{sheet}: current-year column is {fy_cur}, expected {period}")
        seen = set()
        for r in range(FIRST_ROW, LAST_ROW + 1):
            lab = ws.cell(r, LABEL_COL).value
            if lab is None:
                continue
            code = labels.get(_norm(lab))
            if code is None:
                errors.append(f"{sheet}!B{r}: unknown line item {lab!r} (add it or an alias to config/line_items.csv)")
                continue
            if code in seen:
                errors.append(f"{sheet}!B{r}: line item {lab!r} appears twice")
                continue
            seen.add(code)
            status = ws.cell(r, STATUS_COL).value or ""
            source = ws.cell(r, SOURCE_COL).value or ""
            for col, fy in ((CUR_COL, fy_cur), (CMP_COL, fy_cmp)):
                cell = ws.cell(r, col)
                try:
                    v = _number(wv.cell(r, col).value, cell.value, f"{sheet}!{cell.coordinate}")
                except IngestError as e:
                    errors.append(str(e))
                    continue
                rows.append({"report": period, "fiscal_year": fy, "company": co["company"], "code": code,
                             "value": fmt_num(v), "status": status, "source": source})
        missing = [it["code"] for it in items if it["code"] not in seen]
        if missing:
            errors.append(f"{sheet}: missing line items {missing}")
        notes.append({"company": co["company"], "sheet_title": ws["A1"].value or "",
                      "header_note": ws["A2"].value or "", "extraction_note": ws["A51"].value or ""})

    if errors:
        raise IngestError("capture workbook failed ingestion:\n  - " + "\n  - ".join(errors))
    return rows, notes


def run(period: str | None = None, workbook: str | None = None) -> Path:
    s = load_settings()
    period = period or s["period"]
    wb = Path(workbook) if workbook else ROOT / s["capture_workbook"]
    rows, notes = ingest(wb, period)
    out = period_dir(period)
    write_csv(out / "line_items.csv", rows, ["report", "fiscal_year", "company", "code", "value", "status", "source"])
    write_csv(out / "company_notes.csv", notes, ["company", "sheet_title", "header_note", "extraction_note"])
    unconfirmed = [r for r in rows if r["status"].strip().lower() != "confirmed"]
    print(f"ingest: {len(rows)} values for {len(notes)} companies -> {out.relative_to(ROOT)}/line_items.csv")
    if unconfirmed:
        print(f"ingest: WARNING {len(unconfirmed)} values not marked 'Confirmed'", file=sys.stderr)
    return out
