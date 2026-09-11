# Sudoc Explorer
## Plan de validation et de tests — V1

# 1. Principe

Les tests couvrent :

1. données sources ;
2. collecte ;
3. parsing ;
4. stockage ;
5. calculs ;
6. clustering ;
7. interprétation métier.

# 2. Tests de collecte SRU

Pour chaque campagne, comparer :

- `numberOfRecords` annoncé ;
- nombre téléchargé ;
- nombre parsé ;
- nombre chargé ;
- nombre de PPN distincts.

Tout écart doit être signalé.

La pagination doit être testée indépendamment.

# 3. Fixtures UNIMARC

Constituer progressivement des fixtures :

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

Chaque bug significatif doit devenir un test de non-régression.

# 4. Tests du référentiel RCR

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

# 5. Tests du type de bibliothèque

Pour une notice IdRef contenant :

`130$a = Bibliothèque universitaire`

résultat attendu :

`library_type = Bibliothèque universitaire`

Tester :

- 130 absent ;
- 130 sans `$a` ;
- réponse JSON invalide ;
- erreur HTTP ;
- plusieurs sous-zones.

# 6. Validation des volumes RCR

Pour chaque année produire :

- RCR avec ≥ 1 document ;
- RCR avec ≥ 100 documents ;
- RCR avec ≥ 500 documents ;
- RCR avec ≥ 1 000 documents ;
- RCR avec ≥ 2 000 documents ;
- RCR avec ≥ 5 000 documents.

La population du clustering doit être exactement :

`{RCR | nombre_documents_corpus >= 1000}`

# 7. Validation Dewey

Mesurer :

- taux de couverture ;
- valeurs non interprétables ;
- valeurs multiples ;
- distribution.

Effectuer un contrôle manuel sur un échantillon de notices dans le Sudoc.

Le clustering ne doit pas être interprété avant cette validation.

# 8. Validation Jaccard

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

# 9. Validation des profils Dewey

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

# 10. Validation du clustering

## 10.1. Statistique

Étudier selon les méthodes :

- silhouette score ;
- inertie ;
- stabilité ;
- comparaison de plusieurs nombres de clusters.

## 10.2. Sensibilité

Tester plusieurs :

- profondeurs Dewey ;
- méthodes ;
- nombres de clusters.

Le seuil RCR reste fixé à 1 000 dans la V1.

## 10.3. Métier

Examiner manuellement plusieurs bibliothèques connues.

Questions :

- les profils scientifiques se rapprochent-ils ?
- les bibliothèques juridiques apparaissent-elles proches ?
- les bibliothèques spécialisées ressortent-elles ?
- les clusters sont-ils dominés artificiellement par la taille ?
- les classes annoncées comme caractéristiques sont-elles réellement surreprésentées ?

Un bon score statistique ne suffit pas.

# 11. Validation externe par le type et l'ILN

Pour chaque cluster :

- nombre de RCR ;
- nombre d'ILN ;
- répartition des types.

On examinera notamment si les clusters :

- traversent plusieurs établissements ;
- reproduisent essentiellement les ILN ;
- correspondent spontanément à certaines typologies de bibliothèques.

# 12. Validation des pairs

Pour un RCR :

1. calculer les RCR les plus proches ;
2. examiner leurs profils Dewey ;
3. examiner leurs documents communs ;
4. contrôler manuellement un échantillon.

L'application doit toujours indiquer la métrique utilisée.

# 13. Validation de la politique documentaire

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
