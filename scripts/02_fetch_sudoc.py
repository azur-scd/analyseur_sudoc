"""Collecte annuelle Sudoc SRU : XML brut et rapport d'exhaustivité."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from sudoc_explorer.sudoc import collect_sudoc

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025, help="Année de publication (défaut : 2025)")
    parser.add_argument("--page-size", type=int, default=200, help="Notices par requête (défaut : 200)")
    parser.add_argument("--max-records", type=int, default=2000, help="Plafond cumulé de notices, cache compris (défaut : 2000)")
    parser.add_argument("--max-pages", type=int, help="Limite totale de pages, y compris celles en cache")
    parser.add_argument("--run-dir", type=Path, help="Dossier de campagne à créer ou reprendre")
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.run_dir or ROOT / "data/raw/sudoc" / str(args.year) / stamp
    try:
        print(f"Collecte {args.year} dans {run_dir}", flush=True)
        with httpx.Client(timeout=90, follow_redirects=True,
                          headers={"User-Agent": "SudocExplorer/0.2"}) as client:
            report = collect_sudoc(client, run_dir, year=args.year, page_size=args.page_size,
                                   max_records=args.max_records,
                                   max_pages=args.max_pages, progress=lambda message: print(message, flush=True))
        print(f"Statut : {report['status']} ; {report['records_validated']} notices validées, "
              f"{report['distinct_ppns']} PPN distincts.")
        print(f"Rapport : {run_dir / 'report.json'}")
        for error in report["errors"]:
            print(error, file=sys.stderr)
        return {"complete": 0, "limited": 2, "failed": 1, "interrupted": 130}[report["status"]]
    except (OSError, ValueError) as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
