"""Contrôle qualité mécanique des résultats : cohérence entre resultats.json,
l'annexe et le référentiel. Ne juge pas le fond : l'agent de contrôle le fait.
"""
import csv
import json
import os

from commun import STATUTS, TYPES_PREUVE, Resultats, charger_profil, chemin


def preparer(dossier):
    """Pose les statuts qui ne dépendent que du profil : Non applicable, Après mise en ligne."""
    profil = charger_profil(dossier)
    res = Resultats(dossier)
    poses = {"Non applicable": [], "Après mise en ligne": []}
    for idc, c in res.ref.items():
        a = c["applicabilite"]
        if a != "toujours" and not profil["applicabilite"].get(a):
            res.poser(idc, "Non applicable", "Constat export", "profil.json",
                      f"Profil client : « {a} » non concerné.", script="preparer")
            poses["Non applicable"].append(idc)
        elif c["preprod"] == "apres_mel":
            res.poser(idc, "Après mise en ligne", "Constat export", "référentiel",
                      "Ne se vérifie qu'en prod : " + c["methode"], script="preparer")
            poses["Après mise en ligne"].append(idc)
    res.enregistrer()
    return poses


def verifier(dossier):
    profil = charger_profil(dossier)
    res = Resultats(dossier)
    erreurs, alertes = [], []
    comptes_annexe = {}
    for idc, r in res.data.items():
        c = res.ref.get(idc)
        if c is None:
            erreurs.append(f"{idc} : absent du référentiel.")
            continue
        if r["statut"] not in STATUTS:
            erreurs.append(f"{idc} : statut invalide « {r['statut']} ».")
        if r["type_preuve"] not in TYPES_PREUVE:
            erreurs.append(f"{idc} : type de preuve invalide « {r['type_preuve']} ».")
        a = c["applicabilite"]
        if a != "toujours" and not profil["applicabilite"].get(a) and r["statut"] != "Non applicable":
            erreurs.append(f"{idc} : profil « {a} » non concerné mais statut {r['statut']}.")
        if r["statut"] in ("OK", "KO", "Partiel") and not r.get("preuve"):
            erreurs.append(f"{idc} : statut {r['statut']} sans preuve.")
        if r["statut"] == "KO" and r["type_preuve"] == "Hypothèse":
            alertes.append(f"{idc} : KO fondé sur une hypothèse, à faire valider par le TM avant tout ticket.")
        n = r.get("n_urls")
        if n:
            onglet = r.get("onglet_annexe")
            p = chemin(dossier, "annexe", f"{onglet}.csv") if onglet else None
            if not p or not os.path.exists(p):
                erreurs.append(f"{idc} : {n} lignes annoncées mais onglet d'annexe « {onglet} » introuvable.")
                continue
            if p not in comptes_annexe:
                with open(p, encoding="utf-8-sig", newline="") as f:
                    comptes_annexe[p] = [l.get("Contrôle", "") for l in csv.DictReader(f, delimiter=";")]
            reel = sum(1 for x in comptes_annexe[p] if idc in x.split())
            if reel != n:
                erreurs.append(f"{idc} : {n} lignes annoncées, {reel} dans annexe/{onglet}.csv.")
    manquants = {}
    for idc, c in res.ref.items():
        if idc not in res.data:
            manquants.setdefault(c["source_donnee"], []).append(idc)
    rapport = {
        "controles": len(res.ref),
        "avec_resultat": len(res.data),
        "par_statut": {s: sum(1 for r in res.data.values() if r["statut"] == s) for s in STATUTS},
        "erreurs": erreurs,
        "alertes": alertes,
        "sans_resultat_par_source": manquants,
    }
    os.makedirs(chemin(dossier, "donnees"), exist_ok=True)
    with open(chemin(dossier, "donnees", "verification.json"), "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
    return rapport
