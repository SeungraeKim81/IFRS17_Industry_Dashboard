"""Shared paths and small helpers for the dashboard pipeline."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
TEMPLATES = ROOT / "templates"


def load_settings() -> dict:
    with open(CONFIG / "dashboard.json", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load_companies() -> list[dict]:
    return read_csv(CONFIG / "companies.csv")


def load_line_items() -> list[dict]:
    return read_csv(CONFIG / "line_items.csv")


def quarter_info(period: str) -> dict | None:
    """Extraction period 2026Q2 -> year 2026, quarter 2, 6 months to date, prior year-end 2025FY; None for FY periods."""
    import re
    m = re.fullmatch(r"(\d{4})Q([1-3])", period)
    if not m:
        return None
    year, q = int(m.group(1)), int(m.group(2))
    return {"year": year, "quarter": q, "ytd_months": 3 * q, "prior_annual": f"{year - 1}FY", "prior_fy": f"FY{year - 1}"}


def period_dir(period: str) -> Path:
    return DATA / period


def fmt_num(v: float) -> str:
    """Stable text form for CSV output (no float noise)."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s
