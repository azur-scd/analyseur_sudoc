"""Enrichissement borné du lot : BnF puis RCR IdRef, avec cache et provenance."""

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from lxml import etree

from analyseur_sudoc.database import FIELDS
from analyseur_sudoc.libraries import LISTRCR_URL, extract_library_type, fetch, parse_listrcr
from analyseur_sudoc.sudoc import now, write_json
from analyseur_sudoc.unimarc import children, clean, dewey


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_report(path, report):
    for attempt in range(5):
        try:
            write_json(path, report)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))


def ark_from_url(url):
    parsed = urlsplit(url)
    if parsed.hostname != "catalogue.bnf.fr":
        raise ValueError(f"Domaine BnF inattendu : {url}")
    match = re.fullmatch(r"/(ark:/12148/cb[0-9]{8}[0-9bcdfghjkmnpqrstvwxz])(?:/.*)?", parsed.path)
    if not match:
        raise ValueError(f"ARK BnF invalide : {url}")
    return match[1]


def parse_bnf(raw, ark=None):
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {"s": "http://www.loc.gov/zing/srw/"}
    if root.xpath('//*[local-name()="diagnostic"]'):
        raise ValueError("Diagnostic SRU BnF")
    count = int(root.findtext("s:numberOfRecords", namespaces=ns))
    records = root.findall("s:records/s:record/s:recordData/*", ns)
    if count == 0 and not records:
        return dict(status="not_found", classifications=[])
    if count != 1:
        if ark is None:
            return dict(status="multiple_matches", number_of_records=count, classifications=[])
        raise ValueError("La recherche ARK ne retourne pas une notice unique")
    if len(records) != 1:
        raise ValueError("La réponse BnF unique ne contient pas exactement une notice")
    record = records[0]
    if (ark is not None and record.get("id") != ark) or record.get("format", "").upper() != "UNIMARC":
        return dict(status="identity_to_review", returned_id=record.get("id"), classifications=[])
    values, occurrences = [], Counter()
    title = []
    for index, field in enumerate(children(record, "datafield"), 1):
        tag = field.get("tag")
        occurrences[tag] += 1
        for subindex, sub in enumerate(children(field, "subfield"), 1):
            text = "".join(sub.itertext())
            if tag == "200" and sub.get("code") == "a":
                title.append(clean(text))
            if tag == "676" and sub.get("code") == "a":
                values.append({**dewey(dict(raw=text, value=clean(text), subfield_index=subindex)),
                               "source_field": "676", "field_index": index, "occurrence": occurrences[tag],
                               "ind1": field.get("ind1"), "ind2": field.get("ind2"),
                               "dewey_source": "bnf:676$a", "bnf_ark": ark,
                               "editions": [{"raw": "".join(s.itertext()), "value": clean("".join(s.itertext()))}
                                            for s in children(field, "subfield") if s.get("code") == "v"]})
    return dict(status="matched", returned_id=record.get("id"), title=title, classifications=values)


def bnf_identifiers(document):
    """Identifiants imprimés du Sudoc, sans les mentions de prix ou de reliure."""
    found = []
    for field in document.get("source_fields", []):
        kind = {"010": "isbn", "073": "ean"}.get(field["source_field"])
        if kind is None:
            continue
        for sub in field["subfields"]:
            if sub["code"] != "a":
                continue
            value = re.sub(r"[\s-]", "", sub["raw"]).upper()
            if (kind == "isbn" and re.fullmatch(r"(?:[0-9]{9}[0-9X]|[0-9]{13})", value)
                    or kind == "ean" and re.fullmatch(r"[0-9]{13}", value)):
                pair = (kind, value)
                if pair not in found:
                    found.append(pair)
    return found


def preferred_bnf_search(document):
    """Une seule recherche par notice : ARK, sinon EAN, sinon ISBN."""
    if document["bnf_links"]:
        return "ark", sorted({v["url"] for v in document["bnf_links"]})[0]
    identifiers = bnf_identifiers(document)
    for kind in ("ean", "isbn"):
        for candidate_kind, value in identifiers:
            if candidate_kind == kind:
                return kind, value
    return None


def cached_fetch(client, url, path, delay):
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if path.exists() and meta_path.exists():
        raw = path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["url"] != str(url) or meta["sha256"] != digest(raw):
            raise ValueError(f"Cache modifié : {path}")
        # Un diagnostic SRU est une réponse d'erreur transitoire, pas une notice à réutiliser.
        if path.suffix != ".xml" or not (b"<srw:diagnostics>" in raw or b"<diagnostics>" in raw):
            return raw, meta
    raw = fetch(client, url, delay=delay)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    meta = dict(url=str(url), retrieved_at=now(), sha256=digest(raw), file=str(path.resolve()))
    write_json(meta_path, meta)
    return raw, meta


