# Sudoc Explorer
## PRD — Document des Exigences Produit

**Version :** 1.0  
**Statut :** validé pour la V1  
**Nature :** application locale d'exploration et d'analyse des collections signalées dans le Sudoc

---

# 1. Vision

Sudoc Explorer est une application locale permettant d'explorer les données bibliographiques et de localisation du Sudoc afin de mieux comprendre les profils documentaires des bibliothèques du réseau et d'aider à l'analyse des collections et de la politique documentaire.

Le projet comporte deux axes complémentaires.

## 1.1. Axe A — Observatoire des bibliothèques Sudoc

L'application doit permettre :

1. de construire des profils documentaires des bibliothèques du réseau ;
2. de comparer ces profils ;
3. d'identifier les bibliothèques présentant des collections similaires ;
4. de regrouper les bibliothèques en clusters ;
5. de caractériser ces clusters ;
6. de positionner une bibliothèque donnée par rapport au réseau.

L'unité fondamentale d'analyse est le **RCR**.

## 1.2. Axe B — Analyse de politique documentaire

Pour une année de publication donnée, l'application doit permettre :

1. d'identifier les documents correspondant au périmètre documentaire retenu ;
2. de déterminer lesquels sont possédés ou non par une bibliothèque donnée ;
3. d'observer leur diffusion dans le réseau Sudoc ;
4. d'observer plus particulièrement leur présence dans les bibliothèques présentant un profil documentaire similaire ;
5. de faire émerger des documents potentiellement intéressants à examiner.

Un groupe configurable de RCR pourra éventuellement être utilisé dans cet axe pour considérer plusieurs bibliothèques locales comme un ensemble documentaire.

La pertinence de cette agrégation devra être évaluée expérimentalement.

Sudoc Explorer n'a pas vocation à décider automatiquement des acquisitions.

Il constitue un **outil d'exploration et d'aide à la décision professionnelle**.

---

# 2. Principes structurants

## 2.1. PPN

Le PPN Sudoc constitue l'identifiant bibliographique principal des documents.

## 2.2. RCR

Le RCR constitue l'identifiant fondamental d'une bibliothèque.

Il constitue également l'unité exclusive utilisée pour le clustering.

## 2.3. ILN

L'ILN représente un regroupement institutionnel de RCR.

Il constitue une information descriptive importante mais ne remplace jamais le RCR comme unité de clustering.

Plusieurs RCR appartenant au même ILN peuvent appartenir à des clusters différents.

## 2.4. Possession et acquisition

Une localisation Sudoc permet d'établir qu'une bibliothèque **signale posséder** un document.

Elle ne permet pas nécessairement de connaître :

- son mode d'acquisition ;
- sa date d'acquisition ;
- son prix ;
- son fournisseur.

L'année de publication ne doit jamais être assimilée à l'année d'acquisition.

Les termes privilégiés dans l'application sont donc :

- bibliothèque possédante ;
- document possédé ;
- localisation ;
- document absent de la collection signalée.

## 2.5. Une année à la fois

Chaque corpus porte sur une seule année de publication.

L'année constitue un paramètre de collecte.

La première expérimentation portera sur **2025**.

Le même processus doit ensuite fonctionner sans modification du code pour les années précédentes.

Une collecte simultanée de plusieurs années n'est pas prévue.

## 2.6. Explicabilité

Les résultats doivent autant que possible être explicables.

L'utilisateur doit pouvoir comprendre :

- pourquoi deux RCR sont considérés comme proches ;
- pourquoi un RCR appartient à un cluster ;
- quelles disciplines caractérisent un cluster ;
- pourquoi un document ressort dans l'analyse de politique documentaire.

## 2.7. Reproductibilité

Les données sources doivent être conservées.

Une modification du parser ou des algorithmes doit pouvoir être rejouée sans réinterroger systématiquement les services de l'Abes.

---

# 3. Périmètre documentaire

## 3.1. Documents inclus

Le corpus comprend uniquement :

- les **monographies imprimées** ;
- les **documents multimédias multisupports sur support physique**.

Pour la recherche Sudoc, le périmètre initial repose notamment sur :

- `TDO = b`
- `TDO = x`

Le caractère physique des documents multisupports devra être vérifié empiriquement sur les résultats obtenus.

## 3.2. Documents exclus

Sont notamment exclus :

