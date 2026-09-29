# Référentiel bilingue des sections Dewey

Le fichier [`resources/dewey_1000_sections.csv`](../resources/dewey_1000_sections.csv) a été fourni par l'utilisateur le 29 septembre 2026. Il est conservé tel quel comme référentiel versionné pour les futurs profils et affichages. Il n'est pas encore intégré au pipeline ou à DuckDB.

## Structure

- Encodage : UTF-8 ; séparateur : point-virgule ; première ligne d'en-tête.
- Colonnes : `code_dewey` (texte à trois chiffres, zéros initiaux significatifs), `intitule_en`, `intitule_fr`.
- 904 lignes de données, ordonnées par code croissant, sans code dupliqué ni cellule vide.
- Le référentiel contient les 904 codes utilisés. Les 96 autres codes possibles entre `000` et `999` ne sont pas utilisés et doivent être ignorés : ne pas les ajouter, les afficher ni tenter de leur attribuer un intitulé.
- Certains intitulés sont répétés sous des codes différents : 14 groupes en anglais et 12 en français. Le code, et non l'intitulé, doit servir de clé.
- Empreinte SHA-256 du fichier source : `B0746BE5FA1B48DA9E03A836C8F8DD2067FF713F5BEBED300FCD893BE62AC007`.

Lors de son utilisation, conserver `code_dewey` comme chaîne de trois caractères. Un indice Dewey détaillé peut être relié à une section par ses trois premiers chiffres seulement si cet indice a déjà été validé et normalisé ; un code sans correspondance dans ce référentiel doit être ignoré pour les analyses fondées sur ces sections.
