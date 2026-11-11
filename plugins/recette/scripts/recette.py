"""Point d'entrée des scripts de recette SEO.

    python recette.py <commande> <dossier de recette>

Commandes, dans l'ordre conseillé :
    mcp           assemble les exports obtenus par le MCP Screaming Frog (crawl-mcp/)
                  en exports/<site>/<code>.csv
    exports       ce que les scripts comprennent des exports Screaming Frog (préprod et
                  site actuel), interface en français ou en anglais : à lancer en premier
    preparer      statuts Non applicable et Après mise en ligne (profil client)
    sitemap       lit le sitemap de la préprod (SIT-01, SIT-03)
    robots        robots.txt et blocages de la préprod (ROB-01, PRE-02)
    sf            contrôles sur les exports Screaming Frog et croisements avec le sitemap
    redirections  anciennes URLs testées sur la préprod (RED-01 à RED-05)
    gabarits      Hn, menu et footer, favicon, JSON-LD, domaine en dur (sur les gabarits)
    langues       redirections selon la langue (site international)
    verifier      cohérence résultats / annexe / référentiel
    tout          toutes les commandes ci-dessus
    lighthouse    CWV-01 : Lighthouse mobile sur l'accueil et chaque gabarit (Node.js et Chrome),
                  pour le contrôle post-refonte : jamais sur une préprod
    repartition   contrôles encore sans résultat, répartis entre recette-live et recette-expert
    poser         résultats des agents (donnees/resultats-agents/*.json), puis verifier
    controler     contrôle qualité mécanique des tickets, hypothèses et cahier des charges
    contre-verifier  relance un échantillon d'URLs de l'annexe et compare les codes HTTP
    livrables     controler, puis les deux classeurs .xlsx dans livrables/ (refusé si erreur)
    retour        onglet Tickets du classeur validé par le TM (retour-tm/*.xlsx) -> retour-tm/tickets.csv
    etape         python recette.py etape <dossier> <nom> debut|fin [agent] [tokens] [appels d'outils]
                  durée et coût de chaque étape, dans donnees/metriques.json
    paquet        dossier préparé par l'application Audit : <dossier>-retour.zip à y réimporter
                  (sans l'accès à la préprod ni les exports)
    bilan         mesures de la recette et journal local, pour l'agent recette-amelioration
                  (à lancer en fin de processus, hors « tout »)
"""
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bilan  # noqa: E402
import controles_sf  # noqa: E402
import controles_web  # noqa: E402
import lighthouse  # noqa: E402
import livrables  # noqa: E402
import mcp_exports  # noqa: E402
import paquet  # noqa: E402
import poser  # noqa: E402
import qualite  # noqa: E402
import sf  # noqa: E402
import verifier  # noqa: E402
from commun import chemin, charger_acces, charger_profil  # noqa: E402
from web import Client  # noqa: E402


@contextlib.contextmanager
def verrou(dossier, attente=120):
    p = chemin(dossier, "donnees", ".verrou")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    debut = time.monotonic()
    while True:
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() - debut > attente:  # verrou abandonné par un agent interrompu
                os.remove(p)
                continue
            time.sleep(0.5)
    try:
        yield
    finally:
        os.close(fd)
        os.remove(p)


def _client(dossier):
    profil = charger_profil(dossier)
    acces = charger_acces(dossier) or {}
    acces.setdefault("preprod", profil.get("preprod", ""))
    return Client(acces, ssl_verifie=profil.get("ssl_verifie", True), delai=profil.get("delai_requetes", 0.2))


def commande(nom, dossier):
    if nom == "mcp":
        return mcp_exports.assembler(dossier)
    if nom == "lighthouse":
        return lighthouse.lighthouse(dossier)
    if nom == "repartition":
        return verifier.repartition(dossier)
    if nom == "poser":  # plusieurs agents peuvent le lancer en même temps : un seul écrit à la fois
        with verrou(dossier):
            return {"poser": poser.poser(dossier), "verifier": verifier.verifier(dossier)}
    if nom == "contre-verifier":
        return qualite.contre_verifier(dossier)
    if nom == "retour":
        return qualite.retour(dossier)
    if nom == "controler":
        return livrables.controler(dossier)
    if nom == "livrables":
        return livrables.livrables(dossier)
    if nom == "exports":
        return {"preprod": sf.diagnostic(chemin(dossier, "exports", "preprod")),
                "ancien-site": sf.diagnostic(chemin(dossier, "exports", "ancien-site"), ["internal_all"])}
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
    if nom == "paquet":
        return paquet.paquet(dossier)
    if nom == "bilan":
        return bilan.bilan(dossier)
    raise SystemExit(f"Commande inconnue : {nom}\n{__doc__}")


def main(argv):
    try:  # console Windows : accents et guillemets français
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(argv) < 3 or (len(argv) != 3 and argv[1] != "etape"):
        raise SystemExit(__doc__)
    nom, dossier = argv[1], os.path.abspath(argv[2])
    if not os.path.isdir(dossier):
        raise SystemExit(f"Dossier introuvable : {dossier}")
    if nom == "etape":
        if len(argv) < 5:
            raise SystemExit(__doc__)
        extra = argv[5:8] + [None] * (3 - len(argv[5:8]))
        print(json.dumps(bilan.noter_etape(dossier, argv[3], argv[4], *extra), ensure_ascii=False))
        return
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
    rapport = sortie.get("verifier") if nom == "tout" else sortie[nom]
    if isinstance(rapport, dict) and isinstance(rapport.get("verifier"), dict):
        rapport = rapport["verifier"]
    if isinstance(rapport, dict) and rapport.get("erreurs"):
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