- périodiques et revues ;
- thèses ;
- ebooks et autres ressources électroniques ;
- images ;
- documents sonores ;
- CD ;
- DVD ;
- documents audiovisuels ;
- autres types documentaires hors périmètre.

## 3.3. Année de publication

L'année est paramétrable lors de chaque collecte.

Conceptuellement :

```text
année = paramètre utilisateur
ET
(TDO = b OU TDO = x)
```

La syntaxe CQL exacte doit être validée à partir de la documentation SRU de l'Abes et de tests sur le service réel.

---

# 4. Sources de données

## 4.1. Sudoc SRU

Le catalogue Sudoc via SRU constitue la source principale des données bibliographiques et de localisation.

Le projet prend comme référence normative le **Guide d'utilisation du service SRU du catalogue Sudoc — Abes**.

Les réponses sont récupérées en UNIMARC encapsulé dans XML.

Le XML brut est conservé.

## 4.2. Référentiel national RCR — `listrcr`

Le service IdRef/Abes :

`https://www.idref.fr/services/listrcr`

fournit un référentiel global des RCR sous forme TSV.

Les données particulièrement utiles pour la V1 sont :

- RCR ;
- LIBELLE ;
- ILN ;
- PPN ;
- VILLE ;
- CDPOSTAL ;
- PAYS ;
- LATITUDE ;
- LONGITUDE.

Le fichier source est conservé avec sa date de récupération.

## 4.3. Notices RCR IdRef

Le PPN fourni dans `listrcr` permet d'interroger la notice descriptive du RCR :

`https://www.idref.fr/{PPN}.json`

Le type de bibliothèque est récupéré dans la zone UNIMARC JSON `130$a`.

---

# 5. Objectifs produit

## O1 — Constituer un corpus annuel

Récupérer pour une année choisie tous les documents correspondant au périmètre documentaire.

## O2 — Construire le référentiel des bibliothèques

Disposer pour chaque RCR des informations descriptives essentielles :

- RCR ;
- libellé ;
- ILN ;
- PPN de la notice RCR ;
- type de bibliothèque ;
- ville ;
- code postal ;
- pays ;
- latitude ;
- longitude.

## O3 — Construire des profils documentaires

Pour chaque RCR, construire un profil fondé principalement sur la répartition des documents dans les classes Dewey.

## O4 — Sélectionner la population du clustering

Un RCR participe au clustering s'il possède au minimum **1 000 documents appartenant au corpus annuel étudié**.

Tous les RCR atteignant ce seuil sont conservés.

Aucune autre exclusion n'est effectuée selon le type de bibliothèque, l'ILN, la localisation géographique, la spécialisation ou l'établissement.

## O5 — Mesurer la proximité entre RCR

Deux formes de proximité doivent au minimum être distinguées :

- proximité disciplinaire, fondée sur les profils Dewey ;
- proximité des collections, fondée sur les ensembles de PPN possédés.

## O6 — Clusteriser les RCR

Le clustering porte exclusivement sur les RCR éligibles.

Un établissement possédant plusieurs RCR peut donc avoir ses différentes bibliothèques réparties dans différents clusters.

## O7 — Caractériser les clusters

Pour chaque cluster, déterminer notamment :

- nombre de RCR ;
- nombre d'ILN ;
- membres ;
- profil Dewey moyen ;
- classes Dewey surreprésentées ;
- classes sous-représentées ;
- RCR représentatifs ;
- types de bibliothèques représentés ;
- distances ou similarités internes.

## O8 — Positionner une bibliothèque

Pour un RCR donné :

- profil documentaire ;
- éligibilité au clustering ;
- cluster éventuel ;
- RCR les plus proches ;
- disciplines caractéristiques ;
- documents communs avec ses pairs.

## O9 — Explorer les documents absents

Pour un RCR cible :

- identifier les documents du corpus qu'il ne possède pas ;
- mesurer leur diffusion dans le réseau ;
- mesurer leur diffusion parmi les RCR similaires ;
- permettre leur exploration bibliographique.

## O10 — Expérimenter éventuellement un groupe local

Dans le seul module de politique documentaire, plusieurs RCR pourront éventuellement être considérés comme un ensemble.

Cette fonctionnalité est expérimentale et ne participe jamais au clustering.

---

# 6. Utilisateurs

L'utilisateur principal est un professionnel de bibliothèque travaillant sur :

