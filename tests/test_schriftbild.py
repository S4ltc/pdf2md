"""Schriftbild (schriftbild.py): Schriftgroesse und Fett/Kursiv je Zeile, Ueberschriften aus der Schriftgroesse
(nur fuer PDFs ohne Lesezeichen) und Fett/Kursiv als Markdown im fertigen Text."""

import pypdfium2 as pdfium
import pytest

import pdf2md as p
import schriftbild as sb
from conftest import erzeuge_gestaltet

FLIESS = "Dies ist eine ganz normale Zeile Fliesstext mit genug Woertern fuer den Durchschnitt."


def z(text, groesse=11.0, stil="", seite=0):
    """Eine Zeile wie zeilen_lesen() sie liefert, ganz in einem Stil."""
    return sb.Zeile(seite, text, groesse, 1.0 if "fett" in stil else 0.0, 1.0 if "kursiv" in stil else 0.0,
                    [(text, stil)])


def gemischt(*laeufe, seite=0, groesse=11.0):
    text = " ".join(t for t, _ in laeufe)
    zeichen = sum(len(t) for t, _ in laeufe)
    fett = sum(len(t) for t, s in laeufe if "fett" in s) / zeichen
    kursiv = sum(len(t) for t, s in laeufe if "kursiv" in s) / zeichen
    return sb.Zeile(seite, text, groesse, fett, kursiv, list(laeufe))


def fliesstext(seite, n=12):
    return [z(FLIESS, seite=seite) for _ in range(n)]


class TestStil:
    @pytest.mark.parametrize("name, flags, gewicht, winkel, erwartet", [
        ("Helvetica-Bold", 0, 0, 0, "fett"),
        ("Helvetica-Oblique", 0, 0, 0, "kursiv"),
        ("ABCDEF+TimesNewRomanPS-BoldItalicMT", 0, 0, 0, "fettkursiv"),
        ("Arial-BoldMT", 0, 0, 0, "fett"),
        ("MinionPro-It", 0, 0, 0, "kursiv"),
        ("MinionPro-BoldIt", 0, 0, 0, "fettkursiv"),
        ("CMBX10", 0, 0, 0, "fett"),                       # TeX fett
        ("CMTI10", 0, 0, 0, "kursiv"),                     # TeX kursiv
        ("CMR10", 0, 0, 0, ""),
        ("Helvetica", 0, 700, 0, "fett"),                  # nur am Gewicht erkennbar
        ("Garamond", 64, 400, 0, "kursiv"),                # Italic-Flag
        ("Garamond", 0, 400, -12, "kursiv"),               # Neigungswinkel
        ("Helvetica", 0, 400, 0, ""),
        ("CMMI10", 64, 400, -14, ""),                      # Formelschrift: kursive Variablen sind keine Betonung
        ("MTMI", 64, 400, -15, ""),
        ("CambriaMath", 64, 700, 0, ""),
        ("Symbol", 0, 700, 0, ""),
    ])
    def test_stil(self, name, flags, gewicht, winkel, erwartet):
        assert sb.stil(name, flags, gewicht, winkel) == erwartet


class TestZeilenLesen:
    def lesen(self, pfad):
        dokument = pdfium.PdfDocument(str(pfad))
        try:
            seite = dokument[0]
            textseite = seite.get_textpage()
            try:
                return sb.zeilen_lesen(textseite, 0)
            finally:
                textseite.close()
                seite.close()
        finally:
            dokument.close()

    def test_fett_und_kursiv_als_laeufe(self, tmp_path):
        pdf = erzeuge_gestaltet(tmp_path / "s.pdf",
                                [[("Ein **wichtiger Begriff** und __ein kursiver Teil__ im Satz.", 11)]])
        zeile = self.lesen(pdf)[0]
        assert zeile.laeufe == [("Ein", ""), ("wichtiger Begriff", "fett"), ("und", ""),
                                ("ein kursiver Teil", "kursiv"), ("im Satz.", "")]

    def test_groesse_je_zeile(self, tmp_path):
        pdf = erzeuge_gestaltet(tmp_path / "s.pdf", [[("Kapitel", 18), ("Fliesstext", 11)]])
        zeilen = self.lesen(pdf)
        assert [z.text for z in zeilen] == ["Kapitel", "Fliesstext"]
        assert zeilen[0].groesse == pytest.approx(18, abs=0.5) and zeilen[1].groesse == pytest.approx(11, abs=0.5)


