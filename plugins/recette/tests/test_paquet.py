"""Paquet de retour pour l'application Audit : jamais l'accès à la préprod ni les exports.

    python -m unittest discover -s plugins/recette/tests
"""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import paquet  # noqa: E402


def ecrire(base, rel, contenu="x"):
    p = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(contenu)


class TestPaquet(unittest.TestCase):
    def test_contenu(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "Recette-SEO-Essai")
            for rel in ("audit-preparation.json", "profil.json", "controle-qualite.md", "acces-preprod.local.json",
                        "donnees/resultats.json", "donnees/tickets.json", "donnees/.verrou",
                        "donnees/resultats-agents/recette-live.json", "captures/MOB-02-accueil-360.png",
                        "captures/serveur/01-accueil-360.png", "exports/preprod/internal_all.csv",
                        "crawl-mcp/x.csv", ".audit/scripts.ok"):
                ecrire(d, rel)
            r = paquet.paquet(d)
            self.assertTrue(r["paquet"].endswith("Recette-SEO-Essai-retour.zip"))
            noms = set(zipfile.ZipFile(r["paquet"]).namelist())
            self.assertIn("donnees/tickets.json", noms)
            self.assertIn("donnees/resultats-agents/recette-live.json", noms)
            self.assertIn("captures/MOB-02-accueil-360.png", noms)
            self.assertIn("audit-preparation.json", noms)
            for interdit in ("acces-preprod.local.json", "exports/preprod/internal_all.csv", "crawl-mcp/x.csv",
                             "captures/serveur/01-accueil-360.png", "donnees/.verrou", ".audit/scripts.ok"):
                self.assertNotIn(interdit, noms)

    def test_refuse_hors_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                paquet.paquet(tmp)


if __name__ == "__main__":
    unittest.main()
