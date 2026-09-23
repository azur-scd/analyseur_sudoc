import json
import tempfile
import unittest
from pathlib import Path

import duckdb
import httpx
from lxml import etree

from analyseur_sudoc.database import FIELDS
from analyseur_sudoc.enrichment import ark_from_url, cached_fetch, digest, parse_bnf, write_jsonl
from analyseur_sudoc.unimarc import parse_record
from analyseur_sudoc.warehouse import load_corpus


class BnfTests(unittest.TestCase):
    def response(self, record_id="ark:/12148/cb487118969", count=1):
        return f'''<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
          <numberOfRecords>{count}</numberOfRecords><records><record><recordData>
          <record xmlns="info:lc/xmlns/marcxchange-v2" id="{record_id}" format="UNIMARC">
          <datafield tag="676" ind1=" " ind2=" "><subfield code="a">025.4</subfield><subfield code="v">23</subfield></datafield>
          </record></recordData></record></records></searchRetrieveResponse>'''.encode()

    def test_exact_identity_and_provenance(self):
        result = parse_bnf(self.response(), "ark:/12148/cb487118969")
        self.assertEqual(result["classifications"][0]["dewey_source"], "bnf:676$a")
        self.assertEqual(result["classifications"][0]["dewey_3"], "025")
        self.assertEqual(result["classifications"][0]["editions"][0]["value"], "23")
        self.assertEqual(parse_bnf(self.response("wrong"), "ark:/12148/cb487118969")["classifications"], [])
        with self.assertRaises(ValueError):
            parse_bnf(self.response(count=2), "ark:/12148/cb487118969")

    def test_diagnostics_missing_and_url_validation(self):
        with self.assertRaises(ValueError):
            parse_bnf(b'<response><diagnostic>error</diagnostic></response>', "ark")
        result = parse_bnf(b'<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><numberOfRecords>0</numberOfRecords></searchRetrieveResponse>', "ark")
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(ark_from_url("http://catalogue.bnf.fr/ark:/12148/cb487118969"), "ark:/12148/cb487118969")
        with self.assertRaises(ValueError):
            ark_from_url("https://catalogue.bnf.fr.invalid/ark:/12148/cb487118969")

    def test_cached_response_and_tamper_detection(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, content=b"payload")
        with tempfile.TemporaryDirectory() as temp, httpx.Client(transport=httpx.MockTransport(handler)) as client:
            path = Path(temp) / "source.xml"
            for _ in range(2):
                cached_fetch(client, "https://example.org/", path, 0)
            self.assertEqual(len(calls), 1)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                cached_fetch(client, "https://example.org/", path, 0)


class WarehouseTests(unittest.TestCase):
    def test_roundtrip_idempotence_and_corpus_isolation(self):
        record = etree.fromstring(b'''<record><controlfield tag="001">000000001</controlfield>
          <datafield tag="200"><subfield code="a">Title</subfield></datafield>
          <datafield tag="676"><subfield code="a">005.1</subfield></datafield>
          <datafield tag="930"><subfield code="b">012345678</subfield></datafield>
          <datafield tag="330"><subfield code="a">Summary one</subfield><subfield code="a">Summary two</subfield></datafield></record>''')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            document = parse_record(record, {"page_file": "test.xml"})
            library = dict.fromkeys(FIELDS)
            library.update(rcr="012345678", label="Library")
            write_jsonl(folder / "documents.jsonl", [document])
            write_jsonl(folder / "libraries.jsonl", [library])
            report = dict(status="complete", records=1, libraries=1,
                          documents_sha256=digest((folder / "documents.jsonl").read_bytes()),
                          libraries_sha256=digest((folder / "libraries.jsonl").read_bytes()))
            (folder / "report.json").write_text(json.dumps(report))
            db = folder / "test.duckdb"
            self.assertEqual(load_corpus(folder, db, "first", 2025)["counts"]["HOLDING"], 1)
            self.assertEqual(load_corpus(folder, db, "first", 2025)["status"], "already_loaded")
            with self.assertRaises(ValueError):
                load_corpus(folder, db, "first", 2024)
            load_corpus(folder, db, "second", 2025)
            with duckdb.connect(str(db)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM DOCUMENT").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT count(*) FROM SUMMARY").fetchone()[0], 4)
                self.assertEqual(con.execute("SELECT dewey_3 FROM CLASSIFICATION LIMIT 1").fetchone()[0], "005")
                self.assertEqual(con.execute("SELECT rcr FROM HOLDING LIMIT 1").fetchone()[0], "012345678")
            (folder / "documents.jsonl").write_text("{}")
            with self.assertRaises(ValueError):
                load_corpus(folder, db, "third", 2025)
