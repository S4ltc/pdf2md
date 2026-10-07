"""Reparatur falsch oder gar nicht lesbarer Zeichen in PDFs (Formelschriften, defekte Umlaute).

Viele Fachbuecher (TeX, Springer-MathTime) haben Formelschriften ohne brauchbare Zeichenzuordnung:
PDFium liefert dort Steuerzeichen oder sogar falsche Buchstaben (z.B. 'D' fuer '=', 'C' fuer '+').
Zwei Wege beheben das, beide arbeiten je Schrift und Zeichen (nicht je Vorkommen):

  A  Glyphnamen aus dem eingebetteten Schriftprogramm (CFF/Type1) lesen, z.B. 'beta' -> 'β'.
     Exakt, aber nur bei Schriften mit vertrauenswuerdigen Namen (LaTeX/Computer Modern).
  B  Formvergleich: das Zeichen wird aus der Seite gerendert und mit Referenzzeichen aus freien
     Schriften (STIX, DejaVu) verglichen. Mehrere Vorkommen stimmen ab. Ersetzt wird nur, wenn
     das gefundene Zeichen deutlich besser passt als das von PDFium gelieferte.

Nicht sicher erkannte Zeichen bleiben unveraendert (spaeter '�').
"""

import ctypes
import math
import re
import sys
from array import array
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as raw
from fontTools.agl import toUnicode
from fontTools.cffLib import CFFFontSet
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader

import lesefolge

try:
    import formelsatz       # Platzhalter unlesbarer Zeichen in Formeln aufloesen
except Exception:           # pragma: no cover
    formelsatz = None

SCHRIFTEN = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "schriften"

# ---------------------------------------------------------------- Einstellungen
# Schriften, deren Zeichenzuordnung nachweislich vertauscht sein kann: hier wird JEDES Zeichen geprueft.
# Bei allen anderen Schriften werden nur unlesbare Steuerzeichen (Code < 32) repariert.
# MathTime-Schriften heissen MT2MIT, MT2SYT, MT2EXA ...: nach "MT2" folgen Buchstaben. Normale Schriften wie
# "TimesNewRomanPSMT2" oder "ArialMT2" enden dagegen darauf und sind KEINE MathTime-Schriften.
VERDAECHTIG = re.compile(r"MT2(?=[A-Za-z])|MTEX|MTMI|MTSY|MathTime", re.IGNORECASE)
MATHESCHRIFT = re.compile(r"MT2(?=[A-Za-z])|MTEX|MTMI|MTSY|MathTime|CM(?:MI|SY|EX|BSY|MIB|MSY|R|BX|TI|SS|TT)\d|"
                          r"MathematicalPi|Symbol|MSAM|MSBM|EUFM|EUSM|Euclid|Mathematica|SFRM|SFMI", re.IGNORECASE)
GROSSE_GLYPHEN = re.compile(r"CMEX|MTEX|MT2EX|MEX\d", re.IGNORECASE)   # Erweiterungsschriften: Groesse ist kein Merkmal
STRICHE = "-–—−‐‑"        # Bindestrich, Gedankenstriche, Minus: fuer die Abstandsregel gilt das als ein Zeichen

MAX_PROBEN = 8            # so viele Vorkommen je Zeichen werden verglichen (Abstimmung)
RENDER_SKALA = 4          # Seiten-Rendering fuer den Vergleich (4 = etwa 290 dpi)
GEO_GEWICHT = 0.5         # Gewicht der Hoehen-/Lagestrafe gegenueber der Formaehnlichkeit
GEO_RELIEF = 0.2          # dasselbe fuer Zeichen, deren Hoehe/Lage je nach Schrift stark abweicht (FORM_ZAEHLT)
MIN_ABSTAND = 0.12        # so viel besser als das Original muss das neue Zeichen passen (nur verdaechtige Schriften)
MIN_WERT = 0.6            # Mindestpunktzahl (Aehnlichkeit minus Geometrie-Strafe)
MIN_MARGE = 0.06          # so viel besser als das zweitbeste Zeichen muss der Sieger sein
# Beide Schwellen sind an zwei unabhaengigen Datensaetzen gemessen (siehe README): mit ihnen gab es bei
# ueber 300 geprueften Zeichen keine einzige falsche Zuordnung; unsichere Zeichen bleiben lieber offen.

