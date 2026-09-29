"""Migre les classifications d'autorité dans la table CLASSIFICATION."""

import argparse
import csv
import json
from pathlib import Path

import duckdb

from analyseur_sudoc.classification_database import ensure_classification_schema


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    reference_path = Path(__file__).resolve().parents[1] / "resources" / "rameau_domains_2026.csv"
    with reference_path.open(encoding="utf-8-sig", newline="") as stream:
        reference_codes = {row["code"] for row in csv.DictReader(stream)}
    with duckdb.connect(args.database) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            before = (con.execute("SELECT count(*) FROM AUTHORITY_CLASSIFICATION").fetchone()[0]
                      if "AUTHORITY_CLASSIFICATION" in tables else 0)
            ensure_classification_schema(con)
            after = con.execute("SELECT count(*) FROM CLASSIFICATION WHERE run_id <> ''").fetchone()[0]
            rameau = con.execute("""SELECT count(*),count(dewey_normalized),
                    count(*) FILTER (WHERE dewey_normalized IS NOT NULL AND dewey_1 IS NOT NULL
                                     AND dewey_2 IS NOT NULL AND dewey_3 IS NOT NULL)
                FROM CLASSIFICATION WHERE scheme='rameau_domain'""").fetchone()
            rameau_codes = {row[0] for row in con.execute(
                "SELECT DISTINCT dewey_raw FROM CLASSIFICATION WHERE scheme='rameau_domain'").fetchall()}
            remaining = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            if after < before or "AUTHORITY_CLASSIFICATION" in remaining:
                raise ValueError("La fusion des classifications n'a pas été vérifiée")
            columns = {row[1] for row in con.execute("DESCRIBE CLASSIFICATION").fetchall()}
            if {"code_raw", "code"}.intersection(columns) or rameau[0] != rameau[1] or rameau[0] != rameau[2]:
                raise ValueError("Colonnes redondantes présentes ou domaine Rameau non normalisé")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(json.dumps({"status": "merged", "authority_rows_before": before,
                      "authority_rows_in_classification": after,
                      "rameau_classifications": rameau[0],
                      "rameau_normalized": rameau[1],
                      "rameau_all_dewey_fields_populated": rameau[2],
                      "official_domain_codes": len(reference_codes),
                      "rameau_codes_absent_du_referentiel": sorted(rameau_codes - reference_codes),
                      "legacy_table_removed": True}, indent=2))
