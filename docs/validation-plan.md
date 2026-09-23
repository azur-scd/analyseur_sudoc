# Analyseur Sudoc
## Plan de validation et de tests — V1

Ce plan distingue :

1. la couverture actuellement assurée par les fichiers de tests présents dans le dépôt ;
2. les validations opérationnelles déjà documentées pour le pipeline livré ;
3. les validations analytiques prévues pour la cible V1, non présentées comme déjà implémentées.

# 1. Couverture automatisée actuellement présente

Les tests hors réseau s'exécutent avec la commande actuellement documentée pour
**PowerShell sous Windows** :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les fichiers actuellement présents couvrent les zones suivantes :

- `tests/test_sudoc.py` : collecte Sudoc SRU et règles de campagne ;
- `tests/test_unimarc.py` : parsing UNIMARC et exports documentaires ;
- `tests/test_quality.py` : audit local des extractions ;
- `tests/test_enrichment.py` : enrichissement BnF / IdRef du corpus ;
- `tests/test_authority_enrichment.py` : enrichissement des autorités liées aux `606$a` ;
- `tests/test_database.py` : chargement et accès DuckDB ;
- `tests/test_libraries.py` : référentiel RCR, métadonnées et types de bibliothèques.

Chaque bug significatif rencontré sur ces étapes doit devenir un test de
non-régression dans la famille concernée.

# 2. Validations documentées pour le pipeline livré

## 2.1. Collecte SRU

Pour chaque campagne, comparer :

- `numberOfRecords` annoncé ;
- nombre téléchargé ;
- nombre parsé ;
- nombre chargé ;
- nombre de PPN distincts.

Tout écart doit être signalé. La pagination doit être testée indépendamment.

## 2.2. Fixtures et cas UNIMARC

Constituer progressivement des fixtures couvrant notamment :

- notice avec 210 ;
- notice avec 214 ;
- plusieurs éditeurs ;
- 700 ;
- 701 ;
- 702 ;
- 710 ;
- plusieurs 676 ;
- absence de Dewey ;
- plusieurs localisations ;
- cas atypiques découverts.

## 2.3. Référentiel RCR et types de bibliothèques

Tester :

- nettoyage `="040702201"` vers `040702201` ;
- conservation des zéros initiaux ;
- PPN ;
- `null` ;
- latitude ;
- longitude ;
- RCR sans coordonnées ;
- RCR sans PPN ;
- jointure sur RCR.

Pour une notice IdRef contenant :

`130$a = Bibliothèque universitaire`

résultat attendu :

`library_type = Bibliothèque universitaire`

Tester aussi :

- 130 absent ;
- 130 sans `$a` ;
- réponse JSON invalide ;
- erreur HTTP ;
- plusieurs sous-zones.

## 2.4. Audit qualité et normalisation

Les validations actuellement documentées pour l'audit portent notamment sur :

- couverture pays, langues, dates, Dewey, indexations et résumés ;
- distinction entre présence d'une classification et caractère exploitable ;
- comptage séparé des méthodes Sudoc, BnF et IdRef ;
- conservation des valeurs brutes, des provenances et des empreintes ;
- absence de modification automatique des notices auditées.

# 3. Validations analytiques prévues pour la cible V1

Les sections suivantes décrivent des validations prospectives de la phase
analytique. Elles ne doivent pas être interprétées comme une couverture déjà
implémentée dans le dépôt actuel.

## 3.1. Validation des volumes RCR

Pour chaque année produire :

- RCR avec ≥ 1 document ;
- RCR avec ≥ 100 documents ;
- RCR avec ≥ 500 documents ;
- RCR avec ≥ 1 000 documents ;
- RCR avec ≥ 2 000 documents ;
- RCR avec ≥ 5 000 documents.

La population du clustering doit être exactement :

`{RCR | nombre_documents_corpus >= 1000}`

## 3.2. Validation Dewey pour l'analyse

Mesurer :

- taux de couverture ;
- valeurs non interprétables ;
- valeurs multiples ;
- distribution.

Effectuer un contrôle manuel sur un échantillon de notices dans le Sudoc.
Le clustering ne doit pas être interprété avant cette validation.

## 3.3. Validation Jaccard

Exemple :

```text
A = {1,2,3,4}
B = {3,4,5,6}
```

Résultat attendu :

```text
intersection = 2
union = 6
Jaccard = 2/6
```

Les tests mathématiques doivent être indépendants des données réelles.

## 3.4. Validation des profils Dewey

Exemple artificiel :

```text
RCR A
500 = 50
600 = 50

RCR B
500 = 10
600 = 90
```

Attendu :

```text
A → 50 %, 50 %
B → 10 %, 90 %
```

Les valeurs absolues et relatives restent accessibles.

## 3.5. Validation du clustering

### Statistique

Étudier selon les méthodes :

- silhouette score ;
- inertie ;
- stabilité ;
- comparaison de plusieurs nombres de clusters.

### Sensibilité

Tester plusieurs :

- profondeurs Dewey ;
- méthodes ;
- nombres de clusters.

Le seuil RCR reste fixé à 1 000 dans la V1.

### Métier

Examiner manuellement plusieurs bibliothèques connues.

Questions :

- les profils scientifiques se rapprochent-ils ?
- les bibliothèques juridiques apparaissent-elles proches ?
- les bibliothèques spécialisées ressortent-elles ?
- les clusters sont-ils dominés artificiellement par la taille ?
- les classes annoncées comme caractéristiques sont-elles réellement surreprésentées ?

Un bon score statistique ne suffit pas.

## 3.6. Validation externe par le type et l'ILN

Pour chaque cluster :

- nombre de RCR ;
- nombre d'ILN ;
- répartition des types.

On examinera notamment si les clusters :

- traversent plusieurs établissements ;
- reproduisent essentiellement les ILN ;
- correspondent spontanément à certaines typologies de bibliothèques.

## 3.7. Validation des pairs

Pour un RCR :

1. calculer les RCR les plus proches ;
2. examiner leurs profils Dewey ;
3. examiner leurs documents communs ;
4. contrôler manuellement un échantillon.

L'application devra toujours indiquer la métrique utilisée.

## 3.8. Validation de la politique documentaire

Pour un échantillon de documents remontés :

- vérifier l'absence dans le RCR cible ;
- vérifier le nombre de possédants ;
- vérifier la présence chez les pairs ;
- vérifier Dewey ;
- vérifier les données bibliographiques ;
- évaluer manuellement la pertinence apparente.

Les résultats sont présentés comme :

> **documents potentiellement intéressants à examiner**

et non comme :

> **documents à acheter**.
