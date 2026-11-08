# Règles de la recette SEO

Ces règles s'appliquent à tous les agents. Le contrôle qualité les vérifie une par une.

## 1. Aucun chiffre inventé

- Un comptage (nombre d'URLs, de liens, de pages, de mots, un poids, une durée, un score) vient **toujours d'un script** lancé sur un fichier du dossier de recette ou d'une mesure enregistrée (rapport Lighthouse, réponse HTTP). L'IA ne compte pas et n'estime pas.
- Chaque chiffre du livrable renvoie à son fichier source et, quand c'est possible, à l'onglet de l'annexe qui liste les URLs.
- Pas de chiffre disponible : on écrit « non mesuré » et on dit pourquoi. On n'écrit jamais « environ », « une dizaine », « la plupart ».
- Pas de gain promis (trafic, positions, pourcentage d'amélioration).

## 2. Trois types de preuve

| Type | Ce que c'est | Preuve attendue |
|---|---|---|
| **Constat export** | Tiré des exports Screaming Frog ou des fichiers fournis | Nom du fichier, colonne, nombre d'URLs, onglet de l'annexe |
| **Constat observé** | Vu sur la préprod (requête HTTP, navigateur) | URL, date, code ou extrait HTML, capture |
| **Hypothèse** | Hors des documents PumpUp, déduction, ou point qu'on ne peut pas prouver depuis le site | Raisonnement et ce qu'il faudrait pour confirmer |

Une hypothèse **ne devient jamais un ticket** tant que le TM ne l'a pas validée dans l'onglet Hypothèses.

## 3. Statut d'un contrôle

| Statut | Quand |
|---|---|
| OK | Contrôle fait, aucune anomalie |
| KO | Contrôle fait, au moins une anomalie (règle de la colonne `regle_ko`) |
| Partiel | Contrôle fait sur une partie seulement (échantillon, une partie des gabarits) : on dit laquelle |
| Non testable | Information ou accès manquant : on dit lequel |
| Non applicable | Le profil client exclut le contrôle (colonne `applicabilite`) |
| Après mise en ligne | Ne peut se vérifier qu'en prod (colonne `preprod` = `apres_mel`) : va dans l'onglet Après mise en ligne |

Un contrôle n'est jamais laissé vide. « Non testable » est une réponse honnête, pas un échec.

## 4. Priorité (1 à 3)

1. On part de la priorité du référentiel (celle de la checklist PumpUp, ou la priorité proposée pour les contrôles ajoutés).
2. On monte d'un cran (sans dépasser 1) si l'anomalie touche une page stratégique de la fiche client, ou si elle bloque la mise en ligne.
3. La raison du changement est écrite dans la colonne Commentaire.

Aucune autre modulation. Deux recettes avec les mêmes anomalies donnent les mêmes priorités.

## 5. Colonnes du référentiel (`referentiel-controles.csv`)

Séparateur `;`, encodage UTF-8.

| Colonne | Valeurs |
|---|---|
| `id` | Identifiant stable du contrôle, repris dans les livrables et les tickets |
| `bloc` | Technique, Contenu, Refonte |
| `priorite` | 1, 2 ou 3 |
| `origine` | `checklist` (checklist PumpUp), `decision_tm` (décidé par l'équipe), `proposition` (ajouté, à valider une fois dans le référentiel) |
| `applicabilite` | `toujours`, `international`, `local`, `pagination`, `filtres`, `moteur_interne`, `ecommerce`, `avis`, `blog` (réglé par la fiche client) |
| `preprod` | `testable`, `adapte` (se teste en préprod avec une précaution écrite dans `methode`), `partiel` (une partie maintenant, le reste après mise en ligne), `apres_mel` |
| `source_donnee` | `sf` (exports Screaming Frog), `requetes` (requêtes ciblées de nos scripts), `navigateur` (Playwright), `documents` (fiche client, cahier des charges), `gsc` (Search Console, après mise en ligne). Combinables avec `+` |
| `methode` | Comment on contrôle |
| `regle_ko` | Ce qui fait passer le contrôle en KO |
| `exports_sf` | Exports Screaming Frog utilisés (voir `templates/exports-screaming-frog.md`), séparés par `|` |
| `onglet_annexe` | Onglet de l'annexe qui reçoit la liste des URLs concernées |

## 6. Répartition des sources

Screaming Frog reste la source unique pour tout ce qui se compte à l'échelle du site. On ne relance pas un second crawl complet : deux crawls donneraient deux chiffres différents, et la préprod n'a pas à encaisser une double charge.

Nos propres requêtes et le navigateur complètent, de façon ciblée :
- ce que Screaming Frog ne voit pas (zones header et footer, menu mobile face au menu desktop, pop-ins, redirections selon la langue, recherche interne) ;
- le test des anciennes URLs sur la préprod ;
- l'échantillon de gabarits (un par type de page) ;
- la contre-vérification du contrôle qualité, qui recompte un échantillon d'URLs.

## 7. Ce que le plugin ne fait jamais

- Modifier la préprod ou le back-office.
- Saisir un mot de passe dans un formulaire. Les accès basic auth sont lus dans `acces-preprod.local.json`, qui n'est jamais commité ni copié dans les livrables.
- Envoyer quoi que ce soit au client ou à l'équipe de développement.
