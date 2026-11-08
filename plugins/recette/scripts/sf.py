"""Lecture des exports Screaming Frog, interface en anglais ou en français.

La langue n'a pas d'importance :
- un fichier est reconnu par son nom (anglais ou français) ; sinon par son
  contenu (colonnes présentes, codes HTTP des lignes) ; sinon par la
  correspondance manuelle de exports/<preprod|ancien-site>/correspondance.json :
      {"internal_all": "mon-export.csv"}
- une colonne est retrouvée par son nom exact (alias anglais et français),
  sinon par ses mots-clés, quel que soit leur ordre (« Title 1 Length »,
  « Longueur du titre 1 » et « Titre 1 longueur » donnent la même colonne).

Une colonne ou un fichier introuvable n'est jamais deviné au hasard : le
contrôle concerné passe en « Non testable » et `recette.py exports` dit
précisément ce qui manque.
"""
import csv
import json
import os
import re
from collections import Counter

from commun import lire_csv_simple, normaliser

# code -> motifs (regex sur le nom de fichier normalisé, sans extension)
MOTIFS_FICHIERS = {
    "internal_all": [r"^internal_all$", r"^interne_(tout|all|tous)$", r"^internal_tout$"],
    "redirection_3xx_inlinks": [r"3xx.*(inlinks|liens_entrants)", r"(inlinks|liens_entrants).*3xx"],
    "client_error_4xx_inlinks": [r"4xx.*(inlinks|liens_entrants)", r"(inlinks|liens_entrants).*4xx"],
    "server_error_5xx_inlinks": [r"5xx.*(inlinks|liens_entrants)", r"(inlinks|liens_entrants).*5xx"],
    "redirect_chains": [r"redirect_chains?", r"chaines?_de_redirections?"],
    "insecure_content": [r"insecure_content", r"contenu_non_securise"],
    "images_missing_alt_inlinks": [r"missing_alt", r"alt_manquant", r"sans_(texte_)?alt"],
    "sitemaps": [r"^sitemaps?_(all|tout|tous)$"],
}

# nom canonique -> en-têtes possibles (normalisés)
ALIAS_COLONNES = {
    "address": ["address", "adresse", "url"],
    "status_code": ["status_code", "code_de_statut", "code_d_etat", "code_http", "code_de_reponse"],
    "status": ["status", "statut", "etat"],
    "indexability": ["indexability", "indexabilite"],
    "indexability_status": ["indexability_status", "statut_d_indexabilite", "statut_de_l_indexabilite",
                            "statut_indexabilite"],
    "content_type": ["content_type", "type_de_contenu"],
    "title": ["title_1", "titre_1"],
    "title_len": ["title_1_length", "longueur_du_title_1", "longueur_du_titre_1", "titre_1_longueur"],
    "title_px": ["title_1_pixel_width", "largeur_en_pixels_du_title_1", "largeur_en_pixels_du_titre_1",
                 "titre_1_largeur_en_pixels"],
    "desc": ["meta_description_1", "meta_description_1"],
    "desc_len": ["meta_description_1_length", "longueur_de_la_meta_description_1",
                 "meta_description_1_longueur"],
    "desc_px": ["meta_description_1_pixel_width", "largeur_en_pixels_de_la_meta_description_1",
                "meta_description_1_largeur_en_pixels"],
    "h1_1": ["h1_1"],
    "h1_2": ["h1_2"],
    "canonical": ["canonical_link_element_1", "element_de_lien_canonique_1", "lien_canonique_1",
                  "balise_canonique_1"],
    "meta_robots": ["meta_robots_1"],
    "x_robots": ["x_robots_tag_1"],
    "word_count": ["word_count", "nombre_de_mots"],
    "depth": ["crawl_depth", "profondeur_de_crawl", "profondeur_d_exploration", "profondeur"],
    "inlinks": ["inlinks", "liens_entrants"],
    "unique_inlinks": ["unique_inlinks", "liens_entrants_uniques"],
    "size": ["size_bytes", "taille_octets", "size", "taille"],
    "redirect_url": ["redirect_url", "url_de_redirection"],
    "hash": ["hash"],
    "near_dup": ["no_near_duplicates", "nb_de_quasi_doublons", "nombre_de_quasi_doublons",
                 "n_de_quasi_doublons"],
    "closest": ["closest_similarity_match", "correspondance_de_similarite_la_plus_proche"],
    "rel_next": ["rel_next_1"],
    "rel_prev": ["rel_prev_1"],
    "source": ["source", "from", "de"],
    "destination": ["destination", "to", "vers"],
    "link_type": ["type"],
    "anchor": ["anchor", "ancre", "anchor_text", "texte_d_ancre"],
    "final_address": ["final_address", "adresse_finale", "url_finale"],
    "n_redirects": ["number_of_redirects", "nombre_de_redirections"],
    "loop": ["loop", "boucle"],
    "alt": ["alt_text", "texte_alternatif", "texte_alt", "alt"],
}

