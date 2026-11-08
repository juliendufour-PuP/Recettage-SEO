"""Livrables de la recette : contrôle qualité mécanique, puis les deux classeurs .xlsx.

Entrées (dans le dossier de recette) :
    donnees/resultats.json     un résultat par contrôle (scripts et agents)
    annexe/*.csv               les listes d'URLs, écrites par script
    donnees/tickets.json       les tickets rédigés par l'agent recette-livrable :
        {"tickets": [{"controles": ["COD-02"], "exigences": [], "titre": "...",
                      "description": "...", "resolution": "...", "resultat_attendu": "...",
                      "urls_exemple": ["..."], "bloque_mise_en_ligne": false, "motif_bloquant": ""}],
         "sans_ticket": [{"id": "URL-05", "motif": "..."}]}
    donnees/hypotheses.json    [{"sujet", "raisonnement", "pour_confirmer", "priorite_proposee"}]
    donnees/cdc.json           [{"exigence", "source", "statut", "preuve", "controles": []}]

Les identifiants (T-001, H-001, CDC-01), les priorités, les nombres d'URLs et
le type de preuve des tickets sont calculés ici, jamais saisis par un agent.
Un chiffre écrit dans un ticket doit se retrouver dans les résultats des
contrôles liés : sinon c'est une erreur de contrôle qualité.
"""
import csv
import json
import os
import re
from datetime import datetime

from commun import STATUTS, Resultats, charger_profil, chemin, cle_url, maintenant
from xlsx import Classeur, Formule

STATUTS_CDC = ("Conforme", "Non conforme", "Partiel", "Non testable", "Après mise en ligne")
CODES_HTTP = {"200", "301", "302", "303", "307", "308", "400", "401", "403", "404", "410", "500", "502", "503", "504"}
NOMBRE = re.compile(r"(?<![\w.,/#:-])\d+(?:[.,]\d+)?(?![\w])")


def _json(dossier, nom, defaut):
    p = chemin(dossier, "donnees", nom)
    if not os.path.exists(p):
        return defaut, False
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f), True


def _nombres(texte):
    return {n.replace(",", ".") for n in NOMBRE.findall(str(texte or ""))}


def _annexes(dossier):
    """onglet -> (entêtes, lignes) ; lignes = dicts avec la colonne Contrôle."""
    d = chemin(dossier, "annexe")
    sortie = {}
    if not os.path.isdir(d):
        return sortie
    for nom in sorted(os.listdir(d)):
        if nom.endswith(".csv"):
            with open(os.path.join(d, nom), encoding="utf-8-sig", newline="") as f:
                r = csv.DictReader(f, delimiter=";")
                sortie[nom[:-4]] = (r.fieldnames or [], list(r))
    return sortie


def _charger(dossier):
    profil = charger_profil(dossier)
    res = Resultats(dossier)
    t, t_ok = _json(dossier, "tickets.json", {"tickets": [], "sans_ticket": []})
    if isinstance(t, list):
        t = {"tickets": t, "sans_ticket": []}
    hyp, _ = _json(dossier, "hypotheses.json", [])
    cdc, _ = _json(dossier, "cdc.json", [])
    for i, c in enumerate(cdc, start=1):
        c["id"] = f"CDC-{i:02d}"
    for i, h in enumerate(hyp, start=1):
        h["id"] = f"H-{i:03d}"
    tickets = t.get("tickets") or []
    for i, tk in enumerate(tickets, start=1):
        tk["id"] = f"T-{i:03d}"
    return profil, res, tickets, t.get("sans_ticket") or [], hyp, cdc, t_ok


