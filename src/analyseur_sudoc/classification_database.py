"""Schéma partagé et migration des classifications de notices et d'autorités."""


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
    code_raw VARCHAR,
    code VARCHAR,
    requested_authority_ppn VARCHAR,
    resolved_authority_ppn VARCHAR,
    PRIMARY KEY(corpus_id, ppn, source, run_id, occurrence)
)"""

REQUIRED_COLUMNS = {
    "run_id", "scheme", "code_raw", "code",
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
    if REQUIRED_COLUMNS.issubset(_columns(con, "CLASSIFICATION")):
        if "AUTHORITY_CLASSIFICATION" in tables:
            _merge_legacy_authorities(con)
        return

    old_columns = _columns(con, "CLASSIFICATION")
    if not {"corpus_id", "ppn", "occurrence", "source", "payload"}.issubset(old_columns):
        raise ValueError("Schéma CLASSIFICATION inconnu ; migration refusée")
    profile_existed = "LIBRARY_PROFILE" in tables
    con.execute("DROP VIEW IF EXISTS LIBRARY_PROFILE")
    con.execute("DROP TABLE IF EXISTS CLASSIFICATION_MERGED")
    con.execute(f"CREATE TABLE CLASSIFICATION_MERGED {CLASSIFICATION_SCHEMA}")
    con.execute("""INSERT INTO CLASSIFICATION_MERGED
        (corpus_id,ppn,occurrence,dewey_raw,dewey_normalized,dewey_1,dewey_2,dewey_3,
         source,annotation,payload,run_id,scheme,code_raw,code,requested_authority_ppn,resolved_authority_ppn)
        SELECT corpus_id,ppn,occurrence,dewey_raw,dewey_normalized,dewey_1,dewey_2,dewey_3,
               coalesce(source,'sudoc:676$a'),annotation,payload,'','dewey',dewey_raw,dewey_normalized,NULL,NULL
        FROM CLASSIFICATION""")
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
    con.execute("""INSERT INTO CLASSIFICATION
        (corpus_id,ppn,occurrence,dewey_raw,dewey_normalized,dewey_1,dewey_2,dewey_3,
         source,annotation,payload,run_id,scheme,code_raw,code,requested_authority_ppn,resolved_authority_ppn)
        SELECT r.corpus_id,a.ppn,a.occurrence,
               CASE WHEN a.scheme='dewey' THEN a.code_raw END,
               CASE WHEN a.scheme='dewey' AND regexp_full_match(a.code,'[0-9]{3}(\\.[0-9]+)?') THEN a.code END,
               CASE WHEN a.scheme='dewey' AND regexp_full_match(a.code,'[0-9]{3}(\\.[0-9]+)?') THEN substr(a.code,1,1) END,
               CASE WHEN a.scheme='dewey' AND regexp_full_match(a.code,'[0-9]{3}(\\.[0-9]+)?') THEN substr(a.code,1,2) END,
               CASE WHEN a.scheme='dewey' AND regexp_full_match(a.code,'[0-9]{3}(\\.[0-9]+)?') THEN substr(a.code,1,3) END,
               a.source,NULL,a.payload,a.run_id,a.scheme,a.code_raw,a.code,
               a.requested_authority_ppn,a.resolved_authority_ppn
        FROM AUTHORITY_CLASSIFICATION a JOIN AUTHORITY_RUN r USING(run_id)
        WHERE NOT EXISTS (
          SELECT 1 FROM CLASSIFICATION c WHERE c.corpus_id=r.corpus_id AND c.ppn=a.ppn
            AND c.source=a.source AND c.run_id=a.run_id AND c.occurrence=a.occurrence
        )""")
    con.execute("DROP TABLE AUTHORITY_CLASSIFICATION")


def _create_library_profile(con):
    con.execute("""CREATE OR REPLACE VIEW LIBRARY_PROFILE AS
        SELECT h.corpus_id,h.rcr,l.label,l.iln,l.library_type,count(DISTINCT h.ppn) AS documents,
        count(DISTINCT CASE WHEN c.dewey_normalized IS NOT NULL THEN h.ppn END) AS documents_with_dewey
        FROM HOLDING h JOIN LIBRARY l USING(rcr)
        LEFT JOIN CLASSIFICATION c ON c.corpus_id=h.corpus_id AND c.ppn=h.ppn
        GROUP BY h.corpus_id,h.rcr,l.label,l.iln,l.library_type""")
