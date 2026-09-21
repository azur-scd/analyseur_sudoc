"""Audit local et non destructif des documents UNIMARC extraits."""

import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from sudoc_explorer.sudoc import now, write_json

AUDIT_VERSION = "0.2.0"


def audit_documents(documents, year):
    distributions = defaultdict(Counter)
    coverage = Counter()
    anomalies = []
    lengths = []
    seen = set()
    for d in documents:
        ppn = d["ppn"]
        if ppn in seen:
            raise ValueError(f"PPN répété : {ppn}")
        seen.add(ppn)

        def flag(rule, category, message, evidence):
            anomalies.append(dict(ppn=ppn, title=d.get("title"), rule=rule,
                                  category=category, message=message, evidence=evidence,
                                  source=d["source"]))

        def distribute(name, values):
            distributions[name].update(set(str(v) for v in values if v is not None))

        fields = d["source_fields"]

        def raw(tag, code):
            return [s["raw"] for f in fields if f["source_field"] == tag
                    for s in f["subfields"] if s["code"] == code]

        for key, pattern in [("countries", r"[A-Z]{2}"), ("languages", r"[a-z]{3}")]:
            vals = [x["value"] for x in d[key] if x["value"]]
            coverage[key] += bool(vals)
            distribute(key, vals)
            distributions[key + "_per_record"][str(len(set(vals)))] += 1
            if not vals:
                flag(key + "_missing", "lacune", "Aucune valeur non vide", d[key])
            invalid = [v for v in vals if not re.fullmatch(pattern, v)]
            if invalid:
                flag(key + "_syntax", "anomalie", "Syntaxe du code inattendue (sans validation référentielle)", invalid)
            special = sorted(set(vals) & ({"XX", "ZZ"} if key == "countries" else {"und", "mul", "zxx"}))
            if special:
                flag(key + "_special", "a_verifier", "Code spécial : interprétation à examiner, pas une erreur de syntaxe", special)

        dates = d["coded_dates"]
        pubyear = d["publication_year"]
        coverage["publication_year"] += pubyear is not None
        distribute("publication_year", [pubyear if pubyear is not None else "indeterminee"])
        distribute("date_type", [v["date_type"] or "absent" for v in dates])
        if pubyear is None:
            flag("year_uncertain", "a_verifier", "Année unique non dérivée de 100$a", dates)
        elif pubyear != year:
            flag("year_outside", "hors_perimetre", "Année dérivée différente de l'année demandée", dates)
        text_dates = [v["value"] for p in d["publication_statements"]
                      if p["statement_type"] in {"publication", "legacy_publication_distribution"}
                      for v in p["dates"] if v["value"]]
        distribute("publication_date_text", text_dates)
        text_years = set(int(v) for text in text_dates for v in re.findall(r"(?<!\d)[12]\d{3}(?!\d)", text))
        if pubyear is not None and text_years and pubyear not in text_years:
            flag("date_disagreement", "a_verifier", "100$a et années repérées en 210/214 de publication diffèrent", text_dates)

        dew = d["classifications"]
        valid = [v for v in dew if v["dewey_normalized"]]
        coverage["dewey_present"] += bool(dew)
        coverage["dewey_usable"] += bool(valid)
        distributions["dewey_occurrences_per_record"][str(len(dew))] += 1
        for level in (1, 2, 3):
            distribute(f"dewey_{level}", [v[f"dewey_{level}"] for v in valid])
        if not dew:
            flag("dewey_missing", "lacune", "Pas de 676$a", [])
        invalid = [v for v in dew if not v["dewey_normalized"]]
        if invalid:
            flag("dewey_unusable", "a_verifier", "Notation non normalisée par le parseur (pas nécessairement erronée)", invalid)

        subjects = d["subjects"]
        usable_subjects = [s for s in subjects if any(v.get("value") for v in s["subfields"]
                                                   if v["code"] not in {"2", "5", "6", "7", "8"})]
        coverage["subjects"] += bool(usable_subjects)
        distribute("subject_tags", [s["source_field"] for s in subjects])
        distributions["subject_occurrences_per_record"][str(len(subjects))] += 1
        distributions["subject_occurrences_by_tag"].update(s["source_field"] for s in subjects)
        distribute("subject_vocabularies", [v.get("value") for s in subjects for v in s["subfields"] if v["code"] == "2"])
        linked = [s for s in subjects if any(v["code"] == "3" and v.get("value") for v in s["subfields"])]
        coverage["subjects_with_authority"] += bool(linked)
        if not usable_subjects:
            flag("subjects_missing", "lacune", "Aucune indexation 600–620 exploitable", subjects)
        if len(usable_subjects) != len(subjects):
            flag("subjects_empty", "a_verifier", "Zone sujet sans contenu ni identifiant", [s for s in subjects if s not in usable_subjects])

        summaries = [s["value"] for s in d["summaries"] if s["value"]]
        coverage["summaries"] += bool(summaries)
        distributions["summaries_per_record"][str(len(summaries))] += 1
        lengths.extend(len(s) for s in summaries)
        if not summaries:
            flag("summary_missing", "lacune", "Aucun résumé 330$a non vide", [])
        if len(set(summaries)) < len(summaries):
            flag("summary_duplicate", "a_verifier", "Résumé normalisé répété à l'identique dans la notice", [v for v, n in Counter(summaries).items() if n > 1])
        short = [s for s in summaries if len(s) < 80]
        if short:
            flag("summary_short", "a_verifier", "Résumé inférieur à 80 caractères (seuil exploratoire)", short)
        coverage["dewey_and_subjects_and_summary"] += bool(valid and usable_subjects and summaries)

        leaders = d["leader_raw"]
        leader_types = d.get("leader_types", [dict(record_type=v[6] if len(v) > 6 else None,
                            bibliographic_level=v[7] if len(v) > 7 else None,
                            type_code=v[6:8] if len(v) > 7 else None) for v in leaders])
        kind = leader_types[0]["type_code"] if len(leader_types) == 1 else None
        coverage["leader_type_level"] += bool(kind and kind.strip())
        distribute("leader_type_level", [v["type_code"] or "inconnu" for v in leader_types] or ["inconnu"])
        distribute("leader_record_type", [v["record_type"] for v in leader_types])
        distribute("leader_bibliographic_level", [v["bibliographic_level"] for v in leader_types])
        type_fields = {}
        for key, tag in [("content_types", "181"), ("media_types", "182")]:
            occurrences = d.get(key, [f for f in fields if f["source_field"] == tag])
            type_fields[tag] = occurrences
            coverage[key + "_present"] += bool(occurrences)
            distributions[key + "_occurrences_per_record"][str(len(occurrences))] += 1
            code_values = []
            for field in occurrences:
                vocab = sorted({s["raw"].strip() for s in field["subfields"] if s["code"] == "2" and s["raw"].strip()})
                for sub in field["subfields"]:
                    if sub["code"] in {"a", "b", "c"} and sub["raw"].strip():
                        code_values.append((sub["code"], sub["raw"], " + ".join(vocab) or "sans $2"))
            coverage[key + "_coded"] += bool(code_values)
            for subcode in ("a", "b", "c"):
                vals = [json.dumps([vocab, value], ensure_ascii=False) for code, value, vocab in code_values if code == subcode]
                distribute(f"{tag}_{subcode}_by_vocabulary", vals)
                distributions[f"{tag}_{subcode}_occurrences"].update(vals)
            if not code_values:
                flag(key + "_missing", "lacune", f"Aucun code non vide en {tag}$a/$b/$c", occurrences)
        first_nature = d.get("nature_of_content", [{"code": v[4] if len(v) > 4 else None, "raw": v} for v in raw("105", "a")])
        meaningful = [v["code"] for v in first_nature if v["code"] not in {None, "", " ", "|", "#"}]
        coverage["nature_105_position_4"] += bool(meaningful)
        distribute("nature_105_position_4", [v["code"] if v["code"] is not None else "champ_court" for v in first_nature] or ["absent"])
        if not meaningful:
            flag("nature_105_position_4_missing", "lacune", "105$a position 4 absent, court ou non renseigné", first_nature)
        if kind not in {"am", "rm"}:
            flag("leader_scope", "a_verifier", "Type/niveau du label différent des am/rm observés dans le lot", leaders)
        if kind == "rm":
            flag("physical_object", "a_verifier", "Objet/multisupport : vérifier l'adéquation au périmètre physique", raw("215", "a"))
        forms = raw("106", "a")
        distribute("form_106a", forms)
        if "s" in forms:
            flag("electronic_form", "hors_perimetre", "106$a=s : forme électronique", forms)
        media = [s["raw"] for f in type_fields["182"] for s in f["subfields"] if s["code"] == "c"]
        if "c" in media:
            flag("computer_media", "a_verifier", "182$c=c : médiation informatique, vérifier le support et les accompagnements", media)
        # Le SRU exporte la nature du contenu dans 105$a positions 4–7, pas 105$b.
        nature = set(c for value in raw("105", "a") for c in value[4:8] if c not in " |#")
        distribute("nature_105_positions_4_7", nature)
        notes = [f for f in fields if f["source_field"] == "328"]
        if "m" in nature:
            flag("original_thesis", "hors_perimetre", "105$a positions 4–7 : m, thèse originelle", notes or raw("105", "a"))
        elif notes or nature & {"v", "7"}:
            flag("academic_work", "a_verifier", "Travail universitaire, reproduction ou texte remanié : décision de périmètre nécessaire", notes or raw("105", "a"))

    n = len(seen)
    return {"records": n, "year_requested": year,
            "coverage": {k: {"records": v, "percent": round(100 * v / n, 2) if n else 0}
                         for k, v in sorted(coverage.items())},
            "distributions": {k: dict(sorted(v.items(), key=lambda pair: (-pair[1], pair[0]))) for k, v in sorted(distributions.items())},
            "summary_lengths": {"occurrences": len(lengths), "min": min(lengths, default=None),
                                "median": statistics.median(lengths) if lengths else None, "max": max(lengths, default=None)},
            "anomaly_counts": dict(Counter(a["rule"] for a in anomalies)),
            "records_by_category": {cat: len({a["ppn"] for a in anomalies if a["category"] == cat})
                                    for cat in sorted({a["category"] for a in anomalies})}}, anomalies


