"""Step 3 - indicator definitions and calculation.

Every indicator the dashboard shows is defined once here, with the formula
text that is printed in the dashboard's methodology section. Ratios use the
company's own figures; industry figures are aggregate ratios (sum over sum)
plus the median of the company ratios.
"""
from __future__ import annotations

from statistics import median

from .common import fmt_num, load_companies, period_dir, read_csv, write_csv


def _div(a: float, b: float):
    return None if b == 0 else a / b


# code, label, unit, higher_is_better (None = neutral), group, formula text, function
METRICS = [
    ("insurance_revenue", "Insurance revenue", "thb_m", True, "scale",
     "Total insurance revenue", lambda v: v["insurance_revenue"]),
    ("net_profit", "Net profit", "thb_m", True, "scale",
     "Net profit for the year", lambda v: v["net_profit"]),
    ("csm_close", "CSM closing", "thb_m", True, "scale",
     "Contractual service margin at year end", lambda v: v["csm_close"]),
    ("nb_csm", "New-business CSM", "thb_m", True, "scale",
     "CSM from contracts initially recognised in the year", lambda v: v["nb_csm"]),
    ("nb_pv_premium", "New-business PV premium", "thb_m", True, "scale",
     "PV of future inflows on new business", lambda v: v["nb_pv_premium"]),
    ("isr_gross", "Insurance service result", "thb_m", True, "profitability",
     "Insurance revenue + insurance service expense", lambda v: v["insurance_revenue"] + v["insurance_service_expense"]),
    ("ism_gross", "Insurance service margin", "pct", True, "profitability",
     "(Insurance revenue + insurance service expense) / insurance revenue",
     lambda v: _div(v["insurance_revenue"] + v["insurance_service_expense"], v["insurance_revenue"])),
    ("ism_net", "Insurance service margin after reinsurance", "pct", True, "profitability",
     "(Insurance service result + reinsurance result) / insurance revenue",
     lambda v: _div(v["insurance_revenue"] + v["insurance_service_expense"] + v["reinsurance_result"], v["insurance_revenue"])),
    ("inv_margin", "Investment result net of IFIE", "pct", True, "profitability",
     "(Net investment income + net insurance finance expense) / insurance revenue",
     lambda v: _div(v["net_investment_income"] + v["ifie"], v["insurance_revenue"])),
    ("other_ratio", "Other expense, net", "pct", True, "profitability",
     "(Other expense + other income) / insurance revenue",
     lambda v: _div(v["other_expense"] + v["other_income"], v["insurance_revenue"])),
    ("tax_ratio", "Income tax", "pct", True, "profitability",
     "Income tax / insurance revenue", lambda v: _div(v["income_tax"], v["insurance_revenue"])),
    ("npm", "Net profit margin", "pct", True, "profitability",
     "Net profit / insurance revenue", lambda v: _div(v["net_profit"], v["insurance_revenue"])),
    ("current_loss_ratio", "Current-service loss ratio", "pct", False, "profitability",
     "-(Incurred claims + past service) / (BEL release + RA release + PAA revenue + other revenue + acquisition recovery)",
     lambda v: _div(-(v["incurred_claims"] + v["past_service"]),
                    v["bel_release"] + v["ra_release"] + v["paa_revenue"] + v["other_revenue"] + v["acq_recovery"])),
    ("csm_release_share", "CSM release in revenue", "pct", None, "profitability",
     "CSM release / insurance revenue", lambda v: _div(-v["csm_release"], v["insurance_revenue"])),
    ("csm_growth", "CSM growth", "pct", True, "csm",
     "CSM closing / CSM opening - 1", lambda v: _div(v["csm_close"], v["csm_open"]) - 1 if v["csm_open"] else None),
    ("release_ratio", "CSM release ratio", "pct", None, "csm",
     "CSM release / (opening CSM + new business + accretion + future-service changes)",
     lambda v: _div(-v["csm_release"], v["csm_open"] + v["csm_nb"] + v["csm_accretion"] + v["csm_future_service"])),
    ("nb_to_release", "New business / release", "x", True, "csm",
     "CSM from new business / CSM release", lambda v: _div(v["nb_csm"], -v["csm_release"])),
    ("nb_csm_margin", "New-business CSM margin", "pct", True, "new_business",
     "CSM from new business / PV premium of new business", lambda v: _div(v["nb_csm"], v["nb_pv_premium"])),
    ("acq_cost_ratio", "Acquisition cost ratio", "pct", False, "new_business",
     "PV acquisition cost / PV premium of new business", lambda v: _div(v["nb_pv_acq"], v["nb_pv_premium"])),
    ("nb_claims_ratio", "Claims & benefits ratio (NB)", "pct", False, "new_business",
     "PV claim outgo / PV premium of new business", lambda v: _div(v["nb_pv_claims"], v["nb_pv_premium"])),
    ("onerous_ratio", "Onerous new business", "pct", False, "new_business",
     "Loss component on new business / CSM from new business", lambda v: _div(v["nb_loss_component"], v["nb_csm"])),
]
METRIC_INDEX = {m[0]: m for m in METRICS}
# Market share is computed across companies, not per company.
SHARE_OF = {"rev_share": "insurance_revenue", "csm_share": "csm_close", "nb_csm_share": "nb_csm"}


