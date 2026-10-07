"""Formelsatz als LaTeX, nur aus der Lage der Zeichen (keine Bilderkennung).

PDFium liefert Formeln als flachen Text: Indizes und Exponenten stehen auf der Grundlinie ("p1 V1", "10−3" liest sich
wie "10 minus 3"), Brueche zerfallen in Zeilen ("V" / "T0 + t = V0" / "T0"). Dieses Modul rekonstruiert:
- Hoch-/Tiefstellung: kleineres Zeichen ueber/unter der Grundlinie seiner Zeile -> "p$_{1}$", "10$^{−3}$", Fussnoten-
  zeichen "Probenrichtung$^{a}$".
- Brueche: kurze waagerechte Linie (Bruchstrich) mit Zeichen direkt darueber und darunter, die nicht ueber den Strich
  hinausreichen -> "$\\frac{V}{T_{0} + t}$". Die ganze Zeile mit dem Bruch wird in Lesereihenfolge neu gesetzt.
- Wurzeln: "√" mit Strich ueber dem Radikanden -> "\\sqrt{...}".
- Grosse Operatoren mit Grenzen darueber/darunter (∑ ∏ ∫) -> "\\sum_{i=1}^{n}".
Unsichere Formeln (unlesbares Zeichen "�" in einer neu gesetzten Formel, Bruch mit mehrzeiligem Zaehler/Nenner)
bekommen die sichtbare Markierung UNSICHER davor.

Ergebnis ist wie bei zeichen.py und tabellen.py ein Ersatz-Woerterbuch {Zeichenindex: Text}: "" = Zeichen entfaellt.
Ausserhalb einer Formel stehen Hoch-/Tiefstellungen als eigenes "$...$"-Stueck am Zeichen davor; innerhalb von
\\frac{}{} ohne Dollarzeichen."""
from __future__ import annotations

import ctypes
import re
import unicodedata
from dataclasses import dataclass, field

import pypdfium2.raw as raw

UNSICHER = "⚠[Formel unsicher] "
ABSATZ = "\ue001"       # wie lesefolge.SPALTENBRUCH / tabellen.MARKER: pdf2md macht daraus eine Leerzeile
KLEINER = 0.85          # so viel kleiner (relativ zur Zeilenschrift) muss ein Index/Exponent sein
HOCH = 0.15             # Grundlinie so weit (x Schriftgroesse) ueber der Zeile: hochgestellt
TIEF = 0.08             # ... unter der Zeile: tiefgestellt
MAX_BALKEN_DICKE = 1.6  # pt
MIN_BALKEN = 2.0        # pt
MAX_BALKEN = 360.0      # pt
GROSSE_OPERATOREN = {"∑": r"\sum", "∏": r"\prod", "∫": r"\int", "∮": r"\oint", "⋃": r"\bigcup", "⋂": r"\bigcap"}
LATEX_MASKE = str.maketrans({"%": r"\%", "#": r"\#", "&": r"\&", "_": r"\_", "{": r"\{", "}": r"\}", "$": r"\$"})
# frei stehende Akzente ueber dem Buchstaben davor -> kombinierende Zeichen; in Formeln als LaTeX-Akzent
AKZENTE = {"˙": "̇", "¨": "̈", "¯": "̄", "ˆ": "̂", "˜": "̃", "´": "́", "`": "̀",
           "ˇ": "̌"}
LATEX_AKZENTE = {"̇": r"\dot", "̈": r"\ddot", "̄": r"\bar", "̂": r"\hat", "̃": r"\tilde",
                 "⃗": r"\vec", "̌": r"\check", "́": r"\acute", "̀": r"\grave"}
WORT_OPERATOREN = {"lim": r"\lim", "max": r"\max", "min": r"\min", "sup": r"\sup", "inf": r"\inf"}
# TeX-Schrift CMEX: grosse Operatoren liegen auf Buchstabencodes, die die PDF als Buchstaben ausgibt ("Z" statt ∫).
# Die Schrift hat keine Buchstaben, die Zuordnung ist deshalb eindeutig (cmex10-Kodierung).
CMEX = {"P": "∑", "X": "∑", "Q": "∏", "Y": "∏", "R": "∫", "Z": "∫", "H": "∮", "I": "∮", "S": "⋃", "[": "⋃",
        "T": "⋂", "\\": "⋂"}


@dataclass(eq=False, slots=True)
class Teil:
    """Ein Zeichen oder ein schon zusammengesetztes Formelstueck (Bruch, Wurzel, Operator mit Grenzen)."""
    indizes: list[int]          # Zeichenindizes, die darin aufgehen
    text: str
    l: float
    r: float
    b: float
    t: float
    y: float                    # Grundlinie
    g: float                    # Schriftgroesse
    latex: bool = False         # schon LaTeX (Bruch ...), nicht mehr maskieren
    unsicher: bool = False
    folge: int = 0              # Stelle im Zeichenstrom (Lesereihenfolge von PDFium)
    leer_davor: bool = False    # im Strom stand ein Leerzeichen davor
    zeile: int = 0              # PDFium-Zeile
    akzent: bool = False        # ein frei stehender Akzent wurde angehaengt (Text weicht vom Strom ab)


@dataclass
class Seite:
    teile: list[Teil] = field(default_factory=list)


PLATZHALTER = re.compile("\ue002(\\d+):(\\d+)\ue003")


