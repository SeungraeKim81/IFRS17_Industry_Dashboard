# Thai life insurance industry — IFRS 17 dashboard

A repeatable workflow that turns the published TFRS 17 (IFRS 17) financial
statements of Thai life insurers into one self-contained HTML dashboard.
**Samsung Life Insurance (Thailand)** is the highlighted insurer (our
perspective); any other insurer can be highlighted from the page or the
command line.

| | |
|---|---|
| Objective | A Thailand life-industry dashboard in HTML, rebuilt the same way every reporting period |
| Scope | IFRS 17 figures and indicators: insurance revenue and service result, CSM roll-forward, new business, profit bridge |
| Source | Public information, mainly the audited financial statements (SET filings, OIC annual disclosures, company websites) |
| Coverage | FY2025 with FY2024 comparatives, 17 insurers, THB million |
| Output | `output/FY2025/Thai_Life_IFRS17_Dashboard_FY2025.html`: one file that works offline and can be emailed |
| Published | <https://seungraekim81.github.io/IFRS17_Industry_Dashboard/> (see `docs/DEPLOY.md`) |
| Languages | English and Korean (한국어), switched with the button at the top right; the choice is remembered in the browser |

## Quick start

Requires Python 3.10+ and `openpyxl` (`pip install -r requirements.txt`).

```bash
python -m pipeline all
```

That runs the four steps below and writes the dashboard. Each step can also be run on its own:

```bash
python -m pipeline ingest      # capture workbook -> data/FY2025/line_items.csv
python -m pipeline validate    # reconciliations (blocking) + plausibility flags (advisory)
python -m pipeline metrics     # indicators, ranks, industry aggregates
python -m pipeline build       # render the HTML
python -m pipeline build --focus "Dhipaya Life"   # highlight another insurer
python -m pipeline site       # collect the built dashboards into _site/ for GitHub Pages
python -m pipeline extract --spec config/extraction/samsung-life.json --pdf <statement.pdf>
python -m pipeline verify-extract extract/2025FY/samsung-life.json
python -m pipeline review-workbook --period 2025FY
python -m unittest discover -s tests -v
```

## How it works

```
 Financial statements (PDF / XLSX / DOCX)
        │  analyst extraction, guided by Source Map + Note Anchors
        ▼
 data/capture/IFRS17_extraction_FY2025_v11.xlsx      one sheet per insurer
        │  1 ingest    match rows by label, normalise, fail on unknown/missing items
        ▼
 data/FY2025/line_items.csv                          tidy: company × year × line item
        │  2 validate  6 reconciliations × 2 years × 17 insurers must tie (0.05m)
        ▼               + plausibility flags for reviewer follow-up
 data/FY2025/validation.csv, flags.csv
        │  3 metrics   22 indicators, ranks, shares, industry aggregate & median
        ▼
 data/FY2025/metrics.csv, industry.csv
        │  4 build     embed data + commentary in templates/dashboard.html
        ▼
 output/FY2025/Thai_Life_IFRS17_Dashboard_FY2025.html
```

The build stops if any reconciliation fails, so a published dashboard always
ties to the insurers' printed subtotals.

## Dashboard sections

1. **Focus**: KPI tiles for the highlighted insurer, each with its change from the prior year, rank and industry
   benchmark, plus auto-generated headlines and any notes or review flags that apply to it
2. **Market position**: insurance revenue, closing CSM and new-business CSM with market shares
3. **CSM engine**: roll-forward waterfall (focus vs industry, opening = 100) and the CSM sustainability quadrant
4. **New-business quality**: NB CSM margin, acquisition cost ratio, onerous share and NB / release; focus FY2025 vs FY2024 against all insurers
5. **Insurance service margin by RA policy**: compared only within each risk-adjustment disaggregation group
6. **Profit bridge**: what happens to 100 baht of insurance revenue
7. **All insurers**: sortable table with FY2025 / FY2024 / change views and a CSV download
8. **Data quality**: reconciliation matrix and plausibility flags
9. **Method & notes**: comparability notes, indicator definitions, per-insurer extraction notes

## Repository layout

| Path | What it holds |
|---|---|
| `config/dashboard.json` | Period, focus insurer, tolerance, plausibility thresholds, title |
| `config/companies.csv` | Insurer master: names, workbook sheet, RA policy, source units |
| `config/line_items.csv` | The 30 captured line items, their workbook labels and sign convention |
| `config/commentary.json` | Analyst comparability notes (tagged to insurers where they apply) |
| `config/i18n/ko.json` | Korean text for everything that comes from data: indicator names and definitions, reconciliation names, commentary, period and unit text |
| `data/capture/` | The analyst capture workbook (input) |
| `data/<period>/` | Generated, committed CSVs, so every change to a figure shows in the diff |
| `pipeline/` | The four steps (`ingest`, `validate`, `metrics`, `build`) |
| `templates/dashboard.html` | Page layout, styles and charts (vanilla JS + SVG, no external libraries) |
| `output/<period>/` | The built dashboard |
| `docs/WORKFLOW.md` | The operating process: roles, steps, gates, review checklist, period roll-over |
| `docs/BACKLOG.md` | Benchmark review, improvement proposals and open decisions |
| `docs/HANDOFF.md` | Handoff (Korean) for the local session: decisions, how to start, the remaining extractions, pitfalls, results |
| `sources/<period>/registry.csv` | Register of the published statements (kept in Google Drive): file ID, name, size, SHA-256, pages, status |
| `config/extraction/` | Per-insurer extraction specs: page, row, column, unit and sign for every line item |
| `extract/<period>/` | Values extracted from the statements, with provenance, and a review workbook in the capture layout |
| `tools/split_pdf.py` | Run on your own computer: split a large statement PDF into parts under 5 MB for the Drive connector, keeping the page ranges in the names |
| `tools/pdf_pages.py`, `tools/visual_spec.py`, `tools/pilot_values.py` | Extraction helpers: page sheets and page renders for scanned statements, spec builder for transcribed figures, pilot reference values |
| `docs/DEPLOY.md` | Publishing on GitHub Pages: routes, one-off setup, troubleshooting |
| `.github/workflows/pages.yml` | Validate on every push; publish to GitHub Pages from `main` |
| `docs/benchmark/` | The benchmark board this version was built against |

## Versioning

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-11 | First pipeline release: FY2025 + FY2024, 17 insurers, Samsung Life focus. Reproduces every figure on the benchmark board. |
| v1.1 | 2026-11 | GitHub Pages publishing: validation workflow, `site` step, per-period addresses, `noindex` by default |
| v1.2 | 2026-11 | Korean version: language switch at the top right (English / 한국어), remembered per browser and settable by `#lang=ko`; Korean review flags; translation completeness tests |
