"""Zeichenkorrektur auf Zeichenebene (PDFium).

Fehler, die an einer Schrift haengen und im fertigen Text nicht mehr sicher zu erkennen sind. Gefunden an DIN-Normen,
treten aber genauso in Buechern auf (Word-PDFs mit Symbol-Schrift, alte Satzsysteme):

1. Akzente als eigenes Zeichen: moderne DIN-PDFs (Schrift Cambria, ab etwa 2024) setzen "ü" als "u" + U+0308, und
   PDFium erzeugt danach ein Leerzeichen, das im PDF nicht steht ("fü r", "prü fung", 500 bis 1000 Mal je Norm).
   Das erzeugte Leerzeichen faellt weg; das Zusammenfuegen zu "ü" macht die NFC-Normalisierung in pdf2md.
2. Falsch zugeordnete Akzente fuer Grossbuchstaben in derselben Schrift: "Aǆ nderungen" (U+01C6 statt Trema),
   "EƵ preuve" (U+01B5 statt Akut). Sie werden zum kombinierenden Akzent, das erzeugte Leerzeichen danach faellt weg.
3. Symbol- und Wingdings-Schriften liefern Zeichen aus dem privaten Unicodebereich (U+F020 bis U+F0FF, U+F8E7).
   Die werden nach der Kodierung der Schrift in echte Zeichen uebersetzt (Aufzaehlungsstrich, Pfeil, griech. Buchstabe).
4. Schriften, deren Text als Mac-Roman statt Windows-1252 gelesen wird (DIN-PDFs um 2004/2005): "f¸r", "Europ‰isch",
   "schweiflen". Erkannt je Schrift an Zeichen wie ‰ ¸ ˆ mitten im Wort, OHNE intakte Umlaute in derselben Schrift;
   dann wird jedes Zeichen ab 0x80 dieser Schrift umkodiert.
5. Doppelt gedruckter Text: manche PDFs enthalten Tabellen oder Absaetze zweimal an derselben Stelle (gemessen:
   290.000 und 260.000 Zeichen in zwei Buechern), Formelsatz verdoppelt Kursivglyphen ("𝑁𝑁1,Ed"). Verdacht,
   wenn viele laengere Zeilen oder Formelzeichen doppelt vorkommen; entfernt werden nur ganze Zeilen, die fast
   vollstaendig schon an derselben Position stehen (siehe _doppelt_gedruckt).

Nur Seiten mit Verdacht (verdaechtig()) werden zeichenweise gelesen, alle anderen bleiben unberuehrt.
"""

import ctypes
import re
from collections import Counter

import pypdfium2.raw as raw

# ---------------------------------------------------------------- Verdacht (am Text von get_text_range)
_VERDACHT = re.compile(
    r"[\u0300-\u036f] "                         # Akzent, danach ein (erzeugtes) Leerzeichen
    r"|[ƵǄ-ǌ]"                   # falsch zugeordnete Grossbuchstaben-Akzente
    r"|[\uf020-\uf0ff\uf8e5-\uf8ff]"            # Symbol/Wingdings im privaten Unicodebereich
    r"|[^\W\d_][‰¸ˆ]|[‰¸ˆ][^\W\d_]")             # Mac-Roman statt Windows-1252


MIN_DOPPELTE_ZEILEN = 3        # so viele laengere Zeilen muessen doppelt vorkommen, damit eine Seite geprueft wird
MIN_ANTEIL_DOPPELT = 0.9       # so viel einer Zeile muss an derselben Stelle schon stehen, damit sie als Kopie wegfaellt


def doppelte_zeilen(text: str) -> bool:
    """Kommen auffaellig viele laengere Zeilen doppelt vor? Hinweis auf doppelt gedruckten Text (manche PDFs enthalten
    Tabellen oder ganze Absaetze zweimal an derselben Stelle). Nur ein Verdacht: entfernt wird spaeter nur, was
    Zeichen fuer Zeichen an derselben Position steht."""
    zeilen = [z.strip() for z in text.replace("\r", "\n").split("\n") if len(z.strip()) >= 8]
    if len(zeilen) < 2 * MIN_DOPPELTE_ZEILEN:
        return False
    doppelt = sum(n - 1 for n in Counter(zeilen).values() if n > 1)
    return doppelt >= MIN_DOPPELTE_ZEILEN and doppelt >= 0.1 * len(zeilen)


# Mathematische Kursivbuchstaben doppelt ("𝑁𝑁1,Ed", "𝜃𝜃"): Formelsatz (Cambria Math) mit doppelt gezeichneten Glyphen
DOPPELTE_MATHEZEICHEN = re.compile(r"([\U0001D400-\U0001D7FF])\1")


