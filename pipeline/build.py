"""Step 4 - render the self-contained HTML dashboard.

All data the page needs is embedded as one JSON block, so the output is a
single file that opens offline and can be emailed or archived as-is.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from .common import CONFIG, OUTPUT, ROOT, TEMPLATES, load_companies, load_settings, period_dir, read_csv
from .metrics import METRICS, SHARE_OF, load_values

METRIC_LABEL = {"insurance_revenue": "insurance revenue", "csm_close": "closing CSM", "nb_csm": "new-business CSM"}
from .validate import RECONCILIATIONS


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return ""


def payload(period: str, focus: str | None = None) -> dict:
    s = load_settings()
    pdir = period_dir(period)
    companies = load_companies()
    names = {c["company"] for c in companies}
    focus = focus or s["focus_company"]
    if focus not in names:
        raise SystemExit(f"build: focus company {focus!r} is not in config/companies.csv")

    values = load_values(period)
    metrics: dict[tuple[str, str], dict] = {}
    for r in read_csv(pdir / "metrics.csv"):
        metrics.setdefault((r["company"], r["fiscal_year"]), {})[r["metric"]] = {
            "v": float(r["value"]), "rank": int(r["rank_desc"]), "n": int(r["n"])}
    years = sorted({fy for _, fy in values}, reverse=True)

    cos = []
    for c in companies:
        y = {}
        for fy in years:
            if (c["company"], fy) not in values:
                continue
            y[fy] = {"raw": values[(c["company"], fy)], "m": metrics[(c["company"], fy)]}
        cos.append({"name": c["company"], "short": c["short_name"], "legal": c["legal_name"],
                    "ra": c["ra_policy"], "units": f"face {c['face_unit']}, notes {c['notes_unit']}", "y": y})
    cos.sort(key=lambda c: -c["y"][period]["raw"]["insurance_revenue"])
    for i, c in enumerate(cos):
        c["size_rank"] = i + 1
        c["tier"] = 1 if i < s["large_insurer_count"] else 2

    industry: dict = {}
    for r in read_csv(pdir / "industry.csv"):
        industry.setdefault(r["fiscal_year"], {})[r["metric"]] = {
            "agg": float(r["aggregate"]), "median": float(r["median"]) if r["median"] else None}

    checks: dict = {}
    for r in read_csv(pdir / "validation.csv"):
        checks.setdefault(r["company"], {}).setdefault(r["fiscal_year"], {})[r["check"]] = {
            "ok": r["result"] == "OK", "diff": float(r["difference"])}

    with open(CONFIG / "commentary.json", encoding="utf-8") as f:
        commentary = json.load(f)

    return {
        "meta": {**{k: s[k] for k in ("title", "market", "standard", "period", "comparative", "period_end",
                                       "unit", "large_insurer_count", "comparative_caveat", "tolerance_thb_m")},
                 "default_focus": focus, "workbook": s["capture_workbook"],
                 "indexing": bool(s.get("search_engine_indexing", False)),
                 "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "git": _git_rev()},
        "years": years,
        "companies": cos,
        "industry": industry,
        "metric_defs": [{"code": m[0], "label": m[1], "unit": m[2], "better": m[3], "group": m[4], "formula": m[5]}
                        for m in METRICS] + [
            {"code": k, "label": "Share of " + METRIC_LABEL[b], "unit": "pct", "better": True, "group": "scale",
             "formula": f"Company {METRIC_LABEL[b]} / sum over all insurers covered"}
            for k, b in SHARE_OF.items()],
        "check_defs": [{"id": c[0], "label": c[1]} for c in RECONCILIATIONS],
        "checks": checks,
        "flags": read_csv(pdir / "flags.csv"),
        "company_notes": read_csv(pdir / "company_notes.csv"),
        "commentary": commentary,
    }


def render(data: dict) -> str:
    tpl = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    robots = "" if data["meta"]["indexing"] else '<meta name="robots" content="noindex,nofollow">'
    desc = (f"{data['meta']['standard']} figures and indicators for {len(data['companies'])} Thai life insurers, "
            f"{data['meta']['period']}, highlighting {data['meta']['default_focus']}.")
    return (tpl.replace("__TITLE__", data["meta"]["title"]).replace("__ROBOTS__", robots)
            .replace("__DESCRIPTION__", desc.replace('"', "&quot;")).replace("__DATA__", blob))


def run(period: str, focus: str | None = None) -> None:
    data = payload(period, focus)
    out = OUTPUT / period / f"Thai_Life_IFRS17_Dashboard_{period}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"build: {out.relative_to(ROOT)} (focus: {data['meta']['default_focus']}, {len(data['companies'])} insurers)")
