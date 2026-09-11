# Sudoc Explorer

Application locale d'exploration et d'analyse des collections signalées dans le Sudoc.

## Documentation

- [PRD](docs/PRD.md)
- [Spécification fonctionnelle](docs/functional-spec.md)
- [Spécification des données](docs/data-spec.md)
- [Architecture technique](docs/architecture.md)
- [Plan de validation et de tests](docs/validation-plan.md)
- [Mapping UNIMARC](docs/unimarc-mapping.md)

## Principes V1

- une année de publication à la fois ;
- première année : 2025 ;
- monographies imprimées et documents multisupports physiques ;
- clustering au niveau RCR ;
- seuil d'éligibilité au clustering : 1 000 documents du corpus annuel ;
- référentiel RCR via IdRef `listrcr` ;
- type de bibliothèque via `130$a` de la notice RCR IdRef ;
- stockage analytique local dans DuckDB ;
- prototype en Python et Streamlit.

## Statut

Cadrage V1 validé. Développement à venir.
