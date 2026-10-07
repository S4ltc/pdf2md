"""Zeichenkorrektur (zeichen.py): Umlaut-Leerzeichen, falsche Grossbuchstaben-Akzente, Symbol-/Wingdings-Schriften und
Texte in Mac-Roman statt Windows-1252. Die PDFium-Aufrufe werden durch eine nachgebaute Textseite ersetzt, so laesst
sich genau festlegen, welches Zeichen erzeugt ist, zu welcher Schrift es gehoert und wo es steht."""

import unicodedata

import pytest

import pdf2md as p
import zeichen


class Seite:
    """Nachgebaute PDFium-Textseite: Liste von Zeichen mit Schrift, 'erzeugt' (von PDFium eingefuegtes Leerzeichen),
    Rahmen und 'ausgelassen' (liefert get_text_range nicht)."""

    def __init__(self, text: str, schrift: str = "Cambria", erzeugt=(), schriften=None, rahmen=None, ausgelassen=()):
        self.zeichen = [{"c": c, "gen": k in erzeugt, "font": (schriften or {}).get(k, schrift),
                         "box": (rahmen or {}).get(k, (float(k), float(k) + 1, 0.0, 10.0)), "weg": k in ausgelassen}
                        for k, c in enumerate(text)]

    def count_chars(self) -> int:
        return len(self.zeichen)


class RawNachbau:
    @staticmethod
    def FPDFText_GetUnicode(tp, k):
        return ord(tp.zeichen[k]["c"])

    @staticmethod
    def FPDFText_IsGenerated(tp, k):
        return 1 if tp.zeichen[k]["gen"] else 0

    @staticmethod
    def FPDFText_GetFontInfo(tp, k, puffer, laenge, flags):
        name = tp.zeichen[k]["font"].encode("latin-1")
        puffer.value = name
        return len(name) + 1

    @staticmethod
    def FPDFText_GetCharBox(tp, k, links, rechts, unten, oben):
        links.value, rechts.value, unten.value, oben.value = tp.zeichen[k]["box"]
        return 1

    @staticmethod
    def FPDFText_GetTextIndexFromCharIndex(tp, k):
        return -1 if tp.zeichen[k]["weg"] else k


@pytest.fixture(autouse=True)
def nachbau(monkeypatch):
    monkeypatch.setattr(zeichen, "raw", RawNachbau)


def korrigiert(seite: Seite, korrektur: zeichen.Korrektur | None = None) -> str:
    k = korrektur or zeichen.Korrektur()
    return unicodedata.normalize("NFC", zeichen.zeichen_lesen(seite, 0, seite.count_chars(), k.korrektur(seite)))


def leerzeichen_nach(text: str, vor: str) -> set[int]:
    """Index des Leerzeichens direkt hinter dem ersten Vorkommen von vor."""
    return {text.index(vor) + len(vor)}


class TestUmlautLeerzeichen:
    def test_erzeugtes_leerzeichen_nach_trema_faellt_weg(self):
        text = "fu\u0308 r die Pru\u0308 fung"
        erzeugt = leerzeichen_nach(text, "fu\u0308") | leerzeichen_nach(text, "Pru\u0308")
        assert korrigiert(Seite(text, erzeugt=erzeugt)) == "für die Prüfung"

    def test_echtes_leerzeichen_bleibt(self):
        assert korrigiert(Seite("Menu\u0308 aus")) == "Menü aus"          # nicht erzeugt: steht so im PDF

    def test_vor_grossbuchstaben_bleibt_es(self):
        text = "Mu\u0308 Nord"
        assert korrigiert(Seite(text, erzeugt=leerzeichen_nach(text, "Mu\u0308"))) == "Mü Nord"

    def test_formelakzente_bleiben_unberuehrt(self):
        """Q-Punkt und u-Strich: dort ist das Leerzeichen echt ("Q\u0307 Wärmestrom", "ū werden")."""
        text = "Q\u0307 waerme und u\u0304 werden"
        erzeugt = leerzeichen_nach(text, "Q\u0307") | leerzeichen_nach(text, "u\u0304")
        assert korrigiert(Seite(text, erzeugt=erzeugt)) == unicodedata.normalize("NFC", text)

    def test_franzoesisches_a_mit_akzent_bleibt(self):
        text = "Soudage a\u0300 l'arc"
        assert korrigiert(Seite(text, erzeugt=leerzeichen_nach(text, "a\u0300"))) == "Soudage à l'arc"

    def test_falscher_grossbuchstaben_akzent(self):
        text = "aller Aǆ nderungen, Oǆ sterreich, EƵ preuve"
        erzeugt = leerzeichen_nach(text, "Aǆ") | leerzeichen_nach(text, "Oǆ") | leerzeichen_nach(text, "EƵ")
        assert korrigiert(Seite(text, erzeugt=erzeugt)) == "aller Änderungen, Österreich, Épreuve"

    def test_statistik(self):
        text = "fu\u0308 r"
        k = zeichen.Korrektur()
        korrigiert(Seite(text, erzeugt=leerzeichen_nach(text, "fu\u0308")), k)
        assert k.statistik() == {"akzente": 1}
        assert "1 Akzentfehler" in zeichen.statistik_text(k.statistik())


