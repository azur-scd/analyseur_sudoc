# Sudoc Explorer
## Mapping UNIMARC — V1

Ce document centralise les choix de mapping UNIMARC utilisés par le projet.

> Important : les règles ci-dessous constituent le mapping initial. Elles devront être vérifiées et complétées à partir des notices Sudoc réellement rencontrées.

# 1. Documents bibliographiques

| Information | Zone(s) UNIMARC | Remarques |
|---|---|---|
| PPN | 001 | identifiant principal |
| données codées / dates | 100 | à confirmer selon cas réels |
| langue | 101 | une ou plusieurs valeurs possibles |
| pays | 102 | pays de publication/production |
| titre / complément | 200 | titre et sous-titre |
| publication ancienne structuration | 210 | notamment `$a`, `$c`, `$d` |
| publication / production / diffusion | 214 | notamment `$a`, `$c`, `$d` |
| Dewey | 676 | plusieurs occurrences possibles |
| auteur principal personne | 700 | conserver rôle |
| coauteurs personnes | 701 | conserver rôle |
| responsabilités secondaires | 702 | conserver rôle |
| collectivités | 710, 711, 712 | conserver type et rôle |
| localisations Sudoc | zones pertinentes | mapping à confirmer sur réponse SRU |

# 2. Éditeurs

Prendre en compte au minimum :

- `210$c`
- `214$c`

Toujours conserver :

- valeur brute ;
- zone source ;
- valeur normalisée éventuelle.

# 3. Auteurs

Pour les zones 700, 701, 702, 710, 711 et 712, conserver autant que possible :

- zone source ;
- nom ;
- prénom ;
- identifiant d'autorité ;
- code de fonction / rôle.

Ne pas concaténer définitivement les responsabilités dans une simple chaîne.

# 4. Dewey

Conserver :

- valeur brute ;
- valeur normalisée ;
- niveau 1 ;
- niveau 2 ;
- niveau 3.

Exemple :

`530.12 → 5 → 53 → 530`

Ne jamais transformer une absence de Dewey en `000`.

# 5. Notice RCR IdRef

Le type de bibliothèque est extrait de :

- zone `130`
- sous-zone `a`

Exemple :

```json
{
  "tag": 130,
  "subfield": [
    {
      "code": "a",
      "content": "Bibliothèque universitaire"
    }
  ]
}
```

Résultat :

`library_type = "Bibliothèque universitaire"`

# 6. Principes de parsing

Le parser ne doit pas supposer :

- qu'une zone est toujours présente ;
- qu'une zone n'existe qu'une seule fois ;
- que l'ordre des zones est fixe ;
- que les sous-zones arrivent toujours dans le même ordre.

Chaque anomalie ou cas nouveau rencontré dans les données réelles doit être :

1. documenté ici ;
2. ajouté à une fixture de test si pertinent ;
3. couvert par un test de non-régression.
