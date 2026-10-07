"""Der ganze Ablauf mit echten Dateien: Fertig/Pruefen, Nachbessern, Rueckgaengig, Namen reparieren,
Text erneuern, Protokoll. Alles in einem temporaeren Arbeitsordner (siehe conftest.arbeitsordner)."""

import csv
import re

import pdf2md as p
from conftest import FUELLTEXT, erzeuge_buch, erzeuge_docx, erzeuge_epub, erzeuge_pdf


def kopf_von(md):
    werte, text = p.kopf_lesen(md.read_text(encoding="utf-8"))
    return werte, text


def protokoll(ordner):
    with open(ordner.protokoll, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


class TestVerarbeiten:
    def test_vollstaendiges_buch_landet_in_fertig(self, arbeitsordner, konverter, lauf):
        datei = erzeuge_buch(arbeitsordner.eingang / "quelle.pdf")
        meldung = p.verarbeiten(datei, konverter, lauf)
        assert meldung.startswith("OK")
        name = "Testbuch - Anna Beispiel - 2019"
        assert (arbeitsordner.fertig / f"{name}.pdf").is_file() and (arbeitsordner.fertig / f"{name}.md").is_file()
        assert not datei.exists()                                               # das Original wurde verschoben
        werte, text = kopf_von(arbeitsordner.fertig / f"{name}.md")
        assert (werte["titel"], werte["autor"], werte["jahr"]) == ("Testbuch", "Anna Beispiel", "2019")
        assert werte["jahr_quelle"] == "Copyright-/Erscheinungsvermerk im Text"
        assert werte["originaldatei"] == "quelle.pdf"
        assert "Dies ist ein Absatz" in text

    def test_fehlende_angaben_gehen_nach_pruefen_mit_originalname(self, arbeitsordner, konverter, lauf):
        datei = erzeuge_pdf(arbeitsordner.eingang / "namenlos.pdf", ["x", FUELLTEXT])
        assert p.verarbeiten(datei, konverter, lauf).startswith("PRÜFEN")
        assert (arbeitsordner.pruefen / "namenlos.pdf").is_file()
        werte, _ = kopf_von(arbeitsordner.pruefen / "namenlos.md")
        assert "Titel fehlt" in werte["pruefen"] and "Jahr fehlt" in werte["pruefen"]

    def test_scan_ohne_text_wird_erkannt(self, arbeitsordner, konverter, lauf):
        datei = erzeuge_pdf(arbeitsordner.eingang / "scan.pdf", [""] * 20, titel="Scan", autor="Anna")
        assert "kaum Text" in p.verarbeiten(datei, konverter, lauf)
        assert (arbeitsordner.pruefen / "scan.pdf").is_file()

    def test_gleicher_name_bekommt_zaehler(self, arbeitsordner, konverter, lauf):
        for n in (1, 2):
            p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / f"q{n}.pdf"), konverter, lauf)
        assert (arbeitsordner.fertig / "Testbuch - Anna Beispiel - 2019.pdf").is_file()
        assert (arbeitsordner.fertig / "Testbuch - Anna Beispiel - 2019 (2).pdf").is_file()

    def test_langer_titel_behaelt_autor_und_jahr_im_dateinamen(self, arbeitsordner, konverter, lauf):
        titel = ("Ein sehr langer Haupttitel: " + "mit vielen Woertern im Untertitel " * 6).strip()
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf", titel=titel), konverter, lauf)
        namen = [d.stem for d in arbeitsordner.fertig.glob("*.md")]
        assert len(namen) == 1 and namen[0].endswith(" - Anna Beispiel - 2019") and len(namen[0]) <= p.MAX_NAME_LEN
        werte, _ = kopf_von(arbeitsordner.fertig / f"{namen[0]}.md")
        assert werte["titel"] == titel                                          # voller Titel bleibt im Kopfblock

    def test_docx_und_epub(self, arbeitsordner, konverter, lauf):
        docx = erzeuge_docx(arbeitsordner.eingang / "d.docx", titel="Handbuch", autor="Clara Zahl",
                            text="© 2021 Verlag. " + FUELLTEXT)
        epub = erzeuge_epub(arbeitsordner.eingang / "e.epub", "Der lange Weg", "Dora Dichter", "2018-05-01")
        assert p.verarbeiten(docx, konverter, lauf).startswith("OK")
        assert p.verarbeiten(epub, konverter, lauf).startswith("OK")
        assert (arbeitsordner.fertig / "Handbuch - Clara Zahl - 2021.docx").is_file()
        assert (arbeitsordner.fertig / "Der lange Weg - Dora Dichter - 2018.epub").is_file()

    def test_protokoll_wird_geschrieben(self, arbeitsordner, konverter, lauf):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        zeile, = protokoll(arbeitsordner)
        assert zeile["status"] == "OK" and zeile["original_name"] == "q.pdf" and zeile["jahr"] == "2019"

    def test_md_hat_lf_zeilenenden_und_seitenmarker(self, arbeitsordner, konverter, lauf):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        roh = next(arbeitsordner.fertig.glob("*.md")).read_bytes()
        assert b"\r" not in roh and re.search(rb"<!-- (?:PDF-Seite 2|Seite \S+ \(PDF 2\)) -->", roh)

    def test_markitdown_engine_als_rueckfall(self, arbeitsordner, konverter, lauf, monkeypatch):
        monkeypatch.setattr(p, "PDF_ENGINE", "markitdown")
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        werte, _ = kopf_von(next(arbeitsordner.fertig.glob("*.md")))
        assert werte["textquelle"] == "MarkItDown"


