# Enrichissement BnF / IdRef et chargement DuckDB

## Lot livré

- Entrée : `data/processed/sudoc/sample-2000/unimarc-v0.3.8` (1 995 notices
  retenues sur le premier corpus de 2 000 notices de documents parus en 2025).
- Enrichissement : `data/enrichment/sample-2000/bnf-idref-v0.3.0`.
- Base : `data/sudoc.duckdb`.
- Identifiant du corpus : `sample-2000-2025-bnf-fuzzy-v1`.

> Convention de version : le dossier `unimarc-v0.3.8` est une extraction produite par `scripts/03_parse_unimarc.py` à partir du parseur `src/analyseur_sudoc/unimarc.py`. La version `0.3.8` désigne ici la version interne du parseur UNIMARC, et non la version du paquet Python.

Pour ce premier corpus de 2 000 notices de documents parus en 2025, les 1 995
notices retenues sont incluses suivant la décision utilisateur, y compris les
travaux universitaires édités et les autres cas précédemment litigieux. Le
filtre antérieur sans 930$b reste appliqué à ce lot brut de 2 000 notices.

## BnF

Les Dewey Sudoc restent présentes. Chaque ajout porte `dewey_source=bnf:676$a`,
l'ARK, la référence de champ, l'édition, les règles de normalisation et
`enrichment_source` (requête, fichier XML, empreinte SHA-256 et date).
Pour une nouvelle campagne d'enrichissement, le script émet une seule requête
BnF par notice sans Dewey exploitable : lien ARK existant s'il y en a un,
sinon EAN `073$a`, sinon ISBN `010$a`. Les recherches par EAN ou ISBN utilisent
le critère `bib.fuzzyISBN`. Une réponse avec une seule notice permet de reprendre
ses `676$a` ; une réponse multiple ne donne aucun ajout.
L'identifiant recherché, la méthode, la réponse et sa provenance restent tracés.
Le rapprochement ne repose pas sur le titre.

