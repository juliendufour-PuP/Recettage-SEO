# Recettage SEO : la recette SEO PumpUp pour Claude Code

Un plugin Claude Code qui fait la recette SEO d'un site en préproduction après une refonte, avant sa mise en ligne.

À partir de la fiche client, du cahier des charges SEO et des exports Screaming Frog, il passe en revue la checklist technique PumpUp, contrôle les redirections depuis l'ancien site et livre :
- un **fichier de travail** (Google Sheets) : chaque contrôle avec son statut, sa priorité de 1 à 3, sa preuve, et les tickets à créer (titre, description, résolution, résultat attendu) ;
- une **annexe** : les listes complètes d'URLs à corriger (404, redirections, H1…).

Trois règles : aucun chiffre inventé (tout comptage vient d'un script), les constats prouvés sont séparés des hypothèses, et une hypothèse ne devient un ticket qu'une fois validée par le TM.

> **État : en construction (v0.1).** Le référentiel des contrôles et les gabarits sont prêts. Les scripts, les agents et la commande `/recette:lancer` arrivent dans les prochaines versions.

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

1. Copie `plugins/recette/templates/fiche-client.md` dans un dossier `Recette-SEO-<Client>` et remplis-la.
2. Fais les crawls Screaming Frog avec les réglages de `plugins/recette/templates/exports-screaming-frog.md` : la préprod et le site actuel en prod. Dépose les exports dans `exports/preprod/` et `exports/ancien-site/`.
3. Si la préprod est protégée par un mot de passe, copie `acces-preprod.local.example.json` en `acces-preprod.local.json` et remplis-le. Ce fichier reste sur ton poste.
4. Mets le cahier des charges SEO, l'arborescence cible et le plan de redirections dans le dossier.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `plugins/recette/references/referentiel-controles.csv` | Les contrôles : la checklist technique PumpUp, les contrôles de refonte (redirections) et les ajouts proposés, avec leur priorité, leur méthode et ce qui les fait passer en KO |
| `plugins/recette/references/regles-recette.md` | Les règles communes : preuves, statuts, priorité, interdiction des chiffres inventés |
| `plugins/recette/templates/` | Fiche client, exports Screaming Frog, structure des livrables, modèle d'accès à la préprod |