class TestSammeln:
    def test_nur_unterstuetzte_formate_und_keine_office_sperrdateien(self, tmp_path):
        for name in ("a.pdf", "b.docx", "c.epub", "d.txt", "~$e.docx", ".versteckt.pdf", "f.doc"):
            (tmp_path / name).write_bytes(b"x")
        assert [d.name for d in p.dateien_sammeln([tmp_path])] == ["a.pdf", "b.docx", "c.epub"]

    def test_einzelne_datei_und_unbekanntes(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x")
        (tmp_path / "b.xyz").write_bytes(b"x")
        assert p.dateien_sammeln([tmp_path / "a.pdf", tmp_path / "b.xyz"]) == [tmp_path / "a.pdf"]


class TestNachbessern:
    def vorbereiten(self, ordner, konverter, lauf):
        datei = erzeuge_pdf(ordner.eingang / "roh.pdf", ["Titelseite", FUELLTEXT], titel="Microsoft Word - Dokument1",
                            autor="Max Muster")
        p.verarbeiten(datei, konverter, lauf)
        return ordner.pruefen / "roh.md"

    def bearbeite(self, md, **ersetzungen):
        text = md.read_text(encoding="utf-8")
        for alt, neu in ersetzungen.items():
            assert alt in text
            text = text.replace(alt, neu)
        md.write_text(text, encoding="utf-8")

    def test_vollstaendig_ausgefuellt_wandert_nach_fertig(self, arbeitsordner, konverter, lauf):
        md = self.vorbereiten(arbeitsordner, konverter, lauf)
        self.bearbeite(md, **{"titel: null": "titel: Mein Buch: mit Untertitel", "jahr: null": "jahr: 2015"})
        assert p.nachbessern(lauf) == 1
        name = "Mein Buch – mit Untertitel - Max Muster - 2015"
        assert (arbeitsordner.fertig / f"{name}.pdf").is_file() and (arbeitsordner.fertig / f"{name}.md").is_file()
        assert not md.exists() and not (arbeitsordner.pruefen / "roh.pdf").exists()
        werte, _ = kopf_von(arbeitsordner.fertig / f"{name}.md")
        assert "pruefen" not in werte and werte["titel_quelle"] == "manuell nachgetragen"

    def test_unvollstaendig_bleibt_liegen(self, arbeitsordner, konverter, lauf):
        md = self.vorbereiten(arbeitsordner, konverter, lauf)
        assert p.nachbessern(lauf) == 0 and md.exists()

    def test_ungueltiges_jahr_wird_abgelehnt(self, arbeitsordner, konverter, lauf):
        md = self.vorbereiten(arbeitsordner, konverter, lauf)
        self.bearbeite(md, **{"titel: null": "titel: Buch", "jahr: null": "jahr: abc"})
        assert p.nachbessern(lauf) == 0 and md.exists()

    def test_isbn_als_titel_wird_abgelehnt(self, arbeitsordner, konverter, lauf):
        md = self.vorbereiten(arbeitsordner, konverter, lauf)
        self.bearbeite(md, **{"titel: null": "titel: 978-3-000-00004-5", "jahr: null": "jahr: 2015"})
        assert p.nachbessern(lauf) == 0

    def test_scan_bleibt_bis_die_pruefzeile_geloescht_ist(self, arbeitsordner, konverter, lauf):
        datei = erzeuge_pdf(arbeitsordner.eingang / "scan.pdf", [""] * 20, titel="Scan", autor="Anna")
        p.verarbeiten(datei, konverter, lauf)
        md = arbeitsordner.pruefen / "scan.md"
        self.bearbeite(md, **{"jahr: null": "jahr: 2010"})
        assert p.nachbessern(lauf) == 0                                         # 'kaum Text' blockiert
        text = md.read_text(encoding="utf-8")
        md.write_text("\n".join(z for z in text.split("\n") if not z.startswith("pruefen:")), encoding="utf-8")
        assert p.nachbessern(lauf) == 1


class TestRueckgaengig:
    def zustand(self, ordner):
        return sorted(str(d.relative_to(ordner.basis)) for d in ordner.basis.rglob("*") if d.is_file()
                      and d.name != "Protokoll.csv" and d.suffix in (".pdf", ".md"))

    def test_letzten_lauf_zurueckdrehen(self, arbeitsordner, konverter, lauf):
        erzeuge_buch(arbeitsordner.eingang / "a.pdf")
        erzeuge_pdf(arbeitsordner.eingang / "b.pdf", ["x", FUELLTEXT])
        for datei in p.dateien_sammeln([arbeitsordner.eingang]):
            p.verarbeiten(datei, konverter, lauf)
        assert (arbeitsordner.fertig / "Testbuch - Anna Beispiel - 2019.pdf").exists()
        p.rueckgaengig()
        assert (arbeitsordner.eingang / "a.pdf").is_file() and (arbeitsordner.eingang / "b.pdf").is_file()
        assert not list(arbeitsordner.fertig.glob("*.pdf")) and not list(arbeitsordner.pruefen.glob("*.pdf"))
        assert p.rueckgaengig_plan() is None                                    # nichts mehr offen
        assert p.rueckgaengig() == 0

    def test_mehrere_laeufe_nacheinander(self, arbeitsordner, konverter):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "a.pdf"), konverter, "2026-01-01 10:00:00")
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "b.pdf", titel="Zweites"), konverter, "2026-01-01 11:00:00")
        p.rueckgaengig()                                                        # nur der juengere Lauf
        assert (arbeitsordner.eingang / "b.pdf").is_file() and not (arbeitsordner.eingang / "a.pdf").exists()
        p.rueckgaengig()
        assert (arbeitsordner.eingang / "a.pdf").is_file()

    def test_nach_nachbessern(self, arbeitsordner, konverter):
        datei = erzeuge_pdf(arbeitsordner.eingang / "roh.pdf", ["x", FUELLTEXT], titel="Microsoft Word - Dokument1",
                            autor="Max Muster")
        p.verarbeiten(datei, konverter, "2026-01-01 10:00:00")
        md = arbeitsordner.pruefen / "roh.md"
        md.write_text(md.read_text(encoding="utf-8").replace("titel: null", "titel: Buch").replace("jahr: null", "jahr: 2015"),
                      encoding="utf-8")
        p.nachbessern("2026-01-01 11:00:00")
        assert (arbeitsordner.fertig / "Buch - Max Muster - 2015.pdf").exists()
        p.rueckgaengig()                                                        # zurueck nach Pruefen mit altem Namen
        assert (arbeitsordner.pruefen / "roh.pdf").is_file() and (arbeitsordner.pruefen / "roh.md").is_file()


