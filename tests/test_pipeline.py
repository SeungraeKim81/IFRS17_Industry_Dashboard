"""Run with:  python -m unittest discover -s tests -v   (from the repository root)"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import openpyxl

from pipeline import build, ingest, metrics, validate
from pipeline.common import ROOT, load_settings, read_csv

PERIOD = load_settings()["period"]
WORKBOOK = ROOT / load_settings()["capture_workbook"]
BENCHMARK = ROOT / "tests" / "fixtures" / f"{PERIOD}_benchmark.json"  # tools/benchmark_fixture.py


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

    def test_extractions_give_every_company_and_item(self):
        rows, notes, rows_3m, _ = ingest.ingest_extractions(PERIOD)
        self.assertEqual(rows_3m, [])  # annual: no three-month profit or loss
        self.assertEqual(len(notes), 17)
        self.assertEqual(len(rows), 17 * 2 * 30)
        self.assertEqual({r["status"] for r in rows}, {"Extracted"})
        self.assertTrue(all(re.match(r"(file )?p\.\d+ ", r["source"]) for r in rows))  # where each value was read

    def test_quarterly_extractions(self):
        """A quarter takes every insurer extracted; the comparative is the same quarter a year earlier, where extracted."""
        rows, notes, rows_3m, _ = ingest.ingest_extractions("2026Q2")
        per_year = {}
        for r in rows:
            per_year.setdefault(r["fiscal_year"], set()).add(r["company"])
        self.assertEqual(len(notes), len(per_year["2026Q2"]))
        self.assertTrue(per_year["2025Q2"] < per_year["2026Q2"])  # fewer insurers extracted for 2025Q2
        self.assertEqual({r["code"] for r in rows_3m}, {"insurance_revenue", "insurance_service_expense",
                         "reinsurance_result", "net_investment_income", "ifie", "other_expense", "other_income",
                         "income_tax", "net_profit"})
        nd = [r for r in rows if r["status"] == "Not disclosed"]
        self.assertTrue(nd and all(r["value"] == "" for r in nd))
        self.assertEqual(ingest.extract_period("2026Q2"), "2026Q2")
        self.assertEqual(ingest.extract_period("FY2025"), "2025FY")

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


class TestNotDisclosed(unittest.TestCase):
    def test_indicator_needing_a_missing_item_is_none(self):
        from pipeline.common import load_line_items
        v = {it["code"]: 1.0 for it in load_line_items()}
        v["nb_pv_acq"] = None
        acq = metrics.METRIC_INDEX["acq_cost_ratio"][6]
        npm = metrics.METRIC_INDEX["npm"][6]
        self.assertIsNone(metrics.evaluate(acq, v))
        self.assertEqual(metrics.evaluate(npm, v), 1.0)
        nb = next(r for r in validate.RECONCILIATIONS if r[0] == "nb_csm")
        self.assertIsNone(metrics.evaluate(nb[2], v))  # reported N/A by the validation gate, not failed


class TestQuarterly(unittest.TestCase):
    """Quarterly pages: annualised release ratio, accepted breaks, like-for-like industry figures."""

    @classmethod
    def setUpClass(cls):
        cls.period = "2026Q1"
        ingest.run(cls.period)
        validate.run(cls.period)
        metrics.run(cls.period)

    def test_release_ratio_is_annualised(self):
        self.assertAlmostEqual(metrics.annualise("release_ratio", 0.02, "2026Q1"), 0.08)
        self.assertAlmostEqual(metrics.annualise("release_ratio", 0.04, "2026Q2"), 0.08)
        self.assertAlmostEqual(metrics.annualise("release_ratio", 0.08, "FY2025"), 0.08)
        self.assertAlmostEqual(metrics.annualise("npm", 0.02, "2026Q1"), 0.02)  # only listed flows

    def test_accepted_breaks_pass_only_as_recorded(self):
        checks, _ = validate.validate(self.period)
        acc = [c for c in checks if c["result"] == "ACCEPTED"]
        self.assertTrue(acc)
        self.assertTrue(all(c["fiscal_year"] == "2025Q1" for c in acc))  # 1Q2025 statements, the comparative
        self.assertEqual([c for c in checks if c["result"] == "FAIL"], [])
        self.assertEqual(validate._result(1.0, {"difference": "1.0"}, 0.05), "ACCEPTED")
        self.assertEqual(validate._result(2.0, {"difference": "1.0"}, 0.05), "FAIL")

    def test_like_for_like_industry(self):
        common = read_csv(ROOT / "data" / self.period / "industry_common.csv")
        n = {r["fiscal_year"]: int(r["n"]) for r in common if r["metric"] == "insurance_revenue"}
        allrows = read_csv(ROOT / "data" / self.period / "industry.csv")
        n_all = {r["fiscal_year"]: int(r["n"]) for r in allrows if r["metric"] == "insurance_revenue"}
        self.assertEqual(n["2026Q1"], n["2025Q1"])  # same insurers in both years
        self.assertLess(n["2026Q1"], n_all["2026Q1"])


class TestMetricsAgainstBenchmark(unittest.TestCase):
    """The FY2025 figures must reproduce the benchmark expectations (to 3 dp).

    The expectations were the pilot benchmark board (docs/benchmark/, kept for reference); since the
    switch to the extractions they are tests/fixtures/<period>_benchmark.json. Regenerate them with
    tools/benchmark_fixture.py only when a figure changes on purpose, and say so in the pull request."""

    @classmethod
    def setUpClass(cls):
        cls.bench = {r["name"]: r for r in json.loads(BENCHMARK.read_text(encoding="utf-8"))["companies"]}
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


class TestTranslations(unittest.TestCase):
    def test_data_translations_complete(self):
        data = build.payload(PERIOD)
        for lang in data["i18n"]:
            with self.subTest(lang=lang):
                self.assertEqual(build.missing_translations(data, lang), [])

    def test_interface_keys_match(self):
        """UI.en and every other UI.<lang> in the template define the same keys."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        tpl = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
        block = tpl[tpl.index("const UI = {"):tpl.index("const TR = ")]
        script = ("const nf=(v,d)=>String(v);" + block +
                  "const out={};for(const l in UI){out[l]={keys:Object.keys(UI[l]).sort(),"
                  "cols:Object.keys(UI[l].cols).sort(),toc:UI[l].toc.length,wf:UI[l].wf.length}}"
                  "console.log(JSON.stringify(out));")
        res = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
        out = json.loads(res.stdout)
        self.assertIn("ko", out)
        for lang, v in out.items():
            with self.subTest(lang=lang):
                self.assertEqual(v, out["en"])


