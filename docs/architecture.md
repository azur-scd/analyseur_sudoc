# Sudoc Explorer
## Architecture technique

Ce document distingue l'architecture effectivement implémentée dans le dépôt et
la cible V1 décrite dans le [PRD](PRD.md). Les éléments absents de l'arborescence
actuelle sont explicitement signalés comme prévus et non comme présents.

# 1. Architecture actuellement implémentée

## 1.1. Pipeline livré

```text
IdRef / listrcr ──► référentiel RCR + types de bibliothèques
                         │
                         ▼
                    Sudoc SRU
                         │
                         ▼
                  XML UNIMARC brut
                         │
                         ▼
                   parsing UNIMARC
                         │
         ┌───────────────┼────────────────┬────────────────┐
         ▼               ▼                ▼                ▼
    documents       holdings        classifications    locations
         │               │                │                │
         └───────────────┴────────────────┴────────────────┘
                         │
                         ▼
                    audit qualité
                         │
                         ▼
            normalisation Dewey et enrichissements
                  (BnF, types RCR, autorités 606$a)
                         │
                         ▼
                        DuckDB
```

## 1.2. Modules présents

```text
src/sudoc_explorer/
├── authority_database.py
├── authority_enrichment.py
├── database.py
├── enrichment.py
├── libraries.py
├── quality.py
├── sudoc.py
├── unimarc.py
└── warehouse.py
```

## 1.3. Scripts présents

```text
scripts/
├── 01_fetch_references.py
├── 02_fetch_sudoc.py
├── 03_parse_unimarc.py
├── 04_audit_unimarc.py
├── 05_dewey_review.py
├── 06_enrich_bnf_idref.py
├── 07_load_corpus.py
├── 08_enrich_606a_authorities.py
└── 09_load_authority_enrichment.py
```

## 1.4. Organisation du dépôt documentée à partir de l'arborescence réelle

```text
./
├── README.md
├── pyproject.toml
├── docs/
│   ├── PRD.md
│   ├── functional-spec.md
│   ├── data-spec.md
│   ├── architecture.md
│   ├── validation-plan.md
│   ├── unimarc-mapping.md
│   ├── sru-collection.md
│   ├── quality-audit.md
│   ├── dewey-enrichment.md
│   ├── enrichment-and-database.md
│   ├── idref-subject-classifications.md
│   ├── index.md
│   ├── decisions.md
│   ├── output-contracts.md
│   └── reproduction.md
├── scripts/
│   ├── 01_fetch_references.py
│   ├── 02_fetch_sudoc.py
│   ├── 03_parse_unimarc.py
│   ├── 04_audit_unimarc.py
│   ├── 05_dewey_review.py
│   ├── 06_enrich_bnf_idref.py
│   ├── 07_load_corpus.py
│   ├── 08_enrich_606a_authorities.py
│   └── 09_load_authority_enrichment.py
├── src/
│   └── sudoc_explorer/
│       ├── __init__.py
│       ├── authority_database.py
│       ├── authority_enrichment.py
│       ├── database.py
│       ├── enrichment.py
│       ├── libraries.py
│       ├── quality.py
│       ├── sudoc.py
│       ├── unimarc.py
│       └── warehouse.py
└── tests/
    ├── test_authority_enrichment.py
    ├── test_database.py
    ├── test_enrichment.py
    ├── test_libraries.py
    ├── test_quality.py
    ├── test_sudoc.py
    └── test_unimarc.py
```

## 1.5. Artefacts locaux et données non versionnés

Git versionne :

- le code ;
- la documentation ;
- les tests ;
- la configuration non sensible ;
- les petites fixtures de test.

Ne sont pas versionnés :

- l'environnement Python ;
- les corpus XML massifs ;
- les bases DuckDB de travail ;
- les fichiers intermédiaires volumineux ;
- les caches de campagnes et d'enrichissements ;
- les secrets.

# 2. Architecture cible V1

## 2.1. Chaîne fonctionnelle cible

La cible V1 décrite par le PRD prolonge le pipeline livré par des traitements
analytiques et une interface locale. Les critères de validation attendus pour
ces étapes à venir sont détaillés dans le [plan de validation](validation-plan.md) :

```text
DuckDB ──► profils par RCR ──► similarité ──► clustering ──►
analyses documentaires ──► interface Streamlit
```

## 2.2. Éléments prévus mais absents de l'arborescence actuelle

Les éléments ci-dessous sont mentionnés dans la cible V1 ou dans d'anciennes
versions de la documentation, mais **ne sont pas présents** dans le dépôt actuel :

- `app/app.py` ;
- `config/groups.yml` ;
- `src/sudoc_explorer/similarity.py` ;
- `src/sudoc_explorer/clustering.py`.

Ils doivent être considérés comme des composants prévus, non encore livrés.

# 3. Feuille de route V0.1 à V0.8

## V0.1 — Référentiels (**livré**)

- téléchargement `listrcr` ;
- nettoyage TSV ;
- récupération des types via IdRef ;
- création de `LIBRARY`.

## V0.2 — Collecte Sudoc (**livré**)

Implémentée dans `sudoc.py` et `scripts/02_fetch_sudoc.py`.
Voir [les règles de collecte SRU](sru-collection.md) pour le découpage par
préfixe PPN, la reprise et la portée du contrôle d'exhaustivité.

- année paramétrable ;
- requête SRU ;
- pagination ;
- conservation XML ;
- rapport d'exhaustivité.

## V0.3 — Parsing UNIMARC (**livré**)

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

## V0.3.1 à V0.3.8 — Audit et normalisation Dewey (**livrés**)

- audit statistique des extractions ;
- contrôles de couverture et d'anomalies ;
- normalisation Dewey ;
- préparation du lot candidat BnF.

## V0.4 — Enrichissements et DuckDB (**livré**)

- enrichissements BnF et IdRef ;
- chargement transactionnel dans DuckDB ;
- chargement séparé des classifications d'autorité ;
- contrôles d'identité des lots, des empreintes et des relations PPN/RCR.

## V0.5 — Analyse descriptive (**à venir**)

- profils RCR ;
- distributions Dewey ;
- statistiques descriptives pour l'exploration analytique.

## V0.6 — Similarité et clustering (**à venir**)

- population RCR ≥ 1 000 ;
- Jaccard ;
- cosinus ;
- clustering ;
- caractérisation.

## V0.7 — Politique documentaire (**à venir**)

- documents absents ;
- diffusion réseau ;
- diffusion chez les pairs.

## V0.8 — Interface (**à venir**)

- Streamlit ;
- filtres ;
- tableaux ;
- graphiques ;
- navigation.

# 4. Convention documentaire sur les versions

Plusieurs niveaux de version coexistent dans le projet :

- **version du paquet Python** : portée par `pyproject.toml` ;
- **version du parser / format d'extraction** : par exemple `unimarc-v0.3.8` ;
- **version des audits, lots et enrichissements** : par exemple `audit-v0.3.1`,
  `bnf-idref-v0.1.0` ou `idref-606a-v0.1.0` ;
- **cible produit V1** : niveau fonctionnel visé par le PRD et les spécifications.