def platzhalter(k: int, code: int) -> str:
    return f"\ue002{k}:{code}\ue003"


def aufloesen(text: str, zuordnung=None) -> tuple[str, int]:
    """Ersetzt die Platzhalter unlesbarer Zeichen: zuordnung(Zeichenindex, Code) liefert das reparierte Zeichen oder
    None; sonst kommt das urspruengliche Steuerzeichen zurueck (pdf2md macht daraus "�"). Gibt (Text, Anzahl
    reparierter Zeichen) zurueck."""
    if "\ue002" not in text:
        return text, 0
    repariert = 0

    def ersetzen(m: re.Match) -> str:
        nonlocal repariert
        k, code = int(m.group(1)), int(m.group(2))
        neu = zuordnung(k, code) if zuordnung else None
        if neu:
            repariert += 1
            return neu.translate(LATEX_MASKE) if neu in "%#&_{}$" else neu
        return chr(code)

    return PLATZHALTER.sub(ersetzen, text), repariert


_NAME = ctypes.create_string_buffer(256)


def _schriftname(tp, k: int) -> str:
    flags = ctypes.c_int()
    try:
        raw.FPDFText_GetFontInfo(tp, k, _NAME, 256, ctypes.byref(flags))
        return _NAME.value.decode("latin-1")
    except Exception:
        return ""


def _groesse(tp, k: int, matrix) -> float:
    g = raw.FPDFText_GetFontSize(tp, k)
    if g <= 1.5 and raw.FPDFText_GetMatrix(tp, k, matrix):   # TeX: Schrift 1 pt, skaliert ueber die Textmatrix
        g *= abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5
    return max(g, 1.0)


def zeichen(tp, ersatz: dict[int, str] | None = None, zuordnung=None) -> list[Teil]:
    """Sichtbare Zeichen der Seite mit Rahmen, Grundlinie und Schriftgroesse. ersatz: Korrekturen aus zeichen.py.
    zuordnung(Zeichenindex, Code): repariertes Zeichen der Formelreparatur (formeln.py) oder None."""
    ersatz = ersatz or {}
    n = tp.count_chars()
    tp = getattr(tp, "raw", tp)         # rohes Handle: spart bei jedem Aufruf den Umweg ueber _as_parameter_
    l, r, b, t = (ctypes.c_double() for _ in range(4))
    x, y = ctypes.c_double(), ctypes.c_double()
    matrix = raw.FS_MATRIX()
    unicode_, textindex = raw.FPDFText_GetUnicode, raw.FPDFText_GetTextIndexFromCharIndex
    rahmen, ursprung, schrift = raw.FPDFText_GetCharBox, raw.FPDFText_GetCharOrigin, raw.FPDFText_GetFontSize
    teile: list[Teil] = []
    leer, zeile = False, 0
    k = 0
    while k < n:
        code = unicode_(tp, k)
        # nur Steuer-/Sonderzeichen koennen im Text fehlen (get_text_range laesst z.B. Code 3 aus); kennt die
        # Formelreparatur das Zeichen (MathTime: Code 2 = Malpunkt), gehoert es dazu, sie setzt es ebenfalls ein
        if (code < 32 or code >= 0xFFF0) and textindex(tp, k) == -1 and not (zuordnung and zuordnung(k, code)):
            k += 1
            continue
        if code in (10, 13):
            zeile += code == 10
            leer = True
            k += 1
            continue
        if code in (32, 9, 0xA0) or ersatz.get(k) == "":
            leer = leer or code in (32, 9, 0xA0)
            k += 1
            continue
        breite = 1
        repariert = zuordnung(k, code) if zuordnung is not None and k not in ersatz else None
        if repariert:
            text = repariert                    # die Formelreparatur kennt das Zeichen ("D" in MathTime ist "=")
        elif code < 32 and k not in ersatz:
            # unlesbare Glyphe: erst die Formelreparatur (formeln.py) kennt das Zeichen; Platzhalter, den sie oder
            # pdf2md spaeter aufloest (sonst stuende das Zeichen fuer immer als Steuerzeichen in der Formel)
            text = platzhalter(k, code)
        elif 0xD800 <= code <= 0xDBFF and k + 1 < n:        # Zeichen ausserhalb der Basisebene (UTF-16-Paar)
            tief_ = raw.FPDFText_GetUnicode(tp, k + 1)
            text = chr(0x10000 + ((code - 0xD800) << 10) + (tief_ - 0xDC00)) if 0xDC00 <= tief_ <= 0xDFFF else "�"
            breite = 2
        else:
            text = chr(code) if not 0xD800 <= code <= 0xDFFF else "�"
        text = ersatz.get(k, text)
        if 0x300 <= ord(text[:1] or " ") <= 0x36F and teile:  # kombinierender Akzent: gehoert zum Zeichen davor
            teile[-1].text += text
            teile[-1].indizes.append(k)
            k += breite
            continue
        if not rahmen(tp, k, l, r, b, t) or not ursprung(tp, k, x, y):
            k += breite
            continue
        g = schrift(tp, k)
        if g <= 1.5:
            g = _groesse(tp, k, matrix)
        neu = Teil([k] + ([k + 1] if breite == 2 else []), text, l.value, r.value, b.value, t.value, y.value,
                   max(g, 1.0), folge=len(teile), leer_davor=leer, zeile=zeile)
        if text in CMEX and neu.t - neu.b > 1.15 * neu.g and _schriftname(tp, k).upper().find("CMEX") >= 0:
            neu.text = CMEX[text]
            neu.akzent = True               # Text weicht vom Zeichenstrom ab: muss als Ersatz geschrieben werden
        vorher = teile[-1] if teile else None
        if (text in AKZENTE and vorher is not None and len(vorher.text) == 1 and vorher.text.isalpha()
                and vorher.l - 0.1 * vorher.g <= (neu.l + neu.r) / 2 <= vorher.r + 0.3 * vorher.g
                and neu.b >= vorher.y + 0.4 * vorher.g):
            # Akzent als eigenes Zeichen ueber dem Buchstaben ("Q˙" fuer den Waermestrom, "u¨" fuer ü): verbinden
            vorher.text += AKZENTE[text]
            vorher.indizes += neu.indizes
            vorher.akzent = True
            k += breite
            continue
        teile.append(neu)
        leer = False
        k += breite
    return teile