- collections ;
- politique documentaire ;
- acquisitions ;
- données bibliographiques ;
- pilotage d'un réseau documentaire.

La V1 est une application locale destinée aux professionnels.

---

# 7. Cas d'usage

- Constituer le corpus d'une année.
- Explorer une année éditoriale.
- Examiner une bibliothèque.
- Comparer deux RCR.
- Trouver les bibliothèques similaires.
- Clusteriser le réseau.
- Explorer un cluster.
- Examiner un document.
- Explorer les documents absents.
- Explorer des opportunités documentaires.
- Tester éventuellement une analyse agrégée locale.

---

# 8. Hors périmètre V1

Sont exclus :

- clustering d'ILN ;
- clustering de groupes de RCR ;
- fusion des RCR d'un établissement avant clustering ;
- analyse simultanée de plusieurs années ;
- périodiques ;
- thèses ;
- ebooks ;
- images ;
- CD/DVD ;
- autres documents audiovisuels ;
- analyse des prêts ;
- commandes automatiques ;
- écriture dans Koha ;
- écriture dans le Sudoc ;
- données financières d'acquisition ;
- date réelle d'acquisition des autres établissements ;
- recommandation automatique par IA ;
- embeddings sémantiques ;
- interface publique.

---

# 9. Critères de réussite V1

La V1 est considérée comme réussie si elle permet :

1. de constituer de manière reproductible un corpus annuel ;
2. de contrôler son exhaustivité ;
3. de récupérer et conserver le référentiel RCR ;
4. d'obtenir le libellé, l'ILN et le type des bibliothèques ;
5. d'extraire correctement les principales informations UNIMARC ;
6. d'identifier les RCR possédant chaque PPN ;
7. de mesurer la couverture Dewey ;
8. de construire les profils Dewey par RCR ;
9. de sélectionner exactement les RCR ≥ 1 000 documents ;
10. de comparer deux RCR ;
11. de calculer leurs similarités ;
12. de produire des clusters statistiquement évaluables ;
13. de produire des clusters professionnellement interprétables ;
14. de caractériser chaque cluster ;
15. d'identifier les bibliothèques les plus proches d'un RCR ;
16. d'identifier les documents absents de ce RCR ;
17. d'évaluer leur diffusion dans le réseau et chez les pairs ;
18. de remonter de tout résultat analytique aux PPN concernés ;
19. de conserver les données sources et paramètres permettant de reproduire les résultats.

---

# 10. Décisions figées pour la V1

| Question | Décision |
|---|---|
| Première année | 2025 |
| Année | paramétrable |
| Années par collecte | 1 |
| Livres imprimés | inclus |
| Multisupports physiques | inclus |
| Ebooks | exclus |
| Revues | exclues |
| Thèses | exclues |
| Images | exclues |
| CD/DVD | exclus |
| Format bibliographique | UNIMARC |
| Source bibliographique | SRU Sudoc |
| Guide SRU Abes | référence normative |
| Conservation XML brut | oui |
| Identifiant bibliothèque | RCR |
| Référentiel RCR | IdRef `listrcr` |
| Nom de bibliothèque | LIBELLE |
| Regroupement institutionnel | ILN |
| Type de bibliothèque | `130$a` notice RCR IdRef |
| Unité de clustering | RCR |
| Seuil de clustering | ≥ 1 000 documents du corpus annuel |
| Exclusion supplémentaire | aucune |
| Type utilisé pour construire les clusters | non |
| ILN utilisé pour construire les clusters | non |
| Type/ILN utilisés pour interprétation | oui |
| Fusion des RCR d'un établissement | non |
| Groupe de RCR dans clustering | non |
| Groupe de RCR en politique documentaire | expérimental |
| Base locale | DuckDB |
| Langage | Python |
| Interface prototype | Streamlit |
| Décision automatique d'achat | non |

---

# 11. Principe directeur

Sudoc Explorer suit la chaîne :

**données sources conservées → transformations documentées → contrôles qualité → profils documentaires par RCR → analyses statistiques explicables → interprétation professionnelle.**

Le clustering doit répondre à la question :

> **Quelles bibliothèques du réseau Sudoc présentent des profils documentaires similaires ?**

Le module de politique documentaire doit répondre à une question différente :

> **Quels documents absents d'une collection méritent d'être examinés au regard de leur présence dans le réseau et, surtout, dans des bibliothèques présentant un profil documentaire comparable ?**