# Mots-clés, en second recours : nom canonique -> règles. Une règle est
# (groupes, interdits) : l'en-tête doit contenir un mot de chaque groupe et
# aucun mot interdit. Les mots vides (de, du, la, of…) sont ignorés.
_LONG = {"length", "longueur", "pixel", "pixels", "largeur", "width"}
_N = lambda *mots: set(mots)
MOTS_CLES = {
    "address": [([_N("address", "adresse", "url")], _N("redirect", "redirection", "final", "finale", "canonical",
                                                       "canonique", "source", "destination", "type", "encoded",
                                                       "encodee", "encode", "originale", "original"))],
    "status_code": [([_N("code"), _N("status", "statut", "etat", "http", "reponse", "response")], set())],
    "indexability": [([_N("indexability", "indexabilite")], _N("status", "statut", "etat", "raison"))],
    "indexability_status": [([_N("indexability", "indexabilite"), _N("status", "statut", "etat", "raison")], set())],
    "content_type": [([_N("type"), _N("content", "contenu")], set())],
    "title": [([_N("title", "titre"), _N("1")], _LONG)],
    "title_len": [([_N("title", "titre"), _N("1"), _N("length", "longueur")], _N("pixel", "pixels"))],
    "title_px": [([_N("title", "titre"), _N("1"), _N("pixel", "pixels", "width", "largeur")], set())],
    "desc": [([_N("meta"), _N("description"), _N("1")], _LONG)],
    "desc_len": [([_N("meta"), _N("description"), _N("1"), _N("length", "longueur")], _N("pixel", "pixels"))],
    "desc_px": [([_N("meta"), _N("description"), _N("1"), _N("pixel", "pixels", "width", "largeur")], set())],
    "h1_1": [([_N("h1"), _N("1")], _LONG | _N("2"))],
    "h1_2": [([_N("h1"), _N("2")], _LONG)],
    "canonical": [([_N("canonical", "canonique", "canonicals", "canoniques"), _N("1")], set())],
    "meta_robots": [([_N("meta"), _N("robots"), _N("1")], set())],
    "x_robots": [([_N("x"), _N("robots"), _N("1")], set())],
    "word_count": [([_N("word", "words", "mots"), _N("count", "nombre", "nb")], set())],
    "depth": [([_N("depth", "profondeur")], _N("folder", "dossier", "repertoire"))],
    "inlinks": [([_N("inlinks")], _N("unique", "uniques", "js", "total", "pourcentage", "percent")),
                ([_N("liens"), _N("entrants")], _N("unique", "uniques", "js", "total", "pourcentage", "percent"))],
    "unique_inlinks": [([_N("unique", "uniques"), _N("inlinks")], _N("js", "pourcentage", "percent")),
                       ([_N("unique", "uniques"), _N("liens"), _N("entrants")], _N("js", "pourcentage", "percent"))],
    "size": [([_N("size", "taille")], _N("transferred", "transfere", "transferee", "transferes", "total", "image"))],
    "redirect_url": [([_N("redirect", "redirection"), _N("url", "adresse")], _N("type", "final", "finale"))],
    "near_dup": [([_N("near", "quasi"), _N("duplicates", "duplicate", "doublons", "doublon")],
                  _N("closest", "proche", "similarity", "similarite"))],
    "closest": [([_N("closest", "proche"), _N("similarity", "similarite")], set())],
    "rel_next": [([_N("rel"), _N("next", "suivant", "suiv"), _N("1")], set())],
    "rel_prev": [([_N("rel"), _N("prev", "precedent", "prec"), _N("1")], set())],
    "anchor": [([_N("anchor", "ancre")], set())],
    "final_address": [([_N("final", "finale"), _N("address", "adresse", "url")], set())],
    "n_redirects": [([_N("number", "nombre", "nb"), _N("redirects", "redirections", "redirection")], set())],
    "loop": [([_N("loop", "boucle")], set())],
    "alt": [([_N("alt")], _N("length", "longueur"))],
}
MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "l", "d", "en", "of", "the", "a", "par", "per", "no", "n"}


