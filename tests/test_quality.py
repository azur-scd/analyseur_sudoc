import unittest

from sudoc_explorer.quality import audit_documents


def document():
    return dict(ppn="000000001", title="Test", source={}, source_fields=[],
                countries=[{"value": "FR"}, {"value": "FR"}], languages=[{"value": "fre"}],
                coded_dates=[], publication_year=2025, publication_statements=[],
                classifications=[], subjects=[], summaries=[], leader_raw=["     nam0 22        450 "])


class QualityTests(unittest.TestCase):
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
