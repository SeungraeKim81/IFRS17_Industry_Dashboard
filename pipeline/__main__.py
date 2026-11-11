"""Command line: python -m pipeline [ingest|validate|metrics|build|all|site] [--period FY2025 | --period 2026Q2]
                 (without --period, ingest/validate/metrics/build/all run every period in config/dashboard.json "periods")
                 python -m pipeline extract --spec <spec.json> --pdf <statement.pdf>
                 python -m pipeline verify-extract <extract.json>
                 python -m pipeline review-workbook --period 2025FY"""
from __future__ import annotations

import argparse

import sys

from . import build, extract, ingest, metrics, review_workbook, site, validate, verify_extract
from .common import load_settings


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__)
    ap.add_argument("step", nargs="?", default="all", choices=["ingest", "validate", "metrics", "build", "all", "site", "extract", "verify-extract", "review-workbook"])
    ap.add_argument("target", nargs="?", help="verify-extract: the extraction JSON")
    ap.add_argument("--spec", help="extract: extraction spec (config/extraction/<company_id>.json)")
    ap.add_argument("--pdf", help="extract: the statement PDF")
    ap.add_argument("--period", help="reporting period, e.g. FY2025 (default: config/dashboard.json)")
    ap.add_argument("--workbook", help="capture workbook (default: config/dashboard.json)")
    ap.add_argument("--focus", help="company to highlight (default: config/dashboard.json)")
    a = ap.parse_args()
    if a.step == "extract":
        extract.run(a.spec, a.pdf)
        return
    if a.step == "verify-extract":
        sys.exit(0 if verify_extract.run(a.target) else 1)
    if a.step == "review-workbook":
        review_workbook.build(a.period or "2025FY")
        return
    s = load_settings()
    if a.step == "site":
        site.run(a.period)
        return
    for period in ([a.period] if a.period else s.get("periods", [s["period"]])):
        if a.step in ("ingest", "all"):
            ingest.run(period, a.workbook)
        if a.step in ("validate", "all"):
            validate.run(period)
        if a.step in ("metrics", "all"):
            metrics.run(period)
        if a.step in ("build", "all"):
            build.run(period, a.focus)


if __name__ == "__main__":
    main()
