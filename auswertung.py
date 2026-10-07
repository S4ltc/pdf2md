"""Auswertung fuer das Fenster: Kennzahlen aus Protokoll.csv und den Kopfbloecken der .md.

Nur reine Funktionen: Text, Dicts und Listen hinein, Zahlen heraus (Dateien liest ui_app.py). Die Dauer einer
Umwandlung steht nicht im Protokoll; sie ergibt sich aus dem Abstand der Zeitstempel innerhalb eines Laufs (die erste
Datei: Abstand zum Laufbeginn, denn "lauf" ist die Startzeit). Seitenzahlen kommen aus dem Kopfblock (Feld seiten).
Aeltere .md haben nicht alle Kopfblockfelder; fehlende Angaben zaehlen als 0 und "aktuell" sagt, welche Buecher mit dem
aktuellen Verfahren erzeugt sind."""

import csv
import io
import re
from collections import Counter
from datetime import datetime
from pathlib import PureWindowsPath

UMWANDLUNG = ("OK", "PRÜFEN", "FEHLER", "TEXT_ERNEUERT")      # Zeilen, die eine Umwandlung (mit Dauer) sind
ARTEN = {"OK": "Umwandlung", "PRÜFEN": "Umwandlung", "FEHLER": "Umwandlung", "NACHGEBESSERT": "Umwandlung",
         "TEXT_ERNEUERT": "Text erneuert", "UMBENANNT": "Umbenannt", "RÜCKGÄNGIG": "Rückgängig"}
MAX_DAUER = 6 * 3600              # laengere Abstaende sind keine Umwandlung (Rueckfrage offen, Rechner im Ruhezustand)
KATEGORIEN = ("Crossref", "Norm", "Text", "PDF-Metadaten", "Dokument", "von Hand", "fehlt")
FELDER = ("titel", "autor", "jahr")

GEDRUCKT = re.compile(r"<!-- Seite \S+ \(PDF \d+\) -->")
NUR_PDF = re.compile(r"<!-- PDF-Seite \d+ -->")
UNSICHER = "⚠[Formel unsicher]"
ERSETZT = re.compile(r"\((\d+) Zeichen ersetzt\)")
HOCHTIEF = re.compile(r"(\d+) Hoch-/Tiefstellungen")
FORMELTEILE = re.compile(r"(\d+) Formelteile")
ZAHL_VORN = re.compile(r"\s*(\d+)")
IM_TEXT = re.compile(r"\((\d+) direkt im Text")
FORMELZEILE = re.compile(r"\$[^$\n]+\$")                    # wie pdf2md.FORMELSTUECK: eine Zeile mit LaTeX-Formel
# Tabellentitel am Zeilenanfang ("Tabelle 3.2", "Tab. 4-1", "Table A1"); je Buch zaehlt jede Nummer einmal
TABELLENTITEL = re.compile(r"^[ \t]*(?:#+[ \t]*)?(?:Tabelle|Tab\.|Table)[ \t]*([A-Z]?\d+(?:[.\-–]\d+)*)", re.MULTILINE)