def doppelt_verdacht(text: str) -> bool:
    return doppelte_zeilen(text) or bool(DOPPELTE_MATHEZEICHEN.search(text))


def verdaechtig(text: str) -> bool:
    return bool(_VERDACHT.search(text)) or doppelt_verdacht(text)


# ---------------------------------------------------------------- Tabellen
# Adobe-Symbol-Kodierung (Code -> Unicode). Der Pfeil-Verlaengerer 0xBE dient in Normen als Aufzaehlungsstrich.
SYMBOL = {
    0x20: " ", 0x21: "!", 0x22: "∀", 0x23: "#", 0x24: "∃", 0x25: "%", 0x26: "&", 0x27: "∋", 0x28: "(", 0x29: ")",
    0x2A: "∗", 0x2B: "+", 0x2C: ",", 0x2D: "−", 0x2E: ".", 0x2F: "/", 0x3A: ":", 0x3B: ";", 0x3C: "<", 0x3D: "=",
    0x3E: ">", 0x3F: "?", 0x40: "≅", 0x5B: "[", 0x5C: "∴", 0x5D: "]", 0x5E: "⊥", 0x5F: "_", 0x60: "‾", 0x7B: "{",
    0x7C: "|", 0x7D: "}", 0x7E: "∼", 0xA0: "€", 0xA1: "ϒ", 0xA2: "′", 0xA3: "≤", 0xA4: "⁄", 0xA5: "∞", 0xA6: "ƒ",
    0xA7: "♣", 0xA8: "♦", 0xA9: "♥", 0xAA: "♠", 0xAB: "↔", 0xAC: "←", 0xAD: "↑", 0xAE: "→", 0xAF: "↓", 0xB0: "°",
    0xB1: "±", 0xB2: "″", 0xB3: "≥", 0xB4: "×", 0xB5: "∝", 0xB6: "∂", 0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBA: "≡",
    0xBB: "≈", 0xBC: "…", 0xBD: "|", 0xBE: "—", 0xBF: "↵", 0xC0: "ℵ", 0xC1: "ℑ", 0xC2: "ℜ", 0xC3: "℘", 0xC4: "⊗",
    0xC5: "⊕", 0xC6: "∅", 0xC7: "∩", 0xC8: "∪", 0xC9: "⊃", 0xCA: "⊇", 0xCB: "⊄", 0xCC: "⊂", 0xCD: "⊆", 0xCE: "∈",
    0xCF: "∉", 0xD0: "∠", 0xD1: "∇", 0xD2: "®", 0xD3: "©", 0xD4: "™", 0xD5: "∏", 0xD6: "√", 0xD7: "⋅", 0xD8: "¬",
    0xD9: "∧", 0xDA: "∨", 0xDB: "⇔", 0xDC: "⇐", 0xDD: "⇑", 0xDE: "⇒", 0xDF: "⇓", 0xE0: "◊", 0xE1: "〈", 0xE2: "®",
    0xE3: "©", 0xE4: "™", 0xE5: "∑", 0xE6: "⎛", 0xE7: "⎜", 0xE8: "⎝", 0xE9: "⎡", 0xEA: "⎢", 0xEB: "⎣", 0xEC: "⎧",
    0xED: "⎨", 0xEE: "⎩", 0xEF: "⎪", 0xF1: "〉", 0xF2: "∫", 0xF3: "⌠", 0xF4: "⎮", 0xF5: "⌡", 0xF6: "⎞", 0xF7: "⎟",
    0xF8: "⎠", 0xF9: "⎤", 0xFA: "⎥", 0xFB: "⎦", 0xFC: "⎫", 0xFD: "⎬", 0xFE: "⎭",
}
SYMBOL.update({0x30 + i: str(i) for i in range(10)})
SYMBOL.update(zip(range(0x41, 0x5B), "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ"))
SYMBOL.update(zip(range(0x61, 0x7B), "αβχδεφγηιϕκλμνοπθρστυϖωξψζ"))
ADOBE_PUA = {0xF8E5: "‾", 0xF8E6: "|", 0xF8E7: "—", 0xF8E8: "®", 0xF8E9: "©", 0xF8EA: "™"}   # Symbol-Zusatzzeichen

