# Structure des livrables

Deux classeurs .xlsx générés par `recette.py livrables`, pensés pour Google Sheets : l'agent `recette-livrable` les dépose dans Google Drive convertis en Google Sheets si le TM le veut, sinon le TM les importe (glisser dans Drive, puis Ouvrir avec > Google Sheets). Les identifiants (T-001, H-001, CDC-01), les priorités et les nombres sont calculés par le script.

## Fichier 1 : base de travail du TM

`<Client> - Recette SEO préprod - <AAAA-MM-JJ>`

### Onglet Synthèse

- Client, préprod, date de la recette, exports utilisés (nom et date de chaque fichier).
- Nombre de contrôles par statut (OK, KO, Partiel, Non testable, Non applicable, Après mise en ligne).
- Nombre de tickets par priorité, et ceux qui bloquent la mise en ligne.
- Ce qui n'a pas été testé et pourquoi.

Tous les chiffres sont calculés par formule à partir des autres onglets, jamais saisis.

### Onglet Recette

Une ligne par contrôle du référentiel, dans l'ordre du référentiel.

| Colonne | Contenu |
|---|---|
| ID | Identifiant du référentiel (ex. COD-02) |
| Bloc | Technique, Contenu, Refonte |
| Catégorie | Reprise du référentiel |
| Contrôle | Reprise du référentiel |
| Priorité (1-3) | Après application de la règle de relèvement |
| Statut | OK, KO, Partiel, Non testable, Non applicable, Après mise en ligne |
| Type de preuve | Constat export, Constat observé, Hypothèse |
| Preuve | Fichier et colonne, ou URL et extrait, ou capture |
| URLs concernées | Nombre calculé par script |
| Lien annexe | Lien vers l'onglet de l'annexe |
| Ticket | ID du ticket créé, s'il y en a un |
| Commentaire | Raison d'un relèvement de priorité, précisions |

### Onglet Tickets

Une ligne par ticket. Un ticket peut regrouper plusieurs contrôles quand la correction est la même.

| Colonne | Contenu |
|---|---|
| ID ticket | T-001, T-002… |
| Contrôles | IDs du référentiel concernés |
| Priorité (1-3) | La plus haute des contrôles regroupés |
| Titre | Court, commence par un verbe d'action |
| Description du problème | Ce qui ne va pas, sur quelles pages, avec le nombre d'URLs |
| **Résolution** | Ce que le développeur doit faire |
| **Résultat attendu** | Ce qu'on doit constater une fois la correction faite (sert aussi de critère pour relancer la recette) |
| URLs d'exemple | 3 à 5 URLs |
| Lien annexe | Liste complète |
| Type de preuve | Constat export ou Constat observé (jamais Hypothèse) |
| Bloque la mise en ligne | oui (avec le motif) ou non |
| Validation TM | À valider, Validé, Rejeté |
| Commentaire TM | |

### Onglet Hypothèses

Les pistes hors référentiel ou non prouvées. Le TM les valide ici avant qu'elles ne deviennent des tickets.

| Colonne | Contenu |
|---|---|
| ID | H-001… |
| Sujet | |
| Constat ou raisonnement | Ce qui a été vu, et pourquoi c'est une hypothèse |
| Pour confirmer | L'information ou le test qui manque |
| Priorité proposée (1-3) | |
| Décision TM | À valider, Validé (devient un ticket), Rejeté |

### Onglet Cahier des charges

Une ligne par exigence du cahier des charges SEO, dans son ordre.

| Colonne | Contenu |
|---|---|
| ID | CDC-01… |
| Exigence | Telle qu'écrite dans le cahier des charges |
| Source dans le cahier des charges | Section et page |
| Statut | Conforme, Non conforme, Partiel, Non testable, Après mise en ligne |
| Preuve | Contrôle lié, fichier et colonne, ou URL et extrait |
| Contrôles liés | IDs du référentiel |
| Ticket | ID du ticket, s'il y en a un |

### Onglet Après mise en ligne

Contrôles à faire en prod : ceux du référentiel marqués `apres_mel`, la levée des blocages de la préprod (PRE-02) et les données réelles des Core Web Vitals.

## Fichier 2 : annexe

`<Client> - Recette SEO préprod - Annexe - <AAAA-MM-JJ>`

Un onglet par liste, nommé comme dans la colonne `onglet_annexe` du référentiel (Liens-internes-4xx, Redirections, H1…). En tête de chaque onglet : le contrôle concerné, le fichier source et la date de l'export. Les lignes sont écrites par script directement à partir des exports et des requêtes, sans retouche par l'IA.

L'onglet Redirections contient : ancienne URL, cible prévue (plan de redirections), cible obtenue, code, nombre de sauts, cible indexable, statut.
