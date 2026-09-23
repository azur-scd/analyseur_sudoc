# Parcours de reproduction

Ce document réutilise les commandes déjà présentes dans le README et les autres
documents. Les dossiers `data/…` cités ci-dessous sont des artefacts locaux non
versionnés. Les étapes de collecte et certains enrichissements dépendent du réseau.
Les commandes reprises ici sont celles déjà documentées pour **PowerShell sous
Windows**.

## Convention des identifiants d'exemple

Les commandes et requêtes reprises ci-dessous réemploient les identifiants déjà
documentés pour le lot de démonstration :

- `corpus_id` d'exemple : `sample-2000-2025-bnf-idref-v1` ;
- `run_id` d'exemple : `idref-606a-v1`.

## 1. Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Après mise à jour du projet, réinstaller les dépendances avec :

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

## 2. Tests hors réseau

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Ces tests s'exécutent sans collecte réseau supplémentaire.

## 3. Collecte réseau

### Référentiel RCR et types de bibliothèques

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py --limit 10
```

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py
```

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py --run-dir data/reference/listrcr/DATE_CAMPAGNE
```

Le TSV `listrcr` et l'enrichissement IdRef nécessitent le réseau, sauf si les
fichiers déjà présents dans le dossier de campagne sont réutilisés.

### Collecte Sudoc SRU

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 1 --max-pages 2
```

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 200 --max-records 2000
```

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 200 --max-records 2000 --run-dir data/raw/sudoc/2025/NOM_CAMPAGNE
```

Ces commandes créent ou réutilisent des campagnes locales dans
`data/raw/sudoc/<année>/<campagne>/` et dépendent du réseau SRU.

## 4. Parsing UNIMARC

```powershell
.\.venv\Scripts\python.exe scripts/03_parse_unimarc.py --run-dir data/raw/sudoc/2025/sample-2000
```

Cette étape travaille sur les XML déjà téléchargés et crée un nouveau dossier
local sous `data/processed/sudoc/sample-2000/`.
Dans ce parcours, `sample-2000` désigne le nom local du lot collecté ; les
identifiants `sample-2000-2025-bnf-idref-v1` et `idref-606a-v1` utilisés plus
loin correspondent au chargement DuckDB de ce même lot après enrichissement.

## 5. Audit

### Audit d'une extraction

```powershell
.\.venv\Scripts\python.exe scripts/04_audit_unimarc.py --input-dir data/processed/sudoc/sample-2000/unimarc-v0.3.7 --year 2025 --output-dir data/processed/sudoc/sample-2000/audit-v0.2.0
```

### Audit d'un lot enrichi et périmètre validé

```powershell
.\.venv\Scripts\python.exe scripts/04_audit_unimarc.py --input-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --year 2025 --scope-validated --output-dir data/processed/sudoc/sample-2000/audit-v0.3.1
```

### Revue locale de la normalisation Dewey

```powershell
.\.venv\Scripts\python.exe scripts/05_dewey_review.py --before data/processed/sudoc/sample-2000/unimarc-v0.3.7 --after data/processed/sudoc/sample-2000/unimarc-v0.3.8 --output-dir data/processed/sudoc/sample-2000/dewey-review-v0.3.8
```

Ces étapes sont locales et n'effectuent pas de requêtes réseau.

## 6. Enrichissement

### Enrichissement BnF / IdRef du lot bibliographique

Dans cet exemple, `data/reference/listrcr/smoke-test` désigne un répertoire de
référence déjà collecté et réutilisé comme cache antérieur, conformément à la
commande documentée dans `enrichment-and-database.md`.

```powershell
.\.venv\Scripts\python.exe scripts/06_enrich_bnf_idref.py --input-dir data/processed/sudoc/sample-2000/unimarc-v0.3.8 --run-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --prior-reference data/reference/listrcr/smoke-test
```

### Enrichissement des autorités liées aux `606$a`

```powershell
.\.venv\Scripts\python.exe scripts/08_enrich_606a_authorities.py --input-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --run-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --include-rameau
```

Ces étapes dépendent du réseau lors de la collecte BnF/IdRef, sauf réutilisation
complète d'un cache déjà présent dans les dossiers d'enrichissement.

## 7. Chargement DuckDB

Le chargement est documenté en deux temps : d'abord le corpus bibliographique
issu du lot `bnf-idref-v0.1.0`, puis l'enrichissement d'autorités `idref-606a`
chargé séparément sur ce même corpus via `scripts/09_load_authority_enrichment.py`.

### Chargement du corpus enrichi

Dans cet exemple de chargement, le dossier
`data/enrichment/sample-2000/bnf-idref-v0.1.0` est chargé dans DuckDB sous
`corpus_id = sample-2000-2025-bnf-idref-v1`.

```powershell
.\.venv\Scripts\python.exe scripts/07_load_corpus.py --enrichment-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-idref-v1 --year 2025
```

### Chargement de l'enrichissement d'autorités

Dans cet exemple, le dossier `data/enrichment/sample-2000/idref-606a-v0.1.0`
complète ensuite ce corpus avec `run_id = idref-606a-v1`, sans changer
l'identifiant de corpus.

```powershell
.\.venv\Scripts\python.exe scripts/09_load_authority_enrichment.py --enrichment-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-idref-v1 --run-id idref-606a-v1
```

Le fichier `data/sudoc.duckdb` est un artefact local non versionné.

## 8. Vérifications SQL

```sql
-- Toutes les Dewey ajoutées par la BnF.
SELECT ppn, dewey_raw, dewey_normalized
FROM CLASSIFICATION WHERE source = 'bnf:676$a';
```

```sql
-- Notices et noms des bibliothèques possédantes pour le lot livré.
SELECT d.ppn, d.title, l.rcr, l.label, l.iln, l.library_type
FROM DOCUMENT d
JOIN HOLDING h USING (corpus_id, ppn)
JOIN LIBRARY l USING (rcr)
WHERE d.corpus_id = 'sample-2000-2025-bnf-idref-v1';
```

```sql
-- Les résumés répétés restent des lignes distinctes.
SELECT ppn, occurrence, value FROM SUMMARY;
```

```sql
-- Classes distinctes par notice et par méthode IdRef.
SELECT DISTINCT ppn, scheme, code
FROM AUTHORITY_CLASSIFICATION
WHERE run_id = 'idref-606a-v1' AND code IS NOT NULL;
```

```sql
-- Comparer sans mélanger les méthodes : sudoc:676$a, bnf:676$a,
-- idref:dewey, idref:rameau_domain.
SELECT DISTINCT ppn, source AS methode, dewey_normalized AS code
FROM CLASSIFICATION
WHERE corpus_id = 'sample-2000-2025-bnf-idref-v1' AND dewey_normalized IS NOT NULL
UNION ALL
SELECT DISTINCT ppn, 'idref:' || scheme AS methode, code
FROM AUTHORITY_CLASSIFICATION
WHERE run_id = 'idref-606a-v1' AND code IS NOT NULL;
```
