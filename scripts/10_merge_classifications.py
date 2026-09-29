"""Migre les classifications d'autorité dans la table CLASSIFICATION."""

import argparse
import json

import duckdb

from analyseur_sudoc.classification_database import ensure_classification_schema


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    with duckdb.connect(args.database) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            before = (con.execute("SELECT count(*) FROM AUTHORITY_CLASSIFICATION").fetchone()[0]
                      if "AUTHORITY_CLASSIFICATION" in tables else 0)
            ensure_classification_schema(con)
            after = con.execute("SELECT count(*) FROM CLASSIFICATION WHERE run_id <> ''").fetchone()[0]
            remaining = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            if after < before or "AUTHORITY_CLASSIFICATION" in remaining:
                raise ValueError("La fusion des classifications n'a pas été vérifiée")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(json.dumps({"status": "merged", "authority_rows_before": before,
                      "authority_rows_in_classification": after,
                      "legacy_table_removed": True}, indent=2))
