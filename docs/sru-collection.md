# Collecte Sudoc SRU — V0.2

## Source et requête

Référence : [Guide d'utilisation SRU du catalogue Sudoc, Abes](https://abes.fr/guide-utilisation-service-sru-catalogue-sudoc/).
Le collecteur utilise `https://www.sudoc.abes.fr/cbs/sru/`, SRU 1.1,
`operation=searchRetrieve`, `recordSchema=unimarc`, `recordPacking=xml`.
La taille de page est configurable de 1 à 1 000, avec 200 par défaut.
Le plafond `--max-records` est fixé à 2 000 par défaut, cache compris, et
enregistré dans le manifeste. La dernière requête demande seulement le reliquat.
Aucune collecte complète ne doit être lancée sans demande explicite de l'utilisateur.

Les limitations APU et TDO nécessitent un index de recherche. Le 19 septembre
2026, `apu=2025 and (tdo=b or tdo=x)` et les recherches avec `ppn=*` ou `tou=*`
ont renvoyé le diagnostic `IMPOSSIBLE_ADI`, sous HTTP 200. En revanche,
`ppn=0* and apu=2025 and (tdo=b or tdo=x)` a renvoyé deux notices.

La collecte est donc partitionnée par premier chiffre du PPN : dix requêtes,
de `ppn=0*` à `ppn=9*`, chacune avec les limitations année et TDO `b`/`x`.
Ces partitions couvrent les identifiants numériques attendus sans chevauchement.
Les PPN sont validés comme des chaînes de neuf caractères, le dernier pouvant
être `X`. Chaque PPN reçu doit appartenir au préfixe demandé.

## Fichiers d'une campagne

```text
manifest.json                 Paramètres immuables et date de démarrage
report.json                   État et comptes, mis à jour à chaque page validée
pages/0/000000001.xml          Réponse brute : préfixe 0, position initiale 1
pages/0/000000001.json         Paramètres, date de récupération et SHA-256
pages/…                       Autres préfixes et positions
rejected/…xml                 Réponses HTTP ou SRU rejetées
```

L'écriture de chaque fichier se fait par remplacement d'un fichier temporaire.
Une page sans son fichier de métadonnées sera redemandée à la reprise. Une page
dont le SHA-256 a changé est signalée comme corrompue ; elle n'est pas réutilisée.
Une seule exécution doit utiliser un dossier de campagne à la fois.

Une reprise conserve l'année, le plafond de notices, la taille de page, les requêtes et la version du
collecteur. Un changement nécessite une nouvelle campagne. Le rapport est recalculé
depuis les pages disponibles ; ses comptes ne sont pas incrémentés une seconde fois.
La limite `--max-pages` porte sur le total de pages de la campagne, cache compris.

## Contrôles

- Diagnostics SRU contrôlés avant les comptes ; le diagnostic vide `1/0` observé
  sur les réponses réussies est accepté.
- Le diagnostic `1/61` est accepté uniquement à la position 1 si le serveur
  annonce explicitement zéro résultat et ne renvoie aucune notice.
- Requête renvoyée par le serveur comparée à la requête envoyée.
- XML strict, sans résolution d'entités externes ni DTD.
- Schéma UNIMARC, encapsulation XML, positions contiguës, champ `001` exploitable.
- Progression selon le nombre réellement reçu, même si la page est courte.
- Arrêt sur page vide prématurée, saut de position, PPN répété ou variation du total.
- Trois tentatives au maximum pour les erreurs réseau, HTTP 429/5xx retenues et
  indisponibilités SRU temporaires. `IMPOSSIBLE_ADI` n'est pas réessayé.
- Requêtes séquentielles, pause de 0,5 seconde avant chaque tentative ; attente
  croissante entre tentatives et prise en compte de `Retry-After` en secondes
  (plafond de 60 secondes).

## Lecture du rapport

`records_downloaded` compte les notices des réponses structurellement valides
disponibles, cache compris ; `records_validated` compte celles ayant aussi passé
les contrôles entre pages. Ils peuvent différer si une page change de total ou
contient des doublons. `distinct_ppns` compte les PPN validés distincts.
Le XML d'une page reçue reste conservé même si un contrôle entre pages échoue.

`sru_number_of_records` reste nul tant que les dix partitions n'ont pas toutes
été interrogées. `announced_records_known_partitions` et
`missing_records_known_partitions` ne concernent que les partitions déjà observées.
Ils ne permettent pas d'estimer à eux seuls le volume national d'un essai limité.

`complete=true` exige que les dix partitions soient terminées avec égalité des
comptes annoncés, validés et distincts. Les étapes de parsing métier et de
chargement ne sont pas encore réalisées : `records_parsed` et `records_loaded`
restent nuls, et ne sont pas artificiellement assimilés au nombre téléchargé.

## Limites à conserver pour la suite

L'exhaustivité est contrôlée **par rapport aux résultats annoncés par le SRU**.
Le catalogue est vivant ; les contrôles ne garantissent pas un instantané figé.
Une modification à total constant, sans doublon visible, peut échapper à la
détection. Les sources brutes permettent de rejouer le traitement effectivement
réalisé, pas de reconstituer l'état global du catalogue à une date passée.

Le filtre `b`/`x` définit un ensemble de candidats. Le caractère physique des
multisupports, les exclusions métier et l'interprétation exacte des dates
nécessitent encore les contrôles UNIMARC de la V0.3. Le rapport porte donc
`scope_validation=pending_unimarc_validation`.

Les réponses observées utilisent des champs MARC sans espace de noms, des
localisations en `930$b` et parfois des caractères de non-tri dans les titres.
Ces observations préparent le parsing ; elles ne constituent pas encore une
validation générale du mapping métier.