def load_values(period: str) -> dict[tuple[str, str], dict[str, float]]:
    vals: dict[tuple[str, str], dict[str, float]] = {}
    for r in read_csv(period_dir(period) / "line_items.csv"):
        vals.setdefault((r["company"], r["fiscal_year"]), {})[r["code"]] = float(r["value"])
    return vals


def compute(period: str) -> list[dict]:
    """Long table: company, fiscal_year, metric, value, rank (1 = largest)."""
    vals = load_values(period)
    years = sorted({fy for _, fy in vals}, reverse=True)
    out = []
    for fy in years:
        per_co = {}
        for co in load_companies():
            v = vals.get((co["company"], fy))
            if v is None:
                continue
            per_co[co["company"]] = {m[0]: m[6](v) for m in METRICS}
        for share, base in SHARE_OF.items():
            tot = sum(m[base] for m in per_co.values())
            for m in per_co.values():
                m[share] = _div(m[base], tot)
        codes = [m[0] for m in METRICS] + list(SHARE_OF)
        for code in codes:
            ranked = sorted((m[code], c) for c, m in per_co.items() if m[code] is not None)[::-1]
            rank = {c: i + 1 for i, (_, c) in enumerate(ranked)}
            for c, m in per_co.items():
                if m[code] is None:
                    continue
                out.append({"company": c, "fiscal_year": fy, "metric": code,
                            "value": fmt_num(m[code]), "rank_desc": rank[c], "n": len(ranked)})
    return out


def industry(period: str) -> list[dict]:
    """Industry aggregate (sum over sum) and median of company values, per year."""
    vals = load_values(period)
    out = []
    for fy in sorted({fy for _, fy in vals}, reverse=True):
        rows = [v for (c, y), v in vals.items() if y == fy]
        agg = {k: sum(r[k] for r in rows) for k in rows[0]}
        for code, *_rest, fn in METRICS:
            comp = [x for x in (fn(r) for r in rows) if x is not None]
            out.append({"fiscal_year": fy, "metric": code, "aggregate": fmt_num(fn(agg)),
                        "median": fmt_num(median(comp)), "n": len(comp)})
        for code in ("csm_open", "csm_nb", "csm_accretion", "csm_future_service", "csm_release", "csm_close"):
            out.append({"fiscal_year": fy, "metric": "sum_" + code, "aggregate": fmt_num(agg[code]),
                        "median": "", "n": len(rows)})
    return out


def run(period: str) -> None:
    rows = compute(period)
    write_csv(period_dir(period) / "metrics.csv", rows, ["company", "fiscal_year", "metric", "value", "rank_desc", "n"])
    ind = industry(period)
    write_csv(period_dir(period) / "industry.csv", ind, ["fiscal_year", "metric", "aggregate", "median", "n"])
    print(f"metrics: {len(rows)} company values, {len(ind)} industry values -> data/{period}/metrics.csv, industry.csv")
