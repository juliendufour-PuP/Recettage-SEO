"""Requêtes HTTP vers la préprod et lecture du HTML (bibliothèque standard).

- Les redirections ne sont jamais suivies automatiquement : chaque saut est relevé.
- L'accès basic auth n'est envoyé qu'au domaine de la préprod.
- Débit limité : peu de requêtes en parallèle, délai entre deux requêtes.
"""
import base64
import gzip
import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

AGENT = "PumpUp-Recette-SEO/0.1 (+recette preprod)"
TAILLE_MAX = 5 * 1024 * 1024
VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
         "track", "wbr"}
MOTS_ZONES = {
    "cookie": re.compile(r"cookie|consent|gdpr|rgpd|tarteaucitron|cmplz|didomi|axeptio|onetrust|cookiebot", re.I),
}
# Classes ou id qui désignent l'en-tête et le pied de page du site (pas « entry-header » d'un article).
ZONES_SITE = {
    "header": {"site-header", "masthead", "elementor-location-header", "header", "main-header", "top-header",
               "site-header-wrap", "et-top-navigation", "main-header-bar"},
    "footer": {"site-footer", "colophon", "elementor-location-footer", "footer", "main-footer", "et-footer-nav",
               "main-footer-wrap"},
}


class _SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, acces=None, ssl_verifie=True, delai=0.2):
        self.acces = acces or {}
        hote = urlsplit(self.acces.get("preprod", "")).netloc.lower()
        self.hote_preprod = hote
        self.entete_auth = None
        if self.acces.get("identifiant"):
            jeton = f"{self.acces['identifiant']}:{self.acces.get('mot_de_passe', '')}".encode()
            self.entete_auth = "Basic " + base64.b64encode(jeton).decode()
        ctx = ssl.create_default_context()
        if not ssl_verifie:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(_SansRedirection(), urllib.request.HTTPSHandler(context=ctx))
        self.delai = delai
        self._verrou = threading.Lock()
        self._derniere = 0.0

    def _attendre(self):
        with self._verrou:
            ecart = time.monotonic() - self._derniere
            if ecart < self.delai:
                time.sleep(self.delai - ecart)
            self._derniere = time.monotonic()

    def recuperer(self, url, entetes=None, avec_auth=True, timeout=20):
        """Une requête GET, sans suivre les redirections."""
        self._attendre()
        h = {"User-Agent": AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        h.update(entetes or {})
        hote = urlsplit(url).netloc.lower()
        if avec_auth and self.entete_auth and hote == self.hote_preprod:
            h["Authorization"] = self.entete_auth
        h.update({k: v for k, v in (self.acces.get("en_tetes_supplementaires") or {}).items()} if hote == self.hote_preprod else {})
        req = urllib.request.Request(url, headers=h, method="GET")
        try:
            rep = self.opener.open(req, timeout=timeout)
            statut, entetes_rep, corps = rep.status, dict(rep.headers), rep.read(TAILLE_MAX)
        except urllib.error.HTTPError as e:
            statut, entetes_rep = e.code, dict(e.headers or {})
            try:
                corps = e.read(TAILLE_MAX)
            except Exception:
                corps = b""
        except Exception as e:  # réseau, DNS, SSL, délai
            return {"url": url, "status": None, "erreur": f"{type(e).__name__}: {e}", "headers": {}, "corps": b""}
        if corps[:2] == b"\x1f\x8b":
            try:
                corps = gzip.decompress(corps)
            except OSError:
                pass
        entetes_rep = {k.lower(): v for k, v in entetes_rep.items()}
        loc = entetes_rep.get("location")
        return {"url": url, "status": statut, "headers": entetes_rep, "corps": corps,
                "location": urljoin(url, loc) if loc else None, "erreur": None}

    def suivre(self, url, max_sauts=10, entetes=None):
        """Suit les redirections une par une. Retourne la liste des réponses (sans les corps intermédiaires)."""
        chaine, vues = [], set()
        courant = url
        for _ in range(max_sauts + 1):
            r = self.recuperer(courant, entetes=entetes)
            boucle = courant in vues
            vues.add(courant)
            chaine.append(r)
            if boucle or not r["status"] or not (300 <= r["status"] < 400) or not r.get("location"):
                return chaine, boucle
            for x in chaine[:-1]:
                x["corps"] = b""
            courant = r["location"]
        return chaine, False


def texte(corps, entetes=None):
    ct = (entetes or {}).get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
        try:
            return corps.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return corps.decode("utf-8", "replace")


class Page(HTMLParser):
    """Relève titres Hn, liens, balises SEO et JSON-LD, avec la zone de la page où ils se trouvent."""

    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.pile = []  # (balise, zone)
        self.hn = []    # dict(niveau, texte, zone)
        self.liens = []  # dict(href, zone, texte)
        self.meta_robots = ""
        self.canonical = ""
        self.icones = []
        self.jsonld_brut = []
        self.lang = ""
        self.title = ""
        self._hn_courant = None
        self._lien_courant = None
        self._dans_jsonld = False
        self._dans_title = False
        self._buffer = []
        self.mots = 0

    def zone(self):
        return self.pile[-1][1] if self.pile else "main"

    def _zone_de(self, balise, attrs):
        parent = self.zone()
        if parent == "cookie":
            return "cookie"
        a = dict(attrs)
        attr = " ".join(v or "" for k, v in attrs if k in ("id", "class"))
        if MOTS_ZONES["cookie"].search(attr):
            return "cookie"
        if parent in ("header", "footer"):
            return parent
        jetons = set(attr.lower().split())
        role = (a.get("role") or "").lower()
        # Un <header> ou <footer> dans <main> ou <article> est celui du contenu, pas celui du site.
        dans_contenu = any(b in ("main", "article") for b, _ in self.pile)
        if role == "banner" or jetons & ZONES_SITE["header"] or (balise == "header" and not dans_contenu):
            return "header"
        if role == "contentinfo" or jetons & ZONES_SITE["footer"] or (balise == "footer" and not dans_contenu):
            return "footer"
        if balise == "nav" or parent == "nav":
            return "nav"
        return parent

    def handle_starttag(self, balise, attrs):
        a = dict(attrs)
        zone = self._zone_de(balise, attrs)
        if balise not in VIDES:
            self.pile.append((balise, zone))
        if balise == "html":
            self.lang = a.get("lang", "")
        elif balise == "meta" and (a.get("name") or "").lower() == "robots":
            self.meta_robots = a.get("content", "")
        elif balise == "link":
            rel = (a.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = urljoin(self.url, a.get("href", ""))
            if "icon" in rel:
                self.icones.append(urljoin(self.url, a.get("href", "")))
        elif balise == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._dans_jsonld, self._buffer = True, []
        elif balise == "title":
            self._dans_title, self._buffer = True, []
        elif re.fullmatch(r"h[1-6]", balise):
            self._hn_courant = {"niveau": int(balise[1]), "texte": [], "zone": zone}
        elif balise == "a" and a.get("href"):
            self._lien_courant = {"href": a["href"], "zone": zone, "texte": []}

    def handle_endtag(self, balise):
        if balise == "script" and self._dans_jsonld:
            self.jsonld_brut.append("".join(self._buffer))
            self._dans_jsonld = False
        elif balise == "title" and self._dans_title:
            self.title = "".join(self._buffer).strip()
            self._dans_title = False
        elif re.fullmatch(r"h[1-6]", balise) and self._hn_courant:
            h = self._hn_courant
            h["texte"] = re.sub(r"\s+", " ", "".join(h["texte"])).strip()
            self.hn.append(h)
            self._hn_courant = None
        elif balise == "a" and self._lien_courant:
            l = self._lien_courant
            l["texte"] = re.sub(r"\s+", " ", "".join(l["texte"])).strip()
            self.liens.append(l)
            self._lien_courant = None
        for i in range(len(self.pile) - 1, -1, -1):
            if self.pile[i][0] == balise:
                del self.pile[i:]
                break

    def handle_data(self, data):
        if self._dans_jsonld or self._dans_title:
            self._buffer.append(data)
            return
        if self.pile and self.pile[-1][0] in ("script", "style", "noscript", "template"):
            return
        if self._hn_courant:
            self._hn_courant["texte"].append(data)
        if self._lien_courant:
            self._lien_courant["texte"].append(data)
        self.mots += len(re.findall(r"\w+", data))

    def types_jsonld(self):
        """Retourne (types trouvés, objets, erreurs de syntaxe)."""
        types, objets, erreurs = set(), [], []

        def parcourir(o):
            if isinstance(o, list):
                for x in o:
                    parcourir(x)
            elif isinstance(o, dict):
                t = o.get("@type")
                for x in (t if isinstance(t, list) else [t]):
                    if isinstance(x, str):
                        types.add(x)
                objets.append(o)
                for v in o.values():
                    if isinstance(v, (list, dict)):
                        parcourir(v)

        for brut in self.jsonld_brut:
            try:
                parcourir(json.loads(brut))
            except json.JSONDecodeError as e:
                erreurs.append(str(e))
        return types, objets, erreurs


def analyser(url, html):
    p = Page(url)
    try:
        p.feed(html)
        p.close()
    except Exception:  # HTML très cassé : on garde ce qui a été lu
        pass
    return p
