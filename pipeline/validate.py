"""Step 2 - validation gate.

Hard checks (the run stops if any fails): the reconciliations carried in
the capture workbook, re-performed on the ingested numbers, plus one
consistency check between the CSM roll-forward and the new-business note.

Soft checks (reported, never blocking): plausibility flags that point the
reviewer at figures worth a second look.
"""
from __future__ import annotations

from .common import fmt_num, load_settings, period_dir, write_csv
from .metrics import METRIC_INDEX, load_values

# id, label, left side (computed), right side (as printed)
RECONCILIATIONS = [
    ("revenue_split", "Revenue split = total insurance revenue",
     lambda v: v["bel_release"] + v["ra_release"] - v["csm_release"] + v["acq_recovery"] + v["paa_revenue"] + v["other_revenue"],
     lambda v: v["insurance_revenue"]),
    ("expense_split", "Expense breakdown = total insurance service expense",
     lambda v: v["incurred_claims"] + v["past_service"] + v["loss_component"] + v["acq_amortisation"],
     lambda v: v["insurance_service_expense"]),
    ("net_profit", "Net profit bridge = net profit as printed",
     lambda v: (v["insurance_revenue"] + v["insurance_service_expense"] + v["reinsurance_result"] + v["other_expense"]
                + v["other_income"] + v["net_investment_income"] + v["ifie"] + v["income_tax"]),
     lambda v: v["net_profit"]),
    ("csm_rollforward", "CSM roll-forward = closing CSM",
     lambda v: v["csm_open"] + v["csm_nb"] + v["csm_accretion"] + v["csm_future_service"] + v["csm_release"],
     lambda v: v["csm_close"]),
    ("nb_csm", "New business: PV inflow - acquisition - claims - RA + loss component = CSM",
     lambda v: v["nb_pv_premium"] - v["nb_pv_acq"] - v["nb_pv_claims"] - v["nb_ra"] + v["nb_loss_component"],
     lambda v: v["nb_csm"]),
    ("nb_consistency", "CSM roll-forward new business = new-business note",
     lambda v: v["csm_nb"], lambda v: v["nb_csm"]),
]


def _plausibility(c: str, fy: str, v: dict, prev: dict | None, p: dict) -> list[dict]:
    m = {k: METRIC_INDEX[k][6](v) for k in ("release_ratio", "nb_to_release", "nb_csm_margin")}
    flags = []

    def add(fid, msg):
        flags.append({"company": c, "fiscal_year": fy, "flag": fid, "message": msg})

    if v["csm_accretion"] < 0 < v["csm_open"]:
        add("negative_accretion", f"CSM interest accretion is negative ({v['csm_accretion']:,.1f}m) on a positive opening CSM")
    rr = m["release_ratio"]
    if rr is not None and not (p["release_ratio_min"] <= rr <= p["release_ratio_max"]):
        add("release_ratio", f"CSM release ratio {rr:.1%} is outside {p['release_ratio_min']:.0%}-{p['release_ratio_max']:.0%}")
    if m["nb_to_release"] is not None and m["nb_to_release"] > p["nb_to_release_max"]:
        add("nb_to_release", f"New business / release {m['nb_to_release']:.1f}x is above {p['nb_to_release_max']:.1f}x")
    if m["nb_csm_margin"] is not None and m["nb_csm_margin"] > p["nb_csm_margin_max"]:
        add("nb_margin", f"New-business CSM margin {m['nb_csm_margin']:.1%} is above {p['nb_csm_margin_max']:.0%}")
    if v["nb_csm"] > 0 and v["nb_loss_component"] > v["nb_csm"]:
        add("onerous_nb", f"Losses on onerous new business ({v['nb_loss_component']:,.1f}m) exceed new-business CSM ({v['nb_csm']:,.1f}m)")
    if v["net_profit"] < 0:
        add("loss_year", f"Net loss of {v['net_profit']:,.1f}m")
    if prev and prev["insurance_revenue"]:
        g = v["insurance_revenue"] / prev["insurance_revenue"] - 1
        if abs(g) > p["yoy_revenue_abs_max"]:
            add("revenue_yoy", f"Insurance revenue changed {g:+.0%} year on year")
    return flags


def validate(period: str) -> tuple[list[dict], list[dict]]:
    s = load_settings()
    tol = s["tolerance_thb_m"]
    vals = load_values(period)
    checks, flags = [], []
    for (c, fy), v in sorted(vals.items()):
        for cid, label, lhs, rhs in RECONCILIATIONS:
            a, b = lhs(v), rhs(v)
            checks.append({"company": c, "fiscal_year": fy, "check": cid, "label": label,
                           "computed": fmt_num(round(a, 6)), "printed": fmt_num(round(b, 6)),
                           "difference": fmt_num(round(a - b, 6)), "result": "OK" if abs(a - b) <= tol else "FAIL"})
        prev_fy = "FY" + str(int(fy[2:]) - 1)
        flags += _plausibility(c, fy, v, vals.get((c, prev_fy)), s["plausibility"])
    return checks, flags


def run(period: str, strict: bool = True) -> bool:
    checks, flags = validate(period)
    write_csv(period_dir(period) / "validation.csv", checks,
              ["company", "fiscal_year", "check", "label", "computed", "printed", "difference", "result"])
    write_csv(period_dir(period) / "flags.csv", flags, ["company", "fiscal_year", "flag", "message"])
    fails = [c for c in checks if c["result"] != "OK"]
    print(f"validate: {len(checks) - len(fails)}/{len(checks)} reconciliations OK, {len(flags)} plausibility flags")
    for f in fails:
        print(f"  FAIL {f['company']} {f['fiscal_year']} {f['check']}: computed {f['computed']} vs printed "
              f"{f['printed']} (diff {f['difference']})")
    if fails and strict:
        raise SystemExit("validate: reconciliation failures - fix the capture workbook before building")
    return not fails
