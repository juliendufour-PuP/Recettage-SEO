"""Exports obtenus par le serveur MCP de Screaming Frog, remis au format des scripts.

L'agent recette-crawl dépose les fichiers produits par le MCP dans
crawl-mcp/preprod/ et crawl-mcp/ancien-site/, nommés <code>.<csv|ndjson>, ou
<code>.partie-<N>.<csv|ndjson> quand l'export a été demandé par tranches.
Ce script les assemble en exports/<site>/<code>.csv, que sf.py lit comme
un export manuel. Il n'écrase jamais un export déposé à la main.
"""
import csv
import json
import os
import re

from commun import chemin, lire_csv_simple, maintenant

# Noms de sortie reconnus par sf.py (MOTIFS_FICHIERS)
NOMS_SORTIE = {"sitemaps": "sitemaps_all"}
MOTIF = re.compile(r"^(?P<code>[a-z0-9_]+?)(\.partie-(?P<n>\d+))?\.(?P<ext>csv|ndjson|jsonl)$", re.I)


def _plat(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(_plat(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _lire(p, ext):
    """-> (entêtes, lignes, lignes illisibles)"""
    if ext == "csv":
        lignes = lire_csv_simple(p)
        return (lignes[0], lignes[1:], 0) if lignes else ([], [], 0)
    entetes, objets, illisibles = [], [], 0
    with open(p, encoding="utf-8-sig") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                o = json.loads(ligne)
            except ValueError:
                illisibles += 1
                continue
            if not isinstance(o, dict):
                illisibles += 1
                continue
            for k in o:
                if k not in entetes:
                    entetes.append(k)
            objets.append(o)
    return entetes, [[_plat(o.get(k)) for k in entetes] for o in objets], illisibles


def assembler(dossier):
    rapport = {}
    for site in ("preprod", "ancien-site"):
        source = chemin(dossier, "crawl-mcp", site)
        if not os.path.isdir(source):
            continue
        cible = chemin(dossier, "exports", site)
        os.makedirs(cible, exist_ok=True)
        manifeste_p = os.path.join(cible, "_mcp.json")
        manifeste = {}
        if os.path.exists(manifeste_p):
            with open(manifeste_p, encoding="utf-8") as f:
                manifeste = json.load(f)
        groupes = {}
        ignores = []
        for nom in sorted(os.listdir(source)):
            m = MOTIF.match(nom)
            if not m:
                if not nom.startswith("_"):
                    ignores.append(nom)
                continue
            ext = "csv" if m["ext"].lower() == "csv" else "ndjson"
            groupes.setdefault(m["code"].lower(), []).append((int(m["n"] or 0), nom, ext))
        sortie = {"assembles": {}, "refuses": [], "ignores": ignores}
        for code, parties in sorted(groupes.items()):
            parties.sort()
            nom_sortie = NOMS_SORTIE.get(code, code) + ".csv"
            p_sortie = os.path.join(cible, nom_sortie)
            if os.path.exists(p_sortie) and nom_sortie not in manifeste:
                sortie["refuses"].append(f"{nom_sortie} : un export déposé à la main existe déjà, il est gardé.")
                continue
            entetes, toutes, illisibles, erreur = None, [], 0, None
            for _, nom, ext in parties:
                e, lignes, ill = _lire(os.path.join(source, nom), ext)
                illisibles += ill
                if entetes is None:
                    entetes = e
                elif e != entetes:
                    # Les tranches NDJSON peuvent ne pas avoir les mêmes clés : on aligne sur les noms.
                    if ext == "ndjson" and set(e) <= set(entetes):
                        idx = {k: i for i, k in enumerate(e)}
                        lignes = [[l[idx[k]] if k in idx else "" for k in entetes] for l in lignes]
                    else:
                        erreur = f"{nom} n'a pas les mêmes colonnes que {parties[0][1]}"
                        break
                toutes.extend(lignes)
            if erreur:
                sortie["refuses"].append(f"{code} : {erreur}.")
                continue
            with open(p_sortie, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(entetes or [])
                w.writerows(toutes)
            manifeste[nom_sortie] = {"code": code, "parties": [n for _, n, _ in parties], "lignes": len(toutes),
                                     "lignes_illisibles": illisibles, "date": maintenant()}
            sortie["assembles"][nom_sortie] = manifeste[nom_sortie]
        with open(manifeste_p, "w", encoding="utf-8") as f:
            json.dump(manifeste, f, ensure_ascii=False, indent=2)
        rapport[site] = sortie
    if not rapport:
        rapport["erreur"] = "Aucun dossier crawl-mcp/preprod ou crawl-mcp/ancien-site."
    return rapport
