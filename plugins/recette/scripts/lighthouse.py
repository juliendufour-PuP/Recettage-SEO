"""CWV-01 : mesures de laboratoire Lighthouse (mobile) sur l'accueil et chaque gabarit.

Lance `npx lighthouse` (version fixée) avec le Chrome du poste, ou le Chromium
installé par Playwright. Les rapports complets sont gardés dans
donnees/lighthouse/ : ce sont eux la preuve. Seuils Google : LCP 2,5 s,
CLS 0,1, TBT 200 ms (TBT remplace l'INP en laboratoire).

Si la préprod est protégée, l'en-tête d'authentification est passé à
Lighthouse par un fichier temporaire, supprimé à la fin, jamais copié dans
le dossier de recette.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile

from commun import Annexe, Resultats, charger_acces, charger_profil, chemin, nettoyer_url, normaliser
from web import Client

VERSION = "13.6.0"
SEUILS = {"lcp_ms": 2500, "cls": 0.1, "tbt_ms": 200}


def trouver_chrome():
    if os.environ.get("CHROME_PATH") and os.path.exists(os.environ["CHROME_PATH"]):
        return os.environ["CHROME_PATH"]
    candidats = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    caches = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
              os.path.expanduser("~/Library/Caches/ms-playwright"), os.path.expanduser("~/.cache/ms-playwright")]
    for c in caches:
        candidats += sorted(glob.glob(os.path.join(c, "chromium-*", "chrome-win*", "chrome.exe")), reverse=True)
        candidats += sorted(glob.glob(os.path.join(c, "chromium-*", "chrome-mac*", "*.app", "Contents", "MacOS", "*")),
                            reverse=True)
        candidats += sorted(glob.glob(os.path.join(c, "chromium-*", "chrome-linux*", "chrome")), reverse=True)
    candidats += [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    return next((c for c in candidats if c and os.path.isfile(c)), None)


def _mesure(rapport):
    a = rapport.get("audits", {})
    val = lambda k: (a.get(k) or {}).get("numericValue")
    perf = ((rapport.get("categories") or {}).get("performance") or {}).get("score")
    return {"score_performance": round(perf * 100) if perf is not None else None,
            "lcp_ms": round(val("largest-contentful-paint")) if val("largest-contentful-paint") is not None else None,
            "cls": round(val("cumulative-layout-shift"), 3) if val("cumulative-layout-shift") is not None else None,
            "tbt_ms": round(val("total-blocking-time")) if val("total-blocking-time") is not None else None}


def lighthouse(dossier, timeout=240):
    profil = charger_profil(dossier)
    res = Resultats(dossier)
    annexe = Annexe(dossier)
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    chrome = trouver_chrome()
    if not npx or not chrome:
        manque = "Node.js (npx)" if not npx else "Chrome ou Chromium (installer Chrome, ou lancer une fois Playwright)"
        res.non_testable("CWV-01", f"Lighthouse non lancé : {manque} introuvable sur le poste.", "Constat observé")
        res.enregistrer()
        return {"erreur": manque}
    pages = [{"type": g.get("type", ""), "url": g["url"]} for g in profil.get("gabarits", []) if g.get("url")]
    accueil = nettoyer_url(profil.get("preprod", "") + "/")
    if accueil and all(nettoyer_url(p["url"]) != accueil for p in pages):
        pages.insert(0, {"type": "accueil", "url": accueil})
    acces = charger_acces(dossier) or {}
    acces.setdefault("preprod", profil.get("preprod", ""))
    entete = Client(acces).entete_auth
    sortie = chemin(dossier, "donnees", "lighthouse")
    os.makedirs(sortie, exist_ok=True)
    fichier_entetes = None
    mesures, echecs = [], []
    try:
        if entete:
            fd, fichier_entetes = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump({"Authorization": entete}, f)
        for i, p in enumerate(pages, start=1):
            nom = f"{i:02d}-{normaliser(p['type'])[:30] or 'page'}.json"
            cible = os.path.join(sortie, nom)
            cmd = [npx, "-y", f"lighthouse@{VERSION}", p["url"], "--output=json", f"--output-path={cible}",
                   "--only-categories=performance", "--form-factor=mobile", "--quiet",
                   "--chrome-flags=--headless=new --no-sandbox"]
            if fichier_entetes:
                cmd.append(f"--extra-headers={fichier_entetes}")
            env = dict(os.environ, CHROME_PATH=chrome)
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
            except subprocess.TimeoutExpired:
                echecs.append({"url": p["url"], "erreur": f"délai de {timeout} s dépassé"})
                continue
            if r.returncode != 0 or not os.path.exists(cible):
                echecs.append({"url": p["url"], "erreur": (r.stderr or r.stdout or "").strip()[-300:]})
                continue
            with open(cible, encoding="utf-8") as f:
                rapport = json.load(f)
            erreur_lh = (rapport.get("runtimeError") or {}).get("message")
            m = _mesure(rapport)
            if erreur_lh or m["lcp_ms"] is None:
                echecs.append({"url": p["url"], "erreur": erreur_lh or "mesures absentes du rapport"})
                continue
            m.update({"url": p["url"], "gabarit": p["type"], "rapport": f"donnees/lighthouse/{nom}"})
            m["depassements"] = [k for k, s in SEUILS.items() if m[k] is not None and m[k] > s]
            mesures.append(m)
    finally:
        if fichier_entetes and os.path.exists(fichier_entetes):
            os.remove(fichier_entetes)
    with open(os.path.join(sortie, "synthese.json"), "w", encoding="utf-8") as f:
        json.dump({"version_lighthouse": VERSION, "chrome": chrome, "seuils": SEUILS, "mesures": mesures,
                   "echecs": echecs}, f, ensure_ascii=False, indent=2)
    noms = {"lcp_ms": "LCP", "cls": "CLS", "tbt_ms": "TBT"}
    for m in mesures:
        if m["depassements"]:
            annexe.ajouter("Lighthouse", "CWV-01", {
                "URL": m["url"], "Gabarit": m["gabarit"], "Score performance": m["score_performance"],
                "LCP (ms)": m["lcp_ms"], "CLS": m["cls"], "TBT (ms)": m["tbt_ms"],
                "Au-delà du seuil": ", ".join(noms[k] for k in m["depassements"]), "Rapport": m["rapport"]},
                "lighthouse " + VERSION)
    n_ko = annexe.compter("Lighthouse", "CWV-01")
    ancien = chemin(dossier, "annexe", "Lighthouse.csv")
    if not n_ko and os.path.exists(ancien):
        os.remove(ancien)
    preuve = "donnees/lighthouse/synthese.json (rapports Lighthouse mobile, mesure de laboratoire)"
    note = (f" Échec de mesure sur {len(echecs)} page(s) : voir synthese.json." if echecs else "")
    if not mesures:
        res.non_testable("CWV-01", "Aucune mesure Lighthouse réussie." + note, "Constat observé")
    elif n_ko:
        res.poser("CWV-01", "KO", "Constat observé", preuve,
                  f"{n_ko} page(s) sur {len(mesures)} mesurées au-delà d'un seuil Google (LCP 2500 ms, CLS 0.1, "
                  f"TBT 200 ms), en laboratoire.{note} Les données réelles se contrôlent après la mise en ligne.",
                  n_urls=n_ko, onglet="Lighthouse", script="lighthouse")
    else:
        res.poser("CWV-01", "Partiel", "Constat observé", preuve,
                  f"{len(mesures)} page(s) mesurées sous les seuils Google, en laboratoire.{note} "
                  "Les données réelles se contrôlent après la mise en ligne.", script="lighthouse")
    annexe.enregistrer()
    res.enregistrer()
    return {"mesurees": len(mesures), "au_dela_seuil": n_ko, "echecs": echecs}
