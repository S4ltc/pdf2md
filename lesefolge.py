"""Lesereihenfolge zweispaltiger PDF-Seiten.

PDFium liefert den Text in der Reihenfolge, in der das PDF ihn zeichnet. Das ist bei manchen Verlagen (z.B. InDesign)
nicht die Lesereihenfolge: die rechte Spalte kommt vor der linken, Tabellen stehen am Ende der Seite. Hier wird die
Seite in Laeufe (Zeilenstuecke) zerlegt, eine Spaltenluecke gesucht und die Reihenfolge korrigiert:

    Kopf/breite Zeilen  ->  linke Spalte  ->  rechte Spalte  ->  breite Zeile  ->  linke Spalte ...

Es wird nur umsortiert, nie etwas hinzugefuegt oder weggelassen. Ist die Reihenfolge schon richtig oder die Seite
nicht eindeutig zweispaltig, bleibt alles wie es ist (Rueckgabe None).
"""

import ctypes

import pypdfium2.raw as raw

LUECKE = 3.0            # ab dieser Luecke (in Zeichenhoehen) innerhalb einer Zeile beginnt ein neuer Lauf
MIN_LAEUFE = 12         # weniger Zeilenstuecke: nichts tun
MIN_BREITE = 100.0      # Seitentext schmaler als das (pt): nichts tun
MIN_SPALTENZEILEN = 5   # so viele fast volle Zeilen braucht jede Spalte
LANG = 0.3              # ab diesem Anteil der Textbreite gilt ein Lauf als Textzeile (sonst haengt er am Vorgaenger)
BREIT = 0.6             # ab diesem Anteil der Textbreite ist ein Lauf "breit" (ueber beide Spalten)
STEG_MIN = 5.0          # Mindestbreite der Spaltenluecke (pt)
TOLERANZ = 6.0          # so weit (pt) darf eine Spalte ueber/unter der anderen beginnen/enden
DURCHLAESSIG = 0.25     # so viele Textzeilen duerfen die Spaltenluecke ueberqueren (breite Tabelle, Formel)

# Markiert im rohen Seitentext eine harte Absatzgrenze (Spalten-/Bandwechsel): ein frei stehendes Zeichen aus dem
# privaten Unicodebereich, das in keinem Buchtext vorkommt und von pdf2md._seite_bereinigen() vor _absaetze_bilden()
# in eine echte Leerzeile umgewandelt wird (die _absaetze_bilden() bereits nie ueberbrueckt). So bleibt die Grenze
# durch die Zeilenlisten (zeilen_je_seite, _kopf_fuss_entfernen) hindurch erhalten, waehrend echte Leerzeilen dort
# sonst als bedeutungslos verworfen werden.
SPALTENBRUCH = ""


def laeufe_lesen(tp) -> list[list]:
    """Zerlegt den Zeichenstrom in Laeufe: [start, ende, (links, unten, rechts, oben) oder None, Fortsetzung].
    Ein Lauf endet nach seinem Zeilenumbruch, bei einer grossen Luecke in der Zeile oder wenn eine neue Zeile ohne
    Umbruchzeichen beginnt (PDFium setzt nach einem Trennstrich keinen). Fortsetzung: der Lauf begann nach einer Luecke
    in derselben Zeile."""
    n = tp.count_chars()
    links, rechts = ctypes.c_double(), ctypes.c_double()
    unten, oben = ctypes.c_double(), ctypes.c_double()
    # Zeiger und Funktionen einmal anlegen: die Schleife laeuft ueber jedes Zeichen jeder Seite und war der groesste
    # Zeitposten der Umwandlung (10 Mio. byref-Aufrufe bei einem 900-Seiten-Buch)
    zeiger = (ctypes.byref(links), ctypes.byref(rechts), ctypes.byref(unten), ctypes.byref(oben))
    zeichen_code, zeichen_rahmen = raw.FPDFText_GetUnicode, raw.FPDFText_GetCharBox
    laeufe: list[list] = []
    start = 0
    box = None
    letzte = None                       # (rechts, unten, hoehe) des letzten sichtbaren Zeichens
    nach_umbruch = False
    fortsetzung = False
    for i in range(n):
        code = zeichen_code(tp, i)
        if code in (10, 13):
            nach_umbruch = True
            continue
        sichtbar = code != 32 and zeichen_rahmen(tp, i, *zeiger)
        if sichtbar and not (links.value == rechts.value == unten.value == oben.value == 0.0):
            l, r, b, t = links.value, rechts.value, unten.value, oben.value
        else:
            sichtbar = False
        neu = nach_umbruch
        luecke = False
        if sichtbar and letzte is not None and not neu:
            hoehe = max(letzte[2], 4.0)
            if l - letzte[0] > LUECKE * hoehe and abs(b - letzte[1]) < 0.5 * hoehe:
                neu = luecke = True     # grosse Luecke in der Zeile (zwei Spalten in einer Zeile, Tabellenzellen)
            elif letzte[1] - b > 0.7 * hoehe and l < letzte[0] - 2 * hoehe:
                neu = True              # neue Zeile ohne Umbruchzeichen (Indizes und Exponenten springen nicht so weit zurueck)
        if neu and i > start:
            laeufe.append([start, i, box, fortsetzung])
            start, box, fortsetzung = i, None, luecke
        nach_umbruch = False
        if sichtbar:
            box = (l, b, r, t) if box is None else (min(box[0], l), min(box[1], b), max(box[2], r), max(box[3], t))
            letzte = (r, b, t - b)
    if n > start:
        laeufe.append([start, n, box, fortsetzung])
    # Laeufe ohne sichtbares Zeichen (nur Leerraum) gehoeren zum Vorgaenger
    ergebnis: list[list] = []
    for lauf in laeufe:
        if lauf[2] is None and ergebnis:
            ergebnis[-1][1] = lauf[1]
        else:
            ergebnis.append(lauf)
    return ergebnis