# Wingdings: nur die in Dokumenten ueblichen Aufzaehlungs-, Kaestchen-, Pfeil- und Hakenzeichen
WINGDINGS = {
    0x20: " ", 0x6C: "●", 0x6D: "❍", 0x6E: "■", 0x6F: "□", 0x70: "◻", 0x71: "❑", 0x72: "❒", 0x73: "⬧", 0x74: "⧫",
    0x75: "◆", 0x76: "❖", 0x77: "⬥", 0x78: "⌧", 0x9F: "•", 0xA1: "○", 0xA7: "▪", 0xA8: "◻", 0xD8: "➢", 0xDF: "←",
    0xE0: "→", 0xE1: "↑", 0xE2: "↓", 0xE8: "➔", 0xEF: "⇦", 0xF0: "⇨", 0xFB: "✗", 0xFC: "✓", 0xFD: "☒", 0xFE: "☑",
}

AKZENT_FALSCH = {0x01C6: "\u0308", 0x01B5: "\u0301"}      # "Aǆ" -> Ä, "EƵ" -> É (nur nach einem Vokal)
VOKALE = set("AEIOUaeiouYy")
MACROMAN_BEWEIS = set("‰¸ˆ")                            # mitten im Wort nie echt (ä, ü, ö in Mac-Roman gelesen)
UMLAUT_ECHT = set("äöü")                                # in einer falsch gelesenen Schrift unmoeglich (waere Š š Ÿ)
# In Formelschriften ist "ˆ" ein echter Akzent (x-Dach: "xˆ", "Gˆw"), dort nie umkodieren
FORMELSCHRIFT = re.compile(r"CM[A-Z]*\d|CMU|MT2|MTSY|MTMI|MTEX|MathTime|esint|Symbol|STIX|Math", re.IGNORECASE)
MIN_BEWEIS = 5              # so oft muss ein Beweiszeichen mitten in einem Wort stehen ...
MIN_WOERTER = 3             # ... und zwar in so vielen verschiedenen Woertern ("f¸r", "Europ‰ische", "m¸ssen")


def _als_text(codes: list[int]) -> str:
    """Zeichencodes einer Seite als Text; UTF-16-Haelften werden zu Zeichen ausserhalb der Basisebene zusammengesetzt."""
    teile: list[str] = []
    i = 0
    while i < len(codes):
        c = codes[i]
        if 0xD800 <= c <= 0xDBFF and i + 1 < len(codes) and 0xDC00 <= codes[i + 1] <= 0xDFFF:
            teile.append(chr(0x10000 + ((c - 0xD800) << 10) + (codes[i + 1] - 0xDC00)))
            i += 2
            continue
        teile.append("?" if 0xD800 <= c <= 0xDFFF else chr(c))
        i += 1
    return "".join(teile)


def _macroman(zeichen: str) -> str | None:
    try:
        return zeichen.encode("mac_roman").decode("cp1252")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None


