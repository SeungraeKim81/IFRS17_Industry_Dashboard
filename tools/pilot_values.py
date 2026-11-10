"""Print the pilot workbook's figures and source notes for one insurer, as a reference while extracting.

  python3 tools/pilot_values.py "Dhipaya Life"

The pilot is a reference, not the truth: where an extraction differs, the statement page decides
(several pilot figures were found to be off by a rounding unit). Its page numbers may belong to
another edition of the statement; locate tables by heading.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    company = sys.argv[1]
    rows = [r for r in csv.DictReader(open(ROOT / "data" / "FY2025" / "line_items.csv", encoding="utf-8"))
            if r["company"] == company]
    if not rows:
        sys.exit(f"no pilot rows for {company!r}; names are as in config/companies.csv")
    d: dict = {}
    for r in rows:
        d.setdefault(r["code"], {})[r["fiscal_year"]] = (r["value"], r["source"])
    for code, v in d.items():
        print(f"{code:26s} {v['FY2025'][0]:>12s} {v['FY2024'][0]:>12s}  {v['FY2025'][1][:70]}")
    try:
        import openpyxl
        ws = openpyxl.load_workbook(ROOT / "data" / "capture" / "IFRS17_extraction_FY2025_v11.xlsx")[company]
        print("\nPilot notes:\n" + str(ws["A2"].value) + "\n\n" + str(ws["A51"].value))
    except Exception as e:  # the notes are a convenience
        print(f"(pilot notes not shown: {e})")


if __name__ == "__main__":
    main()
