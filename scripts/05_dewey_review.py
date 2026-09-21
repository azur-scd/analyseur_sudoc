"""Compare deux extractions et prépare l'enrichissement BnF, sans réseau."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_documents(path):
    payload = (path / "documents.jsonl").read_bytes()
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    documents = {d["ppn"]: d for d in rows}
    if len(documents) != len(rows):
        raise ValueError("PPN répété")
    return documents, hashlib.sha256(payload).hexdigest()


def review(before, after, output):
    old, old_hash = read_documents(before)
    new, new_hash = read_documents(after)
    if old.keys() != new.keys():
        raise ValueError("Les deux extractions doivent contenir les mêmes PPN")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Le dossier de sortie doit être vide")
    output.mkdir(parents=True, exist_ok=True)
    usable = lambda d: any(v["dewey_normalized"] for v in d["classifications"])
    gained = [p for p in new if usable(new[p]) and not usable(old[p])]
    missing = [d for d in new.values() if not usable(d)]
    candidates = [d for d in missing if d["bnf_links"]]
    stats = dict(records=len(new), before_usable=sum(usable(d) for d in old.values()),
                 after_usable=sum(usable(d) for d in new.values()), gained_records=len(gained),
                 missing_usable=len(missing), bnf_candidate_records=len(candidates),
                 bnf_unique_urls=len({link["url"] for d in candidates for link in d["bnf_links"]}),
                 without_bnf_link=sum(not d["bnf_links"] for d in missing),
                 before_documents_sha256=old_hash, after_documents_sha256=new_hash)
    (output / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["ppn", "titre", "dewey_brutes", "dewey_normalisees", "regles", "annotations", "urls_bnf", "origines_bnf", "statut", "source_xml"]
    def export(name, docs):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
            writer.writeheader()
            for d in docs:
                writer.writerow(dict(ppn=d["ppn"], titre=d["title"],
                    dewey_brutes=" | ".join(v["raw"] for v in d["classifications"]),
                    dewey_normalisees=" | ".join(v["dewey_normalized"] or "" for v in d["classifications"]),
                    regles=json.dumps([v["dewey_normalization_rules"] for v in d["classifications"]]),
                    annotations=" | ".join(v["dewey_annotation"] or "" for v in d["classifications"]),
                    urls_bnf=" | ".join(sorted({v["url"] for v in d["bnf_links"]})),
                    origines_bnf=" | ".join(sorted({v["origin"] for v in d["bnf_links"]})),
                    statut="normalisee" if usable(d) else "bnf_a_consulter" if d["bnf_links"] else "sans_lien_bnf",
                    source_xml=d["source"]["page_file"]))
    export("notices_gagnees.csv", [new[p] for p in gained])
    export("candidats_bnf.csv", candidates)
    export("sans_dewey_exploitable.csv", missing)
    export("notations_a_examiner.csv", [d for d in new.values() if any(not v["dewey_normalized"] for v in d["classifications"])])
    lines = ["# Bilan Dewey et préparation BnF", "", f"Corpus conservé : {len(new)} notices.",
             f"Dewey exploitable : {stats['before_usable']} → {stats['after_usable']} notices (+{len(gained)}).",
             f"Couverture : {100 * stats['after_usable'] / len(new):.2f} %." if new else "Corpus vide.",
             f"Sans Dewey exploitable : {len(missing)}, dont {len(candidates)} avec lien BnF ({stats['bnf_unique_urls']} URL distinctes).", "",
             "Les liens BnF sont des candidats : ni leur résolution ni la présence d'une Dewey n'ont été vérifiées. Aucun téléchargement effectué.",
             "Le gain BnF effectif reste inconnu. Une recherche par ISBN pour les notices sans lien relève d'une étape ultérieure.",
             "Les codes avec préfixes/suffixes ambigus restent à examiner. Les sources et annotations sont conservées.",
             "Toutes les notices du corpus, y compris les cas de périmètre litigieux validés par l'utilisateur, sont conservées."]
    (output / "rapport.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.before, args.after, args.output_dir), indent=2))
