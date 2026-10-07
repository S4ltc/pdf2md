"""Schriftbild: Schriftgroesse und Fett/Kursiv je Zeile (PDFium), daraus Ueberschriften und Hervorhebungen.

1. Ueberschriften aus der Schriftgroesse: nur fuer PDFs ohne Lesezeichen (pdf2md nimmt sonst die Lesezeichen, die
   sind genauer). Eine Zeile ist Ueberschrift, wenn sie deutlich groesser als der Fliesstext ist (GROESSER) oder fett
   in Textgroesse mit Abschnittsnummer ("2.4 Lagerung"), kurz ist und kein Satz, keine Bild-/Tabellenunterschrift,
   keine Inhaltsverzeichniszeile ("3.1 Zahnräder 45") und kein Kolumnentitel (gleiche Zeile auf vielen Seiten).
   Ebene: Tiefe der Abschnittsnummer ("3.1.1" = dritte Ebene), ohne Nummer der Rang der Schriftgroesse.
   Ergebnis im Format von pdf2md.lesezeichen_lesen(), damit dieselbe Stelle die Ueberschriften einsetzt.
2. Hervorhebungen: fette und kursive Wortgruppen werden **fett**, *kursiv* bzw. ***beides***. Eingesetzt wird erst in
   den fertigen Text (einsetzen()), damit Seitenzahlen, Kopfzeilen und Silbentrennung wie bisher arbeiten. Formelschriften
   (kursive Variablen) und einzelne kurze Woerter ("F", "ab") zaehlen nicht; Ueberschriften, Tabellen, Formeln ($...$)
   und Marker bleiben unberuehrt; wo eine Stelle nicht eindeutig wiederzufinden ist, unterbleibt die Hervorhebung.

Die Schrift kommt aus dem Textobjekt (FPDFTextObj_GetFont): Name, Gewicht, Flags und Neigungswinkel; gelesen wird
je Textobjekt einmal, je Zeichen nur Code und Textobjekt."""
from __future__ import annotations

import ctypes
import re
from collections import Counter
from dataclasses import dataclass

import pypdfium2.raw as raw

GROESSER = 1.15         # Ueberschrift: mindestens so viel groesser als der Fliesstext
NUMMER_GROESSER = 1.05  # ... mit Abschnittsnummer ("3.5 Einflüsse") genuegt etwas groesser
MIN_BUCHSTABEN = 4      # ein einzelnes betontes Wort braucht so viele Buchstaben (kuerzer: meist ein Formelzeichen)
MAX_UEBERSCHRIFT = 120  # Zeichen
MAX_WOERTER = 14
MAX_ZEILEN = 3          # so viele gleich gesetzte Zeilen nacheinander werden zu einer Ueberschrift
KOLUMNE_SEITEN = 3      # dieselbe Zeile in derselben Groesse auf so vielen Seiten: Kolumnentitel
MAX_JE_SEITE = 4.0      # mehr Ueberschriften je Textseite: die Schriftgroessen taugen nicht (Normen haben bis 3)
GRUNDSCHRIFT = 0.3      # ein Stil auf mehr als diesem Anteil des Textes ist die Grundschrift, keine Betonung ...
MIN_GRUNDTEXT = 2000    # ... sofern es so viele Zeichen Text gibt (in einem kurzen Text ist ein Wort schnell 30 %)
UMGEBUNG = 30           # so viele Zeichen Umgebung merkt sich eine Hervorhebung zum Wiederfinden
RAND = 300              # so weit darf eine Hervorhebung ueber ihren Seitenmarker hinaus gesucht werden

MATHE = re.compile(r"CMMI|CMSY|CMEX|CMBSY|MSAM|MSBM|MTMI|MTSY|MTEX|MT2|MathTime|Math|Symbol|STIX|esint|Euclid|rsfs|"
                   r"eufm|Wingding|Dingbat|ZapfD", re.IGNORECASE)
FETT = re.compile(r"bold|black|heavy|demi|cmbx|cmb\d|(?:^|[-_,])(?:bd|blk|hv|sb|xb)(?=$|[-_,]|it)", re.IGNORECASE)
KURSIV = re.compile(r"italic|oblique|kursiv|^cm(?:ti|sl|bxti|bxsl|itt)\d|(?:^|[-_,])(?:it|ital|obl|i|bi|\w*it)$",
                    re.IGNORECASE)
