"""Gedruckte Seitenzahlen (seitenzahlen.py) und Verbinden ueber den Seitenwechsel (pdf2md.seiten_zu_text)."""
import pytest

import pdf2md as p
import seitenzahlen as sz


def rand(*zahlen):
    """Randzahlen-Kandidaten je Seite: None = keine Zahl auf der Seite."""
    return [set() if z is None else ({z} if isinstance(z, int) else set(z)) for z in zahlen]


class TestKandidaten:
    @pytest.mark.parametrize("zeilen, erwartet", [
        (["EN 34567-2:2019 (D)", "9", "Text"], {9}),                         # Norm: Zahl unter der Kopfzeile
        (["Text", "– 12 –"], {12}),
        (["Text", "Seite 5 von 41"], {5, 41}),                 # 41 faellt erst bei der Folge heraus
        (["12.3 Aufbau des Prüfstands 197", "Text"], {197}),                # lebende Kolumne mit Zahl hinten
        (["198 12 Bauteile im Überblick", "Text"], {198}),                 # Zahl vorn
        (["DIN EN 34567-2:2019-10", "Text"], set()),                         # Normnummer ist keine Seitenzahl
    ])
    def test_kandidaten(self, zeilen, erwartet):
        assert sz.kandidaten(zeilen) == erwartet


class TestRandzahlen:
    def test_din_en_norm_mit_zwei_zaehlungen(self):
        """DIN-Deckblatt (1), nationales Vorwort (2), EN-Deckblatt (EN-Seite 1), dann EN-Seiten 2, 3, ..."""
        ergebnis = sz.aus_randzahlen(rand(None, 2, None, 2, 3, 4, 5, 6, 7))
        assert ergebnis == [1, 2, 1, 2, 3, 4, 5, 6, 7]

    def test_vorspann_ohne_zahl_bleibt_offen(self):
        ergebnis = sz.aus_randzahlen(rand(None, None, None, None, None, 1, 2, 3, 4, 5, 6))
        assert ergebnis[:3] == [None, None, None] and ergebnis[5:] == [1, 2, 3, 4, 5, 6]

    def test_seiten_ohne_zahl_im_abschnitt(self):
        """Kapitelanfang oder Bildseite ohne gedruckte Zahl bekommt die Zahl aus der Folge."""
        assert sz.aus_randzahlen(rand(11, 12, None, 14, None, 16)) == [11, 12, 13, 14, 15, 16]

    def test_einzelne_zahl_zaehlt_nicht(self):
        """Eine Abschnittsnummer oder Achsbeschriftung am Rand ist keine Seitenzahl."""
        ergebnis = sz.aus_randzahlen(rand(None, None, None, None, None, None, None, None, 3, None, None, None))
        assert ergebnis == [None] * 12

    def test_stoerzahlen_verlieren_gegen_die_folge(self):
        seiten = rand(*[(i + 10, 1 + i % 3) for i in range(12)])          # jede Seite noch eine falsche Zahl
        assert sz.aus_randzahlen(seiten) == [i + 10 for i in range(12)]


class TestZuordnen:
    def test_label_mit_roemischem_vorspann(self):
        labels = ["i", "ii", "iii", "1", "2", "3", "4"]
        gedruckt, quelle = sz.zuordnen(labels, rand(None, None, None, None, 2, 3, None))
        assert gedruckt == labels and quelle == "Seitenlabel der PDF"

    def test_label_das_nur_die_position_wiederholt_gilt_nicht(self):
        """Norm: Labels 1..n, gedruckt ist aber erst ab der 10. PDF-Seite "1" (Versatz 9)."""
        labels = [str(i + 1) for i in range(20)]
        seiten = rand(*([None] * 9 + list(range(1, 12))))
        gedruckt, quelle = sz.zuordnen(labels, seiten)
        assert gedruckt[9:] == [str(i) for i in range(1, 12)] and quelle == "Seitenzahlen am Seitenrand"

    def test_label_das_den_randzahlen_widerspricht_gilt_nicht(self):
        labels = ["A", "B"] + [str(i + 100) for i in range(10)]
        gedruckt, quelle = sz.zuordnen(labels, rand(None, None, *range(1, 11)))
        assert gedruckt[2:] == [str(i) for i in range(1, 11)] and quelle == "Seitenzahlen am Seitenrand"

    def test_ohne_alles(self):
        assert sz.zuordnen(None, rand(None, None)) == ([None, None], "")


class TestSeitenmarker:
    def test_marker_mit_gedruckter_seite(self):
        text = p.seiten_zu_text(["Erster Satz.", "Zweiter Satz."], labels=["xi", "xii"])
        assert "<!-- Seite xi (PDF 1) -->" in text and "<!-- Seite xii (PDF 2) -->" in text

    def test_marker_ohne_gedruckte_seite(self):
        assert p.seiten_zu_text(["Ein Satz."]).startswith("<!-- PDF-Seite 1 -->\n")

    def test_seitenzahl_kommt_aus_der_fusszeile(self):
        seiten = [f"Text der Seite {i} mit einem vollstaendigen Satz.\n{i - 4}" for i in range(5, 15)]
        text = p.seiten_zu_text(seiten)
        assert "<!-- Seite 1 (PDF 1) -->" in text and "<!-- Seite 10 (PDF 10) -->" in text

    def test_alle_markerformen_werden_erkannt(self):
        alt = "<!-- Seite 3 -->\nText"
        neu = "<!-- Seite 197 (PDF 206) -->\nText <!-- Seite 198 (PDF 207) --> weiter\n<!-- PDF-Seite 3 -->\nEnde"
        assert p.nutztext(alt) == "Text" and p.nutztext(neu) == "Text weiter\nEnde"


