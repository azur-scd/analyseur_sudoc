# Analyseur Sudoc
## Spécification des données — V1

**Version :** 1.0  
**Statut :** spécification cible V1 et état d'implémentation partiel  
**Nature :** modèle de données, contrats de stockage et état d'implémentation documentaire de la V1

> **Positionnement du document**
>
> Ce document décrit à la fois le modèle de données cible pour la V1 et l'état
> d'implémentation actuellement observable dans le dépôt.
>
> Il ne constitue donc pas exclusivement un inventaire de l'existant.
>
> Les sections ci-dessous distinguent explicitement :
> 
> - la cible V1 ;
> - les éléments déjà implémentés et vérifiés ;
> - les éléments implémentés mais restant à valider ;
> - les éléments restant à faire ;
> - les éléments hors périmètre V1 ou expérimentaux.

---

# 1. Lecture du document

## 1.1. Portée documentaire

La présente spécification conserve les décisions métier et techniques déjà
retenues pour la V1, tout en explicitant leur statut d'implémentation.

Les sections de modèle cible décrivent donc ce que la V1 doit produire ou
conserver, sans présumer que chaque point soit déjà livré.

## 1.2. État actuel explicitement documenté

Pour le premier corpus de 2 000 notices de documents parus en 2025,
l'utilisateur a validé la conservation des 1 995 notices retenues, y compris
les cas de périmètre litigieux. Le modèle effectivement chargé, les champs
répétables et la provenance BnF/IdRef sont décrits dans
[enrichment-and-database.md](enrichment-and-database.md).

Les exclusions générales ci-dessous décrivent le cadrage cible de la V1 et ne
s'appliquent donc pas automatiquement à ce lot déjà validé.

# 2. Statuts utilisés dans ce document

| Statut | Signification |
|---|---|
| Cible V1 | Règle, structure ou exigence décrivant l'état attendu pour la V1, sans préjuger de son implémentation complète. |
| Implémenté et vérifié | Élément présent dans le dépôt et corroboré par le code, les tests existants ou la documentation d'implémentation. |
| Implémenté mais à valider | Élément déjà présent ou amorcé dans le dépôt, mais dont la confirmation sur données réelles, la formulation exacte ou la couverture complète restent ouvertes. |
| À faire | Élément visé par la V1 mais non implémenté dans l'état actuel du dépôt. |
| Hors périmètre V1 / expérimental | Élément explicitement expérimental, ou exclu du socle stabilisé de la V1. |

# 3. État d'implémentation synthétique