def priorites(profil, res, annexes, tickets):
    """Règle de regles-recette.md §4 : priorité du référentiel, +1 cran (sans dépasser 1)
    si l'anomalie touche une page stratégique ou bloque la mise en ligne."""
    strat = {}
    for p in profil.get("pages_strategiques", []):
        for k in ("url", "ancienne_url"):
            if p.get(k):
                strat[cle_url(p[k])] = p.get("nom") or p[k]
    bloquants = {}
    for tk in tickets:
        if tk.get("bloque_mise_en_ligne"):
            for c in tk.get("controles") or []:
                bloquants[c] = tk.get("motif_bloquant") or f"ticket {tk['id']}"
    sortie = {}
    for idc, c in res.ref.items():
        p = int(c["priorite"])
        r = res.data.get(idc) or {}
        raisons = []
        if r.get("statut") in ("KO", "Partiel"):
            pages = set()
            onglet = r.get("onglet_annexe")
            if onglet in annexes:
                for ligne in annexes[onglet][1]:
                    if idc not in (ligne.get("Contrôle") or "").split():
                        continue
                    for v in ligne.values():
                        if isinstance(v, str) and v.startswith("http") and cle_url(v) in strat:
                            pages.add(strat[cle_url(v)])
            if pages:
                raisons.append("touche une page stratégique (" + ", ".join(sorted(pages)) + ")")
            if r.get("bloquant") or idc in bloquants:
                raisons.append("bloque la mise en ligne : " + (r.get("motif_bloquant") or bloquants.get(idc, "")))
        if raisons and p > 1:
            sortie[idc] = (p - 1, f"Priorité relevée de {p} à {p - 1} : " + " ; ".join(raisons) + ".")
        elif raisons:
            sortie[idc] = (p, "Déjà en priorité 1 : " + " ; ".join(raisons) + ".")
        else:
            sortie[idc] = (p, "")
    return sortie


