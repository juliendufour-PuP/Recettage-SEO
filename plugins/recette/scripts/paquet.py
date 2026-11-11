"""Paquet de retour d'une recette faite sur le poste du TM, pour l'application Audit.

    python recette.py paquet DOSSIER

Écrit <dossier parent>/<nom du dossier>-retour.zip avec ce que les agents ont produit.
Jamais dedans : l'accès à la préprod (*.local.json), les exports Screaming Frog et le crawl
(le serveur les a déjà), les captures du serveur, les fichiers cachés et les verrous.
"""
import os
import zipfile

EXCLUS_DOSSIERS = {"exports", "crawl-mcp", "retour-tm", "__pycache__"}
EXCLUS_CHEMINS = {os.path.join("captures", "serveur")}
TAILLE_MAX = 200 * 1024 * 1024


def exclu(rel):
    morceaux = rel.split(os.sep)
    if any(m.startswith(".") for m in morceaux):
        return True
    if morceaux[0] in EXCLUS_DOSSIERS:
        return True
    if any(rel == c or rel.startswith(c + os.sep) for c in EXCLUS_CHEMINS):
        return True
    nom = morceaux[-1]
    return nom.endswith(".local.json") or nom.endswith("-retour.zip") or nom == "audit-preparation.json"


def paquet(dossier):
    dossier = os.path.abspath(dossier)
    if not os.path.exists(os.path.join(dossier, "audit-preparation.json")):
        raise SystemExit("Ce dossier n'a pas été préparé par l'application Audit (audit-preparation.json absent).")
    sortie = os.path.join(os.path.dirname(dossier), os.path.basename(dossier) + "-retour.zip")
    fichiers, taille = [], 0
    for racine, dirs, noms in os.walk(dossier):
        dirs[:] = sorted(d for d in dirs if not exclu(os.path.relpath(os.path.join(racine, d), dossier)))
        for n in sorted(noms):
            p = os.path.join(racine, n)
            rel = os.path.relpath(p, dossier)
            if exclu(rel):
                continue
            fichiers.append((p, rel))
            taille += os.path.getsize(p)
    if taille > TAILLE_MAX:
        raise SystemExit(f"Paquet trop lourd ({taille // 1024 // 1024} Mo) : vérifie qu'aucun export n'est hors de exports/.")
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(dossier, "audit-preparation.json"), "audit-preparation.json")
        for p, rel in fichiers:
            z.write(p, rel.replace(os.sep, "/"))
    return {"paquet": sortie, "fichiers": len(fichiers) + 1, "taille_ko": round(os.path.getsize(sortie) / 1024)}
