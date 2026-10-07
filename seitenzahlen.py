"""Gedruckte Seitenzahlen je PDF-Seite, damit Quellenangaben aus der .md stimmen.

Die PDF-Seite (Position in der Datei) ist fast nie die gedruckte Seite: Buecher haben einen Vorspann mit roemischen
Zahlen (Versatz meist 4 bis 24 Seiten), Normen ein nationales Deckblatt und Vorwort (Versatz 2 bis 6). Zitiert wird
aber die gedruckte Seite.

Quellen, in dieser Reihenfolge:
1. Seitenlabel der PDF (`FPDF_GetPageLabel`): Verlage hinterlegen dort die gedruckte Zahl, auch roemisch ("xii").
   Nur, wenn es nicht bloss die Position wiederholt und den Zahlen am Seitenrand nicht widerspricht.
2. Zahlen am Seitenrand (Kopf-/Fusszeile): je Seite die Kandidaten sammeln, dann Abschnitte mit gleichbleibendem
   Versatz (PDF-Seite minus Zahl) suchen. Eine einzelne Zahl zaehlt nie, erst eine Folge ueber mehrere Seiten.
   Seiten ohne eigene Zahl (Kapitelanfang, Bildseite) innerhalb eines Abschnitts bekommen die Zahl aus dem Versatz.
Wo beides nichts Sicheres liefert, bleibt die Seite ohne gedruckte Zahl (lieber keine als eine falsche Angabe)."""
from __future__ import annotations

import ctypes
import re

RAND = 4                    # so viele Zeilen am Seitenanfang/-ende koennen die Seitenzahl enthalten
MIN_BELEGE = 3              # so viele Seiten muessen denselben Versatz zeigen, damit ein Abschnitt gilt
MIN_DICHTE = 0.4            # Anteil belegter Seiten in einem Abschnitt
MAX_LUECKE = 8              # so viele Seiten ohne Beleg darf ein Abschnitt ueberbruecken
VERLAENGERUNG = 2           # so viele Seiten vor/nach einem Abschnitt bekommen ebenfalls eine Zahl
MIN_UEBEREINSTIMMUNG = 0.8  # so oft muessen Label und Randzahl uebereinstimmen, damit das Label gilt
VORSEITEN = 6               # Normen: nationale Vorseiten mit Versatz 0 ("2" auf PDF-Seite 2) duerfen kurz sein

ZAHL_ALLEIN = re.compile(r"[-–—]?\s*(\d{1,4})\s*[-–—]?")
SEITE_X = re.compile(r"(?:Seite|S\.|Page)\s*(\d{1,4})(?:\s*(?:von|of|/)\s*\d{1,4})?", re.IGNORECASE)
ZAHL_VORN = re.compile(r"(\d{1,4})\s{1,6}(?:\d{1,3}\s+)?[^\d\s.,:;/)\-–].{0,90}")   # "584 10 Beziehungen zur ..."
ZAHL_HINTEN = re.compile(r".{0,90}[^\d\s.,:;/(\-–]\s{1,6}(\d{1,4})")            # "12.3 Aufbau des Prüfstands 197"
GUELTIGES_LABEL = re.compile(r"[0-9A-Za-z][0-9A-Za-z.\-–]{0,11}")


def label_lesen(dokument) -> list[str | None]:
    """Seitenlabel je Seite (pypdfium2-Dokument). None, wo keins hinterlegt ist."""
    import pypdfium2.raw as raw
    ergebnis: list[str | None] = []
    for i in range(len(dokument)):
        try:
            n = raw.FPDF_GetPageLabel(dokument.raw, i, None, 0)
            if n <= 2:
                ergebnis.append(None)
                continue
            puffer = ctypes.create_string_buffer(n)
            raw.FPDF_GetPageLabel(dokument.raw, i, puffer, n)
            text = puffer.raw[:n - 2].decode("utf-16-le", errors="replace").strip()
            ergebnis.append(text if GUELTIGES_LABEL.fullmatch(text) else None)
        except Exception:
            ergebnis.append(None)
    return ergebnis


