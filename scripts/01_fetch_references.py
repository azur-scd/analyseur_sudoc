"""Télécharge le référentiel RCR, enrichit ses types et crée LIBRARY."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

from sudoc_explorer.database import save_libraries
from sudoc_explorer.libraries import collect_references

ROOT = Path(__file__).resolve().parents[1]


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("La limite doit être positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="TSV local, sinon téléchargement listrcr")
    parser.add_argument("--run-dir", type=Path, help="Dossier de campagne à créer ou reprendre")
    parser.add_argument("--database", type=Path, help="Base de destination")
    parser.add_argument("--limit", type=positive, help="Limiter le nombre de RCR pour un essai")
    args = parser.parse_args()
    run_dir = args.run_dir or ROOT / "data/reference/listrcr" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    database = args.database or ROOT / "data" / ("sudoc.sample.duckdb" if args.limit else "sudoc.duckdb")
    try:
        print(f"Collecte dans {run_dir}", flush=True)
        with httpx.Client(timeout=30, follow_redirects=True,
                          headers={"User-Agent": "SudocExplorer/0.1"}) as client:
            rows, report = collect_references(client, run_dir, args.source, args.limit)
        report["database"] = str(database.resolve())
        report["database_written"] = False
        report_path = run_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if report["errors"]:
            print(f"{len(report['errors'])} échec(s) IdRef. Base non modifiée. Rapport : {report_path}", file=sys.stderr)
            return 2
        save_libraries(rows, database)
        report["database_written"] = True
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(rows)} bibliothèques ; {report['with_type']} avec type. Base : {database}")
        print(f"Rapport : {report_path}")
        return 0
    except (OSError, ValueError, httpx.HTTPError, duckdb.Error) as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
