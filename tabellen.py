"""Tabellen mit gezeichnetem Gitter (Normen, viele Fachbuecher) als Markdown-Tabellen.

Erkannt wird nur, was eindeutig ist: ein Gitter aus waagerechten und senkrechten Linien, die an anderen Gitterlinien
enden (Linien von Zeichnungen haengen meist frei). Tabellen ohne Linien, nur mit Leerraum, bleiben Text; so wird aus
Formeln und Fliesstext nie eine Tabelle (das Problem des MarkItDown-Wegs). echt() prueft zusaetzlich am Text, dass das
Gitter keine Zeichnung und kein Diagramm ist.

Ablauf je Seite:
  linien()   duenne Pfadobjekte (und die Kanten umrandeter Rechtecke) als waagerechte/senkrechte Strecken
  gitter()   Strecken zusammenfassen, freie Enden kuerzen/entfernen, zusammenhaengende Gitter mit >= 2x2 Zellen
  zellen     Zeilen-/Spaltengrenzen, verbundene Zellen (fehlende Trennlinie), jedes Zeichen in seine Zelle
  markdown   | a | b |-Zeilen; verbundene Zellen stehen in ihrer ersten Zelle, die uebrigen bleiben leer

Das Ergebnis wird als Korrektur im Zeichenstrom eingesetzt (siehe zeichen.py): das erste Zeichen der Tabelle wird zur
ganzen Markdown-Tabelle, alle anderen Zeichen der Tabelle entfallen. So bleiben Lesereihenfolge, Zeichenkorrektur und
Formelreparatur der uebrigen Seite unberuehrt.
"""

import ctypes
import math
import re
import unicodedata
from dataclasses import dataclass, field

import pypdfium2.raw as raw

MAX_DICKE = 2.5         # pt: dicker ist keine Linie mehr, sondern eine Flaeche
MIN_LAENGE = 4.0        # pt: kuerzere Strecken sind Punkte oder Ecken
TOLERANZ = 2.0          # pt: so nah muessen Linienenden/Kreuzungen beieinander liegen
MIN_ZEILEN = 2
MIN_SPALTEN = 2
MIN_BELEGT = 0.25       # so viel Anteil der Zellen muss Text enthalten
MIN_GEFUELLT = 3        # ... und mindestens so viele Zellen, verteilt ueber mindestens zwei Zeilen und zwei Spalten
MAX_SCHNITTE = 1        # so oft darf eine Gitterlinie ein Wort zerschneiden (Zeichnung statt Tabelle, siehe einsetzen)
# Duenn gefuellte Gitter (Anteil gefuellter Zellen < DUENN) sind oft Schaltbilder/Diagramme. Gemessen an 57 Buechern und
# 46 Normen: Schaltbilder haben viele verbundene Zellen (Zellen je Elementarzelle < MIN_REGELMAESSIG), Abbildungen mit
# Rahmen sind klein (<= KLEIN Zellen oder hoechstens 2 Spalten) und kurz beschriftet (< MIN_TEXTLAENGE Zeichen je Zelle).
DUENN = 0.5
MIN_REGELMAESSIG = 0.6
KLEIN = 16
MIN_TEXTLAENGE = 15
MAX_ZELLEN = 5000       # Schutz gegen riesige Raster (Millimeterpapier, Zeichnungen)


@dataclass
class Strecke:
    lage: float         # y (waagerecht) bzw. x (senkrecht)
    von: float
    bis: float
    roh_von: float | None = None    # Ausdehnung vor dem Kuerzen freier Enden (fuer seitlich offene Tabellen)
    roh_bis: float | None = None

    def roh(self) -> "Strecke":
        """Die Strecke in ihrer urspruenglichen Laenge."""
        return Strecke(self.lage, self.von if self.roh_von is None else self.roh_von,
                       self.bis if self.roh_bis is None else self.roh_bis)


@dataclass
class Tabelle:
    xs: list[float]                     # Spaltengrenzen, aufsteigend
    ys: list[float]                     # Zeilengrenzen, absteigend (PDF: y waechst nach oben)
    waagerecht: list[Strecke]
    senkrecht: list[Strecke]
    bereich: dict = field(default_factory=dict)   # (zeile, spalte) -> Nummer der (verbundenen) Zelle
    zellen: dict = field(default_factory=dict)    # Nummer -> Liste von Textteilen
    nur_waagerecht: bool = False                  # Tabelle ohne senkrechte Linien (Spalten aus dem Leerraum)

    @property
    def rahmen(self) -> tuple[float, float, float, float]:
        return self.xs[0], self.ys[-1], self.xs[-1], self.ys[0]

    def enthaelt(self, x: float, y: float) -> bool:
        l, b, r, t = self.rahmen
        return l - 0.5 <= x <= r + 0.5 and b - 0.5 <= y <= t + 0.5


