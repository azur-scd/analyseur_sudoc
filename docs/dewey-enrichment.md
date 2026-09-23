# Normalisation Dewey et préparation de l'enrichissement BnF

La version interne 0.3.8 du parseur UNIMARC — définie dans
`src/analyseur_sudoc/unimarc.py` et exécutée par
`scripts/03_parse_unimarc.py` — retire les espaces de regroupement décimaux et
sépare les annotations littéraires reconnues. Voir `unimarc-mapping.md`.
Cette version ne devine pas la signification des préfixes/suffixes (B, C, NZ,
v23, etc.) et ne complète pas les indices par des chiffres supposés.

> Note : il ne s'agit pas de la version du paquet Python déclarée dans
> `pyproject.toml` (actuellement 0.4.0). La référence `0.3.8` ici désigne la
> version du moteur d'extraction UNIMARC, pas le numéro de version du projet.

Le script suivant compare deux extractions contenant exactement les mêmes
PPN et prépare les listes d'examen, sans accès réseau :

```powershell
.\.venv\Scripts\python.exe scripts/05_dewey_review.py --before data/processed/sudoc/sample-2000/unimarc-v0.3.7 --after data/processed/sudoc/sample-2000/unimarc-v0.3.8 --output-dir data/processed/sudoc[...]
```

La sortie doit être vide. Elle contient un rapport, les statistiques avec
empreintes des documents d'entrée, les notices gagnées, les candidats BnF,
toutes les notices sans Dewey exploitable et les notations encore à examiner.
Les CSV comportent PPN, titre, indices bruts et normalisés, règles, annotations,
URL BnF avec origine 033/035 et référence XML.

Résultat sur les 1 995 notices : 714 → 758 notices avec Dewey exploitable,
soit 44 notices supplémentaires et 38,00 % de couverture. Sur les 1 237
notices restant à enrichir, 24 ont une URL BnF et 1 213 n'en ont pas.
Les 24 liens constituent un lot candidat, sans garantie de présence d'une
Dewey ni vérification distante de la correspondance. Aucun téléchargement
BnF ni recherche par ISBN n'est réalisé à cette étape.

Décision utilisateur : toutes les 1 995 notices sont conservées, y compris
les travaux universitaires édités et les autres cas litigieux de périmètre.
Les alertes des audits précédents restent des observations historiques et
ne doivent pas déclencher d'exclusion. Le filtre antérieur sans 930$b reste
appliqué aux cinq notices écartées du lot brut de 2 000.
