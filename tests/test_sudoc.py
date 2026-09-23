import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote_plus

import httpx

from analyseur_sudoc.sudoc import DIAG, SRU, SruError, build_query, collect_sudoc, parse_page


def response_xml(ppns=(), *, total=None, start=1, query=None, namespace=""):
    """Enveloppe CBS : MARC sans namespace, diagnostic 1/0 même en cas de succès."""
    records = "".join(f'''<s:record><s:recordSchema>unimarc</s:recordSchema>
        <s:recordPacking>xml</s:recordPacking><s:recordData><record {namespace}>
        <leader>     cam0 22        450 </leader><controlfield tag="001">{ppn}</controlfield>
        <datafield tag="200"><subfield code="a">Titre &amp; sous-titre</subfield></datafield>
        </record></s:recordData><s:recordPosition>{start + index}</s:recordPosition></s:record>'''
        for index, ppn in enumerate(ppns))
    total = len(ppns) if total is None else total
    echo = "" if query is None else f"<s:echoedSearchRetrieveRequest><s:query>{quote_plus(query)}</s:query></s:echoedSearchRetrieveRequest>"
    return f'''<?xml version="1.0" encoding="UTF-8"?>
        <s:searchRetrieveResponse xmlns:s="{SRU}" xmlns:d="{DIAG}">
        <s:numberOfRecords>{total}</s:numberOfRecords><s:records>{records}</s:records>
        {echo}<d:diagnostics><d:uri>info:srw/diagnostic/1/0</d:uri></d:diagnostics>
        </s:searchRetrieveResponse>'''.encode()


def diagnostics(code="2", detail="IMPOSSIBLE_ADI"):
    return f'''<s:searchRetrieveResponse xmlns:s="{SRU}" xmlns:d="{DIAG}">
        <s:numberOfRecords/><d:diagnostics><d:uri>info:srw/diagnostic/1/{code}</d:uri>
        <d:details>{detail}</d:details><d:message>Error</d:message></d:diagnostics>
        </s:searchRetrieveResponse>'''.encode()


class PageTests(unittest.TestCase):
    def test_real_sudoc_response(self):
        path = Path(__file__).parent / "fixtures/sru_2025_prefix0_page1.xml"
        page = parse_page(path.read_bytes(), 1, 1, build_query(2025, "0"))
        self.assertEqual(page.total, 2)
        self.assertEqual(page.ppns, ("029392810",))

    def test_query_and_validation(self):
        self.assertEqual(build_query(2024, "2"), "ppn=2* and apu=2024 and (tdo=b or tdo=x)")
        for year, prefix in ((2025, "*"), (99, "0"), ("2025", "0"), (2025, "")):
            with self.subTest(year=year, prefix=prefix), self.assertRaises(ValueError):
                build_query(year, prefix)

    def test_marc_with_and_without_namespace(self):
        for namespace in ("", 'xmlns="http://www.loc.gov/MARC21/slim"'):
            page = parse_page(response_xml(["029392810", "004678508"], namespace=namespace), 1, 2)
            self.assertEqual(page.total, 2)
            self.assertEqual(page.ppns, ("029392810", "004678508"))

    def test_diagnostic_before_empty_count(self):
        with self.assertRaisesRegex(SruError, "IMPOSSIBLE_ADI"):
            parse_page(diagnostics(), 1, 100)

    def test_zero_is_a_valid_empty_result(self):
        self.assertEqual(parse_page(response_xml(), 1, 100).total, 0)

    def test_zero_with_position_diagnostic(self):
        raw = response_xml().replace(b"diagnostic/1/0", b"diagnostic/1/61")
        self.assertEqual(parse_page(raw, 1, 200).total, 0)
        with self.assertRaises(SruError):
            parse_page(raw, 2, 200)
        with self.assertRaises(SruError):
            parse_page(raw.replace(b">0</s:numberOfRecords>", b">2</s:numberOfRecords>"), 1, 200)

    def test_bad_pages_are_rejected(self):
        valid = response_xml(["029392810"])
        cases = [b"<html>unavailable</html>", b"<broken", response_xml(total=1),
                 valid.replace(b">1</s:numberOfRecords>", b"></s:numberOfRecords>"),
                 valid.replace(b">1</s:recordPosition>", b">2</s:recordPosition>"),
                 valid.replace(b"029392810", b"bad"),
                 valid.replace(b' tag="001"', b' tag="003"'),
                 valid.replace(b">unimarc<", b">marc21<"),
                 valid.replace(b">xml<", b">string<"),
                 response_xml(["029392810"], total=0),
                 response_xml(["029392810", "004678508"])]
        for raw in cases:
            with self.subTest(raw=raw[:80]), self.assertRaises(SruError):
                parse_page(raw, 1, 1)

    def test_next_record_position_gap(self):
        raw = response_xml(["029392810"], total=3).replace(
            b"</s:searchRetrieveResponse>", b"<s:nextRecordPosition>3</s:nextRecordPosition></s:searchRetrieveResponse>")
        with self.assertRaisesRegex(SruError, "nextRecordPosition"):
            parse_page(raw, 1, 1)

    def test_doctype_is_rejected(self):
        raw = response_xml().replace(b'?>', b'?><!DOCTYPE test [<!ENTITY x SYSTEM "file:///missing">]>', 1)
        with self.assertRaisesRegex(SruError, "DTD"):
            parse_page(raw, 1, 100)

    def test_query_echo_is_checked(self):
        with self.assertRaisesRegex(SruError, "requête"):
            parse_page(response_xml(query=build_query(2024, "0")), 1, 100, build_query(2025, "0"))