def audit_extraction(input_dir, output_dir, year):
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    if output_dir.is_relative_to(input_dir) or input_dir.is_relative_to(output_dir):
        raise ValueError("La sortie doit être distincte de l'extraction")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Le dossier de sortie doit être vide")
    payload = (input_dir / "documents.jsonl").read_bytes()
    report_bytes = (input_dir / "report.json").read_bytes()
    extraction = json.loads(report_bytes)
    if extraction["status"] != "complete":
        raise ValueError("Extraction incomplète")
    documents = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if len(documents) != extraction["counts"]["documents"]:
        raise ValueError("Nombre de documents différent du rapport d'extraction")
    stats, anomalies = audit_documents(documents, year)
    stats.update(audit_version=AUDIT_VERSION, created_at=now(), source=str(input_dir),
                 documents_sha256=hashlib.sha256(payload).hexdigest(),
                 extraction_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
                 parser_version=extraction["parser_version"],
                 sampling_warning="Lot limité, non aléatoire, paginé par préfixe PPN : non représentatif de l'année entière.")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "statistics.json", stats)
    with (output_dir / "anomalies.jsonl").open("w", encoding="utf-8") as stream:
        for row in anomalies:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output_dir / "anomalies.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["ppn", "title", "category", "rule", "message", "evidence", "source"], delimiter=";")
        writer.writeheader()
        for row in anomalies:
            writer.writerow({**row, "evidence": json.dumps(row["evidence"], ensure_ascii=False), "source": json.dumps(row["source"], ensure_ascii=False)})
    with (output_dir / "distributions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["distribution", "valeur", "nombre"])
        for name, values in stats["distributions"].items():
            writer.writerows((name, key, value) for key, value in values.items())
    lines = ["# Contrôle des données extraites", "", f"Notices analysées : **{stats['records']}**. Année cible : **{year}**.", "",
             stats["sampling_warning"], "", "Aucune notice modifiée ou exclue par cet audit. Les catégories se recouvrent.", "",
             "## Couverture", "", "| Indicateur | Notices | % du lot |", "|---|---:|---:|"]
    for key, value in stats["coverage"].items():
        lines.append(f"| {key} | {value['records']} | {value['percent']} |")
    for name in ["countries", "languages", "publication_year", "date_type", "dewey_1", "subject_tags", "summaries_per_record", "leader_type_level",
                 "leader_record_type", "leader_bibliographic_level", "content_types_occurrences_per_record",
                 "media_types_occurrences_per_record", "181_a_by_vocabulary", "181_b_by_vocabulary",
                 "181_c_by_vocabulary", "182_a_by_vocabulary", "182_b_by_vocabulary", "182_c_by_vocabulary",
                 "nature_105_position_4", "nature_105_positions_4_7"]:
        lines += ["", f"## Distribution : {name}", "", "| Valeur | Notices |", "|---|---:|"]
        lines += [f"| {str(key).replace('|', '&#124;') if str(key).strip() else '(espace)'} | {value} |" for key, value in stats["distributions"].get(name, {}).items()]
    lines += ["", "## Anomalies et points à examiner", "", "Les lacunes ne sont pas des erreurs de catalogage. Chaque règle ci-dessous liste tous les PPN concernés.",
              "Les preuves complètes, titres et fichiers XML sources figurent dans anomalies.csv et anomalies.jsonl."]
    for rule, count in stats["anomaly_counts"].items():
        rows = [a for a in anomalies if a["rule"] == rule]
        lines += ["", f"### {rule} — {count} notices ({rows[0]['category']})", "", rows[0]["message"], "", ", ".join(a["ppn"] for a in rows)]
    lines += ["", "## Méthode et limites", "", "Voir docs/quality-audit.md. Comptages par notice et valeur distincte, sauf distributions explicitement nommées occurrences. Pays/langues : contrôle syntaxique seulement, pas de validation exhaustive des codes. Absence de signal de périmètre ne vaut pas conformité certifiée."]
    (output_dir / "rapport.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stats
