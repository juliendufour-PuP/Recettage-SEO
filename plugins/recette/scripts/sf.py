"""Lecture des exports Screaming Frog (interface en anglais ou en français).

Identification des fichiers par leur nom, avec une correspondance manuelle
possible dans exports/<preprod|ancien-site>/correspondance.json :
    {"internal_all": "mon-export.csv"}

Les colonnes sont retrouvées par alias normalisés. Une colonne introuvable
n'est jamais devinée : le contrôle concerné passe en « Non testable ».
Les alias français sont à confirmer sur de vrais exports.
"""
import json
import os
import re

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
}


class Export:
    def __init__(self, code, path):
        self.code = code
        self.path = path
        self.fichier = os.path.basename(path)
        lignes = lire_csv_simple(path)
        # Certains exports ont une ligne de titre avant les en-têtes : on prend la
        # première ligne qui contient une colonne connue.
        debut = 0
        connus = {a for alias in ALIAS_COLONNES.values() for a in alias}
        for i, l in enumerate(lignes[:5]):
            if any(normaliser(c) in connus for c in l):
                debut = i
                break
        self.entetes = lignes[debut] if lignes else []
        self.lignes = [l for l in lignes[debut + 1:] if any(c.strip() for c in l)]
        norm = [normaliser(e) for e in self.entetes]
        self.index = {}
        for canon, alias in ALIAS_COLONNES.items():
            for a in alias:
                if a in norm:
                    self.index[canon] = norm.index(a)
                    break

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


def identifier(dossier_exports):
    """Retourne ({code: chemin}, [fichiers non reconnus])."""
    trouves, inconnus = {}, []
    if not os.path.isdir(dossier_exports):
        return trouves, inconnus
    manuel = {}
    p = os.path.join(dossier_exports, "correspondance.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            manuel = json.load(f)
    for code, fichier in manuel.items():
        trouves[code] = os.path.join(dossier_exports, fichier)
    for nom in sorted(os.listdir(dossier_exports)):
        if not nom.lower().endswith(".csv"):
            continue
        if nom in manuel.values():
            continue
        base = normaliser(os.path.splitext(nom)[0])
        code = next((c for c, motifs in MOTIFS_FICHIERS.items()
                     if any(re.search(m, base) for m in motifs)), None)
        if code and code not in trouves:
            trouves[code] = os.path.join(dossier_exports, nom)
        else:
            inconnus.append(nom)
    return trouves, inconnus


def charger(dossier_exports):
    trouves, inconnus = identifier(dossier_exports)
    return {code: Export(code, p) for code, p in trouves.items()}, inconnus
