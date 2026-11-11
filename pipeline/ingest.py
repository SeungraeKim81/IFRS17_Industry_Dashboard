"""Step 1 - read the period's line items into tidy, reviewable CSV.

Two sources, chosen by "source" in config/dashboard.json:

  "extract"   the extractions from the published statements, made by `python -m pipeline extract`.
              Annual period FY2025: extract/2025FY/<company_id>.json, one per insurer on the annual
              dashboard (config/companies.csv, annual = yes); both fiscal years come from that file.
              Quarterly period 2026Q2: every insurer extracted in extract/2026Q2/, year to date; the
              comparative is the same quarter a year earlier (extract/2025Q2/) where it was extracted.
              The quarterly three-month profit or loss goes to line_items_3m.csv.
              Each value keeps where it was read (file page, printed figure); the company note is
              the extraction spec's notes (config/extraction/[quarterly/<period>/]<company_id>.json).
              A value the statement does not disclose is written blank with status "Not disclosed".
  "workbook"  the analyst capture workbook (the pilot; kept for reference).

The capture workbook layout:

The capture workbook has one sheet per insurer with a fixed layout:
column B = line item label, C = current year, D = comparative year,
E = status, F = source reference. Rows are matched by label (not by row
number) against config/line_items.csv, so a moved row is still read and an
unknown or missing label stops the run.

Output (data/<period>/):
  line_items.csv     one row per company x fiscal year x line item
  line_items_3m.csv  quarterly periods only: the three-month profit or loss, same layout
  company_notes.csv  the analyst's extraction notes per company
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import json

import openpyxl

from .common import (ROOT, annual_companies, comparative_period, fmt_num, load_companies, load_line_items,
                     load_settings, period_dir, quarter_info, write_csv)

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

    for co in annual_companies():
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


def extract_period(period: str) -> str:
    """Dashboard period -> extraction folder: FY2025 -> 2025FY; quarterly periods keep their name (2026Q2)."""
    m = re.fullmatch(r"FY(\d{4})", period)
    if m:
        return f"{m.group(1)}FY"
    if quarter_info(period):
        return period
    raise IngestError(f"period {period!r}: expected FYyyyy or yyyyQn")


def _load_folder(folder: Path) -> dict[str, dict]:
    out = {}
    for f in sorted(folder.glob("*.json")):
        ex = json.loads(f.read_text(encoding="utf-8"))
        out[ex["company"]] = ex
    return out


def _row(period: str, fy: str, company: str, code: str, rec: dict | None, source_text) -> dict:
    if rec["value"] is None:
        return {"report": period, "fiscal_year": fy, "company": company, "code": code, "value": "",
                "status": "Not disclosed", "source": source_text(rec)}
    return {"report": period, "fiscal_year": fy, "company": company, "code": code, "value": fmt_num(rec["value"]),
            "status": "Extracted", "source": source_text(rec)}


def ingest_extractions(period: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Line items, company notes, (quarterly only) the three-month profit or loss, and accepted breaks."""
    from .review_workbook import _source_text
    folder = ROOT / "extract" / extract_period(period)
    by_company = _load_folder(folder)
    quarterly = quarter_info(period) is not None
    fy_cmp = comparative_period(period)
    known = {c["company"]: c for c in load_companies()}
    if quarterly:
        unknown = sorted(set(by_company) - set(known))
        if unknown:
            raise IngestError(f"{folder.relative_to(ROOT)}/: insurers not in config/companies.csv: {', '.join(unknown)}")
        companies = [c for c in load_companies() if c["company"] in by_company]
        cmp_folder = ROOT / "extract" / extract_period(fy_cmp)
        cmp_by_company = _load_folder(cmp_folder) if cmp_folder.exists() else {}
        spec_dir = ROOT / "config" / "extraction" / "quarterly" / period
    else:
        companies = annual_companies()
        cmp_by_company = by_company
        spec_dir = ROOT / "config" / "extraction"
    rows, rows_3m, notes, errors = [], [], [], []
    accepted = []  # breaks the statement itself contains, recorded in the extraction (verify-extract)
    for co in companies:
        name = co["company"]
        ex = by_company.get(name)
        if ex is None:
            errors.append(f"{name}: no extraction in {folder.relative_to(ROOT)}/")
            continue
        cmp_ex = cmp_by_company.get(name)
        for it in load_line_items():
            code = it["code"]
            for fy, src in ((period, ex), (fy_cmp, cmp_ex)):
                if src is None:
                    continue  # no comparative extraction for this insurer
                rec = src["items"].get(code, {}).get(fy)
                if rec is None:
                    errors.append(f"{name}: {code} {fy} missing from the extraction")
                elif rec["value"] is None and not quarterly:
                    errors.append(f"{name}: {code} {fy} is not disclosed; the annual dashboard does not handle "
                                  "not-disclosed values yet")
                else:
                    rows.append(_row(period, fy, name, code, rec, _source_text))
        for fy, src in ((period, ex), (fy_cmp, cmp_ex)) if quarterly else ((period, ex),):
            for b in (src or {}).get("accepted_breaks", []):
                if b["check"] != "continuity":  # continuity is checked on the extraction, not on the page data
                    accepted.append({"company": name, "fiscal_year": fy, "check": b["check"],
                                     "difference": fmt_num(b["difference"]), "reason": b["reason"]})
        if quarterly:
            for fy, src in ((period, ex), (fy_cmp, cmp_ex)):
                for code, years in (src or {}).get("items_3m", {}).items():
                    if fy in years:
                        rows_3m.append(_row(period, fy, name, code, years[fy], _source_text))
        s = ex["source"]
        spec = spec_dir / f"{ex['company_id']}.json"
        spec_notes = json.loads(spec.read_text(encoding="utf-8")).get("notes", "") if spec.exists() else ""
        notes.append({"company": name,
                      "sheet_title": f"{name} - extracted from {s['original_name']} (THB million)",
                      "header_note": spec_notes,
                      "extraction_note": (f"Source: {s['original_name']} ({s.get('doc_type', '')}), "
                                          f"{s.get('pages', '')} pages, text layer: {s.get('text_layer', '')}, "
                                          f"SHA-256 {s['sha256']} (sources/{extract_period(period)}/registry.csv).")})
    if errors:
        raise IngestError("extractions failed ingestion:\n  - " + "\n  - ".join(errors))
    return rows, notes, rows_3m, accepted


