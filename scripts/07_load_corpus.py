"""Charge un lot enrichi et ses RCR dans DuckDB, de façon transactionnelle."""

import argparse
import json
from pathlib import Path

from analyseur_sudoc.warehouse import load_corpus
from analyseur_sudoc.sudoc import write_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrichment-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    result = load_corpus(args.enrichment_dir, args.database, args.corpus_id, args.year)
    write_json(args.enrichment_dir / "database-report.json", result)
    print(json.dumps(result, indent=2))
