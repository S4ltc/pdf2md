"""Grenzfaelle aus dem Haertetest (Oktober 2026): Platzhalter-Metadaten, HTML-Zeichensaetze und Dublin-Core/
citation-Angaben, XLSX ohne "NaN", verstaendliche Fehlermeldungen, gesperrte Dateien, lange Pfade, Netzausfall bei
Kapitel-DOIs. Jeder Test steht fuer eine Schwachstelle, die mit echten oder erzeugten Dateien aufgefallen ist."""
import zipfile
from pathlib import Path

import pytest

import pdf2md as p
import zitierdaten
from conftest import FUELLTEXT, erzeuge_buch, erzeuge_pdf


def leere_info():
    return {"titel": None, "autor": None, "jahr": None, "seiten": None, "titel_quelle": None, "autor_quelle": None,
            "jahr_quelle": None, "kennungen": []}


class TestPlatzhalter:
    @pytest.mark.parametrize("titel", ["Microsoft Word - Bericht", "Dokument1", "document 3", "Präsentation1",
                                       "Mappe1", "Book1", "Untitled-1", "Unbenannt", "Layout 1", "Bericht.docx",
                                       '???:*<>|"', " - – "])
    def test_platzhalter_und_leere_titel_werden_verworfen(self, titel):
        info = leere_info()
        p._titel_setzen(info, titel, "PDF-Metadaten")
        assert info["titel"] is None

    @pytest.mark.parametrize("titel", ["Sehr langes Dokument", "Layout von Leiterplatten", "Das Dokument als Quelle",
                                       "Unbenannte Größen in der Mechanik"])
    def test_echte_titel_mit_platzhalterwort_bleiben(self, titel):
        info = leere_info()
        p._titel_setzen(info, titel, "PDF-Metadaten")
        assert info["titel"] == titel

    @pytest.mark.parametrize("autor", ["python-docx", "openpyxl", "python-pptx", "Microsoft Office User",
                                       "Microsoft Office-Benutzer", "Windows-Benutzer", "Windows User"])
    def test_programm_und_standardnamen_sind_keine_autoren(self, autor):
        info = leere_info()
        p._autor_setzen(info, autor, "Dokument-Eigenschaften")
        assert info["autor"] is None

    def test_nachbessern_mit_titel_ohne_buchstaben_wartet(self, tmp_path):
        md = tmp_path / "x.md"
        (tmp_path / "x.pdf").write_bytes(b"x")
        assert p.uebernahme_pruefen({"titel": "???", "autor": "A", "jahr": "2001"}, md) == "Titel fehlt"


class TestHtml:
    def schreibe(self, pfad, kopf, text="<p>" + FUELLTEXT + "</p>", kodierung="utf-8"):
        pfad.write_bytes(f"<html><head>{kopf}</head><body>{text}</body></html>".encode(kodierung))
        return pfad

    def test_dublin_core_wie_bei_gutenberg(self, tmp_path):
        datei = self.schreibe(tmp_path / "g.html", '<meta charset="utf-8"><meta name="dc.title" content="Die Verwandlung">'
                              '<meta name="dc.creator" content="Kafka, Franz, 1883-1924">'
                              '<meta name="dcterms.created" content="2007-08-21">'
                              '<title>Die Verwandlung, by Franz Kafka—A Project Gutenberg eBook</title>')
        info = p.metadaten_lesen(datei)
        assert (info["titel"], info["autor"], info["jahr"]) == ("Die Verwandlung", "Franz Kafka", None)

    def test_citation_angaben_von_fachzeitschriften(self, tmp_path):
        datei = self.schreibe(tmp_path / "a.html",
                              '<meta content="Wälzlager im Vergleich" name="citation_title">'
                              '<meta name="citation_author" content="Muster, Max">'
                              '<meta name="citation_author" content="Beispiel, Anna">'
                              '<meta name="citation_publication_date" content="2019/05/03">'
                              '<meta name="citation_doi" content="10.1000/beispiel.2019.001"><title>Journal</title>')
        info = p.metadaten_lesen(datei)
        assert (info["titel"], info["autor"], info["jahr"]) == ("Wälzlager im Vergleich", "Max Muster, Anna Beispiel",
                                                               "2019")
        assert "10.1000/beispiel.2019.001" in info["kennungen"]

    def test_windows_1252_ohne_angabe_wird_richtig_gelesen(self, tmp_path, konverter):
        datei = self.schreibe(tmp_path / "alt.htm", "<title>Größen</title>", "<p>Übergröße ÄÖÜ ß " + FUELLTEXT + "</p>",
                              kodierung="cp1252")
        assert p.metadaten_lesen(datei)["titel"] == "Größen"
        text, _, _ = p.umwandeln(datei, None, konverter)
        assert "Übergröße ÄÖÜ ß" in text

    def test_angegebener_zeichensatz_gilt(self, tmp_path, konverter):
        datei = self.schreibe(tmp_path / "l1.html", '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
                              "<title>Maße</title>", "<p>Fußnote " + FUELLTEXT + "</p>", kodierung="latin-1")
        assert p.metadaten_lesen(datei)["titel"] == "Maße"
        assert "Fußnote" in p.umwandeln(datei, None, konverter)[0]


