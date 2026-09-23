"""Classifications d'autorités reliées exclusivement aux têtes 606$a."""

import json
import re
from collections import Counter
from pathlib import Path

import httpx
from lxml import etree

from analyseur_sudoc.enrichment import cached_fetch, digest, read_jsonl, write_jsonl
from analyseur_sudoc.sudoc import now, write_json
from analyseur_sudoc.unimarc import children, clean, dewey

VERSION = "0.1.0"
PPN = re.compile(r"[0-9]{8}[0-9X]")


def heading_links(document):
    """Dans l'export, seul le $3 immédiatement avant le $a lui appartient."""
    result = []
    for field in document["subjects"]:
        if field["source_field"] != "606":
            continue
        subs = field["subfields"]
        for index, sub in enumerate(subs):
            if sub["code"] != "a":
                continue
            previous = subs[index - 1] if index else None
            identifier = previous["raw"].strip() if previous and previous["code"] == "3" else None
            # Deux $3 contigus avant un $a ne sont pas un lien univoque.
            ambiguous = index >= 2 and subs[index - 1]["code"] == subs[index - 2]["code"] == "3"
            status = "linked" if identifier and PPN.fullmatch(identifier) and not ambiguous else (
                "ambiguous_identifier" if ambiguous else "invalid_identifier" if identifier is not None else "no_identifier")
            result.append(dict(source_field="606", field_index=field["field_index"],
                               occurrence=field["occurrence"], subfield_index=sub["subfield_index"],
                               heading_raw=sub["raw"], heading=clean(sub["raw"]),
                               authority_ppn=identifier if status == "linked" else None,
                               identifier_raw=previous["raw"] if previous and previous["code"] == "3" else None,
                               identifier_subfield_index=previous["subfield_index"] if identifier is not None else None,
                               status=status))
    return result


def parse_authority(raw, requested_ppn, include_rameau):
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    if etree.QName(root).localname != "record":
        raise ValueError("Notice XML IdRef attendue")
    ids = [n.text or "" for n in children(root, "controlfield") if n.get("tag") == "001"]
    if len(ids) != 1 or not PPN.fullmatch(ids[0]):
        raise ValueError("Identifiant 001 IdRef absent ou invalide")
    canonical = ids[0]
    fields = children(root, "datafield")
    former = ["".join(s.itertext()).strip() for f in fields if f.get("tag") == "035"
              for s in children(f, "subfield") if s.get("code") == "a"]
    if canonical != requested_ppn and requested_ppn not in former:
        return dict(status="identity_to_review", authority_ppn=canonical, classifications=[])
    classifications, occurrences, labels = [], Counter(), []
    for index, field in enumerate(fields, 1):
        tag = field.get("tag")
        occurrences[tag] += 1
        subs = [dict(code=s.get("code"), raw="".join(s.itertext()), subfield_index=i)
                for i, s in enumerate(children(field, "subfield"), 1)]
        if tag in {"250", "280"}:
            labels.extend(s["raw"] for s in subs if s["code"] == "a")
        schemes = [clean(s["raw"]) for s in subs if s["code"] == "2"]
        if tag == "676":
            scheme = "dewey"
        elif tag == "686" and include_rameau and schemes and all(
                s and s.casefold() == "note de regroupement par domaine" for s in schemes):
            scheme = "rameau_domain"
        else:
            continue
        for sub in subs:
            if sub["code"] != "a":
                continue
            normalized = dewey(dict(raw=sub["raw"], value=clean(sub["raw"]))) if scheme == "dewey" else None
            # Un domaine n'est ni une Dewey de document, ni un indice à développer.
            code = normalized["dewey_normalized"] if normalized else clean(sub["raw"])
            classifications.append(dict(scheme=scheme, code_raw=sub["raw"], code=code,
                source=f"idref:authority:{tag}$a", source_field=tag, field_index=index,
                occurrence=occurrences[tag], subfield_index=sub["subfield_index"],
                ind1=field.get("ind1"), ind2=field.get("ind2"),
                classification_identifiers=schemes, source_subfields=subs,
                normalization=normalized, authority_ppn=canonical))
    return dict(status="resolved" if canonical == requested_ppn else "resolved_former_identifier",
                authority_ppn=canonical, labels=labels, classifications=classifications)


