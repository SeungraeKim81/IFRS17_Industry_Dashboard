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


def period_dir(period: str) -> Path:
    return DATA / period


def fmt_num(v: float) -> str:
    """Stable text form for CSV output (no float noise)."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s
