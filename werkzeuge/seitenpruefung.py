"""Prueft die gedruckten Seitenzahlen (seitenzahlen.py) unabhaengig: Das Inhaltsverzeichnis nennt zu jedem Kapitel die
gedruckte Seite ("12.3 Getriebe ..... 197"), das Lesezeichen desselben Kapitels zeigt auf die PDF-Seite. Stimmt die
zugeordnete Zahl dieser PDF-Seite mit dem Inhaltsverzeichnis ueberein, ist die Zuordnung dort richtig.
Nur lesend.  Aufruf: python werkzeuge/seitenpruefung.py <ordner mit PDFs> [...]"""
import concurrent.futures as cf
import os
import re
import sys
from pathlib import Path

CODE_DIR = os.environ.get("CODE_DIR", str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, CODE_DIR)

INHALT_ZEILE = re.compile(r"(.{4,}?)(?:\s*(?:\.\s*){2,}|\s*…\s*|\s+)(\d{1,4}|[ivxlcdm]{1,6})\s*$", re.IGNORECASE)
MAX_GROESSE = 150_000_000


def pruefen(pfad: str) -> dict:
    import pypdfium2 as pdfium
    import pdf2md
    import seitenzahlen
    p = Path(pfad)
    dok = pdfium.PdfDocument(pfad)
    try:
        labels = seitenzahlen.label_lesen(dok)
        roh = []
        for i in range(len(dok)):
            seite = dok[i]
            tp = seite.get_textpage()
            roh.append(tp.get_text_range())
            tp.close()
            seite.close()
    finally:
        dok.close()
    zeilen = [[z.rstrip() for z in (pdf2md.LIZENZVERMERK.sub("", z) for z in s.replace("\r\n", "\n").split("\n"))
               if z.strip()] for s in roh]
    gedruckt, quelle = seitenzahlen.zuordnen(labels, [seitenzahlen.kandidaten(z) for z in zeilen])
    # Inhaltsverzeichnis: erste 15 % der Seiten (hoechstens 40)
    inhalt, mehrfach = {}, set()
    for z in (z for s in zeilen[:min(40, max(6, len(zeilen) * 15 // 100))] for z in s):
        m = INHALT_ZEILE.fullmatch(z.strip())
        if m:
            schluessel = pdf2md._norm_titel(m.group(1))
            if schluessel in inhalt:
                mehrfach.add(schluessel)            # "Literatur" in jedem Kapitel: nicht eindeutig
            inhalt.setdefault(schluessel, m.group(2).lower())
    gleich, anders, beispiele = 0, 0, []
    lesezeichen = pdf2md.lesezeichen_lesen(p)
    zaehler = {}
    for eintraege in lesezeichen.values():
        for _, titel in eintraege:
            zaehler[pdf2md._norm_titel(titel)] = zaehler.get(pdf2md._norm_titel(titel), 0) + 1
    mehrfach |= {t for t, n in zaehler.items() if n > 1}
    for seite, eintraege in lesezeichen.items():
        for _, titel in eintraege:
            if pdf2md._norm_titel(titel) in mehrfach:
                continue
            soll = inhalt.get(pdf2md._norm_titel(titel))
            if soll is None or seite < len(zeilen) * 10 // 100:      # Eintraege im Vorspann selbst zaehlen nicht
                continue
            ist = (gedruckt[seite] or "").lower()
            if ist == soll:
                gleich += 1
            else:
                anders += 1
                if len(beispiele) < 3:
                    beispiele.append(f"{titel[:30]!r}: Inhalt {soll}, zugeordnet {ist or '-'} (PDF {seite + 1})")
    return {"name": p.name, "seiten": len(zeilen), "mit_zahl": sum(1 for g in gedruckt if g), "quelle": quelle,
            "gleich": gleich, "anders": anders, "beispiele": beispiele}


def main():
    dateien = [f for ordner in sys.argv[1:] for f in sorted(Path(ordner).glob("*.pdf"))
               if f.stat().st_size <= MAX_GROESSE]
    summe = {"seiten": 0, "mit_zahl": 0, "gleich": 0, "anders": 0}
    with cf.ProcessPoolExecutor(max_workers=min(10, os.cpu_count() or 4)) as pool:
        for e in pool.map(pruefen, map(str, dateien)):
            for k in summe:
                summe[k] += e[k]
            flag = "!!" if e["anders"] else "  "
            print(f"{flag} {e['name'][:50]:50} {e['mit_zahl']:5}/{e['seiten']:<5} {e['quelle'][:26]:26} "
                  f"Inhalt: {e['gleich']} gleich, {e['anders']} anders", flush=True)
            for b in e["beispiele"]:
                print(f"      {b}")
    print(f"GESAMT Seiten mit Zahl {summe['mit_zahl']}/{summe['seiten']}, Inhaltsverzeichnis: {summe['gleich']} gleich, "
          f"{summe['anders']} anders")


if __name__ == "__main__":
    main()
