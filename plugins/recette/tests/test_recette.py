"""Jeu d'essai : une fausse préprod locale (protégée par mot de passe) et de faux
exports Screaming Frog, avec des anomalies connues. Chaque anomalie doit être
trouvée, avec le bon nombre, et rien d'autre.

    python -m unittest discover -s plugins/recette/tests
"""
import base64
import csv
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import recette  # noqa: E402

AUTH = "Basic " + base64.b64encode(b"test:secret").decode()


def page(titre, corps, extra_head=""):
    return f"""<!doctype html><html lang="fr"><head><title>{titre}</title>
<meta name="robots" content="noindex, nofollow">{extra_head}</head><body>
<header class="site-header"><nav><a href="/">Accueil</a><a href="/services/">Services</a>
<a href="/contact/">Contact</a></nav></header>
<main>{corps}</main>
<footer class="site-footer"><h3>Nous suivre</h3><a href="/contact/">Contact</a><a href="/mentions/">Mentions</a></footer>
</body></html>"""


PAGES = {
    "/": page("Accueil", "<h1>Bienvenue</h1><h2>Nos services</h2><h4>Détail</h4><p>Texte</p>",
              '<link rel="icon" href="/favicon.ico"><script type="application/ld+json">'
              '{"@context":"https://schema.org","@type":"Organization","name":"Test"}</script>'),
    "/services/": page("Services", "<article><header class=\"entry-header\"><h1>Services</h1></header>"
                       "<h2>Offre</h2><h3>Détail</h3></article>",
                       '<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList",'
                       '"itemListElement":[]}</script>'),
    "/contact/": page("Contact", "<h1>Contact</h1>"),
    "/orpheline/": page("Orpheline", "<h1>Orpheline</h1>"),
}
REDIRECTIONS = {
    "/ancien-service.html": "/services",
    "/services": "/services/",
    "/ancienne-page": "/",
}


