# Recettage SEO : la recette SEO PumpUp pour Claude Code

Un plugin Claude Code qui fait la recette SEO d'un site en préproduction après une refonte, avant sa mise en ligne.

Le TM lance `/recette:lancer <client>`. Le plugin part de la fiche client et du cahier des charges SEO. Il fait les crawls Screaming Frog par son serveur MCP, ou lit les exports du TM. Il passe ensuite en revue les 79 contrôles de la checklist technique PumpUp et contrôle les redirections depuis l'ancien site. Il livre deux fichiers, à ouvrir dans Google Sheets :
- un **fichier de travail** : chaque contrôle avec son statut, sa priorité de 1 à 3 et sa preuve, et les tickets à créer (titre, description, résolution, résultat attendu, validation TM) ;
- une **annexe** : les listes complètes d'URLs à corriger (404, redirections, H1…).

Trois règles :
- aucun chiffre inventé : tout comptage vient d'un script ;
- les constats prouvés sont séparés des hypothèses ;
- une hypothèse ne devient un ticket qu'une fois validée par le TM.

Un contrôle qualité obligatoire vérifie tout avant la livraison.

> **État : v0.4, à tester sur un vrai cas.** La commande `/recette:lancer`, les huit agents, les livrables et le crawl par le MCP Screaming Frog sont en place. Le crawl par MCP n'a pas encore tourné sur un vrai poste.

## Comment se déroule une recette