NUMMER = re.compile(r"(\d{1,2}|[A-Z](?=\.\d))((?:\.\d{1,2})*)\.?\s+(?=\S)")
BESCHRIFTUNG = re.compile(r"(?:Abb\.|Abbildung|Bild|Fig\.|Figure|Tab\.|Tabelle|Table|Gl\.|Gleichung|Quelle|Seite)\s",
                          re.IGNORECASE)
ZUSATZ = re.compile(r"\((?:informativ|normativ|informative|normative)\)", re.IGNORECASE)   # Anhang A (normativ)
GEZAEHLT = re.compile(r"(?:Teil|Kapitel|Band|Anhang|Abschnitt|Lektion|Part|Chapter)\s+\d{1,4}$", re.IGNORECASE)
MARKER = re.compile(r"<!-- (?:Seite \S+ \(PDF (\d+)\)|PDF-Seite (\d+)) -->")     # wie pdf2md.seitenmarker()
ZEICHEN = {"fett": "**", "kursiv": "*", "fettkursiv": "***"}
TRENNSTRICH = ("-", "­")
RANDZEICHEN = " ,.;:!?)]}([{\"'„“”‚‘»«"     # gehoeren nicht in die Betonung ("**) in kJ/mol**")


@dataclass(slots=True)
class Zeile:
    seite: int
    text: str
    groesse: float                  # Median der Schriftgroessen
    fett: float                     # Anteil fetter Zeichen
    kursiv: float                   # Anteil kursiver Zeichen
    laeufe: list[tuple[str, str]]   # (Text, Stil) gleichen Stils nacheinander; Stil "", "fett", "kursiv", "fettkursiv"


@dataclass(frozen=True, slots=True)
class Hervorhebung:
    seite: int
    text: str
    stil: str
    vorher: str                     # Text der Zeile davor/danach, zum eindeutigen Wiederfinden
    nachher: str


def stil(name: str, flags: int = 0, gewicht: int = 0, winkel: float = 0) -> str:
    """"fett", "kursiv", "fettkursiv" oder "" fuer eine Schrift. Formelschriften zaehlen nie (ihre Kursive ist die
    der Variablen, keine Betonung)."""
    name = re.sub(r"^[A-Z]{6}\+", "", name or "")
    if MATHE.search(name):
        return ""
    fett = bool(FETT.search(name)) or gewicht >= 600 or bool(flags & (1 << 18))      # ForceBold
    kursiv = bool(KURSIV.search(name)) or bool(flags & 64) or winkel != 0            # Italic-Flag
    return ("fett" if fett else "") + ("kursiv" if kursiv else "")


_NAME = ctypes.create_string_buffer(256)


def _objektstil(tp, k: int, objekt, matrix) -> tuple[str, float]:
    groesse = raw.FPDFText_GetFontSize(tp, k)
    if groesse <= 1.5 and raw.FPDFText_GetMatrix(tp, k, matrix):     # TeX: 1 pt, skaliert ueber die Textmatrix
        groesse *= abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5
    name, flags, gewicht, winkel = "", 0, 0, 0
    schrift = raw.FPDFTextObj_GetFont(objekt) if objekt else None
    if schrift:
        if raw.FPDFFont_GetBaseFontName(schrift, _NAME, 256):
            name = _NAME.value.decode("latin-1")
        flags, gewicht = raw.FPDFFont_GetFlags(schrift), raw.FPDFFont_GetWeight(schrift)
        w = ctypes.c_int()
        if raw.FPDFFont_GetItalicAngle(schrift, ctypes.byref(w)):
            winkel = w.value
    return stil(name, max(flags, 0), gewicht, winkel), max(groesse, 1.0)


