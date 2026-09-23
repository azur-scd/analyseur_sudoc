# Sudoc Explorer

Les classifications IdRef des autorités liées aux seules `606$a` sont traitées
séparément : [sélection, structure JSON et accès DuckDB](docs/idref-subject-classifications.md).

Le lot enrichi BnF et IdRef est chargé dans `data/sudoc.duckdb`.
Voir [l'enrichissement et le schéma DuckDB](docs/enrichment-and-database.md)
pour les commandes de reprise, la provenance des données et les requêtes SQL.

Le contrôle statistique des extractions est disponible dans
`scripts/04_audit_unimarc.py` : pays, langues, dates, Dewey, indexations,
résumés et signaux de documents hors périmètre. Voir les commandes, fichiers
produits et limites dans [la documentation de l'audit](docs/quality-audit.md).

Application locale d'exploration et d'analyse des collections signalées dans le Sudoc.

## Architecture actuelle et cible V1

### Architecture actuellement implémentée

Le dépôt implémente aujourd'hui un pipeline documentaire et technique couvrant :

- le référentiel RCR via `listrcr` et l'enrichissement IdRef des bibliothèques ;
- la collecte Sudoc SRU par campagnes rejouables ;
- l'extraction UNIMARC des notices, localisations, résumés, indexations et liens BnF ;
- l'audit qualité local des lots extraits et enrichis ;
- la normalisation Dewey et la préparation de l'enrichissement BnF ;
- les enrichissements BnF/IdRef ;
- le chargement analytique local dans DuckDB.

### Cible V1 encore à venir

Le [PRD](docs/PRD.md) et les spécifications décrivent une cible V1 plus large.
Les profils RCR, la similarité, le clustering, l'analyse documentaire et
l'interface Streamlit restent des objectifs à venir ; ils ne sont pas décrits
ici comme déjà implémentés.

## Documentation

- [Index de la documentation](docs/index.md)

### Vision et spécifications

- [PRD](docs/PRD.md)
- [Spécification fonctionnelle](docs/functional-spec.md)
- [Spécification des données](docs/data-spec.md)

### Pipeline implémenté

- [Collecte Sudoc SRU](docs/sru-collection.md)
- [Mapping UNIMARC](docs/unimarc-mapping.md)
- [Audit local des extractions](docs/quality-audit.md)
- [Normalisation Dewey et préparation de l'enrichissement BnF](docs/dewey-enrichment.md)
- [Enrichissement BnF / IdRef et chargement DuckDB](docs/enrichment-and-database.md)
- [Classifications IdRef via les seules têtes 606$a](docs/idref-subject-classifications.md)
- [Contrats documentaires des sorties](docs/output-contracts.md)
- [Parcours de reproduction](docs/reproduction.md)

### Qualité, validation et tests

- [Plan de validation et de tests](docs/validation-plan.md)
- [Synthèse des décisions documentées](docs/decisions.md)

### Architecture et évolution

- [Architecture technique](docs/architecture.md)

## Principes V1

Les principes ci-dessous décrivent la cible produit V1. Seule la partie pipeline
et constitution du corpus est actuellement implémentée dans le dépôt.

- une année de publication à la fois ;
- première année : 2025 ;
- monographies imprimées et documents multisupports physiques ;
- clustering au niveau RCR ;
- seuil d'éligibilité au clustering : 1 000 documents du corpus annuel ;
- référentiel RCR via IdRef `listrcr` ;
- type de bibliothèque via `130$a` de la notice RCR IdRef ;
- stockage analytique local dans DuckDB ;
- prototype en Python et Streamlit.

## Statut du dépôt

- **V0.1 — Référentiels : livré** (`scripts/01_fetch_references.py`, table `LIBRARY`).
- **V0.2 — Collecte Sudoc SRU : livrée** (`scripts/02_fetch_sudoc.py`, campagnes,
  `manifest.json`, `report.json`, reprise des pages XML).
- **V0.3 — Parsing UNIMARC : livré** (`scripts/03_parse_unimarc.py`, extractions
  `documents.jsonl`, `holdings.jsonl`, `classifications.jsonl`, `subjects.jsonl`,
  `summaries.jsonl`, `bnf_links.jsonl`, `locations.jsonl`).
- **V0.3.1 à V0.3.8 — Audit et normalisation Dewey : livrés**
  (`scripts/04_audit_unimarc.py`, `scripts/05_dewey_review.py`).
- **V0.4 — Enrichissements et chargement DuckDB : livré**
  (`scripts/06_enrich_bnf_idref.py` à `scripts/09_load_authority_enrichment.py`).
- **V0.5 à V0.8 — Profils RCR, similarité, clustering, analyses et interface : à venir**.

## Convention documentaire sur les versions

Plusieurs niveaux de version coexistent dans le dépôt ; ils ne décrivent pas la
même chose :

- **version du paquet Python** : version publiée dans `pyproject.toml` ;
- **version du parser / format d'extraction** : versions telles que `unimarc-v0.3.8` ;
- **version des lots, audits et enrichissements** : versions de dossiers et de
  campagnes comme `audit-v0.3.1`, `bnf-idref-v0.1.0` ou `idref-606a-v0.1.0` ;
- **cible produit V1** : niveau fonctionnel décrit par le PRD et les spécifications.

## Installation (PowerShell, Python 3.11 ou supérieur)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## Collecter les bibliothèques

Essai sur 10 RCR (base distincte `data/sudoc.sample.duckdb`) :

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py --limit 10
```

Collecte nationale (base `data/sudoc.duckdb`) :

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py
```

Le script télécharge le [TSV national IdRef](https://www.idref.fr/services/listrcr),
le décode en UTF-16 ou UTF-8 et conserve les identifiants sous forme de chaînes.
Il récupère les notices `https://www.idref.fr/{PPN}.json` et extrait `130$a`.
Les sous-zones `a` multiples sont dédupliquées et séparées par ` ; `.
Une bibliothèque sans PPN ou sans type reste présente, avec une valeur nulle.
Les coordonnées invalides deviennent nulles et sont signalées dans le rapport,
avec leur valeur source. Les identifiants invalides arrêtent l'import.
Les RCR dupliqués sont fusionnés : les champs contradictoires deviennent nuls,
leurs valeurs sont conservées dans les avertissements du rapport. Aucun PPN
contradictoire n'est choisi arbitrairement pour l'enrichissement.

Chaque campagne conserve le TSV brut, les JSON IdRef valides, un manifeste daté
et `report.json` dans `data/reference/listrcr/<date>/`. Le rapport indique les
volumes, la couverture des types et les erreurs. La date `metadata_retrieved_at`
est celle de récupération du TSV de la campagne. Ces fichiers et les bases sont
ignorés par Git. Les requêtes sont séquentielles, espacées d'au moins 0,2 seconde ;
les erreurs transitoires sont réessayées jusqu'à trois tentatives.

Pour reprendre une campagne interrompue ou en erreur, réutiliser son dossier :

```powershell
.\.venv\Scripts\python.exe scripts/01_fetch_references.py --run-dir data/reference/listrcr/<date>
```

Ajouter `--limit 10` pour reprendre un essai limité. Les JSON déjà présents sont
réutilisés ; une nouvelle campagne récupère des données fraîches. `--source fichier.tsv`
permet de fournir le TSV local à une nouvelle campagne ; l'enrichissement IdRef
nécessite toujours le réseau si les JSON ne sont pas déjà en cache.

`--database chemin.duckdb` change la destination. En cas de succès, `LIBRARY`
est remplacée dans une transaction, les autres tables sont conservées.
Un échec IdRef produit un rapport et laisse la base intacte (code de sortie 2).
Les autres erreurs retournent 1 ; le succès retourne 0.

## Collecter le corpus Sudoc d'une année

Après mise à jour du projet, réinstaller les dépendances avec
`.\.venv\Scripts\python.exe -m pip install -e .` (ajout de `lxml`).

Essai de pagination sur deux pages, avec une notice par page :

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 1 --max-pages 2
```

Collecte de travail : au maximum **2 000 notices**, par pages de **200**.
Aucune collecte complète ne doit être lancée sans demande explicite de l'utilisateur.

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 200 --max-records 2000
```

Le script parcourt les dix préfixes PPN numériques, de `0` à `9`, en appliquant
`apu=<année> and (tdo=b or tdo=x)`. Il conserve les réponses SRU contenant les
notices UNIMARC et les exemplaires dans `data/raw/sudoc/<année>/<campagne>/`.
Cette étape collecte les candidats du corpus ; la validation métier du support
physique et des exclusions sera effectuée lors du parsing UNIMARC (V0.3).

Pour reprendre une campagne, fournir le même dossier, la même année et la même
taille de page et le même plafond `--max-records`. Retirer `--max-pages` peut
poursuivre un essai, mais ne supprime jamais le plafond de notices :

```powershell
.\.venv\Scripts\python.exe scripts/02_fetch_sudoc.py --year 2025 --page-size 200 --max-records 2000 --run-dir data/raw/sudoc/2025/<campagne>
```

Les pages déjà présentes sont vérifiées et réutilisées. `manifest.json` conserve
le plafond de notices, qui inclut les pages en cache. La dernière requête est
réduite au nombre restant : les pages courtes des préfixes précédents comptent
dans les 2 000 notices. Les anciennes campagnes sans plafond enregistré
nécessitent un nouveau dossier avec cette version.
`manifest.json` conserve également
les paramètres, `report.json` les comptes par préfixe et le statut de la campagne.
Les réponses rejetées sont conservées dans `rejected/`. Aucun chargement du
corpus dans DuckDB n'est effectué à ce stade.

Un rapport `complete` signifie que toutes les pages des dix préfixes ont été
validées, avec autant de PPN distincts que de notices annoncées par le serveur.
Un essai reste `limited`, une erreur `failed`, un arrêt clavier `interrupted`.
Les codes de sortie correspondants sont 0, 2, 1 et 130. Un code 2 est donc attendu
pour un essai limité. Une variation des totaux ou des PPN répétés arrête la
collecte : créer alors une nouvelle campagne pour ne pas mélanger les résultats.

Voir [les choix et limites de la collecte SRU](docs/sru-collection.md).

## Extraire les données UNIMARC du lot existant

```powershell
.\.venv\Scripts\python.exe scripts/03_parse_unimarc.py --run-dir data/raw/sudoc/2025/sample-2000
```

Cette commande travaille uniquement sur les XML déjà téléchargés. Elle crée un
nouveau dossier horodaté sous `data/processed/sudoc/sample-2000/`. L'option
`--output-dir` permet de choisir un autre dossier vide. Aucune collecte supplémentaire
ni écriture dans DuckDB n'est effectuée.

- `documents.jsonl` : une notice par ligne, titres, dates, langues, pays,
  éditeurs/agents, auteurs, Dewey, localisations et champs bruts.
- `authors.jsonl`, `publishers.jsonl`, `classifications.jsonl` : extractions par
  occurrence avec PPN et provenance. Les agents des zones 214 sont distingués par rôle.
- `subjects.jsonl` : toutes les occurrences des zones 600 à 620 incluses,
  avec indicateurs et sous-zones ordonnées (code, valeur brute et normalisée).
  Ces indexations sont aussi présentes dans `documents.jsonl`, sous `subjects`.
- `summaries.jsonl` : tous les résumés en `330$a`, y compris les occurrences
  répétées, avec texte brut, texte normalisé et provenance ; également présents
  sous `summaries` dans `documents.jsonl`.
- `bnf_links.jsonl` : valeurs des `033$a` contenant `catalogue.bnf`, avec URL,
  valeur brute, PPN et provenance ; à défaut de lien BnF en 033$a, URL calculées
  à partir des huit chiffres après `FRBNF` dans les `035$a` (clé ARK modulo 29).
  `origin` distingue `033a` et `035a`. Ces liens sont aussi dans `documents.jsonl`.
- `locations.jsonl` : toutes les zones 930, y compris les répétitions et les anomalies.
- `holdings.jsonl` : couples PPN/RCR dédoublonnés issus de 930$b, source validée
  par l'utilisateur, avec toutes les occurrences qui les justifient. Également
  présents sous `holdings` dans `documents.jsonl`.
- `localisations_a_verifier.csv` : tableau ouvrable dans un tableur, une ligne par
  notice, pour comparer les RCR de 930$b aux candidats trouvés dans les $5.
- `report.json` : comptages d'extraction et statut de validation des localisations.

La source **930$b est validée par l'utilisateur** pour les RCR. Un RCR apparaît
une seule fois par notice dans `holdings`, même si plusieurs 930 le contiennent.
Le parser ne complète pas 930$b à partir des $5. Les anciennes extractions
conservent leur fichier `holdings_observed.jsonl` ; les nouvelles utilisent
`holdings.jsonl`. Voir [le mapping UNIMARC](docs/unimarc-mapping.md).

Les notices sans aucun `930$b` non vide sont exclues de tous les exports.
Leurs PPN et leur provenance sont listés dans `report.json` sous `exclusions`.
Le rapport distingue les notices lues, conservées et exclues. Les sources XML
et les anciennes versions des extractions restent conservées.

## Tests hors réseau

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
