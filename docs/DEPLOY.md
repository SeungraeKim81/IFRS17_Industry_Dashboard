# Publishing on GitHub Pages

Set up the same way as the earnings tracker
(<https://seungraekim81.github.io/earnings-tracker/>): on every push,
`.github/workflows/pages.yml` does the following:

1. **Validate**: rebuilds from the committed extractions (`python -m pipeline all`), runs the six reconciliations
   and the tests (including the benchmark regression), and checks that the committed `data/` matches a fresh
   run. If any of these fails, nothing is published and the site keeps its previous version.
2. **Publish** (pushes to `main` only): runs `python -m pipeline site`, which collects **only the built
   dashboards**, and deploys them to GitHub Pages. The extractions, CSVs, pipeline code and docs are not part of
   the site.

Pull requests and other branches are validated but never published.

Site address once live: **<https://seungraekim81.github.io/IFRS17_Industry_Dashboard/>**

| Address | Content |
|---|---|
| `/` | The front page: the period named by `site_root` in `config/dashboard.json` (2026Q2; falls back to `period`) |
| `/FY2025/` | The FY2025 dashboard. Every period gets its own lasting address |
| `/#focus=Dhipaya%20Life` | Opens with another insurer highlighted |
| `/#lang=ko` | Opens in Korean (the language button at the top right does the same, and the browser remembers it) |

---

## 1. Decide before publishing

A GitHub Pages site is **public on the internet**, whatever the repository's visibility.

| Item | What becomes visible | Note |
|---|---|---|
| The dashboard | Every figure, the commentary and Samsung Life as the highlighted insurer | Highlighting shows whose perspective the page takes. Change `focus_company` if that should not be public |
| Search engines | Not indexed by default (`"search_engine_indexing": false` puts `noindex` on the page) | Anyone with the link can still open it. Set it to `true` to allow indexing |
| Repository (only if made public) | All files and **the whole commit history**: capture workbook, extraction notes, benchmark board, docs | Needed only for route A below |
| Secrets | None in the repository | |

## 2. Choose a route

This repository is **private**. GitHub Pages on a private repository needs a paid plan (GitHub Pro, Team or
Enterprise).

| Route | Do this | Result |
|---|---|---|
| **A. Make the repository public** (same as the earnings tracker) | Settings → General → Danger Zone → **Change repository visibility** → Change to public | Works on the free plan. The repository becomes public too (see section 1) |
| **B. Keep the repository private** (paid plan) | Settings → Secrets and variables → Actions → **Variables** tab → **New repository variable**: name `PAGES_FROM_PRIVATE`, value `true` | Only the site is public; the repository stays private |

## 3. Turn on GitHub Pages (once)

1. Settings → **Pages**
2. **Build and deployment → Source**: select **GitHub Actions** (not "Deploy from a branch", which would
   publish without validation). There is no save button; the choice applies at once.

## 4. Create `main` and publish the first time

The repository has no `main` branch yet; the work sits on `claude/eloquent-goodall-jcg173`.

1. Create `main` from that branch: on the repository page, **branch menu → View all branches → New branch**,
   name `main`, source `claude/eloquent-goodall-jcg173`. (Or ask Claude to create it.)
2. Settings → General → **Default branch** → switch to `main`.
3. The push that creates `main` starts the workflow. If it ran before Pages was switched on, rerun it:
   **Actions → Validate and publish → Run workflow → Branch `main`**.

After one to two minutes the run shows a green tick, and the **deploy** box shows the site address.
Settings → Pages also shows "Your site is live at …".

If the deploy job is then rejected straight away, check the `github-pages` environment rule (section 6).

Later changes go through a pull request into `main`. Merging it publishes automatically.

## 5. Updating the site

- New figures or commentary: correct the extraction spec (`config/extraction/`) and re-run `python -m pipeline extract`,
  or edit the config; run `python -m pipeline all` and the tests, commit,
  merge into `main`. The site updates in one to two minutes.
- Check the preview before merging, because merging publishes. Every pull request's
  *Validate and publish / validate* run uploads the built site as the `dashboard-site`
  artifact (kept 14 days): on the pull request's **Checks** tab click *Validate and
  publish* (on: pull_request), download it under Artifacts, unzip and open `index.html`.
  It is the same site that merging will publish. On your own computer,
  `python3 tools/preview_pr.py <number> --compare` downloads it into `_preview/` and lists
  the pages that differ from the live site. The pull
  request template (`.github/pull_request_template.md`) lists what to look at. If
  something is wrong, comment on the pull request and fix it on the same branch; the
  preview is rebuilt with each push.
- New period: follow "Rolling to a new period" in `docs/WORKFLOW.md`. The previous period stays at its own address.
- If the site looks unchanged, do a hard refresh (Windows `Ctrl+Shift+R`, Mac `Cmd+Shift+R`).

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Site address returns 404 | Pages not switched on, or no deploy yet | Sections 3 and 4 |
| deploy step: "Get Pages site failed" / "Not Found" | Source is not set to GitHub Actions | Section 3 |
| deploy job fails in about 2 seconds with no log | The `github-pages` environment does not allow `main` to deploy (it can keep the default branch from when Pages was switched on) | Settings → Environments → `github-pages` → Deployment branches and tags: add `main`, then re-run the failed job |
| deploy step greyed out (skipped) | Repository private without `PAGES_FROM_PRIVATE`, or not on `main` | Section 2 / merge into `main` |
| validate fails at "Committed data matches" | `data/` was edited by hand or not regenerated | Run `python -m pipeline all`, commit `data/` and `output/` |
| validate fails at "Rebuild" with a reconciliation failure | An extraction no longer ties | Fix the extraction spec against the statement and re-extract. The site keeps its previous version |

To take the site down: Settings → Pages → **Unpublish site**.