class TestUeberschriften:
    def test_nummerierte_abschnitte_nach_ihrer_tiefe(self):
        seiten = [[z("3 Getriebe", 18, "fett")] + fliesstext(0),
                  [z("3.1 Zahnräder", 14, "fett")] + fliesstext(1),
                  fliesstext(2, 4) + [z("3.1.1 Stirnräder", 11, "fett")] + fliesstext(2, 4)]
        assert sb.ueberschriften(seiten) == {0: [(0, "3 Getriebe")], 1: [(1, "3.1 Zahnräder")],
                                             2: [(2, "3.1.1 Stirnräder")]}

    def test_ohne_nummer_entscheidet_die_groesse(self):
        seiten = [[z("Vorwort", 18)] + fliesstext(0), [z("Danksagung", 14)] + fliesstext(1)]
        assert sb.ueberschriften(seiten) == {0: [(0, "Vorwort")], 1: [(1, "Danksagung")]}

    def test_zweizeilige_ueberschrift_wird_eine(self):
        seiten = [[z("Grundlagen der", 16), z("Berechnung", 16)] + fliesstext(0)]
        assert sb.ueberschriften(seiten) == {0: [(0, "Grundlagen der Berechnung")]}

    def test_kolumnentitel_ist_keine_ueberschrift(self):
        """Eine groessere Zeile, die auf vielen Seiten gleich wiederkehrt, ist ein Kolumnentitel."""
        seiten = [[z("Kapitel 3 Getriebe", 13)] + fliesstext(i) for i in range(6)]
        assert sb.ueberschriften(seiten) == {}

    @pytest.mark.parametrize("text", ["Abb. 3.1 Zahnrad im Schnitt", "Tabelle 2 Werkstoffe", "3.1 Zahnräder 45",
                                      "Dies ist ein langer Satz in grosser Schrift, der einfach immer weiter geht "
                                      "und mit einem Punkt endet.", "F = m · a", "123"])
    def test_keine_ueberschrift(self, text):
        """Bildunterschriften, Inhaltsverzeichniszeilen (Nummer ... Seite), Saetze, Formeln und Zahlen."""
        seiten = [[z(text, 14, "fett")] + fliesstext(0)]
        assert sb.ueberschriften(seiten) == {}

    def test_fetter_nummerierter_abschnitt_in_textgroesse(self):
        seiten = [fliesstext(0, 5) + [z("2.4 Lagerung", 11, "fett")] + fliesstext(0, 5)]
        assert sb.ueberschriften(seiten) == {0: [(1, "2.4 Lagerung")]}

    def test_ohne_text_nichts(self):
        assert sb.ueberschriften([[], []]) == {}

    def test_zweite_zeile_ohne_nummer_gehoert_dazu(self):
        seiten = [fliesstext(0, 5) + [z("13.6.4 Grenzen kennen und", 11, "fett"), z("nutzen", 11, "fett")]
                  + fliesstext(0, 5)]
        assert sb.ueberschriften(seiten) == {0: [(2, "13.6.4 Grenzen kennen und nutzen")]}

    def test_nummerierte_zeile_etwas_groesser(self):
        """Nummerierte Abschnittstitel sind oft nur wenig groesser (11 pt bei 10 pt Fliesstext) und nicht fett."""
        seiten = [[z(FLIESS, 10)] * 5 + [z("3.5 Einfluss der Umgebung", 11)] + [z(FLIESS, 10)] * 5]
        assert sb.ueberschriften(seiten) == {0: [(1, "3.5 Einfluss der Umgebung")]}

    def test_anhang_mit_zusatz(self):
        seiten = [[z("Anhang A", 14, "fett"), z("(informativ)", 11, "fett"), z("Liste der Gefährdungen", 14, "fett")]
                  + fliesstext(0)]
        assert sb.ueberschriften(seiten) == {0: [(0, "Anhang A (informativ) Liste der Gefährdungen")]}

    @pytest.mark.parametrize("text", ["Druck (bar) ) K( r ut ar e p", "M2 M2 l2",
                                      "EUROPÄISCHE NORM EUROPEAN STANDARD NORME EUROPÉENNE", "(informativ)"])
    def test_beschriftungen_und_deckblatt_sind_keine(self, text):
        seiten = [[z(text, 14)] + fliesstext(0)]
        assert sb.ueberschriften(seiten) == {}

    def test_dicht_gegliederte_norm(self):
        """Normen haben oft drei Abschnitte je Seite; das ist noch kein Zeichen fuer unbrauchbare Schriftgroessen."""
        themen = iter(["Anwendungsbereich", "Begriffe", "Prüfung", "Werkstoffe", "Bewertung", "Grenzwerte",
                       "Kennzeichnung", "Lagerung", "Dokumentation"])
        seiten = [sum(([z(f"{i}.{k} {next(themen)}", 11, "fett")] + fliesstext(i, 3) for k in range(1, 4)), [])
                  for i in range(1, 4)]
        assert sum(len(v) for v in sb.ueberschriften(seiten).values()) == 9


