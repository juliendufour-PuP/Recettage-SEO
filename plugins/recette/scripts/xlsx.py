"""Écriture d'un classeur .xlsx avec la bibliothèque standard (zipfile + XML).

Pensé d'abord pour Google Sheets (import du .xlsx, converti en feuille Google).

Juste ce qu'il faut pour les livrables : plusieurs onglets, texte, nombres,
formules, en-tête mis en forme et figé, largeurs de colonnes, listes déroulantes
et filtre automatique. Les formules sont recalculées à l'ouverture (Excel,
Google Sheets, LibreOffice).
"""
import re
import zipfile
from xml.sax.saxutils import escape

_INTERDITS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
NOM_ONGLET_INTERDIT = re.compile(r"[\[\]:*?/\\]")

# Styles : 0 normal, 1 en-tête (vert profond, texte blanc, gras), 2 titre, 3 retour à la ligne
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="3"><font><sz val="10"/><name val="Arial"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
<font><b/><sz val="13"/><color rgb="FF203B32"/><name val="Arial"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF203B32"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def col(n):
    """0 -> A, 25 -> Z, 26 -> AA."""
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def nom_onglet(nom, deja):
    n = NOM_ONGLET_INTERDIT.sub("-", str(nom)).strip("'")[:31] or "Onglet"
    base, i = n, 2
    while n.lower() in {d.lower() for d in deja}:
        suffixe = f" ({i})"
        n = base[:31 - len(suffixe)] + suffixe
        i += 1
    return n


class Formule(str):
    """Valeur écrite comme formule (sans le signe =)."""


class Onglet:
    def __init__(self, nom):
        self.nom = nom
        self.lignes = []        # liste de (valeurs, style)
        self.largeurs = {}
        self.ligne_entete = None
        self.listes = []        # (colonne, première ligne, dernière ligne, valeurs)
        self.retour_ligne = set()

    def ajouter(self, valeurs, style=0):
        self.lignes.append((list(valeurs), style))
        return len(self.lignes)  # numéro de ligne Excel

    def entete(self, valeurs):
        self.ligne_entete = self.ajouter(valeurs, style=1)
        return self.ligne_entete

    def liste(self, colonne, debut, fin, valeurs):
        if fin >= debut:
            self.listes.append((colonne, debut, fin, valeurs))

    def _cellule(self, ref, v, style):
        s = f' s="{style}"' if style else ""
        if v is None or v == "":
            return f'<c r="{ref}"{s}/>' if style else ""
        if isinstance(v, Formule):
            return f'<c r="{ref}"{s}><f>{escape(_INTERDITS.sub("", v))}</f></c>'
        if isinstance(v, bool):
            v = "oui" if v else "non"
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"{s}><v>{v}</v></c>'
        texte = _INTERDITS.sub("", str(v))[:32000]
        return f'<c r="{ref}"{s} t="s"><v>{self.chaines(texte)}</v></c>'

    def xml(self, chaines):
        self.chaines = chaines
        parties = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">']
        if self.ligne_entete:
            parties.append(f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="{self.ligne_entete}" '
                           f'topLeftCell="A{self.ligne_entete + 1}" activePane="bottomLeft" state="frozen"/>'
                           '</sheetView></sheetViews>')
        if self.largeurs:
            parties.append("<cols>" + "".join(
                f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                for i, w in sorted(self.largeurs.items())) + "</cols>")
        parties.append("<sheetData>")
        for n, (valeurs, style) in enumerate(self.lignes, start=1):
            cellules = []
            for i, v in enumerate(valeurs):
                st = style or (3 if i in self.retour_ligne else 0)
                cellules.append(self._cellule(f"{col(i)}{n}", v, st))
            parties.append(f'<row r="{n}">{"".join(cellules)}</row>')
        parties.append("</sheetData>")
        if self.ligne_entete and len(self.lignes) > self.ligne_entete:
            nb = len(self.lignes[self.ligne_entete - 1][0])
            parties.append(f'<autoFilter ref="A{self.ligne_entete}:{col(max(nb, 1) - 1)}{len(self.lignes)}"/>')
        if self.listes:
            parties.append(f'<dataValidations count="{len(self.listes)}">')
            for c, d, f, valeurs in self.listes:
                liste = escape('"' + ",".join(valeurs) + '"')
                parties.append(f'<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
                               f'sqref="{col(c)}{d}:{col(c)}{f}"><formula1>{liste}</formula1></dataValidation>')
            parties.append("</dataValidations>")
        parties.append("</worksheet>")
        return "".join(parties)


class Classeur:
    def __init__(self):
        self.onglets = []

    def onglet(self, nom):
        o = Onglet(nom_onglet(nom, [x.nom for x in self.onglets]))
        self.onglets.append(o)
        return o

    def enregistrer(self, chemin):
        # Chaînes partagées (sharedStrings) : le format qu'écrivent Excel et Google Sheets.
        index, liste = {}, []

        def chaine(texte):
            if texte not in index:
                index[texte] = len(liste)
                liste.append(texte)
            return index[texte]

        feuilles = [o.xml(chaine) for o in self.onglets]
        partages = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(liste)}" '
                    f'uniqueCount="{len(liste)}">'
                    + "".join(f'<si><t xml:space="preserve">{escape(t)}</t></si>' for t in liste) + "</sst>")
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                       '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                       '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                       + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                                 for i in range(1, len(self.onglets) + 1))
                       + "</Types>")
            z.writestr("_rels/.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                       '</Relationships>')
            z.writestr("xl/workbook.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                       + "".join(f'<sheet name="{escape(o.nom, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                                 for i, o in enumerate(self.onglets, start=1))
                       + '</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                                 for i in range(1, len(self.onglets) + 1))
                       + f'<Relationship Id="rId{len(self.onglets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                       + f'<Relationship Id="rId{len(self.onglets) + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
                       '</Relationships>')
            z.writestr("xl/styles.xml", _STYLES)
            z.writestr("xl/sharedStrings.xml", partages)
            for i, x in enumerate(feuilles, start=1):
                z.writestr(f"xl/worksheets/sheet{i}.xml", x)
