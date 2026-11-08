"""Point d'entrée des scripts de recette SEO.

    python recette.py <commande> <dossier de recette>

Commandes, dans l'ordre conseillé :
    preparer      statuts Non applicable et Après mise en ligne (profil client)
    sitemap       lit le sitemap de la préprod (SIT-01, SIT-03)
    robots        robots.txt et blocages de la préprod (ROB-01, PRE-02)
    sf            contrôles sur les exports Screaming Frog et croisements avec le sitemap
    redirections  anciennes URLs testées sur la préprod (RED-01 à RED-05)
    gabarits      Hn, menu et footer, favicon, JSON-LD, domaine en dur (sur les gabarits)
    langues       redirections selon la langue (site international)
    verifier      cohérence résultats / annexe / référentiel
    tout          toutes les commandes ci-dessus
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import controles_sf  # noqa: E402
import controles_web  # noqa: E402
import verifier  # noqa: E402
from commun import charger_acces, charger_profil  # noqa: E402
from web import Client  # noqa: E402


def _client(dossier):
    profil = charger_profil(dossier)
    acces = charger_acces(dossier) or {}
    acces.setdefault("preprod", profil.get("preprod", ""))
    return Client(acces, ssl_verifie=profil.get("ssl_verifie", True), delai=profil.get("delai_requetes", 0.2))


def commande(nom, dossier):
    if nom == "preparer":
        return verifier.preparer(dossier)
    if nom == "sitemap":
        return controles_web.sitemap(dossier)
    if nom == "robots":
        return controles_web.robots(dossier)
    if nom == "sf":
        client = _client(dossier)
        return controles_sf.lancer(dossier, recuperer=lambda u: client.suivre(u)[0][-1])
    if nom == "redirections":
        return controles_web.redirections(dossier)
    if nom == "gabarits":
        return controles_web.gabarits(dossier)
    if nom == "langues":
        return controles_web.langues(dossier)
    if nom == "verifier":
        return verifier.verifier(dossier)
    raise SystemExit(f"Commande inconnue : {nom}\n{__doc__}")


def main(argv):
    try:  # console Windows : accents et guillemets français
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(argv) != 3:
        raise SystemExit(__doc__)
    nom, dossier = argv[1], os.path.abspath(argv[2])
    if not os.path.isdir(dossier):
        raise SystemExit(f"Dossier introuvable : {dossier}")
    noms = ["preparer", "sitemap", "robots", "sf", "redirections", "gabarits", "langues", "verifier"] \
        if nom == "tout" else [nom]
    sortie = {}
    for n in noms:
        try:
            sortie[n] = commande(n, dossier)
        except SystemExit as e:
            if nom != "tout":
                raise
            sortie[n] = {"arret": str(e)}
    print(json.dumps(sortie if nom == "tout" else sortie[nom], ensure_ascii=False, indent=2, default=str))
    rapport = sortie.get("verifier")
    if isinstance(rapport, dict) and rapport.get("erreurs"):
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
