# Enrichissement BnF / IdRef et chargement DuckDB

## Lot livré

- Entrée : `data/processed/sudoc/sample-2000/unimarc-v0.3.8` (1 995 notices).
- Enrichissement : `data/enrichment/sample-2000/bnf-idref-v0.1.0`.
- Base : `data/sudoc.duckdb`.
- Identifiant du corpus : `sample-2000-2025-bnf-idref-v1`.

> Convention de version : le dossier `unimarc-v0.3.8` est une extraction produite par `scripts/03_parse_unimarc.py` à partir du parseur `src/analyseur_sudoc/unimarc.py`. La version `0.3.8` désigne ici la version interne du parseur UNIMARC, et non la version du paquet Python.

Les 1 995 notices sont incluses suivant la décision utilisateur, y compris
les travaux universitaires édités et les autres cas précédemment litigieux.
Le filtre antérieur sans 930$b reste appliqué au lot brut de 2 000 notices.