Documentation : [API SRU Catalogue général BnF](https://api.bnf.fr/fr/api-sru-catalogue-general).

### Campagne active : `bib.fuzzyISBN`, une requête par notice

La campagne `data/enrichment/sample-2000/bnf-idref-v0.3.0` a traité les mêmes
1 995 notices. Parmi elles, 1 156 sans Dewey exploitable avaient un lien ARK,
un EAN ou un ISBN. Le script a effectué exactement une tentative par notice
candidate : 24 par ARK, 844 par EAN et 288 par ISBN. Les deux derniers cas
utilisent `bib.fuzzyISBN`, avec priorité à l'EAN.

Le SRU a retourné 1 155 réponses traitées et un diagnostic « erreur de
traitement » pour l'ISBN `9782336615714`. Une recherche EAN a retourné
plusieurs notices et n'a donné aucun ajout. Les 56 Dewey BnF utilisables
proviennent de 5 liens ARK, 30 recherches EAN et 21 recherches ISBN.
La couverture est de **814 / 1 995 (40,80 %)**. Le statut du rapport reste
`partial` à cause du diagnostic SRU. Le lot est chargé dans `data/sudoc.duckdb` sous l'identifiant
`sample-2000-2025-bnf-fuzzy-v1` ; la base conserve le rapport et son erreur.

Le chargeur accepte désormais automatiquement un rapport `partial` produit par
la politique « une requête BnF par notice » lorsque toutes les erreurs relèvent
de la BnF, représentent au plus 1 % des notices candidates, et que chaque
candidate possède exactement une issue (réponse ou erreur). Les autres cas
restent refusés. Les empreintes, effectifs et relations PPN/RCR sont toujours
contrôlés avant le chargement transactionnel.

## RCR

Le référentiel listrcr est téléchargé et conservé intégralement. Seuls les RCR
présents dans les localisations du corpus sont enrichis via leur PPN IdRef,
en récupérant `130$a` (type de bibliothèque). Nom, ILN, ville, pays, code postal
et coordonnées proviennent de listrcr. Les 339 RCR sont retrouvés et ont un type.
Trois réponses IdRef du test précédent ont été réutilisées ; les autres ont
été téléchargées. Les sources et empreintes restent dans `libraries.jsonl`.
Les anomalies du référentiel national sont consignées ; aucune ne concerne
les 339 RCR de ce lot.

Les requêtes sont séquentielles, espacées d'au moins 0,3 seconde, avec trois
tentatives au maximum pour les erreurs réseau et HTTP transitoires.
La reprise vérifie les paramètres et les empreintes des caches ; les réponses
déjà enregistrées ne sont pas téléchargées à nouveau.

```powershell
.\.venv\Scripts\python.exe scripts/06_enrich_bnf_idref.py --input-dir data/processed/sudoc/sample-2000/unimarc-v0.3.8 --run-dir data/enrichment/sample-2000/bnf-idref-v0.3.0 --prior-reference data/reference/listrcr/smoke-test
.\.venv\Scripts\python.exe scripts/07_load_corpus.py --enrichment-dir data/enrichment/sample-2000/bnf-idref-v0.3.0 --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-fuzzy-v1 --year 2025
.\.venv\Scripts\python.exe scripts/11_corpus_summary.py --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-fuzzy-v1 --bnf-dir data/enrichment/sample-2000/bnf-idref-v0.3.0 --rameau-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --output-dir data/reports/sample-2000-classifications-v1
```

Le rapport comprend aussi une comparaison exploratoire Dewey/Rameau : il ne
retient que les notices ayant exactement un code bibliographique distinct
(union Sudoc/BnF) et un seul domaine Rameau. Il mesure l'égalité des codes à
3 chiffres, puis de leurs préfixes à 2 et 1 chiffre. Les autres configurations
restent hors de cette comparaison initiale. Un même code détaillé présent dans
Sudoc et BnF ne compte qu'une fois. Le résultat détaillé par notice est exporté
dans `comparaison-dewey-rameau.csv`. Le tableau suivant du même rapport traite
les notices avec plusieurs codes d'un côté ou des deux : correspondance complète,
partielle ou absente à 3, 2 et 1 chiffre après dédoublonnage des préfixes. Les
ensembles et leurs intersections figurent dans
`comparaison-dewey-rameau-multiples.csv`.

La couverture par source est aussi recalculée pour les notices dont la zone
`102$a` contient `FR` (même avec d'autres codes pays), et pour toutes les autres
notices, y compris celles sans code pays. Chaque pourcentage utilise l'effectif
de son groupe comme dénominateur.
Une analyse exploratoire compare aussi la présence d'une Dewey Sudoc/BnF,
d'un indice via les autorités (Dewey IdRef ou domaine Rameau), puis d'au moins
un indice des deux voies. Elle indique l'écart de proportions et le résultat
du test exact de Fisher ; elle ne permet pas d'attribuer causalement un écart
au pays de publication.

## Stockage

Le chargement est transactionnel. Il vérifie les empreintes, effectifs,
identifiants uniques et liens PPN/RCR avant validation. Une campagne avec
erreurs de collecte n'est pas chargée. Recharger le même corpus est sans effet ;
des données différentes demandent un nouvel identifiant de corpus.
La base de test antérieure `data/sudoc.sample.duckdb` reste indépendante.

| Table | Contenu |
|---|---|
| CORPUS | Année demandée, provenance, empreintes et rapport |
| DOCUMENT | PPN, titre, année dérivée, statut inclus, provenance et document JSON complet |
| LIBRARY | Métadonnées des RCR, identifiants conservés en texte |
| CORPUS_LIBRARY | Métadonnées complètes et provenance des bibliothèques, figées par corpus |
| HOLDING | Couples PPN/RCR dédoublonnés par corpus, avec preuves |
| CLASSIFICATION | Dewey Sudoc/BnF/IdRef et domaines Rameau, avec source, schéma, exécution et lien d'autorité |
| DOCUMENT_FIELD | Champs répétables, une ligne par occurrence et catégorie |

Les vues AUTHOR, PUBLISHER, SUBJECT, SUMMARY, LANGUAGE, COUNTRY, BNF_LINK,
LEADER_TYPE, CONTENT_TYPE, MEDIA_TYPE, NATURE_OF_CONTENT, LOCATION, CODED_DATE
et PUBLICATION_STATEMENT exposent les catégories de DOCUMENT_FIELD. Leurs
colonnes `payload` contiennent les objets JSON complets, sans perte de sous-zones.
LIBRARY_PROFILE compte les notices possédées et leur couverture Dewey.
La clé d'un document est `(corpus_id, ppn)` : un PPN peut appartenir à plusieurs lots.
LIBRARY conserve la première entrée chargée pour un RCR ; CORPUS_LIBRARY conserve
les métadonnées exactes de chaque chargement pour comparer les campagnes.

```sql
-- Toutes les Dewey ajoutées par la BnF.
SELECT ppn, dewey_raw, dewey_normalized
FROM CLASSIFICATION WHERE source = 'bnf:676$a';

-- Classifications IdRef et domaines Rameau, avec provenance de l'autorité.
SELECT ppn, run_id, scheme, dewey_raw, dewey_normalized,
       requested_authority_ppn, resolved_authority_ppn
FROM CLASSIFICATION
WHERE run_id = 'idref-606a-v1' AND dewey_normalized IS NOT NULL;

-- Notices et noms des bibliothèques possédantes pour le lot livré.
SELECT d.ppn, d.title, l.rcr, l.label, l.iln, l.library_type
FROM DOCUMENT d
JOIN HOLDING h USING (corpus_id, ppn)
JOIN LIBRARY l USING (rcr)
WHERE d.corpus_id = 'sample-2000-2025-bnf-fuzzy-v1';

-- Les résumés répétés restent des lignes distinctes.
SELECT ppn, occurrence, value FROM SUMMARY;
```