def _pfad_ist_rechteck(obj) -> bool:
    n = raw.FPDFPath_CountSegments(obj)
    return 4 <= n <= 6


def linien(seite) -> tuple[list[Strecke], list[Strecke]]:
    """Waagerechte und senkrechte Strecken der Seite (PDF-Koordinaten, pt)."""
    waagerecht: list[Strecke] = []
    senkrecht: list[Strecke] = []
    for obj in seite.get_objects(filter=[raw.FPDF_PAGEOBJ_PATH], max_depth=3):
        try:
            l, b, r, t = obj.get_bounds()
        except Exception:
            continue
        w, h = r - l, t - b
        if h <= MAX_DICKE and w >= MIN_LAENGE:
            waagerecht.append(Strecke((b + t) / 2, l, r))
        elif w <= MAX_DICKE and h >= MIN_LAENGE:
            senkrecht.append(Strecke((l + r) / 2, b, t))
        elif w > MAX_DICKE and h > MAX_DICKE and _pfad_ist_rechteck(obj):
            fuellung, strich = ctypes.c_int(), ctypes.c_int()
            raw.FPDFPath_GetDrawMode(obj, ctypes.byref(fuellung), ctypes.byref(strich))
            if strich.value and not fuellung.value:          # nur umrandete Rechtecke; gefuellte sind Hintergrund
                waagerecht += [Strecke(b, l, r), Strecke(t, l, r)]
                senkrecht += [Strecke(l, b, t), Strecke(r, b, t)]
    return waagerecht, senkrecht


def _zusammenfassen(strecken: list[Strecke]) -> list[Strecke]:
    """Strecken auf derselben Lage, die sich beruehren oder ueberlappen, werden eine Strecke."""
    ergebnis: list[Strecke] = []
    for s in sorted(strecken, key=lambda s: (round(s.lage / TOLERANZ), s.von)):
        if ergebnis:
            letzte = ergebnis[-1]
            if abs(letzte.lage - s.lage) <= TOLERANZ and s.von <= letzte.bis + TOLERANZ:
                letzte.bis = max(letzte.bis, s.bis)
                continue
        ergebnis.append(Strecke(s.lage, s.von, s.bis))
    return ergebnis


def _beruehrt(w: Strecke, s: Strecke) -> bool:
    """Kreuzen oder beruehren sich eine waagerechte und eine senkrechte Strecke?"""
    return (w.von - TOLERANZ <= s.lage <= w.bis + TOLERANZ) and (s.von - TOLERANZ <= w.lage <= s.bis + TOLERANZ)


def _verankert(ende: float, lage_andere: list[float]) -> bool:
    return any(abs(ende - x) <= TOLERANZ for x in lage_andere)


MAX_FREIES_ENDE = 0.5   # so viel der Laenge darf ein frei haengendes Endstueck ausmachen, um nur gekuerzt zu werden


def _kuerzen(strecke: Strecke, kreuzungen: list[float]) -> Strecke | None:
    """Die Strecke zwischen ihrer ersten und letzten Kreuzung, oder None, wenn sie keine Gitterlinie ist: weniger als
    zwei Kreuzungen oder frei haengende Enden, die zusammen mehr als MAX_FREIES_ENDE der Laenge ausmachen. Kurze freie
    Enden kommen in echten Tabellen vor: eine Trennlinie, die mitten in einer verbundenen Kopfzelle endet
    (Normtabelle: "µm | mm")."""
    if len(kreuzungen) < 2:
        return None
    von, bis = min(kreuzungen), max(kreuzungen)
    if _verankert(strecke.von, kreuzungen) and _verankert(strecke.bis, kreuzungen):
        return strecke
    frei = max(von - strecke.von, 0) + max(strecke.bis - bis, 0)
    if frei > MAX_FREIES_ENDE * (strecke.bis - strecke.von):
        return None
    roh = strecke.roh()
    return Strecke(strecke.lage, von, bis, roh.von, roh.bis)


def _freie_enden_entfernen(waagerecht: list[Strecke], senkrecht: list[Strecke]):
    """Gitterlinien enden an anderen Gitterlinien; Linien von Zeichnungen (Masspfeile, Kanten) haengen meist frei.
    Kurze freie Enden werden abgeschnitten, Linien mit langen freien Enden entfallen. Wiederholt, bis sich nichts mehr
    aendert."""
    while True:
        w_neu = [k for k in (_kuerzen(w, [s.lage for s in senkrecht if _beruehrt(w, s)]) for w in waagerecht) if k]
        s_neu = [k for k in (_kuerzen(s, [w.lage for w in w_neu if _beruehrt(w, s)]) for s in senkrecht) if k]
        gleich = (len(w_neu) == len(waagerecht) and len(s_neu) == len(senkrecht)
                  and all((a.von, a.bis) == (b.von, b.bis) for a, b in zip(w_neu + s_neu, waagerecht + senkrecht)))
        if gleich:
            return w_neu, s_neu
        waagerecht, senkrecht = w_neu, s_neu


