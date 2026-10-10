"""Oberflaeche je Betriebssystem: System fuer Tastenkuerzel und Texte (stand), Filter des Hinzufuegen-Dialogs,
systemneutrale Hinweise und der Schriftstapel. Windows soll unveraendert aussehen; macOS und Linux laufen hier mit
umgesetzter Systemkennung (plattform.SYSTEM), das Fenster selbst nur auf GitHub bzw. von Hand."""
import fnmatch
import json
import re

import pytest

import pdf2md
import plattform
import ui_app

WEB = ui_app.web_ordner()
WINDOWS_FILTER = ("Unterstützte Dateien (*.pdf;*.docx;*.pptx;*.xlsx;*.epub;*.html;*.htm)", "Alle Dateien (*.*)")


@pytest.fixture
def api(tmp_path):
    (tmp_path / "Eingang").mkdir()
    return ui_app.Api(tmp_path)


@pytest.mark.parametrize("system", ["win32", "darwin", "linux"])
def test_stand_nennt_das_system(api, monkeypatch, system):
    """Die Oberflaeche waehlt danach die Kuerzeltaste (Mac: Cmd) und den Namen des Dateimanagers."""
    monkeypatch.setattr(plattform, "SYSTEM", system)
    stand = api.stand()
    assert stand["system"] == system
    json.dumps(stand)


def test_dateitypen_unter_windows_unveraendert(monkeypatch):
    """Windows zeigt die Muster in der Beschriftung des Filters: dort darf sich nichts aendern."""
    monkeypatch.setattr(plattform, "SYSTEM", "win32")
    assert ui_app.Api._dateitypen() == WINDOWS_FILTER


def _muster(filter_text: str) -> list[str]:
    from webview.util import parse_file_type                 # dasselbe Format, das pywebview selbst prueft
    return parse_file_type(filter_text)[1].split(";")


@pytest.mark.parametrize("system", ["linux", "darwin"])
def test_dateitypen_ausserhalb_windows_auch_gross(monkeypatch, system):
    """Der Dialog von Qt bzw. GTK unter Linux vergleicht die Muster mit Gross-/Kleinschreibung: "BERICHT.PDF" fehlte
    unter "Unterstützte Dateien". Nachgebildet mit fnmatchcase (wie GTK, Muster einzeln)."""
    pytest.importorskip("webview.util")
    monkeypatch.setattr(plattform, "SYSTEM", system)
    unterstuetzt, alle = ui_app.Api._dateitypen()
    assert alle == WINDOWS_FILTER[1]
    muster = _muster(unterstuetzt)
    for name in ("BERICHT.PDF", "bericht.pdf", "Folien.PPTX", "Seite.HTM", "Roman.EPUB"):
        assert any(fnmatch.fnmatchcase(name, m) for m in muster), name
    assert not any(fnmatch.fnmatchcase("Notiz.TXT", m) for m in muster)
    # vorher (Windows-Fassung) fehlte die grosse Endung
    assert not any(fnmatch.fnmatchcase("BERICHT.PDF", m) for m in _muster(WINDOWS_FILTER[0]))


def test_dateitypen_sind_die_unterstuetzten_formate():
    assert {"." + e for e in ui_app.ENDUNGEN} == pdf2md.UNTERSTUETZT


def test_hinzufuegen_dialog_bekommt_den_filter_des_systems(api, monkeypatch):
    pytest.importorskip("webview")
    gesehen = []

    class Fenster:
        def create_file_dialog(self, art, allow_multiple, file_types):
            gesehen.append((allow_multiple, file_types))
            return None                                      # Dialog abgebrochen

    monkeypatch.setattr(plattform, "SYSTEM", "linux")
    api._fenster_setzen(Fenster())
    assert api.hinzufuegen_dialog() == {"kopiert": [], "abgelehnt": []}
    assert gesehen == [(True, ui_app.Api._dateitypen())] and "*.PDF" in gesehen[0][1][0]


def test_hinweis_literaturliste_stimmt_auf_jedem_system(api, tmp_path):
    """Frueher "neben das Programm"; als App unter macOS/Linux liegt die Ablage aber in Dokumente/pdf2md. Die Datei
    liegt immer neben den Ordnern Eingang und Fertig."""
    fertig = tmp_path / "Fertig"
    fertig.mkdir()
    kopf = {"titel": "Beispielelemente", "autor": "Erika Muster", "jahr": "2020"}
    (fertig / "Beispielelemente - Erika Muster - 2020.md").write_text(pdf2md.kopf_schreiben(kopf) + "Text",
                                                                      encoding="utf-8")
    hinweis = api.werkzeug_vorschau("literatur")["hinweis"]
    assert "neben die Ordner Eingang und Fertig" in hinweis and "Programm" not in hinweis
    ziel = pdf2md.literatur_schreiben(pdf2md.literatur_plan())
    assert ziel.parent == pdf2md.EINGANG.parent == pdf2md.FERTIG.parent
    hilfe = (WEB / "index.html").read_text(encoding="utf-8")
    assert "neben das Programm" not in hilfe and "neben die Ordner Eingang und Fertig" in hilfe


def _variable(css: str, name: str) -> list[str]:
    wert = re.search(rf"{name}:\s*([^;]+);", css).group(1)
    return [s.strip() for s in wert.split(",")]


def test_schriftstapel_windows_zuerst_dann_systemschriften():
    """Segoe UI Variable fehlt auf macOS und Linux; Windows bleibt bei Segoe UI Variable bzw. Segoe UI."""
    css = (WEB / "stil.css").read_text(encoding="utf-8")
    assert _variable(css, "--schrift")[:3] == ['"Segoe UI Variable Text"', '"Segoe UI"', "var(--schrift-system)"]
    assert _variable(css, "--schrift-anzeige")[:3] == ['"Segoe UI Variable Display"', '"Segoe UI"',
                                                       "var(--schrift-system)"]
    system = _variable(css, "--schrift-system")
    assert {"-apple-system", "system-ui", '"Noto Sans"', '"DejaVu Sans"'} <= set(system) and system[-1] == "sans-serif"
    fest = _variable(css, "--schrift-fest")
    assert fest[:3] == ["ui-monospace", '"Cascadia Mono"', "Consolas"] and fest[-1] == "monospace"
    # Schriftnamen stehen nur in den Variablen, jede andere Stelle nutzt sie
    ausserhalb = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    ausserhalb = re.sub(r"--schrift[\w-]*:[^;]+;", "", ausserhalb)
    assert "Segoe" not in ausserhalb and "Consolas" not in ausserhalb


def test_html_enthaelt_die_windows_fassung_app_js_die_anderen():
    """index.html bleibt die Windows-Fassung (Strg, Explorer); app.js setzt Kuerzel und Dateimanager je System."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'aria-keyshortcuts="Control+O" title="Dateien nach Eingang kopieren (Strg+O)"' in html
    assert html.count("im Explorer öffnen") == 6                      # drei Ordnerknoepfe, je title und aria-label
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for teil in ('taste: "Meta", strg: "⌘"', '"im Finder"', '"im Dateimanager"', "e.metaKey && !e.ctrlKey",
                 "kuerzelTaste(e)", "systemSetzen(zustand.stand.system)"):
        assert teil in js, teil
    assert "e.ctrlKey && !e.altKey" not in js                           # Kuerzel nur noch ueber kuerzelTaste
