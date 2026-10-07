"""Lesereihenfolge zweispaltiger Seiten (lesefolge.py) und ihr Zusammenspiel mit pdf2md und der Formelreparatur."""

import re

import formeln as F
import lesefolge as L
import pdf2md as p
from conftest import FUELLTEXT, erzeuge_pdf, erzeuge_zweispaltig, spaltenzeilen


def lauf(start, x0, x1, y):
    """Ein Lauf (Zeilenstueck) wie laeufe_lesen ihn liefert: [start, ende, (links, unten, rechts, oben), Fortsetzung]."""
    return [start, start + 10, (x0, y - 8, x1, y), False]


def seite(links_zuerst=True, spalten=2, kopf=False):
    """Laeufe einer Seite: 20 Zeilen je Spalte, dazu optional eine Kopfzeile ueber beiden Spalten."""
    breite = 460 / spalten
    spaltenlaeufe = []
    for s in range(spalten):
        x0 = 60 + s * breite
        spaltenlaeufe.append([lauf(0, x0, x0 + breite - 20, 700 - 12 * k) for k in range(20)])
    if not links_zuerst:
        spaltenlaeufe.reverse()
    alle = [lz for spalte in spaltenlaeufe for lz in spalte]
    if kopf:
        alle.insert(0, lauf(0, 60, 520, 780))
    for nr, lz in enumerate(alle):                                              # fortlaufende Zeichenbereiche
        lz[0], lz[1] = nr * 10, nr * 10 + 10
    return alle