def _gruppen(waagerecht: list[Strecke], senkrecht: list[Strecke]) -> list[tuple[list[Strecke], list[Strecke]]]:
    """Zusammenhaengende Gitter (Zusammenhangskomponenten ueber Kreuzungen)."""
    alle = [("w", i) for i in range(len(waagerecht))] + [("s", i) for i in range(len(senkrecht))]
    eltern = {k: k for k in alle}

    def wurzel(k):
        while eltern[k] != k:
            eltern[k] = eltern[eltern[k]]
            k = eltern[k]
        return k

    for i, w in enumerate(waagerecht):
        for j, s in enumerate(senkrecht):
            if _beruehrt(w, s):
                eltern[wurzel(("w", i))] = wurzel(("s", j))
    gruppen: dict = {}
    for k in alle:
        gruppen.setdefault(wurzel(k), ([], []))[0 if k[0] == "w" else 1].append(
            waagerecht[k[1]] if k[0] == "w" else senkrecht[k[1]])
    return list(gruppen.values())


def _grenzen(werte: list[float]) -> list[float]:
    ergebnis: list[float] = []
    for v in sorted(werte):
        if ergebnis and v - ergebnis[-1] <= TOLERANZ:
            continue
        ergebnis.append(v)
    return ergebnis


def _abgedeckt(strecken: list[Strecke], lage: float, von: float, bis: float) -> bool:
    """Liegt auf 'lage' eine Linie, die den Abschnitt von..bis (zur Haelfte) abdeckt?"""
    laenge = bis - von
    for s in strecken:
        if abs(s.lage - lage) <= TOLERANZ:
            ueberlapp = min(s.bis, bis) - max(s.von, von)
            if ueberlapp >= 0.5 * laenge:
                return True
    return False


MIN_UEBERSTAND = 3 * TOLERANZ   # so weit (pt) muessen waagerechte Linien ueber die aeusserste senkrechte hinausragen


def _offene_seiten(xs: list[float], waagerecht: list[Strecke]) -> tuple[list[float], list[Strecke]]:
    """Seitlich offene Tabellen: die aeusseren Spalten haben keine senkrechte Randlinie, nur die waagerechten Linien
    reichen bis dorthin (Buch mit Normtabelle: "Zeile | Bezug | ... | Spalte 7"). Ragen mindestens zwei waagerechte
    Linien auf einer Seite ueber die aeusserste senkrechte Linie hinaus, bekommt die Tabelle dort eine Randspalte.
    Sonst endete das Gitter an der letzten senkrechten Linie, die Randspalten fielen heraus und ihre Woerter wurden
    am Rand zerschnitten ("Nennmaße|n in m")."""
    roh = [y.roh() for y in waagerecht]
    links = [y.von for y in roh if y.von < xs[0] - MIN_UEBERSTAND]
    rechts = [y.bis for y in roh if y.bis > xs[-1] + MIN_UEBERSTAND]
    if len(links) < 2 and len(rechts) < 2:
        return xs, waagerecht
    neu = list(xs)
    if len(links) >= 2:
        neu.insert(0, min(links))
    if len(rechts) >= 2:
        neu.append(max(rechts))
    return neu, roh


def gitter(seite) -> list[Tabelle]:
    """Alle Gitter-Tabellen einer Seite (noch ohne Text)."""
    waagerecht, senkrecht = linien(seite)
    if len(waagerecht) < MIN_ZEILEN + 1 or len(senkrecht) < MIN_SPALTEN + 1:
        return []
    waagerecht, senkrecht = _zusammenfassen(waagerecht), _zusammenfassen(senkrecht)
    waagerecht, senkrecht = _freie_enden_entfernen(waagerecht, senkrecht)
    tabellen = []
    for w, s in _gruppen(waagerecht, senkrecht):
        xs = _grenzen([x.lage for x in s])
        ys = _grenzen([y.lage for y in w])[::-1]
        if len(xs) < MIN_SPALTEN + 1 or len(ys) < MIN_ZEILEN + 1:
            continue
        xs, w = _offene_seiten(xs, w)
        if (len(xs) - 1) * (len(ys) - 1) > MAX_ZELLEN:
            continue
        breite = xs[-1] - xs[0]
        # eine echte Tabelle hat oben und unten eine (fast) durchgehende Linie
        durchgehend = [y for y in w if y.bis - y.von >= 0.9 * breite]
        if len(durchgehend) < 2:
            continue
        tabelle = Tabelle(xs, ys, w, s)
        _verbundene_zellen(tabelle)
        tabellen.append(tabelle)
    return tabellen


