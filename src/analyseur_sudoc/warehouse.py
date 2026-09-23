"""Chargement transactionnel, isolé par corpus, des données enrichies."""

import json
from pathlib import Path

import duckdb

from analyseur_sudoc.database import FIELDS
from analyseur_sudoc.enrichment import digest, read_jsonl
from analyseur_sudoc.sudoc import now

FIELD_LISTS = {"authors": "AUTHOR", "publishers": "PUBLISHER", "subjects": "SUBJECT",
               "summaries": "SUMMARY", "languages": "LANGUAGE", "countries": "COUNTRY",
               "bnf_links": "BNF_LINK", "leader_types": "LEADER_TYPE",
               "content_types": "CONTENT_TYPE", "media_types": "MEDIA_TYPE",
               "nature_of_content": "NATURE_OF_CONTENT", "locations": "LOCATION",
               "coded_dates": "CODED_DATE", "publication_statements": "PUBLICATION_STATEMENT"}


def load_corpus(enrichment_dir, database, corpus_id, year):
    directory, database = Path(enrichment_dir).resolve(), Path(database).resolve()
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    if report["status"] != "complete":
        raise ValueError("Enrichissement incomplet : chargement refusé")
    for file in ("documents", "libraries"):
        if digest((directory / f"{file}.jsonl").read_bytes()) != report[f"{file}_sha256"]:
            raise ValueError(f"Empreinte modifiée : {file}")
    documents, libraries = read_jsonl(directory / "documents.jsonl"), read_jsonl(directory / "libraries.jsonl")
    ppns, rcrs = {d["ppn"] for d in documents}, {r["rcr"] for r in libraries}
    if len(ppns) != len(documents) or len(rcrs) != len(libraries):
        raise ValueError("Identifiants répétés")
    if not documents or len(documents) != report["records"] or len(libraries) != report["libraries"]:
        raise ValueError("Effectifs incohérents")
    holdings = [(corpus_id, d["ppn"], h["rcr"], json.dumps(h, ensure_ascii=False)) for d in documents for h in d["holdings"]]
    if len({(h[1], h[2]) for h in holdings}) != len(holdings) or any(h[2] not in rcrs for h in holdings):
        raise ValueError("Localisations répétées ou RCR absent du référentiel")
    signature = digest(json.dumps([report["documents_sha256"], report["libraries_sha256"], year]).encode())
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("""CREATE TABLE IF NOT EXISTS CORPUS (
                corpus_id VARCHAR PRIMARY KEY, year_requested INTEGER, source_dir VARCHAR,
                signature VARCHAR, loaded_at TIMESTAMPTZ, report JSON)""")
            existing = con.execute("SELECT signature FROM CORPUS WHERE corpus_id=?", [corpus_id]).fetchone()
            if existing:
                if existing[0] != signature:
                    raise ValueError("Ce corpus existe avec des données différentes : utiliser un nouvel identifiant")
                con.execute("COMMIT")
                return dict(status="already_loaded", corpus_id=corpus_id, database=str(database))
            con.execute("""CREATE TABLE IF NOT EXISTS LIBRARY (
                rcr VARCHAR PRIMARY KEY, label VARCHAR, iln VARCHAR, library_ppn VARCHAR,
                library_type VARCHAR, city VARCHAR, postal_code VARCHAR, country VARCHAR,
                latitude DOUBLE, longitude DOUBLE, metadata_retrieved_at TIMESTAMPTZ)""")
            con.execute("""CREATE TABLE IF NOT EXISTS CORPUS_LIBRARY (
                corpus_id VARCHAR REFERENCES CORPUS(corpus_id), rcr VARCHAR REFERENCES LIBRARY(rcr),
                metadata JSON, PRIMARY KEY(corpus_id,rcr))""")
            con.execute("""CREATE TABLE IF NOT EXISTS DOCUMENT (
                corpus_id VARCHAR REFERENCES CORPUS(corpus_id), ppn VARCHAR, title VARCHAR,
                subtitle VARCHAR, publication_year INTEGER, scope_status VARCHAR,
                source JSON, payload JSON, PRIMARY KEY(corpus_id,ppn))""")
            con.execute("""CREATE TABLE IF NOT EXISTS HOLDING (
                corpus_id VARCHAR, ppn VARCHAR, rcr VARCHAR REFERENCES LIBRARY(rcr), evidence JSON,
                PRIMARY KEY(corpus_id,ppn,rcr), FOREIGN KEY(corpus_id,ppn) REFERENCES DOCUMENT(corpus_id,ppn))""")
            con.execute("""CREATE TABLE IF NOT EXISTS CLASSIFICATION (
                corpus_id VARCHAR, ppn VARCHAR, occurrence INTEGER, dewey_raw VARCHAR,
                dewey_normalized VARCHAR, dewey_1 VARCHAR, dewey_2 VARCHAR, dewey_3 VARCHAR,
                source VARCHAR, annotation VARCHAR, payload JSON, PRIMARY KEY(corpus_id,ppn,occurrence),
                FOREIGN KEY(corpus_id,ppn) REFERENCES DOCUMENT(corpus_id,ppn))""")
            con.execute("""CREATE TABLE IF NOT EXISTS DOCUMENT_FIELD (
                corpus_id VARCHAR, ppn VARCHAR, category VARCHAR, occurrence INTEGER, payload JSON,
                PRIMARY KEY(corpus_id,ppn,category,occurrence),
                FOREIGN KEY(corpus_id,ppn) REFERENCES DOCUMENT(corpus_id,ppn))""")
            con.execute("INSERT INTO CORPUS VALUES (?,?,?,?,?,?)", [corpus_id, year, str(directory), signature, now(), json.dumps(report)])
            con.executemany(f"INSERT INTO LIBRARY ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)}) ON CONFLICT DO NOTHING",
                            [[row.get(k) for k in FIELDS] for row in libraries])
            con.executemany("INSERT INTO CORPUS_LIBRARY VALUES (?,?,?)", [(corpus_id, r["rcr"], json.dumps(r, ensure_ascii=False)) for r in libraries])
            con.executemany("INSERT INTO DOCUMENT VALUES (?,?,?,?,?,?,?,?)", [
                (corpus_id, d["ppn"], d["title"], d["subtitle"], d["publication_year"], "included_user_validated",
                 json.dumps(d["source"]), json.dumps(d, ensure_ascii=False)) for d in documents])
            if holdings:
                con.executemany("INSERT INTO HOLDING VALUES (?,?,?,?)", holdings)
            classifications = [(corpus_id, d["ppn"], i, v["dewey_raw"], v["dewey_normalized"],
                                v["dewey_1"], v["dewey_2"], v["dewey_3"], v.get("dewey_source", "sudoc:676$a"),
                                v.get("dewey_annotation"), json.dumps(v, ensure_ascii=False))
                               for d in documents for i, v in enumerate(d["classifications"], 1)]
            if classifications:
                con.executemany("INSERT INTO CLASSIFICATION VALUES (?,?,?,?,?,?,?,?,?,?,?)", classifications)
            occurrences = [(corpus_id, d["ppn"], key, i, json.dumps(v, ensure_ascii=False))
                           for d in documents for key in FIELD_LISTS for i, v in enumerate(d.get(key, []), 1)]
            if occurrences:
                con.executemany("INSERT INTO DOCUMENT_FIELD VALUES (?,?,?,?,?)", occurrences)
            for key, name in FIELD_LISTS.items():
                con.execute(f"""CREATE OR REPLACE VIEW {name} AS
                    SELECT corpus_id, ppn, occurrence, json_extract_string(payload, '$.source_field') AS source_field,
                    json_extract_string(payload, '$.value') AS value, payload
                    FROM DOCUMENT_FIELD WHERE category='{key}'""")
            con.execute("""CREATE OR REPLACE VIEW LIBRARY_PROFILE AS
                SELECT h.corpus_id, h.rcr, l.label, l.iln, l.library_type, count(DISTINCT h.ppn) AS documents,
                count(DISTINCT CASE WHEN c.dewey_normalized IS NOT NULL THEN h.ppn END) AS documents_with_dewey
                FROM HOLDING h JOIN LIBRARY l USING(rcr)
                LEFT JOIN CLASSIFICATION c ON c.corpus_id=h.corpus_id AND c.ppn=h.ppn
                GROUP BY h.corpus_id,h.rcr,l.label,l.iln,l.library_type""")
            counts = {name: con.execute(f"SELECT count(*) FROM {name} WHERE corpus_id=?", [corpus_id]).fetchone()[0]
                      for name in ["DOCUMENT", "HOLDING", "CLASSIFICATION", "DOCUMENT_FIELD", "CORPUS_LIBRARY"]}
            if counts["DOCUMENT"] != len(documents) or counts["HOLDING"] != len(holdings):
                raise ValueError("Vérification des effectifs après chargement échouée")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    return dict(status="loaded", database=str(database), corpus_id=corpus_id, counts=counts)
