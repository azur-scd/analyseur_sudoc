# Analyseur Sudoc
## Spécification des données — V1

Mise à jour du lot expérimental : l'utilisateur a validé la conservation des
1 995 notices, y compris les cas de périmètre litigieux. Le modèle effectivement
chargé, les champs répétables et la provenance BnF/IdRef sont décrits dans
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

## DOCUMENT

- ppn
- title
- subtitle
- publication_year
- language
- country

## PUBLISHER

- ppn
- publisher
- source_field

## AUTHOR

- ppn
- source_field
- name
- firstname
- authority_id
- role

## CLASSIFICATION

- ppn
- dewey_raw
- dewey_normalized
- dewey_1
- dewey_2
- dewey_3

## LIBRARY

- rcr
- label
- iln
- library_ppn
- library_type
- city
- postal_code
- country
- latitude
- longitude
- metadata_retrieved_at

## HOLDING

- ppn
- rcr

Cette table matérialise le graphe fondamental :

`DOCUMENT ↔ LIBRARY`

## LIBRARY_GROUP — expérimental

- group_id
- label

## LIBRARY_GROUP_MEMBER — expérimental

- group_id
- rcr

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
