import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from sudoc_explorer.unimarc import bnf_ark_url, coded_date, extract_campaign, parse_record

FIXTURES = Path(__file__).parent / "fixtures"


class RecordTests(unittest.TestCase):
    def test_document_types_positions_repetitions_and_missing(self):
        record = etree.fromstring(b'''<record><leader>     nam0 22        450 </leader>
          <controlfield tag="001">000000001</controlfield>
          <datafield tag="105" ind1=" " ind2=" "><subfield code="a">    va  000yy</subfield></datafield>
          <datafield tag="181" ind1=" " ind2=" "><subfield code="c">txt</subfield><subfield code="2">rdacontent</subfield><subfield code="6">z01</subfield></datafield>
          <datafield tag="181" ind1=" " ind2=" "><subfield code="a">i#</subfield></datafield>
          <datafield tag="182" ind1=" " ind2=" "><subfield code="c">n</subfield><subfield code="c">c</subfield></datafield>
          <datafield tag="182" ind1=" " ind2=" "><subfield code="a">n</subfield></datafield>
        </record>''')
        parsed = parse_record(record, {})
        self.assertEqual(parsed["leader_types"][0]["type_code"], "am")
        self.assertEqual(parsed["leader_types"][0]["record_type"], "a")
        self.assertEqual(parsed["leader_types"][0]["bibliographic_level"], "m")
        self.assertEqual(parsed["nature_of_content"][0]["code"], "v")
        self.assertEqual(len(parsed["content_types"]), 2)
        self.assertEqual(parsed["content_types"][1]["occurrence"], 2)
        self.assertEqual([s["value"] for s in parsed["media_types"][0]["subfields"]], ["n", "c"])
        self.assertEqual(len(parsed["media_types"]), 2)
        record.find("leader").text = "short"
        record.find("datafield/subfield").text = "tiny"
        parsed = parse_record(record, {})
        self.assertIsNone(parsed["leader_types"][0]["type_code"])
        self.assertIsNone(parsed["nature_of_content"][0]["code"])
        for node in list(record):
            if node.tag != "controlfield":
                record.remove(node)
        parsed = parse_record(record, {})
        for key in ("leader_types", "content_types", "media_types", "nature_of_content"):
            self.assertEqual(parsed[key], [])

    def test_bnf_ark_known_keys_and_input_validation(self):
        # Deux clés réellement présentes dans les 033 du lot, et l'exemple utilisateur.
        for number, key in [("45225369", "x"), ("45636685", "4"), ("48731321", "f")]:
            self.assertEqual(bnf_ark_url(number), f"http://catalogue.bnf.fr/ark:/12148/cb{number}{key}")
        for invalid in ["1234567", "123456789", "1234567X", 48731321]:
            with self.assertRaises(ValueError):
                bnf_ark_url(invalid)

    def test_bnf_035_fallback_preserves_identifier_and_ignores_z(self):
        field = etree.SubElement(self.record, "datafield", tag="035", ind1=" ", ind2=" ")
        etree.SubElement(field, "subfield", code="a").text = "FRBNF487863030000002"
        etree.SubElement(field, "subfield", code="z").text = "FRBNF11111111"
        link, = parse_record(self.record, self.source)["bnf_links"]
        self.assertEqual(link["url"], "http://catalogue.bnf.fr/ark:/12148/cb48786303r")
        self.assertEqual(link["raw"], "FRBNF487863030000002")
        self.assertEqual(link["bnf_number"], "48786303")
        self.assertEqual(link["identifier_suffix"], "0000002")
        self.assertEqual(link["source_field"], "035")
        self.assertEqual(link["origin"], "035a")
        self.assertEqual(link["checksum_algorithm"], "bnf_ark_mod29")

    def test_bnf_033_takes_priority_over_035(self):
        field = etree.SubElement(self.record, "datafield", tag="035")
        etree.SubElement(field, "subfield", code="a").text = "FRBNF487863030000002"
        field = etree.SubElement(self.record, "datafield", tag="033")
        url = "https://catalogue.bnf.fr/ark:/12148/cb45225369x"
        etree.SubElement(field, "subfield", code="a").text = url
        links = parse_record(self.record, self.source)["bnf_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], url)
        self.assertEqual(links[0]["origin"], "033a")

    def test_bnf_035_without_bnf_033_and_invalid_identifiers(self):
        field = etree.SubElement(self.record, "datafield", tag="033")
        etree.SubElement(field, "subfield", code="a").text = "https://other.example/"
        field = etree.SubElement(self.record, "datafield", tag="035")
        for value in ["FRBRF48786303", "FRBNF1234567", "FRBNF1234567X", "OTHER48786303"]:
            etree.SubElement(field, "subfield", code="a").text = value
        etree.SubElement(field, "subfield", code="z").text = "FRBNF48786303"
        self.assertEqual(parse_record(self.record, self.source)["bnf_links"], [])
        for value in ["FRBNF48786303", " frbnf452253690000009 "]:
            etree.SubElement(field, "subfield", code="a").text = value
        links = parse_record(self.record, self.source)["bnf_links"]
        self.assertEqual(len(links), 2)
        self.assertEqual([link["bnf_number"] for link in links], ["48786303", "45225369"])

    def setUp(self):
        self.record = etree.parse(str(FIXTURES / "unimarc_multiple.xml")).getroot()
        self.source = {"page_file": "pages/0/000000001.xml", "record_position": 1}
        self.doc = parse_record(self.record, self.source)

    def test_title_variants_and_raw_values(self):
        self.assertEqual(self.doc["title"], "Le titre")
        self.assertEqual(self.doc["subtitle"], "Un sous-titre")
        self.assertEqual(len(self.doc["titles"]), 2)
        self.assertEqual(self.doc["titles"][0]["main_titles"][0]["raw"], "\x98Le \x9ctitre")
        self.assertEqual(self.doc["titles"][0]["part_numbers"][0]["value"], "2")
        self.assertEqual(self.doc["source"], self.source)

    def test_dates_languages_countries_and_publishers(self):
        self.assertEqual(self.doc["publication_year"], 2025)
        self.assertEqual(self.doc["coded_dates"][0]["date2_year"], 1986)
        self.assertEqual([v["value"] for v in self.doc["languages"]], ["fre", "eng"])
        self.assertEqual([v["value"] for v in self.doc["countries"]], ["FR", "GB"])
        self.assertEqual([p["source_field"] for p in self.doc["publishers"]], ["210", "214", "214"])
        self.assertEqual(self.doc["publication_statements"][1]["dates"][0]["raw"], "[2025?]")

    def test_all_author_types_roles_and_corporate_subdivisions(self):
        self.assertEqual([a["source_field"] for a in self.doc["authors"]], ["700", "701", "702", "710", "711", "712"])
        author = self.doc["authors"][0]
        self.assertEqual([r["value"] for r in author["roles"]], ["070", "340"])
        self.assertEqual(author["authority_ids"][0]["value"], "00123456X")
        corporate = self.doc["authors"][3]
        self.assertEqual(corporate["firstnames"], [])
        self.assertEqual([s["value"] for s in corporate["subdivisions"]], ["Bibliothèque", "Service"])

    def test_manufacturer_is_preserved_without_becoming_publisher(self):
        self.record.find('datafield[@tag="214"]').set("ind2", "3")
        doc = parse_record(self.record, self.source)
        self.assertEqual(doc["publishers"][1]["statement_type"], "manufacture")
        self.assertEqual(doc["publishers"][1]["value"], "Premier éditeur")
        self.assertIsNone(doc["publishers"][1]["publisher"])

    def test_dewey_multiple_slashes_leading_zero_and_unknown(self):
        dew = self.doc["classifications"]
        self.assertEqual(dew[0]["dewey_raw"], "746.9/7/0996")
        self.assertEqual(dew[0]["dewey_normalized"], "746.970996")
        self.assertEqual((dew[1]["dewey_1"], dew[1]["dewey_2"], dew[1]["dewey_3"]), ("0", "00", "005"))
        self.assertIsNone(dew[2]["dewey_normalized"])

    def test_930_evidence_is_not_collapsed_or_inferred(self):
        self.assertEqual(len(self.doc["locations"]), 5)
        holdings = self.doc["holdings"]
        self.assertEqual([h["rcr"] for h in holdings], ["040702201", "751032301"])
        self.assertEqual(len(holdings[0]["evidence"]), 2)
        self.assertEqual(holdings[0]["validation_status"], "user_confirmed_930b")
        self.assertEqual(self.doc["locations"][2]["comparison_b_5"], "mismatch")
        self.assertEqual(self.doc["locations"][3]["comparison_b_5"], "not_comparable")
        self.assertIsNone(self.doc["locations"][4]["rcr_values"][0]["rcr"])
        self.assertIn("777777777", [v["rcr_candidate"] for v in self.doc["local_links_5"]])

    def test_missing_fields_stay_missing(self):
        record = etree.fromstring(b'<record><controlfield tag="001">01234567X</controlfield></record>')
        doc = parse_record(record, self.source)
        self.assertIsNone(doc["title"])
        self.assertIsNone(doc["publication_year"])
        self.assertEqual(doc["classifications"], [])
        self.assertEqual(doc["holdings"], [])
        self.assertEqual(doc["subjects"], [])
        self.assertEqual(doc["bnf_links"], [])
        self.assertEqual(doc["summaries"], [])

    def test_summaries_repeated_fields_subfields_and_raw_text(self):
        first = etree.SubElement(self.record, "datafield", tag="330", ind1="1", ind2=" ")
        etree.SubElement(first, "subfield", code="a").text = "  Résumé français.\nSuite.  "
        etree.SubElement(first, "subfield", code="a").text = "Another abstract."
        etree.SubElement(first, "subfield", code="b").text = "Source du résumé"
        second = etree.SubElement(self.record, "datafield", tag="330", ind1=" ", ind2=" ")
        etree.SubElement(second, "subfield", code="a").text = "Another abstract."
        etree.SubElement(second, "subfield", code="a")
        third = etree.SubElement(self.record, "datafield", tag="330")
        etree.SubElement(third, "subfield", code="b").text = "Sans résumé"
        for node in self.record.iter():
            node.tag = "{http://www.loc.gov/MARC21/slim}" + node.tag
        summaries = parse_record(self.record, self.source)["summaries"]
        self.assertEqual(len(summaries), 4)
        self.assertEqual(summaries[0]["raw"], "  Résumé français.\nSuite.  ")
        self.assertEqual(summaries[0]["value"], "Résumé français. Suite.")
        self.assertEqual(summaries[0]["ind1"], "1")
        self.assertEqual([s["occurrence"] for s in summaries], [1, 1, 2, 2])
        self.assertEqual([s["subfield_index"] for s in summaries], [1, 2, 1, 2])
        self.assertEqual(summaries[1]["value"], summaries[2]["value"])
        self.assertIsNone(summaries[3]["value"])

    def test_bnf_links_filter_repeated_fields_and_preserve_url(self):
        url = "https://catalogue.bnf.fr/ark:/12148/cb123456789?x=1&y=2"
        for tag, code, value in [("033", "a", "  " + url + "  "),
                                 ("033", "a", "https://other.example/record"),
                                 ("033", "z", url), ("856", "a", url)]:
            field = etree.SubElement(self.record, "datafield", tag=tag)
            etree.SubElement(field, "subfield", code=code).text = value
        field = etree.SubElement(self.record, "datafield", tag="033")
        for value in ["https://CATALOGUE.BNF.fr/ark:/12148/cb987654321", url]:
            etree.SubElement(field, "subfield", code="a").text = value
        links = parse_record(self.record, self.source)["bnf_links"]
        self.assertEqual(len(links), 3)
        self.assertEqual(links[0]["url"], url)
        self.assertEqual(links[0]["raw"], "  " + url + "  ")
        self.assertEqual(links[1]["url"], "https://CATALOGUE.BNF.fr/ark:/12148/cb987654321")
        self.assertEqual(links[2]["subfield_index"], 2)
        self.assertEqual(links[2]["occurrence"], 4)

    def test_subject_range_inclusive_and_repeated_subfields(self):
        for tag in range(599, 622):
            field = etree.SubElement(self.record, "datafield", tag=str(tag), ind1="1", ind2="2")
            etree.SubElement(field, "subfield", code="a").text = f"Sujet {tag}"
        field = etree.SubElement(self.record, "datafield", tag="606", ind1=" ", ind2=" ")
        for code, text in [("3", "02712345X"), ("x", "  Histoire  "), ("x", "Études"),
                           ("2", "rameau"), ("5", "Contexte local"), ("9", "Autre")]:
            etree.SubElement(field, "subfield", code=code).text = text
        doc = parse_record(self.record, self.source)
        subjects = doc["subjects"]
        self.assertEqual([s["source_field"] for s in subjects], [str(i) for i in range(600, 621)] + ["606"])
        self.assertEqual(subjects[0]["ind1"], "1")
        self.assertEqual(subjects[-1]["occurrence"], 2)
        subs = subjects[-1]["subfields"]
        self.assertEqual([s["code"] for s in subs], ["3", "x", "x", "2", "5", "9"])
        self.assertEqual(subs[1]["raw"], "  Histoire  ")
        self.assertEqual(subs[1]["value"], "Histoire")
        self.assertEqual(subs[0]["value"], "02712345X")
        self.assertEqual(subs[-1]["subfield_index"], 6)

    def test_subject_namespaces(self):
        field = etree.SubElement(self.record, "datafield", tag="620")
        etree.SubElement(field, "subfield", code="d").text = "Paris"
        for node in self.record.iter():
            node.tag = "{http://www.loc.gov/MARC21/slim}" + node.tag
        doc = parse_record(self.record, self.source)
        self.assertEqual(doc["subjects"][0]["subfields"][0]["value"], "Paris")

    def test_uncertain_or_range_date_does_not_become_publication_year(self):
        for value in ("20260101f20242026", "20260101g20242026", "20260101d20XX    ", "2025"):
            self.record.find('datafield[@tag="100"]/subfield').text = value
            self.assertIsNone(parse_record(self.record, self.source)["publication_year"])

    def test_namespaces_and_reordered_fields(self):
        expected = self.doc["title"]
        for node in self.record.iter():
            node.tag = "{http://www.loc.gov/MARC21/slim}" + node.tag
        doc = parse_record(self.record, self.source)
        self.assertEqual(doc["title"], expected)
        self.assertEqual(len(doc["locations"]), 5)


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run, self.output = self.base / "raw", self.base / "processed"
        self.page_path = self.run / "pages/0/000000001.xml"
        self.page_path.parent.mkdir(parents=True)
        raw = (FIXTURES / "sru_2025_prefix0_page1.xml").read_bytes()
        self.page_path.write_bytes(raw)
        self.report = {"collection_id": "test", "status": "limited", "records_validated": 1,
                       "partitions": [{"pages": [{"file": "pages/0/000000001.xml", "count": 1,
                           "sha256": hashlib.sha256(raw).hexdigest(),
                           "params": {"startRecord": 1, "maximumRecords": 1,
                                      "query": "ppn=0* and apu=2025 and (tdo=b or tdo=x)"}}]}]}
        self.save_report()

    def save_report(self):
        (self.run / "report.json").write_text(json.dumps(self.report), encoding="utf-8")

    def test_real_page_exports_and_provenance(self):
        report = extract_campaign(self.run, self.output)
        self.assertEqual(report["records_parsed"], 1)
        doc = json.loads((self.output / "documents.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(doc["ppn"], "029392810")
        self.assertEqual(doc["publication_year"], 2025)
        self.assertEqual(doc["title"], "Tīfaifai and quilts of Polynesia")
        subjects = [json.loads(line) for line in (self.output / "subjects.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertGreater(len(subjects), 0)
        self.assertEqual(len(subjects), report["counts"]["subjects"])
        self.assertEqual(report["counts"]["records_with_subjects"], 1)
        self.assertEqual(sum(report["subjects_by_field"].values()), len(subjects))
        self.assertEqual(subjects[0]["ppn"], doc["ppn"])
        self.assertEqual(subjects[0]["source"], doc["source"])
        self.assertEqual(subjects[0]["subfields"], doc["subjects"][0]["subfields"])
        self.assertGreater(len(doc["locations"]), len(doc["holdings"]))
        holdings = [json.loads(line) for line in (self.output / "holdings.jsonl").read_text(encoding="utf-8").splitlines()]
        pairs = [(h["ppn"], h["rcr"]) for h in holdings]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(report["counts"]["holdings"], len(holdings))
        self.assertEqual(report["counts"]["duplicate_rcr_occurrences_collapsed"],
                         sum(len(h["evidence"]) - 1 for h in holdings))
        self.assertGreater(report["counts"]["duplicate_rcr_occurrences_collapsed"], 0)
        self.assertEqual(report["holdings_validation"], "user_confirmed_930b")

        with (self.output / "localisations_a_verifier.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        self.assertEqual(rows[0]["page_file"], "pages/0/000000001.xml")
        self.assertEqual(rows[0]["ppn"], "029392810")
        with self.assertRaisesRegex(ValueError, "vide"):
            extract_campaign(self.run, self.output)

    def test_checksum_failure_is_reported(self):
        self.page_path.write_bytes(self.page_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Empreinte"):
            extract_campaign(self.run, self.output)
        self.assertEqual(json.loads((self.output / "report.json").read_text())["status"], "failed")

    def test_summaries_export_and_provenance(self):
        root = etree.fromstring(self.page_path.read_bytes())
        record = root.find('.//{http://www.loc.gov/zing/srw/}recordData/record')
        for old in record.findall('datafield[@tag="330"]'):
            record.remove(old)
        for text in ["Premier résumé.", "Second résumé."]:
            field = etree.SubElement(record, "datafield", tag="330")
            etree.SubElement(field, "subfield", code="a").text = text
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        report = extract_campaign(self.run, self.output)
        summaries = [json.loads(line) for line in (self.output / "summaries.jsonl").read_text(encoding="utf-8").splitlines()]
        doc = json.loads((self.output / "documents.jsonl").read_text(encoding="utf-8"))
        self.assertEqual([s["value"] for s in summaries], ["Premier résumé.", "Second résumé."])
        self.assertEqual(report["counts"]["summaries"], 2)
        self.assertEqual(report["counts"]["records_with_summaries"], 1)
        for item, nested in zip(summaries, doc["summaries"]):
            self.assertEqual(item, {"ppn": doc["ppn"], "source": doc["source"], **nested})

    def test_bnf_links_export(self):
        root = etree.fromstring(self.page_path.read_bytes())
        record = root.find('.//{http://www.loc.gov/zing/srw/}recordData/record')
        field = etree.SubElement(record, "datafield", tag="033")
        url = "https://catalogue.bnf.fr/ark:/12148/cb123456789"
        etree.SubElement(field, "subfield", code="a").text = url
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        report = extract_campaign(self.run, self.output)
        links = [json.loads(line) for line in (self.output / "bnf_links.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(link["url"] == url for link in links))
        self.assertTrue(all(link["ppn"] == "029392810" for link in links))
        self.assertEqual(report["counts"]["bnf_links"], len(links))
        self.assertEqual(report["counts"]["records_with_bnf_links"], 1)

    def test_035_derived_link_export_and_report(self):
        root = etree.fromstring(self.page_path.read_bytes())
        record = root.find('.//{http://www.loc.gov/zing/srw/}recordData/record')
        field = etree.SubElement(record, "datafield", tag="035")
        etree.SubElement(field, "subfield", code="a").text = "FRBNF487863030000002"
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        report = extract_campaign(self.run, self.output)
        links = [json.loads(line) for line in (self.output / "bnf_links.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(links[0]["origin"], "035a")
        self.assertEqual(links[0]["ppn"], "029392810")
        self.assertEqual(report["counts"]["bnf_links_from_035a"], 1)
        self.assertEqual(report["counts"]["records_with_bnf_links_from_035a"], 1)

    def test_count_mismatch_and_invalid_path(self):
        self.report["records_validated"] = 2
        self.save_report()
        with self.assertRaisesRegex(ValueError, "nombre"):
            extract_campaign(self.run, self.output)
        self.report["partitions"][0]["pages"][0]["file"] = "../outside.xml"
        self.save_report()
        with self.assertRaisesRegex(ValueError, "Chemin"):
            extract_campaign(self.run, self.base / "other-output")

    def test_output_cannot_be_inside_raw(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            extract_campaign(self.run, self.run / "extracted")

    def test_notices_without_930b_are_excluded_from_all_exports(self):
        root = etree.fromstring(self.page_path.read_bytes())
        record = root.find('.//{http://www.loc.gov/zing/srw/}recordData/record')
        for field in record.findall('datafield[@tag="930"]'):
            for sub in field.findall('subfield[@code="b"]'):
                field.remove(sub)
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        result = extract_campaign(self.run, self.output)
        self.assertEqual(result["records_parsed"], 1)
        self.assertEqual(result["records_retained"], 0)
        self.assertEqual(result["records_excluded"], 1)
        self.assertEqual(result["exclusions"][0]["ppn"], "029392810")
        for path in self.output.glob("*.jsonl"):
            self.assertEqual(path.read_text(encoding="utf-8"), "", path.name)
        self.assertEqual(result["counts"]["documents"], 0)
        with (self.output / "localisations_a_verifier.csv").open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream, delimiter=";")), [])

    def test_empty_930b_is_excluded_but_nonempty_invalid_b_remains_reportable(self):
        root = etree.fromstring(self.page_path.read_bytes())
        fields = root.findall('.//{http://www.loc.gov/zing/srw/}recordData/record/datafield[@tag="930"]/subfield[@code="b"]')
        for sub in fields:
            sub.text = "   "
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        self.assertEqual(extract_campaign(self.run, self.output)["records_excluded"], 1)
        fields[0].text = "invalid"
        raw = etree.tostring(root)
        self.page_path.write_bytes(raw)
        self.report["partitions"][0]["pages"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_report()
        result = extract_campaign(self.run, self.base / "other")
        self.assertEqual(result["records_retained"], 1)
        self.assertEqual(result["counts"]["invalid_930b_values"], len(fields))


if __name__ == "__main__":
    unittest.main()
