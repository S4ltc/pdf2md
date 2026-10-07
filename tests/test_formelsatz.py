"""Formelsatz (formelsatz.py) an nachgebauten Zeichen: nur die Lage zaehlt, PDFium wird nicht gebraucht."""
import pytest

import formelsatz as fs
import pdf2md as p

G, K = 10.0, 7.0          # Schriftgroesse Text / Index


def teil(text, x, y, g=G, folge=0, leer=False, zeile=0, breite=None):
    """Ein Zeichen an Position x mit Grundlinie y (Rahmen grob wie bei echten Schriften)."""
    breite = breite or 0.55 * g
    return fs.Teil([folge], text, x, x + breite, y - 0.2 * g, y + 0.7 * g, y, g, folge=folge, leer_davor=leer,
                   zeile=zeile)


def zeile(*zeichen, y=100.0):
    """Zeichen nebeneinander; ("x", "hoch"/"tief") fuer Exponent/Index; " " fuer Leerzeichen."""
    teile, x, leer = [], 50.0, False
    for z in zeichen:
        if z == " ":
            x += 3.0
            leer = True
            continue
        text, art = (z, "") if isinstance(z, str) else z
        g = K if art else G
        dy = 0.4 * G if art == "hoch" else -0.25 * G if art == "tief" else 0.0
        teile.append(teil(text, x, y + dy, g, folge=len(teile), leer=leer))
        x += 0.55 * g
        leer = False
    return teile


class TestHochTief:
    def test_index_und_exponent(self):
        assert fs.setzen(zeile("p", ("1", "tief"), " ", "V", ("1", "tief")), True) == "p_{1} V_{1}"
        assert fs.setzen(zeile("1", "0", ("−", "hoch"), ("3", "hoch")), True) == "10^{−3}"
        assert fs.setzen(zeile("m", ("2", "hoch")), False) == "m$^{2}$"

    def test_index_und_exponent_am_selben_zeichen(self):
        teile = zeile("s")
        teile.append(teil("R", teile[0].r, 104.0, K, folge=1))           # oben
        teile.append(teil("i", teile[0].r, 97.5, K, folge=2, leer=True))  # unten, PDFium setzt ein Leerzeichen
        teile.append(teil("r", teile[2].r, 97.5, K, folge=3))
        teile.sort(key=lambda t: t.l)
        assert fs.setzen(teile, True) == "s_{ir}^{R}"

    def test_fussnotenzeichen_vor_dem_wort(self):
        assert fs.setzen(zeile(("1", "hoch"), "R", "o", "b"), False) == "$^{1}$Rob"

    def test_gleich_grosse_zeichen_bleiben(self):
        assert fs.setzen(zeile("a", " ", "b", "c"), False) == "a bc"

    def test_kleine_schrift_ohne_grossen_nachbarn_bleibt(self):
        """Eine ganze Fussnotenzeile in kleiner Schrift hat keine Hoch-/Tiefstellung."""
        teile = [teil(c, 50 + 4 * i, 100.0, K, folge=i) for i, c in enumerate("abc")]
        assert fs.setzen(teile, False) == "abc"

    def test_latex_sonderzeichen(self):
        assert fs.setzen(zeile("x", ("%", "tief")), True) == r"x_{\%}"


class TestBruch:
    def test_einfacher_bruch(self):
        zaehler = [teil("V", 100, 108.0, folge=0)]
        nenner = [teil("T", 98, 92.0, folge=1), teil("0", 104, 90.0, K, folge=2)]
        stueck = fs._bruch((104.0, 97.0, 106.0), zaehler + nenner)
        assert stueck is not None and stueck.text == r"\frac{V}{T_{0}}"

    def test_unterstrichener_text_ist_kein_bruch(self):
        """Der Text ueber der Linie geht links und rechts weiter: Unterstreichung, kein Bruch."""
        oben = [teil(c, 60 + 6 * i, 108.0, folge=i) for i, c in enumerate("das Wort hier")]
        unten = [teil(c, 60 + 6 * i, 92.0, folge=20 + i) for i, c in enumerate("naechste Zeile")]
        assert fs._bruch((104.0, 84.0, 108.0), oben + unten) is None

    def test_tabellenkopf_ueber_linie_ist_kein_bruch(self):
        kopf = [teil("A", 50, 108.0), teil("B", 90, 108.0), teil("C", 130, 108.0)]
        werte = [teil("1", 50, 92.0), teil("2", 90, 92.0), teil("3", 130, 92.0)]
        assert fs._bruch((104.0, 45.0, 140.0), kopf + werte) is None


