"""Contrôles calculés sur les exports Screaming Frog de la préprod.

Tout chiffre écrit ici vient d'un comptage sur les fichiers d'export.
Les contrôles qualitatifs (langue des slugs, taxonomie des titles…) ne sont pas
tranchés ici : le script prépare les données dans donnees/ pour les agents.
"""
import csv
import json
import os
import re
import statistics
from collections import defaultdict
from urllib.parse import urlsplit, parse_qsl

import sf
from commun import Annexe, Resultats, charger_profil, chemin, cle_url, nettoyer_url, normaliser

PARAMS_SESSION = {"sid", "sessionid", "session_id", "phpsessid", "jsessionid", "aspsessionid", "cfid",
                  "cftoken", "sess", "s_id"}
MOTIF_PAGINATION = re.compile(r"(?:/page/|[?&](?:page|p|paged|pg)=)(\d+)", re.I)


class Contexte:
    def __init__(self, dossier):
        self.dossier = dossier
        self.profil = charger_profil(dossier)
        self.seuils = self.profil["seuils"]
        self.res = Resultats(dossier)
        self.ann = Annexe(dossier)
        self.exports, self.inconnus = sf.charger(chemin(dossier, "exports", "preprod"))
        self.ref = self.res.ref
        self.ia = self.exports.get("internal_all")
        self.par_cle = {}
        self.html = []
        self.noindex_global = False
        if self.ia:
            self._preparer()

    # -- préparation ----------------------------------------------------------
    def _preparer(self):
        ia = self.ia
        for l in ia.lignes:
            self.par_cle.setdefault(cle_url(ia.val(l, "address")), l)
        if ia.a("content_type"):
            self.html = [l for l in ia.lignes if "html" in ia.val(l, "content_type").lower()]
        else:
            self.html = [l for l in ia.lignes
                         if not re.search(r"\.(jpe?g|png|gif|webp|svg|css|js|pdf|ico|woff2?|ttf|mp4)(\?|$)",
                                          ia.val(l, "address"), re.I)]
        html200 = [l for l in self.html if self.code(l) == 200]
        avec_noindex = [l for l in html200 if self.noindex_propre(l)]
        self.noindex_global = len(html200) >= 5 and len(avec_noindex) >= 0.9 * len(html200)

    def code(self, l):
        v = self.ia.num(l, "status_code")
        return int(v) if v is not None else None

    def noindex_propre(self, l):
        ia = self.ia
        txt = " ".join([ia.val(l, "meta_robots"), ia.val(l, "x_robots"), ia.val(l, "indexability_status")]).lower()
        return "noindex" in txt

    def canonical_ailleurs(self, l):
        can = self.ia.val(l, "canonical")
        return bool(can) and nettoyer_url(can) != nettoyer_url(self.ia.val(l, "address"))

    def indexable(self, l):
        """Indexable en ignorant le noindex global de la préprod (contrôles « adapte »)."""
        if self.code(l) != 200 or self.canonical_ailleurs(l):
            return False
        if self.noindex_propre(l) and not self.noindex_global:
            return False
        return True

    def applicable(self, id_controle):
        a = self.ref[id_controle]["applicabilite"]
        return a == "toujours" or bool(self.profil["applicabilite"].get(a))

    def strategiques(self):
        return [p for p in self.profil["pages_strategiques"] if p.get("url")]

    def preuve(self, export, *canons):
        return f"{export.fichier}, colonnes : " + ", ".join(export.nom_colonne(c) for c in canons)

    # -- écriture --------------------------------------------------------------
    def conclure(self, id_controle, anomalies, preuve, details_ok="", details_ko="", ok_statut="OK"):
        """anomalies : liste de dict (lignes d'annexe)."""
        if not self.applicable(id_controle):
            return
        onglet = self.ref[id_controle]["onglet_annexe"] or None
        if onglet:
            # L'onglet est réécrit même vide, pour ne pas garder une liste d'un ancien lancement.
            self.ann.onglets.setdefault(onglet, [])
            self.ann.sources.setdefault(onglet, set()).add(preuve.split(",")[0])
        for a in anomalies:
            if onglet:
                self.ann.ajouter(onglet, id_controle, a, preuve.split(",")[0])
        n = len(anomalies)
        if n:
            self.res.poser(id_controle, "KO", "Constat export", preuve, details_ko or f"{n} cas.", n_urls=n,
                           onglet=onglet, script="controles_sf")
        else:
            self.res.poser(id_controle, ok_statut, "Constat export", preuve, details_ok or "Aucun cas.",
                           n_urls=0, onglet=None, script="controles_sf")

    def manque(self, id_controle, raison):
        if self.applicable(id_controle):
            self.res.non_testable(id_controle, raison)