def enrich(input_dir, run_dir, client, prior_reference=None, delay=0.3):
    input_dir, run_dir = Path(input_dir).resolve(), Path(run_dir).resolve()
    if input_dir.is_relative_to(run_dir) or run_dir.is_relative_to(input_dir):
        raise ValueError("Sortie distincte de l'extraction requise")
    payload = (input_dir / "documents.jsonl").read_bytes()
    documents = read_jsonl(input_dir / "documents.jsonl")
    if len({d["ppn"] for d in documents}) != len(documents):
        raise ValueError("PPN répété")
    extraction = json.loads((input_dir / "report.json").read_text(encoding="utf-8"))
    if extraction["status"] != "complete" or extraction["counts"]["documents"] != len(documents):
        raise ValueError("Extraction invalide ou incomplète")
    manifest = dict(version="0.3.0", input_dir=str(input_dir), documents_sha256=digest(payload),
                    policy="one_bnf_query_per_document_ark_else_ean_else_isbn_fuzzy", delay_seconds=delay)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Campagne existante avec paramètres différents")
    write_json(manifest_path, manifest)
    report = dict(started_at=now(), status="running", errors=[], bnf=[], rcr_warnings=[])
    report_path = run_dir / "report.json"
    write_report(report_path, report)
    candidates = [d for d in documents if not any(v["dewey_normalized"] for v in d["classifications"])
                  and (d["bnf_links"] or bnf_identifiers(d))]
    for d in candidates:
        kind, identifier = preferred_bnf_search(d)
        try:
            if kind == "ark":
                ark = ark_from_url(identifier)
                request = httpx.Request("GET", "https://catalogue.bnf.fr/api/SRU", params={
                    "version": "1.2", "operation": "searchRetrieve", "query": f'bib.persistentid any "{ark}"',
                    "recordSchema": "unimarcXchange", "maximumRecords": 2, "startRecord": 1})
                cache_name = ark.rsplit("/", 1)[-1]
            else:
                request = httpx.Request("GET", "https://catalogue.bnf.fr/api/SRU", params={
                    "version": "1.2", "operation": "searchRetrieve",
                    "query": f'bib.fuzzyISBN any "{identifier}"',
                    "recordSchema": "unimarcXchange", "maximumRecords": 2, "startRecord": 1})
                cache_name = f"fuzzy-{kind}-{identifier}"
            raw, meta = cached_fetch(client, request.url, run_dir / "bnf" / f"{cache_name}.xml", delay)
            result = parse_bnf(raw, ark if kind == "ark" else None)
            for item in result["classifications"]:
                item["enrichment_source"] = meta
                item["bnf_match_method"] = kind
                item["bnf_match_identifier"] = identifier
                if kind != "ark":
                    item["bnf_ark"] = result["returned_id"]
                d["classifications"].append(item)
            report["bnf"].append(dict(ppn=d["ppn"], search_field=kind,
                                      searched_identifier=identifier, **result))
        except (httpx.HTTPError, ValueError, etree.XMLSyntaxError, TypeError) as exc:
            report["errors"].append(dict(service="bnf", ppn=d["ppn"], search_field=kind,
                                         searched_identifier=identifier, error=str(exc)))
        write_report(report_path, report)
    targets = {h["rcr"] for d in documents for h in d["holdings"]}
    raw, meta = cached_fetch(client, LISTRCR_URL, run_dir / "references" / "listrcr.tsv", delay)
    all_libraries = parse_listrcr(raw, meta["retrieved_at"], report["rcr_warnings"])
    known = {row["rcr"]: row for row in all_libraries}
    libraries = []
    for index, rcr in enumerate(sorted(targets), 1):
        row = known.get(rcr)
        if row is None:
            row = dict.fromkeys(FIELDS)
            row["rcr"] = rcr
            report["rcr_warnings"].append(dict(rcr=rcr, reason="absent_listrcr"))
        else:
            row = dict(row)
            row["reference_source"] = meta
        ppn = row["library_ppn"]
        if ppn:
            try:
                previous = Path(prior_reference) / "idref" / f"{ppn}.json" if prior_reference else None
                if previous and previous.exists():
                    raw = previous.read_bytes()
                    source = dict(file=str(previous.resolve()), sha256=digest(raw), reused=True,
                                  url=f"https://www.idref.fr/{ppn}.json")
                else:
                    raw, source = cached_fetch(client, f"https://www.idref.fr/{ppn}.json",
                                              run_dir / "references" / "idref" / f"{ppn}.json", delay)
                row["library_type"] = extract_library_type(json.loads(raw))
                row["idref_source"] = source
            except (httpx.HTTPError, ValueError) as exc:
                report["errors"].append(dict(service="idref", rcr=rcr, ppn=ppn, error=str(exc)))
        libraries.append(row)
        if index % 20 == 0 or index == len(targets):
            print(f"IdRef : {index}/{len(targets)} RCR", flush=True)
            write_report(report_path, report)
    write_jsonl(run_dir / "documents.jsonl", documents)
    write_jsonl(run_dir / "libraries.jsonl", libraries)
    report.update(status="complete" if not report["errors"] else "partial", finished_at=now(),
                  records=len(documents), bnf_candidates=len(candidates),
                  records_with_dewey=sum(any(v["dewey_normalized"] for v in d["classifications"]) for d in documents),
                  records_enriched=sum(any(v.get("dewey_source") == "bnf:676$a" and v["dewey_normalized"] for v in d["classifications"]) for d in candidates),
                  libraries=len(libraries), libraries_with_type=sum(bool(r["library_type"]) for r in libraries),
                  unknown_rcr=sorted(targets - known.keys()),
                  documents_sha256=digest((run_dir / "documents.jsonl").read_bytes()),
                  libraries_sha256=digest((run_dir / "libraries.jsonl").read_bytes()))
    write_report(report_path, report)
    return report