class TestSymbolschriften:
    def test_symbol(self):
        assert korrigiert(Seite("\uf061 = 5\uf0b0, \uf0b7 Punkt", schrift="SymbolMT")) == "α = 5°, • Punkt"

    def test_wingdings(self):
        assert korrigiert(Seite("ja \uf06f nein \uf06f \uf0e0 weiter", schrift="Wingdings-Regular")) == \
            "ja □ nein □ → weiter"

    def test_aufzaehlungsstrich_der_normen(self):
        """U+F8E7 (Pfeil-Verlaengerer der Symbol-Schrift) steht in Normen als Aufzaehlungsstrich."""
        assert korrigiert(Seite("\uf8e7 Teil 1\n\uf0be Teil 2", schrift="Symbol")) == "— Teil 1\n— Teil 2"

    def test_andere_schrift_bleibt(self):
        """Ein Zeichen aus dem privaten Bereich einer unbekannten Schrift ist nicht sicher zu deuten."""
        assert korrigiert(Seite("x \uf061 y", schrift="Arial")) == "x \uf061 y"

    def test_verdacht_am_text(self):
        assert zeichen.verdaechtig("• \uf0b7 Text") and not zeichen.verdaechtig("normaler Text für alle")


MACROMAN_TEXT = ("Die Europ‰ische Norm gilt f¸r St‰hle. Die Pr¸fung muss durchgef¸hrt werden, "
                 "Ñharmonisierte Normì und Schweiﬂnaht ó nur so.")


class TestMacRoman:
    def lernen(self, seite: Seite) -> zeichen.Korrektur:
        k = zeichen.Korrektur()
        k.lernen(seite)
        return k

    def test_umkodiert(self):
        seite = Seite(MACROMAN_TEXT, schrift="Arial")
        k = self.lernen(seite)
        assert k.macroman_schrift("Arial")
        assert korrigiert(seite, k) == ("Die Europäische Norm gilt für Stähle. Die Prüfung muss durchgeführt werden, "
                                        "„harmonisierte Norm“ und Schweißnaht — nur so.")

    def test_zerlegte_fl_ligatur_ist_ein_sz(self):
        """PDFium zerlegt das Mac-Roman-"ﬂ" (= ß) in f + l mit gleichem Rahmen; ein echtes "fl" hat zwei Rahmen."""
        text = "Die Europ‰ische Norm f¸r St‰hle und Pr¸fung: Schweifl und Oberfl‰che"
        f = text.index("Schweifl") + len("Schwei")
        rahmen = {f: (50.0, 55.0, 0.0, 10.0), f + 1: (50.0, 55.0, 0.0, 10.0)}   # f und l aus einer Glyphe
        seite = Seite(text, schrift="Arial", rahmen=rahmen)
        erg = korrigiert(seite, self.lernen(seite))
        assert "Schweiß und Oberfläche" in erg

    def test_formelschrift_mit_dach_akzent_bleibt(self):
        """In TeX-Schriften ist "ˆ" das Dach ueber einer Variablen (xˆ, Gˆw), keine Kodierungspanne."""
        seite = Seite("Gˆw und Gˆw sowie xˆa, yˆb, zˆc und aˆbc", schrift="CMR10")
        k = self.lernen(seite)
        assert not k.macroman_schrift("CMR10")
        assert korrigiert(seite, k) == "Gˆw und Gˆw sowie xˆa, yˆb, zˆc und aˆbc"

    def test_schrift_mit_echten_umlauten_bleibt(self):
        seite = Seite(MACROMAN_TEXT + " Und hier ein echtes für.", schrift="Arial")
        assert not self.lernen(seite).macroman_schrift("Arial")

    def test_zu_wenig_hinweise(self):
        seite = Seite("Nur ein f¸r hier.", schrift="Arial")
        assert not self.lernen(seite).macroman_schrift("Arial")

    def test_andere_schrift_auf_der_seite_bleibt(self):
        text = MACROMAN_TEXT + " ‰"
        schriften = {len(text) - 1: "Times"}                   # das Promille-Zeichen gehoert zu einer anderen Schrift
        seite = Seite(text, schrift="Arial", schriften=schriften)
        assert korrigiert(seite, self.lernen(seite)).endswith(" ‰")


