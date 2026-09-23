import unittest
import json
import hashlib
import tempfile
from pathlib import Path

from analyseur_sudoc.quality import audit_documents, audit_extraction, classification_analysis


def document():
    return dict(ppn="000000001", title="Test", source={}, source_fields=[],
                countries=[{"value": "FR"}, {"value": "FR"}], languages=[{"value": "fre"}],
                coded_dates=[], publication_year=2025, publication_statements=[],
                classifications=[], subjects=[], summaries=[], leader_raw=["     nam0 22        450 "])


class QualityTests(unittest.TestCase):
    def test_classification_methods_count_records_not_repeated_codes(self):
        d = document()
        d["classifications"] = [dict(dewey_source="sudoc:676$a", dewey_normalized="005"),
                                dict(dewey_source="bnf:676$a", dewey_normalized="500")]
        d["idref_606a_links"] = [dict(authority_ppn="02737372X", status="resolved")] * 2
        d["idref_606a_classifications"] = [dict(scheme="rameau_domain", code="005")] * 2
        stats, rows = classification_analysis([d])
        self.assertEqual(stats["methods"]["idref_rameau_domain"]["occurrences"], 2)
        self.assertEqual(stats["methods"]["idref_rameau_domain"]["records_usable"], 1)
        self.assertEqual(stats["methods"]["idref_dewey"]["records_usable"], 0)
        self.assertEqual(stats["unique_linked_authorities"], 1)
        self.assertEqual(stats["code_distributions"]["idref_rameau_domain"], {"005": 1})
        self.assertEqual(rows[0]["idref_rameau_domain"], ["005"])
        old = document()
        old["ppn"] = "000000002"
        stats, rows = classification_analysis([d, old])
        self.assertEqual(stats["idref_processed_records"], 1)
        self.assertFalse(rows[1]["idref_processed"])
        self.assertIsNone(rows[1]["headings_606a"])
        d["idref_606a_classifications"].append(dict(scheme="dewey", code=None, code_raw="91"))
        stats, _ = classification_analysis([d])
        self.assertEqual(stats["methods"]["idref_dewey"]["records_present"], 1)
        self.assertEqual(stats["methods"]["idref_dewey"]["records_usable"], 0)

    def test_audit_accepts_enriched_report_and_checks_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "input"
            base.mkdir()
            d = document()
            d["idref_606a_links"] = [dict(status="no_identifier", authority_ppn=None)]
            d["idref_606a_classifications"] = []
            d["source_fields"] = [{"source_field": "106", "subfields": [{"code": "a", "raw": "s"}]}]
            payload = (json.dumps(d) + "\n").encode()
            (base / "documents.jsonl").write_bytes(payload)
            (base / "report.json").write_text(json.dumps(dict(status="complete", records=1,
                version="0.1.0", documents_sha256=hashlib.sha256(payload).hexdigest())))
            output = Path(temp) / "audit"
            stats = audit_extraction(base, output, 2025, scope_validated=True)
            self.assertEqual(stats["classification_methods"]["heading_statuses"], {"no_identifier": 1})
            self.assertEqual(stats["anomaly_counts"]["idref_606a_unresolved"], 1)
            self.assertIn("information_perimetre_valide", stats["records_by_category"])
            self.assertNotIn("hors_perimetre", stats["records_by_category"])
            self.assertTrue((output / "classification_methods.csv").exists())
            (base / "documents.jsonl").write_bytes(payload + b"\n")
            with self.assertRaises(ValueError):
                audit_extraction(base, Path(temp) / "bad", 2025)

    def test_new_types_repeat_without_inflating_record_counts(self):
        d = document()
        d["leader_types"] = [dict(record_type="r", bibliographic_level="m", type_code="rm")]
        field = dict(subfields=[dict(code="c", raw="txt"), dict(code="2", raw="rdacontent")])
        d["content_types"] = [field, field]
        d["media_types"] = [dict(subfields=[dict(code="c", raw="c")])]
        d["nature_of_content"] = [dict(code="a", raw="    av  000yy")]
        stats, flags = audit_documents([d], 2025)
        self.assertEqual(stats["distributions"]["leader_type_level"], {"rm": 1})
        self.assertEqual(list(stats["distributions"]["181_c_by_vocabulary"].values()), [1])
        self.assertEqual(list(stats["distributions"]["181_c_occurrences"].values()), [2])
        self.assertEqual(stats["distributions"]["nature_105_position_4"], {"a": 1})
        self.assertEqual(stats["coverage"]["content_types_coded"]["records"], 1)
        self.assertIn("computer_media", {f["rule"] for f in flags})

    def test_distinct_values_and_missing_coverage(self):
        stats, flags = audit_documents([document()], 2025)
        self.assertEqual(stats["distributions"]["countries"], {"FR": 1})
        self.assertEqual(stats["coverage"]["dewey_usable"]["records"], 0)
        self.assertEqual({a["category"] for a in flags}, {"lacune"})

    def test_thesis_export_positions_and_reworked_work(self):
        d = document()
        d["source_fields"] = [{"source_field": "105", "subfields": [{"code": "a", "raw": "y   m   000yy"}]}]
        _, flags = audit_documents([d], 2025)
        self.assertIn("original_thesis", {a["rule"] for a in flags})
        d["source_fields"][0]["subfields"][0]["raw"] = "y   v   000yy"
        _, flags = audit_documents([d], 2025)
        self.assertIn("academic_work", {a["rule"] for a in flags})
        self.assertNotIn("hors_perimetre", {a["category"] for a in flags})

    def test_dates_ignore_copyright_but_flag_publication_disagreement(self):
        d = document()
        d["publication_statements"] = [{"statement_type": "copyright", "dates": [{"value": "2024"}]}]
        _, flags = audit_documents([d], 2025)
        self.assertNotIn("date_disagreement", {a["rule"] for a in flags})
        d["publication_statements"][0]["statement_type"] = "publication"
        _, flags = audit_documents([d], 2025)
        self.assertIn("date_disagreement", {a["rule"] for a in flags})

    def test_duplicate_ppn_rejected_and_empty_corpus(self):
        with self.assertRaises(ValueError):
            audit_documents([document(), document()], 2025)
        stats, flags = audit_documents([], 2025)
        self.assertEqual(stats["records"], 0)
        self.assertEqual(flags, [])

    def test_summaries_and_electronic_form(self):
        d = document()
        d["summaries"] = [{"value": "Court"}, {"value": "Court"}]
        d["source_fields"] = [{"source_field": "106", "subfields": [{"code": "a", "raw": "s"}]}]
        stats, flags = audit_documents([d], 2025)
        self.assertEqual(stats["coverage"]["summaries"]["percent"], 100)
        self.assertTrue({"summary_short", "summary_duplicate", "electronic_form"} <= {a["rule"] for a in flags})
