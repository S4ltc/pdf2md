"""Ueberschriften aus den PDF-Lesezeichen."""

import re

import pdf2md as p
from conftest import FUELLTEXT, erzeuge_pdf


class TestEinfuegen:
    def test_titel_im_text_wird_direkt_zur_ueberschrift(self):
        text = "Vorspann\n1 Einleitung\nDer Text danach."
        erg = p._ueberschriften_einfuegen(text, [(0, "1 Einleitung")])
        assert erg.split("\n") == ["Vorspann", "", "# 1 Einleitung", "", "Der Text danach."]

    def test_ebenen(self):
        erg = p._ueberschriften_einfuegen("A\nB\nC", [(0, "A"), (1, "B"), (2, "C")])
        assert "# A" in erg and "## B" in erg and "### C" in erg

    def test_hoechstens_sechs_ebenen(self):
        assert p._ueberschriften_einfuegen("X", [(9, "X")]).startswith("###### X")

    def test_titel_der_nicht_im_text_steht_kommt_an_den_seitenanfang(self):
        erg = p._ueberschriften_einfuegen("Nur Fliesstext hier.", [(0, "Zusammenfassung")])
        assert erg.startswith("# Zusammenfassung\n\nNur Fliesstext")

    def test_titel_ueber_mehrere_zeilen_wird_zusammengefuehrt(self):
        text = "Ein sehr langer Kapiteltitel der\nueber zwei Zeilen geht\nText."
        erg = p._ueberschriften_einfuegen(text, [(0, "Ein sehr langer Kapiteltitel der ueber zwei Zeilen geht")])
        assert "# Ein sehr langer Kapiteltitel der ueber zwei Zeilen geht" in erg
        assert "\nueber zwei" not in erg

    def test_gross_klein_und_leerraum_egal(self):
        assert "# Einleitung" in p._ueberschriften_einfuegen("EINLEITUNG\nText", [(0, "Einleitung")]).replace(
            "# EINLEITUNG", "# Einleitung")

    def test_lesezeichen_ohne_leerzeichen_am_umbruch(self):
        """Normen: das Lesezeichen laesst den Leerraum an den Zeilenumbruechen weg und umfasst vier Zeilen."""
        text = ("Nationaler Anhang NA\n(informativ)\nZusammenhang zwischen den Prüfklassen\nund der "
                "DIN EN ISO 45678-3\nDie Tabelle NA.1 zeigt ...")
        titel = "Nationaler Anhang NA (informativ)Zusammenhang zwischen den Prüfklassen und der DIN\xa0EN ISO 45678-3 "
        erg = p._ueberschriften_einfuegen(text, [(1, titel)])
        assert erg.startswith("## Nationaler Anhang NA (informativ) Zusammenhang zwischen den Prüfklassen und "
                              "der DIN EN ISO 45678-3\n\nDie Tabelle")

    def test_gleicher_titel_zweimal_auf_einer_seite_nutzt_zwei_zeilen(self):
        erg = p._ueberschriften_einfuegen("Literatur\nText\nLiteratur", [(1, "Literatur"), (1, "Literatur")])
        assert erg.count("## Literatur") == 2

    def test_statistik(self):
        stat = {}
        p._ueberschriften_einfuegen("A\nText", [(0, "A"), (0, "nicht da")], stat)
        assert stat == {"gesamt": 2, "im_text": 1}


class TestGanzeDatei:
    def erzeuge(self, tmp_path):
        return erzeuge_pdf(
            tmp_path / "buch.pdf",
            ["Titelseite\n" + FUELLTEXT, "1 Einleitung\n" + FUELLTEXT, "1.1 Grundlagen\n" + FUELLTEXT,
             "Nur Text ohne Ueberschriftzeile\n" + FUELLTEXT],
            titel="Buch", autor="Anna",
            lesezeichen={1: [(0, "1 Einleitung")], 2: [(1, "1.1 Grundlagen")], 3: [(0, "Zusammenfassung")]})

    def test_lesezeichen_lesen(self, tmp_path):
        assert p.lesezeichen_lesen(self.erzeuge(tmp_path)) == {
            1: [(0, "1 Einleitung")], 2: [(1, "1.1 Grundlagen")], 3: [(0, "Zusammenfassung")]}

    def test_pdf_ohne_lesezeichen(self, tmp_path):
        assert p.lesezeichen_lesen(erzeuge_pdf(tmp_path / "x.pdf", ["Text"])) == {}

    def test_kaputte_datei(self, tmp_path):
        datei = tmp_path / "kaputt.pdf"
        datei.write_bytes(b"kein pdf")
        assert p.lesezeichen_lesen(datei) == {}

    def test_ueberschriften_landen_im_text(self, arbeitsordner, konverter, tmp_path):
        text, quelle, extra = p.umwandeln(self.erzeuge(tmp_path), 4, konverter)
        zeilen = text.split("\n")
        assert "# 1 Einleitung" in zeilen and "## 1.1 Grundlagen" in zeilen
        assert "# Zusammenfassung" in zeilen                                      # nicht im Text: am Seitenanfang
        assert (extra["ueberschriften"], extra["ueberschriften_im_text"]) == (3, 2)
        assert "+ Lesezeichen" in quelle

    def test_ueberschrift_steht_auf_der_richtigen_seite(self, arbeitsordner, konverter, tmp_path):
        text, _, _ = p.umwandeln(self.erzeuge(tmp_path), 4, konverter)
        seite2 = re.split(r"<!-- (?:PDF-Seite|Seite \S+ \(PDF) [23]\)? -->", text)[1]
        assert "# 1 Einleitung" in seite2

    def test_abschaltbar(self, arbeitsordner, konverter, tmp_path, monkeypatch):
        monkeypatch.setattr(p, "UEBERSCHRIFTEN_AUS_LESEZEICHEN", False)
        text, quelle, extra = p.umwandeln(self.erzeuge(tmp_path), 4, konverter)
        assert not re.search(r"(?m)^#{1,6} ", text)
        assert "Lesezeichen" not in quelle and "ueberschriften" not in extra

    def test_scan_mit_lesezeichen_wird_nicht_zum_textbuch(self, arbeitsordner, konverter, tmp_path):
        """Seiten ohne Text bekommen keine Ueberschrift, sonst wuerde die Scan-Erkennung getaeuscht."""
        pdf = erzeuge_pdf(tmp_path / "scan.pdf", [""] * 30, lesezeichen={i: [(0, f"Kapitel {i} mit einem langen Titel")]
                                                                           for i in range(30)})
        text, _, _ = p.umwandeln(pdf, 30, konverter)
        assert len(p.nutztext(text).strip()) < p.MIN_TEXT_ZEICHEN
