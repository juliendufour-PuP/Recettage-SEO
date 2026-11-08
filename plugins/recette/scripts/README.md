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

## Contrôles couverts par les scripts

56 des 79 contrôles du référentiel. Les autres demandent un jugement ou le navigateur et restent aux agents. `verifier` les liste dans `sans_resultat_par_source` :
- navigateur : responsive, menu mobile, fil d'Ariane, pop-ins, Lighthouse, texte en image, filtres, pagination dans la page ;
- jugement sur les données préparées : langue et cohérence des slugs, taxonomie des titles et descriptions, Hn décoratives, comparaison du HTML brut avec le rendu JavaScript ;
- documents : robots.txt prévu pour la prod, réglage noindex du back-office, structure multilingue validée, hreflang.

## Règles respectées

- Chaque nombre vient d'un comptage sur un fichier ou d'une requête enregistrée. Une colonne introuvable donne « Non testable », jamais une estimation.
- Le noindex global de la préprod est détecté (au moins 90 % des pages HTML en noindex) et ignoré pour juger l'indexabilité de chaque page.
- Les contrôles faits sur un échantillon de gabarits passent en « Partiel » quand rien n'est trouvé.
- Les redirections ne sont jamais suivies automatiquement : chaque saut est relevé.

## Limites connues

- La lecture des exports français est testée sur des exports simulés (libellés traduits, mots dans un autre ordre, noms de fichiers quelconques) ; les libellés exacts de la version française restent à confirmer sur un vrai export, avec `recette.py exports`.
- Les données structurées sont contrôlées sur leur présence, pas sur leur validité selon schema.org.

## Tests

```bash
python -m unittest discover -s plugins/recette/tests
```

Le jeu d'essai lance une fausse préprod locale protégée par mot de passe, avec de faux exports et des anomalies connues. Chaque anomalie doit être trouvée, avec le bon nombre.
