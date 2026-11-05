# Operating workflow

How one reporting period moves from published statements to a released
dashboard. The pipeline automates steps 4 to 7; steps 1 to 3 and 8 to 9 are
people's work, and the gates between them are what make the output
trustworthy.

## Roles

| Role | Responsibility |
|---|---|
| **Owner** | Sets scope and the focus insurer, approves release, owns the backlog |
| **Extractor** (analyst) | Collects the statements, fills the capture workbook, explains flags |
| **Reviewer** (second analyst / actuary) | Independent check of extraction and commentary (four-eyes) |
| **Maintainer** | Pipeline, template, tests, repository |

One person can hold more than one role, but **the extractor and the reviewer
must be different people** for any insurer.

## Steps and gates

| # | Step | Who | Output | Gate to pass |
|---|---|---|---|---|
| 1 | **Collect sources**: download each insurer's audited annual statements (SET filing, OIC annual disclosure or company website) | Extractor | `data/<period>/sources.csv` filled (URL, date retrieved, file name, SHA-256, text layer or scanned) | All 17 insurers have a source file, or the gap is agreed with the owner |
| 2 | **Locate notes**: use `Source Map (Annual)` and `Note Anchors` in the workbook. Search by the on-page heading, not the page number; record the new page and year | Extractor | Updated Source Map and Note Anchors | Every note located by heading |
| 3 | **Extract** into the insurer's sheet: current year in C, comparative in D, status in E, note/page in F. Convert to THB million with the face/notes divisors; apply the sign rule (revenue +, expense −) | Extractor | Capture workbook | Workbook's own `OK/CHECK` cells all `OK` |
| 4 | **Ingest**: `python -m pipeline ingest` | Extractor | `data/<period>/line_items.csv` | No unknown or missing line items, every value numeric |
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

The first five are the workbook's own checks. The sixth is added because the
two figures come from different notes and must agree.

### Review checklist (step 8)

- [ ] Focus insurer (Samsung Life): **every** line item traced to the statement, both years
- [ ] Every other insurer: at least 3 line items picked at random traced to the statement, including one CSM item
- [ ] Units: face and notes divisors confirmed for any insurer whose unit changed from last period
- [ ] RA disaggregation policy re-tested (AOC insurance-finance row, RA column) and `config/companies.csv` agrees
- [ ] Every plausibility flag explained (commentary) or fixed
- [ ] Commentary re-read: no stale statements carried from the previous period
- [ ] Dashboard opened and read through as a reader would; headlines for the focus insurer make sense

## Rolling to a new period

1. Copy the capture workbook to `data/capture/IFRS17_extraction_<period>_v1.xlsx`. Clear columns C:F, set the
   headers in row 4 (C = new year, D = comparative), keep Source Map and Note Anchors (page numbers become "last seen").
2. Set `period`, `comparative`, `period_end` and `capture_workbook` in `config/dashboard.json`.
3. Add or remove insurers in `config/companies.csv`; RA policy and units are re-confirmed every year.
4. Re-read `config/commentary.json`: retire notes that no longer apply, add new ones.
5. Run steps 1 to 9. Earlier periods stay in `data/<old period>/` and `output/<old period>/`.

Restated comparatives: the new period's column D holds the comparative **as restated** in the new statements.
The previous period's folder keeps the figures as originally reported, so both remain on record.

## Adding a line item or an indicator

- **Line item**: add a row to the template block (rows 5 to 34) of every insurer sheet, then a row to
  `config/line_items.csv` (label and aliases). Ingest refuses to run until every sheet carries the new item.
- **Indicator**: add one entry to `METRICS` in `pipeline/metrics.py` (label, unit, direction, formula text,
  function), and its Korean label and definition under `metrics` in `config/i18n/ko.json`. It flows
  automatically to the CSV download and the definitions table. To chart it, edit the template.

## Languages

The page is in English and Korean. English is the source; the build stops if any Korean text is missing.

| Text | Where the Korean lives |
|---|---|
| Interface (headings, notes under headings, legends, buttons, tooltips, headlines) | `UI.ko` in `templates/dashboard.html`, next to `UI.en`; a test checks both have the same keys |
| Indicator names and definitions, reconciliation names, period and unit text | `config/i18n/ko.json` |
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
