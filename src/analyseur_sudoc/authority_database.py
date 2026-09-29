"""Chargement des classifications d'autorités dans CLASSIFICATION."""

import json
import re
from pathlib import Path

import duckdb

from analyseur_sudoc.enrichment import digest, read_jsonl
from analyseur_sudoc.classification_database import ensure_classification_schema
from analyseur_sudoc.sudoc import now


def insert_batch(con, table, rows):
    if not rows:
        return
    for offset in range(0, len(rows), 250):
        chunk = rows[offset:offset + 250]
        columns = [list(values) for values in zip(*chunk)]
        con.execute(f"INSERT INTO {table} SELECT {', '.join('unnest(?)' for _ in columns)}", columns)


def load_authority_enrichment(directory, database, corpus_id, run_id):
    directory = Path(directory).resolve()
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    if report["status"] != "complete" or not report["document_dewey_unchanged"]:
        raise ValueError("Enrichissement incomplet ou Dewey bibliographiques modifiées")
    raw = (directory / "documents.jsonl").read_bytes()
    if digest(raw) != report["documents_sha256"]:
        raise ValueError("Documents enrichis modifiés")
    documents = read_jsonl(directory / "documents.jsonl")
    if len(documents) != report["records"] or len({d["ppn"] for d in documents}) != len(documents):
        raise ValueError("Effectifs ou PPN invalides")
    with duckdb.connect(str(database)) as con:
        original = con.execute("SELECT report FROM CORPUS WHERE corpus_id=?", [corpus_id]).fetchone()
        if not original or json.loads(original[0])["documents_sha256"] != report["input_documents_sha256"]:
            raise ValueError("Le corpus ne correspond pas à l'entrée de l'enrichissement")
        stored = dict(con.execute("SELECT ppn,payload FROM DOCUMENT WHERE corpus_id=?", [corpus_id]).fetchall())
        if stored.keys() != {d["ppn"] for d in documents}:
            raise ValueError("Jeux de PPN différents")
        for d in documents:
            baseline = {k: v for k, v in d.items() if k not in {"idref_606a_links", "idref_606a_classifications"}}
            if baseline != json.loads(stored[d["ppn"]]):
                raise ValueError(f"Données bibliographiques modifiées pour {d['ppn']}")
        con.execute("BEGIN TRANSACTION")
        try:
            ensure_classification_schema(con)
            con.execute("""CREATE TABLE IF NOT EXISTS AUTHORITY_RUN (
                run_id VARCHAR PRIMARY KEY, corpus_id VARCHAR REFERENCES CORPUS(corpus_id),
                documents_sha256 VARCHAR, loaded_at TIMESTAMPTZ, report JSON)""")
            previous = con.execute("SELECT corpus_id,documents_sha256 FROM AUTHORITY_RUN WHERE run_id=?", [run_id]).fetchone()
            if previous:
                if previous != (corpus_id, report["documents_sha256"]):
                    raise ValueError("Identifiant d'enrichissement déjà utilisé pour d'autres données")
                con.execute("COMMIT")
                return dict(status="already_loaded", run_id=run_id)
            con.execute("""CREATE TABLE IF NOT EXISTS AUTHORITY_DOCUMENT (
                run_id VARCHAR REFERENCES AUTHORITY_RUN(run_id), corpus_id VARCHAR, ppn VARCHAR, payload JSON,
                PRIMARY KEY(run_id,ppn), FOREIGN KEY(corpus_id,ppn) REFERENCES DOCUMENT(corpus_id,ppn))""")
            con.execute("""CREATE TABLE IF NOT EXISTS AUTHORITY_HEADING (
                run_id VARCHAR, ppn VARCHAR, occurrence INTEGER, authority_ppn VARCHAR,
                status VARCHAR, payload JSON, PRIMARY KEY(run_id,ppn,occurrence),
                FOREIGN KEY(run_id,ppn) REFERENCES AUTHORITY_DOCUMENT(run_id,ppn))""")
            con.execute("INSERT INTO AUTHORITY_RUN VALUES (?,?,?,?,?)", [run_id, corpus_id, report["documents_sha256"], now(), json.dumps(report)])
            insert_batch(con, "AUTHORITY_DOCUMENT", [(run_id, corpus_id, d["ppn"], json.dumps(d, ensure_ascii=False)) for d in documents])
            headings = [(run_id, d["ppn"], i, h["authority_ppn"], h["status"], json.dumps(h, ensure_ascii=False))
                        for d in documents for i, h in enumerate(d["idref_606a_links"], 1)]
            insert_batch(con, "AUTHORITY_HEADING", headings)
            classes = []
            for d in documents:
                for i, item in enumerate(d["idref_606a_classifications"], 1):
                    code = item["code"]
                    is_dewey = item["scheme"] == "dewey" and bool(
                        code and re.fullmatch(r"[0-9]{3}(?:\.[0-9]+)?", code))
                    classes.append((corpus_id, d["ppn"], i,
                                    item["code_raw"] if item["scheme"] == "dewey" else None,
                                    code if is_dewey else None,
                                    code[:1] if is_dewey else None,
                                    code[:2] if is_dewey else None,
                                    code[:3] if is_dewey else None,
                                    item["source"], None, json.dumps(item, ensure_ascii=False), run_id,
                                    item["scheme"], item["code_raw"], code,
                                    item["via_606a"]["authority_ppn"], item["authority_ppn"]))
            if classes:
                con.executemany("""INSERT INTO CLASSIFICATION
                    (corpus_id,ppn,occurrence,dewey_raw,dewey_normalized,dewey_1,dewey_2,dewey_3,
                     source,annotation,payload,run_id,scheme,code_raw,code,requested_authority_ppn,resolved_authority_ppn)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", classes)
            counts = {table: con.execute(f"SELECT count(*) FROM {table} WHERE run_id=?", [run_id]).fetchone()[0]
                      for table in ["AUTHORITY_DOCUMENT", "AUTHORITY_HEADING"]}
            counts["CLASSIFICATION"] = con.execute(
                "SELECT count(*) FROM CLASSIFICATION WHERE run_id=?", [run_id]).fetchone()[0]
            if list(counts.values()) != [len(documents), len(headings), len(classes)]:
                raise ValueError("Écart d'effectifs dans le chargement")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    return dict(status="loaded", run_id=run_id, corpus_id=corpus_id, database=str(Path(database).resolve()), counts=counts)
