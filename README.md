# Sudoc Explorer

Application locale d'exploration et d'analyse des collections signalées dans le Sudoc.

## Documentation

- [PRD](docs/PRD.md)
- [Spécification fonctionnelle](docs/functional-spec.md)
- [Spécification des données](docs/data-spec.md)
- [Architecture technique](docs/architecture.md)
- [Plan de validation et de tests](docs/validation-plan.md)
- [Mapping UNIMARC](docs/unimarc-mapping.md)

## Principes V1

- une année de publication à la fois ;
- première année : 2025 ;
- monographies imprimées et documents multisupports physiques ;
- clustering au niveau RCR ;
- seuil d'éligibilité au clustering : 1 000 documents du corpus annuel ;
- référentiel RCR via IdRef `listrcr` ;
- type de bibliothèque via `130$a` de la notice RCR IdRef ;
- stockage analytique local dans DuckDB ;
- prototype en Python et Streamlit.

## Statut

V0.1 : collecte du référentiel RCR, enrichissement IdRef et table `LIBRARY` disponibles.
V0.2 : collecte annuelle Sudoc SRU, reprise des pages XML et rapport d'exhaustivité disponibles.

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

## Tests hors réseau

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
