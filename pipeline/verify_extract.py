"""Check an extraction (extract/<period>/<company_id>.json) two ways:

1. Reconciliations: the same six identities the pipeline enforces, on the extracted values.
   A line item the statement does not disclose is None. Where the statement prints only a total
   that covers not-disclosed items (MEMO_TOTALS, from the extraction's "memo"), the total stands
   in for them; any other None in an identity fails it.
2. Pilot comparison (FY2025 only): every value against the pilot capture workbook (kept as docs/pilot/FY2025_line_items.csv),
   classified as identical, rounding (within half a unit of the last digit the pilot kept: the
   pilot rounds to thousand Baht, for some insurers to 10,000 Baht) or different.

For a quarterly extraction (2026Q1, 2026Q2 ...) the six identities run on the year-to-date column,
and two more checks apply:

3. The three-month profit or loss (items_3m) ties to its net profit (the net profit bridge).
4. Continuity: the year-to-date opening CSM equals the closing CSM of the prior year-end extraction
   (extract/<year-1>FY/<company_id>.json). A missing prior extraction is reported, not passed.

A break the statement itself contains (two printed figures that do not agree) can be recorded in the spec as an
accepted break: {"check": <reconciliation id or "continuity">, "difference": <THB million>, "reason": ...}. It passes
only while the difference stays what was recorded (within tolerance), so a new reading error still fails.

  python -m pipeline verify-extract extract/2025FY/samsung-life.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import ROOT, load_settings, quarter_info, read_csv
from .validate import RECONCILIATIONS

ROUNDING = 0.0005  # half a thousand Baht, in THB million


def _half_unit(text: str) -> float:
    """Half a unit of the last digit the pilot kept (2 decimals -> 0.005), never below ROUNDING."""
    dec = len(text.split(".")[1]) if "." in text else 0
    return max(ROUNDING, 0.5 * 10 ** -dec + 1e-9)


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def values(ex: dict) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for code, years in ex["items"].items():
        for fy, rec in years.items():
            out.setdefault(fy, {})[code] = rec["value"]
    return out


# memo total -> the line items it covers when they are not disclosed separately
MEMO_TOTALS = {"nb_pv_outflows": ("nb_pv_acq", "nb_pv_claims")}


def _with_memo(ex: dict, fy: str, v: dict) -> dict:
    v = dict(v)
    for memo_code, covered in MEMO_TOTALS.items():
        rec = ex.get("memo", {}).get(memo_code, {}).get(fy)
        if rec and all(v.get(c) is None for c in covered):
            v[covered[0]] = rec["value"]
            v.update({c: 0.0 for c in covered[1:]})
    return v


def _accepted(ex: dict, check: str, difference: float | None) -> str | None:
    """The reason of an accepted break that matches this check and difference, else None."""
    tol = load_settings()["tolerance_thb_m"]
    for b in ex.get("accepted_breaks", []):
        if b["check"] == check and difference is not None and abs(difference - b["difference"]) <= tol:
            return b["reason"]
    return None


def reconcile(ex: dict) -> list[dict]:
    tol = load_settings()["tolerance_thb_m"]
    rows = []
    for fy, v in sorted(values(ex).items(), reverse=True):
        v = _with_memo(ex, fy, v)
        for cid, label, lhs, rhs in RECONCILIATIONS:
            try:
                a, b = lhs(v), rhs(v)
            except TypeError:  # a not-disclosed value with no memo total to stand in for it
                rows.append({"fiscal_year": fy, "check": cid, "label": label, "computed": None, "printed": None,
                             "difference": None, "ok": False})
                continue
            ok = abs(a - b) <= tol
            accepted = None if ok else _accepted(ex, cid, a - b)
            rows.append({"fiscal_year": fy, "check": cid, "label": label, "computed": a, "printed": b,
                         "difference": a - b, "ok": ok or accepted is not None,
                         **({"accepted": accepted} if accepted else {})})
    return rows


# the profit-or-loss lines a quarterly statement prints for the three months of the quarter
PL_3M = ("insurance_revenue", "insurance_service_expense", "reinsurance_result", "net_investment_income", "ifie",
         "other_expense", "other_income", "income_tax", "net_profit")


def reconcile_3m(ex: dict) -> list[dict]:
    """Net profit bridge on the three-month profit or loss of a quarterly extraction."""
    tol = load_settings()["tolerance_thb_m"]
    by_fy: dict[str, dict[str, float]] = {}
    for code, years in ex.get("items_3m", {}).items():
        for fy, rec in years.items():
            by_fy.setdefault(fy, {})[code] = rec["value"]
    rows = []
    for fy, v in sorted(by_fy.items()):
        missing = [c for c in PL_3M if v.get(c) is None]
        if missing:
            rows.append({"fiscal_year": fy, "check": "net_profit_3m", "computed": None, "printed": None,
                         "difference": None, "ok": False, "missing": missing})
            continue
        a = sum(v[c] for c in PL_3M if c != "net_profit")
        rows.append({"fiscal_year": fy, "check": "net_profit_3m", "computed": a, "printed": v["net_profit"],
                     "difference": a - v["net_profit"], "ok": abs(a - v["net_profit"]) <= tol})
    return rows


def continuity(ex: dict) -> dict | None:
    """Year-to-date opening CSM against the prior year-end closing CSM (quarterly extractions only).

    The prior year-end comes from the prior annual extraction (2025FY for 2026Q1); when that does not exist, from
    the prior-year comparative column of the same year's annual extraction (FY2024 in 2025FY for 2025Q1)."""
    q = quarter_info(ex["period"])
    if q is None:
        return None
    opening = ex["items"]["csm_open"][ex["period"]]["value"]
    prior_path = ROOT / "extract" / q["prior_annual"] / f"{ex['company_id']}.json"
    same_year_path = ROOT / "extract" / f"{q['year']}FY" / f"{ex['company_id']}.json"
    prior = note = None
    if prior_path.exists():
        prior, note = load(prior_path)["items"]["csm_close"][q["prior_fy"]]["value"], f"{q['prior_annual']} closing CSM"
    elif same_year_path.exists():
        column = load(same_year_path)["items"]["csm_close"].get(q["prior_fy"])
        if column is not None:
            prior, note = column["value"], f"{q['prior_fy']} closing CSM (comparative in {q['year']}FY)"
    if prior is None:
        return {"opening": opening, "prior_close": None, "difference": None, "ok": False,
                "note": f"no {q['prior_annual']} extraction to compare with"}
    tol = load_settings()["tolerance_thb_m"]
    ok = abs(opening - prior) <= tol
    accepted = None if ok else _accepted(ex, "continuity", opening - prior)
    return {"opening": opening, "prior_close": prior, "difference": opening - prior, "ok": ok or accepted is not None,
            "note": note, **({"accepted": accepted} if accepted else {})}