def _mots(entete_norm):
    return {m for m in entete_norm.split("_") if m and m not in MOTS_VIDES}


def _correspond(mots, regle):
    groupes, interdits = regle
    return all(mots & g for g in groupes) and not (mots & interdits)


def indexer_colonnes(entetes):
    """{nom canonique: index} : alias exacts d'abord, mots-clés ensuite, une colonne par nom."""
    norm = [normaliser(e) for e in entetes]
    index, prises = {}, set()
    for canon, alias in ALIAS_COLONNES.items():
        for a in alias:
            if a in norm and norm.index(a) not in prises:
                index[canon] = norm.index(a)
                prises.add(index[canon])
                break
    mots = [_mots(n) for n in norm]
    for canon, regles in MOTS_CLES.items():
        if canon in index:
            continue
        candidats = [i for i, m in enumerate(mots) if i not in prises and any(_correspond(m, r) for r in regles)]
        if len(candidats) >= 1:
            # en cas de doute, l'en-tête le plus court est le plus proche (« Titre 1 » plutôt que « Titre 1 bis »)
            i = min(candidats, key=lambda k: len(mots[k]))
            index[canon] = i
            prises.add(i)
    return index


class Export:
    def __init__(self, code, path):
        self.code = code
        self.path = path
        self.fichier = os.path.basename(path)
        lignes = lire_csv_simple(path)
        # Certains exports ont une ligne de titre avant les en-têtes : on prend,
        # parmi les premières lignes, celle qui contient le plus de colonnes connues.
        debut, meilleur = 0, 0
        for i, l in enumerate(lignes[:5]):
            n = len(indexer_colonnes(l))
            if n > meilleur:
                debut, meilleur = i, n
        self.entetes = lignes[debut] if lignes else []
        self.lignes = [l for l in lignes[debut + 1:] if any(c.strip() for c in l)]
        self.index = indexer_colonnes(self.entetes)

    def a(self, *canons):
        return all(c in self.index for c in canons)

    def manquantes(self, *canons):
        return [c for c in canons if c not in self.index]

    def nom_colonne(self, canon):
        return self.entetes[self.index[canon]] if canon in self.index else canon

    def val(self, ligne, canon, defaut=""):
        i = self.index.get(canon)
        if i is None or i >= len(ligne):
            return defaut
        return ligne[i].strip()

    def num(self, ligne, canon):
        v = self.val(ligne, canon).replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return None

    def __len__(self):
        return len(self.lignes)


def _par_nom(nom):
    base = normaliser(os.path.splitext(nom)[0])
    return next((c for c, motifs in MOTIFS_FICHIERS.items() if any(re.search(m, base) for m in motifs)), None)


def _par_contenu(path):
    """Reconnaît un export d'après ses colonnes et ses lignes, sans regarder la langue.

    Retourne (code, raison) ou (None, raison). Ne tranche que sur des signes nets.
    """
    try:
        e = Export(None, path)
    except (OSError, UnicodeDecodeError, csv.Error) as err:
        return None, f"illisible ({err})"
    if e.a("n_redirects") or (e.a("final_address") and e.a("loop")):
        return "redirect_chains", "colonnes de chaîne de redirection"
    if e.a("source", "destination"):
        if e.a("alt"):
            return "images_missing_alt_inlinks", "liens source → image avec une colonne alt"
        familles = Counter(e.val(l, "status_code")[:1] for l in e.lignes if e.val(l, "status_code")[:1].isdigit())
        if familles:
            famille, n = familles.most_common(1)[0]
            if n >= 0.8 * sum(familles.values()) and famille in "345":
                code = {"3": "redirection_3xx_inlinks", "4": "client_error_4xx_inlinks",
                        "5": "server_error_5xx_inlinks"}[famille]
                return code, f"liens source → destination, codes {famille}xx"
        dest = [e.val(l, "destination") for l in e.lignes]
        src = [e.val(l, "source") for l in e.lignes]
        if dest and all(d.startswith("http://") for d in dest) and all(s.startswith("https://") for s in src):
            return "insecure_content", "pages https qui chargent des ressources http"
        return None, "liens source → destination sans signe distinctif"
    if e.a("address", "status_code", "content_type"):
        return "internal_all", f"une ligne par URL avec code HTTP et type de contenu ({len(e.entetes)} colonnes)"
    return None, "aucune signature d'export connue"


