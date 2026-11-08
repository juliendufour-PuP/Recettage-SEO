# Recettage SEO : la recette SEO PumpUp pour Claude Code

Un plugin Claude Code qui fait la recette SEO d'un site en préproduction après une refonte, avant sa mise en ligne.

À partir de la fiche client, du cahier des charges SEO et des exports Screaming Frog, il passe en revue la checklist technique PumpUp, contrôle les redirections depuis l'ancien site et livre :
- un **fichier de travail** (Google Sheets) : chaque contrôle avec son statut, sa priorité de 1 à 3, sa preuve, et les tickets à créer (titre, description, résolution, résultat attendu) ;
- une **annexe** : les listes complètes d'URLs à corriger (404, redirections, H1…).

Trois règles : aucun chiffre inventé (tout comptage vient d'un script), les constats prouvés sont séparés des hypothèses, et une hypothèse ne devient un ticket qu'une fois validée par le TM.

> **État : en construction (v0.3).** Le référentiel des contrôles, les gabarits, les scripts de comptage (56 contrôles sur 79 calculés automatiquement) et l'agent d'amélioration continue sont prêts. Les autres agents et la commande `/recette:lancer` arrivent dans les prochaines versions.

## Un processus qui s'améliore

En fin de recette, l'agent `recette-amelioration` mesure le déroulé (durée, tokens, couverture, tickets rejetés ou ajoutés par le TM), le compare aux recettes précédentes et propose au plus 5 améliorations pour aller plus vite, être plus précis et consommer moins de tokens. Les propositions validées par le TM deviennent des consignes que tous les agents appliquent à la recette suivante. Celles qui ne donnent pas le gain annoncé sont retirées.

Une règle ne bouge pas : aucune amélioration ne peut supprimer un contrôle, baisser une priorité ou relever un seuil. Les mesures et les apprentissages restent sur ton poste, dans `~/.claude/recettage-seo/`. Le détail est dans `plugins/recette/references/amelioration-continue.md`.

---

## Installation (5 minutes, une fois par poste)

### 1. Prérequis

- **Claude Code** installé et connecté avec ton compte PumpUp.
- **Node.js** : https://nodejs.org (pour le navigateur piloté).
- **Python 3.10 ou plus récent** : https://www.python.org (pour les scripts de comptage). Sous Windows, coche « Add Python to PATH » à l'installation.
- **Screaming Frog SEO Spider avec licence** : la version gratuite s'arrête à 500 URLs et ne fait pas le rendu JavaScript.
- **Connecteur Google Drive / Sheets** activé dans Claude (claude.ai > Paramètres > Connecteurs), pour créer les deux fichiers.

### 2. Installer le navigateur piloté (Playwright)

Dans un terminal :
```bash
claude mcp add playwright -s user -- npx @playwright/mcp@latest
```

### 3. Installer le plugin

Dans Claude Code :
```
/plugin marketplace add juliendufour-PuP/Recettage-SEO
/plugin install recette@recettage-seo
```
Redémarre Claude Code.

### Mettre à jour

```
/plugin marketplace update recettage-seo
```

---

## Préparer une recette

1. Copie `plugins/recette/templates/fiche-client.md` dans un dossier `Recette-SEO-<Client>` et remplis-la. En attendant les agents, reporte-la dans `profil.json` (modèle `profil.example.json`).
2. Fais les crawls Screaming Frog avec les réglages de `plugins/recette/templates/exports-screaming-frog.md` : la préprod et le site actuel en prod. Dépose les exports dans `exports/preprod/` et `exports/ancien-site/`.
3. Si la préprod est protégée par un mot de passe, copie `acces-preprod.local.example.json` en `acces-preprod.local.json` et remplis-le. Ce fichier reste sur ton poste.
4. Mets le cahier des charges SEO, l'arborescence cible et le plan de redirections dans le dossier.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `plugins/recette/references/referentiel-controles.csv` | Les contrôles : la checklist technique PumpUp, les contrôles de refonte (redirections) et les ajouts proposés, avec leur priorité, leur méthode et ce qui les fait passer en KO |
| `plugins/recette/references/regles-recette.md` | Les règles communes : preuves, statuts, priorité, interdiction des chiffres inventés |
| `plugins/recette/templates/` | Fiche client, profil pour les scripts, exports Screaming Frog, structure des livrables, modèle d'accès à la préprod |
| `plugins/recette/scripts/` | Scripts de comptage et de requêtes (voir son README) |
| `plugins/recette/agents/recette-amelioration.md` | Agent d'amélioration continue |
| `plugins/recette/references/amelioration-continue.md` | Mesures, garde-fous et boucle d'amélioration |
| `plugins/recette/tests/` | Jeu d'essai avec une fausse préprod locale |
