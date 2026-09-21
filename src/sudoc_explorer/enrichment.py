"""Enrichissement borné du lot : BnF puis RCR IdRef, avec cache et provenance."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from lxml import etree

from sudoc_explorer.database import FIELDS
from sudoc_explorer.libraries import LISTRCR_URL, extract_library_type, fetch, parse_listrcr
from sudoc_explorer.sudoc import now, write_json
from sudoc_explorer.unimarc import children, clean, dewey


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def ark_from_url(url):
    parsed = urlsplit(url)
    if parsed.hostname != "catalogue.bnf.fr":
        raise ValueError(f"Domaine BnF inattendu : {url}")
    match = re.fullmatch(r"/(ark:/12148/cb[0-9]{8}[0-9bcdfghjkmnpqrstvwxz])(?:/.*)?", parsed.path)
    if not match:
        raise ValueError(f"ARK BnF invalide : {url}")
    return match[1]


def parse_bnf(raw, ark):
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {"s": "http://www.loc.gov/zing/srw/"}
    if root.xpath('//*[local-name()="diagnostic"]'):
        raise ValueError("Diagnostic SRU BnF")
    count = int(root.findtext("s:numberOfRecords", namespaces=ns))
    records = root.findall("s:records/s:record/s:recordData/*", ns)
    if count == 0 and not records:
        return dict(status="not_found", classifications=[])
    if count != 1 or len(records) != 1:
        raise ValueError("La recherche ARK ne retourne pas une notice unique")
    record = records[0]
    if record.get("id") != ark or record.get("format", "").upper() != "UNIMARC":
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
    return dict(status="matched", title=title, classifications=values)


def cached_fetch(client, url, path, delay):
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if path.exists() and meta_path.exists():
        raw = path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["url"] != str(url) or meta["sha256"] != digest(raw):
            raise ValueError(f"Cache modifié : {path}")
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
    manifest = dict(version="0.1.0", input_dir=str(input_dir), documents_sha256=digest(payload),
                    policy="bnf_existing_links_only_missing_usable_dewey", delay_seconds=delay)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Campagne existante avec paramètres différents")
    write_json(manifest_path, manifest)
    report = dict(started_at=now(), status="running", errors=[], bnf=[], rcr_warnings=[])
    report_path = run_dir / "report.json"
    write_json(report_path, report)
    candidates = [d for d in documents if d["bnf_links"] and not any(v["dewey_normalized"] for v in d["classifications"])]
    for d in candidates:
        for url in sorted({v["url"] for v in d["bnf_links"]}):
            try:
                ark = ark_from_url(url)
                request = httpx.Request("GET", "https://catalogue.bnf.fr/api/SRU", params={
                    "version": "1.2", "operation": "searchRetrieve", "query": f'bib.persistentid any "{ark}"',
                    "recordSchema": "unimarcXchange", "maximumRecords": 2, "startRecord": 1})
                raw, meta = cached_fetch(client, request.url, run_dir / "bnf" / (ark.rsplit("/", 1)[-1] + ".xml"), delay)
                result = parse_bnf(raw, ark)
                for item in result["classifications"]:
                    item["enrichment_source"] = meta
                    d["classifications"].append(item)
                report["bnf"].append(dict(ppn=d["ppn"], requested_url=url, **result))
                print(f"BnF {d['ppn']} : {result['status']}, {len(result['classifications'])} Dewey", flush=True)
            except (httpx.HTTPError, ValueError, etree.XMLSyntaxError, TypeError) as exc:
                report["errors"].append(dict(service="bnf", ppn=d["ppn"], url=url, error=str(exc)))
            write_json(report_path, report)
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
            write_json(report_path, report)
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
    write_json(report_path, report)
    return report
