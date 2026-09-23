# Analyseur Sudoc
## Spécification fonctionnelle — V1

**Version :** 1.0  
**Statut :** spécification fonctionnelle cible V1 et état d'implémentation partiel  
**Nature :** écrans, filtres, règles métier et indicateurs attendus pour la V1

> **Positionnement du document**
>
> Ce document décrit les exigences fonctionnelles **cibles** de la V1.
>
> Il ne constitue pas une description exhaustive de l'état actuel de
> l'implémentation.
>
> Les écrans, filtres, règles métier et indicateurs décrits ci-dessous expriment
> le besoin fonctionnel V1, sans garantie qu'ils soient déjà tous réalisés.
>
> L'avancement réel doit être suivi séparément dans la documentation
> d'architecture et de livraison.

---

# 0. Cadrage cible / état / à faire

## 0.1. Statuts utilisés

| Statut | Signification |
|---|---|
| Cible fonctionnelle V1 | Exigence attendue pour la V1. |
| Réalisé / vérifié | Élément livré et corroboré par le dépôt ou la documentation d'implémentation. |
| Partiellement réalisé / à valider | Élément amorcé ou disponible en partie, restant à confirmer ou stabiliser. |
| Reste à faire | Élément ciblé pour la V1 mais non livré à ce stade. |
| Hors périmètre V1 / expérimental | Élément explicitement exclu du socle V1 ou conservé à titre d'expérimentation. |

## 0.2. État d'implémentation (synthèse)

| Domaine fonctionnel décrit ici | Cible fonctionnelle V1 | Statut d'implémentation |
|---|---|---|
| Tableau de bord, exploration du corpus et filtres analytiques | Oui | Partiellement réalisé / à valider |
| Écran Bibliothèques et profil Dewey par RCR | Oui | Partiellement réalisé / à valider |
| Écran Comparaison (Jaccard, similarité cosinus, écarts disciplinaires) | Oui | Reste à faire |
| Écran Clustering (RCR ≥ 1 000, caractérisation des clusters) | Oui | Reste à faire |
| Écran Politique documentaire (documents absents, diffusion réseau/pairs) | Oui | Reste à faire |
| Score d'intérêt composite | Non (V1 privilégie des indicateurs séparés) | Hors périmètre V1 / expérimental |
| Règles fonctionnelles de cohérence des analyses | Oui | Partiellement réalisé / à valider |

Références utiles pour l'état actuel : [PRD](PRD.md),
[architecture](architecture.md), [data-spec](data-spec.md).

# 1. Tableau de bord du corpus

Afficher au minimum :

- année analysée ;
- date de collecte ;
- requête SRU utilisée ;
- nombre annoncé par SRU ;
- nombre de notices collectées ;
- nombre de PPN distincts ;
- nombre de RCR ;
- nombre d'ILN ;
- nombre de relations PPN/RCR ;
- taux de couverture Dewey ;
- répartition par pays ;
- principaux éditeurs ;
- principales classes Dewey.

# 2. Filtres globaux

Selon les écrans :

- année ;
- Dewey ;
- langue ;
- pays ;
- éditeur ;
- auteur ;
- RCR ;
- ILN ;
- type de bibliothèque.

Le type et l'ILN sont des variables d'exploration mais ne servent pas à construire les clusters.

# 3. Écran Bibliothèques

Pour chaque RCR :

- RCR ;
- libellé ;
- type ;
- ILN ;
- ville ;
- nombre de documents ;
- éligibilité au clustering ;
- cluster.

Afficher également son profil Dewey.

Permettre de basculer entre :

- effectifs ;
- pourcentages.

# 4. Écran Comparaison

Sélection de deux RCR.

Indicateurs :

- nombre de PPN A ;
- nombre de PPN B ;
- intersection ;
- union ;
- indice de Jaccard ;
- similarité cosinus des profils Dewey ;
- disciplines surreprésentées ;
- disciplines sous-représentées.

## 4.1. Jaccard

`J(A,B) = |A ∩ B| / |A ∪ B|`

Cette mesure décrit la proximité des collections effectivement signalées.

## 4.2. Similarité disciplinaire

Une similarité cosinus est calculable sur les vecteurs Dewey normalisés.

Les deux mesures restent distinctes.

# 5. Écran Clustering

Population :

> RCR ayant au moins 1 000 documents du corpus annuel.

Paramètres analytiques :

- profondeur Dewey ;
- méthode de clustering ;
- nombre de clusters lorsque nécessaire.

Le seuil de 1 000 est une règle métier V1 et non un paramètre utilisateur ordinaire.

Afficher :

- nombre de RCR analysés ;
- nombre de clusters ;
- membres ;
- profils moyens ;
- classes caractéristiques ;
- ILN représentés ;
- types de bibliothèques ;
- RCR représentatifs.

Une projection PCA ou UMAP pourra être utilisée pour la visualisation sans nécessairement constituer l'espace utilisé pour le clustering.

# 6. Écran Politique documentaire

Sélection :

- RCR cible ;
- éventuellement groupe de RCR si l'expérimentation est conservée.

Filtres :

- Dewey ;
- langue ;
- pays ;
- éditeur ;
- auteur ;
- nombre minimal de possédants ;
- proportion minimale de pairs possédants ;
- possession locale.

Colonnes possibles :

- PPN ;
- titre ;
- auteur ;
- éditeur ;
- année ;
- pays ;
- Dewey ;
- nombre de RCR possédants ;
- nombre de pairs possédants ;
- pourcentage des pairs possédants ;
- possession locale.

# 7. Score d'intérêt

La V1 privilégie des indicateurs séparés plutôt qu'un score composite opaque.

Dimensions envisageables :

- diffusion dans le Sudoc ;
- diffusion chez les pairs ;
- adéquation disciplinaire ;
- rareté géographique ;
- récence.

Un score composite pourra être expérimenté ultérieurement, avec formule transparente.

# 8. Règles fonctionnelles

1. Une donnée absente reste absente.
2. Une notice sans Dewey ne doit pas être classée en Dewey 000.
3. Tout agrégat doit permettre autant que possible de retrouver les PPN qui le composent.
4. Les effectifs utilisés pour calculer les pourcentages doivent rester accessibles.
5. Les paramètres ayant produit une analyse doivent être enregistrés.
6. Un RCR ayant moins de 1 000 documents reste consultable mais ne participe pas au clustering.
7. Un RCR ayant au moins 1 000 documents participe au clustering sans exclusion supplémentaire.
8. Un RCR présent dans le corpus mais absent du référentiel descriptif n'est jamais supprimé.
9. Le type de bibliothèque et l'ILN servent à interpréter les clusters mais ne sont pas utilisés pour les construire.
