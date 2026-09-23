# Analyseur Sudoc
## Spécification des données — V1

Mise à jour du lot expérimental : pour le premier corpus de 2 000 notices de
documents parus en 2025, l'utilisateur a validé la conservation des 1 995
notices retenues, y compris les cas de périmètre litigieux. Le modèle
effectivement chargé, les champs répétables et la provenance BnF/IdRef sont décrits dans
[enrichment-and-database.md](enrichment-and-database.md). Les exclusions générales
ci-dessous décrivent le cadrage initial et ne s'appliquent pas à ce lot validé.

# 1. Sources

## 1.1. Sudoc SRU

Source principale des données bibliographiques et de localisation.

Référence normative : **Guide d'utilisation du service SRU du catalogue Sudoc — Abes**.

Les données sont récupérées en UNIMARC encapsulé dans XML et conservées sous forme brute.

## 1.2. IdRef `listrcr`

URL :

`https://www.idref.fr/services/listrcr`

Format : TSV.

Colonnes particulièrement utiles :

- RCR ;
- LIBELLE ;
- ILN ;
- PPN ;
- VILLE ;
- CDPOSTAL ;
- PAYS ;
- LATITUDE ;
- LONGITUDE.

## 1.3. Notice RCR IdRef

URL :

`https://www.idref.fr/{PPN}.json`

Le type de bibliothèque est extrait de `130$a`.

# 2. Périmètre bibliographique

Une seule année par collecte.

Types inclus :

- TDO `b` : monographies imprimées ;
- TDO `x` : documents multisupports physiques.

Sont exclus notamment :

- revues ;
- thèses ;
- ebooks ;
- images ;
- CD/DVD ;
- autres documents audiovisuels.

# 3. Mapping UNIMARC initial

| Information | Zone(s) |
|---|---|
| PPN | 001 |
| données codées / dates | 100 |
| langue | 101 |
| pays | 102 |
| titre / complément | 200 |
| publication ancienne structuration | 210 |
| publication / production / diffusion | 214 |
| Dewey | 676 |
| auteur principal | 700 |
| coauteurs | 701 |
| responsabilités secondaires | 702 |
| collectivités | 710, 711, 712 |
| données locales/localisations | zones Sudoc pertinentes |

Le mapping devra être confirmé sur les notices réelles.

# 4. Auteurs

Conserver autant que possible :

- ppn ;
- source_field ;
- name ;
- firstname ;
- authority_id ;
- role.

Les zones 700, 701 et 702 restent distinguables.

Même principe pour 710–712.

# 5. Éditeurs

Prendre en compte au minimum :

- `210$c`
- `214$c`

La valeur source est conservée avant normalisation.

# 6. Dewey

Conserver :

- dewey_raw ;
- dewey_normalized ;
- dewey_1 ;
- dewey_2 ;
- dewey_3.

Exemple :

`530.12 → 5 → 53 → 530`

Toutes les occurrences pertinentes sont conservées.

# 7. Référentiel LIBRARY

Champs :

- rcr ;
- label ;
- iln ;
- library_ppn ;
- library_type ;
- city ;
- postal_code ;
- country ;
- latitude ;
- longitude ;
- metadata_retrieved_at.

`rcr` est la clé primaire.

# 8. Normalisation des identifiants

Les valeurs TSV telles que :

`="040702201"`

sont transformées en :

`040702201`

Le RCR reste une **chaîne de caractères** afin de préserver les zéros initiaux.

Même principe pour les PPN.

La chaîne `null` est convertie en vraie valeur nulle.

# 9. Modèle de données

Cette section décrit le **schéma DuckDB implémenté** (tables et vues). Les sections
précédentes décrivent le modèle logique cible et les données sources.

## 9.1 Tables physiques persistées

### CORPUS

