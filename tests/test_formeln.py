"""Formelreparatur (formeln.py): Glyphnamen, Referenzzeichen, Formvergleich und Schutzregeln."""

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

import formeln as F
import pdf2md as p
from conftest import FUELLTEXT, erzeuge_pdf


class TestGlyphnamen:
    @pytest.mark.parametrize("name, erwartet", [
        ("beta", "β"), ("radical", "√"), ("prime", "′"), ("greatermuch", "≫"),
        ("SOH", None), ("c129", None), (".notdef", None),                       # unbrauchbare Namen
    ])
    def test_name_zu_unicode(self, name, erwartet):
        assert F._name_zu_unicode(name) == erwartet


class TestSchriftmuster:
    @pytest.mark.parametrize("name", ["QdxnpwMT2MIT", "JdfmwsMT2SYT", "MwtpqpMT2EXA", "MTEX3", "MTMI4"])
    def test_mathtime_schriften_sind_verdaechtig(self, name):
        assert F.VERDAECHTIG.search(name)

    @pytest.mark.parametrize("name", ["TimesNewRomanPSMT2", "ArialMT2", "Arial-ItalicMT2", "TimesNewRomanPS-BoldMT2",
                                      "Times-Roman", "DcyyqgTimes-Roman"])
    def test_normale_textschriften_sind_es_nicht(self, name):
        """Regressionstest: 'TimesNewRomanPSMT2' wurde einmal als MathTime erkannt und das 'n' zerstoert."""
        assert not F.VERDAECHTIG.search(name)
        assert not F.MATHESCHRIFT.search(name)

    def test_latex_schriften_sind_mathematik(self):
        assert F.MATHESCHRIFT.search("XtmgkvCMSY9") and F.MATHESCHRIFT.search("BvwfdmCMMI9")


class TestBildhilfen:
    @pytest.mark.parametrize("n", [1, 5, 27, 28, 29, 200])
    def test_profile_kleiner_bilder_haben_feste_laenge(self, n):
        assert len(F._auf_raster(np.random.rand(n))) == F.RASTER

    def test_nachbarn_im_rahmen_hoher_zeichen_werden_entfernt(self):
        bild = Image.new("L", (80, 120), 0)
        zeichner = ImageDraw.Draw(bild)
        zeichner.rectangle((30, 10, 50, 110), fill=255)                        # grosses Zeichen
        zeichner.rectangle((2, 5, 10, 14), fill=255)                           # kleiner Nachbar
        gefiltert = np.asarray(F._grosse_komponenten(bild))
        assert gefiltert[5:14, 2:10].max() == 0
        assert gefiltert[10:110, 30:50].min() == 255


class TestFormvergleich:
    @staticmethod
    def probe(zeichen, schrift="STIXGeneral.ttf"):
        font = ImageFont.truetype(str(F.SCHRIFTEN / schrift), 90)
        bild = Image.new("L", (300, 300), 0)
        ImageDraw.Draw(bild).text((100, 200), zeichen, font=font, fill=255, anchor="ls")
        box = bild.getbbox()
        return {"vec": F._vektor(bild), "breite": (box[2] - box[0]) / 90, "hoehe": (box[3] - box[1]) / 90,
                "oben": (200 - box[1]) / 90, "unten": (200 - box[3]) / 90}

    def bestes(self, probe):
        punkte = {z: F.punktzahl(probe, z, True) for z in F.MATHE_SATZ}
        return max(punkte, key=punkte.get)

    def test_referenzschriften_sind_vorhanden(self):
        assert len(F._referenz().schriften) >= 3

    @pytest.mark.parametrize("zeichen", list("=+×σπ√≤ω"))
    def test_selbsterkennung(self, zeichen):
        assert self.bestes(self.probe(zeichen)) == zeichen

    @pytest.mark.parametrize("zeichen", list("=+×σπ≤ω"))
    def test_erkennung_ueber_schriftgrenzen(self, zeichen):
        assert self.bestes(self.probe(zeichen, "DejaVuSans.ttf")) == zeichen


