"""Ajoute les classes IdRef à DuckDB dans des tables séparées."""

import argparse
import json
from pathlib import Path

from sudoc_explorer.authority_database import load_authority_enrichment
from sudoc_explorer.sudoc import write_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrichment-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = load_authority_enrichment(args.enrichment_dir, args.database, args.corpus_id, args.run_id)
    write_json(args.enrichment_dir / "database-report.json", result)
    print(json.dumps(result, indent=2))
