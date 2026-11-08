# Exports Screaming Frog à fournir

> **Screaming Frog en français ou en anglais : les deux fonctionnent.** Les scripts reconnaissent chaque export par son nom de fichier, et sinon par son contenu (colonnes présentes, codes HTTP des lignes). Les colonnes sont retrouvées par leurs mots-clés, quel que soit leur ordre (« Title 1 Length », « Longueur du titre 1 »). Les valeurs des cellules ne posent pas de problème : l'indexabilité est jugée sur le code HTTP, la canonical et la directive « noindex », identiques dans les deux langues.
>
> Les menus sont donnés ci-dessous en français, avec l'anglais entre parenthèses. Si un libellé diffère sur ta version, corrige ce fichier.

Dépose tous les fichiers dans `Recette-SEO-<Client>/exports/preprod/` et `Recette-SEO-<Client>/exports/ancien-site/`, **sans les renommer**. Format CSV uniquement.

**Avant la recette, lance le diagnostic :**

```bash
python plugins/recette/scripts/recette.py exports Recette-SEO-<Client>
```

Il dit, pour chaque fichier, comment il a été reconnu (par son nom ou par son contenu), quelles colonnes ont été comprises, lesquelles manquent, et quels exports indispensables sont absents. Un fichier resté « non reconnu » se déclare dans `exports/preprod/correspondance.json`, par exemple `{"internal_all": "mon-export.csv"}`.

**Indispensables pour les scripts :** `internal_all` (préprod et ancien site), les trois exports d'inlinks 3xx, 4xx et 5xx, `redirect_chains`, `insecure_content` et `images_missing_alt_inlinks`. Les autres servent aux agents. Un export manquant fait passer ses contrôles en « Non testable » ; rien n'est deviné.

## 1. Réglages du crawl de la préprod

Tout se règle dans **Configuration du crawl** (Configuration). Enregistre ces réglages une fois pour toutes (Fichier > Configuration > Enregistrer sous) et recharge-les à chaque recette.

| Écran | Réglage | Valeur |
|---|---|---|
| Authentification (Authentication) | Identifiants | Ceux de la préprod (basic auth ou formulaire) |
| robots.txt | Mode | Ignorer robots.txt (la préprod bloque souvent tout) |
| Spider > Crawl | Liens de page | Pagination : cocher Crawl. Hreflang : Crawl si site multilingue. AMP : Crawl + Stocker si le site en a. Liens non explorables : Stocker |
| Spider > Crawl | Comportement du crawl | Cocher « Suivi interne nofollow ». « Crawl de tous les sous-domaines » seulement si le site en utilise plusieurs |
| Spider > Crawl | Sitemaps XML | Cocher « Sitemaps XML liés au crawl », puis « Crawler ces sitemaps » avec l'URL du sitemap de la préprod |
| Spider > Avancé (Advanced) | Problèmes | **Décocher « Ignorer les URL non indexables pour les problèmes »** : sur une préprod en noindex, sinon presque tous les problèmes sont masqués |
| Spider > Avancé | Directives | « Respecter noindex », « Respecter les versions canoniques », « Respecter Suiv./Préc. » : décochés |
| Spider > Avancé | Suivi | Cocher « Toujours suivre les redirections » et « Toujours suivre les versions canoniques » |
| Spider > Avancé | Images | Cocher « Extraire des images de l'attribut srcset » |
| Spider > Avancé | Délais | Délai de réponse : 20 s (30 si la préprod est lente). Tentatives de réponse 5xx : 1 |
| Spider > Rendu (Rendering) | Rendu | JavaScript, préréglage Googlebot Mobile : Smartphone, captures d'écran cochées |
| Spider > Rendu | Erreurs | Cocher « Activer le signalement des erreurs JavaScript ». Délai AJAX : 5 s (8 à 10 si les captures sont vides) |
| Spider > Extraction | Données structurées | Cocher JSON-LD, Microdata, RDFa et la validation Schema.org |
| Spider > Extraction | HTML | Cocher « Stocker le HTML » et « Stocker le HTML rendu » |
| Contenu > Doublons (Content > Duplicates) | Quasi-doublons | Activer les quasi-doublons |
| Analyse du crawl (Crawl Analysis) | Configurer | Tout cocher, puis lancer l'analyse à la fin du crawl |

## 2. Exports de la préprod

| Code utilisé dans le référentiel | Export (menus anglais, même emplacement en français) |
|---|---|
| `internal_all` | Onglet Internal (Interne), filtre All (Tous) > Export |
| `redirection_3xx_inlinks` | Bulk Export > Response Codes > Internal > Redirection (3xx) Inlinks |
| `client_error_4xx_inlinks` | Bulk Export > Response Codes > Internal > Client Error (4xx) Inlinks |
| `server_error_5xx_inlinks` | Bulk Export > Response Codes > Internal > Server Error (5xx) Inlinks |
| `redirect_chains` | Reports > Redirects > Redirect Chains |
| `insecure_content` | Reports > Insecure Content |
| `page_titles` | Onglet Page Titles, filtre All > Export |
| `meta_description` | Onglet Meta Description, filtre All > Export |
| `h1` | Onglet H1, filtre All > Export |
| `canonicals` | Onglet Canonicals, filtre All > Export |
| `pagination` | Onglet Pagination, filtre All > Export |
| `hreflang` | Onglet Hreflang, filtre All > Export (site multilingue seulement) |
| `images` | Onglet Images, filtre All > Export |
| `images_missing_alt_inlinks` | Bulk Export > Images > Images Missing Alt Text Inlinks |
| `structured_data` | Bulk Export > Structured Data > All |
| `exact_duplicates` | Onglet Content, filtre Exact Duplicates > Export |
| `near_duplicates` | Onglet Content, filtre Near Duplicates > Export |
| `javascript` | Onglet JavaScript, filtre All > Export |
| `sitemaps` | Onglet Sitemaps, filtre All > Export |
| `all_outlinks` | Bulk Export > Links > All Outlinks (pour PRE-01, peut être lourd) |

## 3. Crawl du site actuel en prod

Crawl standard du site en ligne, sans authentification ni rendu JavaScript, robots.txt respecté. Un seul export suffit :

| Code | Export |
|---|---|
| `ancien_internal_all` | Onglet Internal (Interne), filtre All (Tous) > Export, déposé dans `exports/ancien-site/` |

Les URLs en 200 de cet export sont testées une à une sur la préprod pour les contrôles RED-01 à RED-05.

## 4. Crawl lancé par le plugin (MCP Screaming Frog)

Si le serveur MCP officiel de Screaming Frog est branché sur Claude Code, `/recette:lancer` fait les deux crawls et les exports lui-même, avec ces réglages, puis rend ta configuration telle qu'elle était. L'installation et les règles sont dans `references/crawl-mcp.md`. Les noms d'exports ne sont pas écrits en dur : l'agent les lit dans le catalogue de ton poste, quelle que soit la langue installée.
