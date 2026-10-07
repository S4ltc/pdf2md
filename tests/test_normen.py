"""Normen erkennen (normen.py) und im Ablauf verwenden: Nummer, Ausgabe, Titel von der Titelseite, Herausgeber,
Namenskuerzung und das Entfernen des Lizenz-Wasserzeichens."""

from pathlib import Path

import pytest

import normen
import pdf2md as p
from conftest import DEJAVU, FUELLTEXT

WASSERZEICHEN = ("Datum / Uhrzeit des Ausdrucks: 2020-01-01, 12:00:00 Firmenname: Hochschule Beispiel "
                 "Benutzername: Musternutzer Printed copies are uncontrolled")


class TestNummer:
    @pytest.mark.parametrize("zeile, erwartet", [
        ("DIN EN ISO 12345:2023-07", (False, "DIN EN ISO 12345", "2023", "07")),
        ("E DIN EN ISO 23456-1:2021-09", (True, "DIN EN ISO 23456-1", "2021", "09")),
        ("DIN_EN_34567-2:2019-10", (False, "DIN EN 34567-2", "2019", "10")),
        ("DIN EN 4567-1-8/A1:2026-05", (False, "DIN EN 4567-1-8/A1", "2026", "05")),
        ("DIN SPEC 91345:2016-04 ", (False, "DIN SPEC 91345", "2016", "04")),
        ("VDI 2230 Blatt 1:2015-11", (False, "VDI 2230 Blatt 1", "2015", "11")),
    ])
    def test_kopfzeile(self, zeile, erwartet):
        assert normen._schluessel(normen.KOPFZEILE.fullmatch(zeile)) == erwartet

    @pytest.mark.parametrize("zeile", ["DIN EN ISO 12345", "Siehe DIN EN ISO 12345:2023-07", "ISO 9001:2015",
                                       "Kapitel 3:2019-10"])
    def test_keine_kopfzeile(self, zeile):
        assert normen.KOPFZEILE.fullmatch(zeile) is None

    def test_herausgeber(self):
        assert [normen.herausgeber(n) for n in ("DIN EN ISO 12345", "VDI 2230 Blatt 1", "ISO/IEC 27001")] == \
            ["DIN", "VDI", "ISO"]


def seiten(kopf="DIN EN ISO 12345:2023-07", anzahl=6):
    return ["DEUTSCHE NORM Juli 2023\nDIN EN ISO 12345\nKlebtechnik"] + \
           [f"{kopf}\n{i}\nText der Seite {i}." for i in range(2, anzahl + 1)]


class TestErkennen:
    def test_kopfzeile(self, tmp_path):
        norm = normen.erkennen(tmp_path / "x.pdf", seiten())
        assert (norm["bezeichnung"], norm["ausgabe"], norm["herausgeber"], norm["quelle"]) == \
            ("DIN EN ISO 12345", "2023-07", "DIN", "Kopfzeile der Norm")

    def test_entwurf(self, tmp_path):
        norm = normen.erkennen(tmp_path / "x.pdf", seiten("E DIN 9876:2026-09"))
        assert norm["entwurf"] and norm["bezeichnung"] == "E DIN 9876"

    def test_kopfzeile_nur_auf_den_nationalen_vorseiten(self, tmp_path):
        """DIN-EN-Normen: die DIN-Kopfzeile steht nur auf Seite 2 und 3, danach kommt die EN-Kopfzeile."""
        s = seiten(anzahl=3) + [f"EN ISO 12345:2023 (D)\n{i}\nText." for i in range(4, 40)]
        assert normen.erkennen(tmp_path / "x.pdf", s)["ausgabe"] == "2023-07"

    def test_ref_nr_auf_der_titelseite(self, tmp_path):
        s = ["DEUTSCHE NORM Februar 2001\nKlebtechnik\nRef.-Nr. DIN EN 5678-4:2001-02", "Text", "Text"]
        norm = normen.erkennen(tmp_path / "x.pdf", s)
        assert (norm["bezeichnung"], norm["ausgabe"]) == ("DIN EN 5678-4", "2001-02")

    def test_dateiname_des_downloads(self, tmp_path):
        norm = normen.erkennen(tmp_path / "DIN EN ISO 24680-6_2007-01-00_DE_2345678.pdf", ["Text"] * 5)
        assert (norm["bezeichnung"], norm["ausgabe"], norm["quelle"]) == \
            ("DIN EN ISO 24680-6", "2007-01", "Dateiname (Normen-Download)")

    def test_lesezeichen(self, tmp_path):
        norm = normen.erkennen(tmp_path / "x.pdf", ["Text"] * 5, {0: [(0, "DIN_EN_34567-2:2019-10")]})
        assert norm["bezeichnung"] == "DIN EN 34567-2"

    def test_buch_ist_keine_norm(self, tmp_path):
        """Ein Buch, das Normen zitiert, ist keine Norm (die Nummer steht im Text, nicht als Kopfzeile)."""
        s = [f"Kapitel {i}\nNach DIN EN ISO 12345:2023-07 gilt ...\nMehr Text" for i in range(30)]
        s[5] = "DIN EN ISO 12345:2023-07\n" + s[5]                   # einmal zufaellig oben auf einer Seite
        assert normen.erkennen(tmp_path / "Buch - Autor - 2020.pdf", s) is None