def compare_pilot(ex: dict, pilot_csv: Path | None = None) -> list[dict]:
    if ex["period"] != "2025FY":
        return []
    pilot_csv = pilot_csv or ROOT / "docs" / "pilot" / "FY2025_line_items.csv"
    pilot = {(r["fiscal_year"], r["code"]): (float(r["value"]), r["source"], r["value"])
             for r in read_csv(pilot_csv) if r["company"] == ex["company"]}
    rows = []
    for code, years in ex["items"].items():
        for fy, rec in years.items():
            p = pilot.get((fy, code))
            if rec["value"] is None:
                d, status = None, "not disclosed" if p is None else "DIFFERENT"
            else:
                d = None if p is None else rec["value"] - p[0]
                status = ("missing in pilot" if p is None else "identical" if abs(d) < 1e-9
                          else "rounding" if abs(d) <= _half_unit(p[2]) else "DIFFERENT")
            rows.append({"code": code, "fiscal_year": fy, "extracted": rec["value"], "pilot": None if p is None else p[0],
                         "difference": d, "status": status, "page": rec.get("page"), "printed": rec.get("printed", "const"),
                         "pilot_source": None if p is None else p[1]})
    return rows


def run(path: str) -> bool:
    ex = load(Path(path))
    rec = reconcile(ex)
    cmp_ = compare_pilot(ex)
    print(f"{ex['company']} ({ex['period']}), source {ex['source']['original_name']} sha256 {ex['source']['sha256'][:12]}…")
    print(f"  reconciliations: {sum(r['ok'] for r in rec)}/{len(rec)} OK")
    for r in rec:
        if r.get("accepted"):
            print(f"    ACCEPTED {r['fiscal_year']} {r['check']}: difference {r['difference']:.3f} ({r['accepted']})")
        if not r["ok"]:
            print(f"    FAIL {r['fiscal_year']} {r['check']}: " + ("a value is not disclosed" if r["computed"] is None
                  else f"{r['computed']:.3f} vs {r['printed']:.3f}"))
    counts: dict[str, int] = {}
    for r in cmp_:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    if cmp_:
        print("  vs pilot workbook: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in cmp_:
        if r["status"] not in ("identical", "rounding", "missing in pilot"):
            print(f"    {r['status']}: {r['fiscal_year']} {r['code']} extracted {r['extracted']} pilot {r['pilot']} (p.{r['page']})")
    rec3 = reconcile_3m(ex)
    if rec3:
        print(f"  three-month net profit bridge: {sum(r['ok'] for r in rec3)}/{len(rec3)} OK")
        for r in rec3:
            if not r["ok"]:
                print(f"    FAIL {r['fiscal_year']}: " + (f"missing {r['missing']}" if r["computed"] is None
                      else f"{r['computed']:.3f} vs {r['printed']:.3f}"))
    cont = continuity(ex)
    if cont:
        print(f"  continuity: opening CSM {cont['opening']:.3f} vs {cont['note']} "
              + ("(none)" if cont["prior_close"] is None else f"{cont['prior_close']:.3f}")
              + (" OK" if cont["ok"] else " MISMATCH")
              + (f" (ACCEPTED: difference {cont['difference']:.3f}, {cont['accepted']})" if cont.get("accepted") else ""))
    return (all(r["ok"] for r in rec) and not any(r["status"] == "DIFFERENT" for r in cmp_)
            and all(r["ok"] for r in rec3) and (cont is None or cont["ok"]))