class TestOperator:
    def test_summe_mit_grenzen(self):
        op = fs.Teil([0], "∑", 100, 110, 92, 112, 95, 14.0, folge=0)
        unten = [teil("i", 101, 86.0, K, folge=1), teil("=", 104, 86.0, K, folge=2), teil("1", 107, 86.0, K, folge=3)]
        oben = [teil("n", 103, 114.0, K, folge=4)]
        stueck = fs._operator(op, [op] + unten + oben)
        assert stueck.text == r"\sum_{i=1}^{n}"

    def test_integral_grenzen_rechts(self):
        op = fs.Teil([0], "∫", 100, 106, 85, 115, 88, 10.0, folge=0)    # abgesetztes Integral, 3 Schriftgroessen hoch
        oben = [teil("2", 106.5, 111.0, K, folge=1)]
        unten = [teil("1", 103.0, 86.0, K, folge=2)]
        stueck = fs._operator(op, [op] + oben + unten)
        assert stueck.text == r"\int_{1}^{2}"

    def test_lim(self):
        teile = zeile("l", "i", "m")
        teile += [teil("x", 51, 92.0, K, folge=3), teil("→", 55, 92.0, K, folge=4), teil("0", 59, 92.0, K, folge=5)]
        op = fs._wort_operatoren(teile)[0]
        assert fs._operator(op, teile).text == r"\lim_{x→0}"

    def test_lim_mitten_im_wort_nicht(self):
        assert fs._wort_operatoren(zeile("K", "l", "i", "m", "a")) == []


class TestPlatzhalter:
    def test_aufloesen_mit_reparatur(self):
        text = "a" + fs.platzhalter(7, 3) + "b"
        assert fs.aufloesen(text, lambda k, c: "∑" if k == 7 else None) == ("a∑b", 1)
        assert fs.aufloesen(text) == ("a\x03b", 0)

    def test_unsichere_formel_wird_markiert(self):
        text = p._seite_bereinigen("Es gilt $x_{\x05} = 1$ hier\nNormaler Text mit \x05 Zeichen")
        zeilen = text.split("\n")
        assert zeilen[0].startswith(fs.UNSICHER) and not zeilen[-1].startswith(fs.UNSICHER)


class TestAkzent:
    @pytest.mark.parametrize("text, erwartet", [("Q̇", r"\dot{Q}"), ("x̂", r"\hat{x}"), ("ä", "ä")])
    def test_latex_akzent(self, text, erwartet):
        assert fs._maskiert(fs.Teil([0], text, 0, 1, 0, 1, 0, G)) == erwartet


class TestKeineBasis:
    def test_strichcode_bekommt_keine_indizes(self):
        """Norm-Deckblatt: grosse Strichcode-Zeichen "!&|" ueber der kleinen Dokumentnummer sind keine Formel."""
        teile = zeile("!", "&", "|", ("3", "tief"), ("4", "tief"))
        assert fs.setzen(teile, False) == "!&|34"


class TestBalken:
    """Welche waagerechten Striche als Bruchstrich in Frage kommen."""

    class Obj:
        def __init__(self, l, b, r, t, typ=None):
            import pypdfium2.raw as raw
            self.type = typ or raw.FPDF_PAGEOBJ_PATH
            self.box = (l, b, r, t)

        def get_bounds(self):
            return self.box

    class Seite:
        def __init__(self, objekte):
            self.objekte = objekte

        def get_objects(self, filter=None, max_depth=3):
            return iter(self.objekte)

    def test_freier_strich(self):
        assert fs.balken(self.Seite([self.Obj(100, 200, 120, 200.5)])) == [(200.25, 100, 120)]

    def test_strich_an_senkrechter_linie_ist_tabellenlinie(self):
        objekte = [self.Obj(100, 200, 160, 200.5), self.Obj(99.5, 150, 100.5, 250)]
        assert fs.balken(self.Seite(objekte)) == []

    def test_gleich_lange_striche_uebereinander_sind_tabellenzeilen(self):
        objekte = [self.Obj(100, y, 160, y + 0.5) for y in (200, 214, 228)]
        assert fs.balken(self.Seite(objekte)) == []

    def test_tex_bruchstrich_als_bild(self):
        import pypdfium2.raw as raw
        assert len(fs.balken(self.Seite([self.Obj(144.8, 144.1, 171.0, 144.6, raw.FPDF_PAGEOBJ_IMAGE)]))) == 1


class TestIndexLage:
    def test_ziffern_unter_grossen_zeichen_sind_kein_index(self):
        """Norm-Deckblatt: Dokumentnummer "3428947" klein unter dem grossen Strichcode "R" (20 pt)."""
        basis = fs.Teil([0], "R", 100, 112, 96, 114, 100.0, 20.0, folge=0)
        ziffern = [fs.Teil([i + 1], c, 101 + 4 * i, 104 + 4 * i, 82, 88, 83.0, 7.0, folge=i + 1)
                   for i, c in enumerate("342")]
        assert fs._stellungen([basis] + ziffern) == ["", "", "", ""]

    def test_komma_im_index(self):
        """"s" mit Index "irr,12": das Komma sitzt tiefer als die Grundlinie, gehoert aber zum Index."""
        teile = zeile("s", ("i", "tief"), ("r", "tief"))
        komma = fs.Teil([9], ",", teile[-1].r, teile[-1].r + 2, 93.0, 96.0, 97.5, K, folge=9)
        teile += [komma, teil("1", komma.r, 97.5, K, folge=10), teil("2", komma.r + 4, 97.5, K, folge=11)]
        assert fs.setzen(teile, True) == "s_{ir,12}"