class TestTitel:
    def test_zusammensetzen_mit_strichen(self):
        zeilen = ["Klebtechnik –", "Klebverbindungen an Holz, Glas, Keramik und deren",
                  "Verbundstoffen (ohne Schaumstoffe) –", "Einstufung von Fehlstellen (ISO 12345:2023);"]
        assert normen._zusammensetzen(zeilen) == ("Klebtechnik – Klebverbindungen an Holz, Glas, Keramik und "
                                                  "deren Verbundstoffen (ohne Schaumstoffe) – Einstufung von "
                                                  "Fehlstellen")

    def test_zusammensetzen_alte_titelseite(self):
        """Aeltere Titelseiten setzen jeden Titelteil ohne Strich auf eine eigene Zeile."""
        zeilen = ["Klebtechnik", "Hinweise zum Kleben von Bauteilen",
                  "Teil 4: Kleben von Holz und", "Holzwerkstoffen"]
        assert normen._zusammensetzen(zeilen) == ("Klebtechnik – Hinweise zum Kleben von Bauteilen – "
                                                  "Teil 4: Kleben von Holz und Holzwerkstoffen")

    def test_titelseite_mit_nummernzeile(self):
        zeilen = [("DEUTSCHE NORM Juli 2023", 10.0), ("www.din.de", 7.0), ("DIN EN ISO 12345 D", 14.0),
                  ("Klebtechnik –", 14.0), ("Einstufung (ISO 12345:2023);", 14.0),
                  ("Deutsche Fassung EN ISO 12345:2023", 14.0), ("Welding –", 12.0)]
        assert normen._titel_aus_seite(zeilen, "DIN EN ISO 12345") == "Klebtechnik – Einstufung"

    def test_entwurf_mit_zwischenzeilen(self):
        """Beim Entwurf stehen zwischen Nummer und Titel kleinere Zeilen (ICS, Einsprueche, Ersatz)."""
        zeilen = [("DEUTSCHE NORM Entwurf September 2026", 10.0), ("DIN 9876", 14.0), ("ICS 01.110", 10.0),
                  ("Vorgesehen als Ersatz für", 10.0), ("Technische Dokumentation (TD) –", 14.0),
                  ("Allgemeine Angaben", 14.0), ("Technical documentation (TD) –", 12.0)]
        assert normen._titel_aus_seite(zeilen, "DIN 9876") == \
            "Technische Dokumentation (TD) – Allgemeine Angaben"

    def test_deutsche_und_englische_fassung(self):
        zeilen = [("DIN EN ISO 24680-1", 14.0), ("Verfahrensprüfung –", 14.0),
                  ("Teil 1: Kleben", 14.0), ("(ISO/DIS 24680-1:2025);", 14.0),
                  ("Deutsche und Englische Fassung prEN ISO 24680-1:2025", 14.0)]
        assert normen._titel_aus_seite(zeilen, "DIN EN ISO 24680-1") == \
            "Verfahrensprüfung – Teil 1: Kleben"

    def test_alte_titelseite_ohne_nummernzeile(self):
        zeilen = [("DEUTSCHE NORM Oktober 2003", 10.0), ("Klebtechnik", 9.0), ("Hinweise zum Kleben", 13.0),
                  ("Teil 5: Kleben von beschichteten Blechen", 10.0), ("Deutsche Fassung EN 5678-5:2003", 10.0)]
        assert normen._titel_aus_seite(zeilen, "DIN EN 5678-5") == \
            "Klebtechnik – Hinweise zum Kleben – Teil 5: Kleben von beschichteten Blechen"

    def test_vollstaendiger_titel(self):
        assert normen.vollstaendiger_titel({"bezeichnung": "E DIN 9876", "titel": "Allgemeine Angaben"}) == \
            "E DIN 9876 – Allgemeine Angaben"
        assert normen.vollstaendiger_titel({"bezeichnung": "DIN 9876", "titel": None}) == "DIN 9876"