class Preprod(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def envoyer(self, code, corps=b"", type_="text/html; charset=utf-8", entetes=None):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if self.headers.get("Authorization") != AUTH:
            return self.envoyer(401, b"auth", entetes={"WWW-Authenticate": 'Basic realm="preprod"'})
        hote = f"http://{self.headers['Host']}"
        p = self.path
        if p == "/robots.txt":
            return self.envoyer(200, f"User-agent: *\nDisallow: /\nSitemap: {hote}/sitemap.xml\n".encode(), "text/plain")
        if p == "/sitemap.xml":
            return self.envoyer(200, f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     f'<sitemap><loc>{hote}/sitemap-pages.xml</loc></sitemap></sitemapindex>'.encode(),
                                "application/xml")
        if p == "/sitemap-pages.xml":
            locs = "".join(f"<url><loc>{hote}{u}</loc></url>" for u in ("/", "/services/", "/contact/", "/orpheline/", "/supprimee/"))
            return self.envoyer(200, f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'.encode(),
                                "application/xml")
        if p == "/favicon.ico":
            return self.envoyer(200, b"\x00", "image/x-icon")
        if p in REDIRECTIONS:
            return self.envoyer(301, entetes={"Location": REDIRECTIONS[p]})
        if p in PAGES:
            return self.envoyer(200, PAGES[p].encode())
        return self.envoyer(404, b"introuvable")


def ecrire_csv(chemin_, entetes, lignes):
    os.makedirs(os.path.dirname(chemin_), exist_ok=True)
    with open(chemin_, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(lignes)


class TestRecette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), Preprod)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.serveur.server_port}"
        cls.dossier = tempfile.mkdtemp(prefix="Recette-SEO-Test-")
        d = cls.dossier
        with open(os.path.join(d, "profil.json"), "w", encoding="utf-8") as f:
            json.dump({
                "client": "Test", "preprod": base, "ancien_site": "https://ancien.example",
                "sitemap": base + "/sitemap.xml", "robots": base + "/robots.txt",
                "pages_strategiques": [
                    {"nom": "Services", "url": base + "/services/", "ancienne_url": "https://ancien.example/ancien-service.html"},
                    {"nom": "Contact", "url": base + "/contact/", "ancienne_url": "https://ancien.example/disparue"},
                ],
                "gabarits": [{"type": "accueil", "url": base + "/"}, {"type": "service", "url": base + "/services/"}],
                "applicabilite": {"pagination": True, "international": True},
                "delai_requetes": 0, "requetes_paralleles": 2,
            }, f)
        with open(os.path.join(d, "acces-preprod.local.json"), "w", encoding="utf-8") as f:
            json.dump({"preprod": base, "type": "basic", "identifiant": "test", "mot_de_passe": "secret"}, f)
        ent = ["Address", "Content Type", "Status Code", "Status", "Indexability", "Indexability Status",
               "Title 1", "Title 1 Pixel Width", "Meta Description 1", "Meta Description 1 Pixel Width",
               "H1-1", "H1-2", "Meta Robots 1", "Canonical Link Element 1", "Word Count", "Crawl Depth",
               "Unique Inlinks", "Size (bytes)", "Hash", 'rel="next" 1', 'rel="prev" 1']
        h = "text/html; charset=UTF-8"
        desc = "Une description de longueur correcte pour le test, assez longue pour passer."

        def ligne(chemin_, titre, h1, mots, prof, liens, hash_, canonical=None, px=300, prev=""):
            u = base + chemin_
            return [u, h, "200", "OK", "Non-Indexable", "noindex", titre, px, desc, 600, h1, "", "noindex, nofollow",
                    canonical if canonical is not None else u, mots, prof, liens, 20000, hash_, "", prev]

        ecrire_csv(os.path.join(d, "exports", "preprod", "internal_all.csv"), ent, [
            ligne("/", "Accueil", "Bienvenue", 500, 0, 10, "a1"),
            ligne("/services/", "Services", "Services", 150, 1, 2, "a2"),
            ligne("/contact/", "Contact", "Contact", 300, 1, 10, "a3"),
            ligne("/Produit_Test/", "Contact", "", 300, 2, 10, "a4"),
            ligne("/blog/", "Blog", "Blog", 300, 1, 10, "a5"),
            ligne("/blog/page/2/", "Blog page 2", "Blog page 2", 300, 2, 10, "a6", canonical=base + "/blog/",
                  prev=base + "/blog/"),
            [base + "/img/lourde.jpg", "image/jpeg", "200", "OK", "Indexable", "", "", "", "", "", "", "", "", "",
             "", 2, 1, 250000, "", "", ""],
        ])
        ecrire_csv(os.path.join(d, "exports", "preprod", "client_error_(4xx)_inlinks.csv"),
                   ["Type", "Source", "Destination", "Anchor", "Status Code"],
                   [["Hyperlink", base + "/", base + "/supprimee/", "Ancien lien", "404"],
                    ["Hyperlink", base + "/contact/", base + "/supprimee/", "Ancien lien", "404"]])
        ecrire_csv(os.path.join(d, "exports", "ancien-site", "internal_all.csv"),
                   ["Address", "Content Type", "Status Code", "Unique Inlinks"],
                   [["https://ancien.example/ancien-service.html", h, "200", "30"],
                    ["https://ancien.example/ancienne-page", h, "200", "5"],
                    ["https://ancien.example/disparue", h, "200", "8"],
                    ["https://ancien.example/contact/", h, "200", "20"]])
        cls.sortie = {n: recette.commande(n, d) for n in
                      ("preparer", "sitemap", "robots", "sf", "redirections", "gabarits", "langues", "verifier")}
        with open(os.path.join(d, "donnees", "resultats.json"), encoding="utf-8") as f:
            cls.res = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def statut(self, idc, statut, n=None):
        r = self.res.get(idc)
        self.assertIsNotNone(r, f"{idc} sans résultat")
        self.assertEqual(r["statut"], statut, f"{idc} : {r}")
        if n is not None:
            self.assertEqual(r["n_urls"], n, f"{idc} : {r}")

    def test_verification_sans_erreur(self):
        v = self.sortie["verifier"]
        self.assertEqual(v["erreurs"], [], v)

    def test_profil(self):
        self.statut("SD-03", "Non applicable")
        self.statut("SIT-02", "Après mise en ligne")

    def test_exports(self):
        self.statut("COD-02", "KO", 2)
        self.statut("COD-01", "Non testable")
        self.statut("URL-01", "KO", 1)
        self.statut("URL-03", "KO", 1)
        self.statut("URL-08", "OK", 0)
        self.statut("HN-03", "KO", 1)            # H1 manquant sur /Produit_Test/
        self.statut("TIT-01", "KO", 2)           # title « Contact » en double
        self.statut("PAG-01", "KO", 1)
        self.statut("IMG-02", "KO", 1)
        self.statut("CON-03", "KO", 1)           # /services/ à 150 mots
        self.statut("MAI-03", "KO", 1)           # /services/ sous la médiane des liens
        self.statut("IDX-03", "OK", 0)           # noindex global ignoré

    def test_sitemap(self):
        self.statut("SIT-01", "OK")
        self.statut("SIT-03", "OK")
        self.statut("SIT-04", "KO", 1)           # /supprimee/ en 404
        self.statut("IDX-01", "KO", 4)           # 2 du sitemap hors crawl, 2 pages indexables hors sitemap
        self.statut("MAI-04", "KO", 1)           # /orpheline/

    def test_robots(self):
        self.statut("ROB-01", "OK")
        self.assertIn("Disallow", self.res["PRE-02"]["details"])
        self.assertIn("401", self.res["PRE-02"]["details"])

    def test_redirections(self):
        self.statut("RED-01", "KO", 1)           # /disparue
        self.statut("RED-03", "KO", 1)           # chaîne de 2 sauts
        self.statut("RED-04", "KO", 1)           # vers l'accueil
        self.statut("RED-02", "OK", 0)
        self.statut("RED-05", "KO", 1)           # Contact (ancienne /disparue) sans équivalent

    def test_gabarits(self):
        self.statut("HN-02", "KO", 2)            # H2 puis H4 (accueil), H1 puis H3 du footer (contact)
        self.statut("HN-04", "KO", 3)            # H3 du footer sur les 3 pages
        self.statut("LNK-01", "KO", 1)           # /contact/ dans le menu et le footer
        self.statut("IMG-04", "OK")
        self.statut("SD-01", "KO", 1)            # Contact sans BreadcrumbList
        self.statut("SD-05", "OK")

    def test_langues(self):
        self.statut("ML-03", "OK")
        self.statut("ML-04", "OK")


if __name__ == "__main__":
    unittest.main()
