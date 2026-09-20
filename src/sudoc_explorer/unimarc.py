"""Extraction UNIMARC hors réseau, avec valeurs brutes et provenance."""

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

from lxml import etree

from sudoc_explorer.sudoc import NS, now, parse_page, write_json

PARSER_VERSION = "0.3.6"
AUTHOR_TAGS = {"700", "701", "702", "710", "711", "712"}
SUBJECT_TAGS = {str(tag) for tag in range(600, 621)}
ARK_ALPHABET = "0123456789bcdfghjkmnpqrstvwxz"


def bnf_ark_url(number):
    """Clé ARK BnF : somme pondérée (positions 1..10), modulo 29, §8.3 BnF."""
    if not isinstance(number, str) or not re.fullmatch(r"[0-9]{8}", number):
        raise ValueError("Numéro BnF attendu : huit chiffres")
    name = "cb" + number
    checksum = sum(position * ARK_ALPHABET.index(char) for position, char in enumerate(name, 1)) % 29
    return f"http://catalogue.bnf.fr/ark:/12148/{name}{ARK_ALPHABET[checksum]}"


def extract_bnf_links(grouped):
    links = [{**ref(f), "subfield_index": item["subfield_index"], "origin": "033a",
              "raw": item["raw"], "url": item["raw"].strip()}
             for f in grouped.get("033", []) for item in field_values(f, "a")
             if "catalogue.bnf" in item["raw"].lower()]
    if links:
        return links
    for field in grouped.get("035", []):
        for item in field_values(field, "a"):
            match = re.fullmatch(r"FRBNF([0-9]{8})([0-9A-Za-z]*)", item["raw"].strip(), re.IGNORECASE)
            if match:
                links.append({**ref(field), "subfield_index": item["subfield_index"],
                              "origin": "035a", "raw": item["raw"], "bnf_number": match[1],
                              "identifier_suffix": match[2], "checksum_algorithm": "bnf_ark_mod29",
                              "url": bnf_ark_url(match[1])})
    return links


def clean(value):
    """Retire les caractères de non-tri sans supprimer les mots qu'ils entourent."""
    return " ".join(unicodedata.normalize("NFC", value.replace("\x98", "").replace("\x9c", "")).split()) or None


def children(node, name):
    return [child for child in node if isinstance(child.tag, str) and etree.QName(child).localname == name]


def field_values(field, code):
    return [{"raw": sub["raw"], "value": clean(sub["raw"]), "subfield_index": sub["subfield_index"]}
            for sub in field["subfields"] if sub["code"] == code]


def values(field, code):
    return [item["value"] for item in field_values(field, code) if item["value"] is not None]


def ref(field):
    return {key: field[key] for key in ("source_field", "field_index", "occurrence", "ind1", "ind2")}


def year_number(value):
    return int(value) if re.fullmatch(r"[0-9]{4}", value) and value not in ("0000", "9999") else None


def statement_type(field):
    if field["source_field"] == "210":
        return "legacy_publication_distribution"
    return {"0": "publication", "1": "production", "2": "distribution",
            "3": "manufacture", "4": "copyright"}.get(field["ind2"], "unspecified")


def coded_date(item):
    raw = item["raw"]  # Les positions sont celles du champ brut, sans strip().
    complete = len(raw) >= 17
    code = raw[8] if complete else None
    first, second = (raw[9:13], raw[13:17]) if complete else (None, None)
    return {**item, "date_type": code, "date1_raw": first, "date2_raw": second,
            "date1_year": year_number(first) if first else None,
            "date2_year": year_number(second) if second else None}


def dewey(item):
    value = item["value"]
    candidate = value.replace("/", "") if value else ""
    valid = re.fullmatch(r"[0-9]{3}(?:\.[0-9]+)?", candidate) is not None
    normalized = candidate if valid else None
    return {**item, "dewey_raw": item["raw"], "dewey_normalized": normalized,
            "dewey_1": normalized[:1] if valid else None,
            "dewey_2": normalized[:2] if valid else None,
            "dewey_3": normalized[:3] if valid else None}


