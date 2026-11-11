---
name: lancer
description: Lance la recette SEO PumpUp d'un site en préproduction après une refonte, avant sa mise en ligne - cadrage depuis la fiche client, crawls Screaming Frog (par son serveur MCP ou à partir des exports du TM), contrôles par scripts, navigateur, jugement d'expert et cahier des charges, tickets, contrôle qualité, fichier de travail et annexe pour Google Sheets, puis amélioration continue. À utiliser dès que l'utilisateur demande une recette SEO, une recette de préprod, un contrôle SEO avant mise en ligne ou après refonte, ou de reprendre une recette en cours. Reprend automatiquement une recette interrompue.
argument-hint: "<client> [adresse de la préprod] [dossier des documents]"
---

# /recette:lancer : la recette SEO de la préprod

Tu es le chef d'orchestre. Tu ne fais pas les contrôles toi-même : tu lances les scripts et les agents, tu vérifies leurs fichiers entre deux étapes, et tu tiens le TM informé en une ligne par étape. Le TM doit avoir le moins de choses possible à faire : **deux validations** (le profil de recette, puis les propositions d'amélioration), et une question sur Google Drive à la fin.

## Repères

- `PLUGIN` = deux niveaux au-dessus du dossier de ce skill (`<dossier de ce skill>/../..`), en chemin absolu. `REFS` = `PLUGIN/references`, `SCRIPTS` = `PLUGIN/scripts`, `TEMPLATES` = `PLUGIN/templates`. Vérifie que `REFS/regles-recette.md` existe.
- `DOSSIER` = `<répertoire de travail>/Recette-SEO-<Client>` (nom sans espace ni accent), sauf si le TM donne un autre chemin.
- `APPRENTISSAGES` = `~/.claude/recettage-seo/apprentissages.md` (ou `$RECETTAGE_SEO_HOME/apprentissages.md`).
- `PY` = la commande Python 3.10+, donnée par la dernière ligne (`PY=…`) du script d'installation de l'étape 0. Le TM n'a jamais à installer Python lui-même.
- Agents (selon l'installation, avec le préfixe `recette:`) : `recette-cadrage`, `recette-crawl`, `recette-live`, `recette-expert`, `recette-cdc`, `recette-livrable`, `recette-controle`, `recette-amelioration`.
- Chaque lancement d'agent contient au minimum `DOSSIER=`, `REFS=`, `SCRIPTS=`, `APPRENTISSAGES=` (chemins absolus), `PY=`, le `MODE` s'il y en a un, et une phrase de consigne.
- **Mesures** : au début et à la fin de chaque étape, lance `PY SCRIPTS/recette.py etape DOSSIER <étape> debut` puis `... <étape> fin <agent> <tokens> <appels d'outils>`. Les tokens et les appels d'outils sont ceux que l'outil Agent rend à la fin de l'agent ; pour une étape sans agent, écris `-`. N'estime jamais une valeur absente.
- **Un seul agent à la fois utilise le navigateur Playwright** (`recette-live`).
- Le TM est souvent débutant avec Claude Code : parle simplement, une ligne par étape, sans jargon (pas de « MCP », « PATH », « JSON » dans tes messages au TM).

## Étape 0 : vérifications et reprise

1. **Python** : lance le script d'installation, qui garde un Python déjà présent ou installe une seule fois un Python privé (sans droits administrateur, sans rien modifier d'autre sur le poste) :
   - Windows : `powershell -NoProfile -ExecutionPolicy Bypass -File "SCRIPTS/installer-python.ps1"` ;
   - macOS ou Linux : `sh "SCRIPTS/installer-python.sh"`.

   Le premier lancement peut prendre une minute : préviens le TM (« j'installe Python pour la recette, une seule fois »). `PY` = ce qui suit `PY=` sur la dernière ligne. Une ligne `ECHEC:` : donne-la au TM telle quelle et arrête-toi.
2. **Navigateur** : les outils `mcp__playwright__…` sont-ils disponibles ? Sinon, si `DOSSIER/captures/serveur/releves.json` existe, le navigateur a déjà été fait par l'application Audit : tout va bien, n'en parle pas. Sinon, la recette continue sans navigateur (contrôles navigateur en Non testable) : dis-le au TM en une ligne, sans lui demander d'installer quoi que ce soit.
3. Screaming Frog (seulement si l'étape 2 n'est pas faite) : cherche `sf_crawl` avec ToolSearch. S'il est trouvé, appelle `sf_list_crawls` (limit 10) : tu en auras besoin à l'étape 1.
4. Google Drive : note si le connecteur (`create_file`) est disponible.
5. **Dossier préparé par l'application Audit** : si le répertoire de travail (ou un de ses sous-dossiers) contient `audit-preparation.json`, c'est un dossier téléchargé depuis audit.preprod-lab.com : `DOSSIER` = le dossier qui le contient. Le serveur a déjà fait le cadrage validé, les exports, les gabarits, les scripts et les captures du navigateur. Ne demande ni client ni adresse : dis au TM « je reprends la recette de <client> préparée par le site audit » et continue à l'étape de reprise.
6. **Reprise** : si `DOSSIER` existe, reprends à la première étape incomplète, d'après les fichiers :

   | Étape faite si… | Fichier |
   |---|---|
   | 1 | `profil.json` sans « brouillon » dans `_lisez_moi` |
   | 2 | `exports/preprod/` et `exports/ancien-site/` contiennent un `internal_all` reconnu (`recette.py exports`) |
   | 3 | `profil.json` a des `gabarits` |
   | 4 | `donnees/verification.json` |
   | 5 | `recette.py repartition` ne rend plus aucun contrôle |
   | 6 | `donnees/tickets.json` et `controler` sans erreur |
   | 7 | `controle-qualite.md` avec le verdict « livrable » |
   | 8 | `livrables/*.xlsx` |
   | 9 | `ameliorations.md` |

   Dis au TM en une ligne où tu reprends.

## Étape 1 : cadrage (validation 1)

1. Crée `DOSSIER`, `DOSSIER/exports/preprod` et `DOSSIER/exports/ancien-site`. Si le TM a donné un dossier de documents, copie-les dans `DOSSIER/documents/`. Sans fiche client, copie `TEMPLATES/fiche-client.md` dans `DOSSIER`.
2. Lance `recette-cadrage` avec `MODE=profil`.
3. **Validation 1.** Présente au TM, de façon compacte :
   - les adresses (préprod, site actuel, sitemap, robots.txt) avec le code obtenu ;
   - le tableau des pages stratégiques (nom, URL, ancienne URL) ;
   - les contrôles rendus non applicables par le profil (une ligne) ;
   - les questions numérotées de `cadrage.md` ;
   - si le MCP Screaming Frog est là, les crawls récents de `sf_list_crawls` qui portent sur la préprod ou le site actuel : « je les réutilise, ou je relance un crawl ? »
   - si la préprod est protégée : `acces-preprod.local.json` présent ou non, et `sf.auth_config` pour Screaming Frog.

   Applique ses réponses dans `profil.json` et remplace `_lisez_moi` par « validé par le TM le <date> ».

## Étape 2 : crawls

- **Avec le MCP Screaming Frog** : lance `recette-crawl` avec `ANCIEN_SITE=` et `PREPROD=` (`nouveau` ou l'identifiant choisi par le TM). Un crawl prend du temps : préviens le TM. Si l'agent répond « MCP Screaming Frog indisponible » ou que des exports indispensables manquent, passe au cas suivant pour ceux-là.
- **Sans MCP** (ou pour compléter) : donne au TM la liste des exports à faire, d'après `TEMPLATES/exports-screaming-frog.md`, et le dossier où les déposer. Attends qu'il dise que c'est fait.

Puis lance `PY SCRIPTS/recette.py exports DOSSIER` et donne une ligne par site : exports reconnus, indispensables manquants. Un indispensable manquant n'arrête pas la recette (ses contrôles seront Non testable), mais dis-le au TM et propose-lui de le fournir.

## Étape 3 : gabarits

Lance `recette-cadrage` avec `MODE=gabarits`. Donne au TM la liste des gabarits retenus en une ligne. Ce n'est pas une validation : continue, sauf s'il corrige.

## Étape 4 : scripts

1. Lance `PY SCRIPTS/recette.py tout DOSSIER` **en arrière-plan** (`run_in_background`) : le test des anciennes URLs peut durer plus de 10 minutes. Attends la notification de fin.
2. Une ligne au TM : contrôles par statut, d'après `donnees/verification.json`.

## Étape 5 : navigateur, expertise, cahier des charges

1. `PY SCRIPTS/recette.py repartition DOSSIER` donne les contrôles de `recette-live` et de `recette-expert`.
2. **En parallèle** (un seul message, deux lancements) : `recette-live` avec `CONTROLES=<liste>`, et `recette-expert` avec `MODE=controles` et `CONTROLES=<liste>`.
3. Puis, **en parallèle** :
   - `recette-cdc` avec `CDC=<fichiers>`, si un cahier des charges est dans le dossier ;
   - `recette-expert` avec `MODE=pistes`, si `donnees/pistes-live.md` existe et n'est pas vide.
4. Lance `PY SCRIPTS/recette.py poser DOSSIER`, puis `repartition`. S'il reste des contrôles sans résultat, relance une fois l'agent concerné avec leur liste. Une ligne au TM.

## Étape 6 : tickets

Lance `recette-livrable` avec `MODE=tickets`. Vérifie que `PY SCRIPTS/recette.py controler DOSSIER` rend zéro erreur.

## Étape 7 : contrôle qualité (obligatoire)

1. Lance `recette-controle`.
2. Verdict « à corriger » : relance chaque agent cité dans `controle-qualite.md` avec ses corrections (`CORRECTIONS=…`), puis `poser`, `recette-livrable` en `MODE=tickets` si les résultats ont changé, et de nouveau `recette-controle`. **Deux tours au plus** : au-delà, continue et présente au TM les corrections restantes comme points à vérifier.

## Étape 8 : livrables

**Dossier de l'application Audit** (`audit-preparation.json`) : saute les étapes 8 et 9, le TM construit le livrable dans l'application. Va directement à la fin.

1. Si le connecteur Google Drive est disponible, demande au TM : « Je dépose le fichier de travail dans ton Google Drive, converti en Google Sheets ? »
2. Lance `recette-livrable` avec `MODE=livrables`, en précisant la réponse du TM.

## Étape 9 : amélioration continue (validation 2)

1. Lance `PY SCRIPTS/recette.py etape DOSSIER amelioration debut`, puis `recette-amelioration` avec `MODE=fin`. Pour que la mesure de cette recette soit complète, clos d'abord les étapes précédentes dans `metriques.json`.
2. **Validation 2.** Présente les propositions (ID, axe, gain mesurable, type) et les apprentissages à retirer. Demande au TM lesquels il accepte. Relance `recette-amelioration` avec `MODE=validation` et ses décisions.
3. Si des propositions sont des évolutions du plugin, propose au TM de les envoyer au mainteneur. Ne crée jamais d'issue GitHub sans son accord explicite.

## Fin

Si le dossier vient de l'application Audit (`audit-preparation.json`), lance d'abord `PY SCRIPTS/recette.py paquet DOSSIER` : il écrit `DOSSIER/../<nom du dossier>-retour.zip`, sans l'accès à la préprod ni les exports. Dis au TM : « Dépose ce fichier dans audit.preprod-lab.com, sur la page de l'audit, bouton Importer la recette terminée » avec le chemin complet du fichier. Arrête-toi là : pas de résumé des fichiers, l'application s'en charge.

Sinon :

Réponds au TM, en court :
- les deux fichiers : chemins, et liens Google Sheets s'il y en a ;
- les contrôles par statut, les tickets par priorité et les bloquants. Tous les chiffres viennent de `donnees/controle-livrables.json` et `verification.json` ;
- les 3 à 5 tickets de priorité 1 ;
- ce qui reste à faire de son côté : valider les tickets et les hypothèses dans le fichier, fournir ce qui a rendu des contrôles Non testable ;
- la suite : une fois les tickets validés, télécharger le fichier de travail en .xlsx dans `DOSSIER/retour-tm/` et lancer `/recette:retour`.

## Règles de l'orchestrateur

- Tu ne fais pas le travail d'un agent. Si un agent échoue, relance-le une fois avec le message d'erreur, puis signale le blocage.
- Tu ne modifies jamais la préprod, le site en ligne ou le back-office, et tu n'envoies rien au client ni aux développeurs.
- Tu ne lis jamais `acces-preprod.local.json` dans la conversation et tu ne recopies jamais un mot de passe.
- Tu ne transmets aucun chiffre qui ne vienne d'un fichier du dossier.
- Si le TM ne demande qu'une partie (« refais les tickets », « relance juste le navigateur »), lance seulement l'étape concernée sur le dossier existant, puis `poser`, `controler` et le contrôle qualité.
