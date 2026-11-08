# Amélioration continue du processus de recette

À la fin de chaque recette, l'agent `recette-amelioration` mesure le déroulé, le compare aux recettes précédentes et propose des améliorations sur trois axes : **vitesse**, **précision** et **coût en tokens**. Ce qui marche est retenu dans un fichier d'apprentissages que tous les agents relisent à la recette suivante. Ce qui ne marche pas est retiré.

## 1. Garde-fou : l'exhaustivité passe avant tout

Le besoin premier reste de **ne rien rater**. Une amélioration ne peut donc jamais :
- supprimer un contrôle, le sauter ou le réduire à un échantillon plus petit ;
- baisser une priorité ou relever un seuil pour faire disparaître des anomalies ;
- transformer une hypothèse en constat, ou un « Non testable » en OK ;
- inventer un chiffre : chaque gain annoncé vient de `donnees/bilan.json` ou du journal.

Toute proposition qui touche au périmètre des contrôles, au référentiel ou aux seuils est une **évolution du plugin**. Elle ne s'applique jamais seule : le mainteneur du dépôt la relit.

## 2. Les mesures (calculées par script, jamais estimées)

`python scripts/recette.py bilan <dossier>` produit `donnees/bilan.json` et ajoute une ligne au journal local.

| Axe | Mesure | Source |
|---|---|---|
| Vitesse | Durée de chaque étape et durée totale | `donnees/metriques.json`, rempli par l'orchestrateur |
| Coût | Tokens et appels d'outils de chaque agent, tokens par contrôle traité | `donnees/metriques.json` (valeurs rendues par l'outil Agent) |
| Précision | Contrôles Non testable et leurs causes, erreurs de vérification, tickets rejetés et tickets ajoutés par le TM | `resultats.json`, `verification.json`, `retour-tm/` |
| Couverture | Part des contrôles applicables qui ont un résultat | `resultats.json` |

Une mesure absente (tokens non rendus, retour du TM pas encore fait) est notée `null` et présentée comme « non mesuré ».

**Précision :** un ticket **rejeté** par le TM est un faux positif. Un ticket **ajouté** par le TM (sans contrôle d'origine) est un manque : c'est la mesure la plus importante, puisqu'elle dit ce que la recette a raté.

## 3. Fichiers

Les apprentissages et le journal restent sur le poste du TM, dans `~/.claude/recettage-seo/` (modifiable avec la variable d'environnement `RECETTAGE_SEO_HOME`). Ils ne sont pas dans le plugin, pour ne pas être écrasés à chaque mise à jour, et ne sont jamais publiés.

| Fichier | Contenu |
|---|---|
| `~/.claude/recettage-seo/journal.jsonl` | Une ligne par recette : date, client, version du plugin, mesures |
| `~/.claude/recettage-seo/apprentissages.md` | Les règles apprises, avec leur statut |
| `<dossier>/donnees/metriques.json` | Durées et tokens de la recette (rempli par l'orchestrateur) |
| `<dossier>/donnees/bilan.json` | Les mesures de la recette et la comparaison avec l'historique |
| `<dossier>/ameliorations.md` | Les propositions de l'agent pour cette recette |
| `<dossier>/retour-tm/tickets.csv` | Facultatif : export de l'onglet Tickets une fois validé par le TM |

### Format de `metriques.json`

```json
{
  "etapes": [
    {"etape": "scripts", "agent": null, "debut": "2026-11-08T09:00:00", "fin": "2026-11-08T09:04:10",
     "tokens": null, "appels_outils": null},
    {"etape": "navigateur", "agent": "recette-live", "debut": "...", "fin": "...",
     "tokens": 48210, "appels_outils": 63}
  ]
}
```

### Format d'un apprentissage

```markdown
## A-004 · validé
- Portée : tous les clients | client <nom> | CMS <nom>
- Axe : vitesse | précision | coût
- Règle : ce que les agents font différemment, formulé comme une consigne
- Gain attendu : la mesure qui doit bouger, avec sa valeur de départ (issue du bilan)
- Origine : recette <client> du <date>
- Vérifié : recettes où le gain a été mesuré, ou « pas encore »
```

Statuts : `proposé` (écrit par l'agent), `validé` (accepté par le TM), `rejeté`, `retiré` (validé, puis retiré parce que le gain n'a pas été constaté ou qu'il a causé un manque).

Seuls les apprentissages `validé` sont appliqués. L'orchestrateur passe le chemin du fichier à chaque agent, qui lit les règles dont la portée le concerne.

## 4. La boucle

1. **Mesurer** : `recette.py bilan` en fin de recette.
2. **Vérifier les règles en place** : pour chaque apprentissage validé, la mesure annoncée a-t-elle bougé depuis qu'il s'applique ? Si elle ne bouge pas après trois recettes, ou si un manque est apparu, l'agent propose de le retirer.
3. **Proposer** : au plus 5 propositions nouvelles, classées par gain mesuré. Chacune part d'un chiffre du bilan.
4. **Valider** : l'orchestrateur présente les propositions au TM, qui accepte ou refuse. L'agent ne valide jamais ses propres propositions.
5. **Remonter** : les évolutions du plugin sont rédigées dans `ameliorations.md` sous forme de ticket prêt à coller dans le dépôt (titre, constat chiffré, changement proposé, risque sur l'exhaustivité). Elles ne sont envoyées que si l'utilisateur le demande.

## 5. Exemples de pistes, selon les mesures

- **Vitesse** : une étape longue alors que ses contrôles sont faits par script, des requêtes en série qui pourraient passer en parallèle, un agent qui relit des fichiers déjà résumés dans `donnees/`.
- **Coût** : un agent qui lit tout un export au lieu du résumé du script, des captures en pleine résolution là où un relevé texte suffit, un contrôle qualitatif qui pourrait devenir un script.
- **Précision** : un contrôle souvent rejeté par le TM (règle trop stricte sur un CMS), un « Non testable » qui revient toujours pour la même cause (export oublié, colonne mal reconnue), un ticket ajouté par le TM qui révèle un contrôle absent du référentiel.
