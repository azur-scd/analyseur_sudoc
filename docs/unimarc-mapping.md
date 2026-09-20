# Sudoc Explorer
## Mapping UNIMARC — V1

Ce document centralise les choix de mapping UNIMARC utilisés par le projet.

> Important : les règles ci-dessous constituent le mapping initial. Elles devront être vérifiées et complétées à partir des notices Sudoc réellement rencontrées.

## Extraction implémentée (V0.3.6, étape 1)

Le script `scripts/03_parse_unimarc.py` lit uniquement les pages validées du
rapport de collecte et vérifie leurs empreintes SHA-256. Il produit des JSONL
dans un nouveau dossier, sans modifier les XML sources ni le rapport de collecte.
La position de notice SRU, le fichier XML et son empreinte accompagnent chaque
export. Chaque champ conserve son indice dans la notice et son numéro d'occurrence
par zone (indices commençant à 1), ses indicateurs et toutes ses sous-zones dans
l'ordre original. Le rapport d'extraction est distinct du rapport de collecte.

### Règles de transformation

- Les textes normalisés retirent les caractères de non-tri U+0098/U+009C,
  normalisent Unicode en NFC et les espaces. Les valeurs `raw` restent intactes.
- Toutes les 200 et leurs répétitions sont conservées, y compris $d, $h et $i.
  `title` et `subtitle` ne sont que des champs d'affichage tirés de la première
  200 ayant un $a non vide ; les autres écritures restent dans `titles` et
  les liens $6/$7 dans `source_fields`.
- Les 100$a exportées par le SRU sont positionnelles : caractère 8 pour le type
  de date, caractères 9–12 pour la première année, 13–16 pour la seconde
  (positions commençant à 0). Les deux dates brutes sont conservées. Une année
  de publication unique n'est dérivée que pour un seul 100$a de type d/e/h/i/j/k
  avec une première année numérique exploitable. Les dates incertaines, les
  intervalles et les champs courts restent sans année synthétique.
  Les dates textuelles de 210/214$d sont conservées séparément. L'année de la
  requête SRU n'est jamais utilisée comme valeur de remplacement.
- Les langues du document viennent de tous les 101$a, les pays de tous les
  102$a ; les autres sous-zones restent disponibles dans `source_fields`.
- Chaque 210/214$c donne une ligne d'agent, avec sa zone et ses indicateurs.
  `statement_type` distingue publication, production, distribution, fabrication,
  copyright et type non précisé. Le champ `publisher` est nul pour les agents
  de 214 dont l'indicateur 2 n'est pas 0 ; leur nom reste dans `value`/`raw`.
  Le 210$c ancien ne permet pas toujours de séparer éditeur et distributeur :
  il porte `legacy_publication_distribution`.
- Les 700/701/702 et 710/711/712 sont extraites par occurrence. $3, tous les $4,
  les noms et qualificatifs restent séparés. Pour les collectivités, $b est
  une subdivision et ne devient pas un prénom.
- Chaque 676$a est conservé. Une notation composée de trois chiffres suivis
  éventuellement de décimales est normalisée ; les barres de segmentation sont
  retirées (ex. `746.9/7/0996` → `746.970996`). Les autres notations restent
  brutes avec niveaux nuls. Une absence de Dewey ne devient jamais `000`.

### Liens BnF en 033$a et repli sur 035$a

Chaque sous-zone `a` de chaque zone `033` est conservée dans `bnf_links` si
sa valeur contient `catalogue.bnf` (comparaison insensible à la casse).
Le filtre est une recherche de sous-chaîne, sans validation de domaine ni
consultation de l'URL. Les autres 033 restent dans `source_fields` uniquement.

Chaque occurrence contient `url` (valeur source avec seulement les espaces
extérieurs retirés), `raw` (valeur intégrale), `source_field`, `field_index`,
`occurrence`, `ind1`, `ind2` et `subfield_index`. Les répétitions sont conservées.
Les liens issus de 033$a portent `origin=033a` et restent prioritaires.

**Repli :** si aucun lien BnF n'est extrait de 033$a (zone absente ou ne contenant
aucun lien correspondant au filtre), chaque 035$a commençant par `FRBNF` puis
huit chiffres est examiné. La comparaison du préfixe est insensible à la casse,
après suppression des espaces extérieurs. Les éventuels caractères suivants
doivent être alphanumériques. Les huit premiers chiffres forment `bnf_number` ;
le suffixe est conservé dans `identifier_suffix` mais n'entre pas dans le calcul.
Le préfixe traité est `FRBNF`, comme dans les notices sources, et non `FRBRF`.
La sous-zone $z ne sert jamais à générer un lien.

