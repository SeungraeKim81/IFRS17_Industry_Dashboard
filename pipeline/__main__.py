"""Command line: python -m pipeline [ingest|validate|metrics|build|all] [--period FY2025]"""
from __future__ import annotations

import argparse

from . import build, ingest, metrics, validate
from .common import load_settings


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__)
    ap.add_argument("step", nargs="?", default="all", choices=["ingest", "validate", "metrics", "build", "all"])
    ap.add_argument("--period", help="reporting period, e.g. FY2025 (default: config/dashboard.json)")
    ap.add_argument("--workbook", help="capture workbook (default: config/dashboard.json)")
    ap.add_argument("--focus", help="company to highlight (default: config/dashboard.json)")
    a = ap.parse_args()
    period = a.period or load_settings()["period"]
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
