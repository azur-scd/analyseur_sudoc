import json
import tempfile
import unittest
from pathlib import Path

import httpx

from analyseur_sudoc.libraries import collect_references, extract_library_type, parse_listrcr

TSV = ('RCR\tLIBELLE\tILN\tPPN\tVILLE\tCDPOSTAL\tPAYS\tLATITUDE\tLONGITUDE\n'
       '=\"040702201\"\tBibliothèque\t4\t=\"068875975\"\tDigne\t04000\tFR\t44.09\t6.22\n'
       '040702202\tAutre\t4\tnull\tDigne\t04000\tFR\tnull\tnull\n')
STAMP = "2026-09-19T12:00:00+00:00"
NOTICE = {"record": {"datafield": [{"tag": 130, "subfield": [
    {"code": "a", "content": "Bibliothèque universitaire"}, {"code": "b", "content": 22}]}]}}


class LibraryTests(unittest.TestCase):
    def test_encodings_identifiers_and_nulls(self):
        for encoding in ("utf-8-sig", "utf-16", "utf-16-le"):
            with self.subTest(encoding=encoding):
                rows = parse_listrcr(TSV.encode(encoding), STAMP)
                self.assertEqual(rows[0]["rcr"], "040702201")
                self.assertEqual(rows[0]["library_ppn"], "068875975")
                self.assertEqual(rows[0]["postal_code"], "04000")
                self.assertEqual(rows[0]["label"], "Bibliothèque")
                self.assertAlmostEqual(rows[0]["latitude"], 44.09)
                self.assertAlmostEqual(rows[0]["longitude"], 6.22)
                self.assertIsNone(rows[1]["latitude"])
                self.assertIsNone(rows[1]["library_ppn"])

    def test_bad_input_rejected(self):
        for text in ("<html>error</html>",
                     TSV.replace("068875975", "../bad"), TSV.splitlines()[0]):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_listrcr(text.encode(), STAMP)

    def test_duplicate_rcr_does_not_choose_conflicting_metadata(self):
        warnings = []
        rows = parse_listrcr(TSV.replace("040702202", "040702201").encode(), STAMP, warnings)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rcr"], "040702201")
        self.assertIsNone(rows[0]["library_ppn"])
        self.assertIsNone(rows[0]["label"])
        self.assertEqual(warnings[-1]["reason"], "RCR dupliqué")

    def test_invalid_coordinates_are_null_and_reported(self):
        for value in ("nan", "91", "a49.896258"):
            warnings = []
            rows = parse_listrcr(TSV.replace("44.09", value).encode(), STAMP, warnings)
            self.assertIsNone(rows[0]["latitude"])
            self.assertEqual(warnings[0]["raw_value"], value)
            self.assertEqual(warnings[0]["rcr"], "040702201")

    def test_type_multiple_subfields(self):
        self.assertEqual(extract_library_type(NOTICE), "Bibliothèque universitaire")

    def test_type_single_field_and_subfield(self):
        payload = {"record": {"datafield": {"tag": "130", "subfield": {"code": "a", "content": "BU"}}}}
        self.assertEqual(extract_library_type(payload), "BU")

    def test_missing_type(self):
        for fields in ([], [{"tag": 130}], [{"tag": 130, "subfield": {"code": "b", "content": 22}}]):
            self.assertIsNone(extract_library_type({"record": {"datafield": fields}}))
        with self.assertRaises(ValueError):
            extract_library_type({"error": "not a record"})

    def test_collection_and_resume(self):
        calls = []
        def handler(request):
            calls.append(str(request.url))
            if request.url.path == "/services/listrcr":
                return httpx.Response(200, content=TSV.encode("utf-16"))
            return httpx.Response(200, json=NOTICE)
        with tempfile.TemporaryDirectory() as tmp, httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rows, report = collect_references(client, Path(tmp), delay=0)
            self.assertEqual(report["with_type"], 1)
            self.assertEqual(report["without_ppn"], 1)
            self.assertEqual(report["errors"], [])
            self.assertEqual(rows[0]["library_type"], "Bibliothèque universitaire")
            again, _ = collect_references(client, Path(tmp), delay=0)
            self.assertEqual(rows, again)
            self.assertEqual(len(calls), 2)

    def test_http_and_invalid_json_failures_are_reported_then_retried(self):
        for response in (httpx.Response(404), httpx.Response(200, text="not JSON")):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "input.tsv"
                source.write_bytes(TSV.encode())
                run = Path(tmp) / "run"
                with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
                    rows, report = collect_references(client, run, source, delay=0)
                self.assertEqual(len(report["errors"]), 1)
                self.assertIsNone(rows[0]["library_type"])
                self.assertFalse((run / "idref/068875975.json").exists())
                with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=NOTICE))) as client:
                    _, report = collect_references(client, run, source, delay=0)
                self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
