"""Dateinamen, Metadaten-Erkennung (PDF, DOCX, EPUB, HTML) und Jahr-/Kennungssuche."""

import pytest

import pdf2md as p
from conftest import erzeuge_buch, erzeuge_docx, erzeuge_epub, erzeuge_pdf


class TestNamen:
    def test_bereinigen_entfernt_verbotene_zeichen(self):
        assert p.bereinigen('Was? <ist> "das": Ein|Test/') == "Was ist das – Ein Test"

    def test_doppelpunkt_wird_zum_gedankenstrich(self):
        assert p.bereinigen("Titel: Untertitel") == "Titel – Untertitel"

    @pytest.mark.parametrize("autor, erwartet", [
        ("Anna Beispiel", "Anna Beispiel"),
        ("Anna Beispiel, Bert Redner", "Anna Beispiel, Bert Redner"),
        ("Anna Beispiel, Bert Redner, Clara Zahl", "Anna Beispiel et al."),
        ("A und B und C", "A et al."),
    ])
    def test_kurzer_autor(self, autor, erwartet):
        assert p.kurzer_autor(autor) == erwartet

    def test_kurzer_name_bleibt_unveraendert(self):
        assert p.neuer_name("Kurzer Titel", "Anna Beispiel", "2020") == "Kurzer Titel - Anna Beispiel - 2020"

    def test_et_al_behaelt_den_punkt(self):
        assert p.neuer_name("Buch", "A B, C D, E F", "2015") == "Buch - A B et al. - 2015"

    @pytest.mark.parametrize("titel", [
        "Musteranlagen: Grundlagen, Bauformen, Betrieb und Wartung, Messverfahren, Regelung, Sicherheit und "
        "Beispiele aus der Praxis",
        "A" * 300,
        "Ein sehr langer Haupttitel ohne jeden Untertitel der einfach nicht aufhoeren will und immer weiter geht bis er "
        "zu lang ist fuer einen Dateinamen",
    ])
    def test_lange_namen_behalten_autor_und_jahr(self, titel):
        name = p.neuer_name(titel, "Willi Beispiel", "2015")
        assert len(name) <= p.MAX_NAME_LEN
        assert name.endswith(" - Willi Beispiel - 2015")

    def test_langer_untertitel_faellt_zuerst_weg(self):
        name = p.neuer_name("Beispielelemente 1: Grundlagen der Berechnung und Gestaltung von Maschinenelementen fuer "
                            "alle Studiengaenge", "Erika Muster, Anna Zwei, Otto Drei", "2023")
        assert name == "Beispielelemente 1 - Erika Muster et al. - 2023"

    def test_extrem_langer_autor_wird_gekuerzt(self):
        name = p.neuer_name("Titel", "Sehr Langer Autorenname " * 5, "1999")
        assert len(name) <= p.MAX_NAME_LEN and name.endswith(" - 1999")

    def test_freier_name_haengt_zaehler_an(self, tmp_path):
        (tmp_path / "Buch.pdf").write_bytes(b"x")
        assert p.freier_name(tmp_path, "Buch", ".pdf") == "Buch (2)"
        (tmp_path / "Buch (2).md").write_text("x")
        assert p.freier_name(tmp_path, "Buch", ".pdf") == "Buch (3)"


class TestJahr:
    @pytest.mark.parametrize("text, erwartet", [
        ("Titel\n© 2019 Verlag", "2019"),
        ("(c) 2015 Beispielverlag, Berlin", "2015"),
        ("Copyright 2001 Autor", "2001"),
        ("© Springer Nature Switzerland AG\n2025", "2025"),                     # Jahr nach Zeilenumbruch
        ("©Springer-VerlagGmbH 1914, 1929, 2018, korrigiertePublikation2019", "2019"),   # juengstes Jahr
        ("Erstausgabe 2001 im Verlag", "2001"),
        ("Hier steht gar kein Jahr", None),
    ])
    def test_jahr_finden(self, text, erwartet):
        assert p.jahr_finden(text) == erwartet

    def test_zukunftsjahre_werden_ignoriert(self):
        assert p.jahr_finden("© 2099 Verlag") is None

    def test_isbn_ziffern_sind_kein_jahr(self):
        assert p.jahr_finden("ISBN 978-3-000-00004-5 © Verlag") is None

    def test_seitenmarker_stoeren_nicht(self):
        assert p.jahr_finden("<!-- Seite 1998 -->\n© 2019 Verlag") == "2019"