def protokoll_lesen(text: str) -> list[dict]:
    """Protokoll.csv (Semikolon, BOM erlaubt) als Liste von Zeilen."""
    text = text.lstrip("﻿")
    if not text.strip():
        return []
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def _zeit(wert: str | None) -> datetime | None:
    try:
        return datetime.strptime(wert or "", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _name(zeile: dict) -> str:
    return zeile.get("neuer_name") or PureWindowsPath(zeile.get("md_pfad") or "").stem or zeile.get("original_name", "")


def _seiten(zeile: dict, seiten_je_name: dict[str, int]) -> int | None:
    for schluessel in (_name(zeile), zeile.get("original_name")):
        if schluessel and schluessel in seiten_je_name:
            return seiten_je_name[schluessel]
    return None


def _gruppen(zeilen: list[dict]) -> dict[tuple[str, str], list[dict]]:
    gruppen: dict[tuple[str, str], list[dict]] = {}
    for z in zeilen:
        art = ARTEN.get(z.get("status", ""))
        if art:
            gruppen.setdefault((z.get("lauf", ""), art), []).append(z)
    return gruppen


def _plausibel(sekunden: float | None) -> int | None:
    return int(sekunden) if sekunden is not None and 0 <= sekunden <= MAX_DAUER else None


def dauern(zeilen: list[dict], seiten_je_name: dict[str, int]) -> list[dict]:
    """Je umgewandelter Datei: Name, Lauf, Dauer in Sekunden (oder None) und Seiten (oder None)."""
    ergebnis = []
    for (lauf, _), gruppe in _gruppen(zeilen).items():
        vorher = _zeit(lauf)
        for z in sorted(gruppe, key=lambda z: z.get("zeit", "")):
            jetzt = _zeit(z.get("zeit"))
            if z.get("status") in UMWANDLUNG:
                dauer = (jetzt - vorher).total_seconds() if jetzt and vorher else None
                ergebnis.append({"name": _name(z), "lauf": lauf, "dauer_s": _plausibel(dauer),
                                 "seiten": _seiten(z, seiten_je_name)})
            vorher = jetzt or vorher
    return ergebnis


def laeufe(zeilen: list[dict], seiten_je_name: dict[str, int]) -> list[dict]:
    """Je Lauf und Art (Umwandlung, Text erneuert, Umbenannt, Rückgängig): Dateien, Ausgang, Dauer, Seiten/min."""
    ergebnis = []
    for (lauf, art), gruppe in _gruppen(zeilen).items():
        stati = Counter(z.get("status") for z in gruppe)
        umgewandelt = [z for z in gruppe if z.get("status") in UMWANDLUNG]
        dauer = seiten = None
        if umgewandelt:
            ende = max((_zeit(z.get("zeit")) for z in umgewandelt), default=None, key=lambda t: t or datetime.min)
            start = _zeit(lauf)
            dauer = _plausibel((ende - start).total_seconds()) if ende and start else None
            seiten = sum(_seiten(z, seiten_je_name) or 0 for z in umgewandelt) or None
        ergebnis.append({
            "lauf": lauf, "art": art, "dateien": len(umgewandelt) if art in ("Umwandlung", "Text erneuert") else len(gruppe),
            "ok": stati["OK"] + stati["TEXT_ERNEUERT"], "pruefen": stati["PRÜFEN"], "fehler": stati["FEHLER"],
            "nachgebessert": stati["NACHGEBESSERT"], "dauer_s": dauer, "seiten": seiten,
            "seiten_pro_min": round(seiten * 60 / dauer, 1) if dauer and seiten else None})
    return ergebnis


def quellen_kategorie(quelle: str | None) -> str:
    """Herkunft einer Angabe, zusammengefasst zu wenigen Kategorien (fuer das gestapelte Diagramm)."""
    q = (quelle or "").strip()
    if not q:
        return "fehlt"
    if "Crossref" in q:
        return "Crossref"
    if "Norm" in q or q.startswith("Ausgabe "):
        return "Norm"
    if "im Text" in q or "Copyright" in q:
        return "Text"
    if q == "PDF-Metadaten":
        return "PDF-Metadaten"
    if q.startswith("manuell"):
        return "von Hand"
    return "Dokument"            # Eigenschaften der Datei selbst (EPUB, DOCX, HTML, Erstellungsdatum ...)


def _zahl(text, muster=ZAHL_VORN) -> int:
    m = muster.search(str(text)) if text else None
    return int(m.group(1)) if m else 0


def buchkennzahlen(kopf: dict, text: str, aktuelle_textquelle: str | None = None) -> dict:
    """Kennzahlen einer .md aus Kopfblock und Text (ohne Kopfblock)."""
    try:
        seiten = int(kopf.get("seiten") or 0)
    except (TypeError, ValueError):
        seiten = 0
    zitierquelle = str(kopf.get("zitierdaten_quelle") or "")
    original = str(kopf.get("originaldatei") or "")
    return {
        "seiten": seiten,
        "gedruckt": len(GEDRUCKT.findall(text)),
        "nur_pdf": len(NUR_PDF.findall(text)),
        "fragezeichen": text.count("�"),
        "unsicher": text.count(UNSICHER),
        "formelzeichen": _zahl(kopf.get("formelreparatur"), ERSETZT),
        "hochtief": _zahl(kopf.get("formelsatz"), HOCHTIEF),
        "formelteile": _zahl(kopf.get("formelsatz"), FORMELTEILE),
        "tabellen": _zahl(kopf.get("tabellen")),
        "ueberschriften": _zahl(kopf.get("lesezeichen")),
        "ueberschriften_im_text": _zahl(kopf.get("lesezeichen"), IM_TEXT),
        "spaltenseiten": _zahl(kopf.get("spalten")),
        "formelzeilen": sum(1 for zeile in text.split("\n") if FORMELZEILE.search(zeile)),
        "tabellentitel": len(set(TABELLENTITEL.findall(text))),
        # welche Verfahren gelaufen sind ("PDFium + Formelreparatur + Lesezeichen ..."): aeltere .md haben weniger
        "verfahren": [t.strip() for t in str(kopf.get("textquelle") or "").split("+")[1:]],
        "quellen": {f: quellen_kategorie(kopf.get(f"{f}_quelle")) if kopf.get(f) else "fehlt" for f in FELDER},
        "ieee": bool(kopf.get("quellenangabe")) and (bool(kopf.get("norm"))
                                                     or bool(zitierquelle) and not zitierquelle.startswith("nur ")),
        "norm": bool(kopf.get("norm")),
        "pruefen": kopf.get("pruefen") or None,
        "format": original.rsplit(".", 1)[1].upper() if "." in original else "?",
        "aktuell": aktuelle_textquelle is not None and kopf.get("textquelle") == aktuelle_textquelle,
    }


def herkunft(buecher: list[dict]) -> dict[str, dict[str, int]]:
    """Je Feld (titel, autor, jahr): Anzahl je Herkunftskategorie, in fester Reihenfolge (KATEGORIEN)."""
    ergebnis = {}
    for feld in FELDER:
        zaehler = Counter(b["quellen"][feld] for b in buecher)
        ergebnis[feld] = {k: zaehler[k] for k in KATEGORIEN if zaehler[k]}
    return ergebnis


def pruefgruende(buecher: list[dict], n: int = 6) -> list[tuple[str, int]]:
    zaehler = Counter(g.strip() for b in buecher if b.get("pruefen") for g in str(b["pruefen"]).split(";") if g.strip())
    return zaehler.most_common(n)


def ieee_anteil(buecher: list[dict]) -> tuple[int, int]:
    """(Bücher mit vollständiger IEEE-Quellenangabe, alle Bücher)."""
    return sum(1 for b in buecher if b["ieee"]), len(buecher)


SUMMEN = ("seiten", "formelzeichen", "unsicher", "fragezeichen", "tabellen", "ueberschriften", "spaltenseiten",
          "hochtief", "formelteile", "gedruckt", "nur_pdf")


def _anteil(gedruckt: int, nur_pdf: int) -> float | None:
    return gedruckt / (gedruckt + nur_pdf) if gedruckt + nur_pdf else None


def textsummen(buecher: list[dict]) -> dict:
    summen = {k: sum(b.get(k, 0) for b in buecher) for k in SUMMEN}
    summen.update(buecher=len(buecher), aktuell=sum(1 for b in buecher if b.get("aktuell")),
                  gedruckt_anteil=_anteil(summen["gedruckt"], summen["nur_pdf"]),
                  gedruckt_erfasst=sum(1 for b in buecher if b.get("gedruckt", 0) + b.get("nur_pdf", 0)))
    return summen


# Text-Qualitaet: je Punkt der erreichte Wert und die hoechstmoegliche Anzahl (Nenner). Gezaehlt werden nur Buecher, bei
# denen das Verfahren gelaufen ist (textquelle), sonst stuenden aeltere .md mit 0 im Zaehler, aber vollem Nenner da.
# (Titel, Verfahren oder None, Zaehler, Nenner als Funktion eines Buchs, Bezeichnung des Nenners)
QUALITAET = (
    ("Formelzeichen repariert", "Formelreparatur", lambda b: b["formelzeichen"],
     lambda b: b["formelzeichen"] + b["fragezeichen"], "unlesbaren Zeichen"),
    ("Verbliebene �", "Formelreparatur", lambda b: b["fragezeichen"],
     lambda b: b["formelzeichen"] + b["fragezeichen"], "unlesbaren Zeichen"),
    ("Formeln unsicher markiert", "Formelsatz", lambda b: b["unsicher"], lambda b: b["formelzeilen"], "Formelzeilen"),
    ("Tabellen als Markdown", "Tabellen", lambda b: b["tabellen"], lambda b: b["tabellentitel"],
     "Tabellentiteln im Text"),
    ("Überschriften direkt im Text", "Lesezeichen", lambda b: b["ueberschriften_im_text"],
     lambda b: b["ueberschriften"], "Überschriften aus Lesezeichen"),
    ("Spaltenseiten umsortiert", "Spaltenreihenfolge", lambda b: b["spaltenseiten"], lambda b: b["seiten"], "Seiten"),
    ("Seiten mit gedruckter Zahl", "Seitenzahlen", lambda b: b["gedruckt"], lambda b: b["gedruckt"] + b["nur_pdf"],
     "Seiten mit Marker"),
    ("Bücher mit aktuellem Verfahren", None, lambda b: int(bool(b.get("aktuell"))), lambda b: 1, "Büchern"),
)


def textqualitaet(buecher: list[dict]) -> list[dict]:
    """Je Punkt: Wert, Hoechstzahl, Bezeichnung des Nenners und aus wie vielen Buechern gezaehlt wurde."""
    punkte = []
    for titel, verfahren, zaehler, nenner, bezeichnung in QUALITAET:
        auswahl = [b for b in buecher if verfahren is None or verfahren in b.get("verfahren", [])]
        punkte.append({"titel": titel, "wert": sum(zaehler(b) for b in auswahl), "max": sum(nenner(b) for b in auswahl),
                       "nenner": bezeichnung, "buecher": len(auswahl), "alle": len(buecher)})
    return punkte


def offene_stellen(buecher: list[dict], n: int = 10) -> list[dict]:
    """Buecher mit den meisten offenen Stellen (verbliebene "�", unsichere Formeln, Seiten ohne gedruckte Zahl), nach
    Stellen je 100 Seiten sortiert, damit dicke Buecher nicht automatisch oben stehen."""
    liste = []
    for b in buecher:
        offen = b["fragezeichen"] + b["unsicher"] + b["nur_pdf"]
        if offen:
            liste.append({"name": b["name"], "seiten": b["seiten"], "fragezeichen": b["fragezeichen"],
                          "unsicher": b["unsicher"], "nur_pdf": b["nur_pdf"], "offen": offen,
                          "je_100": round(offen * 100 / max(b["seiten"], 1), 1)})
    liste.sort(key=lambda b: (-b["je_100"], -b["offen"], b["name"]))
    return liste[:n]


def bestand(eingang: list[dict], pruefen: list[dict], fertig: list[dict]) -> dict:
    """Dateien je Bereich und je Format (aus den Listen der Ablage, siehe ablage.py)."""
    formate = Counter(e["format"] for liste in (eingang, pruefen, fertig) for e in liste)
    return {"bereiche": {"Eingang": len(eingang), "Prüfen": len(pruefen), "Fertig": len(fertig)},
            "formate": dict(formate.most_common())}


def uebersicht(buecher_fertig: list[dict], anzahl_pruefen: int, bereit: int) -> dict:
    """Die vier Kennzahlen der Hauptseite."""
    gedruckt = sum(b["gedruckt"] for b in buecher_fertig)
    nur_pdf = sum(b["nur_pdf"] for b in buecher_fertig)
    return {"fertig": len(buecher_fertig), "pruefen": anzahl_pruefen, "bereit": bereit,
            "seiten": sum(b["seiten"] for b in buecher_fertig), "gedruckt_anteil": _anteil(gedruckt, nur_pdf),
            # nur Buecher mit den neuen Markern zaehlen (aeltere haben <!-- Seite N --> ohne gedruckte Zahl)
            "gedruckt_erfasst": sum(1 for b in buecher_fertig if b["gedruckt"] + b["nur_pdf"])}