@pytest.mark.langsam
class TestGanzeReparatur:
    def test_korrekte_pdf_bleibt_unveraendert(self, tmp_path):
        """Schutzregel: Was PDFium richtig liest, wird nie 'repariert'. Buchstaben und Ziffern schon gar nicht."""
        pdf = erzeuge_pdf(tmp_path / "m.pdf", [f"Kraft F = 150 N, Winkel σ ≤ π/2, x × y ± z, Summe ∑ und √2. {FUELLTEXT}"])
        roh = p._pdfium_seiten(pdf)
        rep = F.Reparatur(pdf)
        try:
            neu = rep.reparieren(roh, alle_seiten=True)
        finally:
            rep.schliessen()
        assert neu == roh

    def test_unicode_ausserhalb_der_basisebene(self, tmp_path):
        """Regressionstest: einzelne UTF-16-Haelften machten den Text unspeicherbar."""
        pdf = erzeuge_pdf(tmp_path / "u.pdf", [f"Text mit Sonderzeichen ä ö ü ß und Formeln. {FUELLTEXT}"])
        text = p.seiten_zu_text(p._pdfium_seiten(pdf))
        text.encode("utf-8")

    def test_aktive_reparatur_bricht_normale_pdf_nicht(self, arbeitsordner, konverter, tmp_path, monkeypatch):
        monkeypatch.setattr(p, "FORMELN_REPARIEREN", True)
        pdf = erzeuge_pdf(tmp_path / "n.pdf", [f"Ein normaler Text mit Umlauten äöü. {FUELLTEXT}"])
        text, quelle, extra = p.umwandeln(pdf, 1, konverter)
        assert "Ein normaler Text mit Umlauten äöü." in text
        assert "Formelreparatur" in quelle and extra["ersetzt"] == 0

    @pytest.mark.parametrize("teil", ["analysieren", "aufbauen"])
    def test_ausfall_der_reparatur_verhindert_die_umwandlung_nicht(self, arbeitsordner, konverter, tmp_path, monkeypatch,
                                                                     teil):
        monkeypatch.setattr(p, "FORMELN_REPARIEREN", True)

        def kaputt(*a, **k):
            raise RuntimeError("absichtlich")
        monkeypatch.setattr(F.Reparatur, teil, kaputt)
        pdf = erzeuge_pdf(tmp_path / "n.pdf", [f"Text. {FUELLTEXT}"])
        text, quelle, extra = p.umwandeln(pdf, 1, konverter)
        assert "Text." in text and quelle == "PDFium"                           # bleibt ohne '+ Formelreparatur'


class TestZuordnungFuerFormelsatz:
    """Der Formelsatz holt reparierte Zeichen ueber zuordnung_fuer() (sonst stuende "D" statt "=" in Formeln)."""

    @staticmethod
    def reparatur():
        r = F.Reparatur.__new__(F.Reparatur)
        sz = F._SeitenZeichen()
        sz.codes, sz.fonts = [ord("D"), 2, 2, ord("x")], [0, 0, 1, 1]
        r._zeichen = {5: sz}
        r.fontnamen = ["ABCDEF+MT2SYT2", "ABCDEF+TimesNewRoman"]
        r.zuordnung = {(0, ord("D")): "=", (0, 2): "·", (1, 2): "-"}
        return r

    def test_repariertes_zeichen(self):
        z = self.reparatur().zuordnung_fuer(5)
        assert z(0, ord("D")) == "=" and z(3, ord("x")) is None

    def test_code_2_nur_in_formelschrift(self):
        z = self.reparatur().zuordnung_fuer(5)
        assert z(1, 2) == "·"          # MathTime: Malpunkt
        assert z(2, 2) is None         # Textschrift: Trennstrich, regelt der Neuaufbau

    def test_andere_seite_oder_falscher_code(self):
        r = self.reparatur()
        assert r.zuordnung_fuer(6) is None and r.zuordnung_fuer(5)(0, ord("E")) is None