class TestDoppeltGedruckt:
    BLOCK = "Werkstoff Dichte\nStahl 7,85 g/cm3\nKupfer 8,96 g/cm3\nAluminium 2,70 g/cm3\n"

    def seite(self, kopie_gleiche_stelle=True):
        """Ein Block, danach dieselbe Zeichenfolge noch einmal: an denselben Positionen (doppelte Inhaltsebene) oder
        an anderen (echte Wiederholung im Text)."""
        text = self.BLOCK + self.BLOCK
        n = len(self.BLOCK)
        rahmen = {n + k: (float(k), float(k) + 1, 0.0, 10.0) for k in range(n)} if kopie_gleiche_stelle else {}
        return Seite(text, rahmen=rahmen)

    def test_verdacht(self):
        assert zeichen.doppelte_zeilen(self.BLOCK * 2)
        assert not zeichen.doppelte_zeilen(self.BLOCK + "Ganz anderer Text\nmit neuen Zeilen\nund noch mehr\nEnde")

    def test_kopie_an_derselben_stelle_faellt_weg(self):
        k = zeichen.Korrektur()
        assert korrigiert(self.seite(), k).strip() == self.BLOCK.strip()
        assert k.statistik()["doppelt"] == len(self.BLOCK.replace("\n", "").replace(" ", ""))

    def test_doppelte_formelzeichen(self):
        """Cambria Math: jede Kursivglyphe steht zweimal an derselben Stelle ("𝑁𝑁1,Ed" statt "𝑁1,Ed"). PDFium liefert
        Zeichen ausserhalb der Basisebene als zwei UTF-16-Haelften, die Kopie hat denselben Rahmen."""
        n, theta = "\U0001d441", "\U0001d703"
        assert zeichen.doppelt_verdacht(f"= 0,5{n}{n} sin {theta}{theta}")

        def haelften(z: str) -> str:
            b = z.encode("utf-16-le")
            return "".join(chr(int.from_bytes(b[i:i + 2], "little")) for i in range(0, len(b), 2))

        text = "N = " + haelften(n) * 2 + haelften(theta) * 2 + "1,Ed"
        rahmen = {k: (4.0, 5.0, 0.0, 10.0) for k in range(4, 8)} | {k: (6.0, 7.0, 0.0, 10.0) for k in range(8, 12)}
        assert korrigiert(Seite(text, rahmen=rahmen)) == f"N = {n}{theta}1,Ed"

    def test_aufgeloeste_ligatur_ist_keine_kopie(self):
        """Regression: PDFium loest "ﬃ" in f, f, i mit demselben Rahmen auf; das zweite f ist keine Kopie."""
        zusatz = "Effizienz der Anlage\n"
        text = self.BLOCK + self.BLOCK + zusatz
        n = len(self.BLOCK)
        rahmen = {n + k: (float(k), float(k) + 1, 0.0, 10.0) for k in range(n)}
        f = 2 * n + 1                                              # "E|ffi|zienz": f, f, i aus einer Glyphe
        rahmen.update({f + i: (500.0, 505.0, 0.0, 10.0) for i in range(3)})
        assert korrigiert(Seite(text, rahmen=rahmen)).endswith("Effizienz der Anlage\n")

    def test_zwei_verschiedene_texte_uebereinander_bleiben(self):
        """Regression: eine korrigierte Fassung ueber der alten; nur ein Teil der Zeichen deckt sich. Beide Zeilen
        bleiben vollstaendig, statt dass aus der zweiten Buchstabensalat wird."""
        alt, neu = "Die Gitterparameter sind Winkel\n", "Die Gittergroessen sind Kanten\n"
        text = self.BLOCK + self.BLOCK + alt + neu
        n = len(self.BLOCK)
        rahmen = {n + k: (float(k), float(k) + 1, 0.0, 10.0) for k in range(n)}
        a = 2 * n
        rahmen.update({a + len(alt) + k: (float(a + k), float(a + k) + 1, 0.0, 10.0) for k in range(len(neu))})
        assert korrigiert(Seite(text, rahmen=rahmen)).endswith(alt + neu)

    def test_echte_wiederholung_bleibt(self):
        """Steht derselbe Text an anderer Stelle (andere Position), ist er echter Inhalt."""
        assert korrigiert(self.seite(kopie_gleiche_stelle=False)) == self.BLOCK * 2


class TestZeichenLesen:
    def test_wie_get_text_range(self):
        """Ausgelassene Zeichen (z.B. \\x03) fehlen, der Trennstrich \\x02 wird wie bei PDFium zu U+FFFE."""
        seite = Seite("ab\x03c\x02\nd", ausgelassen={2})
        assert zeichen.zeichen_lesen(seite, 0, seite.count_chars(), {}) == "abc\ufffe\nd"

    def test_ersetzungen(self):
        seite = Seite("abc")
        assert zeichen.zeichen_lesen(seite, 0, 3, {1: "", 2: "XY"}) == "aXY"

    def test_bereich(self):
        seite = Seite("abcdef")
        assert zeichen.zeichen_lesen(seite, 2, 4, {}) == "cd"


class TestBereinigung:
    def test_nfc_und_tabulatoren(self):
        assert p._seite_bereinigen("Pru\u0308fung\tund\tmehr") == "Prüfung und mehr"
