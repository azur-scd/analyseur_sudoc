"""Schéma partagé et migration des classifications de notices et d'autorités."""

import json

from analyseur_sudoc.unimarc import clean, dewey


CLASSIFICATION_SCHEMA = """(
    corpus_id VARCHAR NOT NULL,
    ppn VARCHAR NOT NULL,
    occurrence INTEGER NOT NULL,
    dewey_raw VARCHAR,
    dewey_normalized VARCHAR,
    dewey_1 VARCHAR,
    dewey_2 VARCHAR,
    dewey_3 VARCHAR,
    source VARCHAR NOT NULL,
    annotation VARCHAR,
    payload JSON,
    run_id VARCHAR NOT NULL DEFAULT '',
    scheme VARCHAR,
    requested_authority_ppn VARCHAR,
    resolved_authority_ppn VARCHAR,
    PRIMARY KEY(corpus_id, ppn, source, run_id, occurrence)
)"""

REQUIRED_COLUMNS = {
    "run_id", "scheme",
    "requested_authority_ppn", "resolved_authority_ppn",
}


def _columns(con, table):
    return {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}


def ensure_classification_schema(con):
    """Create or upgrade CLASSIFICATION, merging any legacy authority table."""
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "CLASSIFICATION" not in tables:
        con.execute(f"CREATE TABLE CLASSIFICATION {CLASSIFICATION_SCHEMA}")
        if "AUTHORITY_CLASSIFICATION" in tables:
            _merge_legacy_authorities(con)
        return
    columns = _columns(con, "CLASSIFICATION")
    if REQUIRED_COLUMNS.issubset(columns) and not {"code_raw", "code"}.intersection(columns):
        if "AUTHORITY_CLASSIFICATION" in tables:
            _merge_legacy_authorities(con)
        return

    old_columns = _columns(con, "CLASSIFICATION")
    if not {"corpus_id", "ppn", "occurrence", "source", "payload"}.issubset(old_columns):
        raise ValueError("Schéma CLASSIFICATION inconnu ; migration refusée")
    old_rows = con.execute("SELECT * FROM CLASSIFICATION").fetchall()
    old_names = [item[0] for item in con.description]
    profile_existed = "LIBRARY_PROFILE" in tables
    con.execute("DROP VIEW IF EXISTS LIBRARY_PROFILE")
    con.execute("DROP TABLE IF EXISTS CLASSIFICATION_MERGED")
    con.execute(f"CREATE TABLE CLASSIFICATION_MERGED {CLASSIFICATION_SCHEMA}")
    rows = [_migrate_row(dict(zip(old_names, row))) for row in old_rows]
    _insert_rows(con, "CLASSIFICATION_MERGED", rows)
    con.execute("DROP TABLE CLASSIFICATION")
    con.execute("ALTER TABLE CLASSIFICATION_MERGED RENAME TO CLASSIFICATION")
    if "AUTHORITY_CLASSIFICATION" in tables:
        _merge_legacy_authorities(con)
    if profile_existed and {"HOLDING", "LIBRARY"}.issubset(tables):
        _create_library_profile(con)


def _merge_legacy_authorities(con):
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "AUTHORITY_CLASSIFICATION" not in tables:
        return
    if "AUTHORITY_RUN" not in tables:
        raise ValueError("AUTHORITY_CLASSIFICATION existe sans AUTHORITY_RUN")
    raw_rows = con.execute("""SELECT r.corpus_id,a.ppn,a.occurrence,a.source,a.payload,
            a.run_id,a.scheme,a.code_raw,a.code,a.requested_authority_ppn,a.resolved_authority_ppn
        FROM AUTHORITY_CLASSIFICATION a JOIN AUTHORITY_RUN r USING(run_id)""").fetchall()
    names = [item[0] for item in con.description]
    existing = {(r[0], r[1], r[2], r[3], r[4]) for r in con.execute(
        "SELECT corpus_id,ppn,occurrence,source,run_id FROM CLASSIFICATION").fetchall()}
    rows = []
    for values in raw_rows:
        row = dict(zip(names, values))
        key = (row["corpus_id"], row["ppn"], row["occurrence"], row["source"], row["run_id"])
        if key not in existing:
            rows.append(_migrate_row(row))
    _insert_rows(con, "CLASSIFICATION", rows)
    con.execute("DROP TABLE AUTHORITY_CLASSIFICATION")


def _migrate_row(row):
    scheme = row.get("scheme") or "dewey"
    dewey_raw = row.get("dewey_raw") or row.get("code_raw")
    if scheme == "rameau_domain":
        dewey_raw = row.get("code_raw") or dewey_raw
        normalized = dewey({"raw": dewey_raw or "", "value": clean(dewey_raw or "")})
        dewey_normalized = normalized["dewey_normalized"]
        parts = [normalized["dewey_1"], normalized["dewey_2"], normalized["dewey_3"]]
    else:
        dewey_normalized = row.get("dewey_normalized") or row.get("code")
        parts = [row.get(f"dewey_{n}") for n in (1, 2, 3)]
        if dewey_normalized:
            parts = [dewey_normalized[:1], dewey_normalized[:2], dewey_normalized[:3]]
    return (row["corpus_id"], row["ppn"], row["occurrence"], dewey_raw,
            dewey_normalized, *parts, row.get("source") or "sudoc:676$a",
            row.get("annotation"), row.get("payload"), row.get("run_id") or "",
            scheme, row.get("requested_authority_ppn"), row.get("resolved_authority_ppn"))


def _insert_rows(con, table, rows):
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})", rows)


def _create_library_profile(con):
    con.execute("""CREATE OR REPLACE VIEW LIBRARY_PROFILE AS
        SELECT h.corpus_id,h.rcr,l.label,l.iln,l.library_type,count(DISTINCT h.ppn) AS documents,
        count(DISTINCT CASE WHEN c.dewey_normalized IS NOT NULL THEN h.ppn END) AS documents_with_dewey
        FROM HOLDING h JOIN LIBRARY l USING(rcr)
        LEFT JOIN CLASSIFICATION c ON c.corpus_id=h.corpus_id AND c.ppn=h.ppn
        GROUP BY h.corpus_id,h.rcr,l.label,l.iln,l.library_type""")
