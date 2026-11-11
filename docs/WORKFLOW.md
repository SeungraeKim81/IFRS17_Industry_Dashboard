# Operating workflow

How one reporting period moves from published statements to a released
dashboard. The pipeline automates steps 4 to 7; steps 1 to 3 and 8 to 9 are
people's work, and the gates between them are what make the output
trustworthy.

## Roles

| Role | Responsibility |
|---|---|
| **Owner** | Sets scope and the focus insurer, approves release, owns the backlog |
| **Extractor** (analyst) | Collects the statements, writes the extraction specs and extracts, explains flags |
| **Reviewer** (second analyst / actuary) | Independent check of extraction and commentary (four-eyes) |
| **Maintainer** | Pipeline, template, tests, repository |

One person can hold more than one role, but **the extractor and the reviewer
must be different people** for any insurer.

## Steps and gates

| # | Step | Who | Output | Gate to pass |
|---|---|---|---|---|
| 1 | **Collect sources**: download each insurer's audited annual statements (SET filing, OIC annual disclosure or company website) | Extractor | Statement saved in Google Drive `FS_Life_Industry/Y<year>/<quarter>/` and registered in `sources/<period>/registry.csv` (Drive file ID, name, size, SHA-256, pages, text layer) | All 17 insurers have a source file, or the gap is agreed with the owner |
| 2 | **Locate notes**: find the statement of comprehensive income, the insurance revenue and expense note, the CSM roll-forward and the new-business table **by their headings** (`tools/pdf_pages.py sheet`/`page`, or `pdftotext` when there is a text layer). Last period's spec notes and `docs/HANDOFF.md` section 8 are the starting point; page numbers are never reused | Extractor | The page of each table, with the heading seen | Every table located by heading |
| 3 | **Extract**: write `config/extraction/<company_id>.json` (text layer: table anchors and row patterns; scanned: printed figures via `tools/visual_spec.py`, with per-page units, sign rules and sums), then `python -m pipeline extract` and `python -m pipeline verify-extract` | Extractor | `extract/<period>/<company_id>.json`; registry status `extracted` | 12/12 reconciliations per insurer; every difference from the previous source explained in the spec notes |
| 4 | **Ingest**: `python -m pipeline ingest` (source `extract` in `config/dashboard.json`) | Extractor | `data/<period>/line_items.csv` | Every insurer in `config/companies.csv` has an extraction with all line items |
| 5 | **Validate**: `python -m pipeline validate` | Extractor | `validation.csv`, `flags.csv` | **Blocking:** 6 reconciliations × 2 years × 17 insurers within 0.05m. **Advisory:** each flag is either explained in `config/commentary.json` or fixed at source |
| 6 | **Metrics**: `python -m pipeline metrics` | Maintainer | `metrics.csv`, `industry.csv` | Tests pass (`python -m unittest discover -s tests`) |
| 7 | **Build**: `python -m pipeline build` | Maintainer | `output/<period>/…html` | Opens without console errors, in light and dark mode and at phone width |
| 8 | **Review**: see the checklist below | Reviewer | Signed-off pull request | Checklist complete |
| 9 | **Release**: merge into `main` (publishes to GitHub Pages, see `docs/DEPLOY.md`), tag (`fy2025-v1`), share the link | Owner | Release | Owner approval; the publish run is green |

### The six reconciliations (step 5)

| Check | Identity |
|---|---|
| Revenue split | BEL release + RA release + CSM release + acquisition-cost recovery + PAA revenue + other revenue = total insurance revenue |
| Expense breakdown | incurred claims + past service + loss component + acquisition-cost amortisation = total insurance service expense |
| Net profit | insurance revenue + service expense + reinsurance + other expense + other income + net investment income + IFIE + tax = net profit |
| CSM roll-forward | opening + new business + accretion + future-service changes + release = closing |
| New-business CSM | PV inflows − PV acquisition − PV claims − RA + loss component = CSM from new business |
| NB consistency | new business in the roll-forward = CSM in the new-business note |

`verify-extract` runs the same six on each extraction before it reaches the pipeline. The sixth matters because
the two figures come from different notes and must agree.