LANG = "Dies ist eine lange Zeile mit Fliesstext, die über die ganze Seitenbreite läuft"


class TestSeitenwechsel:
    def test_getrenntes_wort_wird_verbunden(self):
        text = p.seiten_zu_text([f"{LANG} und den Reg-", "ler. Neuer Satz auf der Seite."], labels=["11", "12"])
        assert "den Regler." in text and "<!-- Seite 12 (PDF 2) -->\nNeuer Satz" in text

    def test_satz_ueber_den_seitenwechsel_bekommt_den_marker_im_satz(self):
        text = p.seiten_zu_text([f"{LANG} und dann wird der", "Wert berechnet. Weiter."], labels=["11", "12"])
        assert "wird der Wert" not in text                                  # gross: kein Fortsetzungsbeleg
        text = p.seiten_zu_text([f"{LANG} und dann wird der", "neue Wert berechnet. Weiter."], labels=["11", "12"])
        assert "wird der <!-- Seite 12 (PDF 2) --> neue Wert berechnet." in text
        assert "wird der neue Wert berechnet." in p.nutztext(text)

    def test_getrennt_und_satz_laeuft_weiter(self):
        text = p.seiten_zu_text([f"{LANG} und der Reg-", "ler regelt die Temperatur."], labels=["7", "8"])
        assert "der Regler <!-- Seite 8 (PDF 2) --> regelt die Temperatur." in text

    def test_weiche_trennung_am_seitenende(self):
        text = p.seiten_zu_text([f"{LANG}, es ist empfehlens\ufffe", "wert, das zu tun."], labels=["11", "12"])
        assert "empfehlenswert," in text

    def test_koordination_bleibt(self):
        text = p.seiten_zu_text([f"{LANG} für die Ein-", "und Ausgabe der Daten."], labels=["11", "12"])
        assert "Ein- <!-- Seite 12 (PDF 2) --> und Ausgabe" in text

    @pytest.mark.parametrize("ende, anfang", [
        ("| a | b |", "weiter im Text"),                                    # Tabelle
        (f"{LANG} am Satzende.", "kleiner Anfang"),                          # Satzende
        ("Abb. 3.2 Verlauf der Temperatur über der Zeit im Versuch", "der Text geht weiter"),   # Bildunterschrift
        ("kurz", "weiter"),                                                  # zu kurze Zeile (Beschriftung)
        (f"{LANG} und", "# 2 Neues Kapitel"),                                # Ueberschrift
    ])
    def test_kein_verbinden(self, ende, anfang):
        text = p.seiten_zu_text([ende, anfang], labels=["11", "12"])
        assert "\n\n<!-- Seite 12 (PDF 2) -->\n" in text

    def test_lesezeichen_eine_seite_zu_frueh(self):
        """Steht der Titel erst auf der naechsten Seite, kommt die Ueberschrift dorthin."""
        seiten = ["Ende des Kapitels 9. Schluss.", "10.1 Grundbegriffe des Abschnitts\nText dazu."]
        text = p.seiten_zu_text(seiten, {0: [(1, "10.1 Grundbegriffe des Abschnitts")]}, labels=["583", "584"])
        teil2 = text.split("<!-- Seite 584 (PDF 2) -->")[1]
        assert "## 10.1 Grundbegriffe des Abschnitts" in teil2


class TestSeitenzahlAnTrennung:
    def test_seitenzahl_klebt_an_weicher_trennung(self):
        """Norm: "die Zugfestig\ufffe52" am Seitenende; vorher entstand "Zugfestig52"."""
        seiten = [f"{LANG}\nText der Seite {i} mit einem Satz.\n{i + 40}" for i in range(1, 9)]
        seiten.insert(4, f"{LANG}\nfür die Zugfestig\ufffe45")
        seiten.insert(5, "keitsprüfung der Bauteile.\n46")
        text = p.seiten_zu_text(seiten)
        assert "Zugfestig45" not in text and "Zugfestig" in text
        assert "<!-- Seite 45 (PDF 5) -->" in text


class TestKolumnentitel:
    def test_lebender_kolumnentitel_mit_seitenzahl(self):
        """Kopfzeilen mit wechselndem Abschnittstitel und Seitenzahl verschwinden, wenn das Buch sie durchgehend hat."""
        seiten = []
        for n in range(10, 22):
            kopf = f"{n} 1 Einleitung" if n % 2 == 0 else f"1.{n} Abschnitt Nummer {n} {n}"
            seiten.append(f"{kopf}\nText der Seite {n} mit einem vollstaendigen Satz.")
        text = p.seiten_zu_text(seiten, labels=[str(n) for n in range(10, 22)])
        assert "Einleitung" not in text and "Abschnitt Nummer" not in text
        assert text.count("Text der Seite") == 12

    def test_einzelne_zeile_mit_zahl_bleibt(self):
        seiten = [f"Text der Seite {n} mit einem Satz." for n in range(10, 22)]
        seiten[3] = "13 Bauteile sind betroffen.\n" + seiten[3]
        text = p.seiten_zu_text(seiten, labels=[str(n) for n in range(10, 22)])
        assert "13 Bauteile sind betroffen." in text
