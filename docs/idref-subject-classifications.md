# Classifications IdRef via les seules têtes de vedettes 606$a

## Sélection

Entrée : le lot enrichi BnF/IdRef de 1 995 notices. Toutes sont traitées, y
compris celles ayant déjà une Dewey Sudoc ou BnF. La collecte est bornée aux
autorités liées aux 606$a présentes dans ce lot ; ce n'est pas une collecte
du catalogue Sudoc ou d'IdRef complet.

Dans le XML Sudoc exporté, un $3 précède le libellé de l'élément qu'il identifie.
Le script retient seulement le $3 immédiatement avant chaque $a de chaque 606.
Il ne suit pas les identifiants des subdivisions $x/$y/$z, ni ceux des autres
zones (600, 607, 608, etc.). Un identifiant absent, invalide ou ambigu est
signalé sans recherche par libellé ni attribution depuis une subdivision.
Les répétitions sont conservées. Une même autorité n'est téléchargée qu'une fois.

Dans ce lot : 6 585 occurrences de 606$a, 4 291 liées à 2 925 PPN distincts.

## Classifications récupérées

- **676$a**, zone répétable : Dewey de l'autorité, `scheme=dewey`.
  Les sous-zones, notamment l'édition $v, et la normalisation restent tracées.
- Avec `--include-rameau`, **686$a** uniquement si le $2 est
  **Note de regroupement par domaine** : `scheme=rameau_domain`.
  C'est le cadre de classement Rameau, distinct de la Dewey bibliographique.
  Le code est conservé tel quel, avec ses termes explicatifs $c et les autres
  sous-zones. Il n'est pas converti ni développé en une classe plus précise.
- Les autres classifications 686 (MeSH, CAS/ENZ, corpus internes, etc.) sont
  ignorées. Aucun lien vers une autorité associée, plus large ou plus étroite
  n'est suivi pour récupérer d'autres classifications.

Le XML IdRef est utilisé pour préserver les zéros initiaux et les valeurs
textuelles exactes, puis les résultats sont stockés en JSON. L'identifiant 001
doit correspondre au PPN demandé, ou un ancien identifiant 035$a doit attester
la fusion. Sinon la réponse est conservée mais ses classes ne sont pas ajoutées.

Références Abes consultées le 21 septembre 2026 :

- [606 bibliographique : élément d'entrée et liens](https://documentation.abes.fr/sudoc/formats/unmb/zones/606.htm).
- [676 d'autorité : Dewey](https://documentation.abes.fr/sudoc/formats/unma/zones/676.htm).
- [686 d'autorité : autres classifications et regroupement Rameau](https://documentation.abes.fr/sudoc/formats/unma/zones/686.htm).

## JSON par notice

`documents.jsonl` conserve toutes les données d'entrée et ajoute deux listes :

- `idref_606a_links` : chaque tête de vedette 606$a, son libellé brut, ses indices
  de zone/sous-zone, le PPN d'autorité demandé et résolu, le statut et la provenance.
- `idref_606a_classifications` : une entrée par classe et par chemin depuis
  une 606$a, avec `scheme`, `code_raw`, `code`, la zone IdRef source,
  les sous-zones intégrales, le PPN d'autorité, le chemin `via_606a`,
  l'URL, la date de récupération et l'empreinte du XML dans `authority_source`.

Une autorité sans classe a un lien résolu avec `classification_count=0`.
Une notice sans 606$a a deux listes vides. Les Dewey existantes restent dans
`classifications` sans aucune modification. Il n'y a pas de fusion entre méthodes.

Les exports `authority-results.jsonl` (par autorité) et
`authority-classifications.jsonl` (par occurrence liée à un document), le
rapport JSON et `rapport.md` facilitent les contrôles.

## Exécution et reprise

```powershell
.\.venv\Scripts\python.exe scripts/08_enrich_606a_authorities.py --input-dir data/enrichment/sample-2000/bnf-idref-v0.1.0 --run-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --include-rameau
```

`--collect-only` collecte les sources sans enrichir les documents.
`--process-only` produit les documents depuis la collecte terminée sans réseau.
Le délai entre requêtes est de 0,3 seconde ; les erreurs transitoires font
l'objet de trois tentatives au maximum. Les fichiers XML, requêtes, dates et
empreintes sont conservés. Une reprise réutilise le cache et réessaie les erreurs.
Les réponses 404/410 restent signalées comme introuvables. Une erreur de
collecte empêche la finalisation jusqu'à reprise réussie.

## DuckDB

L'enrichissement est attaché au corpus existant sans le dupliquer ni modifier
les tables DOCUMENT, CLASSIFICATION ou HOLDING :

```powershell
.\.venv\Scripts\python.exe scripts/09_load_authority_enrichment.py --enrichment-dir data/enrichment/sample-2000/idref-606a-v0.1.0 --database data/sudoc.duckdb --corpus-id sample-2000-2025-bnf-idref-v1 --run-id idref-606a-v1
```

Les tables AUTHORITY_RUN, AUTHORITY_DOCUMENT (JSON complet enrichi),
AUTHORITY_HEADING et AUTHORITY_CLASSIFICATION conservent ce nouveau résultat
séparément. Le chargement vérifie l'identité du lot et l'absence de modifications
des données bibliographiques. Il est transactionnel et sans effet si le même
enrichissement est déjà chargé.

```sql
-- Classes distinctes par notice et par méthode IdRef.
SELECT DISTINCT ppn, scheme, code
FROM AUTHORITY_CLASSIFICATION
WHERE run_id = 'idref-606a-v1' AND code IS NOT NULL;

-- Comparer sans mélanger les méthodes : sudoc:676$a, bnf:676$a,
-- idref:dewey, idref:rameau_domain.
SELECT DISTINCT ppn, source AS methode, dewey_normalized AS code
FROM CLASSIFICATION
WHERE corpus_id = 'sample-2000-2025-bnf-idref-v1' AND dewey_normalized IS NOT NULL
UNION ALL
SELECT DISTINCT ppn, 'idref:' || scheme AS methode, code
FROM AUTHORITY_CLASSIFICATION
WHERE run_id = 'idref-606a-v1' AND code IS NOT NULL;
```
