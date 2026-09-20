"""Produit les statistiques et anomalies d'une extraction locale, sans collecte."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sudoc_explorer.quality import audit_extraction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output_dir or args.input_dir.resolve().parent / f"audit-{stamp}"
    stats = audit_extraction(args.input_dir, output, args.year)
    print(f"{stats['records']} notices analysées. Résultats : {output.resolve()}")
    print(stats["records_by_category"])


if __name__ == "__main__":
    main()
