# Enrichissement BnF / IdRef et chargement DuckDB

## Lot livré

- Entrée : `data/processed/sudoc/sample-2000/unimarc-v0.3.8` (1 995 notices
  retenues sur le premier corpus de 2 000 notices de documents parus en 2025).
- Enrichissement : `data/enrichment/sample-2000/bnf-idref-v0.1.0`.
- Base : `data/sudoc.duckdb`.
- Identifiant du corpus : `sample-2000-2025-bnf-idref-v1`.

> Convention de version : le dossier `unimarc-v0.3.8` est une extraction produite par `scripts/03_parse_unimarc.py` à partir du parseur `src/analyseur_sudoc/unimarc.py`. La version `0.3.8` désigne ici la version interne du parseur UNIMARC, et non la version du paquet Python.

Pour ce premier corpus de 2 000 notices de documents parus en 2025, les 1 995
notices retenues sont incluses suivant la décision utilisateur, y compris les
travaux universitaires édités et les autres cas précédemment litigieux. Le
filtre antérieur sans 930$b reste appliqué à ce lot brut de 2 000 notices.
