"""Auswertung: Kennzahlen aus Protokoll.csv und Kopfbloecken (reine Funktionen, keine Dateien)."""
import pytest

import auswertung as A

KOPFZEILE = ("\ufefflauf;zeit;status;original_name;neuer_name;ordner;von_pfad;nach_pfad;md_pfad;titel;autor;jahr;"
             "titel_quelle;autor_quelle;jahr_quelle;kennung;hinweis\n")
PROTOKOLL = (KOPFZEILE +
             "2026-09-20 13:00:00;2026-09-20 13:01:00;OK;a.pdf;A - X - 2020;Fertig;;;C:\\F\\A - X - 2020.md;;;;;;;;\n"
             "2026-09-20 13:00:00;2026-09-20 13:03:00;PRÜFEN;b.pdf;b;Prüfen;;;C:\\P\\b.md;;;;;;;;Jahr fehlt\n"
             "2026-09-20 13:00:00;2026-09-20 13:03:01;NACHGEBESSERT;c.pdf;C - Y - 2001;Fertig;;;;;;;;;;;\n"
             "2026-09-21 09:00:00;2026-09-21 09:00:30;TEXT_ERNEUERT;a.pdf;A - X - 2020;Fertig;;;;;;;;;;;\n"
             "2026-09-22 10:00:00;2026-09-22 10:00:01;UMBENANNT;a.pdf;A neu;Fertig;;;;;;;;;;;\n")


def zeilen():
    return A.protokoll_lesen(PROTOKOLL)


def test_protokoll_lesen_mit_bom_und_leerem_text():
    assert zeilen()[0]["lauf"] == "2026-09-20 13:00:00" and len(zeilen()) == 5
    assert A.protokoll_lesen("") == []


def test_laeufe_dauer_und_seiten_pro_minute():
    l = A.laeufe(zeilen(), {"A - X - 2020": 120, "b": 60})
    assert [(x["art"], x["dateien"], x["ok"], x["pruefen"], x["nachgebessert"]) for x in l] == [
        ("Umwandlung", 2, 1, 1, 1), ("Text erneuert", 1, 1, 0, 0), ("Umbenannt", 1, 0, 0, 0)]
    assert l[0]["dauer_s"] == 180 and l[0]["seiten"] == 180 and l[0]["seiten_pro_min"] == 60.0
    assert l[1]["dauer_s"] == 30 and l[1]["seiten_pro_min"] == 240.0
    assert l[2]["dauer_s"] is None and l[2]["seiten_pro_min"] is None


def test_unplausible_dauer_gilt_als_unbekannt():
    text = KOPFZEILE + "2026-09-20 13:00:00;2026-09-21 13:00:00;OK;a.pdf;A;Fertig;;;;;;;;;;;\n"
    assert A.laeufe(A.protokoll_lesen(text), {"A": 10})[0]["dauer_s"] is None
    assert A.dauern(A.protokoll_lesen(text), {"A": 10})[0]["dauer_s"] is None


def test_dauern_je_datei():
    d = A.dauern(zeilen(), {"A - X - 2020": 120})
    assert [(x["name"], x["dauer_s"], x["seiten"]) for x in d] == [
        ("A - X - 2020", 60, 120), ("b", 120, None), ("A - X - 2020", 30, 120)]


def test_dauern_findet_seiten_auch_ueber_den_originalnamen():
    """Nach dem Nachbessern heisst die .md anders als im Protokoll der Umwandlung."""
    assert A.dauern(zeilen(), {"b.pdf": 60})[1]["seiten"] == 60


KOPF = {"seiten": 3, "titel": "T", "titel_quelle": "Crossref (über ISBN/DOI)", "autor": "X",
        "autor_quelle": "PDF-Metadaten", "jahr": "2020", "jahr_quelle": "Copyright-/Erscheinungsvermerk im Text",
        "quellenangabe": "A. X, *T*. Berlin: S, 2020.", "zitierdaten_quelle": "DNB (über DOI/ISBN)",
        "formelreparatur": "2 Zeichenarten per Glyphname, 1 per Formvergleich, 0 unsicher (14 Zeichen ersetzt)",
        "tabellen": "4 Tabellen mit Gitterlinien als Markdown-Tabellen übernommen",
        "lesezeichen": "9 Überschriften (8 direkt im Text gefunden, den Rest am Seitenanfang eingefügt)",
        "spalten": "5 zweispaltige Seiten in Lesereihenfolge gebracht (im PDF steht der Text in anderer Reihenfolge)",
        "formelsatz": "12 Hoch-/Tiefstellungen, 3 Formelteile (Brüche, Wurzeln, Summen) als LaTeX",
        "originaldatei": "a.pdf", "textquelle": "PDFium + Seitenzahlen"}
TEXT = ("<!-- PDF-Seite 1 -->\nx\n<!-- Seite 1 (PDF 2) -->\n⚠[Formel unsicher] $a\ufffd$\n"
        "<!-- Seite 2 (PDF 3) -->\n\ufffd y")