class TestNamenReparieren:
    def test_zerlegter_umlaut_gilt_als_gleicher_name(self, arbeitsordner):
        """macOS liefert Dateinamen oft zerlegt (NFD: "u" + Trema); der Kopfblock ist NFC. Ohne Normalisierung schlug
        "Namen reparieren" jedes Mal eine Umbenennung in den gleich aussehenden Namen vor."""
        import unicodedata
        arbeitsordner.fertig.mkdir(exist_ok=True)
        kopf = {"titel": "Prüftechnik", "autor": "Erika Muster", "jahr": "2023"}
        name = unicodedata.normalize("NFD", "Prüftechnik - Erika Muster - 2023")
        (arbeitsordner.fertig / f"{name}.md").write_text(p.kopf_schreiben(kopf) + "Text", encoding="utf-8")
        (arbeitsordner.fertig / f"{name}.pdf").write_bytes(b"pdf")
        assert p.namen_plan() == []

    def falsch_benanntes_paar(self, ordner):
        ordner.fertig.mkdir(exist_ok=True)
        kopf = {"titel": "Beispielelemente 1: Grundlagen der Berechnung", "autor": "Erika Muster", "jahr": "2023"}
        (ordner.fertig / "Mein Lieblingsbuch.md").write_text(p.kopf_schreiben(kopf) + "Text", encoding="utf-8")
        (ordner.fertig / "Mein Lieblingsbuch.pdf").write_bytes(b"pdf")

    def test_vorschau_aendert_nichts(self, arbeitsordner):
        self.falsch_benanntes_paar(arbeitsordner)
        plan = p.namen_plan()
        assert [(e["alt"], e["neu"]) for e in plan] == [
            ("Mein Lieblingsbuch", "Beispielelemente 1 – Grundlagen der Berechnung - Erika Muster - 2023")]
        assert (arbeitsordner.fertig / "Mein Lieblingsbuch.pdf").exists()

    def test_veralteter_plan_ueberspringt_verschwundene_dateien(self, arbeitsordner, lauf):
        self.falsch_benanntes_paar(arbeitsordner)
        plan = p.namen_plan()
        (arbeitsordner.fertig / "Mein Lieblingsbuch.pdf").unlink()             # zwischen Vorschau und Ausfuehren
        assert p.namen_reparieren(lauf, plan) == 0
        assert (arbeitsordner.fertig / "Mein Lieblingsbuch.md").exists()

    def test_umbenennen_und_zurueckdrehen(self, arbeitsordner, lauf):
        self.falsch_benanntes_paar(arbeitsordner)
        assert p.namen_reparieren(lauf) == 1
        neu = "Beispielelemente 1 – Grundlagen der Berechnung - Erika Muster - 2023"
        assert (arbeitsordner.fertig / f"{neu}.pdf").is_file() and (arbeitsordner.fertig / f"{neu}.md").is_file()
        assert not (arbeitsordner.fertig / "Mein Lieblingsbuch.pdf").exists()
        assert p.namen_plan() == []                                             # zweiter Lauf: nichts mehr zu tun
        p.rueckgaengig()
        assert (arbeitsordner.fertig / "Mein Lieblingsbuch.pdf").is_file() and (arbeitsordner.fertig / "Mein Lieblingsbuch.md").is_file()

    def test_md_ohne_original_und_ohne_angaben_bleiben_unberuehrt(self, arbeitsordner, lauf):
        arbeitsordner.fertig.mkdir()
        (arbeitsordner.fertig / "Verwaist.md").write_text(p.kopf_schreiben({"titel": "T", "autor": "A", "jahr": "2001"}) + "x")
        (arbeitsordner.fertig / "OhneJahr.md").write_text(p.kopf_schreiben({"titel": "T", "autor": "A", "jahr": None}) + "x")
        (arbeitsordner.fertig / "OhneJahr.pdf").write_bytes(b"x")
        assert p.namen_plan() == [] and p.namen_reparieren(lauf) == 0
        assert (arbeitsordner.fertig / "Verwaist.md").exists() and (arbeitsordner.fertig / "OhneJahr.pdf").exists()