def collect_authorities(input_dir, run_dir, client, delay=0.3):
    input_dir, run_dir = Path(input_dir).resolve(), Path(run_dir).resolve()
    if input_dir.is_relative_to(run_dir) or run_dir.is_relative_to(input_dir):
        raise ValueError("Dossier de sortie distinct requis")
    raw_input = (input_dir / "documents.jsonl").read_bytes()
    parent = json.loads((input_dir / "report.json").read_text(encoding="utf-8"))
    if parent["status"] != "complete" or digest(raw_input) != parent["documents_sha256"]:
        raise ValueError("Entrée incomplète ou empreinte modifiée")
    docs = read_jsonl(input_dir / "documents.jsonl")
    if len(docs) != parent["records"] or len({d["ppn"] for d in docs}) != len(docs):
        raise ValueError("Nombre ou unicité des documents invalide")
    links = [h for d in docs for h in heading_links(d)]
    targets = sorted({h["authority_ppn"] for h in links if h["status"] == "linked"})
    manifest = dict(version=VERSION, input_dir=str(input_dir), documents_sha256=digest(raw_input),
                    selection="606$a_immediately_preceded_by_3", targets=targets, delay_seconds=delay)
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Campagne incompatible avec la reprise")
    write_json(manifest_path, manifest)
    collection_path = run_dir / "collection-report.json"
    prior = json.loads(collection_path.read_text(encoding="utf-8")) if collection_path.exists() else {}
    prior_results = {x["requested_ppn"]: x for x in prior.get("authorities", [])}
    report = dict(status="running", started_at=prior.get("started_at", now()), records=len(docs),
                  headings=len(links), linked_headings=sum(h["status"] == "linked" for h in links),
                  targets=len(targets), authorities=[])
    write_json(collection_path, report)
    for index, ppn in enumerate(targets, 1):
        previous = prior_results.get(ppn)
        if previous and previous["status"] == "not_found":
            result = previous
        else:
            try:
                raw, meta = cached_fetch(client, f"https://www.idref.fr/{ppn}.xml", run_dir / "authorities" / f"{ppn}.xml", delay)
                # Valider la structure et l'identité dès la collecte, sans décider des classes à extraire.
                parsed = parse_authority(raw, ppn, False)
                result = dict(requested_ppn=ppn, status=parsed["status"], authority_ppn=parsed["authority_ppn"], source=meta)
            except httpx.HTTPStatusError as exc:
                result = dict(requested_ppn=ppn, status="not_found" if exc.response.status_code in {404, 410} else "error",
                              http_status=exc.response.status_code, error=str(exc), attempted_at=now())
            except (httpx.HTTPError, ValueError, etree.XMLSyntaxError) as exc:
                result = dict(requested_ppn=ppn, status="error", error=str(exc), attempted_at=now())
        report["authorities"].append(result)
        if index % 50 == 0 or index == len(targets):
            report["processed"] = index
            write_json(collection_path, report)
            print(f"IdRef 606$a : {index}/{len(targets)} autorités", flush=True)
    report.update(status="partial" if any(r["status"] == "error" for r in report["authorities"]) else "complete",
                  finished_at=now(), statuses=dict(Counter(r["status"] for r in report["authorities"])))
    write_json(collection_path, report)
    return report