def _schreiben(ergebnis: dict[int, str], t: Teil, text: str) -> None:
    """Ersatz fuer ein Teil: Text am ersten Zeichenindex, die weiteren (Akzent, zweite UTF-16-Haelfte) entfallen."""
    ergebnis[t.indizes[0]] = text
    for k in t.indizes[1:]:
        ergebnis[k] = ""


def balken(seite, groessen: list | None = None) -> list[tuple[float, float, float]]:
    """Kurze waagerechte Striche der Seite (Bruchstriche, Wurzelstriche): (y, links, rechts). TeX-PDFs setzen sie oft
    als 0,5 pt hohes Bild statt als Linie (gemessen an einem Lehrbuch), deshalb auch Bilder.
    groessen: bekommt die wirksamen Schriftgroessen der Textobjekte (fuer lohnt())."""
    ergebnis = []
    senkrecht = []
    groesse = ctypes.c_float()
    matrix = raw.FS_MATRIX()
    for obj in seite.get_objects(filter=[raw.FPDF_PAGEOBJ_PATH, raw.FPDF_PAGEOBJ_IMAGE, raw.FPDF_PAGEOBJ_TEXT],
                                 max_depth=3):
        if obj.type == raw.FPDF_PAGEOBJ_TEXT:
            if groessen is not None and raw.FPDFTextObj_GetFontSize(obj.raw, ctypes.byref(groesse)):
                g = groesse.value
                if raw.FPDFPageObj_GetMatrix(obj.raw, ctypes.byref(matrix)):
                    g *= abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5
                groessen.append(round(g, 1))
            continue
        try:
            l, b, r, t = obj.get_bounds()
        except Exception:
            continue
        if t - b <= MAX_BALKEN_DICKE and MIN_BALKEN <= r - l <= MAX_BALKEN:
            ergebnis.append(((b + t) / 2, l, r))
        elif r - l <= 2.5 and t - b >= 4:
            senkrecht.append(((l + r) / 2, b, t))
        elif r - l > 2.5 and t - b > 2.5 and obj.type == raw.FPDF_PAGEOBJ_PATH:
            senkrecht += [(l, b, t), (r, b, t)]                 # Rechteck (Zellrahmen): seine Seitenkanten
    # Tabellenlinien enden an senkrechten Linien oder kreuzen sie; ein Bruchstrich steht frei
    frei = [(y, l, r) for y, l, r in ergebnis
            if not any(v_b - 1 <= y <= v_t + 1 and l - 2 <= x <= r + 2 for x, v_b, v_t in senkrecht)]
    # Gleich lange Striche uebereinander (Zeilenlinien einer Tabelle ohne senkrechte Linien, Dampftafeln) sind keine
    # Bruchstriche: ein dritter Strich gleicher Ausdehnung in der Naehe verraet die Tabelle
    return [s for s in frei
            if sum(1 for u in frei if u is not s and abs(u[1] - s[1]) <= 1.5 and abs(u[2] - s[2]) <= 1.5
                   and abs(u[0] - s[0]) <= 40) < 2]