# ---------------------------------------------------------------- Tabellen nur mit waagerechten Linien
# Viele Verlage (Springer, TeX "booktabs") setzen Tabellen ohne senkrechte Linien: eine Linie oben, eine unter dem Kopf,
# eine unten. Die Spalten ergeben sich dann aus dem Leerraum, der in allen Zeilen frei bleibt.
LINIEN_MIN_BREITE = 0.25    # Anteil der Seitenbreite, den die Linien mindestens haben
LINIEN_GLEICH = 3.0         # pt: so genau stimmen Anfang und Ende der Linien einer Tabelle ueberein
LINIEN_MAX_ABSTAND = 0.7    # Anteil der Seitenhoehe, ueber den eine Tabelle hoechstens reicht
MIN_DATENZEILEN = 3         # so viele Zeilen braucht der Tabellenrumpf
MIN_SPALTENLUECKE = 0.55    # x Schriftgroesse: so breit muss der Leerraum zwischen zwei Spalten in jeder Zeile sein
MAX_ZELLTEXT = 40           # mittlere Zeichen je Zelle; Fliesstext zwischen Linien hat laengere "Zellen"


@dataclass
class Linienkandidat:
    links: float
    rechts: float
    ys: list[float]         # Linien von oben nach unten


def linien_kandidaten(seite, gitter_: list[Tabelle] | None = None) -> list[Linienkandidat]:
    """Gruppen aus >= 3 gleich langen, breiten waagerechten Linien ohne senkrechte Linie dazwischen (sonst ist es ein
    Gitter und gitter() zustaendig)."""
    waagerecht, senkrecht = linien(seite)
    breite_seite, hoehe_seite = seite.get_width(), seite.get_height()
    breit = sorted((w for w in _zusammenfassen(waagerecht) if w.bis - w.von >= LINIEN_MIN_BREITE * breite_seite),
                   key=lambda w: -w.lage)
    gruppen: list[list[Strecke]] = []
    for w in breit:
        for g in gruppen:
            if abs(g[0].von - w.von) <= LINIEN_GLEICH and abs(g[0].bis - w.bis) <= LINIEN_GLEICH \
                    and g[0].lage - w.lage <= LINIEN_MAX_ABSTAND * hoehe_seite:
                g.append(w)
                break
        else:
            gruppen.append([w])
    kandidaten = []
    for g in gruppen:
        if len(g) < 3:
            continue
        links, rechts = g[0].von, g[0].bis
        oben, unten = g[0].lage, g[-1].lage
        if any(links - 1 <= s.lage <= rechts + 1 and s.von < oben - 1 and s.bis > unten + 1 for s in senkrecht):
            continue
        if any(t.enthaelt((links + rechts) / 2, (oben + unten) / 2) for t in (gitter_ or [])):
            continue
        kandidaten.append(Linienkandidat(links, rechts, [w.lage for w in g]))
    return kandidaten


def _luecken(zeilen: list[list], links: float, rechts: float, groesse: float) -> list[float]:
    """Spaltengrenzen: x-Bereiche, die in keiner Zeile von einem Zeichen bedeckt sind (Mitte der Luecke)."""
    schritt = 0.5
    n = int((rechts - links) / schritt) + 1
    bedeckt = [False] * n
    for z in zeilen:
        for t in z:
            a, b = int((t.l - links) / schritt), int((t.r - links) / schritt) + 1
            for i in range(max(0, a), min(n, b)):
                bedeckt[i] = True
    grenzen, start = [], None
    for i in range(n + 1):
        frei = i < n and not bedeckt[i]
        if frei and start is None:
            start = i
        elif not frei and start is not None:
            if start > 0 and i < n and (i - start) * schritt >= MIN_SPALTENLUECKE * groesse:
                grenzen.append(links + (start + i) / 2 * schritt)
            start = None
    return grenzen