class TestExtractions(unittest.TestCase):
    """Extractions from the published statements (extract/<period>/*.json)."""

    files = sorted((ROOT / "extract").glob("*/*.json"))

    def test_extractions_reconcile(self):
        from pipeline import verify_extract
        self.assertTrue(self.files)
        for f in self.files:
            ex = verify_extract.load(f)
            with self.subTest(company=ex["company"], period=ex["period"]):
                self.assertEqual(len(ex["items"]), 30)
                self.assertEqual([r for r in verify_extract.reconcile(ex) if not r["ok"]], [])
                if ex.get("ytd_months"):  # quarterly: three-month bridge and continuity with the prior year-end
                    self.assertEqual(set(ex["items_3m"]), set(verify_extract.PL_3M))
                    self.assertEqual([r for r in verify_extract.reconcile_3m(ex) if not r["ok"]], [])
                    self.assertTrue(verify_extract.continuity(ex)["ok"])

    def test_quarterly_checks_catch_a_break(self):
        """A three-month profit or loss that does not tie, or an opening CSM off the prior closing, fails."""
        from pipeline import verify_extract
        pl = {c: 10.0 for c in verify_extract.PL_3M}
        pl["net_profit"] = 80.0  # eight lines of 10
        ex = {"items_3m": {c: {"2026Q1": {"value": x}} for c, x in pl.items()}}
        self.assertTrue(verify_extract.reconcile_3m(ex)[0]["ok"])
        ex["items_3m"]["net_profit"]["2026Q1"]["value"] = 81.0
        self.assertFalse(verify_extract.reconcile_3m(ex)[0]["ok"])
        close = json.loads((ROOT / "extract" / "2025FY" / "samsung-life.json").read_text(encoding="utf-8"))
        close = close["items"]["csm_close"]["FY2025"]["value"]
        q = {"period": "2026Q1", "company_id": "samsung-life", "items": {"csm_open": {"2026Q1": {"value": close}}}}
        self.assertTrue(verify_extract.continuity(q)["ok"])
        q["items"]["csm_open"]["2026Q1"]["value"] = close + 1.0
        self.assertFalse(verify_extract.continuity(q)["ok"])
        q["company_id"] = "no-such-insurer"
        self.assertFalse(verify_extract.continuity(q)["ok"])
        # No 2024FY extraction: 2025Q1 falls back to the FY2024 comparative column of the 2025FY extraction.
        fy = json.loads((ROOT / "extract" / "2025FY" / "samsung-life.json").read_text(encoding="utf-8"))
        close24 = fy["items"]["csm_close"]["FY2024"]["value"]
        q = {"period": "2025Q1", "company_id": "samsung-life", "items": {"csm_open": {"2025Q1": {"value": close24}}}}
        result = verify_extract.continuity(q)
        self.assertTrue(result["ok"])
        self.assertIn("comparative in 2025FY", result["note"])
        q["items"]["csm_open"]["2025Q1"]["value"] = close24 + 1.0
        self.assertFalse(verify_extract.continuity(q)["ok"])
        # an accepted break passes only at the recorded difference
        q["accepted_breaks"] = [{"check": "continuity", "difference": 1.0, "reason": "restated opening"}]
        self.assertTrue(verify_extract.continuity(q)["ok"])
        q["items"]["csm_open"]["2025Q1"]["value"] = close24 + 2.0
        self.assertFalse(verify_extract.continuity(q)["ok"])

    def test_not_disclosed_items_use_the_memo_total(self):
        """Acquisition and other outflows not split: the printed total stands in; without it the check fails."""
        from pipeline import verify_extract
        from pipeline.common import load_line_items
        v = {it["code"]: 0.0 for it in load_line_items()}
        v.update({"nb_pv_premium": 100.0, "nb_pv_acq": None, "nb_pv_claims": None, "nb_ra": 5.0,
                  "nb_loss_component": 2.0, "nb_csm": 17.0})
        def ex(memo):
            items = {k: {"FY2025": {"value": x}} for k, x in v.items()}
            return {"items": items, **({"memo": {"nb_pv_outflows": {"FY2025": {"value": 80.0}}}} if memo else {})}
        nb = lambda e: next(r for r in verify_extract.reconcile(e) if r["check"] == "nb_csm")
        self.assertTrue(nb(ex(True))["ok"])
        self.assertFalse(nb(ex(False))["ok"])

    def test_registry_matches_extractions(self):
        reg = {}
        for f in (ROOT / "sources").glob("*/registry.csv"):
            for r in read_csv(f):
                reg.setdefault((r["period"], r["company"]), []).append(r)
        for f in self.files:
            ex = json.loads(f.read_text(encoding="utf-8"))
            rows = reg[(ex["period"], ex["company"])]
            with self.subTest(company=ex["company"]):
                parts = ex["source"].get("parts")
                if parts:  # read from parts of a file too large for the connector
                    by_name = {r["original_name"]: r for r in rows}
                    for part in parts:
                        self.assertEqual(by_name[part["name"]]["sha256"], part["sha256"])
                        self.assertEqual(by_name[part["name"]]["status"], "extracted (part)")
                else:
                    r = next(r for r in rows if r["original_name"] == ex["source"]["original_name"])
                    self.assertEqual(r["sha256"], ex["source"]["sha256"])
                    self.assertEqual(r["status"], "extracted")

    def test_transcribed_spec_reproduces_extraction(self):
        """A spec made only of transcribed figures needs no PDF: re-running it gives the committed values."""
        from pipeline import extract
        for spec in sorted((ROOT / "config" / "extraction").rglob("*.json")):  # annual and quarterly/<period>/
            body = json.loads(spec.read_text(encoding="utf-8"))
            rules = [r for sec in ("items", "items_3m") for years in body.get(sec, {}).values() for r in years.values()]
            if not all("printed" in r or "const" in r or "not_disclosed" in r for r in rules):
                continue
            res = extract.extract(spec, None)
            committed = json.loads((ROOT / "extract" / res["period"] / f"{res['company_id']}.json").read_text(encoding="utf-8"))
            with self.subTest(spec=str(spec.relative_to(ROOT))):
                for sec in ("items", "items_3m"):
                    self.assertEqual({k: {fy: x["value"] for fy, x in v.items()} for k, v in res.get(sec, {}).items()},
                                     {k: {fy: x["value"] for fy, x in v.items()} for k, v in committed.get(sec, {}).items()})