class TestName:
    def test_mittlere_teile_fallen_weg(self):
        titel = ("DIN EN ISO 12345 – Klebtechnik – Klebverbindungen an Holz, Glas, Keramik und deren "
                 "Verbundstoffen (ohne Schaumstoffe) – Einstufung von Fehlstellen")
        assert p.neuer_name(titel, "DIN", "2023") == \
            "DIN EN ISO 12345 – Klebtechnik – Einstufung von Fehlstellen - DIN - 2023"

    def test_teil_bleibt_beim_titel(self):
        titel = ("DIN EN 34567-3 – Formteile aus Kunststoffen – Teil 3: Technische Lieferbedingungen "
                 "für spritzgegossene glasfaserverstärkte Formteile")
        name = p.neuer_name(titel, "DIN", "2019")
        assert name.startswith("DIN EN 34567-3 – Teil 3 – Technische Lieferbedingungen") and len(name) <= p.MAX_NAME_LEN

    def test_zu_langer_letzter_teil_wird_am_wortende_gekuerzt(self):
        titel = "E DIN EN ISO 24680-1 – Verfahrensprüfung – Teil 1: " + "Kleben von Kunststoffbauteilen " * 5
        name = p.neuer_name(titel, "DIN", "2025")
        assert name.startswith("E DIN EN ISO 24680-1 – Teil 1") and name.endswith("… - DIN - 2025")
        assert len(name) <= p.MAX_NAME_LEN

    def test_buecher_unveraendert(self):
        """Buchtitel ohne Normnummer: weiterhin erst den Untertitel weglassen."""
        titel = "Maschinenelemente – " + "Ein sehr langer Untertitel " * 5
        assert p.neuer_name(titel, "Anna", "2020") == "Maschinenelemente - Anna - 2020"