| Domaine | Cible V1 | Statut actuel | Références |
|---|---|---|---|
| Sources Sudoc SRU, `listrcr`, notice RCR IdRef | Constituer les sources de référence bibliographiques et de bibliothèques | Implémenté et vérifié | sections 4.1, 4.7 et 4.9 |
| Corpus expérimental 2025 de 1 995 notices validées | Documenter l'état réellement chargé pour le premier lot | Implémenté et vérifié | section 1.2 |
| Périmètre bibliographique initial (`TDO = b` et `TDO = x`) | Définir le corpus cible d'une collecte annuelle | Implémenté mais à valider | section 4.2 |
| Mapping UNIMARC initial | Extraire les informations bibliographiques et de localisation attendues | Implémenté mais à valider | section 4.3 |
| Auteurs, collectivités et éditeurs | Conserver les informations sources avant agrégation ou normalisation | Implémenté mais à valider | sections 4.4 et 4.5 |
| Dewey bibliographique | Conserver les indices bruts et normalisés | Implémenté et vérifié | sections 4.6 et 4.9 |
| Référentiel `LIBRARY` et normalisation des identifiants | Conserver un référentiel RCR propre, stable et typé | Implémenté et vérifié | sections 4.7 et 4.8 |
| Schéma DuckDB (`CORPUS`, `DOCUMENT`, `HOLDING`, `CLASSIFICATION`, `DOCUMENT_FIELD`, vues dérivées, tables d'autorités) | Stocker le corpus, les holdings, les classifications, les répétitions documentaires et les enrichissements | Implémenté et vérifié | section 4.9 |
| `LIBRARY_PROFILE` | Exposer un profil agrégé de bibliothèques à partir des holdings et Dewey | Implémenté et vérifié | section 4.9.3 |
| `LIBRARY_GROUP` / `LIBRARY_GROUP_MEMBER` | Supporter un groupe local expérimental | Hors périmètre V1 / expérimental | section 4.9.4 |
| Qualité des données | Produire des indicateurs et anomalies de contrôle | Implémenté mais à valider | section 4.11 |
| Traçabilité des campagnes | Conserver paramètres, empreintes et dates de récupération | Implémenté mais à valider | section 4.12 |
| Documentation exhaustive des transformations et harmonisation terminologique de la traçabilité | Stabiliser le contrat documentaire complet de normalisation et de campagne | À faire | sections 4.10, 4.12 et 5.2 |

---

# 4. Modèle cible V1

Les sous-sections suivantes décrivent le modèle cible de la V1. Le statut
actuel de chaque domaine est rappelé en tête de section pour éviter toute
confusion entre cible et existant.

## 4.1. Sources

**Statut :** implémenté et vérifié pour les sources documentées ci-dessous.

### 4.1.1. Sudoc SRU

Source principale des données bibliographiques et de localisation.

Référence normative : **Guide d'utilisation du service SRU du catalogue Sudoc — Abes**.

Les données sont récupérées en UNIMARC encapsulé dans XML et conservées sous
forme brute.

### 4.1.2. IdRef `listrcr`

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

### 4.1.3. Notice RCR IdRef

URL :

`https://www.idref.fr/{PPN}.json`

Le type de bibliothèque est extrait de `130$a`.

## 4.2. Périmètre bibliographique

**Statut :** implémenté mais à valider sur deux points explicitement ouverts :
la validation empirique de `TDO = x` et la validation de la syntaxe CQL exacte.

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

Le caractère physique des documents multisupports devra être vérifié
empiriquement sur les résultats obtenus.

Conceptuellement :

```text
année = paramètre utilisateur
ET
(TDO = b OU TDO = x)
```

La syntaxe CQL exacte doit être validée à partir de la documentation SRU de
l'Abes et de tests sur le service réel.

## 4.3. Mapping UNIMARC initial

**Statut :** implémenté mais à valider sur notices réelles ; la table ci-dessous
reste la cible documentaire de référence.

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

## 4.4. Auteurs

**Statut :** implémenté mais à valider ; le principe de conservation est posé,
mais la formulation « autant que possible » signale encore un point de
validation documentaire et métier.

Conserver autant que possible :

- ppn ;
- source_field ;
- name ;
- firstname ;
- authority_id ;
- role.

Les zones 700, 701 et 702 restent distinguables.

Même principe pour 710–712.

## 4.5. Éditeurs

**Statut :** implémenté mais à valider ; la conservation minimale est définie,
mais la couverture complète sur notices réelles reste à confirmer.

Prendre en compte au minimum :

- `210$c`
- `214$c`

La valeur source est conservée avant normalisation.

## 4.6. Dewey

**Statut :** implémenté et vérifié.

Conserver :

- dewey_raw ;
- dewey_normalized ;
- dewey_1 ;
- dewey_2 ;
- dewey_3.

Exemple :

`530.12 → 5 → 53 → 530`

Toutes les occurrences pertinentes sont conservées.

## 4.7. Référentiel `LIBRARY`

**Statut :** implémenté et vérifié.

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

## 4.8. Normalisation des identifiants

**Statut :** implémenté et vérifié pour les règles décrites ci-dessous.

Les valeurs TSV telles que :

`="040702201"`

sont transformées en :

`040702201`

Le RCR reste une **chaîne de caractères** afin de préserver les zéros initiaux.

Même principe pour les PPN.

La chaîne `null` est convertie en vraie valeur nulle.

## 4.9. Modèle de données DuckDB

**Statut :** tables physiques, vues dérivées et tables d'autorités implémentées
et vérifiées, à l'exception explicite des tables de groupes de bibliothèques.

Cette section décrit le schéma DuckDB effectivement implémenté. Les sections
précédentes décrivent le modèle logique cible et les données sources.

### 4.9.1. Tables physiques persistées

#### CORPUS

Portée : 1 ligne par corpus (`corpus_id`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK |
| year_requested | INTEGER |  |
| source_dir | VARCHAR |  |
| signature | VARCHAR |  |
| loaded_at | TIMESTAMPTZ |  |
| report | JSON |  |

#### LIBRARY

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

#### CORPUS_LIBRARY

Portée : rattachement d'une bibliothèque à un corpus (`corpus_id`, `rcr`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK → `CORPUS(corpus_id)` |
| rcr | VARCHAR | PK (composite), FK → `LIBRARY(rcr)` |
| metadata | JSON |  |

#### DOCUMENT

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

#### HOLDING

Portée : relation document–bibliothèque par corpus (`corpus_id`, `ppn`, `rcr`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| rcr | VARCHAR | PK (composite), FK → `LIBRARY(rcr)` |
| evidence | JSON |  |

Cette table matérialise le graphe fondamental : `DOCUMENT ↔ LIBRARY` (via
`HOLDING`).

#### CLASSIFICATION

Portée : occurrences de Dewey par document et par corpus (`corpus_id`, `ppn`,
`occurrence`).

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

#### DOCUMENT_FIELD

Portée : valeurs documentaires répétables par catégorie (`corpus_id`, `ppn`,
`category`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| corpus_id | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| category | VARCHAR | PK (composite) |
| occurrence | INTEGER | PK (composite) |
| payload | JSON |  |

#### AUTHORITY_RUN

Portée : 1 exécution d'enrichissement d'autorités (`run_id`) rattachée à un
corpus.

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK |
| corpus_id | VARCHAR | FK → `CORPUS(corpus_id)` |
| documents_sha256 | VARCHAR |  |
| loaded_at | TIMESTAMPTZ |  |
| report | JSON |  |

#### AUTHORITY_DOCUMENT

Portée : documents enrichis dans une exécution (`run_id`, `ppn`), avec
rattachement au corpus/document d'origine.

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK (composite), FK → `AUTHORITY_RUN(run_id)` |
| corpus_id | VARCHAR | FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `DOCUMENT(corpus_id, ppn)` |
| payload | JSON |  |

#### AUTHORITY_HEADING

Portée : occurrences de liens d'autorité par document et par exécution
(`run_id`, `ppn`, `occurrence`).

| Colonne | Type DuckDB | Contraintes |
|---|---|---|
| run_id | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| ppn | VARCHAR | PK (composite), FK (composite) → `AUTHORITY_DOCUMENT(run_id, ppn)` |
| occurrence | INTEGER | PK (composite) |
| authority_ppn | VARCHAR |  |
| status | VARCHAR |  |
| payload | JSON |  |

#### AUTHORITY_CLASSIFICATION

Portée : classifications issues des autorités par document et par exécution
(`run_id`, `ppn`, `occurrence`).

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

### 4.9.2. Vues dérivées (champs documentaires)

**Statut :** implémenté et vérifié.

`AUTHOR` et `PUBLISHER` ne sont pas des tables physiques : ce sont des vues
`CREATE OR REPLACE VIEW` construites sur `DOCUMENT_FIELD` (filtrage par
`category`), avec projection :

- `corpus_id` (VARCHAR)
- `ppn` (VARCHAR)
- `occurrence` (INTEGER)
- `source_field` (extrait JSON via `json_extract_string(payload, '$.source_field')`)
- `value` (extrait JSON via `json_extract_string(payload, '$.value')`)
- `payload` (JSON)

Le même mécanisme est appliqué aux vues : `SUBJECT`, `SUMMARY`, `LANGUAGE`,
`COUNTRY`, `BNF_LINK`, `LEADER_TYPE`, `CONTENT_TYPE`, `MEDIA_TYPE`,
`NATURE_OF_CONTENT`, `LOCATION`, `CODED_DATE`, `PUBLICATION_STATEMENT`.

### 4.9.3. Vues dérivées (profil des bibliothèques)

**Statut :** implémenté et vérifié.

La vue `LIBRARY_PROFILE` est calculée à partir de `HOLDING`, `LIBRARY` et
`CLASSIFICATION` et agrège le nombre de documents et le nombre de documents avec
Dewey par couple (`corpus_id`, `rcr`).

### 4.9.4. Statut des tables de groupes de bibliothèques

**Statut :** hors périmètre V1 / expérimental dans le schéma actuel.

`LIBRARY_GROUP` et `LIBRARY_GROUP_MEMBER` restent un **modèle expérimental**
dans cette spécification et ne sont pas implémentées dans le schéma DuckDB
actuel.

### 4.9.5. Remarque sur les contraintes

**Statut :** implémenté et vérifié.

Les clés primaires et étrangères ci-dessus correspondent aux déclarations SQL
explicitement présentes. En dehors de ces clés, cette section ne suppose pas de
contraintes supplémentaires (par exemple `NOT NULL`) qui ne seraient pas
explicitement déclarées.

## 4.10. Normalisation

**Statut :** implémenté mais à valider pour la documentation exhaustive des
transformations.

Principe :

> Ne jamais détruire une valeur source pour produire une valeur normalisée.

Lorsque nécessaire :

- raw_value ;
- normalized_value.

Les transformations doivent être déterministes et documentées.

## 4.11. Qualité des données

**Statut :** implémenté mais à valider ; des audits et exports existent, mais la
liste ci-dessous reste formulée comme un objectif indicatif (« produire
notamment »).

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

## 4.12. Traçabilité

**Statut :** implémenté mais à valider ; la conservation de campagne existe,
mais certains noms de champs et niveaux de granularité restent à harmoniser
entre cible documentaire et implémentation actuelle.

Chaque campagne conserve :

- collection_id ;
- year_requested ;
- tdo_requested ;
- physical_only (implémentation actuelle : `physical_only_requested`) ;
- collection_date ;
- sru_query (implémentation actuelle : `queries` et détail par partition) ;
- sru_number_of_records ;
- records_downloaded ;
- collector_version.

Le référentiel RCR conserve également sa date de récupération.

---

# 5. Points restant à valider ou à implémenter

## 5.1. Éléments implémentés mais restant à valider

Les points suivants restent explicitement ouverts dans la cible V1 ou dans les
formulations existantes du document :

- confirmation du mapping UNIMARC sur des notices réelles ;
- vérification empirique du caractère physique des documents `TDO = x` ;
- validation de la syntaxe CQL exacte sur le service SRU réel ;
- confirmation de la conservation des auteurs et collectivités « autant que
  possible » sur l'ensemble des cas réels ;
- confirmation de la couverture minimale attendue pour les éditeurs ;
- stabilisation de la liste d'indicateurs qualité lorsque le document dit
  « produire notamment ».

## 5.2. Éléments restant à faire

- documenter de manière exhaustive les transformations déterministes évoquées en
  section 4.10 ;
- harmoniser la terminologie documentaire de la traçabilité cible avec les noms
  de champs actuellement produits par le dépôt ;
- maintenir la séparation documentaire entre cette spécification de données et
  les exigences analytiques plus larges décrites notamment dans [PRD.md](PRD.md).

## 5.3. Éléments hors périmètre V1 ou expérimentaux

- `LIBRARY_GROUP` et `LIBRARY_GROUP_MEMBER` restent expérimentales et ne font
  pas partie du schéma DuckDB actuel ;