def run(period: str | None = None, workbook: str | None = None) -> Path:
    s = load_settings()
    period = period or s["period"]
    rows_3m, accepted = [], []
    if workbook or s.get("source", "workbook") == "workbook":
        wb = Path(workbook) if workbook else ROOT / s["capture_workbook"]
        rows, notes = ingest(wb, period)
    else:
        rows, notes, rows_3m, accepted = ingest_extractions(period)
    out = period_dir(period)
    fields = ["report", "fiscal_year", "company", "code", "value", "status", "source"]
    write_csv(out / "line_items.csv", rows, fields)
    if rows_3m:
        write_csv(out / "line_items_3m.csv", rows_3m, fields)
    if accepted:
        write_csv(out / "accepted_breaks.csv", accepted, ["company", "fiscal_year", "check", "difference", "reason"])
    elif (out / "accepted_breaks.csv").exists():
        (out / "accepted_breaks.csv").unlink()
    write_csv(out / "company_notes.csv", notes, ["company", "sheet_title", "header_note", "extraction_note"])
    unconfirmed = [r for r in rows if r["status"].strip().lower() not in ("confirmed", "extracted", "not disclosed")]
    print(f"ingest: {len(rows)} values for {len(notes)} companies -> {out.relative_to(ROOT)}/line_items.csv")
    if unconfirmed:
        print(f"ingest: WARNING {len(unconfirmed)} values not marked 'Confirmed'", file=sys.stderr)
    return out