def test_xlsx_ohne_nan_fuer_leere_zellen(tmp_path, konverter):
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["Probe", "Wert", "Bemerkung"])
    wb.active.append(["P1", 400, None])
    wb.active.append(["P2", 401, "ok"])
    wb.save(tmp_path / "t.xlsx")
    text = p.umwandeln(tmp_path / "t.xlsx", None, konverter)[0]
    assert "NaN" not in text and "| P1 | 400 |" in text and "ok" in text


class TestMeldungen:
    def test_kaum_text_meldung_je_format(self, arbeitsordner, konverter, lauf):
        from docx import Document
        Document().save(arbeitsordner.eingang / "leer.docx")
        assert "Dokument ist fast leer" in p.verarbeiten(arbeitsordner.eingang / "leer.docx", konverter, lauf)
        erzeuge_pdf(arbeitsordner.eingang / "scan.pdf", ["", ""], titel="Scan", autor="A")
        assert "Scan ohne Texterkennung" in p.verarbeiten(arbeitsordner.eingang / "scan.pdf", konverter, lauf)

    def test_verstaendliche_fehlertexte(self, tmp_path):
        from pypdf import PdfWriter
        leer = tmp_path / "leer.pdf"
        leer.write_bytes(b"")
        assert "leer" in p.fehlertext(ValueError("Cannot read an empty file"), leer)
        geschuetzt = erzeuge_buch(tmp_path / "g.pdf")
        w = PdfWriter(clone_from=geschuetzt)
        w.encrypt(user_password="x", owner_password="y")
        w.write(geschuetzt)
        try:
            p.metadaten_lesen(geschuetzt)
        except Exception as e:
            assert "Passwort" in p.fehlertext(e, geschuetzt)
        kaputt = tmp_path / "k.docx"
        kaputt.write_bytes(b"PK\x03\x04kaputt")
        assert "beschädigt" in p.fehlertext(zipfile.BadZipFile("File is not a zip file"), kaputt)
        assert "beschädigt" in p.fehlertext(RuntimeError("Stream has ended unexpectedly"), tmp_path / "x.pdf")
        assert "geöffnet" in p.fehlertext(PermissionError(13, "Zugriff verweigert"), tmp_path / "x.pdf")
        lang = p.fehlertext(RuntimeError("x" * 1000 + "\nzweite Zeile"), tmp_path / "x.pdf")
        assert len(lang) <= 200 and "zweite" not in lang

    def test_lauf_meldet_passwortschutz_verstaendlich(self, arbeitsordner):
        from pypdf import PdfWriter
        datei = erzeuge_buch(arbeitsordner.eingang / "g.pdf")
        w = PdfWriter(clone_from=datei)
        w.encrypt(user_password="x", owner_password="y")
        w.write(datei)
        stati = []
        p.eingang_verarbeiten("2026-01-01 10:00:00", melder=lambda t: None, datei_fertig=lambda n, s: stati.append(s))
        assert stati[0].startswith("FEHLER") and "Passwort" in stati[0]


class TestGesperrteDateien:
    def gesperrt(self, monkeypatch):
        def verweigern(*args, **kwargs):
            raise PermissionError(32, "Der Prozess kann nicht auf die Datei zugreifen")
        monkeypatch.setattr(p.shutil, "move", verweigern)

    def test_gesperrtes_original_hinterlaesst_keine_md(self, arbeitsordner, monkeypatch):
        erzeuge_buch(arbeitsordner.eingang / "a.pdf")
        self.gesperrt(monkeypatch)
        stati = []
        p.eingang_verarbeiten("2026-01-01 10:00:00", melder=lambda t: None, datei_fertig=lambda n, s: stati.append(s))
        assert "geöffnet" in stati[0]
        assert not list(arbeitsordner.fertig.glob("*.md")) and (arbeitsordner.eingang / "a.pdf").exists()

    def test_nachbessern_mit_gesperrtem_original_bricht_nicht_ab(self, arbeitsordner, konverter, lauf, monkeypatch):
        datei = erzeuge_pdf(arbeitsordner.eingang / "roh.pdf", ["x", FUELLTEXT], titel="Buch", autor="Max Muster")
        p.verarbeiten(datei, konverter, lauf)
        md = arbeitsordner.pruefen / "roh.md"
        md.write_text(md.read_text(encoding="utf-8").replace("jahr: null", "jahr: 2015"), encoding="utf-8")
        self.gesperrt(monkeypatch)
        assert p.nachbessern(lauf) == 0
        assert md.exists() and not list(arbeitsordner.fertig.glob("*.md"))

    def test_rueckgaengig_ueberspringt_gesperrte_datei_und_macht_weiter(self, arbeitsordner, konverter, monkeypatch):
        for n in ("a", "b"):
            p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / f"{n}.pdf", titel=f"Buch {n}"), konverter,
                          "2026-01-01 10:00:00")
        echt = p.shutil.move
        aufrufe = []

        def einmal_gesperrt(quelle, ziel):
            aufrufe.append(quelle)
            if len(aufrufe) == 1:
                raise PermissionError(32, "gesperrt")
            return echt(quelle, ziel)
        monkeypatch.setattr(p.shutil, "move", einmal_gesperrt)
        assert p.rueckgaengig() == 1
        assert len(list(arbeitsordner.eingang.glob("*.pdf"))) == 1


