"""Prueft, ob Zitate aus der .md auf der angegebenen Seite stehen (nur lesend).

Fuer jede .md im Ausgabeordner (von normen_lauf.py / buecher_lauf.py) werden zufaellige Saetze gezogen und im Text der
PDF-Seite gesucht, die der Seitenmarker davor nennt (<!-- Seite S (PDF N) -->). Ein Satz mit Seitenwechsel (Marker
mitten im Satz) wird geteilt: der Teil davor muss auf Seite N-1, der Teil danach auf Seite N stehen.

Ergebnis je Datei: richtig (auf der genannten Seite), falsch (auf einer anderen Seite: Seitenangabe waere falsch),
nicht gefunden (Text weicht ab, z.B. Formel neu gesetzt). Verglichen werden nur Buchstaben und Ziffern.

Aufruf:  python werkzeuge/zitierpruefung.py <ausgabeordner> <ordner mit den PDFs> [saetze_je_datei]"""
import os
import random
import re
import sys
from pathlib import Path

CODE_DIR = os.environ.get("CODE_DIR", str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, CODE_DIR)

MARKER = re.compile(r"<!-- (?:Seite \S+ \(PDF (\d+)\)|PDF-Seite (\d+)|Seite (\d+)) -->")


def kern(text: str) -> str:
    """Nur Buchstaben und Ziffern ohne Akzente (LaTeX-Befehle, Zeichensetzung, Leerraum, Trennstriche und die im PDF
    oft kaputten Umlaute "Uǆ berprü fung" fallen weg, damit der Vergleich nur die Seite prueft)."""
    import unicodedata
    text = re.sub(r"\\[a-zA-Z]+", "", text).replace("ǆ", "").replace("Ƶ", "")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[\W_]+", "", text).lower()


def saetze(md: str) -> list[tuple[str, list[tuple[int, str]]]]:
    """Saetze mit ihren Stuecken je PDF-Seite: [(Satz, [(PDF-Seite, Text), ...])]."""
    ergebnis = []
    seite = 1
    stuecke: list[tuple[int, str]] = []
    puffer = ""
    for teil in re.split(r"(<!-- [^>]*-->)", md):
        m = MARKER.fullmatch(teil)
        if m:
            if puffer.strip():
                stuecke.append((seite, puffer))
            puffer = ""
            seite = int(next(g for g in m.groups() if g))
            continue
        for stueck in re.split(r"(?<=[.!?])\s+|\n\s*\n", teil):
            puffer += stueck
            if re.search(r"[.!?]\s*$", stueck) or "\n\n" in stueck:
                if puffer.strip():
                    stuecke.append((seite, puffer))
                satz = " ".join(s for _, s in stuecke)
                ergebnis.append((satz, stuecke))
                stuecke, puffer = [], ""
            else:
                puffer += " "
    return ergebnis


def tauglich(satz: str) -> bool:
    """Fliesstext-Satz: genug Woerter, keine Tabelle/Ueberschrift/Formel/Platzhalter."""
    return (len(satz.split()) >= 8 and "|" not in satz and "$" not in satz and "�" not in satz
            and not satz.lstrip().startswith("#") and len(kern(satz)) >= 40)


def pruefen(md_pfad: Path, pdf_pfad: Path, anzahl: int) -> dict:
    import pdf2md
    md = md_pfad.read_text(encoding="utf-8")
    kandidaten = [s for s in saetze(md) if tauglich(s[0])]
    random.seed(md_pfad.name)
    stichprobe = random.sample(kandidaten, min(anzahl, len(kandidaten)))
    # Bezug ist der Text jeder einzelnen PDF-Seite nach der Zeichenkorrektur (zeichen.py), aber vor dem Zusammenfuegen
    # der Seiten: so prueft der Vergleich die Seitenzuordnung, nicht die Zeichenkorrektur (Rohtext hat "Schweiflen")
    roh = pdf2md._pdfium_seiten(pdf_pfad)
    seitenkern: dict[int, str] = {}

    def text(nr: int) -> str:
        if nr not in seitenkern:
            if not 1 <= nr <= len(roh):
                return ""
            seitenkern[nr] = kern(pdf2md._seite_bereinigen(pdf2md.formelsatz.aufloesen(roh[nr - 1])[0]))
        return seitenkern[nr]

    richtig = falsch = fehlt = 0
    beispiele = []
    for satz, stuecke in stichprobe:
        ok = True
        anderswo = False
        for seite, stueck in stuecke:
            k = kern(stueck)
            if len(k) < 12:
                continue
            probe = k[:60]
            if probe in text(seite):
                continue
            ok = False
            if any(probe in text(n) for n in range(max(1, seite - 3), seite + 4) if n != seite):
                anderswo = True
        if ok:
            richtig += 1
        elif anderswo:
            falsch += 1
            if len(beispiele) < 3:
                beispiele.append(f"FALSCHE SEITE: {satz[:90]!r}")
        else:
            fehlt += 1
            if len(beispiele) < 3:
                beispiele.append(f"nicht gefunden: {satz[:90]!r}")
    return {"name": md_pfad.name, "richtig": richtig, "falsch": falsch, "fehlt": fehlt, "beispiele": beispiele}


def main():
    import concurrent.futures as cf
    ausgabe, pdfs = Path(sys.argv[1]), Path(sys.argv[2])
    anzahl = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    summe = {"richtig": 0, "falsch": 0, "fehlt": 0}
    paare = []
    for md in sorted(ausgabe.glob("*.md")):
        pdf = next((p for p in pdfs.glob(md.stem[:60] + "*.pdf") if p.stem[:80] == md.stem[:80]), None)
        if pdf is not None:
            paare.append((md, pdf))
    with cf.ProcessPoolExecutor(max_workers=min(10, os.cpu_count() or 4)) as pool:
        ergebnisse = list(pool.map(pruefen, [m for m, _ in paare], [p for _, p in paare], [anzahl] * len(paare)))
    for (md, _), e in zip(paare, ergebnisse):
        for k in summe:
            summe[k] += e[k]
        print(f"{e['richtig']:4} richtig {e['falsch']:3} falsche Seite {e['fehlt']:3} nicht gefunden | {md.name[:60]}")
        for b in e["beispiele"]:
            print(f"      {b}")
    gesamt = sum(summe.values()) or 1
    print(f"GESAMT {summe['richtig']} richtig ({100 * summe['richtig'] / gesamt:.1f} %), {summe['falsch']} falsche Seite, "
          f"{summe['fehlt']} nicht gefunden")


if __name__ == "__main__":
    main()