def _zeile(seite: int, zeichen: list[tuple[str, str | None, float]]) -> Zeile | None:
    sichtbar = [(s, g) for c, s, g in zeichen if s is not None]
    if not sichtbar:
        return None
    groessen = sorted(g for _, g in sichtbar)
    laeufe: list[list] = []
    luecke = False
    for c, s, _ in zeichen:
        if s is None:                       # Leerraum gehoert zu keinem Stil, trennt aber Woerter
            luecke = True
            continue
        if laeufe and laeufe[-1][1] == s:
            laeufe[-1][0] += (" " if luecke else "") + c
        else:
            laeufe.append([c, s])
        luecke = False
    return Zeile(seite, " ".join("".join(c for c, _, _ in zeichen).split()), groessen[len(groessen) // 2],
                 sum("fett" in s for s, _ in sichtbar) / len(sichtbar),
                 sum("kursiv" in s for s, _ in sichtbar) / len(sichtbar),
                 [(t, s) for t, s in laeufe])


def zeilen_lesen(textseite, seite: int) -> list[Zeile]:
    """Die Zeilen einer Seite in der Reihenfolge von PDFium, je Zeile Text, Schriftgroesse und Stil-Laeufe."""
    tp = getattr(textseite, "raw", textseite)
    n = raw.FPDFText_CountChars(tp)
    code_, objekt_, cast = raw.FPDFText_GetUnicode, raw.FPDFText_GetTextObject, ctypes.cast
    matrix = raw.FS_MATRIX()
    stile: dict = {}
    zeilen: list[Zeile] = []
    aktuell: list[tuple[str, str | None, float]] = []
    k = 0
    while k < n:
        code = code_(tp, k)
        breite = 1
        if code in (10, 13):
            zeile = _zeile(seite, aktuell)
            if zeile:
                zeilen.append(zeile)
            aktuell = []
            k += 1
            continue
        if code in (9, 32, 0xA0):
            aktuell.append((" ", None, 0.0))
            k += 1
            continue
        if 0xD800 <= code <= 0xDBFF and k + 1 < n:
            tief = code_(tp, k + 1)
            zeichen = chr(0x10000 + ((code - 0xD800) << 10) + (tief - 0xDC00)) if 0xDC00 <= tief <= 0xDFFF else "�"
            breite = 2
        elif code == 2:
            zeichen = "­"              # weiche Trennung (PDFium: Code 2)
        else:
            zeichen = chr(code) if code >= 32 and not 0xD800 <= code <= 0xDFFF else "�"
        objekt = objekt_(tp, k)
        adresse = cast(objekt, ctypes.c_void_p).value if objekt else None     # Zeiger selbst ist nicht hashbar
        info = stile.get(adresse)
        if info is None:
            info = stile[adresse] = _objektstil(tp, k, objekt, matrix)
        aktuell.append((zeichen, info[0], info[1]))
        k += breite
    zeile = _zeile(seite, aktuell)
    if zeile:
        zeilen.append(zeile)
    return zeilen


# ---------------------------------------------------------------- Ueberschriften
def _ohne_ziffern(text: str) -> str:
    return re.sub(r"\d+", "#", text.casefold())


def _kandidat(z: Zeile, koerper: float) -> bool:
    nummer = bool(NUMMER.match(z.text))
    return (z.groesse >= koerper * GROESSER or (nummer and z.groesse >= koerper * NUMMER_GROESSER)
            or (nummer and z.fett >= 0.9 and z.groesse >= koerper * 0.95))


def _klammern_ok(text: str) -> bool:
    tiefe = 0
    for c in text:
        tiefe += (c == "(") - (c == ")")
        if tiefe < 0:
            return False
    return tiefe == 0


def _titel_ok(titel: str) -> bool:
    woerter = titel.split()
    buchstaben = sum(c.isalpha() for c in titel)
    sichtbar = sum(not c.isspace() for c in titel)
    if not (2 <= len(titel) <= MAX_UEBERSCHRIFT and len(woerter) <= MAX_WOERTER and buchstaben >= 3
            and buchstaben >= 0.5 * sichtbar):
        return False
    if BESCHRIFTUNG.match(titel) or "=" in titel or titel.endswith((",", ";")) or re.match(r"\d{1,4}\s+\d", titel):
        return False
    if titel.startswith("(") or not _klammern_ok(titel):           # Diagrammbeschriftung, Zusatz ohne Titel
        return False
    if max(sum(c.isalpha() for c in w) for w in woerter) < 3:        # "M2 M2 l2"
        return False
    if len(woerter) >= 4 and titel.upper() == titel:                # Deckblatt "EUROPÄISCHE NORM EUROPEAN ..."
        return False
    if titel.endswith(".") and len(woerter) > 6:                     # ein Satz
        return False
    if re.search(r"\s\d{1,4}$", titel) and not GEZAEHLT.search(titel):   # Inhaltsverzeichnis: Titel und Seite
        return False
    return True


def _passt(gruppe: list[Zeile], z: Zeile) -> bool:
    """Gehoert z zur Ueberschrift davor (umbrochener Titel)?"""
    erste = gruppe[0]
    if len(gruppe) >= MAX_ZEILEN:
        return False
    if ZUSATZ.fullmatch(z.text):                                      # "Anhang A" / "(informativ)" / Titel
        return True
    return (abs(z.groesse - erste.groesse) <= 0.3 and (z.fett >= 0.5) == (erste.fett >= 0.5)
            and not NUMMER.match(z.text) and not gruppe[-1].text.endswith((".", ":", "!", "?")))


def ueberschriften(zeilen_je_seite: list[list[Zeile]]) -> dict[int, list[tuple[int, str]]]:
    """Ueberschriften aus der Schriftgroesse: {Seitenindex: [(Ebene, Titel), ...]} wie die Lesezeichen."""
    gewicht: Counter = Counter()
    for zeilen in zeilen_je_seite:
        for z in zeilen:
            gewicht[round(z.groesse * 2) / 2] += len(z.text)
    if not gewicht:
        return {}
    koerper = gewicht.most_common(1)[0][0]
    wiederkehrend: Counter = Counter()
    for zeilen in zeilen_je_seite:
        wiederkehrend.update({(_ohne_ziffern(z.text), round(z.groesse)) for z in zeilen})
    gruppen: list[tuple[int, list[Zeile]]] = []
    for i, zeilen in enumerate(zeilen_je_seite):
        gruppe: list[Zeile] = []
        for z in zeilen:
            kolumne = wiederkehrend[(_ohne_ziffern(z.text), round(z.groesse))] >= KOLUMNE_SEITEN
            if gruppe and not kolumne and _passt(gruppe, z):     # Fortsetzung, auch ohne eigene Nummer
                gruppe.append(z)
                continue
            if gruppe:
                gruppen.append((i, gruppe))
                gruppe = []
            if not kolumne and _kandidat(z, koerper):
                gruppe = [z]
        if gruppe:
            gruppen.append((i, gruppe))
    titel = [(i, " ".join(z.text for z in g), g[0].groesse) for i, g in gruppen]
    titel = [(i, t, g) for i, t, g in titel if _titel_ok(t)]
    textseiten = sum(1 for zeilen in zeilen_je_seite if zeilen)
    if not titel or len(titel) > MAX_JE_SEITE * textseiten:
        return {}
    groessen = sorted({round(g) for _, t, g in titel if not NUMMER.match(t)}, reverse=True)
    ergebnis: dict[int, list[tuple[int, str]]] = {}
    for i, t, g in titel:
        m = NUMMER.match(t)
        ebene = min(m.group(2).count("."), 5) if m else min(groessen.index(round(g)), 2)
        ergebnis.setdefault(i, []).append((ebene, t))
    return ergebnis


# ---------------------------------------------------------------- Hervorhebungen
def _lohnt(text: str) -> bool:
    if "*" in text:
        return False
    buchstaben = sum(c.isalpha() for c in text)
    if buchstaben < 2 * sum(not c.isspace() and not c.isalpha() for c in text):
        return False                                       # ueberwiegend Ziffern und Zeichen
    woerter = [w for w in text.split() if sum(c.isalpha() for c in w) >= 2]
    return len(woerter) >= 2 or buchstaben >= MIN_BUCHSTABEN


def hervorhebungen(zeilen_je_seite: list[list[Zeile]]) -> list[Hervorhebung]:
    """Fette und kursive Wortgruppen in Lesereihenfolge. Wortstuecke an einer Silbentrennung entfallen, denn im
    fertigen Text steht dort das ganze Wort."""
    gesamt = sum(len(z.text) for zeilen in zeilen_je_seite for z in zeilen)
    grund = {merkmal for merkmal in ("fett", "kursiv")              # Grundschrift: z.B. alles als fett gekennzeichnet
             if gesamt >= MIN_GRUNDTEXT and sum(getattr(z, merkmal) * len(z.text) for zeilen in zeilen_je_seite
                                                for z in zeilen) > GRUNDSCHRIFT * gesamt}
    ergebnis: list[Hervorhebung] = []
    for zeilen in zeilen_je_seite:
        getrennt = False
        for z in zeilen:
            for j, (text, art) in enumerate(z.laeufe):
                for merkmal in grund:
                    art = art.replace(merkmal, "")
                nachher = " ".join(t for t, _ in z.laeufe[j + 1:])
                if art and j == len(z.laeufe) - 1 and text.endswith(TRENNSTRICH):
                    text, _, rest = text.rpartition(" ")
                    nachher = rest.rstrip("".join(TRENNSTRICH))
                if art and j == 0 and getrennt:
                    text = text.partition(" ")[2]
                text = text.strip(RANDZEICHEN)
                if art and _lohnt(text):
                    vorher = " ".join(t for t, _ in z.laeufe[:j])
                    ergebnis.append(Hervorhebung(z.seite, text, art, vorher[-UMGEBUNG:], nachher[:UMGEBUNG]))
            getrennt = len(z.text) > 1 and z.text.endswith(TRENNSTRICH) and z.text[-2].isalpha()
    return ergebnis


def _gesperrt(text: str) -> bytearray:
    """1 fuer jedes Zeichen, das keine Hervorhebung bekommen darf: Ueberschriften- und Tabellenzeilen, Marker und
    andere Kommentare, Formeln in $...$."""
    maske = bytearray(len(text))
    for m in re.finditer(r"^[ \t]*[#|][^\n]*|<!--.*?-->|\$[^$\n]+\$", text, re.MULTILINE | re.DOTALL):
        maske[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    return maske


def _seitenbereiche(text: str) -> dict[int, tuple[int, int]]:
    marker = list(MARKER.finditer(text))
    return {int(m.group(1) or m.group(2)) - 1: (m.end(), marker[k + 1].start() if k + 1 < len(marker) else len(text))
            for k, m in enumerate(marker)}


def _kompakt(text: str) -> str:
    return re.sub(r"<!--.*?-->|\s+|\*", "", text)


def _muster(phrase: str) -> re.Pattern:
    links = r"(?<![\w*])" if re.match(r"\w", phrase) else r"(?<!\*)"
    rechts = r"(?![\w*])" if re.search(r"\w$", phrase) else r"(?!\*)"
    return re.compile(links + r"\s+".join(re.escape(w) for w in phrase.split()) + rechts)


def einsetzen(text: str, eintraege: list[Hervorhebung], normieren=None) -> tuple[str, int]:
    """Setzt die Hervorhebungen in den fertigen Markdown-Text ein: gesucht wird auf der Seite der Hervorhebung (am
    Seitenmarker), bei mehreren Fundstellen entscheidet die Umgebung; bleibt es mehrdeutig, unterbleibt sie.
    normieren: dieselbe Zeichenbereinigung wie im Text (Ligaturen, NFC). Gibt (Text, Anzahl) zurueck."""
    if not eintraege:
        return text, 0
    normieren = normieren or (lambda s: s)
    maske = _gesperrt(text)
    seiten = _seitenbereiche(text)
    gesetzt: list[tuple[int, int, str]] = []
    for h in eintraege:
        phrase = " ".join(normieren(h.text).split())
        if not phrase or (seiten and h.seite not in seiten):
            continue
        a, e = seiten.get(h.seite, (0, len(text)))
        muster = _muster(phrase)

        def frei(m: re.Match) -> bool:
            return 1 not in maske[m.start():m.end()]

        treffer = [m for m in muster.finditer(text, a, e) if frei(m)]
        if not treffer:
            treffer = [m for m in muster.finditer(text, max(0, a - RAND), min(len(text), e + RAND)) if frei(m)]
        if len(treffer) > 1:
            v, n = _kompakt(normieren(h.vorher))[-12:], _kompakt(normieren(h.nachher))[:12]

            def passt(m: re.Match) -> int:
                return ((bool(v) and _kompakt(text[max(0, m.start() - 60):m.start()]).endswith(v))
                        + (bool(n) and _kompakt(text[m.end():m.end() + 60]).startswith(n)))
            beste = max(passt(m) for m in treffer)
            treffer = [m for m in treffer if passt(m) == beste] if beste else []
        if len(treffer) != 1:
            continue
        m = treffer[0]
        maske[m.start():m.end()] = b"\x01" * (m.end() - m.start())
        gesetzt.append((m.start(), m.end(), ZEICHEN[h.stil]))
    zusammen: list[tuple[int, int, str]] = []
    for a, e, z in sorted(gesetzt):        # ein betonter Absatz kommt zeilenweise: eine Betonung statt "** **"
        luecke = text[zusammen[-1][1]:a] if zusammen else ""
        if zusammen and zusammen[-1][2] == z and not luecke.strip() and "\n\n" not in luecke:
            zusammen[-1] = (zusammen[-1][0], e, z)
        else:
            zusammen.append((a, e, z))
    teile, ende = [], len(text)
    for a, e, z in reversed(zusammen):
        teile.append(text[e:ende])
        teile.append(z + text[a:e] + z)
        ende = a
    teile.append(text[:ende])
    return "".join(reversed(teile)), len(gesetzt)
