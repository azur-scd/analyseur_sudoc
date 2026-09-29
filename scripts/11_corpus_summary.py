"""Produit un rapport humain de couverture Dewey/ Rameau pour le corpus chargé."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import duckdb

from analyseur_sudoc.enrichment import digest, read_jsonl


def build_report(database, corpus_id, bnf_dir, rameau_dir, output_dir):
    database, bnf_dir, rameau_dir, output_dir = map(
        lambda p: Path(p).resolve(), (database, bnf_dir, rameau_dir, output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    bnf_report = json.loads((bnf_dir / "report.json").read_text(encoding="utf-8"))
    bnf_bytes = (bnf_dir / "documents.jsonl").read_bytes()
    if digest(bnf_bytes) != bnf_report["documents_sha256"]:
        raise ValueError("Empreinte des documents BnF incorrecte")
    bnf_docs = read_jsonl(bnf_dir / "documents.jsonl")

    rameau_report = json.loads((rameau_dir / "report.json").read_text(encoding="utf-8"))
    rameau_bytes = (rameau_dir / "documents.jsonl").read_bytes()
    if digest(rameau_bytes) != rameau_report["documents_sha256"]:
        raise ValueError("Empreinte des documents IdRef/Rameau incorrecte")
    rameau_docs = read_jsonl(rameau_dir / "documents.jsonl")
    bnf_by_ppn = {d["ppn"]: d for d in bnf_docs}
    rameau_by_ppn = {d["ppn"]: d for d in rameau_docs}
    if len(bnf_by_ppn) != len(bnf_docs) or len(rameau_by_ppn) != len(rameau_docs):
        raise ValueError("PPN en double dans les exports")
    if bnf_by_ppn.keys() != rameau_by_ppn.keys():
        raise ValueError("Les exports BnF et IdRef ne portent pas sur les mêmes PPN")

    with duckdb.connect(str(database), read_only=True) as con:
        known = con.execute("SELECT 1 FROM CORPUS WHERE corpus_id=?", [corpus_id]).fetchone()
        if not known:
            raise ValueError(f"Corpus absent de DuckDB : {corpus_id}")
        rows = con.execute("""
            SELECT d.ppn, d.title, c.source, c.scheme, c.dewey_normalized
            FROM DOCUMENT d LEFT JOIN CLASSIFICATION c
              ON c.corpus_id=d.corpus_id AND c.ppn=d.ppn
            WHERE d.corpus_id=? ORDER BY d.ppn
        """, [corpus_id]).fetchall()

    documents = {}
    for ppn, title, source, scheme, code in rows:
        entry = documents.setdefault(ppn, {"title": title, "sudoc": set(), "bnf": set(),
            "idref_dewey": set(), "rameau": set()})
        if not code:
            continue
        if source == "sudoc:676$a":
            entry["sudoc"].add(code)
        elif source == "bnf:676$a":
            entry["bnf"].add(code)
        elif scheme == "rameau_domain":
            entry["rameau"].add(code)
        elif scheme == "dewey" and source.startswith("idref:"):
            entry["idref_dewey"].add(code)

    if set(documents) != set(bnf_by_ppn):
        raise ValueError("Le corpus DuckDB et les exports n'ont pas les mêmes PPN")
    for ppn, doc in rameau_by_ppn.items():
        target = documents[ppn]
        for item in doc.get("idref_606a_classifications", []):
            if item.get("scheme") == "rameau_domain" and item.get("code"):
                target["rameau"].add(str(item["code"]))
            elif item.get("scheme") == "dewey" and item.get("code"):
                target["idref_dewey"].add(str(item["code"]))

    n = len(documents)
    categories = ("sudoc", "bnf", "rameau", "idref_dewey")
    coverage = {key: sum(bool(d[key]) for d in documents.values()) for key in categories}
    all_covered = sum(any(d[k] for k in categories) for d in documents.values())
    combined_dewey = sum(bool(d["sudoc"] or d["bnf"] or d["idref_dewey"])
                         for d in documents.values())
    distribution = Counter(tuple(len(d[k]) for k in categories) for d in documents.values())
    total_codes = {key: sum(len(d[key]) for d in documents.values()) for key in categories}

    lines = ["# Synthèse des classifications du corpus", "",
        f"- Corpus DuckDB : `{corpus_id}`",
        f"- Notices : **{n:,}**".replace(",", " "),
        f"- Données BnF : `{bnf_dir}` (run {bnf_report.get('version', bnf_report.get('policy', '?'))})",
        f"- Données IdRef/Rameau : `{rameau_dir}` (run {rameau_report.get('version', '?')})", "",
        "Les couvertures comptent les notices ayant au moins un code normalisé distinct. "
        "Les codes et occurrences sont dédoublonnés par notice et source. Les domaines Rameau "
        "sont affichés séparément : ce sont des indices de regroupement Rameau et non des Dewey bibliographiques. "
        "Le score global inclut les Dewey de toutes les sources et les domaines Rameau.", "",
        "## Couverture et volume par source", "",
        "| Source | Notices avec au moins un code | Couverture du corpus | Codes distincts cumulés par notice |",
        "|---|---:|---:|---:|"]
    labels = {"sudoc": "Dewey Sudoc", "bnf": "Dewey BnF",
              "idref_dewey": "Dewey des autorités IdRef", "rameau": "Domaines Rameau"}
    for key in categories:
        lines.append(f"| {labels[key]} | {coverage[key]:,} | {coverage[key]/n*100:.2f} % | {total_codes[key]:,} |".replace(",", " "))
    lines += [f"| **Au moins une classification (toutes sources)** | **{all_covered:,}** | **{all_covered/n*100:.2f} %** | — |".replace(",", " "),
        f"| **Au moins une Dewey (Sudoc, BnF ou autorités IdRef)** | **{combined_dewey:,}** | **{combined_dewey/n*100:.2f} %** | — |".replace(",", " "),
              "", "## Nombre de codes par notice", "",
              "Chaque cellule croise le nombre de Dewey distinctes Sudoc, BnF, "
              "IdRef, et de domaines Rameau présents sur une notice. Les zéros sont inclus. "
              "Les codes Rameau du CSV conservent les zéros initiaux (ex. `000`).", "",
              "| Dewey Sudoc | Dewey BnF | Dewey IdRef | Domaines Rameau | Notices |",
              "|---:|---:|---:|---:|---:|"]
    for counts, number in sorted(distribution.items()):
        lines.append("| " + " | ".join(map(str, (*counts, number))) + " |")
    lines += ["", "## Détail par notice", "",
              "Le CSV associé donne pour chaque PPN les codes distincts de chaque source.", ""]
    (output_dir / "rapport.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output_dir / "dewey-par-notice.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["ppn", "titre", "nombre_dewey_sudoc", "dewey_sudoc",
            "nombre_dewey_bnf", "dewey_bnf", "nombre_dewey_idref", "dewey_idref",
            "nombre_domaines_rameau", "domaines_rameau"])
        for ppn, d in sorted(documents.items()):
            writer.writerow([ppn, d["title"], len(d["sudoc"]), " | ".join(sorted(d["sudoc"])),
                len(d["bnf"]), " | ".join(sorted(d["bnf"])), len(d["idref_dewey"]),
                " | ".join(sorted(d["idref_dewey"])), len(d["rameau"]),
                " | ".join(sorted(d["rameau"]))])
    (output_dir / "statistics.json").write_text(json.dumps({
        "corpus_id": corpus_id, "records": n, "coverage_records": coverage,
        "all_classifications_records": all_covered,
        "any_bibliographic_dewey_records": combined_dewey,
        "distinct_codes_per_record_totals": total_codes,
        "distribution": [{"sudoc": a, "bnf": b, "idref_dewey": c,
            "rameau": d, "records": count} for (a,b,c,d), count in sorted(distribution.items())],
        "sources": {"bnf_report": str(bnf_dir / "report.json"),
            "rameau_report": str(rameau_dir / "report.json")}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"records": n, "all_classifications_records": all_covered,
            "coverage_records": coverage, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--bnf-dir", type=Path, required=True)
    parser.add_argument("--rameau-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_report(args.database, args.corpus_id, args.bnf_dir,
        args.rameau_dir, args.output_dir), ensure_ascii=False, indent=2))
