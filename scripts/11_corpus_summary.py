"""Produit un rapport humain de couverture Dewey/ Rameau pour le corpus chargé."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import duckdb

from analyseur_sudoc.enrichment import digest, read_jsonl


def compare_unique_codes(documents):
    """Compare une Dewey bibliographique unique à un domaine Rameau unique par notice."""
    selected = []
    excluded = Counter()
    for ppn, doc in documents.items():
        bibliographic = doc["sudoc"] | doc["bnf"]
        rameau = doc["rameau"]
        if len(bibliographic) != 1 or len(rameau) != 1:
            if len(bibliographic) > 1 and len(rameau) > 1:
                excluded["plusieurs_dewey_et_plusieurs_domaines_rameau"] += 1
            elif len(bibliographic) > 1:
                excluded["plusieurs_dewey_sudoc_bnf"] += 1
            elif len(rameau) > 1:
                excluded["plusieurs_domaines_rameau"] += 1
            elif not bibliographic:
                excluded["sans_dewey_sudoc_bnf"] += 1
            else:
                excluded["sans_domaine_rameau"] += 1
            continue
        selected.append((ppn, next(iter(bibliographic)), next(iter(rameau))))

    levels = (("Indice détaillé (3 chiffres)", 3), ("Classe (2 chiffres)", 2),
              ("Domaine (1 chiffre)", 1))
    results = []
    detail_rows = []
    for ppn, dewey_code, rameau_code in selected:
        row = {"ppn": ppn, "dewey": dewey_code, "rameau": rameau_code}
        for label, width in levels:
            dewey_prefix = dewey_code[:width]
            rameau_prefix = rameau_code[:width]
            row[f"dewey_{width}"] = dewey_prefix
            row[f"rameau_{width}"] = rameau_prefix
            row[f"match_{width}"] = dewey_prefix == rameau_prefix
        detail_rows.append(row)
    for label, width in levels:
        matching = sum(row[f"match_{width}"] for row in detail_rows)
        different = len(detail_rows) - matching
        results.append({"level": label, "width": width, "compared": len(detail_rows),
                        "match": matching, "different": different,
                        "match_percent": round(100 * matching / len(detail_rows), 2)
                        if detail_rows else 0})
    return {"selected_records": len(selected), "excluded_records": dict(excluded),
            "levels": results, "details": detail_rows}


def compare_multiple_codes(documents):
    """Compare les ensembles de codes des notices ayant plusieurs indices détaillés."""
    groups = (
        ("une Dewey / plusieurs Rameau", lambda b, r: len(b) == 1 and len(r) > 1),
        ("plusieurs Dewey / un Rameau", lambda b, r: len(b) > 1 and len(r) == 1),
        ("plusieurs des deux côtés", lambda b, r: len(b) > 1 and len(r) > 1),
    )
    details = []
    for ppn, doc in sorted(documents.items()):
        bibliographic = doc["sudoc"] | doc["bnf"]
        rameau = doc["rameau"]
        group = next((name for name, accepts in groups if accepts(bibliographic, rameau)), None)
        if group is None:
            continue
        for width in (3, 2, 1):
            dewey_codes = {code[:width] for code in bibliographic}
            rameau_codes = {code[:width] for code in rameau}
            common = dewey_codes & rameau_codes
            result = "complet" if dewey_codes == rameau_codes else "partiel" if common else "aucun"
            details.append(dict(ppn=ppn, title=doc["title"], group=group, level=width,
                original_dewey_count=len(bibliographic), original_rameau_count=len(rameau),
                dewey=sorted(dewey_codes), rameau=sorted(rameau_codes), common=sorted(common),
                dewey_only=sorted(dewey_codes - rameau_codes),
                rameau_only=sorted(rameau_codes - dewey_codes), result=result))
    counts = Counter((row["group"], row["level"], row["result"]) for row in details)
    summaries = []
    for group, _ in groups:
        for width in (3, 2, 1):
            total = sum(counts[group, width, result] for result in ("complet", "partiel", "aucun"))
            summaries.append(dict(group=group, level=width, records=total,
                complete=counts[group, width, "complet"], partial=counts[group, width, "partiel"],
                none=counts[group, width, "aucun"]))
    for width in (3, 2, 1):
        rows = [row for row in summaries if row["level"] == width]
        summaries.append(dict(group="Total", level=width,
            records=sum(row["records"] for row in rows),
            complete=sum(row["complete"] for row in rows),
            partial=sum(row["partial"] for row in rows),
            none=sum(row["none"] for row in rows)))
    return {"records": len(details) // 3, "groups": summaries, "details": details}


def coverage_summary(documents, categories):
    """Calcule les mêmes indicateurs de couverture pour tout sous-ensemble de notices."""
    n = len(documents)
    coverage = {key: sum(bool(d[key]) for d in documents.values()) for key in categories}
    total_codes = {key: sum(len(d[key]) for d in documents.values()) for key in categories}
    return {"records": n, "coverage_records": coverage, "distinct_codes_per_record_totals": total_codes,
        "all_classifications_records": sum(any(d[key] for key in categories) for d in documents.values()),
        "any_dewey_records": sum(bool(d["sudoc"] or d["bnf"] or d["idref_dewey"])
                                 for d in documents.values())}


def coverage_table(summary, categories, labels, coverage_label="Couverture du corpus"):
    """Rend le tableau de couverture avec le dénominateur du sous-ensemble."""
    n = summary["records"]
    percent = lambda count: f"{100 * count / n:.2f}" if n else "0.00"
    format_count = lambda count: f"{count:,}".replace(",", " ")
    lines = [f"| Source | Notices avec au moins un code | {coverage_label} | Codes distincts cumulés par notice |",
             "|---|---:|---:|---:|"]
    for key in categories:
        count = summary["coverage_records"][key]
        codes = summary["distinct_codes_per_record_totals"][key]
        lines.append(f"| {labels[key]} | {format_count(count)} | {percent(count)} % | {format_count(codes)} |")
    all_count = summary["all_classifications_records"]
    dewey_count = summary["any_dewey_records"]
    lines += [f"| **Au moins une classification (toutes sources)** | **{format_count(all_count)}** | **{percent(all_count)} %** | — |",
        f"| **Au moins une Dewey (Sudoc, BnF ou autorités IdRef)** | **{format_count(dewey_count)}** | **{percent(dewey_count)} %** | — |"]
    return lines


def fisher_two_sided(a, b, c, d):
    """Probabilité exacte bilatérale pour une table 2 × 2, marges fixées."""
    first, second, successes = a + b, c + d, a + c
    total = first + second
    if total == 0:
        return 1.0

    def log_choose(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    denominator = log_choose(total, first)
    def log_probability(x):
        return log_choose(successes, x) + log_choose(total - successes, first - x) - denominator

    observed = log_probability(a)
    minimum = max(0, first - (total - successes))
    maximum = min(first, successes)
    return min(1.0, sum(math.exp(log_probability(x)) for x in range(minimum, maximum + 1)
                        if log_probability(x) <= observed + 1e-10))


def country_association(documents, french_ppns):
    """Mesure l'association entre FR en 102$a et la présence d'indices par notice."""
    outcomes = (
        ("Dewey Sudoc ou BnF", lambda d: bool(d["sudoc"] or d["bnf"])),
        ("Via autorités : Dewey IdRef ou domaine Rameau",
         lambda d: bool(d["idref_dewey"] or d["rameau"])),
        ("Au moins un indice des deux voies",
         lambda d: bool(d["sudoc"] or d["bnf"] or d["idref_dewey"] or d["rameau"])),
    )
    france_total = len(french_ppns)
    elsewhere_total = len(documents) - france_total
    if france_total == 0 or elsewhere_total == 0:
        raise ValueError("Les deux groupes pays doivent contenir des notices")
    results = []
    for name, has_index in outcomes:
        france_yes = sum(has_index(doc) for ppn, doc in documents.items() if ppn in french_ppns)
        elsewhere_yes = sum(has_index(doc) for ppn, doc in documents.items() if ppn not in french_ppns)
        france_rate = france_yes / france_total
        elsewhere_rate = elsewhere_yes / elsewhere_total
        results.append(dict(outcome=name, france_yes=france_yes, france_total=france_total,
            elsewhere_yes=elsewhere_yes, elsewhere_total=elsewhere_total,
            france_percent=round(100 * france_rate, 2),
            elsewhere_percent=round(100 * elsewhere_rate, 2),
            difference_points=round(100 * (france_rate - elsewhere_rate), 2),
            relative_ratio=round(france_rate / elsewhere_rate, 3) if elsewhere_rate else None,
            fisher_p=fisher_two_sided(france_yes, france_total - france_yes,
                                      elsewhere_yes, elsewhere_total - elsewhere_yes)))
    return results


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
    categories = ("sudoc", "bnf", "idref_dewey", "rameau")
    summary = coverage_summary(documents, categories)
    french_ppns = {ppn for ppn, doc in bnf_by_ppn.items() if any(
        country.get("source_field") == "102" and country.get("value") == "FR"
        for country in doc.get("countries", []))}
    missing_country = sum(not any(country.get("source_field") == "102" and country.get("value")
                                  for country in doc.get("countries", []))
                          for doc in bnf_by_ppn.values())
    french = coverage_summary({ppn: doc for ppn, doc in documents.items() if ppn in french_ppns}, categories)
    elsewhere = coverage_summary({ppn: doc for ppn, doc in documents.items() if ppn not in french_ppns}, categories)
    if french["records"] + elsewhere["records"] != n:
        raise ValueError("Partition des notices par pays incohérente")
    associations = country_association(documents, french_ppns)
    coverage = summary["coverage_records"]
    all_covered = summary["all_classifications_records"]
    combined_dewey = summary["any_dewey_records"]
    distribution = Counter(tuple(len(d[k]) for k in categories) for d in documents.values())
    total_codes = summary["distinct_codes_per_record_totals"]
    comparison = compare_unique_codes(documents)
    multiple = compare_multiple_codes(documents)

    lines = ["# Synthèse des classifications du corpus", "",
        f"- Corpus DuckDB : `{corpus_id}`",
        f"- Notices : **{n:,}**".replace(",", " "),
        f"- Données BnF : `{bnf_dir}` (run {bnf_report.get('version', bnf_report.get('policy', '?'))})",
        f"- Données IdRef/Rameau : `{rameau_dir}` (run {rameau_report.get('version', '?')})", "",
        "Les couvertures comptent les notices ayant au moins un code normalisé distinct. "
        "Les codes et occurrences sont dédoublonnés par notice et source. Les domaines Rameau "
        "sont affichés séparément : ce sont des indices de regroupement Rameau et non des Dewey bibliographiques. "
        "Le score global inclut les Dewey de toutes les sources et les domaines Rameau.", "",
        "## Couverture et volume par source", ""]
    labels = {"sudoc": "Dewey Sudoc", "bnf": "Dewey BnF",
              "idref_dewey": "Dewey des autorités IdRef", "rameau": "Domaines Rameau"}
    lines += coverage_table(summary, categories, labels)
    lines += ["", f"### Documents édités en France : {french['records']} notices", "",
        "Au moins un code `FR` dans la zone `102$a` classe la notice dans ce groupe, "
        "même si d'autres codes pays sont présents. Les pourcentages portent sur ce seul groupe.", ""]
    lines += coverage_table(french, categories, labels, "Couverture du groupe")
    lines += ["", f"### Documents édités ailleurs ou sans code pays : {elsewhere['records']} notices", "",
        "Ce groupe comprend les notices sans code `FR` en `102$a`, y compris celles dont la zone "
        "est absente ou vide. Les pourcentages portent sur ce seul groupe.", ""]
    lines += coverage_table(elsewhere, categories, labels, "Couverture du groupe")
    lines += ["", "### Association entre pays `102$a` et présence d'un indice", "",
        "Chaque notice compte une fois par ligne. Le groupe France contient les notices avec au moins "
        f"un `FR` en `102$a` ; le second groupe contient toutes les autres, dont {missing_country} sans code pays. "
        "Un domaine Rameau est ici un indice indirect de regroupement, pas une Dewey bibliographique. "
        "La dernière ligne compte la présence d'au moins un indice de l'une ou l'autre voie.", "",
        "| Indice présent | France | Ailleurs ou code absent | Écart France − autres (points) | Rapport des proportions | p (Fisher bilatéral) |",
        "|---|---:|---:|---:|---:|---:|"]
    for row in associations:
        lines.append(f"| {row['outcome']} | {row['france_yes']}/{row['france_total']} "
            f"({row['france_percent']:.2f} %) | {row['elsewhere_yes']}/{row['elsewhere_total']} "
            f"({row['elsewhere_percent']:.2f} %) | {row['difference_points']:+.2f} | "
            f"{row['relative_ratio']:.3f} | {row['fisher_p']:.4g} |")
    direct, indirect, either = associations
    lines += ["", f"Dans ce lot, la présence d'une Dewey Sudoc/BnF est proche dans les deux groupes "
        f"({direct['france_percent']:.2f} % contre {direct['elsewhere_percent']:.2f} %). "
        f"La présence d'un indice via les autorités est plus faible dans le groupe France "
        f"({indirect['france_percent']:.2f} % contre {indirect['elsewhere_percent']:.2f} %). "
        f"Il en va de même pour la présence d'au moins un indice "
        f"({either['france_percent']:.2f} % contre {either['elsewhere_percent']:.2f} %).", "",
        "Le test exact de Fisher compare les proportions des deux groupes avec leurs "
        "effectifs observés. Un p faible signale une association dans ce lot ; il ne démontre pas que "
        "le pays cause la présence d'un indice. Les trois résultats se recouvrent et cette lecture "
        "est exploratoire. Le lot est limité et non aléatoire ; le type de document, la langue et "
        "d'autres différences entre groupes peuvent aussi expliquer les écarts.", ""]
    lines += ["", "## Nombre de codes par notice", "",
              "Chaque cellule croise le nombre de Dewey distinctes Sudoc, BnF, "
              "IdRef, et de domaines Rameau présents sur une notice. Les zéros sont inclus. "
              "Les codes Rameau du CSV conservent les zéros initiaux (ex. `000`).", "",
              "| Dewey Sudoc | Dewey BnF | Dewey IdRef | Domaines Rameau | Notices |",
              "|---:|---:|---:|---:|---:|"]
    for counts, number in sorted(distribution.items()):
        lines.append("| " + " | ".join(map(str, (*counts, number))) + " |")
    lines += ["", "## Comparaison Dewey bibliographique / domaines Rameau", "",
        "Cette première comparaison ne retient que les notices avec exactement un code Dewey distinct "
        "dans l'union Sudoc et BnF, et exactement un code Rameau distinct. Les répétitions identiques "
        "dans DuckDB sont dédoublonnées par notice avant la sélection. Une notice portant un code Sudoc "
        "et le même code BnF compte donc comme un seul code bibliographique. Les configurations avec "
        "plusieurs codes détaillés dans l'un des groupes sont écartées à ce stade, même si elles pourraient "
        "converger après réduction en classe ou domaine ; ces cas seront analysés séparément.", "",
        "| Niveau comparé | Notices comparées | Codes identiques | Codes différents | Identiques (%) |",
        "|---|---:|---:|---:|---:|"]
    for result in comparison["levels"]:
        lines.append(f"| {result['level']} | {result['compared']} | {result['match']} | "
                     f"{result['different']} | {result['match_percent']:.2f} % |")
    lines += ["", f"Notices retenues : **{comparison['selected_records']}** sur {n}.", "",
        "Les niveaux sont calculés en prenant les préfixes des codes : 3 chiffres, puis 2, puis 1. "
        "Chaque notice n'est comptée qu'une fois à chaque niveau. Les codes Rameau étant des domaines "
        "généralement à trois chiffres, la comparaison détaillée reste littérale ; les niveaux classe "
        "et domaine comparent respectivement les deux premiers et le premier chiffre.", "",
        "Configurations écartées :", "",
        "| Motif | Notices |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(comparison["excluded_records"].items())]
    lines += ["", "Le fichier `comparaison-dewey-rameau.csv` contient les codes et les résultats "
              "par notice aux trois niveaux.", ""]
    lines += ["", "## Notices avec plusieurs classifications", "",
        "Cette analyse porte sur les notices ayant plusieurs codes détaillés Sudoc/BnF et/ou "
        "plusieurs domaines Rameau, avec au moins un code de chaque côté. Les codes sont dédoublonnés "
        "par notice dans l'union Sudoc/BnF et dans Rameau. À chaque niveau, les préfixes de 3, 2 ou "
        "1 chiffre sont de nouveau dédoublonnés : `531` et `532` donnent ainsi une seule classe `53`. "
        "Une correspondance complète signifie que les deux ensembles sont égaux ; une correspondance "
        "partielle signifie qu'ils ont au moins un code commun sans être égaux ; aucune correspondance "
        "signifie que leur intersection est vide.", "",
        "| Configuration initiale | Niveau | Notices | Complet | Partiel | Aucun |",
        "|---|---:|---:|---:|---:|---:|"]
    for row in multiple["groups"]:
        level_label = f"{row['level']} chiffre" + ("s" if row["level"] > 1 else "")
        lines.append(f"| {row['group']} | {level_label} | {row['records']} | "
                     f"{row['complete']} ({100 * row['complete'] / row['records']:.1f} %) | "
                     f"{row['partial']} ({100 * row['partial'] / row['records']:.1f} %) | "
                     f"{row['none']} ({100 * row['none'] / row['records']:.1f} %) |"
                     if row["records"] else
                     f"| {row['group']} | {level_label} | 0 | 0 | 0 | 0 |")
    lines += ["", f"Notices analysées dans ces trois configurations : **{multiple['records']}**. "
              "Le CSV `comparaison-dewey-rameau-multiples.csv` donne les ensembles, leur intersection "
              "et les codes propres à chaque côté pour chaque notice et chaque niveau.", ""]
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
    with (output_dir / "comparaison-dewey-rameau.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["ppn", "dewey_sudoc_bnf", "domaine_rameau",
            "dewey_3_chiffres", "rameau_3_chiffres", "identique_3_chiffres",
            "dewey_classe_2", "rameau_classe_2", "identique_classe_2",
            "dewey_domaine_1", "rameau_domaine_1", "identique_domaine_1"])
        for row in comparison["details"]:
            writer.writerow([row["ppn"], row["dewey"], row["rameau"], row["dewey_3"],
                row["rameau_3"], row["match_3"], row["dewey_2"], row["rameau_2"],
                row["match_2"], row["dewey_1"], row["rameau_1"], row["match_1"]])
    with (output_dir / "comparaison-dewey-rameau-multiples.csv").open(
            "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["ppn", "titre", "configuration", "niveau_chiffres",
            "nombre_dewey_detailles", "nombre_rameau_detailles", "codes_dewey",
            "codes_rameau", "codes_communs", "dewey_seuls", "rameau_seuls", "resultat"])
        for row in multiple["details"]:
            writer.writerow([row["ppn"], row["title"], row["group"], row["level"],
                row["original_dewey_count"], row["original_rameau_count"],
                *[" | ".join(row[key]) for key in
                  ("dewey", "rameau", "common", "dewey_only", "rameau_only")], row["result"]])
    (output_dir / "statistics.json").write_text(json.dumps({
        "corpus_id": corpus_id, "records": n, "coverage_records": coverage,
        "all_classifications_records": all_covered,
        "any_bibliographic_dewey_records": combined_dewey,
        "coverage_by_publication_country": {"france": french, "elsewhere_or_missing": elsewhere},
        "records_without_publication_country": missing_country,
        "country_index_association": associations,
        "dewey_rameau_comparison": {key: value for key, value in comparison.items() if key != "details"},
        "dewey_rameau_multiple_comparison": {key: value for key, value in multiple.items() if key != "details"},
        "distinct_codes_per_record_totals": total_codes,
        "distribution": [{"sudoc": a, "bnf": b, "idref_dewey": c,
            "rameau": d, "records": count} for (a,b,c,d), count in sorted(distribution.items())],
        "sources": {"bnf_report": str(bnf_dir / "report.json"),
            "rameau_report": str(rameau_dir / "report.json")}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"records": n, "all_classifications_records": all_covered,
            "coverage_records": coverage, "comparison_records": comparison["selected_records"],
            "comparison_levels": comparison["levels"], "output_dir": str(output_dir)}


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