def parse_record(record, source):
    identifiers = [node.text or "" for node in children(record, "controlfield") if node.get("tag") == "001"]
    if len(identifiers) != 1 or not re.fullmatch(r"[0-9]{8}[0-9X]", identifiers[0].strip()):
        raise ValueError("PPN 001 absent, multiple ou invalide")
    ppn = identifiers[0].strip()
    occurrences = Counter()
    fields = []
    for index, node in enumerate(children(record, "datafield"), 1):
        tag = node.get("tag")
        occurrences[tag] += 1
        fields.append({"source_field": tag, "field_index": index, "occurrence": occurrences[tag],
                       "ind1": node.get("ind1"), "ind2": node.get("ind2"),
                       "subfields": [{"subfield_index": i, "code": sub.get("code"),
                                      "raw": "".join(sub.itertext())}
                                     for i, sub in enumerate(children(node, "subfield"), 1)]})
    grouped = defaultdict(list)
    for field in fields:
        grouped[field["source_field"]].append(field)
    bnf_links = extract_bnf_links(grouped)
    summaries = [{**ref(f), **item} for f in grouped["330"] for item in field_values(f, "a")]
    titles = [{**ref(f), "main_titles": field_values(f, "a"), "subtitles": field_values(f, "e"),
               "parallel_titles": field_values(f, "d"), "part_numbers": field_values(f, "h"),
               "part_titles": field_values(f, "i")} for f in grouped["200"]]
    main = next((title for title in titles if any(v["value"] for v in title["main_titles"])), None)
    dates = [{**ref(f), **coded_date(item)} for f in grouped["100"] for item in field_values(f, "a")]
    # Aucune année imputée depuis la requête SRU ou une date en texte libre.
    publication_year = None
    if len(dates) == 1 and dates[0]["date_type"] in {"d", "e", "h", "i", "j", "k"}:
        publication_year = dates[0]["date1_year"]
    publication_statements = [{**ref(f), "statement_type": statement_type(f), "places": field_values(f, "a"),
                               "agents": field_values(f, "c"), "dates": field_values(f, "d")}
                              for f in fields if f["source_field"] in {"210", "214"}]
    publishers = [{**ref(f), **item, "statement_type": statement_type(f),
                   "publisher": item["value"] if statement_type(f) in {"publication", "legacy_publication_distribution"} else None}
                  for f in fields if f["source_field"] in {"210", "214"}
                  for item in field_values(f, "c")]
    authors = [{**ref(f), "kind": "person" if f["source_field"].startswith("70") else "corporate",
                "names": field_values(f, "a"),
                "firstnames": field_values(f, "b") if f["source_field"].startswith("70") else [],
                "subdivisions": field_values(f, "b") if f["source_field"].startswith("71") else [],
                "authority_ids": field_values(f, "3"), "roles": field_values(f, "4"),
                "dates": field_values(f, "f"), "qualifiers": field_values(f, "c")}
               for f in fields if f["source_field"] in AUTHOR_TAGS]
    classifications = [{**ref(f), **dewey(item), "editions": field_values(f, "v")}
                       for f in grouped["676"] for item in field_values(f, "a")]
    subjects = [{**ref(f), "subfields": [{**sub, "value": clean(sub["raw"])} for sub in f["subfields"]]}
                for f in fields if f["source_field"] in SUBJECT_TAGS]
    languages = [{**ref(f), **item} for f in grouped["101"] for item in field_values(f, "a")]
    countries = [{**ref(f), **item} for f in grouped["102"] for item in field_values(f, "a")]
    local_links = []
    for f in fields:
        for item in field_values(f, "5"):
            match = re.fullmatch(r"([0-9]{9}):([0-9]{8}[0-9X])", item["value"] or "")
            local_links.append({**ref(f), **item, "rcr_candidate": match[1] if match else None,
                                "exemplar_id_candidate": match[2] if match else None})
    locations, holding_evidence = [], defaultdict(list)
    for f in grouped["930"]:
        rcrs = [{**item, "rcr": item["value"] if re.fullmatch(r"[0-9]{9}", item["value"] or "") else None}
                for item in field_values(f, "b")]
        links = [item for item in local_links if item["field_index"] == f["field_index"]]
        b_set = {item["rcr"] for item in rcrs if item["rcr"]}
        link_set = {item["rcr_candidate"] for item in links if item["rcr_candidate"]}
        comparison = ("match" if b_set == link_set else "mismatch") if b_set and link_set else "not_comparable"
        locations.append({**ref(f), "rcr_values": rcrs, "links_5": links,
                          "comparison_b_5": comparison, "subfields": f["subfields"]})
        for item in rcrs:
            if item["rcr"]:
                holding_evidence[item["rcr"]].append({**ref(f), "subfield_index": item["subfield_index"],
                                                     "raw": item["raw"], "comparison_b_5": comparison})
    holdings = [{"rcr": rcr, "evidence": evidence, "validation_status": "user_confirmed_930b"}
                for rcr, evidence in sorted(holding_evidence.items())]
    return {"ppn": ppn, "source": source, "bnf_links": bnf_links, "summaries": summaries,
            "leader_raw": [n.text or "" for n in children(record, "leader")],
            "controlfields": [{"tag": n.get("tag"), "raw": n.text or ""} for n in children(record, "controlfield")],
            "source_fields": fields, "titles": titles,
            "title": " ; ".join(v["value"] for v in main["main_titles"] if v["value"]) if main else None,
            "subtitle": (" ; ".join(v["value"] for v in main["subtitles"] if v["value"]) or None) if main else None,
            "coded_dates": dates, "publication_year": publication_year,
            "publication_year_source": "100$a[9:13]" if publication_year is not None else None,
            "publication_statements": publication_statements, "languages": languages, "countries": countries,
            "publishers": publishers, "authors": authors, "classifications": classifications, "subjects": subjects,
            "locations": locations, "local_links_5": local_links, "holdings": holdings}


