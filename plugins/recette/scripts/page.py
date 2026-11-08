"""HTML brut d'une page de la préprod, sans exécuter le JavaScript, pour les agents.

    python page.py <dossier de recette> <url> [<url> ...]

Utilise l'accès de acces-preprod.local.json si la préprod est protégée, sans
jamais l'afficher. Enregistre chaque page dans donnees/html/ et affiche, par
URL : code HTTP, redirection éventuelle, fichier écrit.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commun import charger_acces, charger_profil, chemin, normaliser  # noqa: E402
from web import Client  # noqa: E402


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(argv) < 3:
        raise SystemExit(__doc__)
    dossier = os.path.abspath(argv[1])
    profil = charger_profil(dossier)
    acces = charger_acces(dossier) or {}
    acces.setdefault("preprod", profil.get("preprod", ""))
    client = Client(acces, ssl_verifie=profil.get("ssl_verifie", True), delai=profil.get("delai_requetes", 0.2))
    sortie = chemin(dossier, "donnees", "html")
    os.makedirs(sortie, exist_ok=True)
    resultats = []
    for url in argv[2:]:
        r = client.recuperer(url)
        nom = (normaliser(url.split("://", 1)[-1])[:80] or "page") + "-" + hashlib.sha1(url.encode()).hexdigest()[:6] + ".html"
        fichier = None
        if r.get("corps"):
            fichier = os.path.join(sortie, nom)
            with open(fichier, "wb") as f:
                f.write(r["corps"])
        resultats.append({"url": url, "code": r.get("status"), "erreur": r.get("erreur"),
                          "redirection": (r.get("headers") or {}).get("location"),
                          "fichier": os.path.relpath(fichier, dossier).replace(os.sep, "/") if fichier else None})
    print(json.dumps(resultats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv)
