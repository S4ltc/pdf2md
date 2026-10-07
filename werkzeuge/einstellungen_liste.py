"""Schreibt docs/einstellungen.md: alle Einstellungen je Gruppe mit Standard, Bereich und Tooltip (aus einstellungen.py).

Aufruf:  python werkzeuge/einstellungen_liste.py"""
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import einstellungen as E  # noqa: E402


def bereich(e: E.Einstellung) -> str:
    if e.typ == "bool":
        return "an/aus"
    if e.typ == "wahl":
        return " / ".join(a for _, a in e.optionen)
    von, bis = (E.anzeige(e, x).replace(f" {e.einheit}", "") if e.einheit else E.anzeige(e, x) for x in e.bereich)
    schritt = f"{e.schritt:g}".replace(".", ",")
    return f"{von} bis {bis} {e.einheit} (Schritt {schritt})".replace("  ", " ")


def main() -> None:
    zeilen = ["# Einstellungen", "",
              "Erzeugt aus `einstellungen.py` mit `python werkzeuge/einstellungen_liste.py`. Im Fenster stehen die Texte "
              "als Tooltip, gespeichert werden Abweichungen in `Einstellungen.json` neben dem Programm.", "",
              f"{len(E.EINSTELLUNGEN)} Einstellungen, davon "
              f"{sum(e.stufe == 'normal' for e in E.EINSTELLUNGEN)} normal und "
              f"{sum(e.stufe == 'experte' for e in E.EINSTELLUNGEN)} für Experten (an 58 Büchern gemessen).", ""]
    for stufe, ueberschrift in (("normal", "Normal"), ("experte", "Experte")):
        zeilen += [f"## {ueberschrift}", ""]
        for gruppe in E.GRUPPEN:
            liste = [e for e in E.EINSTELLUNGEN if e.stufe == stufe and e.gruppe == gruppe]
            if not liste:
                continue
            zeilen += [f"### {gruppe}", "", "| Einstellung | Schlüssel | Standard | Bereich | Tooltip |",
                       "|---|---|---|---|---|"]
            for e in liste:
                standard, umfang = E.anzeige(e, e.standard), bereich(e)
                if e.schluessel == "pdf2md.MAX_PROZESSE":          # haengt vom Rechner ab, nicht dessen Zahl nennen
                    standard, umfang = "Anzahl der Prozessorkerne", "1 bis doppelte Kernzahl (Schritt 1)"
                zeilen.append(f"| {e.titel} | `{e.schluessel}` | {standard} | {umfang} | "
                              f"{e.hilfe.replace('|', '/')} |")
            zeilen.append("")
    (WURZEL / "docs" / "einstellungen.md").write_text("\n".join(zeilen), encoding="utf-8", newline="\n")
    print(f"docs/einstellungen.md: {len(E.EINSTELLUNGEN)} Einstellungen")


if __name__ == "__main__":
    main()