### Review checklist (step 8)

- [ ] Focus insurer (Samsung Life): **every** line item traced to the statement, both years
- [ ] Every other insurer: at least 3 line items picked at random traced to the statement, including one CSM item
- [ ] Units: face and notes divisors confirmed for any insurer whose unit changed from last period
- [ ] RA disaggregation policy re-tested (AOC insurance-finance row, RA column) and `config/companies.csv` agrees
- [ ] Every plausibility flag explained (commentary) or fixed
- [ ] Commentary re-read: no stale statements carried from the previous period
- [ ] Dashboard opened and read through as a reader would; headlines for the focus insurer make sense

## Rolling to a new period

1. Register the new statements in `sources/<period>/registry.csv` and extract each insurer into
   `extract/<period>/` (steps 1 to 3). Start each spec from last period's: tables are re-located by heading, the
   page numbers of the old spec are only a starting point.
2. Set `period`, `comparative` and `period_end` in `config/dashboard.json`. Refresh the benchmark expectations
   with `tools/benchmark_fixture.py` once the figures are reviewed, and say so in the pull request.
3. Add or remove insurers in `config/companies.csv`; RA policy and units are re-confirmed every year.
4. Re-read `config/commentary.json`: retire notes that no longer apply, add new ones.
5. Run steps 1 to 9. Earlier periods stay in `data/<old period>/` and `output/<old period>/`.

### Adding a quarter

1. Extract each insurer's interim statement into `extract/<YYYYQn>/` (specs in
   `config/extraction/quarterly/<YYYYQn>/`; `verify-extract` checks the year-to-date identities, the three-month
   bridge and continuity with the prior year-end). A break the statement itself contains is recorded in the
   spec as an accepted break, with its difference and reason.
2. Add the period to `periods` in `config/dashboard.json`. The comparative is found by itself: the same
   quarter a year earlier, where it was extracted.
3. An insurer new to the pipeline needs a row in `config/companies.csv` (`annual` = no keeps it off the
   annual page until it is added there deliberately).
4. Run `python -m pipeline all` and the tests; commit `data/<period>/` and `output/<period>/` with the change.

Restated comparatives: the new period's column D holds the comparative **as restated** in the new statements.
The previous period's folder keeps the figures as originally reported, so both remain on record.

## Adding a line item or an indicator

- **Line item**: add a row to `config/line_items.csv`, then a rule for it in every extraction spec and re-extract.
  Extraction and ingest refuse to run until every insurer carries the new item.
- **Indicator**: add one entry to `METRICS` in `pipeline/metrics.py` (label, unit, direction, formula text,
  function), and its Korean label and definition under `metrics` in `config/i18n/ko.json`. It flows
  automatically to the CSV download and the definitions table. To chart it, edit the template.

## Languages

The page is in English and Korean. English is the source; the build stops if any Korean text is missing.

| Text | Where the Korean lives |
|---|---|
| Interface (headings, notes under headings, legends, buttons, tooltips, headlines) | `UI.ko` in `templates/dashboard.html`, next to `UI.en`; a test checks both have the same keys |
| Indicator names and definitions, reconciliation names, period and unit text | `config/i18n/ko.json` (the quarterly period end is written by the build; the quarterly caveat is `meta.quarterly_caveat`) |
| Commentary | `config/i18n/ko.json` → `commentary.<id>`, one entry per note in `config/commentary.json` |
| Review flags | `pipeline/validate.py` writes `message` and `message_ko` together |
| Insurer names, extraction notes | Not translated: names are kept as published; extraction notes are the analyst's English originals |

When commentary changes, update both languages in the same commit. Korean style: plain declarative (~다),
IFRS 17 terms as used in Korean practice (보험계약마진(CSM), 위험조정(RA), 보험서비스결과, 보험금융비용, CSM 상각).

## Conventions

- Units: THB million everywhere after ingest.
- Signs: revenue and income +, expense −; CSM release is negative in the roll-forward; new-business PV
  components are positive.
- FY = fiscal year ended 31 December (B.E. year = C.E. + 543).
- Indicator ranks: 1 = highest value, whatever the direction; the dashboard shows whether higher is better.