# ---------------------------------------------------------------- Zeilen und Hoch-/Tiefstellung
def _bezug(teile: list[Teil]) -> tuple[float, float]:
    """(Grundlinie, Schriftgroesse) einer Zeile: die der groessten haeufigen Schrift."""
    gross = max(t.g for t in teile)
    haupt = [t for t in teile if t.g >= KLEINER * gross]
    ys = sorted(t.y for t in haupt)
    return ys[len(ys) // 2], gross


SUCHWEITE = 12         # so viele Zeichen links/rechts wird der groessere Nachbar gesucht ("s" vor "R" und "irr,12")
ANGEHAENGT = 0.2       # so dicht (x Schrift) haengt ein Index am Zeichen davor, auch wenn PDFium ein Leerzeichen erzeugt


def _getrennt(vorher: Teil, t: Teil) -> bool:
    """Steht zwischen zwei Teilen ein echter Wortabstand? PDFium erzeugt Leerzeichen auch zwischen Zeichen und Index
    ("c p iGL" fuer c_p^iGL); die zaehlen nicht, wenn eines der beiden kleiner ist und die Luecke schmal."""
    if not t.leer_davor:
        return False
    luecke, g = t.l - vorher.r, max(t.g, vorher.g)
    if luecke <= 0.12 * g:                      # ueberlappend oder fast beruehrend (Index unter einem Exponenten)
        return False
    klein = t.g <= KLEINER * vorher.g or vorher.g <= KLEINER * t.g
    return not (klein and luecke <= ANGEHAENGT * g)


def _kann_basis(t: Teil) -> bool:
    """Woran ein Index/Exponent haengen kann: Buchstabe, Ziffer, schliessende Klammer, Strich, Formelstueck. Nicht an
    Satzzeichen wie "!" oder "|" (Strichcode der Dokumentnummer auf Norm-Deckblaettern: "!&M|" ueber "3428947")."""
    if t.latex or not t.text:
        return True
    c = t.text[0]
    return c.isalnum() or c in ")]}′″'∗*" or unicodedata.category(c).startswith(("L", "N"))


def _stellungen(folge: list[Teil]) -> list[str]:
    """"hoch", "tief" oder "" je Teil einer Zeile (Lesereihenfolge). Ein kleineres Zeichen wird mit dem naechsten
    groesseren Nachbarn verglichen (erst links, dann rechts), nicht mit der ganzen Zeile: PDFium legt Zaehler, Nenner
    und Gleichheitszeichen manchmal in eine Zeile ("T0 + t = V0"), und Fussnoten nebeneinander ("1Robert ... 3Joseph")."""
    ergebnis = [""] * len(folge)
    if not folge:
        return ergebnis
    gross = max(t.g for t in folge)
    for i, t in enumerate(folge):
        if t.latex or t.g > KLEINER * gross:           # kein groesserer Nachbar moeglich: schnell weiter
            continue
        nachbar = None
        # links: ohne Leerzeichen dazwischen ("Boyle1", "V0", "10−3"); sonst rechts ("1Robert" am Fussnotenanfang)
        for richtung in (-1, 1):
            j = i
            for _ in range(SUCHWEITE):
                if richtung < 0 and j > 0 and _getrennt(folge[j - 1], folge[j]):
                    break
                j += richtung
                if not 0 <= j < len(folge) or (richtung > 0 and _getrennt(folge[j - 1], folge[j])):
                    break
                u = folge[j]
                if u.latex or t.g > KLEINER * u.g:
                    continue                            # gleich kleines Zeichen (Teil desselben Index): weiter
                # Ein Index steht rechts neben seinem Zeichen (ein Fussnotenzeichen links vor dem Wort), nicht darunter:
                # Ziffern unter grossen Strichcode-Zeichen sind keine Indizes
                mitte = (u.l + u.r) / 2
                seitlich = t.l >= mitte - 0.1 if richtung < 0 else t.r <= mitte + 0.1
                # ... und ueberlappt es senkrecht (ein Index reicht ueber die Grundlinie, ein Exponent unter die
                # Oberkante); Ziffern ganz unterhalb eines Zeichens gehoeren nicht dazu
                ueberlappt = (t.t > u.y and t.b < u.t) or not t.text[:1].isalnum()   # Komma im Index sitzt tief
                if seitlich and ueberlappt and abs(mitte - (t.l + t.r) / 2) <= 3 * u.g:
                    nachbar = u
                break
            if nachbar is not None:
                break
        if nachbar is None or not _kann_basis(nachbar):
            continue
        if t.y - nachbar.y > HOCH * nachbar.g:
            ergebnis[i] = "hoch"
        elif nachbar.y - t.y > TIEF * nachbar.g:
            ergebnis[i] = "tief"
    return ergebnis


def _maskiert(t: Teil) -> str:
    """Text eines Teils innerhalb von LaTeX: Sonderzeichen maskiert, Akzent ueber Buchstaben als \\dot{Q} usw."""
    if t.latex:
        return t.text
    text = t.text.translate(LATEX_MASKE)
    if len(text) == 2 and text[1] in LATEX_AKZENTE and text[0].isalpha():
        return f"{LATEX_AKZENTE[text[1]]}{{{text[0]}}}"
    return text


def setzen(teile: list[Teil], in_formel: bool) -> str:
    """Text einer Zeile (Teile in Lesereihenfolge) mit Hoch-/Tiefstellung. in_formel: innerhalb von $...$ (dann
    "x_{1}"), sonst eigene Stuecke ("x$_{1}$")."""
    if not teile:
        return ""
    y, g = _bezug(teile)
    st = _stellungen(teile)
    aus: list[str] = []
    i = 0
    while i < len(teile):
        t = teile[i]
        if i and (_getrennt(teile[i - 1], t) or (not st[i] and not st[i - 1] and t.l - teile[i - 1].r > 0.2 * g)):
            aus.append(" ")
        if not st[i]:
            aus.append(_maskiert(t) if in_formel else t.text)
            i += 1
            continue
        # Index und Exponent am selben Zeichen stehen in x-Richtung durcheinander ("s" mit "R" oben, "irr,12" unten):
        # erst alle Tief-, dann alle Hochstellungen der Gruppe
        tief, hoch = [], []
        j = i
        while j < len(teile) and st[j] and (j == i or not _getrennt(teile[j - 1], teile[j])):
            (hoch if st[j] == "hoch" else tief).append(_maskiert(teile[j]))
            j += 1
        stueck = (f"_{{{''.join(tief)}}}" if tief else "") + (f"^{{{''.join(hoch)}}}" if hoch else "")
        aus.append(stueck if in_formel else f"${stueck}$")
        i = j
    return "".join(aus)


# ---------------------------------------------------------------- Brueche, Wurzeln, Operatoren
def _ueberlappt_waagerecht(t: Teil, l: float, r: float, rand: float) -> bool:
    mitte = (t.l + t.r) / 2
    return l - rand <= mitte <= r + rand


def _zeilen(teile: list[Teil]) -> list[list[Teil]]:
    """Teile nach Grundlinie zu Zeilen gruppiert (oben nach unten), je Zeile von links nach rechts."""
    zeilen: list[list[Teil]] = []
    refs: list[Teil] = []                       # je Zeile das Teil mit der groessten Schrift
    for t in sorted(teile, key=lambda t: -t.y):
        for i in range(len(zeilen) - 1, max(-1, len(zeilen) - 4), -1):   # nur die letzten Zeilen kommen in Frage
            ref = refs[i]
            if abs(ref.y - t.y) <= 0.45 * max(ref.g, t.g) or (t.g < KLEINER * ref.g and abs(ref.y - t.y) <= 0.7 * ref.g):
                zeilen[i].append(t)
                if t.g > ref.g:
                    refs[i] = t
                break
        else:
            zeilen.append([t])
            refs.append(t)
    # Eine Zeile nur aus kleinen Zeichen (Exponent "2" von "m²", oberhalb einsortiert, bevor ihre Zeile kam) gehoert
    # zur benachbarten Zeile mit groesserer Schrift
    i = 0
    while i < len(zeilen):
        nachbarn = [j for j in (i - 1, i + 1) if 0 <= j < len(zeilen) and refs[i].g <= KLEINER * refs[j].g
                    and abs(refs[j].y - refs[i].y) <= 0.7 * refs[j].g]
        if nachbarn:
            j = min(nachbarn, key=lambda j: abs(refs[j].y - refs[i].y))
            zeilen[j].extend(zeilen[i])
            del zeilen[i], refs[i]
            i = max(0, i - 1)
            continue
        i += 1
    return [sorted(z, key=lambda t: t.l) for z in zeilen]


def _innen(teile: list[Teil]) -> tuple[str, bool]:
    """LaTeX fuer Zaehler/Nenner/Radikand; unsicher, wenn er mehrere Zeilen hat oder "�" enthaelt."""
    zeilen = _zeilen(teile)
    text = " ".join(setzen(z, True) for z in zeilen)
    unsicher = len(zeilen) > 1 or "�" in text or any(t.unsicher for t in teile)
    return text.strip(), unsicher


def _sauber_begrenzt(auswahl: list[Teil], alle: list[Teil], l: float, r: float) -> bool:
    """Steht auf der Zeile von Zaehler/Nenner noch Text links/rechts ausserhalb des Strichs, ist es kein Bruch
    (Unterstreichung, Trennlinie ueber Fussnoten, Tabellenlinie)."""
    for z in _zeilen(auswahl):
        y, g = _bezug(z)
        for t in alle:
            # kleinere Schrift daneben (Grenze unter "lim") gehoert nicht zur Zeile von Zaehler/Nenner
            if t in auswahl or abs(t.y - y) > 0.3 * g or t.g < KLEINER * g:
                continue
            if (t.r > l - 1.2 * g and t.r <= l - 0.2 * g) or (t.l < r + 1.2 * g and t.l >= r + 0.2 * g):
                return False
    return True


MAX_ZEILEN_BRUCH = 2    # Zaehler/Nenner mit mehr Zeilen: Tabelle mit Linie darunter, kein Bruch
MAX_LUECKE_BRUCH = 1.5  # groessere Luecke (x Schrift) in Zaehler/Nenner: Tabellenspalten, kein Bruch


def _kompakt(teile: list[Teil]) -> bool:
    """Zaehler und Nenner sind kurz und dicht gesetzt; Tabellenkoepfe ueber einer Linie haben Spaltenluecken."""
    zeilen = _zeilen(teile)
    if len(zeilen) > MAX_ZEILEN_BRUCH:
        return False
    for z in zeilen:
        g = max(t.g for t in z)
        if any(b.l - a.r > MAX_LUECKE_BRUCH * g for a, b in zip(z, z[1:])):
            return False
    return True


def _bruch(b: tuple[float, float, float], teile: list[Teil]) -> Teil | None:
    y, l, r = b
    nahe = [t for t in teile if _ueberlappt_waagerecht(t, l, r, 0.5)]
    if not nahe:
        return None
    g = max(t.g for t in nahe)
    # Zaehler: die Zeile direkt ueber dem Strich (samt ihren Exponenten), Nenner: die Zeile direkt darunter. Mit der
    # Schrift der Umgebung gemessen, denn ein Exponent im Zaehler sitzt hoeher als seine eigene kleine Schrift.
    oben = [t for t in nahe if t.b >= y - 0.3 and t.b - y <= 1.4 * g and t.l >= l - 0.6 * t.g and t.r <= r + 0.6 * t.g]
    unten = [t for t in nahe if t.t <= y + 0.3 and y - t.t <= 1.4 * g and t.l >= l - 0.6 * t.g and t.r <= r + 0.6 * t.g]
    if not oben or not unten or set(map(id, oben)) & set(map(id, unten)):
        return None
    oben = min(_zeilen(oben), key=lambda z: min(t.b for t in z) - y)          # die naechste Zeile ueber dem Strich
    unten = min(_zeilen(unten), key=lambda z: y - max(t.t for t in z))        # die naechste Zeile darunter
    if min(t.b for t in oben) - y > 1.0 * g or y - max(t.t for t in unten) > 1.0 * g:
        return None
    if not _sauber_begrenzt(oben, teile, l, r) or not _sauber_begrenzt(unten, teile, l, r):
        return None
    if not _kompakt(oben) or not _kompakt(unten):
        return None
    # ein Bruchstrich ist kaum laenger als Zaehler oder Nenner; Linien in Tabellen laufen ueber die ganze Zelle
    breite = max(max(t.r for t in oben) - min(t.l for t in oben), max(t.r for t in unten) - min(t.l for t in unten))
    if r - l > breite + 2.0 * g:
        return None
    zaehler, u1 = _innen(oben)
    nenner, u2 = _innen(unten)
    if not zaehler or not nenner:
        return None
    # Fliesstext ueber und unter einer Linie (Ueberschrift, Tabellenkopf "Tabelle 5.6 (Fortsetzung)") ist kein Bruch
    if len(re.findall(r"(?<![\\\w])[^\W\d_]{4,}", zaehler + " " + nenner)) >= 3:
        return None
    alle = oben + unten
    return Teil(sorted(k for t in alle for k in t.indizes), rf"\frac{{{zaehler}}}{{{nenner}}}", l, r,
                min(t.b for t in unten), max(t.t for t in oben), y - 0.25 * g, g, latex=True, unsicher=u1 or u2,
                folge=min(t.folge for t in alle), leer_davor=min(alle, key=lambda t: t.folge).leer_davor)


def _wurzel(b: tuple[float, float, float], teile: list[Teil]) -> Teil | None:
    y, l, r = b
    zeichen_ = [t for t in teile if t.text == "√" and abs(t.r - l) <= 0.6 * t.g and t.b <= y <= t.t + 0.5 * t.g]
    if not zeichen_:
        return None
    w = zeichen_[0]
    radikand = [t for t in teile if t is not w and t.t <= y + 0.5 and y - t.t <= 1.2 * t.g and t.l >= l - 0.3 * t.g
                and t.r <= r + 0.6 * t.g and (t.l + t.r) / 2 >= l]
    if not radikand:
        return None
    innen, unsicher = _innen(radikand)
    alle = [w] + radikand
    return Teil(sorted(k for t in alle for k in t.indizes), rf"\sqrt{{{innen}}}", w.l, r, min(t.b for t in alle),
                y, min(t.y for t in radikand), max(t.g for t in radikand), latex=True, unsicher=unsicher,
                folge=min(t.folge for t in alle), leer_davor=w.leer_davor)


def _anschliessend(start: list[Teil], kandidaten: list[Teil]) -> list[Teil]:
    """Erweitert eine Grenze um die Zeichen, die auf ihrer Zeile direkt anschliessen ("i=1" nach dem "i")."""
    gruppe = sorted(start, key=lambda t: t.l)
    if not gruppe:
        return gruppe
    for t in sorted(kandidaten, key=lambda t: t.l):
        letzter = gruppe[-1]
        if t not in gruppe and abs(t.y - letzter.y) <= 0.3 * t.g and 0 <= t.l - letzter.r <= 0.2 * t.g + 0.5:
            gruppe.append(t)
    return gruppe


def _operator(op: Teil, teile: list[Teil]) -> Teil | None:
    """∑/∏/∫ mit kleinen Grenzen darueber/darunter (Integrale: rechts oben/unten), lim/max/min mit Grenze darunter."""
    breite, hoehe, mitte = op.r - op.l, op.t - op.b, (op.b + op.t) / 2
    klein = [t for t in teile if t is not op and t.g < KLEINER * op.g]
    if op.text in ("∫", "∮"):
        oben = [t for t in klein if op.l + 0.2 * breite <= t.l <= op.r + 0.6 * op.g
                and (t.b + t.t) / 2 > mitte + 0.15 * hoehe and t.b <= op.t + 0.3 * op.g]
        unten = [t for t in klein if op.l <= t.l <= op.r + 0.3 * op.g
                 and (t.b + t.t) / 2 < mitte - 0.15 * hoehe and t.t >= op.b - 0.3 * op.g]
        oben = _anschliessend(oben[:1] if oben else [], klein)
        unten = _anschliessend(unten[:1] if unten else [], klein)
    else:
        nah = [t for t in klein if op.l - 0.6 * breite <= (t.l + t.r) / 2 <= op.r + 0.6 * breite]
        oben = [t for t in nah if t.b >= op.t - 0.25 * op.g and t.b - op.t <= 0.8 * op.g]
        unten = [t for t in nah if t.t <= op.b + 0.25 * op.g and op.b - t.t <= 0.8 * op.g]
    if op.text in WORT_OPERATOREN:
        oben = []                                       # lim/max/min haben nur eine Grenze darunter
    if not oben and not unten:
        return None
    text = GROSSE_OPERATOREN.get(op.text) or WORT_OPERATOREN[op.text]
    unsicher = False
    if unten:
        u, x = _innen(unten)
        text += f"_{{{u}}}"
        unsicher |= x
    if oben:
        o, x = _innen(oben)
        text += f"^{{{o}}}"
        unsicher |= x
    alle = [op] + oben + unten
    # Grundlinie: grosse (abgesetzte) Operatoren sitzen mittig auf der Formelachse, ihr Ursprung liegt tiefer
    grundlinie = mitte - 0.25 * op.g if hoehe > 1.3 * op.g else op.y
    return Teil(sorted(k for t in alle for k in t.indizes), text, min(t.l for t in alle), max(t.r for t in alle),
                min(t.b for t in alle), max(t.t for t in alle), grundlinie, op.g * 0.8, latex=True,
                unsicher=unsicher, folge=min(t.folge for t in alle), leer_davor=op.leer_davor)


def _zusammensetzen(teile: list[Teil], striche: list[tuple[float, float, float]]) -> tuple[list[Teil], list[Teil]]:
    """Baut Brueche (kurze Striche zuerst, damit verschachtelte Brueche von innen nach aussen entstehen), Wurzeln und
    Operatoren mit Grenzen. Gibt (alle Teile danach, neu gebaute Formelstuecke) zurueck."""
    neu: list[Teil] = []
    for strich in sorted(striche, key=lambda s: s[2] - s[1]):
        y = strich[0]
        fenster = [t for t in teile if t.b - 40 <= y <= t.t + 40]        # nur Teile in der Naehe des Strichs
        if not fenster:
            continue
        stueck = _bruch(strich, fenster) or _wurzel(strich, fenster)
        if stueck is None:
            continue
        verbraucht = set(stueck.indizes)
        teile = [t for t in teile if not set(t.indizes) & verbraucht] + [stueck]
        neu = [s for s in neu if not set(s.indizes) & verbraucht] + [stueck]
    for op in [t for t in teile if t.text in GROSSE_OPERATOREN and not t.latex] + _wort_operatoren(teile):
        stueck = _operator(op, [t for t in teile if t.b - 40 <= op.y <= t.t + 40 and not set(t.indizes) & set(op.indizes)])
        if stueck is None:
            continue
        verbraucht = set(stueck.indizes)
        teile = [t for t in teile if not set(t.indizes) & verbraucht] + [stueck]
        neu = [s for s in neu if not set(s.indizes) & verbraucht] + [stueck]
    return teile, neu


def _wort_operatoren(teile: list[Teil]) -> list[Teil]:
    """"lim", "max" ... als eigenes Wort (nicht in "Klima"): Kandidaten fuer Operatoren mit Grenze darunter."""
    folge = sorted((t for t in teile if not t.latex), key=lambda t: t.folge)
    gefunden = []
    for i in range(len(folge) - 2):
        a, b, c = folge[i:i + 3]
        if a.text + b.text + c.text not in WORT_OPERATOREN or b.leer_davor or c.leer_davor \
                or abs(a.y - c.y) > 0.2 * a.g:
            continue
        vorher = folge[i - 1] if i else None
        danach = folge[i + 3] if i + 3 < len(folge) else None
        if (vorher is not None and not a.leer_davor and vorher.text.isalpha()) or \
                (danach is not None and not danach.leer_davor and danach.text.isalpha() and abs(danach.y - a.y) < 0.2 * a.g):
            continue
        gefunden.append(Teil(a.indizes + b.indizes + c.indizes, a.text + b.text + c.text, a.l, c.r,
                             min(a.b, b.b, c.b), max(a.t, b.t, c.t), a.y, a.g, folge=a.folge,
                             leer_davor=a.leer_davor, zeile=a.zeile))
    return gefunden


# ---------------------------------------------------------------- Ersatz fuer die Seite
def ersatz(seite, tp, korrektur: dict[int, str] | None = None, striche: list | None = None,
           zuordnung=None) -> tuple[dict[int, str], dict]:
    """{Zeichenindex: Ersatz} fuer Hoch-/Tiefstellungen und Formeln der Seite, dazu eine Statistik
    {"hochtief": n, "formeln": n, "unsicher": n}. zuordnung: reparierte Zeichen der Formelreparatur (siehe zeichen())."""
    statistik = {"hochtief": 0, "formeln": 0, "unsicher": 0}
    groessen: list[float] = []
    striche = balken(seite, groessen) if striche is None else striche
    # Seiten mit nur einer Schriftgroesse und ohne Striche haben weder Indizes noch Brueche: Zeichen gar nicht erst
    # einzeln lesen (das kostet die meiste Zeit)
    if not striche and groessen and min(groessen) > KLEINER * max(groessen):
        return {}, statistik
    teile = zeichen(tp, korrektur, zuordnung)
    if not teile:
        return {}, statistik
    teile, stuecke = _zusammensetzen(teile, striche)
    ergebnis: dict[int, str] = {}
    # 1) Zeilen mit Formelstuecken: ganz neu setzen (Lesereihenfolge von links nach rechts)
    belegt: set[int] = set()
    zeile_von = {id(t): z for z in (_zeilen(teile) if stuecke else []) for t in z}
    for stueck in stuecke:
        if stueck.indizes[0] in belegt:
            continue
        zeile = zeile_von[id(stueck)]
        # nur der zusammenhaengende Bereich um das Stueck (eine Formel neben Fliesstext derselben Zeile)
        alle_k = sorted(k for t in zeile for k in t.indizes)
        if set(alle_k) & belegt:
            continue
        text = setzen_mit_formeln(zeile)
        unsicher = any(t.unsicher for t in zeile if t.latex) or ("�" in text and any(t.latex for t in zeile))
        if unsicher:
            text = UNSICHER + text
            statistik["unsicher"] += 1
        statistik["formeln"] += sum(1 for t in zeile if t.latex)
        erster = min(zeile, key=lambda t: t.folge)
        for k in alle_k:
            ergebnis[k] = ""
        if text.lstrip(UNSICHER).startswith("$"):
            # abgesetzte Formel: eigener Absatz (wie bei Tabellen), sonst klebt sie am Fliesstext davor
            ergebnis[erster.indizes[0]] = f"\r\n{ABSATZ}\r\n{text}\r\n{ABSATZ}\r\n"
        else:
            ergebnis[erster.indizes[0]] = text + "\r\n"
        belegt |= set(alle_k)
    # 2) uebrige Zeilen: nur Hoch-/Tiefstellungen, im Zeichenstrom an Ort und Stelle
    # Gruppen werden nach der Lage (sichtbare Zeile) gebildet und an ihr Bezugszeichen gehaengt: PDFium setzt einen
    # Index manchmal in eine eigene Zeile ("Ṡ R" / "irr,12"), dann stuende er sonst weit weg vom Zeichen.
    rest = [t for t in teile if not set(t.indizes) & belegt and not t.latex]
    for z in _zeilen(rest):
        st = _stellungen(z)
        i = 0
        while i < len(z):
            if not st[i]:
                i += 1
                continue
            tief, hoch = [], []
            j = i
            while j < len(z) and st[j] and (j == i or not _getrennt(z[j - 1], z[j])):
                (hoch if st[j] == "hoch" else tief).append(_maskiert(z[j]))
                j += 1
            stueck = "$" + (f"_{{{''.join(tief)}}}" if tief else "") + (f"^{{{''.join(hoch)}}}" if hoch else "") + "$"
            for t in z[i:j]:
                _schreiben(ergebnis, t, "")
            links = z[i - 1] if i and not st[i - 1] and not _getrennt(z[i - 1], z[i]) else None
            rechts = z[j] if j < len(z) and not _getrennt(z[j - 1], z[j]) else None
            if links is not None:
                _schreiben(ergebnis, links, ergebnis.get(links.indizes[0], links.text) + stueck)
            elif rechts is not None:
                _schreiben(ergebnis, rechts, stueck + ergebnis.get(rechts.indizes[0], rechts.text))
            else:
                _schreiben(ergebnis, z[i], stueck)
            statistik["hochtief"] += 1
            i = j
    for t in rest:                                      # angehaengte Akzente ("Q˙" -> "Q̇") ausserhalb von Formeln
        if t.akzent and t.indizes[0] not in ergebnis:
            _schreiben(ergebnis, t, t.text)
            statistik["akzente"] = statistik.get("akzente", 0) + 1
    return ergebnis, statistik


def _zeilen_im_strom(teile: list[Teil]) -> list[list[Teil]]:
    """Teile in PDFium-Reihenfolge, getrennt an PDFium-Zeilen (der Strom bleibt, wie er ist)."""
    zeilen: dict[int, list[Teil]] = {}
    for t in sorted(teile, key=lambda t: t.folge):
        zeilen.setdefault(t.zeile, []).append(t)
    return [z for z in zeilen.values() if len(z) >= 2]


GLEICHUNGSNUMMER = re.compile(r"\(\d+(?:[.,]\d+)*[a-z]?\)[.,;]?")


def _woerter(zeile: list[Teil], g: float) -> list[list[Teil]]:
    """Zeile in Woerter (an Leerzeichen und Luecken getrennt; Indizes haengen ohne Luecke am Zeichen davor)."""
    woerter: list[list[Teil]] = []
    for i, t in enumerate(zeile):
        if not woerter or _getrennt(zeile[i - 1], t) or t.l - zeile[i - 1].r > 0.25 * g:
            woerter.append([t])
        else:
            woerter[-1].append(t)
    return woerter


def setzen_mit_formeln(zeile: list[Teil]) -> str:
    """Eine Zeile mit Formelstuecken: Woerter (ab drei Buchstaben) und Gleichungsnummern bleiben Text, alles
    dazwischen ist Formel und kommt zusammenhaengend in $...$ ("Nach Bild 4.1 ist $\\frac{V}{T_{0} + t} = ...$ (4.3)")."""
    y, g = _bezug(zeile)
    stellung = dict(zip(map(id, zeile), _stellungen(zeile)))
    aus: list[str] = []
    formel: list[Teil] = []

    def schliessen():
        if formel:
            aus.append("$" + setzen(formel, True) + "$")
            formel.clear()

    rechts = None
    for wort in _woerter(zeile, g):
        grund = "".join(t.text for t in wort if not stellung[id(t)])
        ist_text = not any(t.latex for t in wort) and (
            len(grund.rstrip(".,;:!?)")) >= 3 and grund.rstrip(".,;:!?)").replace("-", "").isalpha()
            or GLEICHUNGSNUMMER.fullmatch(grund) is not None)
        if formel and rechts is not None and wort[0].l - rechts > 1.5 * g:
            schliessen()                            # grosser Abstand: zwei Formeln nebeneinander
        rechts = wort[-1].r
        if ist_text:
            schliessen()
            aus.append(setzen(wort, False))
        else:
            if formel:
                wort[0].leer_davor = True
            formel.extend(wort)
    schliessen()
    return " ".join(aus).strip()