def kandidaten(zeilen: list[str]) -> set[int]:
    """Zahlen, die auf einer Seite (Zeilen ohne Wasserzeichen) als Seitenzahl in Frage kommen."""
    rand = zeilen[:RAND] + zeilen[-RAND:] if len(zeilen) > 2 * RAND else zeilen
    gefunden = set()
    for z in rand:
        z = z.strip()
        if not z or len(z) > 100:
            continue
        for muster in (ZAHL_ALLEIN, SEITE_X):
            m = muster.fullmatch(z)
            if m:
                gefunden.add(int(m.group(1)))
        for muster in (ZAHL_VORN, ZAHL_HINTEN):
            m = muster.fullmatch(z)
            if m:
                gefunden.add(int(m.group(1)))
    return {z for z in gefunden if 0 < z < 5000}


def aus_randzahlen(alle: list[set[int]]) -> list[int | None]:
    """Gedruckte Zahl je Seite aus den Randzahlen (siehe Moduldoku). Seiten 0-basiert, Zahlen wie gedruckt."""
    n = len(alle)
    belege: dict[int, list[int]] = {}
    for i, zahlen in enumerate(alle):
        for z in zahlen:
            belege.setdefault(i + 1 - z, []).append(i)
    abschnitte = []                                     # (Belege, Anfang, Ende, Versatz)
    for versatz, seiten in belege.items():
        lauf = [seiten[0]]
        for s in seiten[1:] + [None]:
            if s is not None and s - lauf[-1] <= MAX_LUECKE:
                lauf.append(s)
                continue
            anfang, ende = lauf[0], lauf[-1]
            dichte = len(lauf) / (ende - anfang + 1)
            if ((len(lauf) >= MIN_BELEGE and dichte >= MIN_DICHTE)
                    or (versatz == 0 and ende < VORSEITEN and len(lauf) >= 1 and dichte >= 0.5)):
                abschnitte.append((len(lauf), anfang, ende, versatz))
            if s is not None:
                lauf = [s]
    ergebnis: list[int | None] = [None] * n
    staerke = [0] * n
    for belegt, anfang, ende, versatz in sorted(abschnitte, reverse=True):
        for i in range(anfang, ende + 1):
            if ergebnis[i] is None and i + 1 - versatz > 0:
                ergebnis[i], staerke[i] = i + 1 - versatz, belegt
    # Seiten direkt vor/nach einem Abschnitt (Deckblatt, letzte Seite ohne Zahl) gehoeren meist noch dazu. Steht eine
    # Seite zwischen zwei Abschnitten, gewinnt der folgende, wenn er dort mit 1 beginnt (EN-Deckblatt einer DIN-EN-Norm).
    for belegt, anfang, ende, versatz in sorted(abschnitte, reverse=True):
        for i in range(anfang - 1, max(-1, anfang - 1 - VERLAENGERUNG), -1):
            zahl = i + 1 - versatz
            if zahl < 1:
                break
            if ergebnis[i] is None or (staerke[i] < 0 and zahl == 1):
                ergebnis[i], staerke[i] = zahl, -1
            elif ergebnis[i] != zahl:
                break
        for i in range(ende + 1, min(n, ende + 1 + VERLAENGERUNG)):
            if ergebnis[i] is not None:
                break
            ergebnis[i], staerke[i] = i + 1 - versatz, -2
    return ergebnis


def _als_zahl(label: str | None) -> int | None:
    return int(label) if label and label.isdigit() else None


def zuordnen(labels: list[str | None] | None, randzahlen: list[set[int]]) -> tuple[list[str | None], str]:
    """Gedruckte Seitenzahl je Seite (Text, z.B. "197" oder "xii", sonst None) und die Quelle."""
    n = len(randzahlen)
    aus_rand = aus_randzahlen(randzahlen)
    labels = (labels or []) + [None] * (n - len(labels or []))
    eigene = [i for i, l in enumerate(labels[:n]) if l and l != str(i + 1)]
    if labels and len(eigene) >= max(1, n // 10):
        # Label nur, wenn es den Randzahlen nicht widerspricht (manche PDFs haben Labels, die nicht zur Druckseite passen)
        vergleich = [(_als_zahl(labels[i]), aus_rand[i]) for i in range(n)
                     if aus_rand[i] is not None and _als_zahl(labels[i]) is not None]
        gleich = sum(1 for a, b in vergleich if a == b)
        if not vergleich or gleich >= MIN_UEBEREINSTIMMUNG * len(vergleich):
            return list(labels[:n]), "Seitenlabel der PDF"
    if any(z is not None for z in aus_rand):
        return [str(z) if z is not None else None for z in aus_rand], "Seitenzahlen am Seitenrand"
    return [None] * n, ""
