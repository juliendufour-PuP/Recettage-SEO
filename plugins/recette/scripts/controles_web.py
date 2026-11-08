"""Contrôles par requêtes ciblées sur la préprod : sitemap, robots.txt,
redirections depuis l'ancien site, gabarits (Hn, menu et footer, JSON-LD…), langues.
"""
import csv
import json
import os
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import sf
import web
from commun import (Annexe, Resultats, charger_acces, charger_profil, chemin, cle_url, lire_csv_simple,
                    nettoyer_url, normaliser, origine)


class Contexte:
    def __init__(self, dossier):
        self.dossier = dossier
        self.profil = charger_profil(dossier)
        self.res = Resultats(dossier)
        self.ann = Annexe(dossier)
        self.ref = self.res.ref
        acces = charger_acces(dossier) or {}
        acces.setdefault("preprod", self.profil.get("preprod", ""))
        self.client = web.Client(acces, ssl_verifie=self.profil.get("ssl_verifie", True),
                                 delai=self.profil.get("delai_requetes", 0.2))
        self.paralleles = int(self.profil.get("requetes_paralleles", 4))
        self.preprod = origine(self.profil.get("preprod", "")) if self.profil.get("preprod") else ""
        os.makedirs(chemin(dossier, "donnees"), exist_ok=True)

    def applicable(self, idc):
        a = self.ref[idc]["applicabilite"]
        return a == "toujours" or bool(self.profil["applicabilite"].get(a))

    def poser(self, idc, anomalies, preuve, details_ok="", details_ko="", ok_statut="OK", type_preuve="Constat observé"):
        if not self.applicable(idc):
            return
        onglet = self.ref[idc]["onglet_annexe"] or None
        if onglet:
            self.ann.onglets.setdefault(onglet, [])
            self.ann.sources.setdefault(onglet, set()).add(preuve)
            for a in anomalies:
                self.ann.ajouter(onglet, idc, a, preuve)
        if anomalies:
            self.res.poser(idc, "KO", type_preuve, preuve, details_ko or f"{len(anomalies)} cas.",
                           n_urls=len(anomalies), onglet=onglet, script="controles_web")
        else:
            self.res.poser(idc, ok_statut, type_preuve, preuve, details_ok or "Aucun cas.", n_urls=0,
                           script="controles_web")

    def manque(self, idc, raison):
        if self.applicable(idc):
            self.res.non_testable(idc, raison, type_preuve="Constat observé")

    def fin(self):
        self.res.enregistrer()
        self.ann.enregistrer()


