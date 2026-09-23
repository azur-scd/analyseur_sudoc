import json
import tempfile
import unittest
from pathlib import Path

import httpx
import duckdb

from analyseur_sudoc.authority_enrichment import collect_authorities, enrich_documents, heading_links, parse_authority
from analyseur_sudoc.authority_database import load_authority_enrichment
from analyseur_sudoc.database import FIELDS
from analyseur_sudoc.enrichment import digest, read_jsonl, write_jsonl
from analyseur_sudoc.unimarc import dewey
from analyseur_sudoc.warehouse import load_corpus


def subject(tag, subs, index=1):
    return dict(source_field=tag, field_index=index, occurrence=1,
                subfields=[dict(code=code, raw=raw, subfield_index=i) for i, (code, raw) in enumerate(subs, 1)])


def authority(ppn="02737372X"):
    return f'''<record><controlfield tag="001">{ppn}</controlfield>
      <datafield tag="250"><subfield code="a">Heading</subfield></datafield>
      <datafield tag="676"><subfield code="a">005.12</subfield><subfield code="v">23</subfield></datafield>
      <datafield tag="676"><subfield code="a">640</subfield></datafield>
      <datafield tag="686"><subfield code="a">000</subfield><subfield code="c">General</subfield><subfield code="2">Note de regroupement par domaine</subfield></datafield>
      <datafield tag="686"><subfield code="a">123</subfield><subfield code="2">mesh</subfield></datafield>
    </record>'''.encode()


class AuthorityTests(unittest.TestCase):
    def test_only_headings_not_subdivisions_or_other_fields(self):
        d = dict(subjects=[subject("606", [("3", "02737372X"), ("a", "Head"), ("3", "027243265"), ("x", "Subdivision")]),
                           subject("607", [("3", "027243265"), ("a", "Place")]),
                           subject("606", [("a", "Unlinked"), ("3", "027243265"), ("y", "Place")], 3)])
        links = heading_links(d)
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["authority_ppn"], "02737372X")
        self.assertIsNone(links[1]["authority_ppn"])
        self.assertEqual(links[1]["status"], "no_identifier")

    def test_repetitions_and_ambiguous_ids(self):
        d = dict(subjects=[subject("606", [("3", "02737372X"), ("a", "First"), ("3", "02737372X"), ("a", "Second")]),
                           subject("606", [("3", "invalid"), ("a", "Invalid")]),
                           subject("606", [("3", "02737372X"), ("3", "027243265"), ("a", "Ambiguous")])])
        links = heading_links(d)
        self.assertEqual([v["status"] for v in links], ["linked", "linked", "invalid_identifier", "ambiguous_identifier"])
        self.assertEqual([v["subfield_index"] for v in links[:2]], [2, 4])

    def test_dewey_and_rameau_are_distinct_and_mesh_excluded(self):
        values = parse_authority(authority(), "02737372X", True)["classifications"]
        self.assertEqual([v["scheme"] for v in values], ["dewey", "dewey", "rameau_domain"])
        self.assertEqual([v["code"] for v in values], ["005.12", "640", "000"])
        self.assertEqual(len(parse_authority(authority(), "02737372X", False)["classifications"]), 2)

    def test_identity_mismatch_and_documented_merge(self):
        result = parse_authority(authority("027243265"), "02737372X", True)
        self.assertEqual(result["status"], "identity_to_review")
        self.assertEqual(result["classifications"], [])
        raw = authority("027243265").replace(b"</record>", b'<datafield tag="035"><subfield code="a">02737372X</subfield></datafield></record>')
        self.assertEqual(parse_authority(raw, "02737372X", True)["status"], "resolved_former_identifier")

    def test_all_documents_cache_and_sources_preserved(self):
        calls = []
        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, content=authority())
        with tempfile.TemporaryDirectory() as tmp, httpx.Client(transport=httpx.MockTransport(handler)) as client:
            base = Path(tmp) / "input"
            base.mkdir()
            docs = [dict(ppn=str(i), classifications=[dewey(dict(raw="500", value="500"))],
                         subjects=[subject("606", [("3", "02737372X"), ("a", "Head")])]) for i in range(2)]
            docs.append(dict(ppn="no606", subjects=[], classifications=[]))
            for d in docs:
                d.update(title="Title", subtitle=None, publication_year=2025, source={}, holdings=[dict(rcr="012345678")])
            write_jsonl(base / "documents.jsonl", docs)
            library = dict.fromkeys(FIELDS)
            library["rcr"] = "012345678"
            write_jsonl(base / "libraries.jsonl", [library])
            report = dict(status="complete", records=3, libraries=1,
                          documents_sha256=digest((base / "documents.jsonl").read_bytes()),
                          libraries_sha256=digest((base / "libraries.jsonl").read_bytes()))
            (base / "report.json").write_text(json.dumps(report))
            output = Path(tmp) / "output"
            for _ in range(2):
                collect_authorities(base, output, client, delay=0)
            self.assertEqual(len(calls), 1)
            result = enrich_documents(output, True)
            enriched = read_jsonl(output / "documents.jsonl")
            self.assertEqual([d["classifications"] for d in enriched], [d["classifications"] for d in docs])
            self.assertEqual(result["counts"]["documents_with_authority_classification"], 2)
            self.assertEqual(enriched[-1]["idref_606a_classifications"], [])
            self.assertEqual(len(enriched[0]["idref_606a_classifications"]), 3)
            self.assertEqual(enriched[0]["idref_606a_classifications"][0]["via_606a"]["authority_ppn"], "02737372X")
            database = Path(tmp) / "test.duckdb"
            load_corpus(base, database, "sample", 2025)
            loaded = load_authority_enrichment(output, database, "sample", "authorities")
            self.assertEqual(loaded["counts"]["AUTHORITY_DOCUMENT"], 3)
            self.assertEqual(loaded["counts"]["AUTHORITY_CLASSIFICATION"], 6)
            self.assertEqual(load_authority_enrichment(output, database, "sample", "authorities")["status"], "already_loaded")
            with duckdb.connect(str(database)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM CLASSIFICATION").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT count(*) FROM AUTHORITY_CLASSIFICATION WHERE scheme='rameau_domain'").fetchone()[0], 2)
                self.assertEqual(json.loads(con.execute("SELECT payload FROM DOCUMENT WHERE ppn='0'").fetchone()[0]), docs[0])
                self.assertEqual(json.loads(con.execute("SELECT payload FROM AUTHORITY_DOCUMENT WHERE ppn='0'").fetchone()[0]), enriched[0])
            with self.assertRaises(ValueError):
                load_authority_enrichment(output, database, "wrong_corpus", "another")