| Étape | Qui | Ce qui se passe |
|---|---|---|
| 1. Cadrage | `recette-cadrage`, puis **validation du TM** | La fiche client devient le profil de recette : adresses, pages stratégiques, contrôles applicables |
| 2. Crawls | `recette-crawl` (MCP) ou le TM | Le site actuel et la préprod, avec les réglages de la recette |
| 3. Gabarits | `recette-cadrage` | Une URL par type de page, choisie dans le crawl |
| 4. Scripts | scripts Python | 57 contrôles comptés sur les exports et par requêtes, Lighthouse compris |
| 5. Analyse | `recette-live`, `recette-expert`, `recette-cdc` | Le navigateur (responsive, menu mobile, fil d'Ariane, pop-ins, JavaScript), le jugement d'expert, le cahier des charges exigence par exigence, les pistes hors checklist |
| 6. Tickets | `recette-livrable` | Les KO regroupés en tickets prêts pour le développeur |
| 7. Contrôle qualité | `recette-controle` | Recomptage, preuves, priorités, relecture des tickets : « livrable » ou « à corriger » |
| 8. Livrables | `recette-livrable` | Les deux fichiers, déposés dans Google Drive en Google Sheets si le TM le veut |
| 9. Amélioration | `recette-amelioration`, puis **validation du TM** | Mesure de la recette et propositions pour la suivante |

Après la validation des tickets, `/recette:retour` mesure la précision de la recette : les tickets rejetés sont des faux positifs, les tickets ajoutés des oublis.

## Un processus qui s'améliore

En fin de recette, l'agent `recette-amelioration` mesure le déroulé (durée, tokens, couverture, tickets rejetés ou ajoutés par le TM) et le compare aux recettes précédentes. Il propose ensuite au plus 5 améliorations pour aller plus vite, être plus précis et consommer moins de tokens. Les propositions validées par le TM deviennent des consignes que tous les agents appliquent à la recette suivante. Celles qui ne donnent pas le gain annoncé sont retirées.

Une règle ne bouge pas : aucune amélioration ne peut supprimer un contrôle, baisser une priorité ou relever un seuil. Les mesures et les apprentissages restent sur ton poste, dans `~/.claude/recettage-seo/`. Le détail est dans `plugins/recette/references/amelioration-continue.md`.

---

## Installation (une fois par poste)

### Le plus simple : depuis le site audit

Sur audit.preprod-lab.com, clique sur « Installer sur mon poste » : tu télécharges un dossier avec une notice d'une page. En résumé :

1. Installe l'application **Claude** (https://claude.ai/download) et connecte-toi avec ton compte PumpUp.
2. Dans Claude, onglet **Code**, colle cette ligne et valide :
   ```
   /plugin install recette --marketplace juliendufour-PuP/Recettage-SEO
   ```
3. C'est tout. **Python n'est pas à installer** : au premier lancement, la recette utilise celui du poste ou installe un Python privé pour elle seule (sans droits administrateur). **Node.js n'est pas nécessaire** pour une recette préparée par le site audit : les captures du navigateur sont faites par le serveur.

### Installation complète (recette entièrement sur le poste)

Pour faire aussi les crawls et le navigateur sur ton poste :

- **Screaming Frog SEO Spider avec licence** : la version gratuite s'arrête à 500 URLs, ne fait pas le rendu JavaScript et n'a pas de serveur MCP.
- **Node.js** (https://nodejs.org), puis le navigateur piloté :
  ```bash
  claude mcp add playwright -s user -- npx @playwright/mcp@latest
  ```
  Sans lui, les contrôles du navigateur passent en Non testable, sauf si le dossier vient du site audit.
- **Connecteur Google Drive** activé dans Claude (claude.ai > Paramètres > Connecteurs), pour déposer les livrables en Google Sheets. Facultatif.
- **Brancher Screaming Frog** (conseillé) : dans Screaming Frog, Fichier > Paramètres > Serveur MCP, active Node.js, puis « Démarrer le serveur MCP ». Ensuite :
  ```bash
  claude mcp add --transport http screaming-frog http://localhost:11435/mcp -s user
  ```
  Remplace `11435` par le port affiché. Laisse Screaming Frog ouvert pendant la recette. Le détail est dans `plugins/recette/references/crawl-mcp.md`. Sans MCP, tu fais les crawls à la main (`plugins/recette/templates/exports-screaming-frog.md`).

Les performances (Lighthouse, Core Web Vitals) ne se mesurent pas sur une préprod : elles se contrôlent une fois le site en ligne, au contrôle post-refonte.

### Mettre à jour

```
/plugin marketplace update recettage-seo
```

---

## Lancer une recette

Dans Claude Code, ouvert dans le dossier où tu ranges tes recettes :

```
/recette:lancer Montana https://dev.residences-montana.com
```

Indique aussi le dossier où se trouvent la fiche client, le cahier des charges, l'arborescence cible et le plan de redirections. Le plugin crée `Recette-SEO-<Client>/`, puis te pose toutes ses questions en une fois, à l'étape du cadrage. Une recette interrompue reprend où elle s'était arrêtée : il suffit de relancer la commande.

### Préprod protégée par un mot de passe

Le plugin ne tape jamais un mot de passe et ne le recopie nulle part.
- **Scripts** : copie `plugins/recette/templates/acces-preprod.local.example.json` en `Recette-SEO-<Client>/acces-preprod.local.json` et remplis-le. Ce fichier reste sur ton poste.
- **Screaming Frog** : enregistre l'authentification dans Screaming Frog et indique le chemin du fichier dans `profil.json` (`"sf": {"auth_config": "..."}`).
- **Navigateur** : Playwright ne passe pas une authentification HTTP sans configuration. Crée un fichier hors du dossier de recette, par exemple `~/.claude/playwright-preprod.json` :
  ```json
  {"browser": {"contextOptions": {"httpCredentials": {"username": "...", "password": "..."}}}}
  ```
  Puis réinstalle Playwright avec `--config` :
  ```bash
  claude mcp add playwright -s user -- npx @playwright/mcp@latest --config ~/.claude/playwright-preprod.json
  ```
  Ce réglage reste à confirmer sur une vraie préprod protégée. Sans lui, les contrôles du navigateur passent en Non testable, avec la raison.

### Après la validation des tickets

Dans Google Sheets : Fichier > Télécharger > Microsoft Excel (.xlsx). Dépose le fichier dans `Recette-SEO-<Client>/retour-tm/`, puis lance :

```
/recette:retour Montana
```

---

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `plugins/recette/skills/lancer/`, `skills/retour/` | Les commandes `/recette:lancer` et `/recette:retour` |
| `plugins/recette/agents/` | Les huit agents : cadrage, crawl, live, expert, cdc, livrable, controle, amelioration |
| `plugins/recette/references/referentiel-controles.csv` | Les 79 contrôles : la checklist technique PumpUp, les contrôles de refonte (redirections) et les ajouts proposés, avec leur priorité, leur méthode et ce qui les fait passer en KO |
| `plugins/recette/references/regles-recette.md` | Les règles communes : preuves, statuts, priorité, interdiction des chiffres inventés |
| `plugins/recette/references/crawl-mcp.md` | Le crawl par le serveur MCP de Screaming Frog |
| `plugins/recette/references/amelioration-continue.md` | Mesures, garde-fous et boucle d'amélioration |
| `plugins/recette/templates/` | Fiche client, profil, exports Screaming Frog, structure des livrables, modèle d'accès à la préprod |
| `plugins/recette/scripts/` | Scripts de comptage, de requêtes, de contrôle qualité et de livrables (voir son README) |
| `plugins/recette/tests/` | Jeu d'essai avec une fausse préprod locale : `python -m unittest discover -s plugins/recette/tests` |
| `docs/prd.md` | Le plan du processus |
