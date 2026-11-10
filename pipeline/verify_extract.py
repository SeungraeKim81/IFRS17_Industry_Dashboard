"""Check an extraction (extract/<period>/<company_id>.json) two ways:

1. Reconciliations: the same six identities the pipeline enforces, on the extracted values.
2. Pilot comparison: every value against the pilot capture workbook (data/FY2025/line_items.csv),
   classified as identical, rounding (within half a unit of the last digit the pilot kept: the
   pilot rounds to thousand Baht, for some insurers to 10,000 Baht) or different.

  python -m pipeline verify-extract extract/2025FY/samsung-life.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import ROOT, load_settings, read_csv
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


def reconcile(ex: dict) -> list[dict]:
    tol = load_settings()["tolerance_thb_m"]
    rows = []
    for fy, v in sorted(values(ex).items(), reverse=True):
        for cid, label, lhs, rhs in RECONCILIATIONS:
            a, b = lhs(v), rhs(v)
            rows.append({"fiscal_year": fy, "check": cid, "label": label, "computed": a, "printed": b,
                         "difference": a - b, "ok": abs(a - b) <= tol})
    return rows


def compare_pilot(ex: dict, pilot_csv: Path | None = None) -> list[dict]:
    pilot_csv = pilot_csv or ROOT / "data" / "FY2025" / "line_items.csv"
    pilot = {(r["fiscal_year"], r["code"]): (float(r["value"]), r["source"], r["value"])
             for r in read_csv(pilot_csv) if r["company"] == ex["company"]}
    rows = []
    for code, years in ex["items"].items():
        for fy, rec in years.items():
            p = pilot.get((fy, code))
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
        if not r["ok"]:
            print(f"    FAIL {r['fiscal_year']} {r['check']}: {r['computed']:.3f} vs {r['printed']:.3f}")
    counts: dict[str, int] = {}
    for r in cmp_:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("  vs pilot workbook: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in cmp_:
        if r["status"] not in ("identical", "rounding"):
            print(f"    {r['status']}: {r['fiscal_year']} {r['code']} extracted {r['extracted']} pilot {r['pilot']} (p.{r['page']})")
    return all(r["ok"] for r in rec) and not any(r["status"] == "DIFFERENT" for r in cmp_)
