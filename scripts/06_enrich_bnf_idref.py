"""Récupère les Dewey BnF candidates et les métadonnées des RCR du lot."""

import argparse
import json
from pathlib import Path

import httpx

from sudoc_explorer.enrichment import enrich


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prior-reference", type=Path)
    args = parser.parse_args()
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "SudocExplorer/0.4"}) as client:
        report = enrich(args.input_dir, args.run_dir, client, args.prior_reference)
    print(json.dumps({k: v for k, v in report.items() if k not in {"bnf", "rcr_warnings"}}, indent=2))
    raise SystemExit(0 if report["status"] == "complete" else 2)
