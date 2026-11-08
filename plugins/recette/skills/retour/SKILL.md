---
name: retour
description: Retour du TM après la validation des tickets d'une recette SEO PumpUp - lit le fichier de travail validé (tickets validés, rejetés, ajoutés), mesure la précision de la recette (faux positifs et oublis), la compare aux recettes précédentes et propose des améliorations du processus, validées par le TM. À utiliser quand l'utilisateur a validé les tickets d'une recette, demande le retour ou le bilan d'une recette, ou veut améliorer le plugin à partir d'une recette terminée.
argument-hint: "<client ou dossier de la recette>"
---

# /recette:retour : ce que la validation du TM apprend à la recette

Un ticket **rejeté** par le TM est un faux positif. Un ticket **ajouté** par le TM (sans contrôle d'origine) est un oubli de la recette : c'est la mesure la plus importante.

## Repères

Les mêmes que `/recette:lancer` : `PLUGIN`, `REFS`, `SCRIPTS`, `APPRENTISSAGES`, `PY`. `DOSSIER` est le dossier de la recette (`Recette-SEO-<Client>` dans le répertoire de travail, ou le chemin donné).

## Étapes

1. **Le fichier validé.** Il faut le fichier de travail avec la colonne « Validation TM » remplie, dans `DOSSIER/retour-tm/`. Depuis Google Sheets : Fichier > Télécharger > Microsoft Excel (.xlsx). S'il n'y est pas, dis-le au TM et arrête-toi. Les tickets ajoutés par le TM sont des lignes de l'onglet Tickets avec la colonne « Contrôles » vide.
2. `PY SCRIPTS/recette.py retour DOSSIER` : écrit `retour-tm/tickets.csv`. En cas d'erreur, donne-la au TM.
3. Lance `recette-amelioration` avec `MODE=retour`.
4. **Validation.** Présente au TM le bilan de précision (tickets validés, rejetés, ajoutés : chiffres de `donnees/bilan.json`), les propositions (ID, axe, gain mesurable, type) et les apprentissages à retirer. Relance `recette-amelioration` avec `MODE=validation` et ses décisions.
5. Si un ticket ajouté par le TM révèle un contrôle absent du référentiel, ou si un contrôle est souvent rejeté, propose au TM d'envoyer l'évolution au mainteneur du plugin (ticket prêt dans `ameliorations.md`). Rien n'est envoyé sans son accord.

## Règles

- Les chiffres viennent de `donnees/bilan.json`, jamais d'un comptage de ta part.
- Tu ne modifies ni le fichier du TM, ni le plugin.
