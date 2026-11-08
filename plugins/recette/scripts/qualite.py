"""Contrôle qualité : contre-vérification d'un échantillon de l'annexe, et retour du TM.

contre_verifier : relance une requête sur un échantillon d'URLs de l'annexe
(celles de la préprod qui ont un code HTTP relevé) et compare le code obtenu.
Un écart ne corrige rien : il est signalé (préprod modifiée depuis le crawl,
ou erreur de lecture d'un export).

retour : lit l'onglet Tickets du classeur rendu par le TM (xlsx ou csv déposé
dans retour-tm/) et l'écrit dans retour-tm/tickets.csv pour le bilan.
"""
import csv
import json
import os
import random
import re
import zipfile
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from commun import charger_acces, charger_profil, chemin, maintenant
from web import Client

COLONNES_URL = ("URL testée", "URL", "Destination", "Adresse")
COLONNES_CODE = (("Code final", True), ("Code", False), ("Code obtenu", False))


def contre_verifier(dossier, par_onglet=5, total=40, graine=0):
    profil = charger_profil(dossier)
    acces = charger_acces(dossier) or {}
    acces.setdefault("preprod", profil.get("preprod", ""))
    client = Client(acces, ssl_verifie=profil.get("ssl_verifie", True), delai=profil.get("delai_requetes", 0.2))
    hote = urlsplit(profil.get("preprod", "")).netloc.lower()
    alea = random.Random(graine)
    verifies, ecarts = [], []
    d = chemin(dossier, "annexe")
    for nom in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not nom.endswith(".csv") or len(verifies) >= total:
            continue
        with open(os.path.join(d, nom), encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            champs = lecteur.fieldnames or []
            lignes = list(lecteur)
        c_url = next((c for c in COLONNES_URL if c in champs), None)
        c_code = next(((c, suivre) for c, suivre in COLONNES_CODE if c in champs), None)
        if not c_url or not c_code:
            continue
        candidates = [l for l in lignes if urlsplit(l.get(c_url) or "").netloc.lower() == hote
                      and re.fullmatch(r"\d{3}", (l.get(c_code[0]) or "").strip())]
        for l in alea.sample(candidates, min(par_onglet, len(candidates), total - len(verifies))):
            url, attendu = l[c_url], int(l[c_code[0]])
            if c_code[1]:
                obtenu = client.suivre(url)[0][-1]["status"]
            else:
                obtenu = client.recuperer(url)["status"]
            e = {"onglet": nom[:-4], "controle": l.get("Contrôle"), "url": url, "code_annexe": attendu,
                 "code_recompte": obtenu}
            verifies.append(e)
            if obtenu != attendu:
                ecarts.append(e)
    rapport = {"date": maintenant(), "verifies": len(verifies), "ecarts": ecarts, "detail": verifies}
    os.makedirs(chemin(dossier, "donnees"), exist_ok=True)
    with open(chemin(dossier, "donnees", "contre-verification.json"), "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
    return {k: v for k, v in rapport.items() if k != "detail"}


# --- Retour du TM -------------------------------------------------------------

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _ref_col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def lire_onglet_xlsx(p, nom_onglet):
    with zipfile.ZipFile(p) as z:
        partages = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                partages.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        cibles = {r.get("Id"): r.get("Target") for r in rels}
        feuille = None
        for s in wb.find("m:sheets", _NS):
            if s.get("name", "").strip().lower() == nom_onglet.lower():
                feuille = cibles[s.get(_R)].lstrip("/")
                feuille = feuille if feuille.startswith("xl/") else "xl/" + feuille
        if not feuille:
            return None
        lignes = []
        for row in ET.fromstring(z.read(feuille)).iter("{%s}row" % _NS["m"]):
            valeurs = {}
            for c in row.findall("m:c", _NS):
                t, v = c.get("t"), c.find("m:v", _NS)
                if t == "s" and v is not None:
                    x = partages[int(v.text)]
                elif t == "inlineStr":
                    x = "".join(e.text or "" for e in c.iter("{%s}t" % _NS["m"]))
                else:
                    x = v.text if v is not None else ""
                valeurs[_ref_col(c.get("r"))] = x
            if valeurs:
                lignes.append([valeurs.get(i, "") for i in range(max(valeurs) + 1)])
        return lignes


def retour(dossier):
    d = chemin(dossier, "retour-tm")
    if not os.path.isdir(d):
        return {"erreur": "Dossier retour-tm/ absent : y déposer le classeur de travail validé (xlsx) ou l'onglet Tickets en csv."}
    sortie = os.path.join(d, "tickets.csv")
    classeurs = sorted((f for f in os.listdir(d) if f.lower().endswith(".xlsx") and not f.startswith("~$")),
                       key=lambda f: os.path.getmtime(os.path.join(d, f)))
    if not classeurs:
        if os.path.exists(sortie):
            return {"source": "tickets.csv", "message": "tickets.csv déjà présent, utilisé tel quel."}
        return {"erreur": "Aucun classeur .xlsx ni tickets.csv dans retour-tm/."}
    p = os.path.join(d, classeurs[-1])
    lignes = lire_onglet_xlsx(p, "Tickets")
    if not lignes:
        return {"erreur": f"Onglet « Tickets » introuvable ou vide dans {classeurs[-1]}."}
    entetes = lignes[0]
    manquantes = [c for c in ("ID ticket", "Contrôles", "Titre", "Validation TM") if c not in entetes]
    if manquantes:
        return {"erreur": f"Colonnes absentes de l'onglet Tickets : {', '.join(manquantes)}."}
    with open(sortie, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(entetes)
        w.writerows(l + [""] * (len(entetes) - len(l)) for l in lignes[1:] if any(x.strip() for x in l))
    n = sum(1 for l in lignes[1:] if any(x.strip() for x in l))
    return {"source": classeurs[-1], "tickets": n, "fichier": "retour-tm/tickets.csv"}
