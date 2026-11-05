"""Run with:  python -m unittest discover -s tests -v   (from the repository root)"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import openpyxl

from pipeline import build, ingest, metrics, validate
from pipeline.common import ROOT, load_settings

PERIOD = load_settings()["period"]
WORKBOOK = ROOT / load_settings()["capture_workbook"]
BENCHMARK = ROOT / "docs" / "benchmark" / "IFRS17_CSM_board_17companies_benchmark.html"


def setUpModule():
    ingest.run(PERIOD)
    validate.run(PERIOD)
    metrics.run(PERIOD)


class TestIngest(unittest.TestCase):
    def test_every_company_and_item_present(self):
        rows, notes = ingest.ingest(WORKBOOK, PERIOD)
        self.assertEqual(len(notes), 17)
        self.assertEqual(len(rows), 17 * 2 * 30)

    def test_samsung_values(self):
        v = metrics.load_values(PERIOD)[("Samsung Life", PERIOD)]
        self.assertAlmostEqual(v["insurance_revenue"], 2321.096)
        self.assertAlmostEqual(v["csm_close"], 5151.677)
        self.assertAlmostEqual(v["csm_release"], -740.036)

    def test_unknown_label_stops_the_run(self):
        tmp = Path(tempfile.mkdtemp()) / "wb.xlsx"
        shutil.copy(WORKBOOK, tmp)
        wb = openpyxl.load_workbook(tmp)
        wb["Samsung Life"]["B9"] = "Claims incurred (renamed)"
        wb.save(tmp)
        with self.assertRaises(ingest.IngestError) as e:
            ingest.ingest(tmp, PERIOD)
        self.assertIn("unknown line item", str(e.exception))


class TestValidate(unittest.TestCase):
    def test_all_reconciliations_pass(self):
        checks, _ = validate.validate(PERIOD)
        self.assertEqual(len(checks), 17 * 2 * len(validate.RECONCILIATIONS))
        self.assertEqual([c for c in checks if c["result"] != "OK"], [])

    def test_known_flags_raised(self):
        _, flags = validate.validate(PERIOD)
        got = {(f["company"], f["fiscal_year"], f["flag"]) for f in flags}
        self.assertIn(("T Life", "FY2025", "negative_accretion"), got)
        self.assertIn(("CHUBB Life", "FY2025", "nb_to_release"), got)


class TestMetricsAgainstBenchmark(unittest.TestCase):
    """The FY2025 figures must reproduce the benchmark board exactly (to its 4 dp)."""

    @classmethod
    def setUpClass(cls):
        html = BENCHMARK.read_text(encoding="utf-8")
        cls.bench = {r["name"]: r for r in json.loads(re.search(r"const D = (\[.*?\]);", html).group(1))}
        cls.m = {}
        for r in metrics.compute(PERIOD):
            if r["fiscal_year"] == PERIOD:
                cls.m.setdefault(r["company"], {})[r["metric"]] = float(r["value"])

    def test_benchmark_values(self):
        pairs = [("ism", "ism_gross", 100), ("relRatio", "release_ratio", 1), ("nbRel", "nb_to_release", 1),
                 ("a", "ism_net", 100), ("b", "inv_margin", 100), ("c", "other_ratio", 100),
                 ("d", "tax_ratio", 100), ("npm", "npm", 100)]
        self.assertEqual(set(self.bench), set(self.m))
        for name, b in self.bench.items():
            for bk, mk, scale in pairs:
                with self.subTest(company=name, metric=mk):
                    self.assertAlmostEqual(self.m[name][mk] * scale, b[bk], places=3)
            self.assertAlmostEqual(self.m[name]["csm_close"], b["csmClose"], places=3)
            self.assertAlmostEqual(self.m[name]["insurance_revenue"], b["rev"], places=3)


class TestBuild(unittest.TestCase):
    def test_payload_and_render(self):
        data = build.payload(PERIOD)
        self.assertEqual(data["meta"]["default_focus"], "Samsung Life")
        self.assertEqual(len(data["companies"]), 17)
        html = build.render(data)
        self.assertNotIn("__DATA__", html)
        self.assertNotIn("</script><", html.split('id="data"')[1].split("</script>")[0])

    def test_unknown_focus_rejected(self):
        with self.assertRaises(SystemExit):
            build.payload(PERIOD, "Not An Insurer")


if __name__ == "__main__":
    unittest.main()