def _nb_colonnes(path):
    try:
        return len(Export(None, path).entetes)
    except (OSError, UnicodeDecodeError, csv.Error):
        return 0


def identifier(dossier_exports, details=None):
    """Retourne ({code: chemin}, [fichiers non reconnus]).

    `details`, s'il est fourni, reçoit {fichier: "comment il a été reconnu"}.
    """
    trouves, inconnus = {}, []
    details = details if details is not None else {}
    if not os.path.isdir(dossier_exports):
        return trouves, inconnus
    manuel = {}
    p = os.path.join(dossier_exports, "correspondance.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            manuel = json.load(f)
    for code, fichier in manuel.items():
        trouves[code] = os.path.join(dossier_exports, fichier)
        details[fichier] = f"{code} (correspondance.json)"
    restants = []
    for nom in sorted(os.listdir(dossier_exports)):
        if not nom.lower().endswith(".csv") or nom in manuel.values():
            continue
        code = _par_nom(nom)
        if code and code not in trouves:
            trouves[code] = os.path.join(dossier_exports, nom)
            details[nom] = f"{code} (nom du fichier)"
        else:
            restants.append(nom)
    # Second passage : les fichiers au nom inconnu (interface traduite, fichier renommé).
    # Si plusieurs fichiers ont la même signature, le plus complet (le plus de colonnes) l'emporte.
    candidats = {}
    for nom in restants:
        code, raison = _par_contenu(os.path.join(dossier_exports, nom))
        if code and code not in trouves:
            candidats.setdefault(code, []).append((nom, raison))
        else:
            inconnus.append(nom)
            details[nom] = "non reconnu : " + (raison if not code else f"{code} déjà fourni par un autre fichier")
    for code, liste in candidats.items():
        liste.sort(key=lambda x: -_nb_colonnes(os.path.join(dossier_exports, x[0])))
        (nom, raison), autres = liste[0], liste[1:]
        trouves[code] = os.path.join(dossier_exports, nom)
        details[nom] = f"{code} (contenu : {raison})"
        for autre, _ in autres:
            inconnus.append(autre)
            details[autre] = f"non reconnu : ressemble à {code}, mais {nom} est plus complet"
    return trouves, sorted(inconnus)


def diagnostic(dossier_exports, indispensables=None):
    """Ce que les scripts comprennent de chaque export : à lancer avant la recette."""
    details = {}
    exports, inconnus = charger(dossier_exports, details)
    attendues = {
        "internal_all": ["address", "status_code", "content_type", "indexability", "indexability_status", "title",
                         "desc", "h1_1", "canonical", "meta_robots", "word_count", "depth", "unique_inlinks",
                         "size", "hash"],
        "redirection_3xx_inlinks": ["source", "destination", "status_code"],
        "client_error_4xx_inlinks": ["source", "destination", "status_code"],
        "server_error_5xx_inlinks": ["source", "destination", "status_code"],
        "redirect_chains": ["address", "final_address", "n_redirects"],
        "insecure_content": ["source", "destination"],
        "images_missing_alt_inlinks": ["source", "destination"],
    }
    fichiers = {}
    for code, e in exports.items():
        fichiers[e.fichier] = {
            "reconnu_comme": details.get(e.fichier, code),
            "lignes": len(e),
            "colonnes_reconnues": {c: e.nom_colonne(c) for c in sorted(e.index)},
            "colonnes_manquantes": e.manquantes(*attendues.get(code, [])),
        }
    for nom in inconnus:
        fichiers[nom] = {"reconnu_comme": details.get(nom, "non reconnu")}
    indispensables = indispensables or ["internal_all", "redirection_3xx_inlinks", "client_error_4xx_inlinks",
                      "server_error_5xx_inlinks", "redirect_chains", "insecure_content", "images_missing_alt_inlinks"]
    return {"dossier": dossier_exports, "fichiers": fichiers,
            "indispensables_absents": [c for c in indispensables if c not in exports]}


def charger(dossier_exports, details=None):
    trouves, inconnus = identifier(dossier_exports, details)
    return {code: Export(code, p) for code, p in trouves.items()}, inconnus