def linientabellen(kandidaten: list[Linienkandidat], teile: list) -> list[Tabelle]:
    """Tabellen aus Linienkandidaten. teile: Zeichen der Seite (formelsatz.zeichen: Rahmen, Grundlinie, Groesse)."""
    import formelsatz
    tabellen_ = []
    offen = list(kandidaten)
    while offen:
        k = offen.pop(0)
        oben, kopf_ende, unten = k.ys[0], k.ys[1], k.ys[-1]
        drin = [t for t in teile if k.links - 1 <= (t.l + t.r) / 2 <= k.rechts + 1 and unten < (t.b + t.t) / 2 < oben]
        if not drin:
            continue
        zeilen = formelsatz._zeilen(drin)                           # oben nach unten
        if len(zeilen) > 1 and TABELLENTITEL.match("".join(t.text for t in zeilen[0])):
            # Ueberschrift zwischen oberer Linie und Kopf: bleibt Text, die Tabelle beginnt darunter
            oben = (min(t.b for t in zeilen[0]) + max(t.t for t in zeilen[1])) / 2
            drin = [t for t in drin if t not in zeilen[0]]
            zeilen = zeilen[1:]
        # Zwei Tabellen untereinander mit gleich langen Linien: an der Ueberschrift "Tab. 1.6 ..." trennen
        titel = next((z for z in zeilen[1:] if TABELLENTITEL.match("".join(t.text for t in z))), None)
        if titel is not None:
            o, u = max(t.t for t in titel), min(t.b for t in titel)
            for teil_ys in ([y for y in k.ys if y > o], [y for y in k.ys if y < u]):
                if len(teil_ys) >= 3:
                    offen.insert(0, Linienkandidat(k.links, k.rechts, teil_ys))
            continue
        rumpf = [z for z in zeilen if (min(t.b for t in z) + max(t.t for t in z)) / 2 < kopf_ende]
        if len(rumpf) < MIN_DATENZEILEN:
            continue
        groesse = sorted(t.g for t in drin)[len(drin) // 2]
        grenzen = _luecken(rumpf, k.links, k.rechts, groesse)
        if not grenzen:
            continue
        xs = [k.links] + grenzen + [k.rechts]

        def erste_spalte(z) -> bool:
            return any((t.l + t.r) / 2 < xs[1] for t in z)

        def wenige_spalten(z) -> bool:
            """Fortsetzung eines umbrochenen Zelltexts fuellt nur eine oder zwei Spalten; eine Datenzeile mit leerer
            erster Spalte (gleiche Gruppe wie darueber) fuellt die meisten."""
            spalten = {next((i for i in range(len(xs) - 1) if (t.l + t.r) / 2 <= xs[i + 1]), len(xs) - 2) for t in z}
            return len(spalten) <= max(1, (len(xs) - 2) // 2)

        ys = [oben]
        mit_erster = bool(zeilen) and erste_spalte(zeilen[0])        # die laufende Tabellenzeile hat Spalte 1
        for a, b in zip(zeilen, zeilen[1:]):
            unter_kopf = max(t.t for t in b) < kopf_ende
            if unter_kopf and min(t.b for t in a) < kopf_ende and mit_erster and not erste_spalte(b) \
                    and wenige_spalten(b):
                continue                    # Fortsetzungszeile (erste Spalte leer): gehoert zur Zeile davor
            mitte = (min(t.b for t in a) + max(t.t for t in b)) / 2
            ys.append(kopf_ende if min(t.b for t in a) > kopf_ende > max(t.t for t in b) else mitte)
            mit_erster = erste_spalte(b)
        ys.append(unten)
        tabelle = Tabelle(xs, ys, [], [], nur_waagerecht=True)
        _kopf_verbinden(tabelle, [t for t in drin if (t.b + t.t) / 2 > kopf_ende], groesse)
        tabellen_.append(tabelle)
    return tabellen_


TABELLENTITEL = re.compile(r"(?:Tab\.|Tabelle|Table)\s*[A-Z]?\d")


def _kopf_verbinden(t: Tabelle, kopf: list, groesse: float) -> None:
    """Zellen: jede fuer sich, ausser im Kopf, wo ein Wort ueber mehrere Spalten reicht ("Temperatur in °C" ueber
    vier Spalten): dort werden die Zellen der Zeile verbunden, statt das Wort zu zerschneiden."""
    spalten = len(t.xs) - 1
    eltern = {(r, c): (r, c) for r in range(len(t.ys) - 1) for c in range(spalten)}

    def wurzel(k):
        while eltern[k] != k:
            eltern[k] = eltern[eltern[k]]
            k = eltern[k]
        return k

    def spalte(x: float) -> int:
        return max(0, min(spalten - 1, next((i for i in range(spalten) if x <= t.xs[i + 1]), spalten - 1)))

    def zeile(y: float) -> int | None:
        return next((i for i in range(len(t.ys) - 1) if t.ys[i + 1] <= y <= t.ys[i]), None)

    wort: list = []
    for z in sorted(kopf, key=lambda u: (-round(u.y), u.l)) + [None]:
        if wort and (z is None or abs(z.y - wort[-1].y) > 0.3 * groesse or z.l - wort[-1].r > 0.25 * groesse):
            r = zeile((wort[0].b + wort[0].t) / 2)
            cs = sorted({spalte((u.l + u.r) / 2) for u in wort})
            if r is not None:
                for c in range(cs[0], cs[-1]):
                    eltern[wurzel((r, c))] = wurzel((r, c + 1))
            wort = []
        if z is not None:
            wort.append(z)
    nummern: dict = {}
    for r in range(len(t.ys) - 1):
        for c in range(spalten):
            t.bereich[(r, c)] = nummern.setdefault(wurzel((r, c)), len(nummern))


def _verbundene_zellen(t: Tabelle) -> None:
    """Zellen ohne Trennlinie dazwischen gehoeren zusammen (Union-Find ueber die Elementarzellen)."""
    zeilen, spalten = len(t.ys) - 1, len(t.xs) - 1
    eltern = {(r, c): (r, c) for r in range(zeilen) for c in range(spalten)}

    def wurzel(k):
        while eltern[k] != k:
            eltern[k] = eltern[eltern[k]]
            k = eltern[k]
        return k

    for r in range(zeilen):
        oben, unten = t.ys[r], t.ys[r + 1]
        for c in range(spalten):
            links, rechts = t.xs[c], t.xs[c + 1]
            if c + 1 < spalten and not _abgedeckt(t.senkrecht, rechts, unten, oben):
                eltern[wurzel((r, c))] = wurzel((r, c + 1))
            if r + 1 < zeilen and not _abgedeckt(t.waagerecht, unten, links, rechts):
                eltern[wurzel((r, c))] = wurzel((r + 1, c))
    nummern: dict = {}
    for r in range(zeilen):
        for c in range(spalten):
            t.bereich[(r, c)] = nummern.setdefault(wurzel((r, c)), len(nummern))


def zelle(t: Tabelle, x: float, y: float) -> int | None:
    """Nummer der (verbundenen) Zelle, in der der Punkt liegt."""
    c = next((i for i in range(len(t.xs) - 1) if t.xs[i] - 0.5 <= x <= t.xs[i + 1] + 0.5), None)
    r = next((i for i in range(len(t.ys) - 1) if t.ys[i + 1] - 0.5 <= y <= t.ys[i] + 0.5), None)
    return None if c is None or r is None else t.bereich[(r, c)]


KOORDINATION = r"(?:und|oder|bzw|sowie|bis|u|and|or)\b"       # "Ein-" / "und Ausgabe": Strich und Leerzeichen bleiben


def _zelltext(teile: list[str]) -> str:
    """Zelltext in einer Zeile. Trennungen am Zeilenende wie im Fliesstext (pdf2md._trennungen_verbinden):
    "Kon-/struktion" -> "Konstruktion", "Ordnungs-/Nr." -> "Ordnungs-Nr.", "Ein-/und Ausgabe" bleibt."""
    text = unicodedata.normalize("NFC", "".join(teile))
    text = re.sub("\u00ad\\s+", "\u00ad\n", text)      # weiches Trennzeichen + (erzeugtes) Leerzeichen = Zeilenende
    trenn = r"([^\W\d_])[-\ufffe\x02\u00ad]\n\s*"
    text = re.sub(trenn + rf"(?={KOORDINATION})", r"\1- ", text)
    text = re.sub(trenn + r"(?=[a-zäöüß])", r"\1", text)
    text = re.sub(trenn, r"\1-", text)
    text = text.replace("\ufffe", "").replace("\x02", "").replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("|", "\\|")


def markdown(t: Tabelle) -> str:
    """Die Tabelle als Markdown. Verbundene Zellen: Text in der ersten Zelle (oben links), die anderen leer."""
    zeilen, spalten = len(t.ys) - 1, len(t.xs) - 1
    erste: dict = {}
    for r in range(zeilen):
        for c in range(spalten):
            erste.setdefault(t.bereich[(r, c)], (r, c))
    ausgabe = []
    for r in range(zeilen):
        werte = []
        for c in range(spalten):
            n = t.bereich[(r, c)]
            werte.append(_zelltext(t.zellen.get(n, [])) if erste[n] == (r, c) else "")
        if r > 0 and not any(werte):
            continue                                     # Zeile nur aus verbundenen Zellen: weglassen
        ausgabe.append("| " + " | ".join(werte) + " |")
        if r == 0:
            ausgabe.append("|" + "---|" * spalten)
    return "\n".join(ausgabe)


def belegt(t: Tabelle) -> float:
    zellen = set(t.bereich.values())
    return sum(1 for n in zellen if _zelltext(t.zellen.get(n, []))) / max(len(zellen), 1)


def echt(t: Tabelle, schnitte: int) -> bool:
    """Ist das Gitter eine Tabelle und keine Zeichnung/kein Diagramm mit Gitternetz? Eine Tabelle hat genug gefuellte
    Zellen in mehreren Zeilen und Spalten, und ihre Linien laufen nie mitten durch ein Wort. Ist sie duenn gefuellt,
    muss sie zudem ein regelmaessiges Raster haben (Schaltbilder und Diagramme bestehen aus vielen verbundenen
    Zellen) und darf kein kleiner Rahmen mit kurzen Beschriftungen sein ("θ FS", "S | N")."""
    b = belegt(t)
    if schnitte > MAX_SCHNITTE or b < MIN_BELEGT:
        return False
    erste: dict = {}
    for (r, c), n in sorted(t.bereich.items()):
        erste.setdefault(n, (r, c))                  # jede (verbundene) Zelle zaehlt mit ihrer ersten Elementarzelle
    texte = {n: _zelltext(t.zellen.get(n, [])) for n in erste}
    gefuellt = [erste[n] for n, text in texte.items() if text]
    if not (len(gefuellt) >= MIN_GEFUELLT and len({r for r, _ in gefuellt}) >= 2
            and len({c for _, c in gefuellt}) >= 2):
        return False
    if t.nur_waagerecht:
        # ohne senkrechte Linien strenger: dicht gefuellt, kurze Zellen (Fliesstext zwischen Linien hat lange "Zellen"),
        # und jede Spalte hat Text in mindestens der Haelfte der Zeilen
        zeilen = len({r for r, _ in t.bereich})
        if b < DUENN or sum(len(x) for x in texte.values()) / len(gefuellt) > MAX_ZELLTEXT:
            return False
        # zweispaltiger Fliesstext zwischen Kopf- und Fusslinie hat eine gemeinsame Luecke, aber Saetze in den "Zellen"
        if sum(1 for x in texte.values() if len(x.split()) >= 5) > 0.3 * len(gefuellt):
            return False
        if any(sum(1 for r, c2 in gefuellt if c2 == c) < 0.5 * zeilen for c in range(len(t.xs) - 1)):
            return False
    if b < DUENN:
        regelmaessig = len(erste) / len(t.bereich)
        mittlere_laenge = sum(len(text) for text in texte.values()) / len(gefuellt)
        if regelmaessig < MIN_REGELMAESSIG:
            return False
        if (len(erste) <= KLEIN or len(t.xs) - 1 <= 2) and mittlere_laenge < MIN_TEXTLAENGE:
            return False
    return True


def _schriftgroesse(tp, k: int, matrix) -> float:
    """Wirksame Schriftgroesse (pt) des Zeichens k: Schriftgroesse mal Skalierung der Textmatrix."""
    groesse = raw.FPDFText_GetFontSize(tp, k)
    if raw.FPDFText_GetMatrix(tp, k, matrix):
        groesse *= abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5
    return max(groesse, 1.0)


MARKER = "\ue001"      # wie lesefolge.SPALTENBRUCH: pdf2md macht daraus eine Leerzeile vor und nach der Tabelle


def einsetzen(tabellen: list[Tabelle], tp, ersatz: dict[int, str] | None = None) -> tuple[dict[int, str], int]:
    """Fuellt die Zellen mit den Zeichen der Seite und gibt ({Zeichenindex: Ersatz}, Anzahl Tabellen) zurueck: das
    erste Zeichen jeder Tabelle wird zur Markdown-Tabelle (mit Leerzeilen-Markern davor und danach), die anderen
    Zeichen der Tabelle entfallen. ersatz: Korrekturen aus zeichen.py, die auch im Zelltext gelten."""
    ersatz = ersatz or {}
    for t in tabellen:
        t.zellen = {}
    n = tp.count_chars()
    links, rechts, unten, oben = (ctypes.c_double() for _ in range(4))
    matrix = raw.FS_MATRIX()
    zuordnung: dict[int, tuple[int, int]] = {}      # Zeichenindex -> (Tabelle, Zelle)
    letzte: tuple[int, int] | None = None
    letzter_rahmen = None                           # (links, rechts, unten, oben) des letzten Zeichens der Tabelle
    trenner = ""
    schnitte: dict[int, int] = {}                   # Tabelle -> wie oft eine Linie ein Wort zerschneidet
    vorher_ziel, vorher_rahmen, luecke = None, None, True   # letztes sichtbares Zeichen der Seite, Leerraum seitdem
    gesehen: set = set()        # (Zelle, Code, Lage): manche PDFs enthalten den Tabellentext doppelt an derselben Stelle
    for k in range(n):
        code = raw.FPDFText_GetUnicode(tp, k)
        if raw.FPDFText_GetTextIndexFromCharIndex(tp, k) == -1:
            continue
        if code in (32, 9, 10, 13, 0xA0):
            if ersatz.get(k, None) != "":           # von zeichen.py gestrichenes Leerzeichen ("fu¨ r") trennt nicht
                luecke = True
                if letzte is not None:
                    trenner = "\n" if code in (10, 13) else (trenner or " ")
            if letzte is not None:
                zuordnung[k] = letzte              # Leerraum innerhalb der Tabelle entfaellt ebenfalls
            continue
        if not raw.FPDFText_GetCharBox(tp, k, links, rechts, unten, oben):
            continue
        x, y = (links.value + rechts.value) / 2, (unten.value + oben.value) / 2
        ziel = None
        for ti, t in enumerate(tabellen):
            if t.enthaelt(x, y):
                z = zelle(t, x, y)
                if z is not None:
                    ziel = (ti, z)
                break
        zeichen = ersatz.get(k, chr(code) if code < 0xD800 or code > 0xDFFF else "")
        if ziel is not None:
            doppelt = (ziel, code, round(links.value, 1), round(unten.value, 1))
            if doppelt in gesehen:                  # zweite Kopie desselben Zeichens (doppelte Inhaltsebene)
                zuordnung[k] = ziel
                continue
            gesehen.add(doppelt)
        if 0x300 <= code <= 0x36F or zeichen[:1] and 0x300 <= ord(zeichen[0]) <= 0x36F:
            if ziel is not None and letzte == ziel:
                tabellen[ziel[0]].zellen.setdefault(ziel[1], []).append(zeichen)   # Akzent gehoert zum Buchstaben
                zuordnung[k] = ziel
            continue
        # Zeichen derselben Zeile ueberlappen sich quer zur Schreibrichtung (bei senkrechten Spaltenkoepfen, um 90°
        # gedreht, also waagerecht); Leerzeichen liefert PDFium selbst (erzeugte Zeichen)
        senkrecht = abs(math.sin(raw.FPDFText_GetCharAngle(tp, k))) > 0.7
        # Wortschnitt: zwei Zeichen ohne Leerraum dazwischen, dicht nebeneinander auf derselben Zeile, aber nicht in
        # derselben Zelle. Dann laeuft eine Gitterlinie mitten durch ein Wort, auch der Aussenrand ("• Da|s Feed"
        # in einem Textkasten mit Randlinie): so etwas ist nie eine Tabelle.
        if not luecke and not senkrecht and vorher_rahmen is not None and ziel != vorher_ziel \
                and unten.value < vorher_rahmen[3] and oben.value > vorher_rahmen[2]:
            groesse = _schriftgroesse(tp, k, matrix)
            if -0.2 * groesse <= links.value - vorher_rahmen[1] < 0.25 * groesse:
                for beteiligt in {z_[0] for z_ in (ziel, vorher_ziel) if z_ is not None}:
                    schnitte[beteiligt] = schnitte.get(beteiligt, 0) + 1
        vorher_ziel, vorher_rahmen, luecke = ziel, (links.value, rechts.value, unten.value, oben.value), False
        if ziel is None:
            letzte, trenner = None, ""
            continue
        ti, z = ziel
        teile = tabellen[ti].zellen.setdefault(z, [])
        if letzter_rahmen is None:
            gleiche_zeile = False
        elif senkrecht:
            gleiche_zeile = links.value < letzter_rahmen[1] and rechts.value > letzter_rahmen[0]
        else:
            gleiche_zeile = unten.value < letzter_rahmen[3] and oben.value > letzter_rahmen[2]
        if teile and letzte == ziel:
            if not trenner and letzter_rahmen is not None and not gleiche_zeile:
                trenner = "\n"                      # neue Zeile in der Zelle ohne Umbruchzeichen ("+6" ueber "+4")
            if trenner:
                teile.append(trenner)
        elif letzte != ziel and teile:
            teile.append("\n")                      # die Zelle wird nach einer anderen Zelle fortgesetzt
        teile.append(zeichen)
        zuordnung[k] = ziel
        letzte, trenner = ziel, ""
        letzter_rahmen = (links.value, rechts.value, unten.value, oben.value)
    ergebnis: dict[int, str] = {}
    gefunden = 0
    for ti, t in enumerate(tabellen):
        indizes = sorted(k for k, (tj, _) in zuordnung.items() if tj == ti)
        if not indizes or not echt(t, schnitte.get(ti, 0)):
            continue                                # keine Tabelle: der Text bleibt, wie er ist
        gefunden += 1
        for k in indizes:
            ergebnis[k] = ""
        ergebnis[indizes[0]] = f"\r\n{MARKER}\r\n{markdown(t)}\r\n{MARKER}\r\n"
    return ergebnis, gefunden


def tabellen_der_seite(seite, tp, ersatz: dict[int, str] | None = None) -> tuple[dict[int, str], int]:
    """Erkennen und Einsetzen in einem Schritt (siehe gitter() und einsetzen())."""
    tabellen = gitter(seite)
    return einsetzen(tabellen, tp, ersatz) if tabellen else ({}, 0)
