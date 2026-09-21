"""Collecte les autorités des seules 606$a et enrichit une copie des JSON."""

import argparse
import json
from pathlib import Path

import httpx

from sudoc_explorer.authority_enrichment import collect_authorities, enrich_documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--process-only", action="store_true")
    parser.add_argument("--include-rameau", action="store_true")
    args = parser.parse_args()
    if args.collect_only and args.process_only:
        parser.error("Modes collect-only et process-only incompatibles")
    if not args.process_only:
        with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "SudocExplorer/0.4"}) as client:
            report = collect_authorities(args.input_dir, args.run_dir, client)
        print(json.dumps({k: v for k, v in report.items() if k != "authorities"}, indent=2))
        if report["status"] != "complete":
            raise SystemExit(2)
    if not args.collect_only:
        print(json.dumps(enrich_documents(args.run_dir, args.include_rameau), indent=2))
