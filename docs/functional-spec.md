# Sudoc Explorer
## Spécification fonctionnelle — V1

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