class TestBuild(unittest.TestCase):
    def test_payload_and_render(self):
        data = build.payload(PERIOD)
        self.assertEqual(data["meta"]["default_focus"], "Samsung Life")
        self.assertEqual(len(data["companies"]), 17)
        html = build.render(data)
        self.assertNotIn("__DATA__", html)
        self.assertNotIn("</script><", html.split('id="data"')[1].split("</script>")[0])

    def test_quarterly_payload(self):
        """Quarterly pages: every insurer extracted, labels, comparative availability, period links."""
        for period, has_cmp in (("2026Q2", True), ("2025Q1", False)):
            ingest.run(period)
            validate.run(period)
            metrics.run(period)
            data = build.payload(period)
            with self.subTest(period=period):
                m = data["meta"]
                self.assertEqual(m["kind"], "quarter")
                self.assertEqual(m["period_label"], period[-1] + "Q" + period[:4])
                self.assertEqual(m["has_comparative"], has_cmp)
                self.assertEqual(m["ytd_months"], 3 * int(period[-1]))
                self.assertIn(period, [p["id"] for p in m["periods"]])
                names = {c["name"] for c in data["companies"]}
                self.assertTrue({"BUI Life", "Saha Life", "Samsung Life"} <= names)
                self.assertEqual(set(data["three_month"]), names)
                self.assertEqual(build.missing_translations(data, "ko"), [])
                self.assertTrue(all(n.get("periods") is None for n in data["commentary"]))  # FY-only notes left out
        self.assertEqual(build.period_label("FY2025"), "FY2025")

    def test_unknown_focus_rejected(self):
        with self.assertRaises(SystemExit):
            build.payload(PERIOD, "Not An Insurer")


if __name__ == "__main__":
    unittest.main()
