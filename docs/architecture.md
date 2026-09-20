# Sudoc Explorer
## Architecture technique — V1

# 1. Pipeline général

```text
                   ┌──────────────────┐
                   │ IdRef / listrcr  │
                   └────────┬─────────┘
                            ▼
                      TSV national
                            │
                   ┌────────┴────────┐
                   │                 │
                   ▼                 ▼
              données RCR       PPN des RCR
                                     │
                                     ▼
                              IdRef/{PPN}.json
                                     │
                                     ▼
                                   130$a
                                     │
                                     ▼
                                  LIBRARY


                  ┌─────────────────┐
                  │    Sudoc SRU    │
                  └────────┬────────┘
                           ▼
                    XML UNIMARC brut
                           │
                           ▼
                    parser UNIMARC
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    DOCUMENT          CLASSIFICATION        HOLDING
    AUTHOR                                   │
    PUBLISHER                                │
        │                                    │
        └────────────────┬───────────────────┘
                         ▼
                       DuckDB
                         │
                         ▼
                  contrôles qualité
                         │
                         ▼
                 profils par RCR
                         │
                         ▼
                    RCR ≥ 1 000
                         │
                         ▼
                     clustering
                         │
                         ▼
                analyses documentaires
                         │
                         ▼
                      Streamlit
```

# 2. Choix techniques

## Python

Langage principal du projet.

## HTTP

`httpx`

## XML

`lxml`

L'utilisation d'une bibliothèque MARC complémentaire pourra être étudiée, mais la logique métier du parsing reste contrôlée dans le projet.

## Base analytique

DuckDB.

## Manipulation de données

- Polars ;
- SQL DuckDB.

## Machine learning

scikit-learn.

## Interface

Streamlit.

## Environnement

`.venv`

Dépendances dans `pyproject.toml`.

# 3. Organisation du dépôt

```text
sudoc-explorer/
│
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
│
├── config/
│   └── groups.yml
│
├── data/
│   ├── raw/
│   │   └── sudoc/
│   ├── reference/
│   │   └── listrcr/
│   ├── processed/
│   └── sudoc.duckdb
│
├── docs/
│   ├── PRD.md
│   ├── functional-spec.md
│   ├── data-spec.md
│   ├── architecture.md
│   ├── validation-plan.md
│   └── unimarc-mapping.md
│
├── src/
│   └── sudoc_explorer/
│       ├── __init__.py
│       ├── config.py
│       ├── sudoc.py
│       ├── unimarc.py
│       ├── libraries.py
│       ├── database.py
│       ├── quality.py
│       ├── similarity.py
│       └── clustering.py
│
├── scripts/
│   ├── 01_fetch_references.py
│   ├── 02_fetch_sudoc.py
│   ├── 03_parse_unimarc.py
│   ├── 04_build_database.py
│   └── 05_analyse.py
│
├── app/
│   └── app.py
│
└── tests/
    ├── fixtures/
    ├── test_unimarc.py
    ├── test_libraries.py
    ├── test_database.py
    ├── test_similarity.py
    └── test_clustering.py
```

# 4. Versionnement Git

Git versionne :

- code ;
- documentation ;
- tests ;
- configuration non sensible ;
- petites fixtures de test.

Ne sont pas versionnés :

- environnement Python ;
- corpus XML massif ;
- DuckDB de production ;
- fichiers intermédiaires volumineux ;
- secrets.

# 5. Étapes de développement

## V0.1 — Référentiels

- téléchargement `listrcr` ;
- nettoyage TSV ;
- récupération des types via IdRef ;
- création de `LIBRARY`.

## V0.2 — Collecte Sudoc

Implémentée dans `sudoc.py` et `scripts/02_fetch_sudoc.py`.
Voir [les règles de collecte SRU](sru-collection.md) pour le découpage par
préfixe PPN, la reprise et la portée du contrôle d'exhaustivité.

- année paramétrable ;
- requête SRU ;
- pagination ;
- conservation XML ;
- rapport d'exhaustivité.

## V0.3 — Parsing UNIMARC

Extraction :

- PPN ;
- titre ;
- année ;
- langue ;
- pays ;
- éditeur ;
- auteurs ;
- Dewey ;
- RCR.

## V0.4 — DuckDB

- tables ;
- chargement ;
- jointures ;
- contrôles qualité.

## V0.5 — Analyse descriptive

- profils RCR ;
- distributions Dewey ;
- statistiques.

## V0.6 — Similarité et clustering

- population RCR ≥ 1 000 ;
- Jaccard ;
- cosinus ;
- clustering ;
- caractérisation.

## V0.7 — Politique documentaire

- documents absents ;
- diffusion réseau ;
- diffusion chez les pairs.

## V0.8 — Interface

- Streamlit ;
- filtres ;
- tableaux ;
- graphiques ;
- navigation.
