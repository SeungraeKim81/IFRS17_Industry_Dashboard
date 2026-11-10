# Pilot reference (FY2025)

The dashboard's first version was built from an analyst capture workbook, the pilot. Since the switch to the
extractions from the published statements (`extract/2025FY/`), the pilot is kept for reference only; nothing in
the pipeline or the published dashboard reads it.

| File | What it is |
|---|---|
| `data/capture/IFRS17_extraction_FY2025_v11.xlsx` | The pilot capture workbook (17 insurers, FY2025 and FY2024) |
| `docs/pilot/FY2025_line_items.csv` | Its line items as read by the workbook ingest (`python -m pipeline ingest --workbook …`), the values `verify-extract` compares an extraction against |
| `docs/benchmark/IFRS17_CSM_board_17companies_benchmark.html` | The benchmark board the pilot dashboard was built against |

Where an extraction differs from the pilot, the published statement decides; the differences found in FY2025 are
listed in `docs/HANDOFF.md` section 10.