class CollectionTests(unittest.TestCase):
    def test_record_limit_across_prefixes_and_resume(self):
        self.data = {"0": [f"{i:09d}" for i in range(2)],
                     "1": [f"{100000000+i:09d}" for i in range(8)],
                     "2": [f"{200000000+i:09d}" for i in range(3000)]}
        def handler(request):
            params = request.url.params
            self.calls.append(dict(params))
            data = self.data.get(params["query"][4], [])
            start, size = int(params["startRecord"]), int(params["maximumRecords"])
            return httpx.Response(200, content=response_xml(
                data[start-1:start-1+size], total=len(data), start=start, query=params["query"]))
        report = self.collect(handler)
        self.assertEqual(report["status"], "limited")
        self.assertEqual(report["records_validated"], 2000)
        self.assertEqual(report["distinct_ppns"], 2000)
        self.assertEqual(len(self.calls), 12)
        self.assertEqual(int(self.calls[-1]["maximumRecords"]), 190)
        self.calls.clear()
        self.assertEqual(self.collect(handler)["records_validated"], 2000)
        self.assertEqual(self.calls, [])
        with self.assertRaises(ValueError):
            self.collect(handler, max_records=2001)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name) / "campaign"
        self.calls = []
        self.data = {"0": ["029392810", "004678508", "070685045"], "2": ["298087316"]}

    def handler(self, request):
        params = request.url.params
        self.calls.append(dict(params))
        prefix = params["query"][4]
        start, size = int(params["startRecord"]), int(params["maximumRecords"])
        data = self.data.get(prefix, [])
        # Le serveur peut retourner moins que maximumRecords : on doit avancer
        # du nombre effectivement reçu, pas de la taille demandée.
        selected = data[start - 1:start]
        return httpx.Response(200, content=response_xml(selected, total=len(data), start=start, query=params["query"]))

    def collect(self, handler=None, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(handler or self.handler)) as client:
            return collect_sudoc(client, self.run, sleep=lambda _: None, **kwargs)

    def test_all_partitions_short_pages_and_exhaustivity(self):
        report = self.collect(page_size=2)
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["complete"])
        self.assertEqual(report["sru_number_of_records"], 4)
        self.assertEqual(report["records_downloaded"], 4)
        self.assertEqual(report["records_validated"], 4)
        self.assertEqual(report["distinct_ppns"], 4)
        self.assertEqual(report["missing_records_known_partitions"], 0)
        self.assertIsNone(report["records_parsed"])
        self.assertEqual([int(c["startRecord"]) for c in self.calls[:3]], [1, 2, 3])
        self.assertEqual(len(report["partitions"]), 10)
        self.assertEqual(json.loads((self.run / "report.json").read_text(encoding="utf-8"))["status"], "complete")

    def test_limited_run_resumes_without_redownload(self):
        first = self.collect(max_pages=1)
        self.assertFalse(first["complete"])
        self.assertEqual(first["status"], "limited")
        self.assertIsNone(first["sru_number_of_records"])
        self.assertEqual(first["missing_records_known_partitions"], 2)
        self.calls.clear()
        final = self.collect()
        self.assertEqual(self.calls[0]["startRecord"], "2")
        self.assertTrue(final["complete"])
        self.calls.clear()
        self.assertTrue(self.collect()["complete"])
        self.assertEqual(self.calls, [])

    def test_changed_settings_do_not_overwrite_campaign(self):
        self.collect(max_pages=1)
        previous = (self.run / "report.json").read_bytes()
        for kwargs in ({"year": 2024}, {"page_size": 10}):
            with self.assertRaisesRegex(ValueError, "Paramètres"):
                self.collect(**kwargs)
        self.assertEqual((self.run / "report.json").read_bytes(), previous)

    def test_modified_cache_fails_without_network(self):
        self.collect(max_pages=1)
        page = self.run / "pages/0/000000001.xml"
        page.write_bytes(page.read_bytes() + b" ")
        self.calls.clear()
        report = self.collect()
        self.assertEqual(report["status"], "failed")
        self.assertIn("modifiée", report["errors"][0])
        self.assertEqual(self.calls, [])

    def test_changed_total_is_not_complete(self):
        self.collect(max_pages=1)
        self.data["0"].append("050959794")
        report = self.collect()
        self.assertFalse(report["complete"])
        self.assertIn("total SRU", report["errors"][0])
        self.assertEqual(report["records_validated"], 1)

    def test_duplicate_ppn_is_not_complete(self):
        self.data["0"] = ["029392810", "029392810"]
        report = self.collect()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["distinct_ppns"], 1)
        self.assertIn("dupliqués", report["errors"][0])

    def test_wrong_prefix_is_rejected(self):
        self.data["0"] = ["298087316"]
        report = self.collect()
        self.assertIn("préfixe", report["errors"][0])
        self.assertFalse(report["complete"])

    def test_permanent_diagnostic_is_retained_and_not_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, content=diagnostics())
        report = self.collect(handler)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(list((self.run / "rejected").glob("*.xml"))), 1)
        self.assertTrue(self.collect()["complete"])

    def test_temporary_http_and_sru_errors_are_retried(self):
        sleeps, calls = [], []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "3"})
            if len(calls) == 2:
                return httpx.Response(200, content=diagnostics(detail="temporarily unavailable"))
            return self.handler(request)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            report = collect_sudoc(client, self.run, max_pages=1, sleep=sleeps.append)
        self.assertEqual(len(calls), 3)
        self.assertIn(3, sleeps)
        self.assertEqual(report["status"], "limited")

    def test_network_failure_has_report_and_resumes(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ConnectError("Offline", request=request)
        report = self.collect(handler)
        self.assertEqual(len(calls), 3)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(self.collect()["complete"])

    def test_interruption_retains_progress(self):
        def handler(request):
            if request.url.params["startRecord"] == "2":
                raise KeyboardInterrupt()
            return self.handler(request)
        report = self.collect(handler)
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(report["records_validated"], 1)
        self.assertTrue(self.collect()["complete"])

    def test_cli_codes(self):
        path = Path(__file__).resolve().parents[1] / "scripts/02_fetch_sudoc.py"
        spec = importlib.util.spec_from_file_location("fetch_sudoc_script", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for status, code in (("complete", 0), ("limited", 2), ("failed", 1), ("interrupted", 130)):
            report = {"status": status, "records_validated": 1, "distinct_ppns": 1, "errors": []}
            with patch.object(module, "collect_sudoc", return_value=report), patch("builtins.print"):
                self.assertEqual(module.main(["--run-dir", str(self.run)]), code)


if __name__ == "__main__":
    unittest.main()