def iter_campaign(run_dir, report):
    """Ne lit que les pages validées du rapport, avec vérification des empreintes."""
    seen, seen_files = set(), set()
    for partition in report["partitions"]:
        for page in partition["pages"]:
            relative = page["file"]
            path = (run_dir / relative).resolve()
            if not path.is_relative_to((run_dir / "pages").resolve()) or path in seen_files:
                raise ValueError(f"Chemin de page invalide ou répété : {relative}")
            seen_files.add(path)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != page["sha256"]:
                raise ValueError(f"Empreinte XML différente : {relative}")
            params = page["params"]
            parsed = parse_page(raw, params["startRecord"], params["maximumRecords"], params["query"])
            if len(parsed.ppns) != page["count"]:
                raise ValueError(f"Nombre de notices différent du rapport : {relative}")
            root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
            for envelope in root.findall("s:records/s:record", NS):
                source = {"collection_id": report["collection_id"], "page_file": relative,
                          "page_sha256": digest,
                          "record_position": int(envelope.findtext("s:recordPosition", namespaces=NS))}
                record = next(n for n in envelope.find("s:recordData", NS) if isinstance(n.tag, str))
                document = parse_record(record, source)
                if document["ppn"] in seen:
                    raise ValueError(f"PPN répété : {document['ppn']}")
                seen.add(document["ppn"])
                yield document
    if len(seen) != report["records_validated"]:
        raise ValueError("Le nombre extrait diffère du nombre validé de la campagne")


