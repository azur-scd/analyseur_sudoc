# Convention documentaire sur les versions

Plusieurs niveaux de version coexistent dans le projet :

- **version du paquet Python** : portée par `pyproject.toml` ;
- **version interne du parseur / format d'extraction UNIMARC** : définie dans `src/analyseur_sudoc/unimarc.py` par `PARSER_VERSION` (par exemple `0.3.8`) et utilisée par `scripts/03_parse_unimarc.py` ;
- **versions des lots, audits et enrichissements** : par exemple `unimarc-v0.3.7`, `audit-v0.3.1`, `bnf-idref-v0.1.0` ou `idref-606a-v0.1.0` ;
- **cible produit V1** : niveau fonctionnel visé par le PRD et les spécifications.

Les dossiers nommés `unimarc-v0.3.8` correspondent donc à des livraisons d'extraction, et non à la version du paquet Python. La distinction est importante pour éviter toute confusion entre les versions documentaires, les versions de parsing et les versions de publication du projet.
