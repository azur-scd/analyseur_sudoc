# Synthèse des décisions documentées

Ce document centralise des décisions déjà explicitées ailleurs dans la
documentation. Il ne crée ni nouvelle règle métier, ni nouvelle datation.

| Décision | Synthèse documentaire | Sources |
|---|---|---|
| Holdings via `930$b` | Les relations de possession sont établies à partir des seuls `930$b` valides. Les `930` restent conservés dans `locations`, mais le parseur ne complète pas `930$b` depuis `$5`. | [README](../README.md), [unimarc-mapping.md](unimarc-mapping.md) |
| Conservation du lot de 1 995 notices | Le lot enrichi conserve les 1 995 notices validées, y compris les cas de périmètre litigieux ; seules les cinq notices sans `930$b` restent exclues du lot brut de 2 000. | [data-spec.md](data-spec.md), [dewey-enrichment.md](dewey-enrichment.md), [enrichment-and-database.md](enrichment-and-database.md) |
| Séparation Sudoc / BnF / IdRef | Les classifications Sudoc, BnF et IdRef sont conservées séparément ; les méthodes restent distinguées dans les exports, l'audit et DuckDB. | [quality-audit.md](quality-audit.md), [enrichment-and-database.md](enrichment-and-database.md), [idref-subject-classifications.md](idref-subject-classifications.md) |
| Autorités limitées aux `606$a` | L'enrichissement IdRef des sujets ne traite que les autorités liées aux seules têtes `606$a`, sans suivre les subdivisions `$x/$y/$z` ni les autres zones sujet. | [idref-subject-classifications.md](idref-subject-classifications.md) |
| Seuil de 1 000 documents pour le clustering | La cible V1 réserve le clustering aux RCR possédant au moins 1 000 documents du corpus annuel ; ce seuil est présenté comme règle métier V1. | [PRD.md](PRD.md), [functional-spec.md](functional-spec.md), [validation-plan.md](validation-plan.md) |
| Distinction RCR / ILN | Le RCR reste l'unité fondamentale d'analyse et de clustering. L'ILN est une information descriptive d'interprétation et ne remplace pas le RCR. | [PRD.md](PRD.md), [functional-spec.md](functional-spec.md) |
| Analyses non prescriptives | Les résultats servent à faire émerger des documents potentiellement intéressants à examiner ; ils ne constituent pas des prescriptions d'acquisition automatiques. | [PRD.md](PRD.md), [validation-plan.md](validation-plan.md) |

## Réserve documentaire

Lorsque la documentation décrit une cible V1 analytique (profils, similarité,
clustering, interface), cette cible ne doit pas être interprétée comme un état
actuellement livré du dépôt. Voir [architecture.md](architecture.md).
