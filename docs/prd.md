# Recettage SEO : plan du processus

Plugin Claude Code utilisé par les traffic managers (TM) de PumpUp pour faire la recette SEO d'un site en préproduction après une refonte, avant sa mise en ligne.

## Besoin

- Automatiser la recette SEO de la préprod sans rien rater.
- Éviter les erreurs et les oublis.

## Entrées fournies par le TM

- La fiche client : activité, priorités, cible, stratégie locale ou internationale, limitations techniques connues, pages stratégiques.
- Le cahier des charges SEO du client.
- Les exports Screaming Frog de la préprod et du site actuel en prod (le second est obligatoire, pour contrôler les redirections).
- L'accès à la préprod, l'URL de son sitemap et de son robots.txt.
- La checklist technique PumpUp, transformée en référentiel de 79 contrôles.

## Livrables

- Un fichier de travail pour le TM : chaque contrôle avec son statut, sa priorité de 1 à 3 et sa preuve, plus les tickets à créer (titre, description, résolution, résultat attendu, validation TM).
- Une annexe : les listes complètes d'URLs à corriger.
- Plus tard (Temps 2) : la création automatique des tickets dans l'outil du client.

## Règles

- Aucun chiffre inventé : tout comptage vient d'un script.
- Les constats prouvés sont séparés des hypothèses. Une hypothèse ne devient un ticket qu'une fois validée par le TM.
- L'IA peut aller au-delà des documents PumpUp, mais ces pistes restent des hypothèses à valider.
- Un contrôle qualité est obligatoire avant la livraison.

## Déroulé

1. Le TM lance `/recette:lancer`.
2. Cadrage : la fiche client devient le profil de recette (contrôles applicables, pages stratégiques, gabarits).
3. Scripts : comptages sur les exports, croisement du sitemap et du crawl, test des anciennes URLs sur la préprod, analyse des gabarits.
4. Navigateur : responsive, menu mobile, fil d'Ariane, pop-ins, Lighthouse.
5. Cahier des charges : chaque exigence vérifiée une par une.
6. Hors référentiel : les pistes de l'IA, toutes en hypothèses.
7. Contrôle qualité : chaque chiffre recompté, chaque point relié à sa preuve.
8. Livrables : le fichier de travail et l'annexe.
9. Amélioration continue : mesure de la recette, comparaison avec les précédentes, propositions validées par le TM.
10. Après la validation des tickets, le TM lance `/recette:retour` : les tickets rejetés et ajoutés mesurent la précision de la recette.
