"""Step 4 - render the self-contained HTML dashboard.

All data the page needs is embedded as one JSON block, so the output is a
single file that opens offline and can be emailed or archived as-is.

One page per period: the annual page (FY2025) and the quarterly pages (2026Q2 ...), all from
the same template. A quarterly page is year to date; it also carries the three-month profit or
loss, the like-for-like industry figures (industry_common.csv) and the quarterly caveat. Every
page links to the other built periods (config/dashboard.json "periods").
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from .common import (CONFIG, OUTPUT, ROOT, TEMPLATES, comparative_period, load_companies, load_settings, period_dir,
                     quarter_info, read_csv)
from .metrics import METRICS, SHARE_OF, load_values

METRIC_LABEL = {"insurance_revenue": "insurance revenue", "csm_close": "closing CSM", "nb_csm": "new-business CSM"}
from .validate import RECONCILIATIONS


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return ""


def load_translation(lang: str) -> dict:
    """config/i18n/<lang>.json: translations of the data-driven text (English is the source)."""
    with open(CONFIG / "i18n" / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)


def missing_translations(data: dict, lang: str) -> list[str]:
    """Every data-driven string shown on the page must have a translation."""
    tr = data["i18n"].get(lang, {})
    miss = [f"meta.{k}" for k in ("title", "standard", "period_end", "unit", "comparative_caveat") if not tr.get("meta", {}).get(k)]
    miss += [f"metrics.{d['code']}" for d in data["metric_defs"]
             if not all(tr.get("metrics", {}).get(d["code"], {}).get(x) for x in ("label", "formula"))]
    miss += [f"checks.{c['id']}" for c in data["check_defs"]
             if not all(tr.get("checks", {}).get(c["id"], {}).get(x) for x in ("label", "short"))]
    miss += [f"commentary.{n['id']}" for n in data["commentary"]
             if not all(tr.get("commentary", {}).get(n["id"], {}).get(x) for x in ("title", "body"))]
    miss += [f"groups.{g}" for g in {d["group"] for d in data["metric_defs"]} if not tr.get("groups", {}).get(g)]
    miss += [f"flags.{f['company']}.{f['fiscal_year']}.{f['flag']}" for f in data["flags"] if not f.get("message_" + lang)]
    return miss


MONTH_END = {1: ("31 March", "3월 31일", "31 มีนาคม"), 2: ("30 June", "6월 30일", "30 มิถุนายน"),
             3: ("30 September", "9월 30일", "30 กันยายน")}


def period_label(period: str) -> str:
    """How a period is named on the page: FY2025, or 2Q2026 for the six months to 30 June 2026."""
    q = quarter_info(period)
    return period if q is None else f"{q['quarter']}Q{q['year']}"


def _quarter_meta(period: str, s: dict, i18n: dict) -> dict:
    """Period end, months to date and the quarterly caveat (English in meta, Korean into the translation)."""
    q = quarter_info(period)
    en, ko, th = MONTH_END[q["quarter"]]
    be = q["year"] + 543
    for lang, tr in i18n.items():
        m = tr.setdefault("meta", {})
        if lang == "ko":
            m["period_end"] = f"{q['year']}년 {ko} (불기 {be}년)"
        elif lang == "th":  # Buddhist Era first, as Thai statements print it
            m["period_end"] = f"{th} {be} (ค.ศ. {q['year']})"
        m["comparative_caveat"] = m.get("quarterly_caveat", "")
    return {"period_end": f"{en} {q['year']} (B.E. {be})", "comparative_caveat": s["quarterly_caveat"],
            "ytd_months": q["ytd_months"]}


def _industry_table(path) -> dict:
    out: dict = {}
    if path.exists():
        for r in read_csv(path):
            out.setdefault(r["fiscal_year"], {})[r["metric"]] = {
                "agg": float(r["aggregate"]) if r["aggregate"] != "" else None,
                "median": float(r["median"]) if r["median"] else None, "n": int(r["n"])}
    return out


def _source_ref(s: dict, period: str) -> str:
    """What the footer names as the data source: the registry of the statements read, or the workbook."""
    if s.get("source", "workbook") == "extract":
        from .ingest import extract_period
        return f"sources/{extract_period(period)}/registry.csv"
    return s["capture_workbook"]


def payload(period: str, focus: str | None = None) -> dict:
    s = load_settings()
    pdir = period_dir(period)
    values = load_values(period)
    # the insurers with figures for this period: the annual list, or every insurer extracted for a quarter
    companies = [c for c in load_companies() if (c["company"], period) in values]
    names = {c["company"] for c in companies}
    focus = focus or s["focus_company"]
    if focus not in names:
        raise SystemExit(f"build: focus company {focus!r} is not in config/companies.csv")

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

    industry = _industry_table(pdir / "industry.csv")
    industry_common = _industry_table(pdir / "industry_common.csv")
    accepted = {(r["company"], r["fiscal_year"], r["check"]): r["reason"]
                for r in (read_csv(pdir / "accepted_breaks.csv") if (pdir / "accepted_breaks.csv").exists() else [])}

    checks: dict = {}
    for r in read_csv(pdir / "validation.csv"):
        checks.setdefault(r["company"], {}).setdefault(r["fiscal_year"], {})[r["check"]] = {
            "ok": r["result"] != "FAIL", "status": r["result"],
            "diff": float(r["difference"]) if r["difference"] != "" else None,
            **({"reason": accepted[(r["company"], r["fiscal_year"], r["check"])]} if r["result"] == "ACCEPTED" else {})}

    with open(CONFIG / "commentary.json", encoding="utf-8") as f:
        # a note tied to periods ("periods") shows only on those pages
        commentary = [n for n in json.load(f) if period in n.get("periods", [period])]
    i18n = {lang: load_translation(lang) for lang in s.get("languages", ["en"]) if lang != "en"}
    quarterly = quarter_info(period) is not None
    cmp = comparative_period(period)
    meta = {k: s[k] for k in ("title", "market", "standard", "period_end", "unit", "large_insurer_count",
                              "comparative_caveat", "tolerance_thb_m")}
    if quarterly:
        meta.update(_quarter_meta(period, s, i18n))
    common_n = {fy: v["insurance_revenue"]["n"] for fy, v in industry_common.items()}

    return {
        "meta": {**meta, "period": period, "comparative": cmp, "kind": "quarter" if quarterly else "annual",
                 "period_label": period_label(period), "comparative_label": period_label(cmp),
                 "has_comparative": cmp in years, "common_n": next(iter(common_n.values()), None),
                 "periods": [{"id": p, "label": period_label(p)} for p in s.get("periods", [s["period"]])],
                 "default_focus": focus, "source_ref": _source_ref(s, period),
                 "indexing": bool(s.get("search_engine_indexing", False)),
                 "languages": s.get("languages", ["en"]), "default_language": s.get("default_language", "en"),
                 "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "git": _git_rev()},
        "years": years,
        "companies": cos,
        "industry": industry,
        "industry_common": industry_common,
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
        "i18n": i18n,
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
    for lang in data["i18n"]:
        miss = missing_translations(data, lang)
        if miss:
            raise SystemExit(f"build: missing {lang} translations in config/i18n/{lang}.json: {', '.join(miss)}")
    out = OUTPUT / period / f"Thai_Life_IFRS17_Dashboard_{period}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"build: {out.relative_to(ROOT)} (focus: {data['meta']['default_focus']}, {len(data['companies'])} insurers)")
