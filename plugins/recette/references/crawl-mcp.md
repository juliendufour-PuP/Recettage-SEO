# Crawl par le serveur MCP de Screaming Frog

Le plugin peut lancer lui-même les crawls et récupérer les exports grâce au serveur MCP officiel de Screaming Frog. Sans lui, le TM fait les crawls à la main (voir `templates/exports-screaming-frog.md`) : les scripts lisent les deux de la même façon.

Source : https://www.screamingfrog.co.uk/seo-spider/mcp/ (lue le 8 novembre 2026). La page ne documente pas Claude Code. Le branchement ci-dessous utilise le mode « Streamable HTTP », le seul qu'un client autre que Claude Desktop puisse joindre. **Il reste à confirmer sur un vrai poste.**

## 1. Installation (une fois par poste)

1. Screaming Frog SEO Spider **à jour, avec licence** : le MCP ne fonctionne pas en version gratuite.
2. Mode de stockage **base de données** (Fichier > Paramètres > Mode de stockage), le réglage par défaut.
3. Fichier > Paramètres > Serveur MCP : accepter et activer **Node.js**, noter le port, puis **Démarrer le serveur MCP**. Le message « MCP Server Active » s'affiche en bas à gauche. Screaming Frog doit rester ouvert pendant la recette.
4. Dans un terminal :
   ```bash
   claude mcp add --transport http screaming-frog http://localhost:11435/mcp -s user
   ```
   Remplace `11435` par le port affiché dans Screaming Frog, puis redémarre Claude Code. La commande `/mcp` doit montrer `screaming-frog` connecté.
5. Dans le même écran de Screaming Frog, laisse **désactivés** les outils Node (exécution de scripts, installation de paquets) : le plugin n'en a pas besoin.

## 2. Ce que le plugin utilise

| Outil MCP | Usage |
|---|---|
| `sf_list_crawls`, `sf_load_crawl` | Retrouver et recharger un crawl déjà fait (le TM choisit) |
| `sf_get_config_spider`, `sf_get_config_sub_schema`, `sf_list_config_categories`, `sf_set_config_spider` | Lire la configuration, appliquer les réglages de la recette, puis remettre celle d'origine |
| `sf_set_crawl_mode`, `sf_crawl`, `sf_crawl_progress` | Lancer un crawl en mode Spider et suivre son avancement |
| `sf_list_filters_for_seo_element`, `sf_export_seo_element_urls` | Exports d'onglets (Interne > Tous, Titles, H1…) |
| `sf_list_bulk_exports`, `sf_generate_bulk_export` | Exports groupés (liens entrants 3xx, 4xx, 5xx, images sans alt, données structurées) |
| `sf_list_reports`, `sf_generate_report` | Rapports (chaînes de redirection, contenu non sécurisé) |
| `sf_task_status` | Attendre la fin de l'écriture d'un export |
| `sf_allowed_base_directory`, `sf_create_directory` | Dossier où Screaming Frog a le droit d'écrire |

Jamais : `sf_run_node_script`, `sf_npm_install`, `sf_write_text_file`, `sf_connect_api`, `sf_disconnect_api`, `sf_clear_crawl`.

## 3. Règles

- **Les noms d'exports ne sont pas écrits en dur.** L'agent lit le catalogue du poste (`sf_list_bulk_exports`, `sf_list_reports`, `sf_list_filters_for_seo_element`) et l'enregistre dans `crawl-mcp/catalogue.json`. Il choisit ensuite l'entrée qui correspond au sens du tableau 4. Si aucune ne correspond clairement, l'export est noté « introuvable » : on ne prend pas un export voisin.
- **La configuration du TM est rendue telle qu'elle était.** Avant tout changement, `sf_get_config_spider` est enregistré dans `crawl-mcp/config-origine.json`. À la fin, même en cas d'échec, l'agent remet cette configuration.
- **Aucun mot de passe ne passe par le MCP.** Si la préprod est protégée, le TM enregistre l'authentification dans Screaming Frog et donne le chemin du fichier dans `profil.json` (`sf.auth_config`). Sans ce fichier, l'agent s'arrête et le dit.
- **Pas de réglage deviné.** Un réglage du tableau de `templates/exports-screaming-frog.md` n'est appliqué que si sa clé est clairement identifiée dans `sf_get_config_sub_schema`. Sinon, il est noté « non appliqué » dans `crawl-mcp/config-appliquee.json`, et l'orchestrateur le signale au TM.
- **Les exports sont demandés en CSV** quand l'outil a un paramètre `export_type`. Sinon, le format rendu est gardé (NDJSON accepté) : `recette.py mcp` convertit.
- **Un export par tranches.** Si un export d'onglet rend moins de lignes que d'URLs crawlées, l'agent le redemande avec `start_index` et `max_rows`. Il nomme alors les fichiers `<code>.partie-1.csv`, `<code>.partie-2.csv`… Le script les assemble.
- Les outils rendent la main tout de suite : l'agent attend avec `sf_crawl_progress` (jusqu'à `crawlRunning` faux) et `sf_task_status`, en espaçant les appels de 30 secondes (`sleep 30` dans Bash), pas en boucle serrée. Un outil refusé parce qu'un crawl tourne se relance après la fin du crawl.