class TestTextErneuern:
    def test_alte_md_wird_gesichert_und_der_kopfblock_bleibt(self, arbeitsordner, konverter, lauf):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        md = next(arbeitsordner.fertig.glob("*.md"))
        text = md.read_text(encoding="utf-8").replace("autor: \"Anna Beispiel\"", "autor: \"HAND GEAENDERT\"")
        md.write_text(text.replace(f'textquelle: "{p.erwartete_textquelle()}"', 'textquelle: "PDFium"'), encoding="utf-8")
        p.text_erneuern(lauf)
        assert (arbeitsordner.sicherung / md.name).is_file()
        werte, neuer_text = kopf_von(md)
        assert werte["autor"] == "HAND GEAENDERT"                               # Handeingaben bleiben
        assert werte["textquelle"] == p.erwartete_textquelle() and "text_erneuert_am" in werte
        assert "Dies ist ein Absatz" in neuer_text

    def test_quellenangabe_und_seitenhinweis_werden_ergaenzt(self, arbeitsordner, konverter, lauf):
        """Aeltere .md ohne Quellenangabe bekommen sie; eine von Hand eingetragene bleibt."""
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        md = next(arbeitsordner.fertig.glob("*.md"))
        werte, text = kopf_von(md)
        assert werte["quellenangabe"].startswith("A. Beispiel, *") and "zitierhinweis" in werte
        for feld in ("quellenangabe", "zitierdaten_quelle", "zitierhinweis", "seitenzahlen"):
            werte.pop(feld)
        werte["textquelle"] = "PDFium"
        md.write_text(p.kopf_schreiben(werte) + text, encoding="utf-8")
        p.text_erneuern(lauf)
        werte, _ = kopf_von(md)
        assert werte["quellenangabe"].startswith("A. Beispiel, *") and "zitierhinweis" in werte

        werte["quellenangabe"] = "VON HAND"
        werte["textquelle"] = "PDFium"
        md.write_text(p.kopf_schreiben(werte) + text, encoding="utf-8")
        p.text_erneuern(lauf)
        assert kopf_von(md)[0]["quellenangabe"] == "VON HAND"

    def test_bereits_aktuelle_buecher_werden_uebersprungen(self, arbeitsordner, konverter, lauf):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        assert p.text_plan() == [] and p.text_erneuern(lauf) == 0
        assert not arbeitsordner.sicherung.exists()

    def test_vorschau_aendert_nichts(self, arbeitsordner, konverter, lauf):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        md = next(arbeitsordner.fertig.glob("*.md"))
        md.write_text(md.read_text(encoding="utf-8").replace(f'textquelle: "{p.erwartete_textquelle()}"', 'textquelle: "PDFium"'),
                      encoding="utf-8")
        vorher = md.read_bytes()
        assert [e["name"] for e in p.text_plan()] == [md.stem]
        assert md.read_bytes() == vorher and not arbeitsordner.sicherung.exists()

    def test_abbruch_und_rueckmeldung_je_buch(self, arbeitsordner, konverter, lauf):
        for n in ("q", "r"):
            p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / f"{n}.pdf", titel=f"Buch {n}"), konverter, lauf)
        for md in arbeitsordner.fertig.glob("*.md"):
            md.write_text(md.read_text(encoding="utf-8").replace(f'textquelle: "{p.erwartete_textquelle()}"',
                                                                 'textquelle: "PDFium"'), encoding="utf-8")
        begonnen, fertig = [], []
        anzahl = p.text_erneuern(lauf, abbrechen=lambda: len(fertig) >= 1,
                                 datei_beginnt=lambda n, i, g: begonnen.append((i, g)),
                                 datei_fertig=lambda n, s: fertig.append(s))
        assert anzahl == 1 and begonnen == [(1, 2)] and fertig == ["TEXT_ERNEUERT"]