def test_buchkennzahlen_aus_kopf_und_text():
    k = A.buchkennzahlen(KOPF, TEXT, "PDFium + Seitenzahlen")
    assert (k["seiten"], k["gedruckt"], k["nur_pdf"], k["fragezeichen"], k["unsicher"]) == (3, 2, 1, 2, 1)
    assert (k["formelzeichen"], k["tabellen"], k["ueberschriften"], k["spaltenseiten"]) == (14, 4, 9, 5)
    assert (k["hochtief"], k["formelteile"], k["ieee"], k["format"], k["aktuell"]) == (12, 3, True, "PDF", True)
    assert k["quellen"] == {"titel": "Crossref", "autor": "PDF-Metadaten", "jahr": "Text"}
    assert k["pruefen"] is None and k["norm"] is False


def test_buchkennzahlen_alter_kopfblock():
    k = A.buchkennzahlen({"seiten": "10", "titel": "T", "titel_quelle": "PDF-Metadaten", "autor": None,
                          "originaldatei": "b.epub", "pruefen": "Autor fehlt"}, "<!-- Seite 1 -->\nText",
                         "PDFium + Seitenzahlen")
    assert (k["seiten"], k["gedruckt"], k["nur_pdf"], k["tabellen"], k["ieee"], k["aktuell"]) == (10, 0, 0, 0, False, False)
    assert k["quellen"] == {"titel": "PDF-Metadaten", "autor": "fehlt", "jahr": "fehlt"}
    assert (k["format"], k["pruefen"]) == ("EPUB", "Autor fehlt")


def test_ieee_nur_mit_online_daten_oder_bei_normen():
    ohne = dict(KOPF, zitierdaten_quelle="nur Titel, Autor und Jahr (ohne Online-Abgleich, Verlag und Ort fehlen)")
    assert A.buchkennzahlen(ohne, "")["ieee"] is False
    norm = {"quellenangabe": "*T*, DIN 1:2020-01, 2020.", "norm": "DIN 1:2020-01", "originaldatei": "n.pdf"}
    assert A.buchkennzahlen(norm, "")["ieee"] is True and A.buchkennzahlen(norm, "")["norm"] is True


@pytest.mark.parametrize("quelle, kategorie", [
    ("Crossref (über ISBN/DOI)", "Crossref"), ("PDF-Metadaten", "PDF-Metadaten"),
    ("Copyright-/Erscheinungsvermerk im Text", "Text"), ("Titelseite der Norm", "Norm"),
    ("Normnummer (Kopfzeile)", "Norm"), ("Ausgabe 2023-07 (Kopfzeile)", "Norm"), ("Herausgeber der Norm", "Norm"),
    ("manuell nachgetragen", "von Hand"), ("EPUB-Metadaten", "Dokument"), ("Dokument-Eigenschaften", "Dokument"),
    ("HTML-Titel", "Dokument"), ("Erstellungsdatum (unsicher)", "Dokument"), (None, "fehlt"), ("", "fehlt"),
    ("etwas anderes", "Dokument")])
def test_quellen_kategorie(quelle, kategorie):
    assert A.quellen_kategorie(quelle) == kategorie


def buecher():
    return [A.buchkennzahlen(KOPF, TEXT, "PDFium + Seitenzahlen") | {"name": "eins"},
            A.buchkennzahlen({"seiten": 100, "titel": "T", "titel_quelle": "manuell nachgetragen",
                              "autor": "A", "autor_quelle": "PDF-Metadaten", "jahr": None,
                              "originaldatei": "x.pdf", "pruefen": "Jahr fehlt; kaum Text (vermutlich Scan)"},
                             "<!-- PDF-Seite 1 -->\n<!-- PDF-Seite 2 -->\n\ufffd\ufffd") | {"name": "zwei"},
            A.buchkennzahlen({"seiten": 10, "titel": "T", "titel_quelle": "Crossref (über ISBN/DOI)",
                              "originaldatei": "y.docx", "pruefen": "Jahr fehlt"}, "") | {"name": "drei"}]


def test_herkunft_gestapelt_je_feld():
    h = A.herkunft(buecher())
    assert h["titel"] == {"Crossref": 2, "von Hand": 1}
    assert h["autor"] == {"PDF-Metadaten": 2, "fehlt": 1}
    assert h["jahr"] == {"Text": 1, "fehlt": 2}
    assert list(h["titel"]) == ["Crossref", "von Hand"]                     # feste Reihenfolge der Kategorien


def test_pruefgruende_und_ieee_anteil():
    assert A.pruefgruende(buecher()) == [("Jahr fehlt", 2), ("kaum Text (vermutlich Scan)", 1)]
    assert A.ieee_anteil(buecher()) == (1, 3)


