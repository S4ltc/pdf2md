"""Textbereinigung: Silbentrennung, Absaetze, Kopf-/Fusszeilen, Umlaute, Sonderfaelle."""

import pytest

import pdf2md as p


class TestSilbentrennung:
    @pytest.mark.parametrize("roh, erwartet", [
        ("Die Kon-\nstruktion ist gut", "Die Konstruktion ist gut"),
        ("die ge￾\nsamte Platte", "die gesamte Platte"),                    # PDFium-Trennmarke
        ("Waerme￾\nuebertragung", "Waermeuebertragung"),
        ("Elektro-\nTechnik", "Elektro-Technik"),                               # Grossbuchstabe: echter Bindestrich
        ("Maschinenbau￾\nTechniker", "Maschinenbau-Techniker"),
        ("die Ein-\nund Ausgabe", "die Ein- und Ausgabe"),                      # Aufzaehlung bleibt lesbar
        ("geschwindigkeits￾\nund Beschleunigung", "geschwindigkeits- und Beschleunigung"),
        ("Seite 12-\n15 ist", "Seite 12-\n15 ist"),                             # Zahlenbereich bleibt
        ("Ende-zu-Ende Test", "Ende-zu-Ende Test"),                             # Strich mitten in der Zeile bleibt
    ])
    def test_faelle(self, roh, erwartet):
        assert p._trennungen_verbinden(roh) == erwartet


class TestSeitenbereinigung:
    def test_ligaturen(self):
        assert p._seite_bereinigen("ﬁnden ﬂiegen oﬃce") == "finden fliegen office"

    def test_inhaltsverzeichnis_punkte(self):
        assert p._seite_bereinigen("1.1 Einleitung ........... 12") == "1.1 Einleitung … 12"
        assert p._seite_bereinigen("Kapitel 2 . . . . . . . 40") == "Kapitel 2 … 40"

    def test_drei_punkte_bleiben(self):
        assert p._seite_bereinigen("Und dann... geht es weiter") == "Und dann... geht es weiter"

    def test_unsichtbare_zeichen_weg_unlesbare_werden_platzhalter(self):
        assert p._seite_bereinigen("Wert\x02 und￾ Test­x") == "Wert� und Testx"

    def test_einzelne_utf16_haelften_machen_den_text_nicht_unspeicherbar(self):
        text = p.seiten_zu_text(["Text mit \ud835 einzelner Haelfte\n"])
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in text)
        text.encode("utf-8")                                                    # darf nicht fehlschlagen


class TestAbsaetze:
    ZEILEN = [
        "Dies ist ein langer Absatz mit Fliesstext, der ueber mehrere Zeilen laeuft und",
        "an der Zeilengrenze umbrochen wird. Er geht noch weiter und wird wieder in der",
        "Mitte eines Satzes umbrochen, damit der Absatz aus vier Zeilen besteht, welche alle",
        "zusammengehoeren. Ende des Absatzes.",
        "Ein neuer Absatz beginnt hier und ist ebenfalls lang genug, um umbrochen zu werden",
        "und wird danach fortgesetzt, bis er zu Ende ist.",
        "1. Erster Punkt einer Liste mit langem Text der fast die volle Zeilenbreite erreicht ja",
        "2. Zweiter Punkt der Liste",
        "F = m * a  (Gleichung 5.1) und noch etwas Text der lang genug ist fuer die volle Breite",
        "Kapitel 1 Einleitung ........................................................ 1",
        "Kapitel 2 Grundlagen ........................................................ 9",
        "Ein Satz, der genau am Zeilenende mit einem Punkt aufhoert und lang genug ist fuer alles.",
        "Danach kommt ein neuer Satz.",
    ]

    def ergebnis(self):
        return p._seite_bereinigen("\n".join(self.ZEILEN))

    def test_umbrochener_absatz_wird_verbunden(self):
        assert "alle zusammengehoeren. Ende des Absatzes." in self.ergebnis()

    def test_liste_bleibt_zeilenweise(self):
        assert "\n2. Zweiter Punkt der Liste" in self.ergebnis()

    def test_inhaltsverzeichnis_bleibt_zeilenweise(self):
        assert "\nKapitel 2 Grundlagen" in self.ergebnis()

    def test_satzende_trennt(self):
        erg = self.ergebnis()
        assert "fuer alles.\nDanach" in erg or "fuer alles.\n\nDanach" in erg

    def test_abkuerzung_am_zeilenende_erzeugt_keinen_absatz(self):
        zeile1 = "Der Schnittpunkt S4 wird nun ein Stueck weit rechts von der Mitte der Tischplatte gelegt, z. B. bei (s."
        zeile2 = "Abb. 2.16e) ergibt sich die folgende Gleichung fuer das Moment M4 und es geht weiter mit Text."
        erg = p._absaetze_bilden("\n".join([zeile1, zeile2] * 5))
        assert "(s.\n\nAbb." not in erg
        assert "(s. Abb. 2.16e)" in erg


