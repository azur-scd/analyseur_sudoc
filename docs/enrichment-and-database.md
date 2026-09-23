# Enrichissement BnF / IdRef et chargement DuckDB

## Lot livré

- Entrée : `data/processed/sudoc/sample-2000/unimarc-v0.3.8` (1 995 notices
  retenues sur le premier corpus de 2 000 notices de documents parus en 2025).
- Enrichissement : `data/enrichment/sample-2000/bnf-idref-v0.1.0`.
- Base : `data/sudoc.duckdb`.
- Identifiant du corpus : `sample-2000-2025-bnf-idref-v1`.

> Convention de version : le dossier `unimarc-v0.3.8` est une extraction produite par `scripts/03_parse_unimarc.py` à partir du parseur `src/analyseur_sudoc/unimarc.py`. La version `0.3.8` désigne ici la version interne du parseur UNIMARC, et non la version du paquet Python.

Pour ce premier corpus de 2 000 notices de documents parus en 2025, les 1 995
notices retenues sont incluses suivant la décision utilisateur, y compris les
travaux universitaires édités et les autres cas précédemment litigieux. Le
filtre antérieur sans 930$b reste appliqué à ce lot brut de 2 000 notices.

## BnF

Seules les 24 notices sans Dewey exploitable ayant un lien BnF existant sont
interrogées, par `bib.persistentid` sur l'ARK, au format `unimarcXchange`.
Une réponse unique dont l'identifiant correspond exactement est requise pour
ajouter les 676$a. Les diagnostics et erreurs HTTP sont signalés ; une absence
de notice ou un identifiant différent est conservé comme résultat sans ajout.

Les Dewey Sudoc restent présentes. Chaque ajout porte `dewey_source=bnf:676$a`,
l'ARK, la référence de champ, l'édition, les règles de normalisation et
`enrichment_source` (requête, fichier XML, empreinte SHA-256 et date).
Le rapprochement repose sur le lien BnF fourni par le Sudoc ; il ne comporte
pas de nouveau rapprochement par titre ou ISBN.

Les 24 notices ont été retrouvées ; 5 contiennent une Dewey, toutes exploitables.
La couverture finale est de 763 / 1 995, soit 38,25 %. Les 19 autres réponses
n'ont pas de 676$a. Aucun autre enrichissement Dewey n'est poursuivi.

Documentation : [API SRU Catalogue général BnF](https://api.bnf.fr/fr/api-sru-catalogue-general).

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
.\.venv\Scripts\python.exe scripts/06_enrich_bnf_idref.py --input-dir data/processed/sudoc/sample-2000/unimarc-v0.3.8 --run-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --prior-reference data/reference/listrcr/smoke-test
.\.venv\Scripts\python.exe scripts/07_load_corpus.py --enrichment-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-idref-v1 --year 2025
```

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
| CLASSIFICATION | Toutes les Dewey, sources Sudoc/BnF distinctes, indices bruts et normalisés |
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

-- Notices et noms des bibliothèques possédantes pour le lot livré.
SELECT d.ppn, d.title, l.rcr, l.label, l.iln, l.library_type
FROM DOCUMENT d
JOIN HOLDING h USING (corpus_id, ppn)
JOIN LIBRARY l USING (rcr)
WHERE d.corpus_id = 'sample-2000-2025-bnf-idref-v1';

-- Les résumés répétés restent des lignes distinctes.
SELECT ppn, occurrence, value FROM SUMMARY;
```