def erzeuge_norm(pfad: Path, metadaten_titel="CEN/TC 121", metadaten_autor="klar irene") -> Path:
    """Eine kleine Norm wie von DIN Media: Titelseite (Nummer und Titel 14 pt, Uebersetzung 12 pt), Kopfzeilen mit
    Nummer und Ausgabe, Wasserzeichen des Downloads mit Druckdatum auf jeder Seite, unbrauchbare PDF-Metadaten."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=str(DEJAVU))
    pdf.set_title(metadaten_titel)
    pdf.set_author(metadaten_autor)

    def zeile(text, groesse):
        pdf.set_font("DejaVu", size=groesse)
        pdf.multi_cell(0, groesse * 0.6, text, new_x="LMARGIN", new_y="NEXT")

    pdf.add_page()
    for text, groesse in [("DEUTSCHE NORM Mai 2024", 10), ("DIN EN ISO 9999", 14), ("Klebtechnik –", 14),
                          ("Prüfung von Testnähten (ISO 9999:2024);", 14), ("Deutsche Fassung EN ISO 9999:2024", 14),
                          ("Welding –", 12), ("Testing of test welds (ISO 9999:2024);", 12), ("©", 7),
                          ("Ersatz für DIN EN ISO 9999:2014-06", 10), (WASSERZEICHEN, 7)]:
        zeile(text, groesse)
    for nr in (2, 3, 4):
        pdf.add_page()
        zeile("DIN EN ISO 9999:2024-05", 10)
        zeile(str(nr), 10)
        zeile(FUELLTEXT, 10)
        zeile(WASSERZEICHEN, 7)
    pdf.output(str(pfad))
    return pfad


class TestAblauf:
    def test_titel_von_der_titelseite(self, tmp_path):
        assert normen.titel_lesen(erzeuge_norm(tmp_path / "n.pdf"), "DIN EN ISO 9999") == \
            "Klebtechnik – Prüfung von Testnähten"

    def test_norm_landet_richtig_benannt_in_fertig(self, arbeitsordner, konverter, lauf):
        datei = erzeuge_norm(arbeitsordner.eingang / "download.pdf")
        meldung = p.verarbeiten(datei, konverter, lauf)
        assert meldung.startswith("OK")
        name = "DIN EN ISO 9999 – Klebtechnik – Prüfung von Testnähten - DIN - 2024"
        assert (arbeitsordner.fertig / f"{name}.pdf").exists()
        werte, text = p.kopf_lesen((arbeitsordner.fertig / f"{name}.md").read_text(encoding="utf-8"))
        assert werte["norm"] == "DIN EN ISO 9999:2024-05" and werte["jahr"] == "2024"   # nicht 2026 (Druckdatum)
        assert werte["autor"] == "DIN" and werte["titel_quelle"] == "Titelseite der Norm"
        assert "Uhrzeit des Ausdrucks" not in text and "Hochschule Beispiel" not in text

    def test_abschaltbar(self, arbeitsordner, konverter, lauf, monkeypatch):
        monkeypatch.setattr(p, "NORMEN_ERKENNEN", False)
        datei = erzeuge_norm(arbeitsordner.eingang / "download.pdf")
        p.verarbeiten(datei, konverter, lauf)
        werte, _ = p.kopf_lesen(next(arbeitsordner.fertig.glob("*.md")).read_text(encoding="utf-8"))
        assert werte["titel"] == "CEN/TC 121" and "norm" not in werte


class TestWasserzeichen:
    def test_ganze_zeile(self):
        assert "Ausdrucks" not in p.seiten_zu_text([f"Text oben\n{WASSERZEICHEN}"])

    @pytest.mark.parametrize("vermerk", [
        " " + "0123456789ABCDEF" * 5,                    # Kennung des Lizenznehmers (Hex, erfunden)
        "Normen-Ticker - Beispiel GmbH - Kd.-Nr.1234567 - Abo-Nr.00000000/000/000 - 2020-01-01 12:00:00",
        "A&I-Normenabonnement - Beispiel - Kd.-Nr.7654321 - Abo-Nr.00000000/000/000 - 2020-01-01 12:00:00",
    ])
    def test_kunden_und_abovermerke(self, vermerk):
        """Kunden-/Abonummern und Lizenzkennungen sind persoenliche Daten des Lizenznehmers: nie in die .md."""
        text = p.seiten_zu_text([f"Text oben\n{vermerk}\nText unten"])
        assert "Text oben" in text and "Text unten" in text
        assert not any(w in text for w in ("0123456789ABCDEF", "Kd.-Nr", "Abo-Nr", "Normen-Ticker", "abonnement"))

    def test_an_text_angehaengt(self):
        text = p.seiten_zu_text([f"Es ist empfehlens{WASSERZEICHEN}\nweiter"])
        assert "empfehlens" in text and "Ausdrucks" not in text and "weiter" in text

    def test_ueber_zeilen_umbrochen(self):
        """Das Wasserzeichen kann auf drei Zeilen verteilt sein (Datum / Firmenname ... Benutzername / Printed ...)."""
        seiten = ["Text oben\nDatum / Uhrzeit des Ausdrucks: 2020-01-01, 12:00:00\nFirmenname: Hochschule Beispiel "
                  "Benutzername: Musternutzer\nPrinted copies are uncontrolled\nText unten",
                  "Text oben\nDatum / Uhrzeit des Ausdrucks: 2020-01-01, 12:00:00 Firmenname: Hochschule Beispiel\n"
                  "Benutzername: Musternutzer Printed copies are uncontrolled\nText unten"]
        for seite in seiten:
            text = p.seiten_zu_text([seite])
            assert "Text oben" in text and "Text unten" in text
            assert not any(w in text for w in ("Ausdrucks", "Firmenname", "Benutzername", "Printed copies"))
        assert "Benutzername: admin" in p.seiten_zu_text(["Anmeldung mit Benutzername: admin\nText"])

    def test_leerseiten(self):
        """"— Leerseite —" und "This page is intentionally blank." machen eine Seite nicht zur Textseite."""
        text = p.seiten_zu_text(["Text der ersten Seite", "This page is intentionally blank.\n Leerseite ",
                                 "— Leerseite —", "Die Leerseite im Satz bleibt stehen."])
        assert len(p.SEITENMARKER_MUSTER.findall(text)) == 2 and "Die Leerseite im Satz" in text and "intentionally" not in text

    def test_lange_kopfzeile_auf_jeder_seite(self):
        """Wiederholte lange Zeilen (hier 150 Zeichen) sind Kopf-/Fusszeilen, auch in kurzen Dokumenten."""
        lang = "Nur zur internen Verwendung, Lizenz fuer Beispiel GmbH, Kunde 4711, " * 2
        text = p.seiten_zu_text([f"{wort} steht auf dieser Seite\nund noch mehr\n{lang}"
                                 for wort in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon")])
        assert lang.strip() not in text and "Gamma steht" in text


class TestDeckblatt:
    @pytest.mark.parametrize("strichcode", ['!&&Y8"', "|ϕCQϕ\ufffd", "!%&'t\"", '!&+ZI"'])
    def test_strichcode_vor_der_dokumentnummer(self, strichcode):
        text = p.seiten_zu_text([f"ICS 77.140.10\n{strichcode}\n3035421\nwww.din.de"])
        assert strichcode not in text and "3035421" in text

    def test_normale_zeile_vor_einer_zahl_bleibt(self):
        assert "Seite" in p.seiten_zu_text(["ICS 77.140.10\nSeite\n3035421"])