class TestRueckmeldung:
    def test_meldungen_und_fortschritt_gehen_an_den_callback(self, arbeitsordner, konverter, lauf, capsys):
        meldungen, schritte = [], []
        datei = erzeuge_buch(arbeitsordner.eingang / "a.pdf")
        status = p.verarbeiten(datei, konverter, lauf, melder=meldungen.append,
                               fortschritt=lambda *a: schritte.append(a))
        assert status.startswith("OK")
        assert capsys.readouterr().out == ""                                     # nichts mehr auf der Konsole
        assert ("Text lesen", 2, 2) in schritte                                  # letzte Seite gemeldet
        assert schritte[-1][0] == "Kopfblock"
        assert p._rueckmeldung == {"melder": None, "fortschritt": None}          # danach wieder Konsole

    def test_ohne_callback_bleibt_die_konsole(self, capsys):
        p.melden("Hallo")
        p.fortschritt_melden("Text lesen", 1, 2)                                 # ohne Ziel: nichts
        assert capsys.readouterr().out == "Hallo\n"


class TestEinstellungenImKopfblock:
    def test_abweichung_steht_im_kopfblock(self, arbeitsordner, konverter, lauf, monkeypatch):
        monkeypatch.setattr(p, "KOPF_FUSS_MIN_SEITEN", 6)
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "a.pdf"), konverter, lauf)
        werte, _ = kopf_von(next(arbeitsordner.fertig.glob("*.md")))
        assert "KOPF_FUSS_MIN_SEITEN=6" in werte["einstellungen"]

    def test_mit_standardwerten_kein_feld(self, monkeypatch):
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", True)                          # conftest schaltet beides ab
        monkeypatch.setattr(p, "FORMELN_REPARIEREN", True)
        kopf = {"seiten": 1, "einstellungen": "abweichend: alt"}
        p._verfahrensfelder(kopf, {"a": 0, "b": 0, "offen": 0, "ersetzt": 0})
        assert "einstellungen" not in kopf


