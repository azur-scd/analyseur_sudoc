# Analyseur Sudoc
## Mapping UNIMARC — V1

Ce document centralise les choix de mapping UNIMARC utilisés par le projet.

> Important : les règles ci-dessous constituent le mapping initial. Elles devront être vérifiées et complétées à partir des notices Sudoc réellement rencontrées.

> Convention de version : la mention `0.3.8` ici désigne la version interne du parseur UNIMARC, définie dans `src/analyseur_sudoc/unimarc.py` par `PARSER_VERSION = "0.3.8"` et exécutée par `scripts/03_parse_unimarc.py`. Elle ne correspond pas à la version du paquet Python déclarée dans `pyproject.toml`.

## Extraction implémentée (parseur UNIMARC v0.3.8, étape 1)

Le script `scripts/03_parse_unimarc.py` lit uniquement les pages validées du
rapport de collecte et vérifie leurs empreintes SHA-256. Il produit des JSONL
dans un nouveau dossier, sans modifier les XML sources ni le rapport de collecte.
La position de notice SRU, le fichier XML et son empreinte accompagnent chaque
export. Chaque champ conserve son indice dans la notice et son numéro d'occurrence
par zone (indices commençant à 1), ses indicateurs et toutes ses sous-zones dans
l'ordre original. Le rapport d'extraction est distinct du rapport de collecte.

### Règles de transformation