class TestReihenfolge:
    def test_rechte_spalte_zuerst_wird_umgestellt(self):
        laeufe = seite(links_zuerst=False)
        ordnung = L.reihenfolge(laeufe)
        assert ordnung is not None
        x = [laeufe[i][2][0] for i in ordnung]
        assert x == sorted(x)                                                   # erst alle linken, dann alle rechten
        y_links = [laeufe[i][2][3] for i in ordnung[:20]]
        assert y_links == sorted(y_links, reverse=True)                         # jede Spalte von oben nach unten
        assert sorted(ordnung) == list(range(len(laeufe)))                      # nichts fehlt, nichts doppelt

    def test_richtige_reihenfolge_bleibt(self):
        assert L.reihenfolge(seite(links_zuerst=True)) is None

    def test_kopfzeile_bleibt_oben(self):
        laeufe = seite(links_zuerst=False, kopf=True)
        ordnung = L.reihenfolge(laeufe)
        assert ordnung is not None and ordnung[0] == 0                          # die Kopfzeile ueber beiden Spalten

    def test_einspaltige_seite_bleibt(self):
        laeufe = [lauf(k * 10, 60, 520, 700 - 12 * k) for k in range(30)]
        assert L.analysiere(laeufe) == (False, None)

    def test_dreispaltige_seite_bleibt(self):
        assert L.reihenfolge(seite(links_zuerst=False, spalten=3)) is None

    def test_zu_wenig_text_bleibt(self):
        assert L.reihenfolge(seite(links_zuerst=False)[:8]) is None

    def test_tabelle_mit_kurzen_zellen_ist_keine_spalte(self):
        laeufe = [lauf(k * 10, 60 + 60 * (k % 6), 100 + 60 * (k % 6), 700 - 12 * (k // 6)) for k in range(60)]
        assert L.reihenfolge(laeufe) is None

    def test_satzbrueche(self):
        assert L.satzbrueche("Das ist ein langer Satz, der hier endet.\nund geht klein weiter.") == 1
        assert L.satzbrueche("Das ist ein langer Satz, der hier weitergeht\nund geht klein weiter.") == 0


class TestMitPdf:
    def test_umgestellte_spalten_im_text(self, tmp_path):
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"), rechts_zuerst=True)
        statistik = {}
        text = p._pdfium_seiten(pdf, statistik)[0]
        assert statistik == {"spalten": 1}
        assert text.index("Linke Spalte, Zeile 01") < text.index("Linke Spalte, Zeile 20") < text.index("Rechte Spalte, Zeile 01")
        assert text.index("Rechte Spalte, Zeile 01") < text.index("Rechte Spalte, Zeile 20")

    def test_ohne_die_funktion_bleibt_die_pdf_reihenfolge(self, tmp_path, monkeypatch):
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"), rechts_zuerst=True)
        monkeypatch.setattr(p, "SPALTENREIHENFOLGE", False)
        text = p._pdfium_seiten(pdf)[0]
        assert text.index("Rechte Spalte, Zeile 01") < text.index("Linke Spalte, Zeile 01")

    def test_neue_reihenfolge_mit_zusaetzlichem_satzbruch_wird_verworfen(self, tmp_path):
        """Kontrolle am Text: Endet die linke Spalte mit einem Satzende und die rechte beginnt klein, waere die neue
        Reihenfolge schlechter als die alte. Dann bleibt der Text, wie PDFium ihn liefert."""
        links = spaltenzeilen("Linke")
        links[-1] += "."
        rechts = [z[0].lower() + z[1:] for z in spaltenzeilen("Rechte")]
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", links, rechts, rechts_zuerst=True)
        statistik = {}
        text = p._pdfium_seiten(pdf, statistik)[0]
        assert statistik == {}
        assert text.index("rechte Spalte, Zeile 01") < text.index("Linke Spalte, Zeile 01")

    def test_richtige_reihenfolge_wird_nicht_angefasst(self, tmp_path, monkeypatch):
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"))
        statistik = {}
        mit = p._pdfium_seiten(pdf, statistik)
        monkeypatch.setattr(p, "SPALTENREIHENFOLGE", False)
        assert mit == p._pdfium_seiten(pdf) and statistik == {}

    def test_normale_seite_bleibt_gleich(self, tmp_path, monkeypatch):
        pdf = erzeuge_pdf(tmp_path / "n.pdf", [FUELLTEXT, FUELLTEXT])
        statistik = {}
        mit = p._pdfium_seiten(pdf, statistik)
        monkeypatch.setattr(p, "SPALTENREIHENFOLGE", False)
        assert mit == p._pdfium_seiten(pdf) and statistik == {}

    def test_kein_zeichen_geht_verloren(self, tmp_path, monkeypatch):
        """Kein Inhalt geht verloren oder wird erfunden. Der SPALTENBRUCH-Marker zaehlt nicht mit: er ist keine
        Inhaltsangabe, sondern eine Formatierungsentscheidung (erzwungener Absatz), die _seite_bereinigen() spaeter
        wieder in eine Leerzeile umwandelt und die deshalb im fertigen Text nie sichtbar ist."""
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"), rechts_zuerst=True)
        neu = p._pdfium_seiten(pdf)[0].replace(p.SPALTENBRUCH, "")
        monkeypatch.setattr(p, "SPALTENREIHENFOLGE", False)
        alt = p._pdfium_seiten(pdf)[0]
        ohne_leerraum = lambda t: sorted("".join(t.split()))
        assert ohne_leerraum(neu) == ohne_leerraum(alt)

    def test_spaltenbruch_verschwindet_im_fertigen_text(self, tmp_path):
        """Der SPALTENBRUCH-Marker darf nie im tatsaechlichen Ergebnis auftauchen, nur als erzwungene Leerzeile."""
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"), rechts_zuerst=True)
        roh = p._pdfium_seiten(pdf)[0]
        assert p.SPALTENBRUCH in roh                                     # der Marker wurde tatsaechlich gesetzt
        text = p.seiten_zu_text([roh])
        assert p.SPALTENBRUCH not in text
        assert "\n\n" in text                                            # ... und wurde zu einer echten Leerzeile

    def test_kein_absatz_ueber_die_spaltengrenze(self, tmp_path):
        """Regressionstest: Endet die linke Spalte mit einer vollen Zeile ohne Satzzeichen (fuer _absaetze_bilden()
        also 'mitten im Satz'), darf sie trotzdem nie mit der ersten Zeile der rechten Spalte verschmolzen werden."""
        links = [f"Linke Spalte Zeile {n:02d} laeuft weiter" for n in range(1, 21)]
        rechts = spaltenzeilen("Rechte")
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", links, rechts, rechts_zuerst=True)
        text = p.seiten_zu_text(p._pdfium_seiten(pdf))
        assert "weiter Rechte" not in text and "weiterRechte" not in text
        assert re.search(r"weiter\s*\n\s*\n\s*Rechte Spalte, Zeile 01", text)

    def test_textquelle_nennt_die_spaltenreihenfolge(self, monkeypatch):
        assert "Spaltenreihenfolge" in p.erwartete_textquelle()
        monkeypatch.setattr(p, "SPALTENREIHENFOLGE", False)
        assert "Spaltenreihenfolge" not in p.erwartete_textquelle()

    def test_gesamtablauf_meldet_die_seiten(self, arbeitsordner, konverter, tmp_path):
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", spaltenzeilen("Linke"), spaltenzeilen("Rechte"), rechts_zuerst=True)
        text, quelle, extra = p.umwandeln(pdf, 1, konverter)
        assert extra["spalten"] == 1 and "+ Spaltenreihenfolge" in quelle
        assert text.index("Linke Spalte, Zeile 20") < text.index("Rechte Spalte, Zeile 01")


class TestFormelreparaturBleibtInReihenfolge:
    def test_wiederaufbau_des_seitentextes_folgt_der_lesereihenfolge(self, tmp_path):
        """Die Formelreparatur baut Seiten aus den Zeichen neu auf. Das muss dieselbe Reihenfolge ergeben wie der Text."""
        pdf = erzeuge_zweispaltig(tmp_path / "z.pdf", [z.replace("Text", "Zett") for z in spaltenzeilen("Linke")],
                                  [z.replace("Text", "Zett") for z in spaltenzeilen("Rechte")], rechts_zuerst=True)
        roh = p._pdfium_seiten(pdf)

        class Ersatz(F.Reparatur):
            def _weg_b(self, seiten, zeichen):                                  # Z -> Q, ohne Seiten zu rendern
                for sz in zeichen.values():
                    for schrift, code in set(zip(sz.fonts, sz.codes)):
                        if code == ord("Z"):
                            self.zuordnung[(schrift, code)] = "Q"
        rep = Ersatz(pdf, spalten=True)
        try:
            neu = rep.reparieren(roh, alle_seiten=True)
        finally:
            rep.schliessen()
        normiert = lambda t: " ".join(t.split())
        assert normiert(neu[0]) == normiert(roh[0].replace("Z", "Q"))
        assert neu[0].index("Linke Spalte, Qeile 20") < neu[0].index("Rechte Spalte, Qeile 01")   # 'Zeile' wurde zu 'Qeile'
