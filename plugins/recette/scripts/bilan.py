"""Bilan chiffré d'une recette et journal local, pour l'agent recette-amelioration.

Aucune valeur n'est estimée : une mesure absente vaut None.
"""
import csv
import json
import os
import re
import statistics
from collections import Counter
from datetime import datetime

from commun import STATUTS, Resultats, charger_profil, chemin, maintenant



def dossier_local():
    base = os.environ.get("RECETTAGE_SEO_HOME") or os.path.join(os.path.expanduser("~"), ".claude", "recettage-seo")
    os.makedirs(base, exist_ok=True)
    return base


def version_plugin():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude-plugin", "plugin.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, ValueError):
        return None


def _date(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _metriques(dossier):
    p = chemin(dossier, "donnees", "metriques.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    etapes = []
    for e in data.get("etapes", []):
        d, fi = _date(e.get("debut")), _date(e.get("fin"))
        etapes.append({
            "etape": e.get("etape"), "agent": e.get("agent"),
            "duree_s": round((fi - d).total_seconds()) if d and fi else None,
            "tokens": e.get("tokens"), "appels_outils": e.get("appels_outils"),
        })

    def somme(cle):
        vals = [e[cle] for e in etapes]
        return sum(vals) if vals and all(v is not None for v in vals) else None

    return {"etapes": etapes, "duree_totale_s": somme("duree_s"), "tokens_total": somme("tokens"),
            "appels_outils_total": somme("appels_outils")}


def _cause(details):
    """Regroupe les raisons de « Non testable » : le nom de fichier ou de colonne garde la cause lisible."""
    d = re.sub(r"\d+", "N", details or "")
    return d[:140]


def _retour_tm(dossier):
    p = chemin(dossier, "retour-tm", "tickets.csv")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        echantillon = f.read(5000)
        f.seek(0)
        sep = ";" if echantillon.count(";") > echantillon.count(",") else ","
        lignes = list(csv.DictReader(f, delimiter=sep))
    norm = lambda s: (s or "").strip().lower()
    valides = [l for l in lignes if norm(l.get("Validation TM")) == "validé"]
    rejetes = [l for l in lignes if norm(l.get("Validation TM")) == "rejeté"]
    ajoutes = [l for l in lignes if not (l.get("Contrôles") or "").strip()]
    rejets_par_controle = Counter(c for l in rejetes for c in re.split(r"[\s,;]+", l.get("Contrôles") or "") if c)
    return {
        "tickets": len(lignes), "valides": len(valides), "rejetes": len(rejetes),
        "ajoutes_par_tm": len(ajoutes), "a_valider": len(lignes) - len(valides) - len(rejetes),
        "rejets_par_controle": dict(rejets_par_controle),
        "tickets_ajoutes": [{"titre": l.get("Titre", ""), "description": (l.get("Description du problème") or "")[:300]}
                            for l in ajoutes],
    }


def bilan(dossier):
    profil = charger_profil(dossier)
    res = Resultats(dossier)
    statuts = Counter(r["statut"] for r in res.data.values())
    applicables = len(res.ref) - statuts.get("Non applicable", 0)
    traites = sum(statuts.get(s, 0) for s in ("OK", "KO", "Partiel", "Après mise en ligne"))
    non_testables = [r for r in res.data.values() if r["statut"] == "Non testable"]
    verif_p = chemin(dossier, "donnees", "verification.json")
    verif = json.load(open(verif_p, encoding="utf-8")) if os.path.exists(verif_p) else None
    met = _metriques(dossier)
    retour = _retour_tm(dossier)
    mesures = {
        "controles_referentiel": len(res.ref),
        "par_statut": {s: statuts.get(s, 0) for s in STATUTS},
        "couverture_pct": round(100 * traites / applicables, 1) if applicables else None,
        "sans_resultat": len(res.ref) - len(res.data),
        "non_testable_causes": Counter(_cause(r["details"]) for r in non_testables).most_common(),
        "erreurs_verification": len(verif["erreurs"]) if verif else None,
        "duree_totale_s": met["duree_totale_s"] if met else None,
        "tokens_total": met["tokens_total"] if met else None,
        "tokens_par_controle_traite": round(met["tokens_total"] / traites) if met and met["tokens_total"] and traites else None,
        "etapes": met["etapes"] if met else None,
        "retour_tm": retour,
    }
    # Comparaison avec l'historique du journal
    journal_p = os.path.join(dossier_local(), "journal.jsonl")
    historique = []
    if os.path.exists(journal_p):
        with open(journal_p, encoding="utf-8") as f:
            for ligne in f:
                try:
                    e = json.loads(ligne)
                except ValueError:
                    continue
                if e.get("dossier") != os.path.abspath(dossier):  # une recette relancée ne se compare pas à elle-même
                    historique.append(e)

    def mediane(cle):
        vals = [e["mesures"].get(cle) for e in historique if e["mesures"].get(cle) is not None]
        return statistics.median(vals) if vals else None

    comparaison = {}
    for cle in ("duree_totale_s", "tokens_total", "tokens_par_controle_traite", "couverture_pct"):
        m, v = mediane(cle), mesures.get(cle)
        comparaison[cle] = {"cette_recette": v, "mediane_historique": m,
                            "ecart_pct": round(100 * (v - m) / m, 1) if m not in (None, 0) and v is not None else None}
    rejets_cumules = Counter()
    for e in historique + [{"mesures": mesures}]:
        r = e["mesures"].get("retour_tm") or {}
        rejets_cumules.update(r.get("rejets_par_controle") or {})
    sortie = {
        "client": profil.get("client"), "date": maintenant(), "version_plugin": version_plugin(),
        "recettes_dans_historique": len(historique), "mesures": mesures, "comparaison": comparaison,
        "rejets_cumules_par_controle": dict(rejets_cumules.most_common()),
    }
    with open(chemin(dossier, "donnees", "bilan.json"), "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    # Journal : une ligne par recette, remplacée si la même recette est relancée
    entree = {"date": sortie["date"], "client": sortie["client"], "dossier": os.path.abspath(dossier),
              "version_plugin": sortie["version_plugin"],
              "mesures": {k: v for k, v in mesures.items() if k not in ("etapes", "non_testable_causes")}}
    lignes = []
    if os.path.exists(journal_p):
        with open(journal_p, encoding="utf-8") as f:
            lignes = [l for l in f if l.strip() and json.loads(l).get("dossier") != entree["dossier"]]
    lignes.append(json.dumps(entree, ensure_ascii=False) + "\n")
    with open(journal_p, "w", encoding="utf-8") as f:
        f.writelines(lignes)
    return sortie