def controler(dossier):
    profil, res, tickets, sans_ticket, hyp, cdc, t_ok = _charger(dossier)
    annexes = _annexes(dossier)
    prio = priorites(profil, res, annexes, tickets)
    erreurs, alertes = [], []
    # 1. Aucun contrôle laissé vide
    vides = [i for i in res.ref if i not in res.data]
    if vides:
        erreurs.append(f"Contrôles sans résultat : {', '.join(vides)}.")
    # 2. Cohérence résultats / annexe (verifier.py)
    v, v_ok = _json(dossier, "verification.json", None)
    if not v_ok:
        erreurs.append("donnees/verification.json absent : lancer « recette.py verifier ».")
    else:
        erreurs.extend("Vérification : " + e for e in v.get("erreurs", []))
    if not t_ok:
        erreurs.append("donnees/tickets.json absent : l'agent recette-livrable ne l'a pas écrit.")
    cdc_ids = {c["id"]: c for c in cdc}
    for c in cdc:
        if c.get("statut") not in STATUTS_CDC:
            erreurs.append(f"{c['id']} : statut « {c.get('statut')} » invalide ({', '.join(STATUTS_CDC)}).")
        if c.get("statut") in ("Conforme", "Non conforme", "Partiel") and not (c.get("preuve") or "").strip():
            erreurs.append(f"{c['id']} : statut {c.get('statut')} sans preuve.")
        for idc in c.get("controles") or []:
            if idc not in res.ref:
                erreurs.append(f"{c['id']} : contrôle lié inconnu {idc}.")
    # 3. Tickets
    couverts = set()
    for tk in tickets:
        n = tk["id"]
        ctrl, exig = tk.get("controles") or [], tk.get("exigences") or []
        if not ctrl and not exig:
            erreurs.append(f"{n} : ni contrôle ni exigence du cahier des charges.")
        for champ in ("titre", "description", "resolution", "resultat_attendu"):
            if not (tk.get(champ) or "").strip():
                erreurs.append(f"{n} : champ « {champ} » vide.")
        autorises = set(CODES_HTTP) | {"0"} | {str(x) for x in profil["seuils"].values() if x is not None}
        for idc in ctrl:
            r = res.data.get(idc)
            if idc not in res.ref:
                erreurs.append(f"{n} : contrôle inconnu {idc}.")
                continue
            if not r or r["statut"] not in ("KO", "Partiel"):
                erreurs.append(f"{n} : {idc} est « {(r or {}).get('statut', 'sans résultat')} », pas KO ni Partiel.")
                continue
            if r["type_preuve"] == "Hypothèse":
                erreurs.append(f"{n} : {idc} repose sur une hypothèse, qui ne devient un ticket qu'après validation du TM.")
            couverts.add(idc)
            if r.get("n_urls") is not None:
                autorises.add(str(r["n_urls"]))
            autorises |= _nombres(r.get("details")) | _nombres(r.get("preuve"))
        for e in exig:
            c = cdc_ids.get(e)
            if not c:
                erreurs.append(f"{n} : exigence inconnue {e}.")
            elif c.get("statut") not in ("Non conforme", "Partiel"):
                erreurs.append(f"{n} : {e} est « {c.get('statut')} », pas Non conforme ni Partiel.")
            else:
                autorises |= _nombres(c.get("exigence")) | _nombres(c.get("preuve"))
        if exig and not ctrl and tk.get("priorite") not in (1, 2, 3):
            erreurs.append(f"{n} : ticket issu du cahier des charges seul, « priorite » (1 à 3) obligatoire.")
        if ctrl and tk.get("priorite") not in (None, ""):
            erreurs.append(f"{n} : « priorite » est calculée depuis les contrôles, ne pas la saisir.")
        for champ in ("titre", "description", "resolution", "resultat_attendu"):
            inconnus = sorted(_nombres(tk.get(champ)) - autorises)
            if inconnus:
                erreurs.append(f"{n} : chiffre(s) {', '.join(inconnus)} dans « {champ} » sans source dans les "
                               "résultats des contrôles liés. Les écrire dans le résultat (script) ou les retirer.")
        urls = tk.get("urls_exemple") or []
        if len(urls) > 5:
            alertes.append(f"{n} : {len(urls)} URLs d'exemple, 5 au plus (les autres sont dans l'annexe).")
        n_total = sum((res.data.get(i) or {}).get("n_urls") or 0 for i in ctrl)
        if n_total >= 3 and len(urls) < 3:
            alertes.append(f"{n} : moins de 3 URLs d'exemple alors que l'annexe en liste {n_total}.")
        if tk.get("bloque_mise_en_ligne") and not (tk.get("motif_bloquant") or "").strip():
            erreurs.append(f"{n} : bloque la mise en ligne sans motif.")
    # 4. Chaque KO a son ticket, ou un motif écrit
    motifs = {s.get("id"): s.get("motif") for s in sans_ticket}
    for idc, r in res.data.items():
        if r["statut"] == "KO" and r["type_preuve"] != "Hypothèse" and idc not in couverts:
            if not (motifs.get(idc) or "").strip():
                erreurs.append(f"{idc} : KO sans ticket ni motif dans « sans_ticket ».")
    for c in cdc:
        if c.get("statut") == "Non conforme" and not any(c["id"] in (t.get("exigences") or []) for t in tickets) \
                and not any(i in couverts for i in c.get("controles") or []):
            erreurs.append(f"{c['id']} : exigence non conforme sans ticket.")
    # 5. Hypothèses
    for h in hyp:
        for champ in ("sujet", "raisonnement", "pour_confirmer"):
            if not (h.get(champ) or "").strip():
                erreurs.append(f"{h['id']} : champ « {champ} » vide.")
        if h.get("priorite_proposee") not in (1, 2, 3):
            erreurs.append(f"{h['id']} : « priorite_proposee » doit valoir 1, 2 ou 3.")
    rapport = {"date": maintenant(), "erreurs": erreurs, "alertes": alertes,
               "tickets": len(tickets), "hypotheses": len(hyp), "exigences_cdc": len(cdc),
               "priorites_relevees": {i: c for i, (p, c) in prio.items() if c}}
    os.makedirs(chemin(dossier, "donnees"), exist_ok=True)
    with open(chemin(dossier, "donnees", "controle-livrables.json"), "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
    return rapport


def _exports_utilises(dossier):
    lignes = []
    racine = chemin(dossier, "exports")
    for base, _, fichiers in os.walk(racine):
        for f in sorted(fichiers):
            if f.lower().endswith(".csv"):
                p = os.path.join(base, f)
                lignes.append((os.path.relpath(p, dossier).replace(os.sep, "/"),
                               datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")))
    return lignes


def livrables(dossier):
    rapport = controler(dossier)
    if rapport["erreurs"]:
        rapport["livrables"] = None
        rapport["message"] = "Livrables non générés : corriger les erreurs du contrôle qualité."
        return rapport
    profil, res, tickets, _, hyp, cdc, _ = _charger(dossier)
    annexes = _annexes(dossier)
    prio = priorites(profil, res, annexes, tickets)
    sources = {}
    p_src = chemin(dossier, "annexe", "_sources.json")
    if os.path.exists(p_src):
        with open(p_src, encoding="utf-8") as f:
            sources = json.load(f)
    client = profil.get("client") or "Client"
    date = datetime.now().strftime("%Y-%m-%d")
    base = f"{client} - Recette SEO préprod - {date}"
    nom_annexe = f"{client} - Recette SEO préprod - Annexe - {date}"
    tickets_par_ctrl = {}
    for tk in tickets:
        for c in tk.get("controles") or []:
            tickets_par_ctrl.setdefault(c, []).append(tk["id"])
        tk["_prio"] = min((prio[c][0] for c in tk.get("controles") or [] if c in prio), default=tk.get("priorite"))
        tk["_preuve"] = "Constat observé" if any((res.data.get(c) or {}).get("type_preuve") == "Constat observé"
                                                  for c in tk.get("controles") or []) else "Constat export"
        tk["_n"] = sum((res.data.get(c) or {}).get("n_urls") or 0 for c in tk.get("controles") or [])
        onglets = sorted({(res.data.get(c) or {}).get("onglet_annexe") for c in tk.get("controles") or []} - {None})
        tk["_annexe"] = ", ".join(f"Annexe > {o}" for o in onglets)

    wb = Classeur()
    syn = wb.onglet("Synthèse")
    rec = wb.onglet("Recette")
    tik = wb.onglet("Tickets")
    hy = wb.onglet("Hypothèses")
    cd = wb.onglet("Cahier des charges")
    amel = wb.onglet("Après mise en ligne")

    # Recette
    rec.entete(["ID", "Bloc", "Catégorie", "Contrôle", "Priorité (1-3)", "Statut", "Type de preuve", "Preuve",
                "URLs concernées", "Lien annexe", "Ticket", "Commentaire"])
    for idc, c in res.ref.items():
        r = res.data[idc]
        preuve = " — ".join(x for x in (r.get("preuve"), r.get("details")) if x)
        rec.ajouter([idc, c["bloc"], c["categorie"], c["controle"], prio[idc][0], r["statut"], r["type_preuve"],
                     preuve, r.get("n_urls"), f"Annexe > {r['onglet_annexe']}" if r.get("onglet_annexe") else "",
                     ", ".join(tickets_par_ctrl.get(idc, [])), prio[idc][1]])
    rec.largeurs = {0: 9, 1: 10, 2: 16, 3: 34, 4: 9, 5: 13, 6: 15, 7: 70, 8: 10, 9: 24, 10: 10, 11: 40}
    rec.retour_ligne = {3, 7, 11}
    n_rec = len(res.ref) + 1

    # Tickets
    tik.entete(["ID ticket", "Contrôles", "Priorité (1-3)", "Titre", "Description du problème", "Résolution",
                "Résultat attendu", "URLs d'exemple", "Lien annexe", "Type de preuve", "Bloque la mise en ligne",
                "Validation TM", "Commentaire TM"])
    for tk in tickets:
        tik.ajouter([tk["id"], " ".join((tk.get("controles") or []) + (tk.get("exigences") or [])), tk["_prio"],
                     tk["titre"], tk["description"], tk["resolution"], tk["resultat_attendu"],
                     "\n".join(tk.get("urls_exemple") or []), tk["_annexe"], tk["_preuve"],
                     ("oui : " + tk.get("motif_bloquant", "")) if tk.get("bloque_mise_en_ligne") else "non",
                     "À valider", ""])
    tik.liste(11, 2, max(len(tickets) + 1, 200), ["À valider", "Validé", "Rejeté"])
    tik.largeurs = {0: 9, 1: 14, 2: 9, 3: 34, 4: 50, 5: 50, 6: 45, 7: 45, 8: 24, 9: 15, 10: 16, 11: 13, 12: 30}
    tik.retour_ligne = {3, 4, 5, 6, 7, 10, 12}

    # Hypothèses
    hy.entete(["ID", "Sujet", "Constat ou raisonnement", "Pour confirmer", "Priorité proposée (1-3)", "Décision TM"])
    for h in hyp:
        hy.ajouter([h["id"], h["sujet"], h["raisonnement"], h["pour_confirmer"], h["priorite_proposee"], "À valider"])
    hy.liste(5, 2, max(len(hyp) + 1, 100), ["À valider", "Validé", "Rejeté"])
    hy.largeurs = {0: 8, 1: 30, 2: 60, 3: 45, 4: 12, 5: 14}
    hy.retour_ligne = {1, 2, 3}

    # Cahier des charges
    cd.entete(["ID", "Exigence", "Source dans le cahier des charges", "Statut", "Preuve", "Contrôles liés", "Ticket"])
    for c in cdc:
        tks = [t["id"] for t in tickets if c["id"] in (t.get("exigences") or [])]
        cd.ajouter([c["id"], c.get("exigence"), c.get("source"), c.get("statut"), c.get("preuve"),
                    " ".join(c.get("controles") or []), ", ".join(tks)])
    cd.largeurs = {0: 8, 1: 50, 2: 25, 3: 15, 4: 50, 5: 15, 6: 10}
    cd.retour_ligne = {1, 4}

    # Après mise en ligne
    amel.entete(["ID", "Contrôle", "À faire en prod", "Pourquoi"])
    for idc, c in res.ref.items():
        r = res.data[idc]
        if r["statut"] == "Après mise en ligne" or idc in ("PRE-02", "CWV-01"):
            pourquoi = {"PRE-02": "Lever les blocages de la préprod (noindex, robots.txt, mot de passe) au moment de la mise en ligne.",
                        "CWV-01": "Les Core Web Vitals réels (données terrain) n'existent qu'en prod."}.get(idc, r.get("details", ""))
            amel.ajouter([idc, c["controle"], c["methode"], pourquoi])
    amel.largeurs = {0: 9, 1: 34, 2: 70, 3: 50}
    amel.retour_ligne = {1, 2, 3}

    # Synthèse : chiffres par formule
    syn.ajouter([f"{client} : recette SEO de la préprod"], style=2)
    syn.ajouter(["Préprod", profil.get("preprod", "")])
    syn.ajouter(["Site actuel", profil.get("ancien_site", "")])
    syn.ajouter(["Date de la recette", date])
    syn.ajouter([])
    syn.ajouter(["Contrôles par statut"], style=2)
    for s in STATUTS:
        syn.ajouter([s, Formule(f'COUNTIF(Recette!F2:F{n_rec},"{s}")')])
    syn.ajouter(["Total", Formule(f"COUNTA(Recette!A2:A{n_rec})")])
    syn.ajouter([])
    syn.ajouter(["Tickets par priorité"], style=2)
    n_tk = max(len(tickets) + 1, 2)
    for p in (1, 2, 3):
        syn.ajouter([f"Priorité {p}", Formule(f"COUNTIF(Tickets!C2:C{n_tk},{p})")])
    syn.ajouter(["Bloquent la mise en ligne", Formule(f'COUNTIF(Tickets!K2:K{n_tk},"oui*")')])
    syn.ajouter(["Validés par le TM", Formule(f'COUNTIF(Tickets!L2:L{n_tk},"Validé")')])
    syn.ajouter(["Hypothèses à valider", Formule(f'COUNTIF(\'Hypothèses\'!F2:F{max(len(hyp) + 1, 2)},"À valider")')])
    syn.ajouter([])
    syn.ajouter(["Non testé, et pourquoi"], style=2)
    for idc, r in res.data.items():
        if r["statut"] == "Non testable":
            syn.ajouter([idc, r.get("details", "")])
    syn.ajouter([])
    syn.ajouter(["Exports utilisés"], style=2)
    for nom, d in _exports_utilises(dossier):
        syn.ajouter([nom, d])
    syn.largeurs = {0: 34, 1: 90}
    syn.retour_ligne = {1}

    # Annexe
    an = Classeur()
    som = an.onglet("Sommaire")
    som.ajouter([f"{client} : annexe de la recette SEO du {date}"], style=2)
    som.entete(["Onglet", "Contrôles", "Lignes", "Source"])
    for onglet, (entetes, lignes) in annexes.items():
        ctrls = sorted({x for l in lignes for x in (l.get("Contrôle") or "").split()})
        src = sources.get(onglet, {})
        som.ajouter([onglet, " ".join(ctrls), len(lignes), ", ".join(src.get("sources", []))])
        o = an.onglet(onglet)
        o.ajouter([onglet], style=2)
        o.ajouter(["Contrôles : " + " ".join(ctrls)])
        o.ajouter(["Source : " + ", ".join(src.get("sources", [])) + (f" ({src['date']})" if src.get("date") else "")])
        o.entete(entetes)
        for l in lignes:
            o.ajouter([l.get(k, "") for k in entetes])
        o.largeurs = {i: (12 if k == "Contrôle" else 45 if "url" in k.lower() or "adresse" in k.lower() else 22)
                      for i, k in enumerate(entetes)}
    som.largeurs = {0: 30, 1: 30, 2: 10, 3: 50}

    sortie = chemin(dossier, "livrables")
    os.makedirs(sortie, exist_ok=True)
    p1, p2 = os.path.join(sortie, base + ".xlsx"), os.path.join(sortie, nom_annexe + ".xlsx")
    wb.enregistrer(p1)
    an.enregistrer(p2)
    rapport["livrables"] = {"travail": p1, "annexe": p2}
    with open(chemin(dossier, "donnees", "controle-livrables.json"), "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
    return rapport
