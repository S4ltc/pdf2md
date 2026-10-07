"""Tabellen mit Gitterlinien (tabellen.py): Erkennung, Zellen, verbundene Zellen, keine Tabellen aus Zeichnungen,
Einbau in den Seitentext."""

import pytest

import pdf2md as p
import tabellen
from conftest import DEJAVU, FUELLTEXT


def erzeuge(pfad, zeilen, breiten=None, vorher="Tabelle 1 — Werkstoffkennwerte", nachher="Text nach der Tabelle.",
            zusatz=None):
    """Eine Seite: Einleitung, Tabellentitel, Tabelle aus umrandeten Zellen (fpdf2 zeichnet Rechtecke), Text danach.
    zeilen: Liste von Zeilen, jede eine Liste von Zelltexten; None als Zelltext = mit der linken Zelle verbunden.
    zusatz(pdf): zeichnet weitere Linien/Texte (z.B. eine Zeichnung)."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=str(DEJAVU))
    pdf.set_font("DejaVu", size=10)
    pdf.add_page()
    pdf.multi_cell(0, 6, "Einleitung: " + FUELLTEXT[:300], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, vorher, new_x="LMARGIN", new_y="NEXT")
    for zeile in zeilen:
        breite_offen = 0
        for i, text in enumerate(zeile):
            breite = (breiten or [40] * len(zeile))[i]
            if text is None:
                continue
            # verbundene Zellen: Breite der folgenden None-Zellen dazurechnen
            j = i + 1
            while j < len(zeile) and zeile[j] is None:
                breite += (breiten or [40] * len(zeile))[j]
                j += 1
            pdf.cell(breite + breite_offen, 8, text, border=1)
        pdf.ln(8)
    pdf.ln(4)
    pdf.multi_cell(0, 6, nachher, new_x="LMARGIN", new_y="NEXT")
    if zusatz:
        zusatz(pdf)
    pdf.output(str(pfad))
    return pfad


def seitentext(pfad) -> str:
    return p.seiten_zu_text(p._pdfium_seiten(pfad, {}))


class TestErkennung:
    def test_einfache_tabelle(self, tmp_path):
        pdf = erzeuge(tmp_path / "t.pdf", [["Werkstoff", "Dichte", "E-Modul"], ["Stahl", "7,85", "210"],
                                           ["Aluminium", "2,70", "70"]])
        text = seitentext(pdf)
        assert "| Werkstoff | Dichte | E-Modul |\n|---|---|---|\n| Stahl | 7,85 | 210 |\n| Aluminium | 2,70 | 70 |" \
            in text

    def test_steht_an_der_richtigen_stelle_mit_leerzeilen(self, tmp_path):
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]])
        text = seitentext(pdf)
        davor, rest = text.split("| A | B |")
        assert davor.rstrip().endswith("Tabelle 1 — Werkstoffkennwerte") and davor.endswith("\n\n")
        assert rest.split("| 3 | 4 |")[1].startswith("\n\nText nach der Tabelle.")

    def test_tabellenzeilen_werden_nicht_zu_absaetzen_verbunden(self, tmp_path):
        lang = "ein sehr langer Zelltext ohne Satzende"
        pdf = erzeuge(tmp_path / "t.pdf", [["Spalte eins", "Spalte zwei"], [lang, lang], [lang, lang], [lang, lang]],
                      breiten=[85, 85])
        zeilen = [z for z in seitentext(pdf).split("\n") if z.startswith("|")]
        assert len(zeilen) == 5

    def test_verbundene_zelle(self, tmp_path):
        pdf = erzeuge(tmp_path / "t.pdf", [["Maße in mm", None, "Bemerkung"], ["von", "bis", ""], ["0", "3", "klein"],
                                           ["3", "6", "mittel"]])
        text = seitentext(pdf)
        assert "| Maße in mm |  | Bemerkung |" in text and "| 3 | 6 | mittel |" in text

    def test_seitlich_offene_tabelle(self, tmp_path):
        """Regression (Buch mit Normtabelle): die aeusseren Spalten haben keine senkrechte Randlinie, nur die
        waagerechten Linien reichen bis dorthin. Die Randspalten gehoeren trotzdem zur Tabelle."""
        def offen(pdf):
            pdf.set_font("DejaVu", size=9)
            for y in (150, 160, 170, 180):                          # waagerecht ueber die ganze Breite (mm)
                pdf.line(10, y, 190, y)
            for x in (40, 100, 160):                                # senkrecht nur innen
                pdf.line(x, 150, x, 180)
            for k, zeile in enumerate([["Zeile", "Bezug", "bis 3 m", "Spalte sieben"],
                                       ["1", "Maße im Grundriss", "10", "30"],
                                       ["2", "Maße im Aufriss", "16", "30"]]):
                for x, text in zip((12, 42, 102, 162), zeile):
                    pdf.text(x, 156 + 10 * k, text)
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]], zusatz=offen)
        text = seitentext(pdf)
        assert "| Zeile | Bezug | bis 3 m | Spalte sieben |" in text and "| 2 | Maße im Aufriss | 16 | 30 |" in text

    def test_zerlegter_umlaut_in_der_zelle(self, tmp_path):
        """Neuere DIN-PDFs setzen "ä" als "a" + Trema; das Trema sitzt hoeher und darf nicht als neue Zeile gelten."""
        pdf = erzeuge(tmp_path / "t.pdf", [["Fla\u0308che", "Gro\u0308ße"], ["1", "2"], ["3", "4"]])
        assert "| Fläche | Größe |" in seitentext(pdf)

    def test_senkrechter_spaltenkopf(self, tmp_path):
        """Um 90° gedrehte Spaltenkoepfe (in Normen haeufig): die Buchstaben stehen uebereinander, sind aber ein Wort."""
        def gedreht(pdf):
            pdf.set_font("DejaVu", size=9)
            with pdf.rotation(90, 30, 190):
                pdf.text(30, 190, "Bruchprüfung")
            for x in (20, 40, 80):
                pdf.line(x, 120, x, 210)
            for y in (120, 195, 210):
                pdf.line(20, y, 80, y)
            pdf.text(45, 190, "Kopf rechts")
            pdf.text(24, 206, "Wert A")
            pdf.text(45, 206, "Wert B")
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]], zusatz=gedreht)
        text = seitentext(pdf)
        assert "| Bruchprüfung | Kopf rechts |" in text and "| Wert A | Wert B |" in text

    def test_doppelt_gezeichneter_text_steht_einmal_in_der_zelle(self, tmp_path):
        """Regression (Handbuch): manche PDFs enthalten den Tabellentext zweimal an derselben Stelle."""
        def nochmal(pdf):
            pdf.set_font("DejaVu", size=10)
            pdf.set_xy(10, 150)
            for zeile in (["Werkstoff", "Dichte"], ["Stahl", "7,85"], ["Kupfer", "8,96"]):
                for text in zeile:
                    pdf.cell(40, 8, text, border=1)
                pdf.ln(8)
            pdf.set_xy(10, 150)                               # derselbe Text noch einmal, ohne Rahmen
            for zeile in (["Werkstoff", "Dichte"], ["Stahl", "7,85"], ["Kupfer", "8,96"]):
                for text in zeile:
                    pdf.cell(40, 8, text)
                pdf.ln(8)
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]], zusatz=nochmal)
        text = seitentext(pdf)
        assert "| Stahl | 7,85 |" in text and "Stahl Stahl" not in text

    def test_senkrechter_strich_im_zelltext(self, tmp_path):
        pdf = erzeuge(tmp_path / "t.pdf", [["Ausdruck", "Wert"], ["|x|", "Betrag"], ["a", "b"]])
        assert "| \\|x\\| | Betrag |" in seitentext(pdf)

    def test_statistik_und_textquelle(self, arbeitsordner, konverter, tmp_path):
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]])
        text, quelle, extra = p.umwandeln(pdf, 1, konverter)
        assert extra["tabellen"] == 1 and "+ Tabellen" in quelle and "| A | B |" in text

    def test_abschaltbar(self, arbeitsordner, konverter, tmp_path, monkeypatch):
        monkeypatch.setattr(p, "TABELLEN_ERKENNEN", False)
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]])
        text, quelle, extra = p.umwandeln(pdf, 1, konverter)
        assert "|---|" not in text and "Tabellen" not in quelle and "tabellen" not in extra


class TestKeineTabelle:
    def test_fast_leeres_gitter_ist_ein_diagramm(self, tmp_path):
        """Ein Diagramm mit Gitternetz und zwei Achsenbeschriftungen ist keine Tabelle."""
        zeilen = [["0,5", "", "", ""], ["", "", "", ""], ["", "", "", ""], ["", "", "", "10"]]
        assert "|---|" not in seitentext(erzeuge(tmp_path / "t.pdf", zeilen))

    def test_linie_durch_ein_wort_ist_eine_zeichnung(self, tmp_path):
        """Laufen Gitterlinien mitten durch Woerter, ist es eine Zeichnung mit Beschriftung, keine Tabelle."""
        def beschriftung(pdf):
            pdf.set_xy(10, 150)
            for k in range(4):                       # Beschriftungen quer ueber die senkrechten Linien
                pdf.set_xy(35, 160 + 8 * k)
                pdf.cell(0, 8, "Beschriftung eins und Beschriftung zwei im Bild")
            for x in (10, 50, 90, 130):
                pdf.line(x, 158, x, 194)
            for y in (158, 170, 182, 194):
                pdf.line(10, y, 130, y)
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]], zusatz=beschriftung)
        text = seitentext(pdf)
        assert text.count("|---|") == 1                     # nur die echte Tabelle
        assert text.count("Beschriftung eins und Beschriftung zwei im Bild") == 4

    def test_text_ueber_den_aussenrand_ist_keine_tabelle(self, tmp_path):
        """Regression (Lehrbuch): ein Kasten mit Randlinien ueber dem linken Teil einer Aufzaehlung.
        Die Zeilen laufen ueber den Aussenrand hinaus ("• Da|s Beispiel A ist ..."), das ist nie eine Tabelle; der Text
        muss vollstaendig bleiben."""
        def kasten(pdf):
            pdf.set_font("DejaVu", size=10)
            for k, text in enumerate(["Das Beispiel A ist der erste Absatz hier.",
                                      "Das Beispiel B steht im zweiten Absatz der Liste.",
                                      "Der dritte Absatz beendet die kleine Aufzählung."]):
                pdf.text(10.8, 158 + 10 * k, "•")              # Spalte 1: nur der Aufzaehlungspunkt
                pdf.text(15, 158 + 10 * k, text)               # Spalte 2 und weit ueber den rechten Rand hinaus
            for x in (10, 14, 20):                            # mm; der rechte Rand schneidet "Da|s"
                pdf.line(x, 150, x, 182)
            for y in (150, 161, 171, 182):
                pdf.line(10, y, 20, y)
        pdf = erzeuge(tmp_path / "t.pdf", [["A", "B"], ["1", "2"], ["3", "4"]], zusatz=kasten)
        text = seitentext(pdf)
        assert text.count("|---|") == 1
        assert "Das Beispiel A ist der erste Absatz hier." in text

    def test_seite_ohne_linien(self, tmp_path):
        from conftest import erzeuge_pdf
        pdf = erzeuge_pdf(tmp_path / "x.pdf", ["Nur Text\n" + FUELLTEXT])
        assert "|---|" not in seitentext(pdf)


def gitter(zeilen: int, spalten: int, texte: dict, verbunden=()) -> tabellen.Tabelle:
    """Tabelle ohne PDF: texte {(zeile, spalte): Text}; verbunden: Gruppen von (zeile, spalte), die eine Zelle sind."""
    t = tabellen.Tabelle(xs=[float(x) for x in range(spalten + 1)], ys=[float(y) for y in range(zeilen, -1, -1)],
                         waagerecht=[], senkrecht=[])
    for r in range(zeilen):
        for c in range(spalten):
            t.bereich[(r, c)] = r * spalten + c
    for gruppe in verbunden:
        ziel = t.bereich[gruppe[0]]
        for k in gruppe[1:]:
            t.bereich[k] = ziel
    t.zellen = {t.bereich[k]: [text] for k, text in texte.items()}
    return t


class TestEcht:
    def test_normale_tabelle(self):
        t = gitter(3, 3, {(r, c): f"Wert {r}{c}" for r in range(3) for c in range(3)})
        assert tabellen.echt(t, 0)

    def test_wortschnitt(self):
        t = gitter(3, 3, {(r, c): f"Wert {r}{c}" for r in range(3) for c in range(3)})
        assert not tabellen.echt(t, 2)

    def test_duenne_regelmaessige_matrix_bleibt(self):
        """GPS-Matrix einer Norm: 12x8, nur Kopf, Zeilennamen und wenige Punkte, aber regelmaessiges Raster."""
        texte = {(0, c): f"Kettenglied {c}" for c in range(1, 8)}
        texte.update({(1, c): "ABCDEFG"[c - 1] for c in range(1, 8)})
        texte.update({(r, 0): f"Merkmal Nummer {r}" for r in range(2, 12)})
        texte.update({(1, 1): "•", (1, 2): "•"})
        assert tabellen.echt(gitter(12, 8, texte), 0)

    def test_schaltbild_mit_vielen_verbundenen_zellen(self):
        """Unregelmaessiges Raster (grosse verbundene Kaesten) und duenn beschriftet: ein Schaltbild."""
        verbunden = [[(r, c) for r in range(0, 3) for c in range(0, 4)], [(r, c) for r in range(3, 6) for c in range(4, 8)]]
        texte = {(0, 0): "Adressenpuffer", (3, 4): "Datenpuffer", (6, 1): "A8..A15", (7, 7): "AD0"}
        assert not tabellen.echt(gitter(8, 8, texte, verbunden), 0)

    def test_kleiner_rahmen_mit_kurzen_beschriftungen(self):
        assert not tabellen.echt(gitter(3, 3, {(0, 1): "θ FS", (1, 2): "F", (2, 0): "h"}), 0)

    def test_kleine_duenne_tabelle_mit_langem_text_bleibt(self):
        """Symboltabelle einer Norm: die Symbole sind Grafik, die Erklaerungen langer Text."""
        texte = {(0, 0): "Graphisches Symbol", (0, 1): "Deutung und Beispiel",
                 (1, 1): "Kreisförmig in Bezug auf den Mittelpunkt der Fläche", (2, 1): "Radial in Bezug auf die Mitte"}
        assert tabellen.echt(gitter(4, 3, texte), 0)


class TestFreieEnden:
    S = tabellen.Strecke

    def gitter_linien(self, extra_senkrecht):
        waagerecht = [self.S(y, 0.0, 100.0) for y in (0.0, 10.0, 20.0)]
        senkrecht = [self.S(x, 0.0, 20.0) for x in (0.0, 100.0)] + extra_senkrecht
        return tabellen._freie_enden_entfernen(waagerecht, senkrecht)

    def test_kurzes_freies_ende_wird_abgeschnitten(self):
        """Normtabelle: die Trennlinie "µm | mm" laeuft durch alle Datenzeilen und endet mitten in der Kopfzelle."""
        _, senkrecht = self.gitter_linien([self.S(50.0, 0.0, 26.0)])
        mitte = [s for s in senkrecht if s.lage == 50.0]
        assert len(mitte) == 1 and (mitte[0].von, mitte[0].bis) == (0.0, 20.0)

    def test_langes_freies_ende_ist_eine_zeichnung(self):
        _, senkrecht = self.gitter_linien([self.S(50.0, 0.0, 60.0)])
        assert not [s for s in senkrecht if s.lage == 50.0]

    def test_linie_mit_nur_einer_kreuzung_faellt_weg(self):
        _, senkrecht = self.gitter_linien([self.S(50.0, 15.0, 22.0)])
        assert not [s for s in senkrecht if s.lage == 50.0]


class TestZelltext:
    @pytest.mark.parametrize("teile, erwartet", [
        (["Kon-", "\n", "struktion"], "Konstruktion"),
        (["Ordnungs-", "\n", "Nr."], "Ordnungs-Nr."),
        (["Ein-", "\n", "und Ausgabe"], "Ein- und Ausgabe"),
        (["Maschinen\ufffe", "\n", "bau"], "Maschinenbau"),
        (["+6", "\n", "+4"], "+6 +4"),
        (["a  |  b"], "a \\| b"),
    ])
    def test_zelltext(self, teile, erwartet):
        assert tabellen._zelltext(teile) == erwartet


class TestNurWaagerecht:
    """Tabellen ohne senkrechte Linien (Linie oben, unter dem Kopf, unten): Spalten aus dem Leerraum."""

    @staticmethod
    def zeile(y, *zellen, x0=50.0, spalte=80.0, g=10.0):
        import formelsatz as fs
        teile = []
        for c, text in enumerate(zellen):
            x = x0 + c * spalte
            for ch in text:
                if ch != " ":
                    teile.append(fs.Teil([len(teile)], ch, x, x + 5, y - 2, y + 7, y, g))
                x += 5.5
        return teile

    def tabelle(self, zeilen, kopf_ende=180.0):
        kandidat = tabellen.Linienkandidat(45.0, 300.0, [200.0, kopf_ende, 100.0])
        teile = [t for z in zeilen for t in z]
        return tabellen.linientabellen([kandidat], teile)

    def test_spalten_aus_dem_leerraum(self):
        zeilen = [self.zeile(188, "Stoff", "T", "D"), self.zeile(168, "Luft", "0", "49,3"),
                  self.zeile(154, "Wasser", "20", "1,02"), self.zeile(140, "Benzol", "25", "9,26")]
        t, = self.tabelle(zeilen)
        assert len(t.xs) == 4 and len(t.ys) == 5 and t.nur_waagerecht

    def test_fortsetzungszeile_gehoert_zur_zeile_davor(self):
        zeilen = [self.zeile(188, "Sym", "Name", "Einheit"), self.zeile(168, "a", "Hilfsgroesse", "-"),
                  self.zeile(156, "", "Anstroemung", ""), self.zeile(140, "b", "Breite", "m"),
                  self.zeile(126, "c", "Laenge", "m")]
        t, = self.tabelle(zeilen)
        assert len(t.ys) == 5                     # Kopf, a (zwei Zeilen), b, c

    def test_zu_wenige_datenzeilen(self):
        assert self.tabelle([self.zeile(188, "A", "B"), self.zeile(168, "1", "2")]) == []

    def test_fliesstext_zwischen_linien_ist_keine_tabelle(self):
        """Ohne gemeinsame Luecke in allen Zeilen gibt es keine Spalten."""
        import formelsatz as fs
        zeilen = []
        for i, y in enumerate((168, 154, 140)):
            zeilen.append([fs.Teil([k], "x", 50 + k * 5.5 + i * 2.7, 55 + k * 5.5 + i * 2.7, y - 2, y + 7, y, 10.0)
                           for k in range(40)])
        assert self.tabelle([self.zeile(188, "Ueberschrift")] + zeilen) == []

    def test_zweispaltiger_fliesstext_ist_keine_tabelle(self):
        """Kopf- und Fusslinie ueber zwei Textspalten: die Spaltenluecke ist gemeinsam, aber die Zellen sind Saetze."""
        satz = "der Text laeuft hier weiter"
        zeilen = [self.zeile(188, "Kapitel", "Abschnitt")] + [
            self.zeile(170 - 12 * i, satz, satz, spalte=170.0) for i in range(5)]
        tabellen_ = self.tabelle(zeilen)
        if tabellen_:
            t = tabellen_[0]
            t.zellen = {n: list(satz) for n in set(t.bereich.values())}
            assert not tabellen.echt(t, 0)