## 4. Exports à demander

Chaque fichier se nomme `<code>.<csv|ndjson>` dans le dossier de sortie.

| Code | Outil | Entrée attendue (libellés anglais de Screaming Frog) |
|---|---|---|
| `internal_all` | `sf_export_seo_element_urls` | Internal > All |
| `page_titles` | `sf_export_seo_element_urls` | Page Titles > All |
| `meta_description` | `sf_export_seo_element_urls` | Meta Description > All |
| `h1` | `sf_export_seo_element_urls` | H1 > All |
| `canonicals` | `sf_export_seo_element_urls` | Canonicals > All |
| `pagination` | `sf_export_seo_element_urls` | Pagination > All |
| `hreflang` | `sf_export_seo_element_urls` | Hreflang > All (site multilingue seulement) |
| `images` | `sf_export_seo_element_urls` | Images > All |
| `exact_duplicates` | `sf_export_seo_element_urls` | Content > Exact Duplicates |
| `near_duplicates` | `sf_export_seo_element_urls` | Content > Near Duplicates |
| `javascript` | `sf_export_seo_element_urls` | JavaScript > All |
| `sitemaps` | `sf_export_seo_element_urls` | Sitemaps > All |
| `redirection_3xx_inlinks` | `sf_generate_bulk_export` | Response Codes > Internal > Redirection (3xx) Inlinks |
| `client_error_4xx_inlinks` | `sf_generate_bulk_export` | Response Codes > Internal > Client Error (4xx) Inlinks |
| `server_error_5xx_inlinks` | `sf_generate_bulk_export` | Response Codes > Internal > Server Error (5xx) Inlinks |
| `images_missing_alt_inlinks` | `sf_generate_bulk_export` | Images > Images Missing Alt Text Inlinks |
| `structured_data` | `sf_generate_bulk_export` | Structured Data > All |
| `redirect_chains` | `sf_generate_report` | Redirects > Redirect Chains |
| `insecure_content` | `sf_generate_report` | Insecure Content |

Ancien site : `internal_all` seulement.

## 5. Déroulé

1. **Dossier de sortie.** `sf_allowed_base_directory` donne `BASE`. L'agent crée `BASE/recettage-seo/<client>-<AAAA-MM-JJ>/ancien-site` et `.../preprod`.
2. **Catalogue** dans `crawl-mcp/catalogue.json`.
3. **Configuration d'origine** dans `crawl-mcp/config-origine.json`.
4. **Ancien site**, sauf si l'orchestrateur donne un crawl à recharger. L'agent lance un crawl standard avec la configuration d'origine du TM : pas d'authentification, robots.txt respecté. Puis il exporte `internal_all`.
5. **Préprod.** Avec `sf.config` dans le profil, l'agent passe ce fichier en `config_path`. Sinon, il applique les réglages du tableau 1 de `templates/exports-screaming-frog.md`, sous les règles du §3. Il ajoute `auth_config_path` si la préprod est protégée, lance le crawl, attend la fin, puis demande les exports du tableau 4.
6. **Remise en état** de la configuration d'origine.
7. **Copie** des fichiers de `BASE/...` vers `DOSSIER/crawl-mcp/<site>/` (même poste : copie simple avec Bash). Si Screaming Frog tourne sur une autre machine, l'agent le dit et s'arrête.
8. **Assemblage** avec `python <SCRIPTS>/recette.py mcp <DOSSIER>`, puis `python <SCRIPTS>/recette.py exports <DOSSIER>`.
9. **Journal** dans `crawl-mcp/journal.md` : crawls (identifiant, date, nombre d'URLs selon `sf_crawl_progress`), réglages appliqués ou non, exports obtenus ou introuvables, et la durée de chaque étape.
