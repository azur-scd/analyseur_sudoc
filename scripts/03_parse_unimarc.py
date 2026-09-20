"""Extrait les notices déjà collectées, sans requête réseau ni chargement DuckDB."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from sudoc_explorer.unimarc import extract_campaign

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="Dossier de la campagne SRU")
    parser.add_argument("--output-dir", type=Path, help="Nouveau dossier de sortie, vide")
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output_dir or ROOT / "data/processed/sudoc" / args.run_dir.resolve().name / f"unimarc-{stamp}"
    try:
        report = extract_campaign(args.run_dir, output)
        print(f"{report['records_parsed']} notices extraites ; {report['counts']['locations']} zones 930.")
        print(f"{report['records_retained']} notices conservées ; {report['records_excluded']} exclues sans 930$b.")
        print(f"Sortie : {output.resolve()}")
        print(f"{report['counts']['holdings']} couples PPN/RCR distincts ; source 930$b validée par l'utilisateur.")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