class TestKopfFuss:
    def seiten(self):
        seiten = []
        for n in range(1, 13):
            seiten.append(["Kapitel 3 Grundlagen", f"Fliesstext der Seite {n} mit Inhalt.",
                           f"Noch eine Zeile {n}.", str(100 + n)])
        for n in range(9):
            seiten[n].insert(1, "Aufgabe 7")
        return seiten

    def test_laufende_kopfzeile_und_seitenzahlen_werden_entfernt(self):
        alle = [z for s in p._kopf_fuss_entfernen(self.seiten()) for z in s]
        assert "Kapitel 3 Grundlagen" not in alle
        assert not any(z.strip().isdigit() for z in alle)

    def test_strukturwoerter_bleiben(self):
        alle = [z for s in p._kopf_fuss_entfernen(self.seiten()) for z in s]
        assert sum(z == "Aufgabe 7" for z in alle) == 9

    def test_fliesstext_bleibt(self):
        alle = [z for s in p._kopf_fuss_entfernen(self.seiten()) for z in s]
        assert sum(z.startswith("Fliesstext") for z in alle) == 12

    def test_sehr_kurze_zeilen_gelten_nicht_als_fusszeile(self):
        seiten = [["Kopf Kapitel", "(3", "Text"] for _ in range(12)] + [["Anderes", "Text"] for _ in range(3)]
        rest = p._kopf_fuss_entfernen([list(s) for s in seiten])
        assert all("(3" in s for s in rest[:12])
        assert all(s[0] != "Kopf Kapitel" for s in rest[:12])

    def test_kopfzeile_wird_auch_wenige_zeilen_vom_rand_erkannt(self):
        """Regressionstest: bei zweispaltigen Seiten (lesefolge.py) steht die Kopfzeile nach dem Umstellen nicht
        immer exakt an Position 0, z.B. wenn ihr eine kurze Randnotiz vorausgeht. Die Kopfzeile selbst muss aber auf
        genug Seiten an der echten Kante stehen, damit sie erkannt wird."""
        seiten = [["Kapitel 3 Grundlagen", f"Fliesstext {n}.", str(100 + n)] for n in range(1, 10)]
        seiten += [["Randnotiz", "Kapitel 3 Grundlagen", f"Fliesstext {n}.", str(100 + n)] for n in range(10, 13)]
        rest = p._kopf_fuss_entfernen([list(s) for s in seiten])
        alle = [z for s in rest for z in s]
        assert "Kapitel 3 Grundlagen" not in alle
        assert all(z.startswith(("Randnotiz", "Fliesstext")) for z in alle)

    def test_kein_falscher_treffer_bei_seitenzahl_im_fliesstext(self):
        """Regressionstest: eine sich pro Seite wiederholende Kurzzeile mitten im Text (Beispielaufgabe mit
        wechselnder Nummer) darf durch den erweiterten Rand nicht als Kopfzeile verschwinden."""
        seiten = [["Kapitel 3 Grundlagen", f"Beispiel {n}: Kurztext.", f"Fliesstext der Aufgabe {n}.",
                   str(100 + n)] for n in range(1, 13)]
        rest = p._kopf_fuss_entfernen([list(s) for s in seiten])
        alle = [z for s in rest for z in s]
        assert sum(z.startswith("Beispiel") for z in alle) == 12
        assert sum(z.startswith("Fliesstext der Aufgabe") for z in alle) == 12


    def test_gestapelte_kopfzeilen(self):
        """Normen haben zwei Kopfzeilen uebereinander ("DIN EN ISO 13579:2023-07", darunter "EN ISO 13579:2023 (D)"),
        die untere steht nie an der Kante und wird erst nach dem Entfernen der oberen erkannt."""
        worte = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa"]
        seiten = [["DIN EN ISO 13579:2023-07", "EN ISO 13579:2023 (D)", f"{w} ist Inhalt.", f"Weiter mit {w}.", str(n)]
                  for n, w in enumerate(worte, 2)]
        rest = p._kopf_fuss_entfernen(seiten)
        assert all(s == [f"{w} ist Inhalt.", f"Weiter mit {w}."] for s, w in zip(rest, worte))

    def test_punktfuehrer_des_inhaltsverzeichnisses_bleiben(self):
        """Regression: die letzte Zeile eines Kapitel-Inhaltsverzeichnisses ("Literatur . . . . 15") steht auf vielen
        Kapitelanfangsseiten am Seitenende, ist aber keine Fusszeile."""
        seiten = [[f"Kapitel {n}", f"{n}.1 Abschnitt . . . . . . . . 3", "Literatur . . . . . . . . . . . . 15"]
                  for n in range(12)]
        rest = p._kopf_fuss_entfernen(seiten)
        assert all(s[-1].startswith("Literatur") for s in rest)