def extract_campaign(run_dir: Path, output_dir: Path):
    run_dir, output_dir = Path(run_dir).resolve(), Path(output_dir).resolve()
    if output_dir.is_relative_to(run_dir) or run_dir.is_relative_to(output_dir):
        raise ValueError("Le dossier de sortie doit être distinct de la collecte brute")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Le dossier de sortie doit être vide pour préserver les extractions existantes")
    input_bytes = (run_dir / "report.json").read_bytes()
    collection = json.loads(input_bytes)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {"status": "running", "parser_version": PARSER_VERSION, "started_at": now(),
              "source_run": str(run_dir), "source_report_sha256": hashlib.sha256(input_bytes).hexdigest(),
              "collection_id": collection["collection_id"], "source_collection_status": collection["status"],
              "expected_records": collection["records_validated"], "records_parsed": 0,
              "records_retained": 0, "records_excluded": 0, "exclusions": [],
              "retention_rule": "at_least_one_nonempty_930b",
              "holdings_validation": "user_confirmed_930b", "holdings_deduplication_key": ["ppn", "rcr"],
              "errors": []}
    write_json(output_dir / "report.json", result)
    counts = Counter()
    histogram = Counter()
    rcr_histogram = Counter()
    subject_fields = Counter()
    rcrs_seen = set()
    files = {"documents": None, "bnf_links": "bnf_links", "summaries": "summaries",
             "publishers": "publishers", "authors": "authors",
             "classifications": "classifications", "subjects": "subjects",
             "locations": "locations", "holdings": "holdings"}
    counts.update({name: 0 for name in files})
    try:
        with ExitStack() as stack:
            streams = {name: stack.enter_context((output_dir / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n"))
                       for name in files}
            csv_file = stack.enter_context((output_dir / "localisations_a_verifier.csv").open("w", encoding="utf-8-sig", newline=""))
            writer = csv.DictWriter(csv_file, fieldnames=["ppn", "title", "page_file", "record_position", "zones_930",
                "rcr_distincts_930b", "rcr_930b", "rcr_candidats_5", "rcr_5_absents_de_930b",
                "comparaisons_930b_5_en_desaccord", "valeurs_930b_invalides"], delimiter=";")
            writer.writeheader()
            for document in iter_campaign(run_dir, collection):
                result["records_parsed"] += 1
                if not any(item["value"] is not None for location in document["locations"]
                           for item in location["rcr_values"]):
                    result["records_excluded"] += 1
                    result["exclusions"].append({"ppn": document["ppn"], "source": document["source"],
                                                 "reason": "missing_or_empty_930b"})
                    continue
                result["records_retained"] += 1
                for name, key in files.items():
                    rows = [document] if key is None else [{"ppn": document["ppn"], "source": document["source"], **row}
                                                          for row in document[key]]
                    for row in rows:
                        streams[name].write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts[name] += len(rows)
                locations = document["locations"]
                subject_fields.update(subject["source_field"] for subject in document["subjects"])
                counts["records_with_subjects"] += bool(document["subjects"])
                counts["records_with_summaries"] += any(item["value"] is not None for item in document["summaries"])
                counts["records_with_bnf_links"] += bool(document["bnf_links"])
                counts["bnf_links_from_033a"] += sum(link["origin"] == "033a" for link in document["bnf_links"])
                counts["bnf_links_from_035a"] += sum(link["origin"] == "035a" for link in document["bnf_links"])
                counts["records_with_bnf_links_from_035a"] += any(link["origin"] == "035a" for link in document["bnf_links"])
                observed = {h["rcr"] for h in document["holdings"]}
                counts["duplicate_rcr_occurrences_collapsed"] += sum(len(h["evidence"]) - 1 for h in document["holdings"])
                candidates = {link["rcr_candidate"] for link in document["local_links_5"] if link["rcr_candidate"]}
                conflicts = sum(loc["comparison_b_5"] == "mismatch" for loc in locations)
                invalid = sum(item["rcr"] is None for loc in locations for item in loc["rcr_values"])
                histogram[len(locations)] += 1
                rcr_histogram[len(observed)] += 1
                rcrs_seen.update(observed)
                counts["930_b_5_mismatches"] += conflicts
                counts["invalid_930b_values"] += invalid
                writer.writerow({"ppn": document["ppn"], "title": document["title"],
                    "page_file": document["source"]["page_file"], "record_position": document["source"]["record_position"],
                    "zones_930": len(locations), "rcr_distincts_930b": len(observed), "rcr_930b": " | ".join(sorted(observed)),
                    "rcr_candidats_5": " | ".join(sorted(candidates)), "rcr_5_absents_de_930b": " | ".join(sorted(candidates-observed)),
                    "comparaisons_930b_5_en_desaccord": conflicts, "valeurs_930b_invalides": invalid})
        result.update(status="complete", counts=dict(counts), subjects_by_field=dict(sorted(subject_fields.items())),
                      zones_930_per_record=dict(sorted(histogram.items())),
                      distinct_rcr_per_record=dict(sorted(rcr_histogram.items())), distinct_rcr=len(rcrs_seen))
    except Exception as exc:
        result["status"] = "failed"
        result["errors"].append(str(exc))
        raise
    finally:
        result["finished_at"] = now()
        write_json(output_dir / "report.json", result)
    return result