def _spaltenluecke(langzeilen, xmin: float, xmax: float):
    """Genau eine Luecke im mittleren Bereich, die (fast) keine Textzeile ueberdeckt: (links, rechts) oder None."""
    breite = xmax - xmin
    von, bis = int(xmin), int(xmax) + 1
    deckung = [0] * (bis - von + 1)
    for l, r in langzeilen:
        for x in range(max(int(l) - von, 0), min(int(r) - von + 1, len(deckung))):
            deckung[x] += 1
    grenze = max(1, int(DURCHLAESSIG * len(langzeilen)))     # eine Tabelle darf die Luecke ueberqueren
    lucken = []
    x = 0
    while x < len(deckung):
        if deckung[x] <= grenze:
            y = x
            while y < len(deckung) and deckung[y] <= grenze:
                y += 1
            lucken.append((x + von, y + von))
            x = y
        else:
            x += 1
    innen = [(a, b) for a, b in lucken
             if b - a >= STEG_MIN and a > xmin + 0.15 * breite and b < xmax - 0.15 * breite]
    return innen[0] if len(innen) == 1 else None


def _blockgrenzen(ys: list[float]):
    """(oberste, unterste) Zeile des zusammenhaengenden Spaltentextes: erst drei Zeilen in regelmaessigem Abstand
    zaehlen, eine einzelne Kopfzeile oder Seitenzahl weit darueber nicht. None, wenn es keinen solchen Block gibt."""
    ys = sorted(ys, reverse=True)
    if len(ys) < 3:
        return None
    abstaende = [a - b for a, b in zip(ys, ys[1:])]
    grenze = 1.8 * sorted(abstaende)[len(abstaende) // 2]
    ok = [i for i in range(len(abstaende) - 1) if abstaende[i] <= grenze and abstaende[i + 1] <= grenze]
    if not ok:
        return None
    return ys[ok[0]], ys[ok[-1] + 2]


def analysiere(laeufe: list[list]) -> tuple[bool, list[int] | None]:
    """(zweispaltig?, neue Reihenfolge der Laeufe als Indexliste oder None, wenn sie schon stimmt)."""
    return _ordnung_mit_bruechen(laeufe)[:2]


def _ordnung_mit_bruechen(laeufe: list[list]) -> tuple[bool, list[int] | None, frozenset[int]]:
    """Wie analysiere(), gibt zusaetzlich die Lauf-Indizes zurueck, vor denen ein Spalten-/Bandwechsel liegt (dort
    darf beim Zusammenbau nie ein Absatz ueber die Grenze hinweg zusammengezogen werden, siehe seitentext())."""
    sichtbar = [lz for lz in laeufe if lz[2] is not None]
    if len(sichtbar) < MIN_LAEUFE:
        return False, None, frozenset()
    lefts = sorted(lz[2][0] for lz in sichtbar)
    rights = sorted(lz[2][2] for lz in sichtbar)
    xmin = lefts[int(0.03 * len(lefts))]
    xmax = rights[max(int(0.97 * len(rights)) - 1, 0)]
    breite = xmax - xmin
    if breite < MIN_BREITE:
        return False, None, frozenset()
    lang = [lz for lz in sichtbar if lz[2][2] - lz[2][0] >= LANG * breite]
    schmal_lang = [(lz[2][0], lz[2][2]) for lz in lang if lz[2][2] - lz[2][0] < BREIT * breite]
    if len(schmal_lang) < 2 * MIN_SPALTENZEILEN:
        return False, None, frozenset()
    steg = _spaltenluecke(schmal_lang, xmin, xmax)
    if steg is None:
        return False, None, frozenset()
    mitte = (steg[0] + steg[1]) / 2
    # jede Spalte braucht mehrere fast volle Zeilen, sonst ist es keine Spalte (z.B. Tabelle oder Randnotiz)
    voll_l = sum(1 for l, r in schmal_lang if r <= steg[0] + 1 and r - l >= 0.8 * (steg[0] - xmin))
    voll_r = sum(1 for l, r in schmal_lang if l >= steg[1] - 1 and r - l >= 0.8 * (xmax - steg[1]))
    if voll_l < MIN_SPALTENZEILEN or voll_r < MIN_SPALTENZEILEN:
        return False, None, frozenset()

    def klasse(box) -> str:
        l, b, r, t = box
        if r - l >= BREIT * breite or (l < steg[0] and r > steg[1]):
            return "F"
        return "L" if (l + r) / 2 < mitte else "R"

    # Gruppen: eine Textzeile mit den kurzen Laeufen, die im Strom danach kommen (Formelteile, Zellen, Nummern)
    gruppen: list[dict] = []
    for nr, lz in enumerate(laeufe):
        box = lz[2]
        ist_lang = box is not None and box[2] - box[0] >= LANG * breite
        if gruppen and not ist_lang:
            gruppen[-1]["laeufe"].append(nr)
            continue
        if box is None:
            gruppen.append({"laeufe": [nr], "klasse": "L", "y": 0.0, "lang": False})
        else:
            gruppen.append({"laeufe": [nr], "klasse": klasse(box), "y": (box[1] + box[3]) / 2, "lang": ist_lang})
    # Was ueber dem ersten oder unter dem letzten vollen Spaltentext steht (Kopfzeile, Seitenzahl, Bild mit Unterschrift,
    # Fusszeile), gehoert nicht zu einer Spalte: es wird wie eine breite Zeile behandelt.
    voll = [g for g in gruppen if g["klasse"] != "F" and g["lang"]
            and (laeufe[g["laeufe"][0]][2][2] - laeufe[g["laeufe"][0]][2][0]) >= 0.8 * min(steg[0] - xmin, xmax - steg[1])]
    grenzen = [_blockgrenzen([g["y"] for g in voll if g["klasse"] == s]) for s in ("L", "R")]
    if all(grenzen):
        oberkante = max(o for o, u in grenzen)
        unterkante = min(u for o, u in grenzen)
        for g in gruppen:
            if g["klasse"] != "F" and (g["y"] > oberkante + TOLERANZ or g["y"] < unterkante - TOLERANZ):
                g["klasse"] = "F"
    breite_gruppen = sorted((g for g in gruppen if g["klasse"] == "F"), key=lambda g: -g["y"])
    for g in gruppen:
        if g["klasse"] != "F":
            g["band"] = sum(1 for f in breite_gruppen if f["y"] >= g["y"])
    # Nur eingreifen, wenn die Reihenfolge nachweislich falsch ist: im Strom steht eine rechte Textzeile VOR einer
    # linken desselben Bandes. Alles andere (Tabellen, Randnotizen, Bildunterschriften) bleibt, wie PDFium es liefert.
    rechts_gesehen: set[int] = set()
    falsch = False
    for g in gruppen:
        if g["klasse"] == "F" or not g["lang"]:
            continue
        if g["klasse"] == "R":
            rechts_gesehen.add(g["band"])
        elif g["band"] in rechts_gesehen:
            falsch = True
            break
    if not falsch:
        return True, None, frozenset()
    ergebnis: list[int] = []
    harte_bruch: set[int] = set()
    letzter = None       # letzter original Lauf-Index im bisherigen Ergebnis

    def anhaengen(gruppe: dict) -> None:
        nonlocal letzter
        if letzter is not None and gruppe["laeufe"][0] != letzter + 1:
            harte_bruch.add(gruppe["laeufe"][0])     # Sprung im Strom: kein Absatz darf das ueberbruecken
        ergebnis.extend(gruppe["laeufe"])
        letzter = gruppe["laeufe"][-1]

    for band in range(len(breite_gruppen) + 1):
        for seite in ("L", "R"):
            for g in sorted((g for g in gruppen if g["klasse"] == seite and g["band"] == band), key=lambda g: -g["y"]):
                anhaengen(g)
        if band < len(breite_gruppen):
            anhaengen(breite_gruppen[band])
    if ergebnis == list(range(len(laeufe))):
        return True, None, frozenset()
    return True, ergebnis, frozenset(harte_bruch)


def reihenfolge(laeufe: list[list]) -> list[int] | None:
    """Neue Reihenfolge der Laeufe (Liste von Indizes) oder None, wenn nichts zu tun ist."""
    return analysiere(laeufe)[1]


def satzbrueche(text: str) -> int:
    """Wie oft endet eine Textzeile mit einem Satzende, und die naechste Zeile beginnt trotzdem klein? Das deutet auf
    eine falsche Reihenfolge hin (in einem richtig gelesenen Satz kommt es kaum vor). Die SPALTENBRUCH-Markierung
    zaehlt dabei nicht als eigene Zeile: sie ist nur eine Formatierungsentscheidung (erzwungener Absatz), keine
    Aussage ueber den Inhalt, und soll die Pruefung des eigentlichen Lesefluss nicht verfaelschen."""
    zeilen = [z.strip() for z in text.replace("\r", "\n").split("\n") if z.strip() and z.strip() != SPALTENBRUCH]
    return sum(1 for a, b in zip(zeilen, zeilen[1:]) if len(a) >= 25 and len(b) >= 3 and b[0].islower() and a[-1] in ".!?:;")


def bereiche(tp) -> list[tuple[int, int, bool, bool]] | None:
    """Zeichenbereiche (start, ende, Fortsetzung, harte Grenze) in Lesereihenfolge, oder None wenn die Reihenfolge
    schon stimmt oder die neue nicht sicher besser ist. Fortsetzung: der Bereich schliesst in derselben Zeile an den
    davor an (Leerzeichen statt Umbruch). Harte Grenze: hier liegt ein Sprung im Strom (Spalten-/Bandwechsel); ein
    Absatz darf sich nie darueber hinweg bilden, auch wenn beide Seiten wie Fliesstext aussehen (siehe seitentext())."""
    laeufe = laeufe_lesen(tp)
    _, ordnung, harte_bruch = _ordnung_mit_bruechen(laeufe)
    if ordnung is None:
        return None
    liste = [(laeufe[i][0], laeufe[i][1], bool(laeufe[i][3]) and k > 0 and ordnung[k - 1] == i - 1, i in harte_bruch)
             for k, i in enumerate(ordnung)]
    # Kontrolle am Text: die neue Reihenfolge darf keine zusaetzlichen Satzbrueche erzeugen, sonst bleibt alles wie es war
    if satzbrueche(seitentext(tp, liste)) > satzbrueche(tp.get_text_range()):
        return None
    return liste


def seitentext(tp, bereich_liste: list[tuple[int, int, bool, bool]] | None, lesen=None) -> str:
    """Text der Seite; ohne Bereichsliste wie PDFium ihn liefert. lesen(start, ende) liest einen Zeichenbereich
    (Standard: get_text_range; zeichen.py liest damit Zeichen fuer Zeichen mit Korrekturen)."""
    if bereich_liste is None:
        return tp.get_text_range()
    teile: list[str] = []
    for start, ende, fortsetzung, hart in bereich_liste:
        stueck = lesen(start, ende) if lesen else tp.get_text_range(start, ende - start)
        if teile:
            # Jeder Lauf traegt praktisch immer seinen eigenen Zeilenumbruch (\r\n) schon am Ende (PDFium schliesst
            # ihn im Zeichenbereich mit ein), das reicht als weicher Umbruch. Eine harte Grenze braucht trotzdem
            # IMMER den Marker: sie darf sich nie darauf verlassen, dass zufaellig schon ein Umbruch dasteht.
            endet_schon = teile[-1].endswith(("\n", "\r", "￾", "\x02"))
            if hart:
                teile[-1] += f"{SPALTENBRUCH}\r\n" if endet_schon else f"\r\n{SPALTENBRUCH}\r\n"
            elif not endet_schon:
                if not fortsetzung:
                    teile[-1] += "\r\n"
                elif not teile[-1].endswith(" "):
                    teile[-1] += " "
        teile.append(stueck)
    return "".join(teile)