class TestWeichesTrennzeichen:
    @pytest.mark.parametrize("roh, erwartet", [
        ("Bruch\u00ad prüfung von Kehl\u00ad nähten", "Bruchprüfung von Kehlnähten"),   # senkrechter Tabellenkopf
        ("Maschinen\u00ad\nbau", "Maschinenbau"),
        ("Ein\u00ad und Ausgabe", "Ein- und Ausgabe"),
        ("Norm\u00adentwurf", "Normentwurf"),                                          # mitten im Wort: nur weg
    ])
    def test_weiches_trennzeichen(self, roh, erwartet):
        assert p._seite_bereinigen(roh) == erwartet


class TestSeitenmarker:
    def test_marker_nur_fuer_seiten_mit_text(self):
        text = p.seiten_zu_text(["Titelseite\nDer Titel des Buches", "", "Seite drei mit Text\nund einer Zeile", ""])
        assert len(p.SEITENMARKER_MUSTER.findall(text)) == 2 and "<!-- PDF-Seite 3 -->" in text

    def test_nutztext_entfernt_marker(self):
        assert "<!--" not in p.nutztext(p.seiten_zu_text(["Text auf Seite eins"]))


class TestUmlaute:
    def test_kodierung_defekt_erkennt_fehlende_umlaute(self):
        schlecht = "Die Lsung fr das Problem ist mglich, wir knnen es zunchst rechnen und mssen dann prfen. " * 60
        assert p.kodierung_defekt(schlecht)

    def test_auch_mit_platzhalter(self):
        markiert = "Die L�sung f�r das Problem ist m�glich, wir k�nnen es zun�chst rechnen. " * 60
        assert p.kodierung_defekt(markiert)

    def test_guter_und_kurzer_text_ist_nicht_defekt(self):
        assert not p.kodierung_defekt("Das ist ein ganz normaler deutscher Text ueber die Kraft. " * 200)
        assert not p.kodierung_defekt("Lsung fr das")

    def test_umlaute_aus_dem_buch_ergaenzen(self):
        text = ("Die Lösung ist klar. " * 5 + "Eine L�sung folgt. " + "Das ist für dich. " * 4 + "Wie f�r mich. "
                + "Und ein x�y bleibt. " + "Die Änderung war groß. " * 3 + "Die �nderung kommt.")
        neu, anzahl = p.umlaute_ergaenzen(text)
        assert "Lösung folgt" in neu and "für mich" in neu and "Änderung kommt" in neu
        assert "x�y" in neu                                               # nicht eindeutig: bleibt
        assert anzahl == 3

    def test_lesezeichen_titel_zaehlen_als_verlaesslicher_beleg(self):
        """Steht das Wort nur einmal intakt im Text, reicht ein zusaetzliches Lesezeichen mit dem Wort (Regression:
        seit Ueberschriften doppelte Titelzeilen ersetzen, fehlte dieser zweite Beleg)."""
        text = "5 Aufeinander abrollende Zahnr�der\n## Beispiel 5: Aufeinander abrollende Zahnräder"
        assert p.umlaute_ergaenzen(text)[1] == 0
        neu, anzahl = p.umlaute_ergaenzen(text, "Beispiel 5: Aufeinander abrollende Zahnräder")
        assert anzahl == 1 and "abrollende Zahnräder\n" in neu

    def test_mehrdeutiges_wird_nicht_geraten(self):
        text = "Wir müssen und mössen. " * 2 + "m�ssen wir."
        neu, anzahl = p.umlaute_ergaenzen(text)
        assert anzahl == 0 and "m�ssen" in neu
