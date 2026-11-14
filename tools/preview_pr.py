"""Download the site a pull request would publish, so it can be checked before merging.

Merging into main publishes the site. Every pull request's "Validate and publish" run uploads
the built site as the `dashboard-site` artifact; this script fetches the one for the pull
request's latest commit into `_preview/` (gitignored, replaced on each run) and, with
--compare, says which pages differ from the live site (build stamps ignored).

Needs the GitHub CLI (`gh`), signed in, and `curl` (Mac, Windows 10+). Run on your own computer:

  python3 tools/preview_pr.py 11 --compare

Then open `_preview/index.html` in a browser, or serve the folder (any static server).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / "_preview"
WORKFLOW = "pages.yml"
ARTIFACT = "dashboard-site"
LIVE = "https://seungraekim81.github.io/IFRS17_Industry_Dashboard/"

# the build stamp in the page's data block changes on every build; it is not content
STAMP = re.compile(r'"(?:generated|git)":"[^"]*"')


def strip_stamp(html: str) -> str:
    return STAMP.sub("", html)


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def latest_run(pr: int) -> dict:
    head = json.loads(gh("pr", "view", str(pr), "--json", "headRefOid,headRefName,state"))
    runs = json.loads(gh("run", "list", "--workflow", WORKFLOW, "--commit", head["headRefOid"],
                         "--event", "pull_request", "--limit", "1",
                         "--json", "databaseId,status,conclusion,url"))
    if not runs:
        sys.exit(f"PR #{pr} ({head['headRefName']}): no '{WORKFLOW}' run for its latest commit yet")
    run = runs[0]
    if run["status"] != "completed":
        sys.exit(f"PR #{pr}: the run is still {run['status']}; try again when it finishes ({run['url']})")
    if run["conclusion"] != "success":
        sys.exit(f"PR #{pr}: the run ended '{run['conclusion']}', so there is no site to preview ({run['url']})")
    return run


def compare(live: str) -> None:
    for p in sorted(PREVIEW.rglob("index.html")):
        rel = p.relative_to(PREVIEW).as_posix()
        # curl uses the system's certificates (python.org builds of Python on a Mac have none)
        r = subprocess.run(["curl", "-sSfL", "--max-time", "30", live + rel], capture_output=True)
        if r.returncode:
            print(f"  {rel:<22} not on the live site ({r.stderr.decode(errors='replace').strip()})")
            continue
        on_site = r.stdout.decode("utf-8")
        same = strip_stamp(p.read_text(encoding="utf-8")) == strip_stamp(on_site)
        print(f"  {rel:<22} {'same as live' if same else 'CHANGED'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--compare", action="store_true", help="compare each page with the live site")
    ap.add_argument("--live", default=LIVE, help="live site address (default: %(default)s)")
    a = ap.parse_args()

    run = latest_run(a.pr)
    if PREVIEW.exists():
        shutil.rmtree(PREVIEW)
    gh("run", "download", str(run["databaseId"]), "--name", ARTIFACT, "--dir", str(PREVIEW))
    pages = sorted(p.relative_to(PREVIEW).as_posix() for p in PREVIEW.rglob("index.html"))
    print(f"PR #{a.pr}: {len(pages)} pages from {run['url']}\n  -> {PREVIEW / 'index.html'}")
    if a.compare:
        compare(a.live.rstrip("/") + "/")


if __name__ == "__main__":
    main()
