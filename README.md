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
| Coverage | FY2025 with FY2024 comparatives (20 insurers), and the quarters 1Q2025 to 2Q2026 year to date (18 to 20 insurers, every insurer extracted), THB million |
| Output | One page per period, `output/<period>/Thai_Life_IFRS17_Dashboard_<period>.html` (FY2025, 2026Q2 ...): each a single file that works offline and can be emailed, linked to the other periods |
| Published | <https://seungraekim81.github.io/IFRS17_Industry_Dashboard/> (see `docs/DEPLOY.md`) |
| Languages | English and Korean (한국어), switched with the button at the top right; the choice is remembered in the browser |

## Quick start

Requires Python 3.10+ and `openpyxl` (`pip install -r requirements.txt`).

```bash
python -m pipeline all
```

That runs the four steps below for every period in `config/dashboard.json` (`periods`) and writes one
dashboard per period. `--period FY2025` or `--period 2026Q2` runs one period. Each step can also be run on its own:

```bash
python -m pipeline ingest      # extractions (extract/2025FY/*.json) -> data/FY2025/line_items.csv
python -m pipeline all --period 2026Q2   # one quarterly page (extract/2026Q2/ vs extract/2025Q2/)
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
 Published statements (PDF, registered in sources/<period>/registry.csv)
        │  extract     tables located by heading; figures read from the text layer or
        │              transcribed from page images (config/extraction/<company_id>.json)
        ▼
 extract/2025FY/<company_id>.json                    one per insurer, every value with its page
        │  1 ingest    the insurers in config/companies.csv; fail on a missing extraction or item
        ▼
 data/FY2025/line_items.csv                          tidy: company × year × line item
        │  2 validate  6 reconciliations × 2 years × 20 insurers must tie (0.05m)
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

**Quarterly pages** (2025Q1 to 2026Q2) run the same steps on `extract/<YYYYQn>/`. They show every insurer
extracted for the quarter, year to date, against the same quarter a year earlier where it was extracted
(the 2025 quarters have none). The CSM release ratio is annualised (× 12 / months to date); industry
changes are like for like over the insurers present in both periods (`industry_common.csv`); the
three-month profit or loss (`line_items_3m.csv`) has its own table. A value the statement does not
disclose is n/a, and a break the statement itself contains passes only as an accepted break
(`accepted_breaks.csv`).

## Dashboard sections

1. **Focus**: KPI tiles for the highlighted insurer, each with its change from the prior year, rank and industry
   benchmark, plus auto-generated headlines and any notes or review flags that apply to it
2. **Market position**: insurance revenue, closing CSM and new-business CSM with market shares
3. **CSM movement analysis**: roll-forward waterfall (focus vs industry, opening = 100) and the CSM sustainability quadrant
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
| `config/companies.csv` | Insurer master: the insurers on the dashboard, names, RA policy, source units (the workbook sheet is used only by the pilot reference) |
| `config/line_items.csv` | The 30 line items, their labels and sign convention |
| `config/commentary.json` | Analyst comparability notes (tagged to insurers where they apply) |
| `config/i18n/ko.json` | Korean text for everything that comes from data: indicator names and definitions, reconciliation names, commentary, period and unit text |
| `data/capture/` | The pilot capture workbook (reference only since the switch to the extractions; `docs/pilot/`) |
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
| `docs/benchmark/`, `docs/pilot/` | The pilot benchmark board and pilot values, kept for reference. The regression expectations are `tests/fixtures/<period>_benchmark.json` (`tools/benchmark_fixture.py`) |

## Versioning

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-11 | First pipeline release: FY2025 + FY2024, 17 insurers, Samsung Life focus. Reproduces every figure on the benchmark board. |
| v1.1 | 2026-11 | GitHub Pages publishing: validation workflow, `site` step, per-period addresses, `noindex` by default |
| v1.2 | 2026-11 | Korean version: language switch at the top right (English / 한국어), remembered per browser and settable by `#lang=ko`; Korean review flags; translation completeness tests |
| v1.4 | 2026-11 | Annual page covers all 20 insurers extracted for FY2025 (adds BUI, Phillip, Saha); benchmark expectations regenerated |
| v1.3 | 2026-11 | Quarterly pages 1Q2025 to 2Q2026 (year to date, every insurer extracted, annualised release ratio, like-for-like industry change, three-month table); period links on every page; not-disclosed values shown as n/a |