# --- Sitemap -----------------------------------------------------------------

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def sitemap(dossier, max_fichiers=200):
    ctx = Contexte(dossier)
    url = ctx.profil.get("sitemap")
    if not url:
        ctx.manque("SIT-01", "URL du sitemap absente de profil.json.")
        ctx.manque("SIT-03", "URL du sitemap absente de profil.json.")
        return ctx.fin()
    a_lire, lus, urls, problemes, par_fichier = [url], set(), [], [], {}
    while a_lire and len(lus) < max_fichiers:
        u = a_lire.pop(0)
        if u in lus:
            continue
        lus.add(u)
        chaine, _ = ctx.client.suivre(u)
        r = chaine[-1]
        if r["status"] != 200:
            problemes.append({"Fichier sitemap": u, "Problème": f"Code {r['status'] or r['erreur']}"})
            continue
        try:
            racine = ElementTree.fromstring(r["corps"])
        except ElementTree.ParseError as e:
            problemes.append({"Fichier sitemap": u, "Problème": f"XML illisible : {e}"})
            continue
        tag = racine.tag.replace(NS, "")
        locs = [e.text.strip() for e in racine.iter() if e.tag.replace(NS, "") == "loc" and e.text]
        if tag == "sitemapindex":
            a_lire.extend(locs)
        else:
            par_fichier[u] = len(locs)
            urls.extend((l, u) for l in locs)
    with open(chemin(dossier, "donnees", "sitemap-urls.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["URL", "Fichier sitemap"])
        w.writerows(urls)
    with open(chemin(dossier, "donnees", "sitemap-fichiers.json"), "w", encoding="utf-8") as f:
        json.dump(par_fichier, f, ensure_ascii=False, indent=2)
    preuve = f"Requêtes sur {url} et ses sous-sitemaps ({len(lus)} fichiers lus)"
    if not par_fichier:
        ctx.res.poser("SIT-01", "KO", "Constat observé", preuve,
                      "Aucun fichier sitemap lisible. " + "; ".join(p["Problème"] for p in problemes),
                      script="controles_web")
    else:
        statut = "KO" if problemes else "OK"
        ctx.res.poser("SIT-01", statut, "Constat observé", preuve,
                      f"{len(par_fichier)} fichiers, {len(urls)} URLs." + (
                          " Fichiers en erreur : " + "; ".join(f"{p['Fichier sitemap']} ({p['Problème']})" for p in problemes)
                          if problemes else ""), script="controles_web")
    trop = [{"Fichier sitemap": f_, "URLs": n} for f_, n in par_fichier.items() if n > 50000]
    if par_fichier:
        ctx.res.poser("SIT-03", "KO" if trop else "OK", "Constat observé", preuve,
                      ("Fichiers au-delà de 50 000 URLs : " + ", ".join(f"{t['Fichier sitemap']} ({t['URLs']})" for t in trop))
                      if trop else f"Fichier le plus long : {max(par_fichier.values())} URLs.", script="controles_web")
    ctx.fin()
    return {"fichiers": len(par_fichier), "urls": len(urls), "problemes": problemes}


# --- Robots.txt et blocages de la préprod ---------------------------------------------

def bloque_tout(contenu):
    """Vrai si le groupe « User-agent: * » contient « Disallow: / »."""
    agents, regles, groupe_ouvert = [], [], False
    groupes = []
    for ligne in contenu.splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ":" not in ligne:
            continue
        cle, val = (x.strip() for x in ligne.split(":", 1))
        cle = cle.lower()
        if cle == "user-agent":
            if groupe_ouvert:
                groupes.append((agents, regles))
                agents, regles = [], []
            agents.append(val)
            groupe_ouvert = False
        elif cle in ("disallow", "allow"):
            regles.append((cle, val))
            groupe_ouvert = True
    groupes.append((agents, regles))
    return any("*" in a and ("disallow", "/") in r for a, r in groupes)


def robots(dossier):
    ctx = Contexte(dossier)
    url = ctx.profil.get("robots") or (ctx.preprod + "/robots.txt" if ctx.preprod else "")
    if not url:
        ctx.manque("ROB-01", "Adresse de la préprod absente de profil.json.")
        return ctx.fin()
    chaine, _ = ctx.client.suivre(url)
    r = chaine[-1]
    contenu = web.texte(r["corps"], r["headers"]) if r["status"] == 200 else ""
    if r["status"] == 200:
        with open(chemin(dossier, "donnees", "robots-preprod.txt"), "w", encoding="utf-8") as f:
            f.write(contenu)
    ctx.res.poser("ROB-01", "OK" if r["status"] == 200 else "KO", "Constat observé", f"Requête sur {url}",
                  f"Code {r['status'] or r['erreur']}." + (" Copie dans donnees/robots-preprod.txt." if contenu else ""),
                  script="controles_web")
    # PRE-02 : relevé des protections de la préprod
    blocages = []
    if bloque_tout(contenu):
        blocages.append("robots.txt : « Disallow: / » pour tous les robots")
    if ctx.preprod:
        accueil = ctx.client.suivre(ctx.preprod + "/")[0][-1]
        xr = accueil["headers"].get("x-robots-tag", "")
        if "noindex" in xr.lower():
            blocages.append(f"En-tête X-Robots-Tag : {xr}")
        if accueil["status"] == 200:
            p = web.analyser(accueil["url"], web.texte(accueil["corps"], accueil["headers"]))
            if "noindex" in p.meta_robots.lower():
                blocages.append(f"Meta robots de l'accueil : {p.meta_robots}")
        sans_auth = ctx.client.recuperer(ctx.preprod + "/", avec_auth=False)
        if sans_auth["status"] in (401, 403):
            blocages.append(f"Accès protégé (code {sans_auth['status']} sans identifiants)")
    with open(chemin(dossier, "donnees", "blocages-preprod.json"), "w", encoding="utf-8") as f:
        json.dump(blocages, f, ensure_ascii=False, indent=2)
    ctx.res.poser("PRE-02", "OK", "Constat observé", f"Requêtes sur {url} et sur l'accueil de la préprod",
                  ("Blocages à lever à la mise en ligne : " + " ; ".join(blocages)) if blocages
                  else "Aucun blocage relevé : vérifier que la préprod ne peut pas être indexée.", script="controles_web")
    ctx.fin()
    return {"robots": r["status"], "blocages": blocages}


# --- Redirections depuis l'ancien site -----------------------------------------------

def _plan(dossier, profil):
    nom = profil.get("plan_redirections")
    if not nom:
        return {}
    p = chemin(dossier, nom)
    if not os.path.exists(p):
        raise SystemExit(f"Plan de redirections introuvable : {p}")
    lignes = lire_csv_simple(p)
    plan = {}
    for l in lignes:
        if len(l) < 2 or not l[0].strip() or not re.match(r"https?://|/", l[0].strip()):
            continue  # ligne d'en-tête ou vide
        plan[cle_url(l[0])] = l[1].strip()
    return plan


def _meta(page_html, url):
    p = web.analyser(url, page_html)
    return p.meta_robots.lower(), p.canonical


def redirections(dossier, limite=None):
    ctx = Contexte(dossier)
    if not ctx.preprod:
        for idc in ("RED-01", "RED-02", "RED-03", "RED-04", "RED-05"):
            ctx.manque(idc, "Adresse de la préprod absente de profil.json.")
        return ctx.fin()
    exports, _ = sf.charger(chemin(dossier, "exports", "ancien-site"))
    ex = exports.get("internal_all")
    if not ex:
        for idc in ("RED-01", "RED-02", "RED-03", "RED-04", "RED-05"):
            ctx.manque(idc, "Export internal_all de l'ancien site absent de exports/ancien-site/.")
        return ctx.fin()
    if ex.manquantes("address", "status_code"):
        for idc in ("RED-01", "RED-02", "RED-03", "RED-04", "RED-05"):
            ctx.manque(idc, f"Colonnes introuvables dans {ex.fichier} : {ex.manquantes('address', 'status_code')}.")
        return ctx.fin()
    html = [l for l in ex.lignes if ex.num(l, "status_code") == 200 and
            (not ex.a("content_type") or "html" in ex.val(l, "content_type").lower())]
    plan = _plan(dossier, ctx.profil)
    limite = limite or int(ctx.profil.get("max_urls_redirections", 5000))
    a_tester = html[:limite]
    accueil = nettoyer_url(ctx.preprod + "/")
    accueil_noindex = None

    def tester(l):
        ancienne = ex.val(l, "address")
        testee = ctx.preprod + cle_url(ancienne)
        chaine, boucle = ctx.client.suivre(testee)
        fin = chaine[-1]
        sauts = len(chaine) - 1
        noindex, canonical = "", ""
        if fin["status"] == 200 and fin["corps"]:
            noindex, canonical = _meta(web.texte(fin["corps"], fin["headers"]), fin["url"])
        fin["corps"] = b""
        return {"ancienne": ancienne, "testee": testee, "finale": fin["url"], "code": fin["status"],
                "erreur": fin["erreur"], "sauts": sauts, "boucle": boucle, "noindex": "noindex" in noindex,
                "canonical": canonical, "inlinks": ex.num(l, "unique_inlinks") or ex.num(l, "inlinks") or 0}

    with ThreadPoolExecutor(max_workers=ctx.paralleles) as pool:
        resultats = list(pool.map(tester, a_tester))

    # noindex global : l'accueil de la préprod est en noindex
    r_acc = ctx.client.recuperer(ctx.preprod + "/")
    if r_acc["status"] == 200:
        accueil_noindex = "noindex" in _meta(web.texte(r_acc["corps"], r_acc["headers"]), r_acc["url"])[0]

    red1, red2, red3, red4 = [], [], [], []
    lignes_annexe = []
    for r in resultats:
        prevue = plan.get(cle_url(r["ancienne"]), "")
        statut = []
        if r["boucle"]:
            statut.append("Boucle")
        if r["code"] is None:
            statut.append("Erreur réseau : " + (r["erreur"] or ""))
        elif r["code"] in (404, 410):
            statut.append(f"Sans redirection ({r['code']})")
        elif r["code"] != 200 and not r["boucle"]:
            statut.append(f"Cible en {r['code']}")
        if prevue and r["code"] == 200 and cle_url(prevue) != cle_url(r["finale"]):
            statut.append("Cible différente du plan")
        if r["sauts"] > 1 and not r["boucle"]:
            statut.append(f"Chaîne ({r['sauts']} sauts)")
        vers_accueil = (r["code"] == 200 and nettoyer_url(r["finale"]) == accueil and cle_url(r["ancienne"]) != "/")
        if vers_accueil:
            statut.append("Redirigée vers l'accueil")
        non_indexable = False
        if r["code"] == 200:
            if r["canonical"] and nettoyer_url(r["canonical"]) != nettoyer_url(r["finale"]):
                non_indexable = True
                statut.append("Cible avec canonical vers une autre URL")
            elif r["noindex"] and not accueil_noindex:
                non_indexable = True
                statut.append("Cible en noindex")
        ligne = {"Ancienne URL": r["ancienne"], "URL testée": r["testee"], "Cible prévue (plan)": prevue,
                 "Cible obtenue": r["finale"], "Code final": r["code"] if r["code"] is not None else "",
                 "Sauts": r["sauts"], "Statut": " ; ".join(statut) or "OK"}
        ids = []
        if r["code"] in (404, 410) or r["code"] is None or "Cible différente du plan" in statut:
            red1.append(ligne)
            ids.append("RED-01")
        if r["code"] is not None and r["code"] not in (404, 410) and (r["code"] != 200 or non_indexable):
            red2.append(ligne)
            ids.append("RED-02")
        if r["boucle"] or r["sauts"] > 1:
            red3.append(ligne)
            ids.append("RED-03")
        if vers_accueil:
            red4.append(ligne)
            ids.append("RED-04")
        lignes_annexe.append((" ".join(ids) or "OK", ligne))

    # RED-05 : pages stratégiques de l'ancien site
    anciennes = [p["ancienne_url"] for p in ctx.profil["pages_strategiques"] if p.get("ancienne_url")]
    origine_red5 = "pages stratégiques de la fiche client"
    if not anciennes:
        tri = sorted(resultats, key=lambda r: -r["inlinks"])[:20]
        anciennes = [r["ancienne"] for r in tri]
        origine_red5 = "à défaut, les 20 pages les plus liées de l'ancien site"
    par_cle = {cle_url(r["ancienne"]): r for r in resultats}
    red5 = []
    for a in anciennes:
        r = par_cle.get(cle_url(a))
        if r is None:
            red5.append({"Ancienne URL": a, "Statut": "Absente du crawl de l'ancien site ou non testée"})
        elif r["code"] != 200 or (nettoyer_url(r["finale"]) == accueil and cle_url(a) != "/"):
            red5.append({"Ancienne URL": a, "Cible obtenue": r["finale"], "Code final": r["code"],
                         "Statut": "Pas de page équivalente"})

    # L'onglet Redirections reçoit la liste complète ; chaque contrôle compte ses propres cas.
    onglet = "Redirections"
    ctx.ann.onglets[onglet] = []
    ctx.ann.sources[onglet] = {ex.fichier, "requêtes sur la préprod"}
    for ids, ligne in lignes_annexe:
        ctx.ann.ajouter(onglet, ids, ligne, ex.fichier)
    partiel = len(html) > len(a_tester)
    portee = f"{len(a_tester)} URLs en 200 de l'ancien site testées sur la préprod" + (
        f" (sur {len(html)}, limite {limite})" if partiel else "")
    preuve = f"{ex.fichier} + requêtes sur {ctx.preprod}"
    for idc, cas, libelle in (("RED-01", red1, "sans redirection ou vers une cible différente du plan"),
                              ("RED-02", red2, "vers une cible en erreur ou non indexable"),
                              ("RED-03", red3, "en chaîne ou en boucle"),
                              ("RED-04", red4, "vers l'accueil")):
        if cas:
            ctx.res.poser(idc, "KO", "Constat observé", preuve, f"{len(cas)} URLs {libelle}. {portee}.",
                          n_urls=len(cas), onglet=onglet, script="controles_web")
        else:
            ctx.res.poser(idc, "Partiel" if partiel else "OK", "Constat observé", preuve, f"Aucune URL {libelle}. {portee}.",
                          n_urls=0, script="controles_web")
    if red5:
        for l in red5:
            ctx.ann.ajouter("Redirections-pages-strategiques", "RED-05", l, ex.fichier)
        ctx.res.poser("RED-05", "KO", "Constat observé", preuve,
                      f"{len(red5)} pages sur {len(anciennes)} sans équivalent ({origine_red5}).", n_urls=len(red5),
                      onglet="Redirections-pages-strategiques", script="controles_web")
    else:
        ctx.ann.onglets.setdefault("Redirections-pages-strategiques", [])
        ctx.ann.sources.setdefault("Redirections-pages-strategiques", set()).add(ex.fichier)
        ctx.res.poser("RED-05", "OK", "Constat observé", preuve,
                      f"{len(anciennes)} pages vérifiées ({origine_red5}).", n_urls=0, script="controles_web")
    if plan:
        absentes_plan = [c for c in plan if c not in par_cle]
        with open(chemin(dossier, "donnees", "plan-hors-ancien-crawl.json"), "w", encoding="utf-8") as f:
            json.dump(absentes_plan, f, ensure_ascii=False, indent=2)
    ctx.fin()
    return {"testees": len(a_tester), "red1": len(red1), "red2": len(red2), "red3": len(red3), "red4": len(red4),
            "red5": len(red5)}


# --- Gabarits ------------------------------------------------------------------

LOCAL_TYPES = {"LocalBusiness", "Store", "Restaurant", "ProfessionalService", "HomeAndConstructionBusiness",
               "MedicalBusiness", "LegalService", "AutomotiveBusiness", "FinancialService", "FoodEstablishment",
               "HealthAndBeautyBusiness", "LodgingBusiness", "RealEstateAgent", "SportsActivityLocation",
               "Dentist", "Electrician", "Plumber", "RoofingContractor", "HVACBusiness", "GeneralContractor"}
ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle"}


def _lien_propre(href, base):
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    u = urlsplit(urljoin(base, href))
    if u.scheme not in ("http", "https"):
        return None
    return urlunsplit((u.scheme, u.netloc.lower(), u.path or "/", u.query, ""))


def gabarits(dossier):
    ctx = Contexte(dossier)
    pages = []
    for g in ctx.profil["gabarits"]:
        if g.get("url"):
            pages.append((g.get("type", ""), g["url"]))
    for p in ctx.profil["pages_strategiques"]:
        if p.get("url") and p["url"] not in [u for _, u in pages]:
            pages.append(("page stratégique : " + p.get("nom", ""), p["url"]))
    if ctx.preprod and not any(cle_url(u) == "/" for _, u in pages):
        pages.insert(0, ("accueil", ctx.preprod + "/"))
    if not pages:
        for idc in ("HN-02", "HN-04", "LNK-01", "IMG-04", "PRE-01"):
            ctx.manque(idc, "Aucun gabarit ni page stratégique dans profil.json.")
        return ctx.fin()

    hote_preprod = urlsplit(ctx.preprod).netloc.lower()
    releves, erreurs = [], []
    for type_, url in pages:
        chaine, _ = ctx.client.suivre(url)
        r = chaine[-1]
        if r["status"] != 200:
            erreurs.append({"URL": url, "Type": type_, "Problème": f"Code {r['status'] or r['erreur']}"})
            continue
        brut = web.texte(r["corps"], r["headers"])
        p = web.analyser(r["url"], brut)
        types, objets, err_json = p.types_jsonld()
        en_dur = len(re.findall(r"""(?:href|src|srcset|content)\s*=\s*["']https?://""" + re.escape(hote_preprod), brut, re.I)) \
            if hote_preprod else 0
        releves.append({"type": type_, "url": r["url"], "page": p, "types": types, "objets": objets,
                        "erreurs_json": err_json, "en_dur": en_dur, "html_brut_mots": p.mots,
                        "html_brut_liens": len(p.liens)})

    preuve = f"Requêtes sur {len(releves)} pages de la préprod (gabarits et pages stratégiques)"
    # HN-02 sauts de niveau / HN-04 Hn dans header, footer, cookies / HN-01 liste pour l'agent
    hn2, hn4, liste_hn = [], [], []
    for rv in releves:
        precedent = None
        for h in rv["page"].hn:
            liste_hn.append({"URL": rv["url"], "Type": rv["type"], "Niveau": f"H{h['niveau']}", "Zone": h["zone"],
                             "Texte": h["texte"][:200]})
            if h["zone"] in ("header", "footer", "cookie"):
                hn4.append({"URL": rv["url"], "Type": rv["type"], "Niveau": f"H{h['niveau']}", "Zone": h["zone"],
                            "Texte": h["texte"][:200]})
            if precedent and h["niveau"] > precedent + 1:
                hn2.append({"URL": rv["url"], "Type": rv["type"], "Problème": f"H{precedent} suivi de H{h['niveau']}",
                            "Texte": h["texte"][:200]})
            precedent = h["niveau"]
    portee = f"{len(releves)} pages analysées"
    ctx.poser("HN-02", hn2, preuve, details_ok=f"Aucun saut de niveau sur les {portee}.", ok_statut="Partiel",
              details_ko=f"{len(hn2)} sauts de niveau ({portee}).")
    ctx.poser("HN-04", hn4, preuve, details_ok=f"Aucune Hn dans le header, le footer ni le bandeau cookies ({portee}).",
              details_ko=f"{len(hn4)} Hn dans le header, le footer ou le bandeau cookies ({portee}).")
    with open(chemin(dossier, "donnees", "hn-gabarits.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["URL", "Type", "Niveau", "Zone", "Texte"], delimiter=";")
        w.writeheader()
        w.writerows(liste_hn)

    # LNK-01 liens à la fois dans le menu (header, nav) et dans le footer
    doublons = {}
    for rv in releves:
        base = rv["url"]
        menu = {_lien_propre(l["href"], base) for l in rv["page"].liens if l["zone"] in ("header", "nav")}
        pied = {_lien_propre(l["href"], base) for l in rv["page"].liens if l["zone"] == "footer"}
        accueil = nettoyer_url(origine(base) + "/")
        for u in (menu & pied) - {None, accueil}:
            doublons.setdefault(u, []).append(rv["url"])
    lnk = [{"Lien": u, "Pages où il est dans le menu et le footer": len(v), "Exemple": v[0]} for u, v in doublons.items()]
    menu_vide = all(not any(l["zone"] in ("header", "nav") for l in rv["page"].liens) for rv in releves)
    if menu_vide:
        ctx.manque("LNK-01", "Aucun lien repéré dans un header ou un nav : la structure du thème n'est pas reconnue, "
                             "contrôle à faire dans le navigateur.")
    else:
        ctx.poser("LNK-01", lnk, preuve, details_ok=f"Aucun lien commun au menu et au footer ({portee}, lien vers l'accueil exclu).",
                  details_ko=f"{len(lnk)} liens à la fois dans le menu et le footer (lien vers l'accueil exclu). "
                             "Les liens légaux (mentions, CGV) peuvent être acceptés : à trier.")

    # IMG-04 favicon
    acc = next((rv for rv in releves if cle_url(rv["url"]) == "/"), releves[0] if releves else None)
    if acc:
        icones = acc["page"].icones or [origine(acc["url"]) + "/favicon.ico"]
        r = ctx.client.recuperer(icones[0])
        ok = r["status"] == 200
        ctx.res.poser("IMG-04", "OK" if ok else "KO", "Constat observé", f"Requête sur {icones[0]}",
                      ("Favicon déclarée dans le HTML" if acc["page"].icones else "Pas de balise link rel=icon, /favicon.ico testé")
                      + f" : code {r['status'] or r['erreur']}.", script="controles_web")

    # PRE-01 domaine de préprod écrit en dur
    en_dur = [{"URL": rv["url"], "Type": rv["type"], "Occurrences": rv["en_dur"]} for rv in releves if rv["en_dur"]]
    ctx.poser("PRE-01", en_dur, preuve, ok_statut="Partiel",
              details_ok=f"Aucune URL absolue vers {hote_preprod} dans le HTML ({portee}).",
              details_ko=f"URLs absolues vers {hote_preprod} sur {len(en_dur)} pages sur {len(releves)}. "
                         "Sur WordPress, elles sont normalement remplacées à la migration (rechercher-remplacer) : "
                         "à inscrire dans la checklist de mise en ligne.")

    # SD-01 à SD-07 présence des données structurées sur les gabarits
    def presents(filtre_types, filtre_gabarit=lambda t: True):
        concernes = [rv for rv in releves if filtre_gabarit(rv["type"].lower())]
        sans = [{"URL": rv["url"], "Type": rv["type"], "Types trouvés": ", ".join(sorted(rv["types"])) or "aucun"}
                for rv in concernes if not (rv["types"] & filtre_types)]
        return concernes, sans

    n_err = sum(len(rv["erreurs_json"]) for rv in releves)
    note_err = (f" {n_err} blocs JSON-LD illisibles (détail dans donnees/gabarits-html-brut.json)." if n_err else "")
    regles = [
        ("SD-01", {"BreadcrumbList"}, lambda t: t != "accueil"),
        ("SD-02", {"Review", "AggregateRating"}, lambda t: True),
        ("SD-03", {"Product", "Offer"}, lambda t: "produit" in t or "product" in t),
        ("SD-04", LOCAL_TYPES, lambda t: True),
        ("SD-05", {"Organization", "Corporation", "OnlineBusiness"} | LOCAL_TYPES, lambda t: True),
        ("SD-06", ARTICLE_TYPES, lambda t: "article" in t or "blog" in t or "actualit" in t),
    ]
    for idc, types_attendus, filtre in regles:
        if not ctx.applicable(idc):
            continue
        concernes, sans = presents(types_attendus, filtre)
        if not concernes:
            ctx.manque(idc, "Aucun gabarit de ce type dans profil.json.")
            continue
        une_seule_fois = idc in ("SD-02", "SD-04", "SD-05")  # suffit sur une page du site
        anomalies = ([] if len(sans) < len(concernes) else sans) if une_seule_fois else sans
        ctx.poser(idc, anomalies, preuve,
                  details_ok=f"Présent ({len(concernes)} pages concernées). La validité selon schema.org n'est pas contrôlée." + note_err,
                  details_ko="Absent sur les pages listées. La validité selon schema.org n'est pas contrôlée." + note_err)
    if ctx.applicable("SD-07"):
        articles = [o for rv in releves for o in rv["objets"]
                    if (set(o.get("@type") if isinstance(o.get("@type"), list) else [o.get("@type")]) & ARTICLE_TYPES)]
        if not articles:
            ctx.manque("SD-07", "Aucun objet Article dans les gabarits analysés.")
        else:
            sans_auteur = [o for o in articles if not o.get("author")]
            ctx.res.poser("SD-07", "KO" if sans_auteur else "OK", "Constat observé", preuve,
                          f"{len(sans_auteur)} objets Article sans author sur {len(articles)}.", script="controles_web")

    # Données pour l'agent : HTML brut (comparaison avec le rendu JavaScript, JS-01), erreurs
    with open(chemin(dossier, "donnees", "gabarits-html-brut.json"), "w", encoding="utf-8") as f:
        json.dump([{"type": rv["type"], "url": rv["url"], "mots_html_brut": rv["html_brut_mots"],
                    "liens_html_brut": rv["html_brut_liens"], "title": rv["page"].title,
                    "canonical": rv["page"].canonical, "meta_robots": rv["page"].meta_robots,
                    "lang": rv["page"].lang, "jsonld": sorted(rv["types"]),
                    "jsonld_illisible": rv["erreurs_json"]} for rv in releves] + [
                      {"erreur": e} for e in erreurs], f, ensure_ascii=False, indent=2)
    ctx.fin()
    return {"pages": len(releves), "erreurs": erreurs}


# --- Langues (site international) ----------------------------------------------------

def langues(dossier):
    ctx = Contexte(dossier)
    if not ctx.applicable("ML-03"):
        return ctx.fin()
    if not ctx.preprod:
        ctx.manque("ML-03", "Adresse de la préprod absente.")
        ctx.manque("ML-04", "Adresse de la préprod absente.")
        return ctx.fin()
    racine = ctx.preprod + "/"
    essais = {}
    for lang in ("fr-FR,fr;q=0.9", "en-US,en;q=0.9", "de-DE,de;q=0.9", "es-ES,es;q=0.9"):
        r = ctx.client.recuperer(racine, entetes={"Accept-Language": lang})
        essais[lang.split(",")[0]] = (r["status"], r.get("location"))
    preuve = f"Requêtes sur {racine} avec plusieurs langues de navigateur"
    codes = {k: v[0] for k, v in essais.items()}
    redirige = {k: v[1] for k, v in essais.items() if v[0] and 300 <= v[0] < 400}
    ctx.res.poser("ML-03", "KO" if redirige else "OK", "Constat observé", preuve,
                  ("La racine redirige : " + ", ".join(f"{k} vers {v}" for k, v in redirige.items()))
                  if redirige else "La racine répond sans redirection : " + ", ".join(f"{k} {c}" for k, c in codes.items()),
                  script="controles_web")
    cibles = set(redirige.values())
    selon_langue = len(cibles) > 1 or (redirige and len(redirige) < len(essais))
    ctx.res.poser("ML-04", "KO" if selon_langue else "OK", "Constat observé", preuve,
                  "La réponse change selon la langue du navigateur : " + json.dumps(essais, ensure_ascii=False)
                  if selon_langue else "Même réponse quelle que soit la langue du navigateur.", script="controles_web")
    ctx.fin()
    return essais
