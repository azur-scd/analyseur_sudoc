# Contrats documentaires des sorties

Ce document regroupe les principaux fichiers de sortie déjà décrits dans le
README et les documents du pipeline. Il ne détaille pas de schéma au-delà de ce
qui est explicitement documenté.

## 1. Campagnes de collecte

| Fichier | Rôle | Identifiant principal | Statut / provenance documentés | Conservation |
|---|---|---|---|---|
| `manifest.json` | Paramètres immuables d'une campagne et date de démarrage. | Dossier de campagne (`data/reference/listrcr/<date>/` ou `data/raw/sudoc/<année>/<campagne>/`). | Conserve les paramètres de collecte, la version du collecteur et, pour SRU, le plafond et la pagination. | Réutilisé lors des reprises ; un changement de paramètres impose une nouvelle campagne. |
| `report.json` | État, comptes, erreurs et couverture d'une campagne. | Même dossier de campagne que le manifeste. | Pour SRU, états `complete`, `limited`, `failed`, `interrupted` documentés ; pour `listrcr`, volumes, couverture des types et erreurs. | Recalculé ou mis à jour au fil de la campagne ; sert de référence de reprise. |

Les campagnes conservent aussi les sources brutes et leur provenance :

- `pages/<préfixe>/<position>.xml` et `pages/<préfixe>/<position>.json` pour SRU ;
- `rejected/` pour les réponses rejetées ;
- TSV `listrcr` brut et JSON IdRef valides pour le référentiel RCR.

## 2. Extractions UNIMARC

| Fichier | Rôle | Identifiant principal | Statut / provenance documentés | Conservation |
|---|---|---|---|---|
| `documents.jsonl` | Une notice par ligne avec les données bibliographiques, Dewey, localisations, résumés, sujets et champs bruts. | `ppn` | La provenance XML est conservée dans les objets exportés ; les enrichissements ultérieurs ajoutent des listes dédiées sans supprimer les données d'entrée. | Les anciennes versions des extractions restent conservées. |
| `holdings.jsonl` | Relations PPN/RCR dédoublonnées issues de `930$b`. | Couple `ppn` / `rcr` | Justification par occurrences de `930$b` et provenance XML ; un RCR n'apparaît qu'une fois par notice. | Les sorties historiques peuvent encore contenir `holdings_observed.jsonl`. |
| `classifications.jsonl` | Occurrences de classifications extraites des notices. | `ppn` avec occurrence de classification | Provenance par champ et distinction des méthodes de classification. | Les valeurs brutes et normalisées sont conservées ensemble. |
| `locations.jsonl` | Export intégral des zones 930, y compris répétitions et anomalies. | `ppn` avec occurrence de zone 930 | Conserve les localisations mêmes sans `930$b` valide. | Sert de trace complète distincte de `holdings.jsonl`. |
| `subjects.jsonl` | Occurrences des zones 600 à 620 avec indicateurs et sous-zones ordonnées. | `ppn` avec occurrence de sujet | Valeurs brutes et normalisées, provenance XML et structure des sous-zones documentées. | Les répétitions sont conservées. |
| `summaries.jsonl` | Occurrences des résumés `330$a`. | `ppn` avec occurrence de résumé | Texte brut, texte normalisé et provenance XML. | Les répétitions restent distinctes. |
| `bnf_links.jsonl` | Liens BnF extraits de `033$a` ou calculés depuis `035$a`. | `ppn` avec occurrence de lien | `origin` distingue `033a` et `035a`, avec valeur brute et provenance. | Les liens restent aussi présents dans `documents.jsonl`. |

Autres sorties documentées de la même famille :

- `authors.jsonl` et `publishers.jsonl` pour les occurrences par agent ;
- `localisations_a_verifier.csv` pour le contrôle manuel des RCR ;
- `report.json` pour les comptages d'extraction, les exclusions et la validation des localisations.

## 3. Audit local

| Fichier | Rôle | Identifiant principal | Statut / provenance documentés | Conservation |
|---|---|---|---|---|
| `rapport.md` | Synthèse lisible des couvertures, distributions et anomalies. | Dossier d'audit | S'appuie sur `documents.jsonl`, son rapport source et leurs empreintes. | Produit local d'analyse, sans modification des notices. |
| `statistics.json` | Statistiques réutilisables et provenance. | Dossier d'audit | Conserve notamment les méthodes de classification et leurs recouvrements documentés. | Réutilisable pour d'autres analyses locales. |
| `distributions.csv`, `anomalies.csv`, `anomalies.jsonl` | Distributions et anomalies détaillées. | `ppn` pour les anomalies | Justification, catégorie, preuves et provenance XML documentées. | Export local ; aucune requête réseau. |

## 4. Enrichissements BnF / IdRef et autorités

| Fichier | Rôle | Identifiant principal | Statut / provenance documentés | Conservation |
|---|---|---|---|---|
| `documents.jsonl` enrichi | Reprend les notices d'entrée avec enrichissements BnF/IdRef ajoutés. | `ppn` | Ajoute des preuves de collecte, dates et empreintes ; les Dewey existantes restent séparées des ajouts. | Ne remplace pas les sources antérieures ; un nouveau dossier d'enrichissement est créé. |
| `libraries.jsonl` | Métadonnées des RCR enrichies pour le lot. | `rcr` | Conserve la provenance `listrcr` et IdRef, ainsi que les empreintes citées dans la documentation. | Réutilisé au chargement DuckDB et à la reprise. |
| `authority-results.jsonl` | Résultat par autorité liée aux `606$a`. | PPN d'autorité résolu | Statut de collecte et preuves par autorité. | Séparé des notices bibliographiques. |
| `authority-classifications.jsonl` | Occurrences de classifications d'autorité reliées aux documents. | Couple logique `ppn` bibliographique / PPN d'autorité | Distingue `scheme`, `code_raw`, `code`, les sous-zones intégrales et le chemin `via_606a`. | Conserve les répétitions et les méthodes séparées. |
| rapport JSON d'enrichissement (nom non figé dans la documentation source) | Rapport de collecte et de traitement du lot d'autorités. | Dossier d'enrichissement | Statuts des liens `606$a`, comptes d'autorités distinctes et résultats de collecte documentés. | Sert aux contrôles et à la reprise. |

## 5. Chargement DuckDB

| Fichier | Rôle | Identifiant principal | Statut / provenance documentés | Conservation |
|---|---|---|---|---|
| `database-report.json` | Rapport JSON du chargement dans DuckDB. | Couple de lot chargé (`corpus_id` ou `run_id`) et dossier d'enrichissement | Le chargement est documenté comme transactionnel, avec contrôles d'empreintes, d'effectifs, d'identité de lot et de relations PPN/RCR. | Écrit dans le dossier d'enrichissement du chargement ; permet de tracer un chargement sans modifier la documentation du lot source. |

## 6. Règles transversales de conservation

- Les valeurs brutes et les valeurs normalisées sont conservées ensemble lorsqu'une normalisation existe.
- Les empreintes, dates de récupération et provenances XML/HTTP restent associées aux collectes et enrichissements lorsqu'elles sont documentées.
- Les reprises réutilisent les dossiers existants ; une modification des paramètres ou de l'identité du lot impose une nouvelle campagne ou un nouvel identifiant.
- Les données locales volumineuses, bases DuckDB et caches de campagne ne sont pas versionnés dans Git.
