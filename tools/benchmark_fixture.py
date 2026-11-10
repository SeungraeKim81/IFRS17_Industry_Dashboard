"""Write the benchmark regression's expected values from the current metrics.

The regression test (tests/test_pipeline.py, TestMetricsAgainstBenchmark) checks that the dashboard
reproduces these figures to 3 decimals. They were first taken from the pilot benchmark board
(docs/benchmark/); since the switch to the extractions from the published statements they are kept
here. Regenerate ONLY when a figure changes on purpose (a corrected extraction, a change of basis),
and list the changed values in the commit message:

  python3 tools/benchmark_fixture.py [--period FY2025]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import metrics  # noqa: E402
from pipeline.common import load_settings  # noqa: E402

# board field -> (metric, scale), as on the pilot benchmark board
FIELDS = {"rev": ("insurance_revenue", 1), "csmClose": ("csm_close", 1), "ism": ("ism_gross", 100),
          "relRatio": ("release_ratio", 1), "nbRel": ("nb_to_release", 1), "a": ("ism_net", 100),
          "b": ("inv_margin", 100), "c": ("other_ratio", 100), "d": ("tax_ratio", 100), "npm": ("npm", 100)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", default=load_settings()["period"])
    a = ap.parse_args()
    m: dict[str, dict[str, float]] = {}
    for r in metrics.compute(a.period):
        if r["fiscal_year"] == a.period:
            m.setdefault(r["company"], {})[r["metric"]] = float(r["value"])
    rows = [{"name": c, **{k: round(m[c][mk] * s, 4) for k, (mk, s) in FIELDS.items()}} for c in sorted(m)]
    out = ROOT / "tests" / "fixtures" / f"{a.period}_benchmark.json"
    out.write_text(json.dumps({"period": a.period, "source": load_settings().get("source", "workbook"),
                               "companies": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"benchmark fixture: {len(rows)} insurers -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
