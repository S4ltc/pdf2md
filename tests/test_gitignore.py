"""Aus dem Quellcode gestartet ist der Projektordner die Ablage (plattform.ablage_basis). Alles, was das Programm dort
anlegt, muss in .gitignore stehen, sonst nimmt ein `git add -A` Buchtitel, Pfade und Protokolle mit ins oeffentliche
Repo. Frueher fehlten Literatur.bib („Literaturliste exportieren“) und .pdf2md.lock (Sperre unter macOS/Linux).
Die Namen kommen aus dem Code, damit ein umbenannter Ordner oder eine neue Datei hier auffaellt."""
import shutil
import subprocess
from pathlib import Path

import pytest

import einstellungen
import pdf2md
import plattform
import ui_app

WURZEL = Path(__file__).resolve().parent.parent

ABLAGE = [
    f"{pdf2md.EINGANG.name}/Beispiel.pdf",
    f"{pdf2md.FERTIG.name}/Beispielelemente - Erika Muster - 2020.md",
    f"{pdf2md.PRUEFEN.name}/Beispiel.md",
    f"{pdf2md.SICHERUNG.name}/Beispielelemente - Erika Muster - 2020.md",
    pdf2md.PROTOKOLL.name,
    pdf2md.LITERATURLISTE,
    einstellungen.DATEINAME,
    einstellungen.DATEINAME + ".tmp",       # Hilfsdatei von einstellungen.speichern
    ui_app.FEHLERDATEI,
    plattform.SPERRDATEI,
]

# Gegenprobe: Programmteile duerfen nicht ignoriert sein (auch nicht die Ausnahmen unter .claude/)
PROGRAMM = ["pdf2md.py", "README.md", "docs/LIESMICH.txt", ".claude/hooks/schutz.py",
            ".claude/skills/veroeffentlichen/SKILL.md"]


def ignoriert(pfad: str) -> bool:
    """git check-ignore --no-index prueft nur die Muster, auch fuer Dateien, die es (noch) nicht gibt."""
    r = subprocess.run(["git", "-C", str(WURZEL), "check-ignore", "-q", "--no-index", pfad],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    return r.returncode == 0


@pytest.fixture(scope="module", autouse=True)
def git_vorhanden():
    if shutil.which("git") is None:
        pytest.skip("git fehlt")
    r = subprocess.run(["git", "-C", str(WURZEL), "rev-parse", "--is-inside-work-tree"], capture_output=True,
                       text=True)
    if r.stdout.strip() != "true":
        pytest.skip("kein Git-Arbeitsverzeichnis (z.B. ausgepackter Quellstand)")


@pytest.mark.parametrize("pfad", ABLAGE)
def test_ablagedateien_sind_ignoriert(pfad):
    assert ignoriert(pfad), f"{pfad} fehlt in .gitignore"


@pytest.mark.parametrize("pfad", PROGRAMM)
def test_programmteile_sind_nicht_ignoriert(pfad):
    assert (WURZEL / pfad).exists()
    assert not ignoriert(pfad)