L'URL est `http://catalogue.bnf.fr/ark:/12148/cb` + les huit chiffres + la clé.
Le calcul suit le §8.3 des
[préconisations officielles BnF](https://multimedia-ext.bnf.fr/pdf/ark_preconisations_bnf.pdf) :
alphabet `0123456789bcdfghjkmnpqrstvwxz`, valeurs de 0 à 28, somme des valeurs
des caractères de `cb` + numéro multipliées par leurs positions de 1 à 10,
puis modulo 29. Le résultat désigne un caractère de cet alphabet ; la clé peut
être une lettre ou un chiffre. Le modulo 11 et la correspondance a=1/b=2/c=3
ne s'appliquent pas à ces ARK.

Exemple : `FRBNF487863030000002` → numéro `48786303`, suffixe `0000002`,
URL `http://catalogue.bnf.fr/ark:/12148/cb48786303r`.
Les liens calculés portent `origin=035a`, `checksum_algorithm=bnf_ark_mod29`,
le 035$a intégral dans `raw` et les mêmes références d'occurrence que les liens
extraits de 033. Le calcul est local : il ne vérifie pas l'existence de la notice
sur le catalogue BnF. En l'absence des deux sources, `bnf_links` reste une liste vide.

`bnf_links.jsonl` ajoute le PPN et la provenance XML à chaque occurrence.
Le rapport fournit `counts.bnf_links`, `counts.records_with_bnf_links`,
`counts.bnf_links_from_033a`, `counts.bnf_links_from_035a` et
`counts.records_with_bnf_links_from_035a`.

### Résumés en 330$a

Chaque sous-zone $a de chaque zone 330 est extraite dans la liste `summaries`.
Les zones et sous-zones répétées sont conservées dans l'ordre du XML, même si
leurs textes sont identiques. Le script ne fusionne ni ne traduit les résumés.

Chaque objet contient `raw` (texte original), `value` (normalisation textuelle
décrite plus haut), `source_field`, `field_index`, `occurrence`, `ind1`, `ind2`
et `subfield_index`. Les autres sous-zones de 330 restent dans `source_fields`.
Sans 330$a, la liste est vide ; un $a vide reste conservé avec `value=null`.

Les résumés figurent dans `documents.jsonl` sous `summaries`, ainsi que dans
`summaries.jsonl` (une occurrence de $a par ligne avec PPN et provenance XML).
`counts.summaries` compte les occurrences extraites, y compris vides ;
`counts.records_with_summaries` compte les notices avec au moins un résumé non vide.

### Indexations des zones 600 à 620

Toutes les zones de **600 à 620 incluses** sont extraites dans `subjects`,
sans filtrage sur la présence d'un $a, sur le vocabulaire ou sur le contenu.
Une occurrence donne un objet distinct ; aucune déduplication ni fusion des
vedettes et subdivisions n'est effectuée. Les éventuelles zones inhabituelles
de cet intervalle sont conservées sans leur attribuer une signification supposée.

Chaque objet contient :

- `source_field`, `field_index`, `occurrence`, `ind1`, `ind2` ;
- `subfields`, liste ordonnée de **toutes** les sous-zones, chacune avec
  `subfield_index`, `code`, `raw` et `value` (normalisation textuelle décrite plus haut).

Les $3, $2, subdivisions et sous-zones répétées restent donc séparés et dans
l'ordre original. Le script ne déduit aucun vocabulaire absent et ne résout pas
les identifiants d'autorité sur le réseau. Les formes normalisées ne remplacent
jamais les valeurs brutes.

Les données figurent dans `documents.jsonl` sous la clé `subjects` et dans
`subjects.jsonl` (une occurrence par ligne, avec `ppn` et `source`). Le rapport
donne `counts.subjects`, `counts.records_with_subjects` et `subjects_by_field`.
Les zones hors intervalle, notamment 676, restent traitées par leurs extractions
respectives ou conservées dans `source_fields`.

### Localisations : source validée et dédoublonnage

À partir de V0.3.6, une notice doit contenir au moins un **930$b non vide** pour
être conservée. Sinon elle est exclue de tous les exports bibliographiques et
du CSV des localisations. Aucun $5 ne permet de contourner ce filtre.
Le rapport conserve son PPN, sa provenance et le motif dans `exclusions`, et
distingue `records_parsed`, `records_retained` et `records_excluded`. Les autres
comptages concernent les notices conservées. Les XML bruts et les anciennes
extractions ne sont pas modifiés. Un $b non vide mais mal formé reste signalé
comme invalide et ne donne pas de relation PPN/RCR ; ce n'est pas une absence de $b.

Chaque 930 est exportée intégralement dans `locations.jsonl`, même sans $b.
La source 930$b est validée par l'utilisateur. Seuls les $b contenant un RCR de
neuf chiffres donnent des relations dans `holdings` (liste dans `documents.jsonl`
et fichier spécialisé `holdings.jsonl`). Le dédoublonnage porte sur le couple
**PPN/RCR** : plusieurs occurrences d'un RCR dans la même notice donnent une
seule relation ; le même RCR dans deux notices donne deux relations distinctes.
Chaque relation conserve toutes ses preuves dans `evidence`, et les champs
930 restent séparés dans `locations`. Les zéros initiaux des RCR sont préservés.

`validation_status=user_confirmed_930b` et le champ `holdings_validation` du
rapport enregistrent cette validation de la source. Le rapport indique la clé
`holdings_deduplication_key`, le nombre de couples dans `counts.holdings` et le
nombre d'occurrences regroupées dans `counts.duplicate_rcr_occurrences_collapsed`.
Les versions antérieures utilisaient `holdings_observed` ; leurs sorties restent
conservées dans leurs dossiers respectifs.

Les sous-zones $5 de toutes les zones sont conservées dans `local_links_5`.
Quand leur valeur suit le motif `RCR:identifiant_exemplaire`, les deux parties
sont extraites comme candidats. Une comparaison avec le $b de la même 930
porte `match`, `mismatch` ou `not_comparable`. Aucun $5 ne remplace un $b manquant.
Les candidats présents uniquement dans d'autres zones apparaissent dans le CSV
de vérification, sans être promus en bibliothèques possédantes.

La concordance $b/$5 reste un contrôle interne de la réponse XML. La validation
de la source est celle fournie par l'utilisateur ; le script n'effectue aucune
validation externe supplémentaire ni nouvelle collecte.

Références : [100 et dates d'échange](https://documentation.abes.fr/sudoc/formats/unmb/zones/100.htm),
[rôles des mentions 214](https://documentation.abes.fr/sudoc/formats/unmb/zones/214.htm),
[formation Abes : RCR en 930$b](https://documentation.abes.fr/sudoc/doc/Formateur_relais/INIT_FicheFormateurs.pdf).

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
