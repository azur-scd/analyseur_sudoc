# Domaines du cadre de classement Rameau (2026)

Le référentiel CSV [`resources/rameau_domains_2026.csv`](../resources/rameau_domains_2026.csv)
reprend la liste officielle fournie pour 2026. Il contient les colonnes `code`
et `domaine`; les codes sont des chaînes de trois chiffres afin de préserver
les zéros initiaux.

Dans `CLASSIFICATION`, les codes des autorités Rameau sont normalisés comme les
indices Dewey et stockés dans `dewey_raw`, `dewey_normalized` et `dewey_1/2/3`.
Le champ `scheme = 'rameau_domain'` permet de les distinguer des Dewey (`scheme
= 'dewey'`). Les libellés français du CSV servent de référentiel d'affichage ;
ils ne remplacent pas les termes $c ni les sous-zones source conservées dans le
payload de la classification.