GRIECHISCH = "αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩϑϕϖϱςϵ"
OPERATOREN = "±∓×÷·∗•≤≥≠≈≡∼≃∝∞∂∇∑∏∫∬∮√∈∉⊂⊃⊆⊇∪∩∧∨¬∀∃∅→←↑↓↔⇒⇐⇔↦⊥∥°′″‰ℓℏℜℑℵ⟨⟩⌈⌉⌊⌋∠△≪≫≺≻−▲▼"
# MathTime & Co. zeichnen Delta und Nabla als ausgefuellte Dreiecke; Referenz ist nur ein Umriss
ALIAS = {"▲": "Δ", "▼": "∇", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
INTERPUNKTION = "!?.,;:'\"()[]{}/\\|-+=<>~^_*&%#@"          # ohne Gedankenstriche: in Formeln ist es das Minuszeichen
ZIFFERN = "0123456789"
LATEIN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
TEXTZEICHEN = "äöüÄÖÜßé–—„“”‚‘’«»•…§°±×²³µ€"      # deutsche Buecher: weitere Akzentbuchstaben verwechseln sich zu leicht mit ä ö ü
MATHE_SATZ = GRIECHISCH + OPERATOREN + INTERPUNKTION + ZIFFERN + LATEIN
# Textschriften mit Sonderzeichen (Einheiten, Rechenzeichen, Ligaturen) brauchen mehr als nur Umlaute
LIGATUREN_KAND = "ﬁﬂﬀﬃﬄ"
TEXT_SATZ = TEXTZEICHEN + INTERPUNKTION + ZIFFERN + LATEIN + GRIECHISCH + "−·≈≤≥≠∞" + LIGATUREN_KAND
# Erweiterungsschriften (CMEX, MTEX, ...) enthalten nur grosse Operatoren, Wurzeln und Klammern
GROSS_SATZ = "∑∏∫∬∮√()[]{}|‖⌈⌉⌊⌋⟨⟩∐⋃⋂"      # ohne '/' und '\': eine grosse Wurzel sieht aus wie ein langer Schraegstrich
SELTEN = set("∮∬∐")        # in Fachbuechern selten: bei knappen Entscheidungen nicht bevorzugen
# Zeichen, deren Hoehe/Lage in Formelschriften stark von der Referenz abweicht (hochgestellt bzw. mitwachsend):
# hier zaehlt fast nur die Form
FORM_ZAEHLT = set("′″‴°˙¨ˆ˜ˇ¯√")
DIAGNOSE = False           # True: Probenbilder werden zur Kontrolle mit abgelegt (nur fuer Tests)

# TeX-Glyphnamen, die in der Adobe Glyph List fehlen (Weg A)
TEX_NAMEN = {"prime": "′", "greatermuch": "≫", "lessmuch": "≪", "rho1": "ϱ", "phi1": "ϕ", "theta1": "ϑ",
             "sigma1": "ς", "omega1": "ϖ", "epsilon1": "ϵ", "asteriskmath": "∗", "similarequal": "≃",
             "followsequal": "⪰", "precedesequal": "⪯", "lessequal": "≤", "greaterequal": "≥",
             "radicalbig": "√", "radicalBig": "√", "radicalbigg": "√", "radicalBigg": "√",
             "summationdisplay": "∑", "summationtext": "∑", "productdisplay": "∏", "producttext": "∏",
             "integraldisplay": "∫", "integraltext": "∫", "bracketleftbig": "[", "bracketrightbig": "]",
             "parenleftbig": "(", "parenrightbig": ")", "braceleftbig": "{", "bracerightbig": "}"}
STEUERNAMEN = {"NUL", "SOH", "STX", "ETX", "EOT", "ENQ", "ACK", "BEL", "BS", "HT", "LF", "VT", "FF", "CR", "SO", "SI",
               "DLE", "DC1", "DC2", "DC3", "DC4", "NAK", "SYN", "ETB", "CAN", "EM", "SUB", "ESC", "FS", "GS", "RS",
               "US", "DEL"}
ERGAENZUNGSTEILE = re.compile(r"(?:tp|bt|ex|mid|left|right|vertex)$", re.IGNORECASE)   # Klammerstuecke: weglassen


def _schrift_pfad(name: str) -> Path | None:
    pfad = SCHRIFTEN / name
    return pfad if pfad.exists() else None


# ---------------------------------------------------------------- Referenzzeichen (Weg B)
GLYPH_GROESSE = 160
RASTER = 28


def _normiert(v: np.ndarray) -> np.ndarray:
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _auf_raster(werte: np.ndarray) -> np.ndarray:
    """Profil auf RASTER Werte bringen: beim Verkleinern zaehlt das Maximum, beim Vergroessern wird gedehnt."""
    if len(werte) >= RASTER:
        profil = np.array([b.max() for b in np.array_split(werte, RASTER)], dtype=np.float32)
    else:
        profil = np.asarray(werte, dtype=np.float32)[np.arange(RASTER) * len(werte) // RASTER]
    kern = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)              # Glaettung: kleine Verschiebungen zwischen
    return np.convolve(profil, kern / kern.sum(), mode="same")      # Schriften duerfen die Aehnlichkeit nicht zerstoeren


def _vektor(ink: Image.Image) -> np.ndarray | None:
    """Ink-Bild (hell auf dunkel) -> Merkmalsvektor, unabhaengig von Groesse und Strichstaerke.
    Enthaelt das weichgezeichnete Bild sowie Zeilen- und Spaltenprofile (Lage der Balken und Striche)."""
    box = ink.point(lambda p: 255 if p > 70 else 0).getbbox()
    if box is None:
        return None
    ink = ink.crop(box)
    breite, hoehe = ink.size
    # Profile in Originalaufloesung, beim Zusammenfassen zaehlt das Maximum: so bleiben duenne Querstriche erhalten
    roh = np.asarray(ink) > 0.35 * max(int(np.asarray(ink).max()), 1)
    zeilen = _auf_raster(roh.sum(axis=1) / breite)
    spalten = _auf_raster(roh.sum(axis=0) / hoehe)
    faktor = (RASTER - 4) / max(breite, hoehe)
    ink = ink.resize((max(1, round(breite * faktor)), max(1, round(hoehe * faktor))), Image.LANCZOS)
    leinwand = Image.new("L", (RASTER, RASTER), 0)
    leinwand.paste(ink, ((RASTER - ink.width) // 2, (RASTER - ink.height) // 2))
    grau = np.asarray(leinwand, dtype=np.float32)
    binaer = Image.fromarray(((grau > 0.35 * max(grau.max(), 1)) * 255).astype(np.uint8), "L")   # Strich ja/nein
    weich = np.asarray(leinwand.filter(ImageFilter.GaussianBlur(1.1)), dtype=np.float32)
    bin_weich = np.asarray(binaer.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)
    teile = [0.60 * _normiert(weich.ravel()),
             0.40 * _normiert(bin_weich.ravel()),
             0.40 * _normiert(zeilen),          # Zeilenprofil (Lage von Querbalken und Serifen)
             0.40 * _normiert(spalten)]         # Spaltenprofil
    v = np.concatenate(teile)
    return v / np.linalg.norm(v)


def _grosse_komponenten(ink: Image.Image, anteil: float = 0.3) -> Image.Image:
    """Behaelt nur zusammenhaengende Flaechen, die mindestens 'anteil' der groessten haben. Entfernt
    Nachbarzeichen, die in den Rahmen hoher Zeichen (z.B. grosse Wurzel) hineinragen."""
    a = np.asarray(ink)
    maske = a > 90
    hoehe, breite = maske.shape
    etikett = np.zeros(maske.shape, dtype=np.int32)
    flaechen = [0]
    for y in range(hoehe):
        for x in range(breite):
            if maske[y, x] and etikett[y, x] == 0:
                n = len(flaechen)
                etikett[y, x] = n
                stapel, flaeche = [(y, x)], 0
                while stapel:
                    cy, cx = stapel.pop()
                    flaeche += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < hoehe and 0 <= nx < breite and maske[ny, nx] and etikett[ny, nx] == 0:
                                etikett[ny, nx] = n
                                stapel.append((ny, nx))
                flaechen.append(flaeche)
    if len(flaechen) <= 2:
        return ink
    behalten = [i for i in range(1, len(flaechen)) if flaechen[i] >= anteil * max(flaechen)]
    return Image.fromarray(np.where(np.isin(etikett, behalten), a, 0).astype(np.uint8), "L")


class _Referenz:
    """Referenzzeichen aus STIX (aufrecht, kursiv) und DejaVu Sans, je Zeichen mehrere Stile."""

    def __init__(self) -> None:
        stile = [("STIXGeneral.ttf", "s"), ("STIXGeneralItalic.ttf", "k"), ("DejaVuSans.ttf", "d")]
        self.schriften = []
        for datei, kuerzel in stile:
            pfad = _schrift_pfad(datei)
            if pfad:
                cmap = TTFont(str(pfad), lazy=True).getBestCmap()
                self.schriften.append((ImageFont.truetype(str(pfad), GLYPH_GROESSE), set(cmap), kuerzel))
        self.cache: dict[str, list] = {}

    def merkmale(self, zeichen: str) -> list:
        if zeichen in self.cache:
            return self.cache[zeichen]
        eintraege = []
        for schrift, cmap, kuerzel in self.schriften:
            if ord(zeichen) not in cmap:
                continue
            leinwand = Image.new("L", (GLYPH_GROESSE * 3, GLYPH_GROESSE * 3), 0)
            ImageDraw.Draw(leinwand).text((GLYPH_GROESSE, GLYPH_GROESSE * 2), zeichen, font=schrift, fill=255, anchor="ls")
            box = leinwand.getbbox()
            if box is None:
                continue
            vec = _vektor(leinwand)
            if vec is None:
                continue
            basis = GLYPH_GROESSE * 2
            eintraege.append({"vec": vec, "oben": (basis - box[1]) / GLYPH_GROESSE, "unten": (basis - box[3]) / GLYPH_GROESSE,
                              "breite": (box[2] - box[0]) / GLYPH_GROESSE, "hoehe": (box[3] - box[1]) / GLYPH_GROESSE})
        self.cache[zeichen] = eintraege
        return eintraege


_REFERENZ: _Referenz | None = None


def _referenz() -> _Referenz:
    global _REFERENZ
    if _REFERENZ is None:
        _REFERENZ = _Referenz()
    return _REFERENZ


def punktzahl(probe: dict, zeichen: str, geometrie: bool, steuercode: bool = False) -> float:
    """Wie gut passt die gerenderte Probe zu 'zeichen'? Hoeher = besser.
    steuercode: Das Zeichen war ein unlesbarer Steuercode. Dann sind Symbole wahrscheinlicher als
    lateinische Buchstaben (die stehen in diesen Schriften an lesbaren Positionen)."""
    beste = -9.0
    gewicht = GEO_RELIEF if zeichen in FORM_ZAEHLT else GEO_GEWICHT
    for ref in _referenz().merkmale(zeichen):
        wert = float(np.dot(probe["vec"], ref["vec"]))
        wert -= 0.15 * abs(math.log(max(probe["breite"], 1e-3) / max(probe["hoehe"], 1e-3))
                           - math.log(max(ref["breite"], 1e-3) / max(ref["hoehe"], 1e-3)))
        if geometrie:
            wert -= gewicht * (abs(probe["oben"] - ref["oben"]) + abs(probe["unten"] - ref["unten"]))
        beste = max(beste, wert)
    if steuercode and zeichen in LATEIN:
        beste -= 0.1
    if zeichen in SELTEN:
        beste -= 0.15
    return beste


# ---------------------------------------------------------------- Weg A: Glyphnamen aus dem Schriftprogramm
def _name_zu_unicode(name: str) -> str | None:
    if name in STEUERNAMEN or re.fullmatch(r"c\d+", name) or name == ".notdef":
        return None
    if name in TEX_NAMEN:
        return TEX_NAMEN[name]
    text = toUnicode(name)
    return text if text and all(ord(c) >= 32 for c in text) else None


def _cff_encoding(font_objekt) -> list[str] | None:
    """Eingebaute Encoding (Code -> Glyphname) aus dem eingebetteten CFF-Schriftprogramm."""
    beschreiber = font_objekt.get("/FontDescriptor")
    if beschreiber is None:
        return None
    beschreiber = beschreiber.get_object()
    if "/FontFile3" not in beschreiber:
        return None
    import io
    cff = CFFFontSet()
    cff.decompile(io.BytesIO(beschreiber["/FontFile3"].get_object().get_data()), otFont=None)
    top = cff[cff.fontNames[0]]
    return top.Encoding if isinstance(top.Encoding, list) else None


def namen_tabelle(font_objekt) -> dict[int, str]:
    """Code -> Unicode fuer eine Schrift mit vertrauenswuerdigen Glyphnamen. Leer, wenn die Schrift
    eine eigene ToUnicode-Tabelle hat (dann sind die Namen erfahrungsgemaess vertauscht) oder keine Namen liefert."""
    if "/ToUnicode" in font_objekt:
        return {}
    try:
        encoding = _cff_encoding(font_objekt)
    except Exception:
        return {}
    if not encoding:
        return {}
    ergebnis = {}
    for code, name in enumerate(encoding):
        if name and name != ".notdef":
            z = _name_zu_unicode(name)
            if z is not None:
                ergebnis[code] = z
            elif ERGAENZUNGSTEILE.search(name) and not name in STEUERNAMEN:
                ergebnis[code] = ""          # Teilstuecke grosser Klammern: weglassen
    return ergebnis


# ---------------------------------------------------------------- Zeichenlesen mit PDFium
class _SeitenZeichen:
    """Zeichen (Code, Schriftindex) einer Seite, kompakt gespeichert."""
    __slots__ = ("codes", "fonts", "folge")

    def __init__(self) -> None:
        self.codes = array("I")
        self.fonts = array("H")
        self.folge = None       # Bereiche (start, ende, Fortsetzung, harte Grenze) in Lesereihenfolge; None = PDFium-Reihenfolge


class Reparatur:
    def __init__(self, pfad: Path, protokoll=None, spalten: bool = True) -> None:
        self.pfad = str(pfad)
        self.spalten = spalten          # zweispaltige Seiten in Lesereihenfolge (lesefolge.py), muss zu pdf2md passen
        self.protokoll = protokoll or (lambda text: None)
        self.doc = pdfium.PdfDocument(self.pfad)
        self.leser: PdfReader | None = None
        self.fontnamen: list[str] = []
        self._fontindex: dict[str, int] = {}
        self.zuordnung: dict[tuple[int, int], str] = {}      # (Schriftindex, Code) -> Ersatz
        self.quelle: dict[tuple[int, int], str] = {}         # -> "A" / "B"
        self.offen: set[tuple[int, int]] = set()
        self.bewertung: dict[tuple[int, int], tuple[float, float]] = {}   # (beste, zweitbeste) Punktzahl, fuer Tests
        self.gesehen: set[tuple[int, int]] = set()          # (Schriftindex, Code), die im Text wirklich vorkommen
        self.haeufigkeit: Counter = Counter()               # wie oft wurde je (Schriftindex, Code) ersetzt (Diagnose)
        self.ersetzt = 0

    def schliessen(self) -> None:
        self.doc.close()

    def _index(self, name: str) -> int:
        if name not in self._fontindex:
            self._fontindex[name] = len(self.fontnamen)
            self.fontnamen.append(name)
        return self._fontindex[name]

    # -- welche Seiten enthalten verdaechtige Schriften?
    def markierte_seiten(self) -> list[int]:
        self.leser = PdfReader(self.pfad)
        if self.leser.is_encrypted:
            self.leser.decrypt("")
        gemerkt: dict[int, bool] = {}
        seiten = []
        for nr, seite in enumerate(self.leser.pages):
            try:
                schriften = seite["/Resources"].get("/Font", {})
            except Exception:
                continue
            treffer = False
            for obj in schriften.values():
                try:
                    kennung = obj.idnum
                except AttributeError:
                    kennung = id(obj)
                if kennung not in gemerkt:
                    basis = str(obj.get_object().get("/BaseFont", "")).split("+")[-1].lstrip("/")
                    gemerkt[kennung] = bool(MATHESCHRIFT.search(basis))
                treffer = treffer or gemerkt[kennung]
            if treffer:
                seiten.append(nr)
        return seiten

    def _zeichen_der_seite(self, tp) -> _SeitenZeichen:
        z = _SeitenZeichen()
        puffer = ctypes.create_string_buffer(256)
        flags = ctypes.c_int()
        for k in range(tp.count_chars()):
            code = raw.FPDFText_GetUnicode(tp, k)
            if code == 2 and raw.FPDFText_IsHyphen(tp, k) == 1:
                # PDFiums Markierung einer Silbentrennung, kein Zeichen der Schrift: wie get_text_range als U+FFFE, sonst
                # "repariert" der Formvergleich sie in TeX-Schriften zum harten "-" ("zeit-lich")
                code = 0xFFFE
            laenge = raw.FPDFText_GetFontInfo(tp, k, puffer, len(puffer), ctypes.byref(flags))
            name = puffer.value.decode("latin-1", "replace").split("+")[-1] if laenge > 0 else "?"
            z.codes.append(code)
            z.fonts.append(self._index(name))
        return z

    # -- Weg A
    def _weg_a(self, seiten: list[int]) -> None:
        """Fuer Schriften mit vertrauenswuerdigen Glyphnamen: Steuerzeichen exakt zuordnen."""
        if self.leser is None:
            return
        fertig: set[str] = set()
        for nr in seiten:
            try:
                schriften = self.leser.pages[nr]["/Resources"].get("/Font", {})
            except Exception:
                continue
            for obj in schriften.values():
                font = obj.get_object()
                basis = str(font.get("/BaseFont", "")).split("+")[-1].lstrip("/")
                if basis in fertig or basis not in self._fontindex:
                    continue
                fertig.add(basis)
                tabelle = namen_tabelle(font)
                for code, ersatz in tabelle.items():
                    if 0 < code < 32:                                 # nur unlesbare Steuerzeichen
                        schluessel = (self._fontindex[basis], code)
                        self.zuordnung[schluessel] = ersatz
                        self.quelle[schluessel] = "A"

    # -- Weg B
    def _weg_b(self, seiten: list[int], zeichen: dict[int, _SeitenZeichen]) -> None:
        proben: dict[tuple[int, int], list] = defaultdict(list)
        vorkommen: Counter = Counter()
        for nr in seiten:
            sz = zeichen[nr]
            for k, (code, font) in enumerate(zip(sz.codes, sz.fonts)):
                if code in (0, 9, 10, 13, 32, 160, 0xFFFE, 0xFFFF):
                    continue
                name = self.fontnamen[font]
                schluessel = (font, code)
                if schluessel in self.zuordnung:
                    continue
                if not VERDAECHTIG.search(name) and code >= 32:
                    continue
                if code < 32 and code in (2,) and not MATHESCHRIFT.search(name):
                    naechstes = sz.codes[k + 1] if k + 1 < len(sz.codes) else 10
                    if naechstes in (10, 13):
                        continue                                       # Trennstrich am Zeilenende, wird spaeter behandelt
                vorkommen[schluessel] += 1

        # Proben einsammeln: Seite rendern, wenn dort noch Proben fehlen
        for nr in seiten:
            sz = zeichen[nr]
            benoetigt = [k for k, (code, font) in enumerate(zip(sz.codes, sz.fonts))
                         if (font, code) in vorkommen and len(proben[(font, code)]) < MAX_PROBEN
                         and (k + 1 >= len(sz.codes) or code != 2 or sz.codes[k + 1] not in (10, 13)
                              or MATHESCHRIFT.search(self.fontnamen[font]))]
            if not benoetigt:
                continue
            seite = self.doc[nr]
            hoehe_pt = seite.get_height()
            tp = seite.get_textpage()
            bild = None
            l, r, b, t = (ctypes.c_double() for _ in range(4))
            ox, oy = ctypes.c_double(), ctypes.c_double()
            matrix = raw.FS_MATRIX()
            for k in benoetigt:
                schluessel = (sz.fonts[k], sz.codes[k])
                if len(proben[schluessel]) >= MAX_PROBEN:
                    continue
                if bild is None:
                    bild = seite.render(scale=RENDER_SKALA, grayscale=True).to_pil().convert("L")
                raw.FPDFText_GetCharBox(tp, k, l, r, b, t)
                raw.FPDFText_GetCharOrigin(tp, k, ox, oy)
                raw.FPDFText_GetMatrix(tp, k, matrix)
                # TeX-PDFs setzen die Schriftgroesse oft auf 1 und skalieren ueber die Textmatrix
                groesse = raw.FPDFText_GetFontSize(tp, k) * math.sqrt(abs(matrix.a * matrix.d - matrix.b * matrix.c))
                if groesse <= 0 or r.value - l.value < 0.3:
                    continue
                pad = 0.5
                box = (int((l.value - pad) * RENDER_SKALA), int((hoehe_pt - t.value - pad) * RENDER_SKALA),
                       int((r.value + pad) * RENDER_SKALA) + 1, int((hoehe_pt - b.value + pad) * RENDER_SKALA) + 1)
                ausschnitt = bild.crop(box)
                ink = ausschnitt.point(lambda p: 255 - p)
                rand = ink.point(lambda p: 255 if p > 90 else 0).getbbox()
                if rand is None:
                    continue
                if (rand[3] - rand[1]) >= 0.8 * groesse * RENDER_SKALA:       # hohes Zeichen: Nachbarn im Rahmen entfernen
                    ink = _grosse_komponenten(ink)
                    rand = ink.point(lambda p: 255 if p > 90 else 0).getbbox() or rand
                vec = _vektor(ink)
                if vec is None:
                    continue
                basis_y = (hoehe_pt - oy.value) * RENDER_SKALA - box[1]
                proben[schluessel].append({
                    "bild": ausschnitt if DIAGNOSE else None,
                    "vec": vec, "breite": (rand[2] - rand[0]) / (groesse * RENDER_SKALA),
                    "hoehe": (rand[3] - rand[1]) / (groesse * RENDER_SKALA),
                    "oben": (basis_y - rand[1]) / (groesse * RENDER_SKALA),
                    "unten": (basis_y - rand[3]) / (groesse * RENDER_SKALA)})
            tp.close()
            seite.close()

        # Abstimmen
        self.proben = proben        # fuer Diagnose und Tests
        for schluessel, liste in proben.items():
            font, code = schluessel
            if not liste:
                self.offen.add(schluessel)          # keine brauchbare Probe (z.B. Zeichen zu klein oder unsichtbar)
                continue
            name = self.fontnamen[font]
            gross = bool(GROSSE_GLYPHEN.search(name))
            satz = GROSS_SATZ if gross else (MATHE_SATZ if MATHESCHRIFT.search(name) else TEXT_SATZ)
            geometrie = not gross
            summen = {z: sum(punktzahl(p, z, geometrie, code < 32) for p in liste) / len(liste) for z in satz}
            bestes = max(summen, key=summen.get)
            wert = summen[bestes]
            gleichartig = STRICHE if bestes in STRICHE else bestes
            zweit = max((w for z, w in summen.items() if z not in gleichartig), default=-9.0)
            urspruenglich = chr(code) if code >= 32 else None
            original_falsch = False
            if urspruenglich is not None and urspruenglich in summen:
                if bestes == urspruenglich or wert - summen[urspruenglich] < MIN_ABSTAND:
                    continue                                          # das Original passt gut genug: nichts aendern
                if urspruenglich.isalnum() and (bestes in LATEIN or bestes in ZIFFERN):
                    continue                                          # nie einen Buchstaben/eine Ziffer durch einen anderen ersetzen
                original_falsch = True                                # ein anderes Zeichen passt deutlich besser
            if wert < MIN_WERT or wert - zweit < MIN_MARGE:
                self.offen.add(schluessel)
                if original_falsch and not urspruenglich.isalnum():
                    # Das gelieferte Zeichen ist nachweislich falsch, das richtige aber nicht sicher: lieber "unbekannt".
                    # Nie bei Buchstaben und Ziffern: das waere der Verlust echten Textes.
                    self.zuordnung[schluessel] = "�"
                    self.quelle[schluessel] = "?"
                continue
            self.zuordnung[schluessel] = ALIAS.get(bestes, bestes)
            self.quelle[schluessel] = "B"
            self.bewertung[schluessel] = (wert, zweit)

    # -- Text
    def reparieren(self, rohtexte: list[str], alle_seiten: bool = False, weg_a: bool = True,
                   korrekturen: dict[int, dict[int, str]] | None = None) -> list[str]:
        """Gibt die Seitentexte zurueck, bei denen Zeichen ersetzt wurden. Unveraenderte Seiten bleiben.
        korrekturen: {Seite: {Zeichenindex: Ersatz}} aus zeichen.py. Die Seitentexte enthalten sie schon; baut die
        Reparatur eine Seite aus den Zeichen neu auf, muessen sie dort wieder hinein."""
        self.analysieren(rohtexte, alle_seiten, weg_a)
        return self.aufbauen(rohtexte, korrekturen)

    def zuordnung_fuer(self, nr: int):
        """Funktion (Zeichenindex, Code) -> repariertes Zeichen oder None fuer Seite nr (nach analysieren()).
        Gebraucht vom Formelsatz (formelsatz.py), der Formeln vor dem Neuaufbau der Seite setzt."""
        sz = getattr(self, "_zeichen", {}).get(nr)
        if sz is None:
            return None

        def zuordnung(k: int, code: int) -> str | None:
            if k >= len(sz.codes) or sz.codes[k] != code:
                return None
            font = sz.fonts[k]
            if code == 2 and not MATHESCHRIFT.search(self.fontnamen[font]):
                return None                         # \x02 in Textschriften ist der Trennstrich (regelt der Neuaufbau)
            return self.zuordnung.get((font, code))  # in MathTime ist \x02 dagegen der Malpunkt
        return zuordnung

    def analysieren(self, rohtexte: list[str], alle_seiten: bool = False, weg_a: bool = True) -> None:
        """Erster Teil von reparieren(): welche Seiten, welche Zeichen, und die Zuordnung (Weg A und B)."""
        if alle_seiten:
            seiten = list(range(len(rohtexte)))
        else:
            # Seiten mit Formelschriften, ausserdem Seiten mit unlesbaren Steuerzeichen im Text (z.B. °, −, × in einer
            # Textschrift ohne Zuordnung). Das Trennzeichen \x02 erscheint in get_text_range als ￾ und zaehlt nicht.
            unlesbar = re.compile(r"[\x01\x03-\x08\x0e-\x1f]")
            seiten = sorted(set(self.markierte_seiten()) | {nr for nr, t in enumerate(rohtexte) if unlesbar.search(t)})
        self.protokoll(f"{len(seiten)} Seite(n) mit Formelschriften werden geprueft ...")
        zeichen = {}
        for nr in seiten:
            seite = self.doc[nr]
            tp = seite.get_textpage()
            zeichen[nr] = self._zeichen_der_seite(tp)
            if self.spalten:
                zeichen[nr].folge = lesefolge.bereiche(tp)
            self.gesehen.update(zip(zeichen[nr].fonts, zeichen[nr].codes))
            tp.close()
            seite.close()
        if weg_a:
            self._weg_a(seiten)
        self._weg_b(seiten, zeichen)
        self._seiten, self._zeichen = seiten, zeichen

    def _trennzeichen(self, k: int, code: int, fonts, codes, ist_math: dict) -> bool:
        """Ist Zeichen k (Code 2) die weiche Trennung einer Textschrift? Am Zeilenende immer, mitten im Wort, wenn die
        Zuordnung ein Strich ist (dieselbe Regel wie beim Neuaufbau Zeichen fuer Zeichen)."""
        if k < len(codes) and codes[k] == 0xFFFE:                     # PDFium-Trennstrich (_zeichen_der_seite)
            return True
        if code != 2 or k >= len(fonts) or ist_math[fonts[k]]:
            return False
        ersatz = self.zuordnung.get((fonts[k], 2))
        return (ersatz is not None and ersatz in STRICHE) or (ersatz is None and (k + 1 >= len(codes)
                                                                                  or codes[k + 1] in (10, 13)))

    def aufbauen(self, rohtexte: list[str], korrekturen: dict[int, dict[int, str]] | None = None) -> list[str]:
        """Zweiter Teil von reparieren(): baut die betroffenen Seiten mit der Zuordnung neu auf."""
        korrekturen = korrekturen or {}
        seiten, zeichen = self._seiten, self._zeichen
        ergebnis = list(rohtexte)
        ist_math = {i: bool(MATHESCHRIFT.search(name)) for i, name in enumerate(self.fontnamen)}
        for nr in seiten:
            sz = zeichen[nr]
            teile = []
            geaendert = False
            codes, fonts = sz.codes, sz.fonts
            korr = korrekturen.get(nr, {})
            # Bereiche in Lesereihenfolge (zweispaltige Seiten, siehe lesefolge.py), sonst die ganze Seite in PDFium-Reihenfolge
            for start, ende, fortsetzung, hart in (sz.folge or [(0, len(codes), False, False)]):
                if sz.folge and teile:
                    # so trennt auch lesefolge.seitentext: eine harte Grenze braucht IMMER den Marker, auch wenn
                    # (wie fast immer) schon ein natuerlicher Zeilenumbruch dasteht; sonst wie gehabt.
                    endet_schon = teile[-1].endswith(("\n", "\r", "￾"))
                    if hart:
                        teile.append(f"{lesefolge.SPALTENBRUCH}\r\n" if endet_schon else f"\r\n{lesefolge.SPALTENBRUCH}\r\n")
                    elif not endet_schon:
                        teile.append(" " if fortsetzung else "\r\n")
                i = start
                while i < ende:
                    if i in korr:
                        if korr[i]:                 # Korrektur aus zeichen.py (steht so schon im Rohtext)
                            text = korr[i]
                            if "\ue002" in text and formelsatz is not None:
                                # Formel aus formelsatz.py: ihre unlesbaren Zeichen stehen als Platzhalter darin. \x02
                                # einer Textschrift ist auch hier die weiche Trennung (wie unten), nicht "-"
                                text = formelsatz.PLATZHALTER.sub(
                                    lambda m: "\ufffe" if self._trennzeichen(int(m.group(1)), int(m.group(2)), fonts, codes,
                                                                        ist_math) else m.group(0), text)
                                text, n = formelsatz.aufloesen(text, lambda k, c: self.zuordnung.get(
                                    (fonts[k], codes[k])) if k < len(codes) else None)
                                if n:
                                    geaendert = True
                                    self.ersetzt += n
                            teile.append(text)
                        i += 1
                        continue
                    code, font = codes[i], fonts[i]
                    i += 1
                    if code == 2 and not ist_math[font] and (i >= ende or codes[i] in (10, 13)):
                        teile.append("￾")      # Trennstrich am Zeilenende: so liefert ihn auch PDFiums get_text_range
                        continue
                    ersatz = self.zuordnung.get((font, code))
                    if code == 2 and ersatz is not None and ersatz in STRICHE and not ist_math[font]:
                        teile.append("￾")      # das Zeichen ist der Trennstrich der Textschrift (auch mitten im Wort)
                        continue
                    if ersatz is not None:
                        teile.append(ersatz)
                        geaendert = True
                        self.ersetzt += 1
                        self.haeufigkeit[(font, code)] += 1
                    elif 0xD800 <= code <= 0xDBFF and i < ende and 0xDC00 <= codes[i] <= 0xDFFF:
                        # Zeichen ausserhalb der Basisebene (z.B. mathematische Kursivbuchstaben) kommen als 2 Haelften
                        teile.append(chr(0x10000 + ((code - 0xD800) << 10) + (codes[i] - 0xDC00)))
                        i += 1
                    elif 0xD800 <= code <= 0xDFFF:
                        teile.append("�")      # einzelne Haelfte ohne Partner: ungueltig
                    elif code:
                        teile.append(chr(code))     # unlesbar: bleibt als Steuerzeichen, wird spaeter zu '�'
            if geaendert:
                ergebnis[nr] = "".join(teile)
        return ergebnis

    def statistik(self) -> dict:
        """Zeichenarten (je Schrift und Code), die per Glyphname (a) bzw. Formvergleich (b) gefunden wurden,
        die offen blieben, und wie viele Zeichen im Text dadurch ersetzt wurden."""
        gesehen = self.gesehen
        a = sum(1 for k, q in self.quelle.items() if q == "A" and k in gesehen)
        b = sum(1 for k, q in self.quelle.items() if q == "B" and k in gesehen)
        return {"a": a, "b": b, "offen": len(self.offen), "ersetzt": self.ersetzt}