class TestUebernahmePruefen:
    def test_gruende(self, tmp_path):
        md = tmp_path / "x.md"
        assert p.uebernahme_pruefen(None, md) == "kein Kopfblock"
        assert p.uebernahme_pruefen({"titel": "T", "autor": None, "jahr": None}, md) == "Autor fehlt; Jahr fehlt"
        assert p.uebernahme_pruefen({"titel": "T", "autor": "A", "jahr": "01"}, md) == "Jahr muss vierstellig sein"
        assert p.uebernahme_pruefen({"titel": "978-3-000-00007-6", "autor": "A", "jahr": "2001"}, md) \
            == "Titel ist eine ISBN"
        assert p.uebernahme_pruefen({"titel": "T", "autor": "A", "jahr": "2001",
                                     "pruefen": "kaum Text (vermutlich Scan)"}, md).startswith("kaum Text")
        assert p.uebernahme_pruefen({"titel": "T", "autor": "A", "jahr": "2001"}, md) == "Originaldatei fehlt"
        (tmp_path / "x.pdf").write_bytes(b"x")
        assert p.uebernahme_pruefen({"titel": "T", "autor": "A", "jahr": "2001"}, md) is None


class TestEingangVerarbeiten:
    def test_ganzer_lauf_mit_nachbessern(self, arbeitsordner):
        erzeuge_buch(arbeitsordner.eingang / "a.pdf")
        erzeuge_pdf(arbeitsordner.eingang / "b.pdf", ["x", FUELLTEXT])
        ergebnis = p.eingang_verarbeiten("2026-01-01 10:00:00", melder=lambda t: None)
        assert (ergebnis["ok"], ergebnis["pruefen"], ergebnis["fehler"], ergebnis["abgebrochen"]) == (1, 1, 0, False)
        md = arbeitsordner.pruefen / "b.md"
        md.write_text(md.read_text(encoding="utf-8").replace("titel: null", "titel: Buch")
                      .replace("jahr: null", "jahr: 2015").replace("autor: null", "autor: Max"), encoding="utf-8")
        assert p.eingang_verarbeiten("2026-01-01 11:00:00", melder=lambda t: None)["nachgebessert"] == 1

    def test_abbruch_nach_der_aktuellen_datei(self, arbeitsordner):
        for n in "abc":
            erzeuge_buch(arbeitsordner.eingang / f"{n}.pdf", titel=f"Buch {n}")
        fertig = []
        ergebnis = p.eingang_verarbeiten("2026-01-01 10:00:00", melder=lambda t: None,
                                         abbrechen=lambda: len(fertig) >= 1,
                                         datei_fertig=lambda name, status: fertig.append(name))
        assert fertig == ["a.pdf"] and ergebnis["abgebrochen"]
        assert sorted(d.name for d in arbeitsordner.eingang.glob("*.pdf")) == ["b.pdf", "c.pdf"]

    def test_fehlerhafte_datei_bleibt_im_eingang(self, arbeitsordner):
        (arbeitsordner.eingang / "kaputt.pdf").write_bytes(b"kein pdf")
        stati = []
        ergebnis = p.eingang_verarbeiten("2026-01-01 10:00:00", melder=lambda t: None,
                                         datei_fertig=lambda n, s: stati.append(s))
        assert ergebnis["fehler"] == 1 and stati[0].startswith("FEHLER")
        assert (arbeitsordner.eingang / "kaputt.pdf").exists()
        assert protokoll(arbeitsordner)[-1]["status"] == "FEHLER"


