"""Socle commun des scripts de recette : référentiel, profil client, résultats, annexe.

Bibliothèque standard Python uniquement, pour une installation sans dépendance.
"""
import csv
import json
import os
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

DOSSIER_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.normpath(os.path.join(DOSSIER_SCRIPTS, "..", "references"))

STATUTS = ("OK", "KO", "Partiel", "Non testable", "Non applicable", "Après mise en ligne")
TYPES_PREUVE = ("Constat export", "Constat observé", "Hypothèse")

SEUILS_DEFAUT = {
    "url_max": 115,          # caractères (seuil Screaming Frog)
    "mots_min": 200,         # mots (seuil Screaming Frog « low content »)
    "image_ko_max": 100,     # Ko (seuil Screaming Frog)
    "title_px_min": 200,
    "title_px_max": 561,
    "title_car_min": 30,
    "title_car_max": 60,
    "desc_px_min": 400,
    "desc_px_max": 985,
    "desc_car_min": 70,
    "desc_car_max": 155,
    "profondeur_max": 3,
}


def normaliser(texte):
    """« Code de statut » -> « code_de_statut » ; « rel="next" 1 » -> « rel_next_1 »."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "_", t.lower())
    return t.strip("_")


def maintenant():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --- Référentiel -----------------------------------------------------------

def charger_referentiel():
    with open(os.path.join(REFS, "referentiel-controles.csv"), encoding="utf-8-sig", newline="") as f:
        return {ligne["id"]: ligne for ligne in csv.DictReader(f, delimiter=";")}


# --- Profil client ----------------------------------------------------------

def chemin(dossier, *parties):
    return os.path.join(dossier, *parties)


def charger_profil(dossier):
    p = chemin(dossier, "profil.json")
    if not os.path.exists(p):
        raise SystemExit(f"profil.json introuvable dans {dossier} (modèle : templates/profil.example.json)")
    with open(p, encoding="utf-8-sig") as f:
        profil = json.load(f)
    seuils = dict(SEUILS_DEFAUT)
    seuils.update({k: v for k, v in (profil.get("seuils") or {}).items() if v not in (None, "")})
    profil["seuils"] = seuils
    profil.setdefault("applicabilite", {})
    profil.setdefault("pages_strategiques", [])
    profil.setdefault("gabarits", [])
    return profil


def charger_acces(dossier):
    """Accès préprod : lu dans acces-preprod.local.json, jamais recopié ailleurs."""
    p = chemin(dossier, "acces-preprod.local.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


# --- URLs --------------------------------------------------------------------

def nettoyer_url(url):
    """Hôte en minuscules, sans fragment. Le chemin garde sa casse (contrôle URL-03)."""
    if not url:
        return ""
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def cle_url(url):
    """Clé de comparaison indépendante du domaine : chemin + paramètres."""
    p = urlsplit((url or "").strip())
    return (p.path or "/") + ("?" + p.query if p.query else "")


def origine(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


# --- Résultats ---------------------------------------------------------------

class Resultats:
    """donnees/resultats.json : un résultat par contrôle du référentiel."""

    def __init__(self, dossier):
        self.dossier = dossier
        self.ref = charger_referentiel()
        self.chemin = chemin(dossier, "donnees", "resultats.json")
        os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
        if os.path.exists(self.chemin):
            with open(self.chemin, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def poser(self, id_controle, statut, type_preuve, preuve, details="", n_urls=None,
              onglet=None, script=None):
        if id_controle not in self.ref:
            raise ValueError(f"Contrôle inconnu du référentiel : {id_controle}")
        if statut not in STATUTS:
            raise ValueError(f"Statut invalide pour {id_controle} : {statut}")
        if type_preuve not in TYPES_PREUVE:
            raise ValueError(f"Type de preuve invalide pour {id_controle} : {type_preuve}")
        if onglet is None and n_urls:
            onglet = self.ref[id_controle].get("onglet_annexe") or None
        self.data[id_controle] = {
            "id": id_controle,
            "statut": statut,
            "type_preuve": type_preuve,
            "preuve": preuve,
            "details": details,
            "n_urls": n_urls,
            "onglet_annexe": onglet,
            "source": script or "script",
            "date": maintenant(),
        }

    def non_testable(self, id_controle, raison, type_preuve="Constat export"):
        self.poser(id_controle, "Non testable", type_preuve, preuve="", details=raison)

    def enregistrer(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(self.data.items())), f, ensure_ascii=False, indent=2)


# --- Annexe ------------------------------------------------------------------

class Annexe:
    """annexe/<Onglet>.csv : listes d'URLs écrites telles quelles par les scripts.

    Chaque ligne porte la colonne « Contrôle ». Un onglet est réécrit en entier
    à chaque lancement du script qui en est propriétaire.
    """

    def __init__(self, dossier):
        self.dossier = chemin(dossier, "annexe")
        os.makedirs(self.dossier, exist_ok=True)
        self.onglets = {}
        self.sources = {}

    def ajouter(self, onglet, id_controle, ligne, source):
        d = {"Contrôle": id_controle}
        d.update(ligne)
        self.onglets.setdefault(onglet, []).append(d)
        self.sources.setdefault(onglet, set()).add(source)

    def compter(self, onglet, id_controle):
        return sum(1 for l in self.onglets.get(onglet, []) if l["Contrôle"] == id_controle)

    def enregistrer(self):
        index_path = os.path.join(self.dossier, "_sources.json")
        index = {}
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
        for onglet, lignes in self.onglets.items():
            colonnes = []
            for l in lignes:
                for k in l:
                    if k not in colonnes:
                        colonnes.append(k)
            with open(os.path.join(self.dossier, onglet + ".csv"), "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
                w.writeheader()
                w.writerows(lignes)
            index[onglet] = {"sources": sorted(self.sources[onglet]), "lignes": len(lignes), "date": maintenant()}
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)


def lire_csv_simple(path):
    """Lit un CSV dont le séparateur est inconnu (virgule, point-virgule, tabulation)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        echantillon = f.read(20000)
        f.seek(0)
        try:
            dialecte = csv.Sniffer().sniff(echantillon, delimiters=",;\t")
        except csv.Error:
            dialecte = csv.excel
        return list(csv.reader(f, dialecte))