class TestKennungen:
    def test_titel_der_nur_eine_isbn_ist(self):
        assert p.ist_kennung("978-3-000-00004-5")
        assert p.ist_kennung("10.1007/978-3-000-00004-5")
        assert not p.ist_kennung("Ein ganz normaler Titel")

    def test_kennungen_dois_vor_isbns_ohne_kapitel_dois(self):
        info = {"kennungen": ["978-3-000-00005-2"]}
        text = "https://doi.org/10.1007/978-3-000-00005-2 und Kapitel 10.1007/978-3-000-00005-2_5 ISBN 978-3-000-00006-9"
        kennungen = p.kennungen_sammeln(info, text)
        assert kennungen[0] == "10.1007/978-3-000-00005-2"
        assert not any(k.endswith("_5") for k in kennungen)
        assert "978-3-000-00006-9" in kennungen


class TestMetadatenLesen:
    def test_pdf(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_buch(tmp_path / "b.pdf", titel="Mein Buch", autor="Anna Beispiel"))
        assert info["titel"] == "Mein Buch" and info["autor"] == "Anna Beispiel" and info["seiten"] == 2

    @pytest.mark.parametrize("titel", ["Microsoft Word - Dokument1", "untitled", "Bericht.docx", "978-3-000-00004-5"])
    def test_platzhaltertitel_werden_verworfen(self, tmp_path, titel):
        info = p.metadaten_lesen(erzeuge_pdf(tmp_path / "b.pdf", ["Text"], titel=titel, autor="Anna"))
        assert info["titel"] is None

    def test_isbn_als_titel_wird_zur_kennung(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_pdf(tmp_path / "b.pdf", ["Text"], titel="978-3-000-00004-5", autor="Anna"))
        assert info["titel"] is None and "978-3-000-00004-5" in info["kennungen"]

    def test_platzhalterautor_wird_verworfen(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_pdf(tmp_path / "b.pdf", ["Text"], titel="Buch", autor="admin"))
        assert info["autor"] is None

    def test_erstellungsdatum_ist_kein_erscheinungsjahr(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_buch(tmp_path / "b.pdf"))
        assert info["jahr"] is None

    def test_docx(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_docx(tmp_path / "d.docx", titel="Handbuch der Testerei", autor="Anna Beispiel"))
        assert info["titel"] == "Handbuch der Testerei" and info["autor"] == "Anna Beispiel" and info["jahr"] is None

    def test_epub_liefert_auch_das_erscheinungsjahr(self, tmp_path):
        info = p.metadaten_lesen(erzeuge_epub(tmp_path / "e.epub", "Der lange Weg", "Dora Dichter", "2018-05-01",
                                              isbn="9781234567897"))
        assert (info["titel"], info["autor"], info["jahr"]) == ("Der lange Weg", "Dora Dichter", "2018")
        assert any("9781234567897" in k for k in info["kennungen"])

    def test_html(self, tmp_path):
        datei = tmp_path / "h.html"
        datei.write_text('<html><head><title>Ein Artikel</title><meta name="author" content="Emil Autor"></head>'
                         "<body>x</body></html>", encoding="utf-8")
        info = p.metadaten_lesen(datei)
        assert info["titel"] == "Ein Artikel" and info["autor"] == "Emil Autor"

    def test_kaputte_office_datei_stoppt_nicht(self, tmp_path):
        datei = tmp_path / "kaputt.docx"
        datei.write_bytes(b"das ist kein zip")
        assert p.metadaten_lesen(datei)["titel"] is None
