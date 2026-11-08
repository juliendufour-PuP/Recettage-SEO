# Exports Screaming Frog à fournir

> Les noms de menus correspondent à Screaming Frog SEO Spider en version récente (interface en anglais). Ils peuvent changer légèrement selon la version et la langue : au premier usage, vérifie-les et corrige ce fichier si besoin. Les exports peuvent être en français ou en anglais, les scripts lisent les deux.

Dépose tous les fichiers dans `Recette-SEO-<Client>/exports/preprod/` et `Recette-SEO-<Client>/exports/ancien-site/`, sans les renommer. Format CSV uniquement.

**Indispensables pour les scripts :** `internal_all` (préprod et ancien site), les trois exports d'inlinks 3xx, 4xx et 5xx, `redirect_chains`, `insecure_content` et `images_missing_alt_inlinks`. Les autres servent aux agents. Un export manquant fait passer ses contrôles en « Non testable » ; rien n'est deviné. Si un fichier n'est pas reconnu par son nom, déclare-le dans `exports/preprod/correspondance.json`, par exemple `{"internal_all": "mon-export.csv"}`.

## 1. Réglages du crawl de la préprod

| Réglage | Où | Valeur |
|---|---|---|
| Authentification | Configuration > Authentication | Identifiants de la préprod (basic auth ou formulaire) |
| Robots.txt | Configuration > robots.txt | Ignore robots.txt (la préprod bloque souvent tout) |
| Noindex et nofollow | Configuration > Spider > Advanced | Décocher « Respect Noindex » et « Respect Nofollow » |
| Rendu | Configuration > Spider > Rendering | JavaScript (nécessaire pour le contrôle JS-01) |
| Sitemap | Configuration > Spider > Crawl | Cocher « Crawl Linked XML Sitemaps » et ajouter l'URL du sitemap de la préprod |
| Doublons | Configuration > Content > Duplicates | Activer « Enable Near Duplicates » |
| Analyse de crawl | Crawl Analysis > Configure | Tout cocher, puis lancer Crawl Analysis > Start à la fin du crawl |
| Données structurées | Configuration > Spider > Extraction | Cocher JSON-LD, Microdata, RDFa et la validation Schema.org |
| HTML | Configuration > Spider > Extraction | Cocher « Store HTML » et « Store Rendered HTML » |

## 2. Exports de la préprod

| Code utilisé dans le référentiel | Export |
|---|---|
| `internal_all` | Onglet Internal, filtre All > Export |
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

Crawl standard du site en ligne, sans authentification ni rendu JavaScript. Un seul export suffit :

| Code | Export |
|---|---|
| `ancien_internal_all` | Onglet Internal, filtre All > Export |

Les URLs en 200 de cet export sont testées une à une sur la préprod pour les contrôles RED-01 à RED-05.