class TestHervorhebungen:
    def test_mit_umgebung(self):
        zeile = gemischt(("Die", ""), ("Zugfestigkeit", "kursiv"), ("ist wichtig.", ""))
        h, = sb.hervorhebungen([[zeile]])
        assert (h.seite, h.text, h.stil) == (0, "Zugfestigkeit", "kursiv")
        assert h.vorher.endswith("Die") and h.nachher.startswith("ist")

    def test_einzelne_formelzeichen_nicht(self):
        zeile = gemischt(("die Kraft", ""), ("F", "kursiv"), ("wirkt auf", ""), ("ab", "fett"))
        assert sb.hervorhebungen([[zeile]]) == []

    def test_getrenntes_wort_am_zeilenende(self):
        """Das Wortstueck vor bzw. nach der Trennung steht im fertigen Text nicht so da: weglassen."""
        zeilen = [gemischt(("Die", ""), ("wichtige Konstruk-", "fett")), gemischt(("tion", "fett"), ("hält.", ""))]
        assert [h.text for h in sb.hervorhebungen([zeilen])] == ["wichtige"]


    def test_grundschrift_ist_keine_betonung(self):
        """Ist (fast) der ganze Text fett gekennzeichnet, ist das die Grundschrift: nur das Kursive zaehlt."""
        zeilen = [z(FLIESS, stil="fett") for _ in range(30)]
        zeilen.append(gemischt(("Der", "fett"), ("Grenzwert", "fettkursiv"), ("gilt hier immer.", "fett")))
        assert [(x.text, x.stil) for x in sb.hervorhebungen([zeilen])] == [("Grenzwert", "kursiv")]

    def test_satzzeichen_am_rand_nicht(self):
        zeile = gemischt(("(T", ""), (") in kJ/mol,", "fett"), ("weiter", ""))
        assert [x.text for x in sb.hervorhebungen([[zeile]])] == ["in kJ/mol"]


def h(text, stil="fett", seite=0, vorher="", nachher=""):
    return sb.Hervorhebung(seite, text, stil, vorher, nachher)


class TestEinsetzen:
    def test_fett_kursiv_und_beides(self):
        text = "<!-- Seite 1 (PDF 1) -->\nDie Zugfestigkeit ist ein Kennwert der Werkstoffe hier."
        neu, anzahl = sb.einsetzen(text, [h("Zugfestigkeit", "kursiv"), h("Kennwert", "fett"),
                                          h("Werkstoffe", "fettkursiv")])
        assert neu.endswith("Die *Zugfestigkeit* ist ein **Kennwert** der ***Werkstoffe*** hier.") and anzahl == 3

    def test_ueber_den_zeilenumbruch(self):
        neu, anzahl = sb.einsetzen("Ein wichtiger\nBegriff steht hier.", [h("wichtiger Begriff")])
        assert neu == "Ein **wichtiger\nBegriff** steht hier." and anzahl == 1

    def test_nicht_in_ueberschrift_tabelle_formel_und_marker(self):
        text = "# Lager\n\n| Lager | 3 |\n|---|---|\n\nFormel $Lager$ und <!-- Lager -->"
        assert sb.einsetzen(text, [h("Lager")]) == (text, 0)

    def test_benachbarte_stellen_werden_eine(self):
        """Ein betonter Absatz kommt zeilenweise; im fertigen Text wird daraus eine Betonung, nicht "** **"."""
        neu, anzahl = sb.einsetzen("Ein langer\nbetonter Satz hier.", [h("Ein langer"), h("betonter Satz")])
        assert neu == "**Ein langer\nbetonter Satz** hier." and anzahl == 2

    def test_nach_einer_ueberschrift_wieder_frei(self):
        """Gesperrt ist nur die Ueberschriftenzeile selbst, nicht der Text danach."""
        neu, anzahl = sb.einsetzen("# Titel\n\nDas Lager dreht.", [h("Lager")])
        assert neu == "# Titel\n\nDas **Lager** dreht." and anzahl == 1

    def test_doppeltes_wort_nach_der_umgebung(self):
        neu, _ = sb.einsetzen("Das Lager trägt. Das Lager dreht.", [h("Lager", vorher="Das ", nachher=" dreht.")])
        assert neu == "Das Lager trägt. Das **Lager** dreht."

    def test_auf_der_richtigen_seite(self):
        text = "<!-- Seite 1 (PDF 1) -->\nDas Lager.\n\n<!-- PDF-Seite 2 -->\nDas Lager."
        neu, _ = sb.einsetzen(text, [h("Lager", seite=1)])
        assert neu == "<!-- Seite 1 (PDF 1) -->\nDas Lager.\n\n<!-- PDF-Seite 2 -->\nDas **Lager**."

    def test_nie_mitten_im_wort(self):
        neu, _ = sb.einsetzen("Der Lastfall und die Last.", [h("Last")])
        assert neu == "Der Lastfall und die **Last**."

    def test_normieren_wie_der_text(self):
        neu, anzahl = sb.einsetzen("Die Oberfläche ist rau.", [h("Oberﬂäche")], normieren=lambda s: s.replace("ﬂ", "fl"))
        assert neu == "Die **Oberfläche** ist rau." and anzahl == 1

    def test_mehrdeutig_ohne_umgebung_bleibt_aus(self):
        text = "Das Lager trägt. Das Lager dreht."
        assert sb.einsetzen(text, [h("Lager")]) == (text, 0)

    def test_seitenmarker_wie_pdf2md(self):
        """einsetzen() erkennt die Seiten an den Markern, die pdf2md schreibt."""
        for marker in (p.seitenmarker(7, "12"), p.seitenmarker(7, None), p.seitenmarker(7, "xii")):
            m = sb.MARKER.fullmatch(marker)
            assert m and int(m.group(1) or m.group(2)) == 7


