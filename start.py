"""Einstieg des gebauten Programms (pdf2md.exe, macOS-App, Linux-Ordner; werkzeuge/bauen.py). Aus dem Quellcode
startet weiter ui_app.py.

ui_app laedt schon beim Import pdf2md und damit markitdown, magika/onnxruntime, pypdfium2 usw., also bevor das try in
ui_app.main() greift. Scheiterte das (typisch fuer ein Paket auf einem anderen System: eine Systembibliothek fehlt
oder passt nicht), verschwand die Fenster-Anwendung ohne Konsole stumm. Hier landet der Traceback in
pdf2md-fehler.txt (in der Ablage, sonst im Temp-Ordner), und eine Meldung nennt die Datei. Deshalb nur
Standardbibliothek und plattform.py (importiert selbst nur die Standardbibliothek).

multiprocessing.freeze_support() kommt zuerst: die Unterprozesse (spawn) starten die gebaute App erneut und muessen
hier enden, bevor ui_app und alle grossen Pakete geladen sind."""
import multiprocessing
import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import plattform

FEHLERDATEI = "pdf2md-fehler.txt"      # wie ui_app.FEHLERDATEI (dort fuer Fehler nach dem Import)


def _ui_app():
    import ui_app                      # ausdruecklich: so findet PyInstaller ui_app und alles, was es braucht
    return ui_app


def starten(laden=_ui_app) -> int:
    """Startet das Fenster; Rueckgabe ist der Exit-Code. laden() liefert das Modul ui_app (Tests setzen eine Funktion
    ein, die scheitert)."""
    multiprocessing.freeze_support()
    try:
        modul = laden()
    except Exception as e:
        startfehler(e, traceback.format_exc())
        return 1
    return modul.main()


def startfehler(fehler: Exception, text: str) -> None:
    """Meldung zu einem Fehler beim Laden des Programms, mit dem Pfad der Datei, die den Traceback enthaelt. Im
    Start-Test beim Bauen (PDF2MD_STARTTEST) nur auf die Konsole, wie ui_app.startfehler_melden: ein Dialog wartete
    dort bis zum Zeitlimit."""
    datei = fehler_festhalten(text)
    meldung = f"pdf2md lässt sich nicht starten:\n{type(fehler).__name__}: {str(fehler)[:500]}"
    if isinstance(fehler, ImportError):
        meldung += "\n\nEin Teil des Programms fehlt oder passt nicht zu diesem System."
    if datei is not None:
        meldung += f"\n\nEinzelheiten stehen in:\n{datei}"
    if os.environ.get("PDF2MD_STARTTEST"):
        print(meldung, file=sys.stderr)
    else:
        plattform.meldung(meldung)


def fehler_festhalten(text: str) -> Path | None:
    """Schreibt text nach FEHLERDATEI in der Ablage; geht das nicht, in den Temp-Ordner. Rueckgabe: die Datei, None,
    wenn beides scheitert."""
    inhalt = f"pdf2md {_version()} ({plattform.SYSTEM}), {datetime.now():%Y-%m-%d %H:%M:%S}\n\n{text}"
    for ordner in (_ablage, lambda: Path(tempfile.gettempdir())):
        try:
            ziel = ordner()
            ziel.mkdir(parents=True, exist_ok=True)
            datei = ziel / FEHLERDATEI
            datei.write_text(inhalt, encoding="utf-8")
            return datei
        except Exception:
            continue
    return None


def _ablage() -> Path:
    """Wie ui_app.ablage_ordner(), aber ohne pdf2md: PDF2MD_ABLAGE, sonst plattform.ablage_basis (pdf2md.BASE_DIR)."""
    return Path(os.environ.get("PDF2MD_ABLAGE") or plattform.ablage_basis(Path(__file__)))


def _version() -> str:
    try:
        from aktualisierung import VERSION     # nur Standardbibliothek
        return VERSION
    except Exception:
        return "(Version unbekannt)"


if __name__ == "__main__":
    sys.exit(starten())
