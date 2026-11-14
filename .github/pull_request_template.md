## Summary

<!-- What changes and why, in two or three sentences. Link the HANDOFF section if there is one. -->

**Changes**
1.

**Figures**
<!-- "No figure changes", or the baseline comparison: rows added / changed, max abs diff, which companies and metrics. A corrected extraction also says whether the benchmark fixtures were regenerated. -->

## Owner check before merging

Merging publishes to the public site within minutes, so check the preview first.

**Open the preview**
1. In the checks list below, click **Details** next to *Validate and publish / validate*.
2. Click **Summary** (top left), scroll to **Artifacts**, and download `dashboard-site`.
3. Unzip the file and open `index.html`. It works offline and is the same site that merging will publish.

**What to look at**
<!-- Concrete items: which period, section and language, and what should appear. -->
- [ ]
- [ ] No other section looks different from the live site

If anything is wrong, comment on this pull request and do not merge. Fixes go onto the same branch, and the preview is rebuilt.

## Test plan
- [ ] `python -m pipeline all` (all periods) and `python -m unittest discover -s tests`
- [ ] CI is green
- [ ] Rendered in light, dark and at 390px; no console errors or overlaps