class TestImAblauf:
    @pytest.fixture(autouse=True)
    def schnell(self, monkeypatch):
        monkeypatch.setattr(p, "FORMELN_REPARIEREN", False)
        monkeypatch.setattr(p, "ONLINE_ABGLEICH", False)

    SEITEN = [[("1 Einleitung", 18), ("Ein **wichtiger Begriff** steht hier im Text der ersten Seite.", 11)]
              + [(FLIESS, 11)] * 8,
              [("1.1 Ziel", 14)] + [(FLIESS, 11)] * 8]

    def test_ohne_lesezeichen_ueberschriften_und_fett(self, tmp_path):
        text, quelle, extra = p.umwandeln(erzeuge_gestaltet(tmp_path / "b.pdf", self.SEITEN), None, None)
        assert "# 1 Einleitung" in text and "## 1.1 Ziel" in text
        assert "**wichtiger Begriff**" in text
        assert extra["hervorhebungen"] == 1 and extra["ueberschriften_schrift"] == 2
        assert "Hervorhebungen" in quelle

    def test_mit_lesezeichen_keine_ueberschriften_aus_der_schrift(self, tmp_path):
        pdf = erzeuge_gestaltet(tmp_path / "b.pdf", self.SEITEN, lesezeichen={0: [(0, "1 Einleitung")]})
        text, _, extra = p.umwandeln(pdf, None, None)
        assert "# 1 Einleitung" in text and "## 1.1 Ziel" not in text
        assert "ueberschriften_schrift" not in extra

    def test_abschaltbar(self, tmp_path, monkeypatch):
        monkeypatch.setattr(p, "HERVORHEBUNGEN", False)
        monkeypatch.setattr(p, "UEBERSCHRIFTEN_AUS_SCHRIFT", False)
        text, quelle, _ = p.umwandeln(erzeuge_gestaltet(tmp_path / "b.pdf", self.SEITEN), None, None)
        assert "**" not in text and "#" not in text and "Hervorhebungen" not in quelle

    def test_kopfblock(self):
        kopf = {}
        p._verfahrensfelder(kopf, {"a": 0, "b": 0, "offen": 0, "ersetzt": 0, "hervorhebungen": 5,
                                   "ueberschriften_schrift": 3})
        assert kopf["hervorhebungen"].startswith("5 ") and kopf["ueberschriften"].startswith("3 ")


class TestNurVorhandeneZeilen:
    def test_nicht_gefundener_titel_wird_nicht_eingefuegt(self):
        """Ueberschriften aus der Schriftgroesse stammen aus den rohen Zeichen ("Europ‰ische", vor der Korrektur).
        Findet sich die Zeile im fertigen Text nicht, darf nichts eingefuegt werden (sonst Dublette mit Zeichenfehler)."""
        text = "Die Europäische Norm\nText der Seite."
        assert p._ueberschriften_einfuegen(text, [(2, "Die Europ‰ische Norm")], nur_vorhandene=True) == text

    def test_gefundener_titel_wird_ueberschrift(self):
        text = "1.1 Ziel\nText der Seite."
        assert p._ueberschriften_einfuegen(text, [(1, "1.1 Ziel")], nur_vorhandene=True).startswith("## 1.1 Ziel")

    def test_seiten_zu_text_reicht_es_durch(self):
        seiten = ["Die Europäische Norm\nText der ersten Seite mit etwas Inhalt."]
        text = p.seiten_zu_text(seiten, {0: [(0, "Die Europ‰ische Norm")]}, nur_vorhandene=True)
        assert "‰" not in text and "#" not in text
