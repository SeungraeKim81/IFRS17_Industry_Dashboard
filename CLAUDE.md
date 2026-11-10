# Notes for Claude

Thai life insurance IFRS 17 industry dashboard: a Python pipeline that turns
the analyst capture workbook into one self-contained HTML page. See
`README.md` for the layout and commands and `docs/WORKFLOW.md` for the process.

**Work in progress:** the data layer is moving from the pilot workbook to the
insurers' published statements (`sources/`). Read `docs/HANDOFF.md` first: it
holds the decisions made so far, the sample test to run next and the
extraction pitfalls.

- Samsung Life is the default highlighted insurer (`config/dashboard.json`,
  `focus_company`). Do not change it unless the owner asks.
- Run `python -m pipeline all` and `python -m unittest discover -s tests` before
  every commit. Commit the regenerated `data/<period>/*.csv` and
  `output/<period>/*.html` together with the change that caused them.
- Do not edit `data/<period>/*.csv` by hand: they are generated from the
  capture workbook. Fix figures in the workbook and re-run.
- The benchmark-regression test (`TestMetricsAgainstBenchmark`) must keep
  passing for FY2025. If a figure changes on purpose (a corrected extraction),
  say so in the pull request and update the test's expectation deliberately.
- Indicators are defined once in `pipeline/metrics.py` (`METRICS`); the
  dashboard's definitions table is generated from it.
- Commentary in `config/commentary.json` holds no figures; numbers on the page
  come from data so they cannot go stale.
- The template uses no external scripts, fonts or styles, so the output works
  offline. Keep it that way. Colours are CSS variables at the top of
  `templates/dashboard.html`, with light and dark values.
- The page is bilingual (English / Korean). Every interface string goes into
  both `UI.en` and `UI.ko` in the template; data-driven text into
  `config/i18n/ko.json`. The build and tests fail on a missing translation.
  See "Languages" in `docs/WORKFLOW.md`.
- Check a template change by rendering it with Playwright (light, dark,
  390px wide) and looking for console errors and overlaps.
- Publishing: `.github/workflows/pages.yml` validates every push and deploys
  `_site/` (from `python -m pipeline site`) to GitHub Pages from `main` only.
  Only built dashboards go on the site. See `docs/DEPLOY.md`.
- Work on the designated branch; open a pull request only when the owner asks.
