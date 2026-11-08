"""Résultats posés par les agents (navigateur, analyse, documents).

Chaque agent écrit donnees/resultats-agents/<agent>.json :

    {"agent": "recette-live",
     "resultats": [
       {"id": "MOB-01", "statut": "KO", "type_preuve": "Constat observé",
        "preuve": "captures/MOB-01-cholet-360.png", "details": "Le menu ...",
        "lignes_annexe": [{"URL": "https://...", "Constat": "..."}]}
     ]}

Ce script valide chaque résultat et l'écrit dans donnees/resultats.json.
L'agent ne donne jamais de nombre d'URLs : il donne les lignes, et le
script les compte et les écrit dans l'annexe (onglet du référentiel, ou
« onglet_annexe » du résultat). Un résultat de script n'est remplacé que s'il
était Non testable ou Partiel, ou si l'agent écrit « remplace_motif ».
"""
import csv
import glob
import json
import os

from commun import STATUTS, TYPES_PREUVE, Resultats, chemin, maintenant

REMPLACABLES = ("Non testable", "Partiel")


def _ecrire_annexe(dossier, onglet, idc, lignes, agent):
    os.makedirs(chemin(dossier, "annexe"), exist_ok=True)
    p = chemin(dossier, "annexe", onglet + ".csv")
    existantes = []
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig", newline="") as f:
            existantes = [l for l in csv.DictReader(f, delimiter=";") if l.get("Contrôle") != idc]
    nouvelles = [dict({"Contrôle": idc}, **{str(k): v for k, v in l.items()}) for l in lignes]
    toutes = existantes + nouvelles
    colonnes = []
    for l in toutes:
        for k in l:
            if k not in colonnes:
                colonnes.append(k)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(toutes)
    index_p = chemin(dossier, "annexe", "_sources.json")
    index = {}
    if os.path.exists(index_p):
        with open(index_p, encoding="utf-8") as f:
            index = json.load(f)
    e = index.setdefault(onglet, {"sources": [], "lignes": 0})
    if f"agent {agent}" not in e["sources"]:
        e["sources"].append(f"agent {agent}")
    e["lignes"], e["date"] = len(toutes), maintenant()
    with open(index_p, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def poser(dossier):
    res = Resultats(dossier)
    rapport = {"poses": [], "refuses": [], "fichiers": []}
    for p in sorted(glob.glob(chemin(dossier, "donnees", "resultats-agents", "*.json"))):
        nom = os.path.basename(p)
        try:
            with open(p, encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            rapport["refuses"].append(f"{nom} : JSON illisible ({e}).")
            continue
        agent = data.get("agent") or os.path.splitext(nom)[0]
        rapport["fichiers"].append(nom)
        for r in data.get("resultats", []):
            idc = r.get("id")
            erreur = None
            if idc not in res.ref:
                erreur = "contrôle absent du référentiel"
            elif r.get("statut") not in STATUTS:
                erreur = f"statut invalide « {r.get('statut')} »"
            elif r.get("type_preuve") not in TYPES_PREUVE:
                erreur = f"type de preuve invalide « {r.get('type_preuve')} »"
            elif r["statut"] in ("OK", "KO", "Partiel") and not (r.get("preuve") or "").strip():
                erreur = f"statut {r['statut']} sans preuve"
            elif r["statut"] in ("Non testable", "Partiel") and not (r.get("details") or "").strip():
                erreur = f"statut {r['statut']} sans explication dans « details »"
            elif r.get("n_urls") not in (None, ""):
                erreur = "« n_urls » est interdit : donner « lignes_annexe », le script compte"
            else:
                avant = res.data.get(idc)
                if avant and not str(avant.get("source", "")).startswith("agent") \
                        and avant["statut"] not in REMPLACABLES and not r.get("remplace_motif"):
                    erreur = (f"déjà posé par le script ({avant['statut']}) : écrire « remplace_motif » "
                              "pour le remplacer")
            if erreur:
                rapport["refuses"].append(f"{nom} / {idc} : {erreur}.")
                continue
            lignes = r.get("lignes_annexe") or []
            onglet = r.get("onglet_annexe") or res.ref[idc].get("onglet_annexe") or (f"Agent-{idc}" if lignes else None)
            if lignes:
                _ecrire_annexe(dossier, onglet, idc, lignes, agent)
            details = r.get("details") or ""
            if r.get("remplace_motif"):
                details = (details + f" (Remplace le résultat du script : {r['remplace_motif']})").strip()
            res.poser(idc, r["statut"], r["type_preuve"], r.get("preuve") or "", details,
                      n_urls=len(lignes) or None, onglet=onglet if lignes else None, script=f"agent {agent}")
            if r.get("bloquant"):
                res.data[idc]["bloquant"] = True
                res.data[idc]["motif_bloquant"] = r.get("motif_bloquant") or ""
            rapport["poses"].append(idc)
    res.enregistrer()
    return rapport