# --- Contrôles -----------------------------------------------------------------

def inlinks(ctx, id_controle, code_export, libelle):
    ex = ctx.exports.get(code_export)
    if not ex:
        return ctx.manque(id_controle, f"Export {code_export} absent (voir templates/exports-screaming-frog.md).")
    if ex.manquantes("source", "destination"):
        return ctx.manque(id_controle, f"Colonnes introuvables dans {ex.fichier} : {ex.manquantes('source', 'destination')}.")
    lignes = [{"Page source": ex.val(l, "source"), "Lien vers": ex.val(l, "destination"),
               "Code": ex.val(l, "status_code"), "Type de lien": ex.val(l, "link_type"),
               "Ancre ou alt": ex.val(l, "anchor")} for l in ex.lignes]
    pages = len({l["Page source"] for l in lignes})
    cibles = len({l["Lien vers"] for l in lignes})
    ctx.conclure(id_controle, lignes, ctx.preuve(ex, "source", "destination"),
                 details_ko=f"{len(lignes)} liens {libelle}, depuis {pages} pages, vers {cibles} URLs.")


def chaines(ctx):
    ex = ctx.exports.get("redirect_chains")
    if not ex:
        return ctx.manque("COD-04", "Export redirect_chains absent.")
    if not ex.a("address"):
        return ctx.manque("COD-04", f"Colonne Address introuvable dans {ex.fichier}.")
    lignes = []
    for l in ex.lignes:
        n = ex.num(l, "n_redirects")
        boucle = ex.val(l, "loop").lower() in ("true", "vrai", "oui", "yes", "1")
        if boucle or n is None or n >= 2:
            lignes.append({"URL de départ": ex.val(l, "address"), "URL finale": ex.val(l, "final_address"),
                           "Redirections": "" if n is None else int(n), "Boucle": "oui" if boucle else "non"})
    ctx.conclure("COD-04", lignes, ctx.preuve(ex, "address", "n_redirects"))


