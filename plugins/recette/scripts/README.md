# Scripts de recette

Python 3.10 ou plus récent, sans aucune dépendance à installer.

```bash
python plugins/recette/scripts/recette.py tout Recette-SEO-<Client>
```

Avant tout, vérifie que les exports sont compris :

```bash
python plugins/recette/scripts/recette.py exports Recette-SEO-<Client>
```

Chaque commande peut aussi se lancer seule : `preparer`, `sitemap`, `robots`, `sf`, `redirections`, `gabarits`, `langues`, `verifier`. L'ordre de `tout` compte : `sitemap` doit passer avant `sf`, qui croise le sitemap avec le crawl.

## Commandes utilisées par /recette:lancer

| Commande | Rôle |
|---|---|
| `mcp` | Assemble les exports obtenus par le MCP Screaming Frog (`crawl-mcp/<site>/`) en `exports/<site>/<code>.csv` ; n'écrase jamais un export déposé à la main |
| `lighthouse` | CWV-01 : Lighthouse mobile (version fixée) sur l'accueil et chaque gabarit, rapports gardés dans `donnees/lighthouse/` |
| `repartition` | Contrôles encore sans résultat, répartis entre `recette-live` et `recette-expert` |
| `poser` | Valide et enregistre les résultats des agents (`donnees/resultats-agents/*.json`), écrit leurs lignes d'annexe et les compte, puis relance `verifier` |
| `controler` | Contrôle qualité mécanique des tickets, hypothèses et exigences du cahier des charges (chiffres sans source, KO sans ticket, hypothèse devenue ticket…) |
| `contre-verifier` | Relance un échantillon d'URLs de l'annexe et compare les codes HTTP |
| `livrables` | `controler`, puis le fichier de travail et l'annexe en .xlsx dans `livrables/` (refusé s'il reste une erreur) |
| `retour` | Lit l'onglet Tickets du fichier validé par le TM (`retour-tm/*.xlsx`) et écrit `retour-tm/tickets.csv` |
| `etape` | `recette.py etape <dossier> <nom> debut|fin [agent] [tokens] [appels]` : durée et coût de chaque étape dans `donnees/metriques.json` |
| `bilan` | Mesures de la recette et journal local, pour `recette-amelioration` |

`page.py <dossier> <url>…` enregistre le HTML brut de pages de la préprod (sans JavaScript, accès de la préprod géré) dans `donnees/html/`, pour les agents.

## Ce qu'il faut dans le dossier de recette

| Fichier | Rôle |
|---|---|
| `profil.json` | Adresses, pages stratégiques, gabarits, profil client (modèle : `templates/profil.example.json`) |
| `acces-preprod.local.json` | Identifiants de la préprod, si elle est protégée (jamais commité) |
| `exports/preprod/*.csv` | Exports Screaming Frog de la préprod |
| `exports/ancien-site/internal_all.csv` | Crawl du site actuel en prod |
| `plan-redirections.csv` | Facultatif : ancienne URL ; nouvelle URL |

Screaming Frog peut être en français ou en anglais. Un export est reconnu par son nom de fichier, sinon par son contenu (colonnes, codes HTTP des lignes) ; une colonne par son nom exact, sinon par ses mots-clés dans n'importe quel ordre. Si un export reste « non reconnu » dans le diagnostic `exports`, indique-le dans `exports/preprod/correspondance.json`, par exemple `{"internal_all": "mon-export.csv"}`.

## Ce qu'ils produisent

| Fichier | Contenu |
|---|---|
| `donnees/resultats.json` | Un résultat par contrôle : statut, type de preuve, preuve, détails, nombre de lignes dans l'annexe |
| `annexe/<Onglet>.csv` | Les listes d'URLs, une ligne par cas, avec la colonne Contrôle |
| `donnees/verification.json` | Cohérence : chaque nombre annoncé est recompté dans l'annexe, et la liste des contrôles encore sans résultat |
| `donnees/inventaire-exports.json` | Exports reconnus, colonnes introuvables, noindex global de la préprod détecté ou non |
| `donnees/slugs.csv`, `pages-strategiques.csv`, `hn-gabarits.csv`, `gabarits-html-brut.json`, `blocages-preprod.json` | Données préparées pour les contrôles faits par les agents |
| `donnees/resultats-agents/<agent>.json` | Résultats écrits par les agents, enregistrés par `poser` |
| `donnees/tickets.json`, `hypotheses.json`, `cdc.json` | Tickets, hypothèses et exigences du cahier des charges, rédigés par les agents |
| `donnees/controle-livrables.json`, `contre-verification.json` | Contrôle qualité mécanique et contre-vérification |
| `livrables/<Client> - Recette SEO préprod - <date>.xlsx` et `... - Annexe - <date>.xlsx` | Les deux livrables, prêts pour Google Sheets |

## Contrôles couverts par les scripts

57 des 79 contrôles du référentiel (avec `lighthouse`). Les autres demandent un jugement ou le navigateur et restent aux agents. `verifier` les liste dans `sans_resultat_par_source` :
- navigateur : responsive, menu mobile, fil d'Ariane, pop-ins, texte en image, filtres, pagination dans la page ;
- jugement sur les données préparées : langue et cohérence des slugs, taxonomie des titles et descriptions, Hn décoratives, comparaison du HTML brut avec le rendu JavaScript ;
- documents : robots.txt prévu pour la prod, réglage noindex du back-office, structure multilingue validée, hreflang.

## Règles respectées

- Chaque nombre vient d'un comptage sur un fichier ou d'une requête enregistrée. Une colonne introuvable donne « Non testable », jamais une estimation.
- Le noindex global de la préprod est détecté (au moins 90 % des pages HTML en noindex) et ignoré pour juger l'indexabilité de chaque page.
- Les contrôles faits sur un échantillon de gabarits passent en « Partiel » quand rien n'est trouvé.
- Les redirections ne sont jamais suivies automatiquement : chaque saut est relevé.

## Limites connues

- La lecture des exports français est confirmée sur de vrais exports de Screaming Frog 24.3 (libellés, noms de fichiers, sous-dossiers de l'« Exportation multiple »).
- Les données structurées sont contrôlées sur leur présence, pas sur leur validité selon schema.org.
- Le crawl par le serveur MCP de Screaming Frog n'a pas encore été testé sur un vrai poste : les noms de champs des exports NDJSON sont lus comme des en-têtes, et `recette.py exports` dit ce qui n'est pas compris.

## Tests

```bash
python -m unittest discover -s plugins/recette/tests
```

Le jeu d'essai lance une fausse préprod locale protégée par mot de passe, avec de faux exports et des anomalies connues. Chaque anomalie doit être trouvée, avec le bon nombre.
