"""Chargement transactionnel du référentiel dans DuckDB."""

from pathlib import Path

import duckdb

FIELDS = ("rcr", "label", "iln", "library_ppn", "library_type", "city",
          "postal_code", "country", "latitude", "longitude", "metadata_retrieved_at")


def save_libraries(rows, database: Path):
    if not rows:
        raise ValueError("Refus de remplacer LIBRARY par un référentiel vide")
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS LIBRARY (
                    rcr VARCHAR PRIMARY KEY, label VARCHAR, iln VARCHAR,
                    library_ppn VARCHAR, library_type VARCHAR, city VARCHAR,
                    postal_code VARCHAR, country VARCHAR, latitude DOUBLE,
                    longitude DOUBLE, metadata_retrieved_at TIMESTAMPTZ
                )
            """)
            connection.execute("DELETE FROM LIBRARY")
            connection.executemany(
                f"INSERT INTO LIBRARY ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
                [[row[field] for field in FIELDS] for row in rows],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
