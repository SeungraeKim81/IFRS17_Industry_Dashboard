# Benchmark review, improvement backlog and open decisions

## 1. What v1.0 changes against the benchmark

The benchmark files are `docs/benchmark/IFRS17_CSM_board_17companies_benchmark.html` and the capture
workbook `data/capture/IFRS17_extraction_FY2025_v11.xlsx`. The pipeline reproduces every figure on the
benchmark board; `tests/test_pipeline.py` checks this for all 17 insurers.

| Area | Benchmark | v1.0 |
|---|---|---|
| Process | Figures pasted by hand into the HTML as a JS array | Workbook → tidy CSV → validation gate → metrics → HTML, one command, tested |
| Highlighted insurer | Dhipaya Life, hard-coded | Samsung Life by default (`config/dashboard.json`), switchable on the page and by `--focus` |
| Years | FY2025 only, although the workbook also holds FY2024 | FY2025 with FY2024 comparatives: changes in the tiles, the table and the new-business strips |
| Focus view | Highlight colour only | KPI tiles with change, rank and benchmark; auto-generated headlines; notes and flags for the insurer |
| New content | Quadrant, service margin, profit bridge, table | Adds market position (3 shares), CSM roll-forward waterfall, new-business quality strips, data-quality matrix, definitions |
| Reconciliations | Workbook formulas; the board text says "five reconciliations" but lists six | Re-performed on the ingested data (6 checks incl. NB consistency), blocking, shown on the page |
| Plausibility | Notes written by hand | Rules raise flags automatically (release-ratio range, NB / release, negative accretion, onerous NB, loss years) |
| Narrative | Hard-coded numbers inside notes (e.g. Rabbit 110.8%, AIA 195,504m) | Notes hold no figures; numbers come from data. Notes live in `config/commentary.json` |
| Rendering defects | Notes contain literal `—` and `\n` sequences | Fixed by construction |
| Distribution | Loads Google Fonts | Fully self-contained; works offline and by email |
| Table | Static | Sortable; FY2025 / FY2024 / change views; CSV download |

Workbook observations (no figures affected):

- The `Notes` sheet still describes the two-insurer pilot ("Muang Thai Life & Tokio Marine Life").
- Generali's tax row is labelled `Income tax (credit)`; it is handled as an alias, but harmonising the label is cleaner.
- `Source Map (Quarter)` is filled only for 3 insurers; the 14 others are blank.

## 2. Improvement proposals (for discussion)

Priority reflects value to the Samsung Life perspective against extraction effort.

| # | Proposal | Value | New data needed | Effort |
|---|---|---|---|---|
| P1 | **Balance-sheet and capital view**: equity, total assets, insurance contract liabilities (BEL / RA / CSM). Gives ROE, CSM-to-equity, RA-to-BEL and an "equity + CSM after tax" value proxy | Profit is shown against revenue only today; owners also need profit against capital | ~8 line items per insurer (statement of financial position, insurance contracts note) | Medium |
| P1 | **RA confidence level** (IFRS 17.119 disclosure) and closing RA | Shows how prudent each insurer's RA is; also explains part of the margin gap between RA policy groups | 2 items per insurer | Low |
| P1 | **CSM run-off profile**: expected release by time band (IFRS 17.109) | Shows how long the stored profit lasts; sharper than the single release ratio | ~5 bands per insurer | Low to medium |
| P2 | **Measurement-model mix** (GMM / VFA / PAA share of revenue and CSM) | Explains release pace and sensitivity to markets (VFA) | Revenue and CSM by model | Medium |
| P2 | **Premium-based market share** from OIC / Thai Life Assurance Association statistics (first-year premium, APE, channel) | The market's usual lens; ties new-business CSM to sales volume and channel | External monthly statistics | Medium |
| P2 | **Quarterly cadence** using `Source Map (Quarter)` | Earlier signal; 4 releases a year | Quarterly statements; note map for 14 insurers | High (recurring) |
| P2 | **Samsung peer group** (see decision D2) | Sharper comparison than "top 10 vs the rest" | None | Low |
| P3 | **Multi-year trends** once FY2026 is captured (CSM growth path, NB margin trend) | Trend beats a single year of change, especially as FY2024 is a transition comparative | Next period | Low (automatic) |
| P3 | **Extraction assistance**: text extraction for PDFs with a text layer (Samsung, Thai Life), OCR suggestions for scanned ones, always confirmed by the extractor | Cuts the most manual step; the reconciliations stay as the control | None | Medium |
| P3 | **Reinsurance and loss-ratio view** (current-service loss ratio, reinsurance drag) | Underwriting quality detail; metrics already computed, not yet charted | None | Low |

## 3. Open decisions for the owner

| # | Decision | Options | v1.0 default |
|---|---|---|---|
| D1 | Distribution channel and audience | GitHub Pages link / email the HTML file / management pack | GitHub Pages (`docs/DEPLOY.md`), not indexed by search engines; the file can still be emailed |
| D2 | Samsung Life peer group | (a) the 7 smallest by revenue, as in the benchmark split; (b) a chosen set of foreign-owned mid-size insurers; (c) by main channel | All 17, with the focus highlighted; size break after the 10 largest |
| D3 | Which P1/P2 items go into v1.1 | See section 2 | None started |
| D4 | Language | English only / English + Thai labels | English |
| D5 | Cadence | Annual / semi-annual / quarterly | Annual |
| D6 | Branding | Neutral palette / Samsung Life corporate palette and logo | Neutral; colours sit in CSS variables at the top of the template, so a palette swap is one place |