class TestPfadlaenge:
    def test_name_passt_in_tiefe_ordner(self):
        tief = Path("C:/" + "/".join(["Ordner mit langem Namen"] * 8))         # gut 200 Zeichen
        grenze = p.name_laenge(tief, ".pdf")
        assert 40 <= grenze < p.MAX_NAME_LEN
        name = p.neuer_name("Ein recht langer Titel über Maschinenelemente und ihre Berechnung", "Anna Beispiel",
                            "2020", max_len=grenze)
        assert len(name) <= grenze and name.endswith("Anna Beispiel - 2020")
        assert len(str(tief / name)) + len(" (2).pdf") <= 259

    def test_normaler_ordner_behaelt_die_volle_laenge(self):
        assert p.name_laenge(Path("C:/Bücher/Fertig"), ".pdf") == p.MAX_NAME_LEN


def test_kapitelabfrage_bricht_bei_netzausfall_ab(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(zitierdaten, "crossref", lambda doi: aufrufe.append(doi))
    buch = {"typ": "edited-book", "doi": "10.1007/978-3-000-00002-8", "titel": "Atlas der Beispiele"}
    text = "".join(f"<!-- Seite {i} (PDF {i}) -->\nKapitel {i} DOI 10.1007/978-3-000-00002-8_{i}\n" for i in range(1, 60))
    neu, anzahl = zitierdaten.kapitel_einfuegen(text, buch)
    assert anzahl == 0 and neu == text and len(aufrufe) <= 8


@pytest.mark.parametrize("inhalt", ["kaputt;ohne;Kopf\n1;2;3\n", "lauf,zeit,status\n2026,x,OK\n", "", "﻿"])
def test_kaputtes_protokoll_bricht_nichts(arbeitsordner, inhalt):
    """Von Hand (z.B. in Excel mit Komma) veraendertes Protokoll.csv: Rueckgaengig findet nichts, statt abzustuerzen."""
    arbeitsordner.protokoll.write_text(inhalt, encoding="utf-8")
    assert p.rueckgaengig_plan() is None
    assert p.rueckgaengig() == 0


def test_rueckgaengig_ohne_md_pfad_verschiebt_keinen_ordner(arbeitsordner, konverter, lauf, monkeypatch):
    p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "a.pdf"), konverter, lauf)
    text = arbeitsordner.protokoll.read_text(encoding="utf-8-sig")
    kopf, zeile = text.strip().split("\n")[:2]
    teile = zeile.split(";")
    teile[8] = ""                                                          # md_pfad fehlt
    arbeitsordner.protokoll.write_text(kopf + "\n" + ";".join(teile) + "\n", encoding="utf-8")
    monkeypatch.chdir(arbeitsordner.basis)
    assert p.rueckgaengig() == 1
    assert (arbeitsordner.eingang / "a.pdf").exists() and arbeitsordner.basis.is_dir()


def test_kurze_praesentation_ist_kein_scan(arbeitsordner, konverter, lauf):
    """Nur Titelfolie (unter 200 Zeichen): bei Office-Dateien gibt es keine Scans, also Fertig statt "kaum Text"."""
    from pptx import Presentation
    p_ = Presentation()
    p_.core_properties.title, p_.core_properties.author = "Kurzvortrag Lager", "Pia Vortrag"
    folie = p_.slides.add_slide(p_.slide_layouts[0])
    folie.shapes.title.text = "Wälzlager"
    folie.placeholders[1].text = "© 2024 Lehrstuhl"
    p_.save(arbeitsordner.eingang / "kurz.pptx")
    assert p.verarbeiten(arbeitsordner.eingang / "kurz.pptx", konverter, lauf).startswith("OK")