Portée : 1 ligne par corpus (`corpus_id`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK |
| year_requested | INTEGER |  |
| source_dir | VARCHAR |  |
| signature | VARCHAR |  |
| loaded_at | TIMESTAMPTZ |  |
| report | JSON |  |

### LIBRARY

Portée : référentiel global partagé entre corpus (clé `rcr`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| rcr | VARCHAR | PK |
| label | VARCHAR |  |
| iln | VARCHAR |  |
| library_ppn | VARCHAR |  |
| library_type | VARCHAR |  |
| city | VARCHAR |  |
| postal_code | VARCHAR |  |
| country | VARCHAR |  |
| latitude | DOUBLE |  |
| longitude | DOUBLE |  |
| metadata_retrieved_at | TIMESTAMPTZ |  |

### CORPUS_LIBRARY

Portée : rattachement d'une bibliothèque à un corpus (`corpus_id`, `rcr`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK → `CORPUS(corpus_id)` |
| rcr | VARCHAR | PK (composite), FK → `LIBRARY(rcr)` |
| metadata | JSON |  |

### DOCUMENT

Portée : 1 ligne par document et par corpus (`corpus_id`, `ppn`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK → `CORPUS(corpus_id)` |
| ppn | VARCHAR | PK (composite) |
| title | VARCHAR |  |
| subtitle | VARCHAR |  |
| publication_year | INTEGER |  |
| scope_status | VARCHAR |  |
| source | JSON |  |
| payload | JSON |  |

### HOLDING

Portée : relation document–bibliothèque par corpus (`corpus_id`, `ppn`, `rcr`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| rcr | VARCHAR | PK (composite), FK → `LIBRARY(rcr)` |
| evidence | JSON |  |

Cette table matérialise le graphe fondamental : `DOCUMENT ↔ LIBRARY` (via `HOLDING`).

### CLASSIFICATION

Portée : occurrences de Dewey par document et par corpus (`corpus_id`, `ppn`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| occurrence | INTEGER | PK (composite) |
| dewey_raw | VARCHAR |  |
| dewey_normalized | VARCHAR |  |
| dewey_1 | VARCHAR |  |
| dewey_2 | VARCHAR |  |
| dewey_3 | VARCHAR |  |
| source | VARCHAR |  |
| annotation | VARCHAR |  |
| payload | JSON |  |

### DOCUMENT_FIELD

Portée : valeurs documentaires répétables par catégorie (`corpus_id`, `ppn`, `category`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| category | VARCHAR | PK (composite) |
| occurrence | INTEGER | PK (composite) |
| payload | JSON |  |

### AUTHORITY_RUN

Portée : 1 exécution d'enrichissement d'autorités (`run_id`) rattachée à un corpus.

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK |
| corpus_id | VARCHAR | FK → `CORPUS(corpus_id)` |
| documents_sha256 | VARCHAR |  |
| loaded_at | TIMESTAMPTZ |  |
| report | JSON |  |

### AUTHORITY_DOCUMENT

Portée : documents enrichis dans une exécution (`run_id`, `ppn`), avec rattachement au corpus/document d'origine.

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK (composite), FK → `AUTHORITY_RUN(run_id)` |
| corpus_id | VARCHAR | FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| payload | JSON |  |

### AUTHORITY_HEADING

Portée : occurrences de liens d'autorité par document et par exécution (`run_id`, `ppn`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| occurrence | INTEGER | PK (composite) |
| authority_ppn | VARCHAR |  |
| status | VARCHAR |  |
| payload | JSON |  |

### AUTHORITY_CLASSIFICATION

Portée : classifications issues des autorités par document et par exécution (`run_id`, `ppn`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| occurrence | INTEGER | PK (composite) |
| requested_authority_ppn | VARCHAR |  |
| resolved_authority_ppn | VARCHAR |  |
| scheme | VARCHAR |  |
| code_raw | VARCHAR |  |
| code | VARCHAR |  |
| source | VARCHAR |  |
| payload | JSON |  |

## 9.2 Vues dérivées (champs documentaires)

`AUTHOR` et `PUBLISHER` ne sont pas des tables physiques : ce sont des vues
`CREATE OR REPLACE VIEW` construites sur `DOCUMENT_FIELD` (filtrage par `category`),
avec projection :

- `corpus_id` (VARCHAR)
- `ppn` (VARCHAR)
- `occurrence` (INTEGER)
- `source_field` (extrait JSON via `json_extract_string(payload, '$.source_field')`)
- `value` (extrait JSON via `json_extract_string(payload, '$.value')`)
- `payload` (JSON)

Le même mécanisme est appliqué aux vues : `SUBJECT`, `SUMMARY`, `LANGUAGE`,
`COUNTRY`, `BNF_LINK`, `LEADER_TYPE`, `CONTENT_TYPE`, `MEDIA_TYPE`,
`NATURE_OF_CONTENT`, `LOCATION`, `CODED_DATE`, `PUBLICATION_STATEMENT`.

## 9.3 Vues dérivées (profil des bibliothèques)

La vue `LIBRARY_PROFILE` est calculée à partir de `HOLDING`, `LIBRARY` et
`CLASSIFICATION` et agrège le nombre de documents et le nombre de documents avec Dewey
par couple (`corpus_id`, `rcr`).

## 9.4 Statut des tables de groupes de bibliothèques

`LIBRARY_GROUP` et `LIBRARY_GROUP_MEMBER` restent un **modèle expérimental** dans cette
spécification et ne sont pas implémentées dans le schéma DuckDB actuel.

## 9.5 Remarque sur les contraintes

Les clés primaires et étrangères ci-dessus correspondent aux déclarations SQL
effectivement présentes. En dehors de ces clés, cette section ne suppose pas de
contraintes supplémentaires (par exemple `NOT NULL`) qui ne seraient pas explicitement
déclarées.

# 10. Normalisation

Principe :

> Ne jamais détruire une valeur source pour produire une valeur normalisée.

Lorsque nécessaire :

- raw_value ;
- normalized_value.

Les transformations doivent être déterministes et documentées.

# 11. Qualité des données

Produire notamment :

- % de notices avec année exploitable ;
- % avec pays ;
- % avec éditeur ;
- % avec auteur ;
- % avec Dewey ;
- nombre moyen de Dewey ;
- nombre de RCR ;
- nombre d'ILN ;
- taux d'enrichissement des RCR ;
- % de RCR avec type ;
- nombre de relations PPN/RCR ;
- nombre moyen de RCR possédants par PPN.

# 12. Traçabilité

Chaque campagne conserve :

- collection_id ;
- year_requested ;
- tdo_requested ;
- physical_only ;
- collection_date ;
- sru_query ;
- sru_number_of_records ;
- records_downloaded ;
- collector_version.

Le référentiel RCR conserve également sa date de récupération.