def enrich_documents(run_dir, include_rameau):
    run_dir = Path(run_dir).resolve()
    prior_report_path = run_dir / "report.json"
    if prior_report_path.exists():
        prior_report = json.loads(prior_report_path.read_text(encoding="utf-8"))
        if prior_report["include_rameau"] != include_rameau:
            raise ValueError("Sortie existante avec un autre choix de classifications")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    collection = json.loads((run_dir / "collection-report.json").read_text(encoding="utf-8"))
    if collection["status"] != "complete":
        raise ValueError("Collecte incomplète, reprendre la collecte")
    input_dir = Path(manifest["input_dir"])
    if digest((input_dir / "documents.jsonl").read_bytes()) != manifest["documents_sha256"]:
        raise ValueError("Entrée modifiée")
    source_report = json.loads((input_dir / "report.json").read_text(encoding="utf-8"))
    docs = read_jsonl(input_dir / "documents.jsonl")
    authorities = {}
    for entry in collection["authorities"]:
        if "source" in entry:
            raw = Path(entry["source"]["file"]).read_bytes()
            if digest(raw) != entry["source"]["sha256"]:
                raise ValueError("Cache d'autorité modifié")
            result = parse_authority(raw, entry["requested_ppn"], include_rameau)
        else:
            result = dict(status=entry["status"], authority_ppn=None, classifications=[])
        authorities[entry["requested_ppn"]] = {**entry, **result}
    report = dict(status="complete", version=VERSION, created_at=now(), records=len(docs),
                  include_rameau=include_rameau, input_documents_sha256=manifest["documents_sha256"],
                  collection_statuses=collection["statuses"], unique_authorities=len(authorities))
    counts, statuses = Counter(), Counter()
    exported = []
    for d in docs:
        links = heading_links(d)
        additions = []
        for link in links:
            if link["status"] == "linked":
                authority = authorities[link["authority_ppn"]]
                link["status"] = authority["status"]
                link["resolved_authority_ppn"] = authority["authority_ppn"]
                link["authority_source"] = authority.get("source")
                link["classification_count"] = len(authority["classifications"])
                for value in authority["classifications"]:
                    addition = {**value, "via_606a": dict(link), "authority_source": authority.get("source")}
                    additions.append(addition)
                    exported.append(dict(ppn=d["ppn"], **addition))
            statuses[link["status"]] += 1
        # Ne jamais ajouter les classes d'autorité à classifications (Dewey document).
        d["idref_606a_links"] = links
        d["idref_606a_classifications"] = additions
        counts["documents_with_606a"] += bool(links)
        counts["documents_with_authority_classification"] += bool(additions)
        for scheme in ("dewey", "rameau_domain"):
            counts[f"documents_with_{scheme}"] += any(v["scheme"] == scheme for v in additions)
            counts[f"{scheme}_occurrences"] += sum(v["scheme"] == scheme for v in additions)
    write_jsonl(run_dir / "documents.jsonl", docs)
    write_jsonl(run_dir / "authority-classifications.jsonl", exported)
    write_jsonl(run_dir / "authority-results.jsonl", authorities.values())
    report.update(counts=dict(counts), heading_statuses=dict(statuses),
                  documents_sha256=digest((run_dir / "documents.jsonl").read_bytes()),
                  document_dewey_unchanged=all(d["classifications"] == original["classifications"]
                      for d, original in zip(docs, read_jsonl(input_dir / "documents.jsonl"))))
    # Le référentiel reste celui du même lot, sans nouvelle collecte RCR.
    library_bytes = (input_dir / "libraries.jsonl").read_bytes()
    if digest(library_bytes) != source_report["libraries_sha256"]:
        raise ValueError("Référentiel d'entrée modifié")
    (run_dir / "libraries.jsonl").write_bytes(library_bytes)
    report.update(libraries=source_report["libraries"], libraries_sha256=digest(library_bytes))
    write_json(run_dir / "report.json", report)
    lines = ["# Classifications des autorités liées aux 606$a", "",
             f"Notices traitées : {len(docs)} ; autorités distinctes : {len(authorities)}.", "",
             "Toutes les notices sont traitées, même si une Dewey Sudoc ou BnF existe déjà.",
             "Les autorités des autres zones et des subdivisions 606$x/$y/$z ne sont pas suivies.", "",
             "| Mesure | Nombre |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(counts.items())]
    lines += ["", "## Statut des liens 606$a", "", "| Statut | Occurrences |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(statuses.items())]
    lines += ["", "## Interprétation", "",
              "`dewey` désigne les 676$a des autorités. `rameau_domain` désigne les 686$a identifiés par « Note de regroupement par domaine » ; ces codes ne sont pas assimilés à une Dewey bibliographique.",
              "Les autres systèmes (MeSH, etc.) sont ignorés. Aucun classement n'est inventé pour les autorités sans classe ou les têtes sans identifiant.",
              "`classifications` conserve les Dewey Sudoc/BnF intactes. Les nouvelles données sont dans `idref_606a_links` et `idref_606a_classifications` de documents.jsonl.",
              "Les répétitions et les chemins document → 606$a → autorité → classification restent présents. Pour compter des classes distinctes par document, dédoublonner par PPN, système et code."]
    (run_dir / "rapport.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