def test_tests_nutzen_nie_die_echte_ablage():
    """conftest.keine_echte_ablage: auch ohne Fixture arbeitsordner landet nichts neben pdf2md.py."""
    for pfad in (p.EINGANG, p.FERTIG, p.PRUEFEN, p.PROTOKOLL, p.SICHERUNG):
        assert p.BASE_DIR not in pfad.parents


class TestZitierstilWechsel:
    def test_text_erneuern_setzt_die_quellenangabe_im_neuen_stil(self, arbeitsordner, konverter, lauf, monkeypatch):
        p.verarbeiten(erzeuge_buch(arbeitsordner.eingang / "q.pdf"), konverter, lauf)
        md = next(arbeitsordner.fertig.glob("*.md"))
        assert kopf_von(md)[0]["zitierstil"] == "IEEE" and p.text_plan() == []
        monkeypatch.setattr(p, "ZITIERSTIL", "apa")
        assert [e["name"] for e in p.text_plan()] == [md.stem]            # Text aktuell, aber anderer Stil
        p.text_erneuern(lauf)
        werte, _ = kopf_von(md)
        assert werte["quellenangabe"] == "Beispiel, A. (2019). *Testbuch*." and werte["zitierstil"] == "APA 7"
        assert "(Autor, Jahr, S. S)" in werte["zitierhinweis"]


class TestLiteraturliste:
    def schreibe(self, ordner, name, kopf):
        ordner.fertig.mkdir(exist_ok=True)
        (ordner.fertig / f"{name}.md").write_text(p.kopf_schreiben(kopf) + "Text", encoding="utf-8")

    def test_aus_kopfblock_und_bibtex_feld(self, arbeitsordner):
        self.schreibe(arbeitsordner, "A", {"titel": "Beispielkunde", "autor": "Hans Muster", "jahr": "2016",
                                           "verlag": "Springer Vieweg", "ort": "Berlin", "auflage": "3"})
        self.schreibe(arbeitsordner, "B", {"titel": "x", "autor": "y", "jahr": "2020",
                                           "bibtex": "@book{fertig2020, title = {{Schon da}}}"})
        self.schreibe(arbeitsordner, "C", {"titel": "DIN EN ISO 12345 – Klebtechnik – Teil", "autor": "DIN",
                                           "jahr": "2023", "norm": "DIN EN ISO 12345:2023-07"})
        plan = p.literatur_plan()
        assert [(e["name"], e["schluessel"]) for e in plan] == [
            ("A", "muster2016beispielkunde"), ("B", "fertig2020"), ("C", "din12345_2023")]
        ziel = p.literatur_schreiben(plan)
        assert ziel == arbeitsordner.basis / "Literatur.bib"
        inhalt = ziel.read_text(encoding="utf-8")
        assert "@book{muster2016beispielkunde, author = {Muster, Hans}, title = {{Beispielkunde}}, edition = {3}" in inhalt
        assert "@book{fertig2020, title = {{Schon da}}}" in inhalt
        assert "@standard{din12345_2023, title = {{Klebtechnik – Teil}}, number = {DIN EN ISO 12345:2023-07}" in inhalt

    def test_gleiche_schluessel_werden_eindeutig(self, arbeitsordner):
        for name in ("A", "B", "C"):
            self.schreibe(arbeitsordner, name, {"titel": "Beispielkunde", "autor": "Hans Muster", "jahr": "2016"})
        assert [e["schluessel"] for e in p.literatur_plan()] == [
            "muster2016beispielkunde", "muster2016beispielkundeb", "muster2016beispielkundec"]
        inhalt = p.literatur_schreiben(p.literatur_plan()).read_text(encoding="utf-8")
        assert "@book{muster2016beispielkundec, " in inhalt

    def test_leer_und_unvollstaendig(self, arbeitsordner):
        assert p.literatur_plan() == []
        self.schreibe(arbeitsordner, "D", {"titel": None, "autor": "Hans Muster", "jahr": "2016"})
        assert p.literatur_plan() == []