def urls(ctx):
    ia = ctx.ia
    pb = defaultdict(list)
    for l in ctx.html:
        u = ia.val(l, "address")
        p = urlsplit(u)
        if re.search(r"_|%20|\+", p.path):
            pb["URL-01"].append((u, "Séparateur autre que « - »"))
        if re.search(r"%[89a-fA-F][0-9a-fA-F]", p.path + p.query) or any(ord(c) > 127 for c in p.path + p.query):
            pb["URL-02"].append((u, "Caractère non ASCII"))
        if re.search(r"[A-Z]", p.path):
            pb["URL-03"].append((u, "Majuscule"))
        params = {normaliser(k) for k, _ in parse_qsl(p.query, keep_blank_values=True)}
        if params & PARAMS_SESSION:
            pb["URL-05"].append((u, "Identifiant de session : " + ", ".join(sorted(params & PARAMS_SESSION))))
        if len(u) > ctx.seuils["url_max"]:
            pb["URL-08"].append((u, f"{len(u)} caractères (seuil {ctx.seuils['url_max']})"))
    preuve = ctx.preuve(ia, "address", "content_type")
    for idc in ("URL-01", "URL-02", "URL-03", "URL-05", "URL-08"):
        ctx.conclure(idc, [{"URL": u, "Problème": m} for u, m in pb[idc]], preuve)
    # Données pour l'analyse qualitative des slugs (URL-04, URL-06, URL-07)
    with open(chemin(ctx.dossier, "donnees", "slugs.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["URL", "Chemin", "Profondeur répertoires", "Title", "H1"])
        for l in ctx.html:
            u = ia.val(l, "address")
            chemin_url = urlsplit(u).path
            w.writerow([u, chemin_url, len([s for s in chemin_url.split("/") if s]), ia.val(l, "title"), ia.val(l, "h1_1")])


def https(ctx):
    if not ctx.applicable("SEC-01"):
        return
    preprod = ctx.profil.get("preprod", "")
    if preprod.startswith("http://"):
        ctx.res.poser("SEC-01", "Après mise en ligne", "Constat observé", f"Adresse de préprod : {preprod}",
                      "La préprod n'est pas en https : contrôle à refaire à la mise en ligne.", script="controles_sf")
        return
    ia = ctx.ia
    lignes = [{"URL": ia.val(l, "address"), "Problème": "Page en http"} for l in ctx.html
              if ia.val(l, "address").startswith("http://")]
    ex = ctx.exports.get("insecure_content")
    sources = [ctx.preuve(ia, "address")]
    if ex:
        sources.append(ex.fichier)
        for l in ex.lignes:
            lignes.append({"URL": ex.val(l, "source") or ex.val(l, "address"),
                           "Problème": "Contenu non sécurisé : " + (ex.val(l, "destination") or "")})
    ctx.conclure("SEC-01", lignes, " + ".join(sources),
                 details_ok="" if ex else "Aucune page en http. Export insecure_content absent : contenu mixte non vérifié.",
                 ok_statut="OK" if ex else "Partiel")


def strategiques_indexables(ctx):
    pages = ctx.strategiques()
    if not pages:
        return ctx.manque("IDX-03", "Aucune page stratégique dans profil.json.")
    lignes = []
    for p in pages:
        l = ctx.par_cle.get(cle_url(p["url"]))
        if l is None:
            lignes.append({"URL": p["url"], "Page": p.get("nom", ""), "Problème": "Absente du crawl"})
        elif not ctx.indexable(l):
            raison = f"Code {ctx.code(l)}" if ctx.code(l) != 200 else (
                "Canonical vers " + ctx.ia.val(l, "canonical") if ctx.canonical_ailleurs(l) else "Noindex propre à la page")
            lignes.append({"URL": p["url"], "Page": p.get("nom", ""), "Problème": raison})
    ctx.conclure("IDX-03", lignes, ctx.preuve(ctx.ia, "address", "status_code", "canonical", "meta_robots"),
                 details_ok=f"{len(pages)} pages stratégiques indexables.")


def filtres(ctx):
    ia = ctx.ia
    lignes = [{"URL": ia.val(l, "address"), "Problème": "URL à paramètres indexable"}
              for l in ctx.html if urlsplit(ia.val(l, "address")).query and ctx.indexable(l)]
    ctx.conclure("FIL-01", lignes, ctx.preuve(ia, "address", "canonical", "meta_robots"),
                 details_ok="Aucune URL à paramètres indexable dans le crawl. Le test des filtres dans le navigateur reste à faire.",
                 ok_statut="Partiel")


def canonicals(ctx):
    ia = ctx.ia
    if not ia.a("canonical"):
        ctx.manque("CAN-01", f"Colonne canonical introuvable dans {ia.fichier}.")
        ctx.manque("CAN-02", f"Colonne canonical introuvable dans {ia.fichier}.")
        return
    base = [l for l in ctx.html if ctx.code(l) == 200 and (ctx.noindex_global or not ctx.noindex_propre(l))]
    c1, c2 = [], []
    for l in base:
        u, can = ia.val(l, "address"), ia.val(l, "canonical")
        if not can:
            c1.append({"URL": u, "Canonical": "", "Problème": "Canonical absente"})
        elif nettoyer_url(can) != nettoyer_url(u):
            c1.append({"URL": u, "Canonical": can, "Problème": "Canonical vers une autre URL"})
            cible = ctx.par_cle.get(cle_url(can))
            if cible is None:
                c2.append({"URL": u, "Canonical": can, "Problème": "Cible absente du crawl"})
            elif ctx.code(cible) != 200:
                c2.append({"URL": u, "Canonical": can, "Problème": f"Cible en {ctx.code(cible)}"})
            elif not ctx.indexable(cible):
                c2.append({"URL": u, "Canonical": can, "Problème": "Cible non indexable"})
    preuve = ctx.preuve(ia, "address", "canonical", "status_code")
    ctx.conclure("CAN-01", c1, preuve, details_ko=f"{len(c1)} pages sur {len(base)} sans canonical sur elles-mêmes. "
                 "Une canonical vers une autre URL peut être voulue : à confirmer page par page.")
    ctx.conclure("CAN-02", c2, preuve)


def pagination(ctx):
    if not ctx.applicable("PAG-01"):
        return
    ia = ctx.ia
    paginees = []
    for l in ctx.html:
        m = MOTIF_PAGINATION.search(ia.val(l, "address"))
        if ia.val(l, "rel_prev") or (m and int(m.group(1)) >= 2):
            paginees.append(l)
    if not paginees:
        for idc in ("PAG-01", "PAG-03"):
            ctx.manque(idc, "Aucune page 2 ou suivante repérée dans le crawl (ni rel=prev, ni motif /page/N ou ?page=N), "
                            "alors que la fiche client annonce des listes paginées : à vérifier dans le navigateur.")
        return
    c1 = [{"URL": ia.val(l, "address"), "Canonical": ia.val(l, "canonical"), "Problème": "Canonical vers une autre page"}
          for l in paginees if ctx.canonical_ailleurs(l)]
    ctx.conclure("PAG-01", c1, ctx.preuve(ia, "address", "canonical"))
    if ia.manquantes("rel_prev", "rel_next"):
        ctx.manque("PAG-03", f"Colonnes rel next / prev introuvables dans {ia.fichier}.")
    else:
        c3 = [{"URL": ia.val(l, "address"), "Problème": "Balise rel=prev absente"} for l in paginees if not ia.val(l, "rel_prev")]
        ctx.conclure("PAG-03", c3, ctx.preuve(ia, "address", "rel_prev", "rel_next"))


def contenu(ctx):
    ia = ctx.ia
    # CON-02 doublons
    if ia.manquantes("hash") and ia.manquantes("near_dup"):
        ctx.manque("CON-02", f"Colonnes Hash et quasi-doublons introuvables dans {ia.fichier} "
                             "(activer Near Duplicates et lancer Crawl Analysis).")
    else:
        lignes = []
        groupes = defaultdict(list)
        for l in ctx.html:
            if ctx.code(l) == 200 and ia.val(l, "hash"):
                groupes[ia.val(l, "hash")].append(ia.val(l, "address"))
        for i, urls_ in enumerate([g for g in groupes.values() if len(g) > 1], 1):
            for u in urls_:
                lignes.append({"URL": u, "Problème": "Doublon exact", "Groupe": f"E{i}", "Proche de": ""})
        if ia.a("near_dup"):
            for l in ctx.html:
                n = ia.num(l, "near_dup")
                if n and n > 0:
                    lignes.append({"URL": ia.val(l, "address"), "Problème": f"Quasi-doublon ({int(n)})",
                                   "Groupe": "", "Proche de": ia.val(l, "closest")})
        ctx.conclure("CON-02", lignes, ctx.preuve(ia, *[c for c in ("hash", "near_dup") if ia.a(c)]),
                     details_ok="" if ia.a("near_dup") else "Aucun doublon exact. Quasi-doublons non disponibles dans l'export.",
                     ok_statut="OK" if ia.a("near_dup") else "Partiel")
    # CON-03 et données des pages stratégiques
    pages = ctx.strategiques()
    lignes_info = []
    for p in pages:
        l = ctx.par_cle.get(cle_url(p["url"]))
        lignes_info.append({
            "Page": p.get("nom", ""), "URL": p["url"], "Dans le crawl": "oui" if l else "non",
            "Code": ctx.code(l) if l else "", "Mots": ia.val(l, "word_count") if l else "",
            "Profondeur": ia.val(l, "depth") if l else "", "Liens entrants uniques": ia.val(l, "unique_inlinks") if l else "",
            "Indexable (hors noindex global)": ("oui" if ctx.indexable(l) else "non") if l else "",
        })
    with open(chemin(ctx.dossier, "donnees", "pages-strategiques.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_info[0].keys()) if lignes_info else ["Page"], delimiter=";")
        w.writeheader()
        w.writerows(lignes_info)
    if not pages:
        ctx.manque("CON-03", "Aucune page stratégique dans profil.json.")
    elif not ia.a("word_count"):
        ctx.manque("CON-03", f"Colonne Word Count introuvable dans {ia.fichier}.")
    else:
        seuil = ctx.seuils["mots_min"]
        faibles = [{"URL": i["URL"], "Page": i["Page"], "Mots": i["Mots"], "Problème": f"Moins de {seuil} mots"}
                   for i in lignes_info if i["Mots"] not in ("", None) and float(str(i["Mots"]).replace(",", ".")) < seuil]
        ctx.conclure("CON-03", faibles, ctx.preuve(ia, "address", "word_count"))


def h1(ctx):
    ia = ctx.ia
    if not ia.a("h1_1"):
        return ctx.manque("HN-03", f"Colonne H1-1 introuvable dans {ia.fichier}.")
    base = [l for l in ctx.html if ctx.indexable(l)]
    lignes, vus = [], defaultdict(list)
    for l in base:
        u, t = ia.val(l, "address"), ia.val(l, "h1_1")
        if not t:
            lignes.append({"URL": u, "H1": "", "Problème": "H1 manquant"})
            continue
        if ia.val(l, "h1_2"):
            lignes.append({"URL": u, "H1": t, "Problème": "Plusieurs H1 (2e : " + ia.val(l, "h1_2") + ")"})
        vus[t.strip().lower()].append((u, t))
    for groupe in vus.values():
        if len(groupe) > 1:
            for u, t in groupe:
                lignes.append({"URL": u, "H1": t, "Problème": f"H1 identique sur {len(groupe)} pages"})
    ctx.conclure("HN-03", lignes, ctx.preuve(ia, "address", "h1_1", "h1_2"))


def images(ctx):
    ex = ctx.exports.get("images_missing_alt_inlinks")
    if not ex:
        ctx.manque("IMG-01", "Export images_missing_alt_inlinks absent.")
    else:
        lignes = [{"Page": ex.val(l, "source"), "Image": ex.val(l, "destination")} for l in ex.lignes]
        ctx.conclure("IMG-01", lignes, ctx.preuve(ex, "source", "destination"),
                     details_ko=f"{len(lignes)} images sans alt, sur {len({l['Page'] for l in lignes})} pages. "
                                "Les images décoratives peuvent garder un alt vide : à trier.")
    ia = ctx.ia
    if not ia.a("content_type", "size"):
        return ctx.manque("IMG-02", f"Colonnes Content Type ou Size introuvables dans {ia.fichier}.")
    imgs = [l for l in ia.lignes if ia.val(l, "content_type").lower().startswith("image/")]
    if not imgs:
        return ctx.manque("IMG-02", "Aucune image dans internal_all : vérifier que les images sont crawlées.")
    seuil = ctx.seuils["image_ko_max"]
    lourdes = []
    for l in imgs:
        taille = ia.num(l, "size")
        if taille and taille > seuil * 1024:
            lourdes.append({"Image": ia.val(l, "address"), "Poids (Ko)": round(taille / 1024),
                            "Problème": f"Plus de {seuil} Ko"})
    ctx.conclure("IMG-02", lourdes, ctx.preuve(ia, "address", "content_type", "size"),
                 details_ok=f"Aucune des {len(imgs)} images au-delà de {seuil} Ko. Le surdimensionnement se contrôle avec Lighthouse.",
                 ok_statut="Partiel")


def metas(ctx):
    ia = ctx.ia
    s = ctx.seuils
    base = [l for l in ctx.html if ctx.indexable(l)]
    for idc, champ, px, longueur, mn_px, mx_px, mn_c, mx_c, nom in (
            ("TIT-01", "title", "title_px", "title_len", s["title_px_min"], s["title_px_max"], s["title_car_min"], s["title_car_max"], "Title"),
            ("DES-01", "desc", "desc_px", "desc_len", s["desc_px_min"], s["desc_px_max"], s["desc_car_min"], s["desc_car_max"], "Meta description")):
        if not ia.a(champ):
            ctx.manque(idc, f"Colonne {nom} 1 introuvable dans {ia.fichier}.")
            if idc == "DES-01":
                ctx.manque("DES-02", f"Colonne {nom} 1 introuvable dans {ia.fichier}.")
            continue
        lignes, vus = [], defaultdict(list)
        par_px = ia.a(px)
        for l in base:
            u, t = ia.val(l, "address"), ia.val(l, champ)
            if not t:
                lignes.append({"URL": u, nom: "", "Problème": "Manquant"})
                continue
            vus[t.strip().lower()].append((u, t))
            mesure = ia.num(l, px) if par_px else len(t)
            mn, mx, unite = (mn_px, mx_px, "px") if par_px else (mn_c, mx_c, "caractères")
            if mesure is not None and mesure > mx:
                lignes.append({"URL": u, nom: t, "Problème": f"Trop long ({int(mesure)} {unite}, max {mx})"})
            elif mesure is not None and mesure < mn:
                lignes.append({"URL": u, nom: t, "Problème": f"Trop court ({int(mesure)} {unite}, min {mn})"})
        doublons = []
        for groupe in vus.values():
            if len(groupe) > 1:
                for u, t in groupe:
                    doublons.append({"URL": u, nom: t, "Problème": f"Identique sur {len(groupe)} pages"})
        preuve = ctx.preuve(ia, *[c for c in ("address", champ, px if par_px else longueur) if ia.a(c)])
        if idc == "TIT-01":
            ctx.conclure("TIT-01", lignes + doublons, preuve)
        else:
            ctx.conclure("DES-01", lignes, preuve)
            ctx.conclure("DES-02", doublons, preuve)


def maillage(ctx):
    ia = ctx.ia
    pages = ctx.strategiques()
    if not pages:
        ctx.manque("MAI-01", "Aucune page stratégique dans profil.json.")
        ctx.manque("MAI-03", "Aucune page stratégique dans profil.json.")
        return
    mx = ctx.seuils["profondeur_max"]
    if not ia.a("depth"):
        ctx.manque("MAI-01", f"Colonne Crawl Depth introuvable dans {ia.fichier}.")
    else:
        profondes = []
        for p in pages:
            l = ctx.par_cle.get(cle_url(p["url"]))
            if l is None:
                profondes.append({"URL": p["url"], "Page": p.get("nom", ""), "Problème": "Absente du crawl"})
            elif (ia.num(l, "depth") or 0) > mx:
                profondes.append({"URL": p["url"], "Page": p.get("nom", ""),
                                  "Problème": f"À {int(ia.num(l, 'depth'))} clics (max {mx})"})
        ctx.conclure("MAI-01", profondes, ctx.preuve(ia, "address", "depth"),
                     details_ok=f"Pages stratégiques à {mx} clics ou moins. La comparaison avec l'arborescence cible reste à faire.",
                     ok_statut="Partiel")
    col = "unique_inlinks" if ia.a("unique_inlinks") else "inlinks"
    if not ia.a(col):
        return ctx.manque("MAI-03", f"Colonne Unique Inlinks introuvable dans {ia.fichier}.")
    valeurs = [ia.num(l, col) for l in ctx.html if ctx.indexable(l) and ia.num(l, col) is not None]
    if not valeurs:
        return ctx.manque("MAI-03", "Aucune page indexable avec un nombre de liens entrants.")
    mediane = statistics.median(valeurs)
    faibles = []
    for p in pages:
        l = ctx.par_cle.get(cle_url(p["url"]))
        if l is not None and (ia.num(l, col) or 0) < mediane:
            faibles.append({"URL": p["url"], "Page": p.get("nom", ""), "Liens entrants": int(ia.num(l, col) or 0),
                            "Problème": f"Sous la médiane du site ({mediane:g})"})
    ctx.conclure("MAI-03", faibles, ctx.preuve(ia, "address", col),
                 details_ok=f"Toutes les pages stratégiques sont au-dessus de la médiane du site ({mediane:g} liens entrants).")


# --- Croisements avec le sitemap ---------------------------------------------------

def urls_sitemap(ctx):
    p = chemin(ctx.dossier, "donnees", "sitemap-urls.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig", newline="") as f:
            return [r["URL"] for r in csv.DictReader(f, delimiter=";")], "donnees/sitemap-urls.csv"
    ex = ctx.exports.get("sitemaps")
    if ex and ex.a("address"):
        return [ex.val(l, "address") for l in ex.lignes], ex.fichier
    return None, None


def croisements(ctx, recuperer=None, limite=2000):
    """SIT-04, SIT-05, IDX-01, MAI-04. `recuperer(url)` teste une URL absente du crawl."""
    liste, source = urls_sitemap(ctx)
    if liste is None:
        for idc in ("SIT-04", "SIT-05", "IDX-01", "MAI-04"):
            ctx.manque(idc, "Ni donnees/sitemap-urls.csv (commande sitemap) ni export sitemaps.")
        return
    ia = ctx.ia
    preuve = f"{source} + {ia.fichier}"
    non200, non_index, absentes, orphelines = [], [], [], []
    testees = 0
    for u in liste:
        l = ctx.par_cle.get(cle_url(u))
        if l is not None:
            code = ctx.code(l)
            if code != 200:
                non200.append({"URL": u, "Code": code, "Origine du code": "crawl"})
            elif not ctx.indexable(l):
                non_index.append({"URL": u, "Problème": "Canonical vers " + ia.val(l, "canonical")
                                  if ctx.canonical_ailleurs(l) else "Noindex propre à la page"})
            n = ia.num(l, "unique_inlinks") if ia.a("unique_inlinks") else ia.num(l, "inlinks")
            if n == 0 and cle_url(u) != "/":
                orphelines.append({"URL": u, "Problème": "Aucun lien interne (trouvée par le sitemap)"})
        else:
            absentes.append({"URL": u, "Problème": "Dans le sitemap, absente du crawl"})
            if recuperer and testees < limite:
                testees += 1
                r = recuperer(u)
                code = r.get("status")
                if code != 200:
                    non200.append({"URL": u, "Code": code or r.get("erreur", ""), "Origine du code": "requête"})
                else:
                    orphelines.append({"URL": u, "Problème": "En 200 mais absente du crawl (aucun lien interne trouvé)"})
    dans_sitemap = {cle_url(u) for u in liste}
    hors_sitemap = [{"URL": ia.val(l, "address"), "Problème": "Indexable, absente du sitemap"}
                    for l in ctx.html if ctx.indexable(l) and cle_url(ia.val(l, "address")) not in dans_sitemap]
    reste = len(absentes) - testees if recuperer else len(absentes)
    ctx.conclure("SIT-04", non200, preuve,
                 details_ok=f"{len(liste)} URLs dans le sitemap, toutes en 200." if not reste else
                 f"{len(liste)} URLs dans le sitemap. {reste} URLs absentes du crawl non testées.",
                 ok_statut="OK" if not reste else "Partiel")
    ctx.conclure("SIT-05", non_index, preuve,
                 details_ok=("Noindex global de la préprod ignoré. " if ctx.noindex_global else "") + "Aucune URL non indexable.")
    ctx.conclure("IDX-01", absentes + hors_sitemap, preuve,
                 details_ko=f"{len(absentes)} URLs du sitemap absentes du crawl, {len(hors_sitemap)} pages indexables absentes du sitemap.")
    ctx.conclure("MAI-04", orphelines, preuve)


# --- Lancement ---------------------------------------------------------------

def lancer(dossier, recuperer=None):
    ctx = Contexte(dossier)
    os.makedirs(chemin(dossier, "donnees"), exist_ok=True)
    inventaire = {
        "exports_reconnus": {c: e.fichier for c, e in ctx.exports.items()},
        "lignes": {c: len(e) for c, e in ctx.exports.items()},
        "colonnes_introuvables_internal_all": [c for c in sf.ALIAS_COLONNES if ctx.ia and c not in ctx.ia.index
                                               and c in ("address", "status_code", "indexability", "content_type",
                                                         "title", "desc", "h1_1", "canonical", "meta_robots",
                                                         "word_count", "depth", "unique_inlinks", "size", "hash")],
        "fichiers_non_reconnus": ctx.inconnus,
        "noindex_global_preprod": ctx.noindex_global,
    }
    with open(chemin(dossier, "donnees", "inventaire-exports.json"), "w", encoding="utf-8") as f:
        json.dump(inventaire, f, ensure_ascii=False, indent=2)
    if not ctx.ia:
        raise SystemExit("Export internal_all introuvable dans exports/preprod/ : rien n'est calculé. "
                         f"Fichiers non reconnus : {ctx.inconnus}")
    inlinks(ctx, "COD-01", "redirection_3xx_inlinks", "vers des redirections")
    inlinks(ctx, "COD-02", "client_error_4xx_inlinks", "vers des erreurs 4xx")
    inlinks(ctx, "COD-03", "server_error_5xx_inlinks", "vers des erreurs 5xx")
    chaines(ctx)
    urls(ctx)
    https(ctx)
    strategiques_indexables(ctx)
    filtres(ctx)
    canonicals(ctx)
    pagination(ctx)
    contenu(ctx)
    h1(ctx)
    images(ctx)
    metas(ctx)
    maillage(ctx)
    croisements(ctx, recuperer)
    ctx.res.enregistrer()
    ctx.ann.enregistrer()
    return inventaire
