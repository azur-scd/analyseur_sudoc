# Sources des fixtures

`sru_2025_prefix0_page1.xml` : première page récupérée le 19 septembre 2026
auprès de `https://www.sudoc.abes.fr/cbs/sru/`, avec la requête
`ppn=0* and apu=2025 and (tdo=b or tdo=x)`, `startRecord=1`,
`maximumRecords=1`, SRU 1.1, schéma UNIMARC, encapsulation XML.

La notice et l'enveloppe ont été conservées. Le bloc `extraResponseData`
(informations techniques de session) et l'instruction de feuille de style ont
été retirés. La fixture vérifie le format effectivement reçu : diagnostic
`1/0`, requête encodée dans l'écho, MARC sans espace de noms, positions et PPN.