def test_textsummen():
    s = A.textsummen(buecher())
    assert (s["buecher"], s["seiten"], s["formelzeichen"], s["unsicher"], s["fragezeichen"]) == (3, 113, 14, 1, 4)
    assert (s["tabellen"], s["ueberschriften"], s["spaltenseiten"], s["gedruckt"], s["nur_pdf"]) == (4, 9, 5, 2, 3)
    assert (s["aktuell"], s["gedruckt_anteil"], s["gedruckt_erfasst"]) == (1, 0.4, 2)


def test_offene_stellen_je_100_seiten():
    liste = [{"name": "dick", "seiten": 1000, "fragezeichen": 50, "unsicher": 0, "nur_pdf": 0},
             {"name": "duenn", "seiten": 100, "fragezeichen": 20, "unsicher": 5, "nur_pdf": 0},
             {"name": "sauber", "seiten": 100, "fragezeichen": 0, "unsicher": 0, "nur_pdf": 0}]
    offen = A.offene_stellen(liste)
    assert [b["name"] for b in offen] == ["duenn", "dick"]
    assert (offen[0]["offen"], offen[0]["je_100"]) == (25, 25.0)
    assert len(A.offene_stellen(liste, n=1)) == 1


def test_bestand_und_uebersicht():
    b = A.bestand([{"format": "PDF"}], [{"format": "PDF"}, {"format": "EPUB"}], [{"format": "PDF"}] * 3)
    assert b == {"bereiche": {"Eingang": 1, "Prüfen": 2, "Fertig": 3}, "formate": {"PDF": 5, "EPUB": 1}}
    u = A.uebersicht(buecher()[:1], anzahl_pruefen=2, bereit=1)
    assert u == {"fertig": 1, "pruefen": 2, "bereit": 1, "seiten": 3, "gedruckt_anteil": 2 / 3,
                 "gedruckt_erfasst": 1}
    assert A.uebersicht([], 0, 0)["gedruckt_anteil"] is None


def test_buchkennzahlen_nenner_aus_dem_text():
    text = ("<!-- Seite 1 (PDF 1) -->\nTabelle 3.2 Werkstoffe\n| a | b |\nTabelle 3.2 Werkstoffe (Fortsetzung)\n"
            "Tab. 4-1 Maße\nim Text $R_{e}$ und $A$\n⚠[Formel unsicher] $x�$\nFließtext ohne Formel")
    kopf = dict(KOPF, textquelle="PDFium + Formelreparatur + Lesezeichen + Tabellen")
    k = A.buchkennzahlen(kopf, text)
    assert (k["formelzeilen"], k["tabellentitel"], k["ueberschriften_im_text"]) == (2, 2, 8)
    assert k["verfahren"] == ["Formelreparatur", "Lesezeichen", "Tabellen"]


def test_textqualitaet_wert_und_hoechstzahl_nur_ueber_buecher_mit_verfahren():
    neu = {"seiten": 100, "formelzeichen": 90, "fragezeichen": 10, "unsicher": 3, "formelzeilen": 40, "tabellen": 5,
           "tabellentitel": 6, "ueberschriften": 20, "ueberschriften_im_text": 18, "spaltenseiten": 4, "gedruckt": 98,
           "nur_pdf": 2, "aktuell": True,
           "verfahren": ["Formelreparatur", "Lesezeichen", "Spaltenreihenfolge", "Tabellen", "Formelsatz", "Seitenzahlen"]}
    alt = dict(neu, formelzeichen=50, fragezeichen=50, tabellen=0, tabellentitel=30, aktuell=False,
               verfahren=["Formelreparatur", "Lesezeichen"])
    punkte = {p["titel"]: p for p in A.textqualitaet([neu, alt])}
    assert (punkte["Formelzeichen repariert"]["wert"], punkte["Formelzeichen repariert"]["max"]) == (140, 200)
    assert (punkte["Verbliebene �"]["wert"], punkte["Verbliebene �"]["max"]) == (60, 200)
    # Tabellen nur aus dem neuen Buch: das alte hatte die Tabellenerkennung noch nicht
    tab = punkte["Tabellen als Markdown"]
    assert (tab["wert"], tab["max"], tab["buecher"], tab["alle"]) == (5, 6, 1, 2)
    assert (punkte["Formeln unsicher markiert"]["wert"], punkte["Formeln unsicher markiert"]["max"]) == (3, 40)
    assert (punkte["Überschriften direkt im Text"]["wert"], punkte["Überschriften direkt im Text"]["max"]) == (36, 40)
    assert (punkte["Seiten mit gedruckter Zahl"]["wert"], punkte["Seiten mit gedruckter Zahl"]["max"]) == (98, 100)
    assert (punkte["Bücher mit aktuellem Verfahren"]["wert"], punkte["Bücher mit aktuellem Verfahren"]["max"]) == (1, 2)
    assert len(A.textqualitaet([])) == 8 and A.textqualitaet([])[0]["max"] == 0
