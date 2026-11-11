"""Step 5 (publishing only) - collect the files GitHub Pages serves into _site/.

  _site/index.html            the front page: config/dashboard.json "site_root" (else "period")
  _site/<period>/index.html   every built period (annual and quarterly), so each keeps a stable address;
                              the same page also under its file name, which the period links on each page use
  _site/.nojekyll             serve files as they are

Only the built dashboards are published. The capture workbook, the CSVs, the
pipeline and the docs stay in the repository.
"""
from __future__ import annotations

import shutil

from .common import OUTPUT, ROOT, load_settings

SITE = ROOT / "_site"


def run(period: str | None = None) -> None:
    s = load_settings()
    current = period or s.get("site_root", s["period"])
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    built = sorted(p for p in OUTPUT.glob("*/Thai_Life_IFRS17_Dashboard_*.html"))
    if not any(p.parent.name == current for p in built):
        raise SystemExit(f"site: no built dashboard for {current}; run `python -m pipeline all` first")
    for p in built:
        (SITE / p.parent.name).mkdir()
        shutil.copyfile(p, SITE / p.parent.name / "index.html")
        shutil.copyfile(p, SITE / p.parent.name / p.name)
        if p.parent.name == current:
            shutil.copyfile(p, SITE / "index.html")
    (SITE / ".nojekyll").touch()
    print(f"site: _site/index.html = {current}; periods: {', '.join(p.parent.name for p in built)}")
