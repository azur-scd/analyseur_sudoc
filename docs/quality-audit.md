# Audit local des extractions

## Nouveautés v0.2.0

L'audit exploite les listes `leader_types`, `content_types`, `media_types` et
`nature_of_content` de l'extraction v0.3.7. Pour les anciennes extractions,
il relit les mêmes informations dans les champs bruts disponibles.

Les distributions comprennent les positions 6 et 7 du label, séparées et
combinées ; les codes $a, $b, $c des zones 181 et 182 ; et la position 4 de
105$a. Les valeurs 181/182 sont présentées sous forme `[vocabulaire $2, code]`
pour ne pas mélanger les systèmes de codage. Les codes restent bruts.
Chaque couple est compté une fois par notice dans les distributions
`by_vocabulary`, et à chaque répétition dans celles suffixées `occurrences`.
Les histogrammes donnent aussi le nombre de zones 181/182 par notice.

La couverture distingue présence de zone et présence de code non vide.
Les codes absents ou non renseignés sont signalés avec les PPN. L'analyse de
la première position 105$a[4] reste distincte du contrôle historique des
quatre positions 4–7 : ce dernier est conservé pour repérer aussi les travaux
universitaires dont le code figure après la première position.

Dernier lot analysé : `unimarc-v0.3.7`, résultats dans `audit-v0.2.0`.

Le script `scripts/04_audit_unimarc.py` analyse `documents.jsonl` d'une extraction
terminée. Il vérifie le nombre de notices et l'unicité des PPN, conserve les
empreintes du fichier et du rapport d'extraction, et refuse une sortie non vide.
Il ne modifie aucune notice et n'effectue aucune requête réseau.

```powershell
.\.venv\Scripts\python.exe scripts/04_audit_unimarc.py --input-dir data/processed/sudoc/sample-2000/unimarc-v0.3.7 --year 2025 --output-dir data/processed/sudoc/sample-2000/audit-v0.2.0
```

## Livrables

- `rapport.md` : couverture, distributions et liste complète des PPN par règle.
- `statistics.json` : statistiques réutilisables et provenance.
- `distributions.csv` : toutes les distributions, séparateur point-virgule.
- `anomalies.csv` et `anomalies.jsonl` : une ligne par PPN et règle, titre,
  catégorie, explication, valeurs justificatives et provenance XML.

## Comptages

Le dénominateur des couvertures est le nombre de notices conservées dans
l'extraction, après exclusion des notices sans 930$b. Chaque pays, langue,
classe Dewey ou type d'indexation est compté une fois par notice : les sommes
peuvent dépasser la taille du lot. Les distributions contenant `occurrences`
comptent les occurrences de champs ; celles suffixées `per_record` donnent
le nombre de notices pour chaque nombre d'occurrences. Les niveaux Dewey
conservent les zéros initiaux. Les résumés sont mesurés en caractères normalisés.

Le lot est limité, non aléatoire et paginé par préfixe PPN. Aucune extrapolation
à l'ensemble des publications de 2025 n'est justifiée.

## Règles et limites

- `lacune` : absence de pays, langue, Dewey, indexation exploitable ou résumé.
  Ces absences ne constituent pas en elles-mêmes des erreurs de catalogage.
- Pays : syntaxe de deux lettres majuscules ; langues : trois minuscules.
  Pas de validation exhaustive contre les référentiels de codes. XX/ZZ et
  und/mul/zxx sont signalés comme codes spéciaux à interpréter.
- Dates : distribution de l'année dérivée et du type de date 100$a ; année
  indéterminée à examiner ; année différente de la cible hors périmètre annuel.
  Les années textuelles de 210/214 de publication sont comparées à 100$a.
  Les mentions de copyright, fabrication et production ne sont pas confondues
  avec une date de publication ; les dates de soutenance 328$d non plus.
- Dewey : distinguer présence de 676$a et notation exploitable par le parseur.
  Une notation non normalisée n'est pas nécessairement une erreur Dewey.
- Indexations : zones 600 à 620, nombre de notices et occurrences par zone,
  vocabulaires $2, présence de liens $3. Une zone ne contenant que des
  sous-zones de contrôle n'est pas considérée comme exploitable.
- Résumés : couverture, répétitions, longueurs ; moins de 80 caractères
  déclenche un examen exploratoire, sans suppression. Aucun jugement
  automatique sur la qualité sémantique ou la langue des textes.
- Périmètre : 105$a positions 4–7 (format **export**) contient la nature du
  contenu : m = thèse originelle, v = version publiée ou reproduction de
  travail universitaire, 7 = mémoire originel. Seul m entraîne ici un signal
  `hors_perimetre` ; v, 7 et les notes 328 demandent une décision professionnelle,
  car un ouvrage remanié et publié n'est pas équivalent à une thèse originelle.
- 106$a=s signale une forme électronique hors périmètre ; 182$c=c signale
  une médiation informatique à examiner (éventuel accompagnement).
  Les labels rm (objets) sont à examiner au regard du périmètre multisupport
  physique. Tout label autre que am/rm est également à examiner. Le seul
  label am ne certifie pas un support imprimé. Un lien 856 n'exclut pas un livre.

Les catégories et règles se recouvrent ; leurs effectifs ne s'additionnent pas.
L'absence de signal ne certifie pas la conformité de tous les documents.
Le périmètre suivi est celui de `docs/PRD.md` ; l'audit ne supprime rien.

Références consultées le 20 septembre 2026 :

- [Abes, zone 105 et correspondance au format export](https://documentation.abes.fr/sudoc/formats/unmb/zones/105.htm).
- [Abes, note 328 et travaux remaniés](https://documentation.abes.fr/sudoc/formats/unmb/zones/328.htm).
- [Abes, forme de la ressource 106](https://documentation.abes.fr/sudoc/formats/unmb/zones/106.htm).