class Korrektur:
    """Sammelt je Schrift Hinweise (lernen) und liefert je Seite {Zeichenindex: Ersatz} (korrektur)."""

    def __init__(self) -> None:
        self._puffer = ctypes.create_string_buffer(256)
        self._flags = ctypes.c_int()
        self.beweis: Counter = Counter()        # Schrift -> Mac-Roman-Hinweise (‰ ¸ ˆ mitten im Wort)
        self.woerter: dict[str, set] = {}       # Schrift -> verschiedene Woerter mit Hinweis
        self.gegen: Counter = Counter()         # Schrift -> intakte Umlaute
        self.zaehler: Counter = Counter()       # akzente, symbole, macroman (ersetzte Zeichen)
        self._entscheidung: dict[str, bool] = {}

    def _schrift(self, tp, k: int) -> str:
        laenge = raw.FPDFText_GetFontInfo(tp, k, self._puffer, len(self._puffer), ctypes.byref(self._flags))
        return self._puffer.value.decode("latin-1", "replace").split("+")[-1] if laenge > 0 else "?"

    def lernen(self, tp) -> None:
        """Mac-Roman-Hinweise je Schrift zaehlen (muss fuer alle verdaechtigen Seiten VOR korrektur() laufen)."""
        n = tp.count_chars()
        text = "".join(chr(c) if c < 0xD800 or c > 0xDFFF else "?" for c in (raw.FPDFText_GetUnicode(tp, k)
                                                                            for k in range(n)))
        for k, z in enumerate(text):
            if z in MACROMAN_BEWEIS:
                # nur mitten im Wort: Buchstabe davor, Kleinbuchstabe danach ("f¸r"), nicht "xˆ" (x-Dach)
                if 0 < k < n - 1 and text[k - 1].isalpha() and text[k + 1].islower():
                    a, b = k, k + 1
                    while a > 0 and text[a - 1].isalpha():
                        a -= 1
                    while b < n and (text[b].isalpha() or text[b] in MACROMAN_BEWEIS):
                        b += 1
                    name = self._schrift(tp, k)
                    self.beweis[name] += 1
                    self.woerter.setdefault(name, set()).add(text[a:b])
            elif z in UMLAUT_ECHT:
                self.gegen[self._schrift(tp, k)] += 1

    def macroman_schrift(self, name: str) -> bool:
        if name not in self._entscheidung:
            self._entscheidung[name] = (self.beweis[name] >= MIN_BEWEIS and self.gegen[name] == 0
                                        and len(self.woerter.get(name, ())) >= MIN_WOERTER
                                        and not FORMELSCHRIFT.search(name))
        return self._entscheidung[name]

    def korrektur(self, tp) -> dict[int, str]:
        """{Zeichenindex: Ersatztext} fuer eine Seite; "" heisst: Zeichen weglassen."""
        n = tp.count_chars()
        codes = [raw.FPDFText_GetUnicode(tp, k) for k in range(n)]
        ersatz: dict[int, str] = {}
        schriften: dict[int, str] = {}
        for k, code in enumerate(codes):
            if code == 32 and 2 <= k < n - 1 and self._wortinneres(codes, k) and raw.FPDFText_IsGenerated(tp, k) == 1:
                ersatz[k] = ""                                  # von PDFium erzeugtes Leerzeichen nach einem Umlaut
                self.zaehler["akzente"] += 1
                continue
            if code in AKZENT_FALSCH and k and chr(codes[k - 1]) in VOKALE:
                ersatz[k] = AKZENT_FALSCH[code]
                self.zaehler["akzente"] += 1
            elif code == 0x66 and self.beweis and k + 1 < n and codes[k + 1] == 0x6C and self._eine_glyphe(tp, k) \
                    and self.macroman_schrift(self._schrift(tp, k)):
                ersatz[k], ersatz[k + 1] = "ß", ""              # "ﬂ" ist in Mac-Roman das "ß" (PDFium zerlegt es in f+l)
                self.zaehler["macroman"] += 1
            elif 0xF020 <= code <= 0xF0FF or code in ADOBE_PUA:
                name = schriften.setdefault(k, self._schrift(tp, k)).lower()
                neu = None
                if code in ADOBE_PUA:
                    neu = ADOBE_PUA[code]
                elif "wingding" in name:
                    neu = WINGDINGS.get(code - 0xF000)
                elif "symbol" in name:
                    neu = SYMBOL.get(code - 0xF000)
                if neu is not None:
                    ersatz[k] = neu
                    self.zaehler["symbole"] += 1
            elif code >= 0x80 and not 0xD800 <= code <= 0xDFFF and self.beweis:
                if self.macroman_schrift(self._schrift(tp, k)):
                    neu = _macroman(chr(code))
                    if neu is not None and neu != chr(code):
                        ersatz[k] = neu
                        self.zaehler["macroman"] += 1
        if doppelt_verdacht(_als_text(codes)):
            for k in self._doppelt_gedruckt(tp, codes):
                ersatz[k] = ""
        return ersatz

    def _doppelt_gedruckt(self, tp, codes: list[int]) -> set[int]:
        """Die zweite Kopie doppelt gedruckten Textes: ganze Zeilen (im Zeichenstrom), deren sichtbare Zeichen zu
        mindestens MIN_ANTEIL_DOPPELT mit gleichem Code an derselben Stelle schon in einer frueheren Zeile stehen.
        Bewusst zeilenweise und nicht Zeichen fuer Zeichen: eine aufgeloeste Ligatur (f, f, i mit demselben Rahmen)
        galt sonst als Kopie ("Effizienz" -> "Efizienz"), und zwei verschiedene Texte uebereinander (korrigierte Fassung
        ueber der alten) wurden zu Buchstabensalat; solche Zeilen bleiben jetzt beide stehen.
        Dazu doppelt gezeichnete Formelzeichen ausserhalb der Basisebene ("𝑁𝑁1,Ed"): von zwei gleichen, direkt
        aufeinander folgenden Zeichen mit demselben Rahmen faellt das zweite weg."""
        links, rechts, unten, oben = (ctypes.c_double() for _ in range(4))
        leer = (32, 9, 10, 13, 0xA0)

        def rahmen(k: int) -> tuple[float, float] | None:
            if not raw.FPDFText_GetCharBox(tp, k, links, rechts, unten, oben):
                return None
            return round(links.value, 1), round(unten.value, 1)

        zeilen: list[list[int]] = [[]]
        for k, code in enumerate(codes):
            zeilen[-1].append(k)
            if code in (10, 13):
                zeilen.append([])
        gesehen: set = set()
        weg: set[int] = set()
        for zeile in zeilen:
            schluessel = []
            for k in zeile:
                if codes[k] in leer or raw.FPDFText_IsGenerated(tp, k) == 1:
                    continue
                r = rahmen(k)
                if r is not None:
                    schluessel.append((codes[k], r))
            if len(schluessel) >= 3 and sum(s in gesehen for s in schluessel) >= MIN_ANTEIL_DOPPELT * len(schluessel):
                weg.update(k for k in zeile if codes[k] not in (10, 13))
                continue
            gesehen.update(schluessel)
        # doppelt gezeichnete Formelzeichen: UTF-16-Paar k, k+1 und gleiches Paar k+2, k+3 an derselben Stelle
        k = 0
        while k + 3 < len(codes):
            paar = codes[k:k + 2]
            if (0xD835 == paar[0] and 0xDC00 <= paar[1] <= 0xDFFF and codes[k + 2:k + 4] == paar
                    and k not in weg and rahmen(k) is not None and rahmen(k) == rahmen(k + 2)):
                weg.update((k + 2, k + 3))
                k += 4
                continue
            k += 1
        self.zaehler["doppelt"] += sum(1 for k in weg if codes[k] not in leer and not 0xDC00 <= codes[k] <= 0xDFFF)
        return weg

    @staticmethod
    def _wortinneres(codes: list[int], k: int) -> bool:
        """Steht das Leerzeichen k mitten in einem deutschen Wort mit Umlaut ("fu¨ r", "Aǆ nderung")? Nur das Trema
        (U+0308) auf a/o/u zaehlt, und danach muss ein Kleinbuchstabe folgen. Andere Akzente bleiben unberuehrt:
        in Formeln ist das Leerzeichen nach "Q\u0307" oder "ū" echt ("Q\u0307 Wärmestrom")."""
        vor, basis, nach = codes[k - 1], codes[k - 2], chr(codes[k + 1])
        if not (nach.islower() or nach == "ß"):
            return False
        if vor == 0x308:
            return chr(basis) in "aouAOU"
        return vor in AKZENT_FALSCH and chr(basis) in VOKALE

    @staticmethod
    def _eine_glyphe(tp, k: int) -> bool:
        """Kommen die Zeichen k und k+1 aus derselben Glyphe (gleicher Rahmen, z.B. eine zerlegte Ligatur)?"""
        a = [ctypes.c_double() for _ in range(4)]
        b = [ctypes.c_double() for _ in range(4)]
        if not (raw.FPDFText_GetCharBox(tp, k, *a) and raw.FPDFText_GetCharBox(tp, k + 1, *b)):
            return False
        return all(abs(x.value - y.value) < 0.01 for x, y in zip(a, b))

    def statistik(self) -> dict:
        return dict(self.zaehler)


