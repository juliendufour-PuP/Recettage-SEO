"""Jeu d'essai de la fin de recette : résultats des agents, contrôle qualité,
classeurs .xlsx, et assemblage des exports du MCP Screaming Frog.

Repart de la fausse préprod de test_recette.py.
"""
import csv
import json
import os
import sys
import unittest
import zipfile
from xml.dom import minidom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_recette  # noqa: E402
from test_recette import recette  # noqa: E402


class TestLivraison(unittest.TestCase):
    LANGUE = "en"

    @classmethod
    def setUpClass(cls):
        test_recette.TestRecette.setUpClass.__func__(cls)
        with open(os.path.join(cls.dossier, "profil.json"), encoding="utf-8") as f:
            cls.base = json.load(f)["preprod"]

    @classmethod
    def tearDownClass(cls):
        test_recette.TestRecette.tearDownClass.__func__(cls)

    def ecrire(self, nom, data):
        p = os.path.join(self.dossier, "donnees", nom)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def resultats(self):
        with open(os.path.join(self.dossier, "donnees", "resultats.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_1_agents_puis_livrables(self):
        d = self.dossier
        res = self.resultats()
        ref = recette.verifier.Resultats(d).ref
        vides = [i for i in ref if i not in res and i != "MOB-01"]
        deja_ok = next(i for i, r in res.items() if r["statut"] == "OK")
        self.ecrire("resultats-agents/recette-live.json", {"agent": "recette-live", "resultats": [
            {"id": "MOB-01", "statut": "KO", "type_preuve": "Constat observé", "preuve": "captures/MOB-01.png",
             "details": "Menu mobile sans lien Services.",
             "lignes_annexe": [{"URL": self.base + "/services/", "Constat": "lien absent"},
                               {"URL": self.base + "/blog/", "Constat": "lien absent"}]},
            {"id": deja_ok, "statut": "KO", "type_preuve": "Constat observé", "preuve": "x"},
            {"id": "ARI-01", "statut": "KO", "type_preuve": "Constat observé", "preuve": "x", "n_urls": 4},
        ] + [{"id": i, "statut": "Non testable", "type_preuve": "Constat observé", "details": "Accès manquant pour le test."}
             for i in vides if i != "ARI-01"] + [
            {"id": "ARI-01", "statut": "Non testable", "type_preuve": "Constat observé", "details": "Pas de fil d'Ariane."}]})
        sortie = recette.commande("poser", d)
        refus = " ".join(sortie["poser"]["refuses"])
        self.assertIn(deja_ok, refus)            # un résultat de script n'est pas écrasé
        self.assertIn("n_urls", refus)           # l'agent ne compte pas
        self.assertEqual(sortie["verifier"]["erreurs"], [], sortie["verifier"])
        res = self.resultats()
        self.assertEqual(res["MOB-01"]["n_urls"], 2)
        self.assertEqual(res[deja_ok]["statut"], "OK")
        self.assertTrue(all(i in res for i in ref), "contrôles encore vides")

        # Sans tickets.json : livraison refusée
        r = recette.commande("livrables", d)
        self.assertIsNone(r["livrables"])
        self.assertTrue(any("tickets.json" in e for e in r["erreurs"]))

        ko = [i for i, x in res.items() if x["statut"] == "KO" and x["type_preuve"] != "Hypothèse"]
        tickets = [{"controles": [i], "titre": f"Corriger {i}",
                    "description": f"{res[i].get('n_urls') or 'Des'} URLs concernées.",
                    "resolution": "Corriger le gabarit.", "resultat_attendu": "Plus aucune URL dans l'annexe.",
                    "urls_exemple": []} for i in ko]
        tickets[0]["description"] += " Environ 37 pages."  # chiffre inventé
        self.ecrire("tickets.json", {"tickets": tickets, "sans_ticket": []})
        self.ecrire("hypotheses.json", [{"sujet": "Maillage", "raisonnement": "r", "pour_confirmer": "p",
                                         "priorite_proposee": 2}])
        self.ecrire("cdc.json", [{"exigence": "Une page par service", "source": "CdC §2", "statut": "Conforme",
                                  "preuve": "arborescence", "controles": []}])
        r = recette.commande("controler", d)
        self.assertTrue(any("37" in e for e in r["erreurs"]), r["erreurs"])

        tickets[0]["description"] = tickets[0]["description"].replace(" Environ 37 pages.", "")
        self.ecrire("tickets.json", {"tickets": tickets, "sans_ticket": []})
        r = recette.commande("livrables", d)
        self.assertEqual(r["erreurs"], [])
        self.assertIn("MOB-01", r["priorites_relevees"])  # page stratégique /services/
        for p in r["livrables"].values():
            self.assertTrue(os.path.exists(p))
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.endswith(".xml") or n.endswith(".rels"):
                        minidom.parseString(z.read(n))  # XML bien formé
                classeur = z.read("xl/workbook.xml").decode()
        with zipfile.ZipFile(r["livrables"]["travail"]) as z:
            wb = z.read("xl/workbook.xml").decode()
            for o in ("Synthèse", "Recette", "Tickets", "Hypothèses", "Cahier des charges", "Après mise en ligne"):
                self.assertIn(f'name="{o}"', wb)
            chaines = z.read("xl/sharedStrings.xml").decode()
            self.assertIn("T-001", chaines)
            self.assertIn("À valider", chaines)
            self.assertIn("COUNTIF", z.read("xl/worksheets/sheet1.xml").decode())
        self.assertIn("Sommaire", classeur)

    def test_3_contre_verification_et_retour(self):
        d = self.dossier
        r = recette.commande("contre-verifier", d)
        self.assertGreater(r["verifies"], 0, r)
        self.assertEqual(r["ecarts"], [], r)
        travail = os.path.join(d, "livrables")
        classeur = next(f for f in os.listdir(travail) if "Annexe" not in f)
        os.makedirs(os.path.join(d, "retour-tm"), exist_ok=True)
        cible = os.path.join(d, "retour-tm", "valide.xlsx")
        try:  # resauvegarde par un tableur : chaînes partagées, comme Excel ou Google Sheets
            import openpyxl
            wb = openpyxl.load_workbook(os.path.join(travail, classeur))
            ws = wb["Tickets"]
            ws["L2"] = "Rejeté"
            ws.append(["", "", 2, "Ticket ajouté par le TM", "Oublié par la recette"])
            wb.save(cible)
            attendu_rejetes, attendu_ajoutes = 1, 1
        except ImportError:
            import shutil
            shutil.copy(os.path.join(travail, classeur), cible)
            attendu_rejetes, attendu_ajoutes = 0, 0
        r = recette.commande("retour", d)
        self.assertNotIn("erreur", r, r)
        b = recette.commande("bilan", d)["mesures"]["retour_tm"]
        self.assertEqual(b["rejetes"], attendu_rejetes)
        self.assertEqual(b["ajoutes_par_tm"], attendu_ajoutes)

    def test_2_mcp(self):
        d = self.dossier
        src = os.path.join(d, "crawl-mcp", "preprod")
        os.makedirs(src, exist_ok=True)
        with open(os.path.join(src, "page_titles.partie-1.ndjson"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"Address": "https://x/a", "Title 1": "A", "Title 1 Length": 1}) + "\n")
        with open(os.path.join(src, "page_titles.partie-2.ndjson"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"Address": "https://x/b", "Title 1": "B"}) + "\n")
            f.write("pas du json\n")
        with open(os.path.join(src, "sitemaps.csv"), "w", encoding="utf-8") as f:
            f.write("Address,Status Code\nhttps://x/a,200\n")
        manuel = test_recette.EXPORTS["en"]["fichiers"][0]
        with open(os.path.join(src, os.path.splitext(manuel)[0] + ".csv"), "w", encoding="utf-8") as f:
            f.write("Address\nhttps://x/a\n")
        r = recette.commande("mcp", d)["preprod"]
        self.assertEqual(r["assembles"]["page_titles.csv"]["lignes"], 2)
        self.assertEqual(r["assembles"]["page_titles.csv"]["lignes_illisibles"], 1)
        self.assertIn("sitemaps_all.csv", r["assembles"])
        self.assertTrue(any("main" in x for x in r["refuses"]), r)  # l'export manuel est gardé
        with open(os.path.join(d, "exports", "preprod", "page_titles.csv"), encoding="utf-8-sig") as f:
            lignes = list(csv.reader(f))
        self.assertEqual(lignes[0], ["Address", "Title 1", "Title 1 Length"])
        self.assertEqual(lignes[2], ["https://x/b", "B", ""])


    def test_4_export_vide_et_plan_absent(self):
        d = self.dossier
        # Un export 5xx sans aucune ligne : zéro anomalie, pas « export absent »
        with open(os.path.join(d, "exports", "preprod", "server_error_(5xx)_inlinks.csv"), "w", encoding="utf-8") as f:
            f.write("Type,Source,Destination,Anchor,Status Code\n")
        recette.commande("sf", d)
        r = self.resultats()["COD-03"]
        self.assertEqual((r["statut"], r["n_urls"]), ("OK", 0), r)
        # Plan de redirections annoncé dans le profil mais absent : les contrôles tournent quand même
        p = os.path.join(d, "profil.json")
        with open(p, encoding="utf-8") as f:
            profil = json.load(f)
        profil["plan_redirections"] = "plan-absent.csv"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(profil, f)
        recette.commande("redirections", d)
        r = self.resultats()["RED-03"]
        self.assertIn("plan-absent.csv", r["details"])
        self.assertIn("absent du dossier", r["details"])


if __name__ == "__main__":
    unittest.main()
