"""werkzeuge/normen_lauf.py und buecher_lauf.py: ohne Ordner mit den PDFs brechen beide mit einem Hinweis ab.
Frueher nahm buecher_lauf.py ohne BUECHER still dist/Fertig; dort liegen aber Nutzerdaten (inzwischen nur Normen),
und ein solcher Lauf sah wie ein gueltiger Buecherlauf aus."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

WERKZEUGE = Path(__file__).resolve().parent.parent / "werkzeuge"


def starten(skript, variable, wert, tmp_path):
    umgebung = {k: v for k, v in os.environ.items() if k not in ("NORMEN", "BUECHER", "CODE_DIR")}
    if wert is not None:
        umgebung[variable] = wert
    umgebung["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, str(WERKZEUGE / skript), str(tmp_path / "ausgabe")], cwd=tmp_path,
                          env=umgebung, capture_output=True, text=True, encoding="utf-8", timeout=120)


@pytest.mark.parametrize("skript, variable", [("normen_lauf.py", "NORMEN"), ("buecher_lauf.py", "BUECHER")])
@pytest.mark.parametrize("wert", [None, "", "fehlt"])
def test_ohne_pdf_ordner_abbruch_mit_hinweis(skript, variable, wert, tmp_path):
    r = starten(skript, variable, wert if wert != "fehlt" else str(tmp_path / "gibt-es-nicht"), tmp_path)
    assert r.returncode == 1
    assert variable in r.stderr
    assert not (tmp_path / "ausgabe").exists()