def zeichen_lesen(tp, start: int, ende: int, ersatz: dict[int, str]) -> str:
    """Text der Zeichen start..ende wie get_text_range, aber mit den Ersetzungen (Zeichen fuer Zeichen gelesen)."""
    teile: list[str] = []
    tp = getattr(tp, "raw", tp)         # rohes Handle: schneller als der Umweg ueber _as_parameter_
    i = start
    while i < ende:
        if i in ersatz:
            teile.append(ersatz[i])
            i += 1
            continue
        if raw.FPDFText_GetTextIndexFromCharIndex(tp, i) == -1:
            i += 1                                          # get_text_range laesst dieses Zeichen aus (z.B. \x03)
            continue
        code = raw.FPDFText_GetUnicode(tp, i)
        i += 1
        if code == 2:
            teile.append("\ufffe")                           # so liefert get_text_range den Trennstrich
        elif 0xD800 <= code <= 0xDBFF and i < ende and 0xDC00 <= raw.FPDFText_GetUnicode(tp, i) <= 0xDFFF:
            teile.append(chr(0x10000 + ((code - 0xD800) << 10) + (raw.FPDFText_GetUnicode(tp, i) - 0xDC00)))
            i += 1
        elif 0xD800 <= code <= 0xDFFF:
            teile.append("�")
        elif code:
            teile.append(chr(code))
    return "".join(teile)


def statistik_text(s: dict) -> str:
    teile = []
    if s.get("akzente"):
        teile.append(f"{s['akzente']} Akzentfehler (z.B. 'fü r')")
    if s.get("symbole"):
        teile.append(f"{s['symbole']} Symbolzeichen")
    if s.get("macroman"):
        teile.append(f"{s['macroman']} Zeichen aus falscher Kodierung (Mac-Roman)")
    if s.get("doppelt"):
        teile.append(f"{s['doppelt']} doppelt gedruckte Zeichen")
    return ", ".join(teile) + " korrigiert" if teile else ""
