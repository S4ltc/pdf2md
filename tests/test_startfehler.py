"""Start und Systemgrenzen ausserhalb von Windows: ui_app.main() meldet verweigerten Zugriff auf die Ablage (macOS:
Datenschutz) und unbehandelte Ausnahmen mit einer Datei, statt still zu verschwinden; pdf2md.fehlertext() erklaert
PermissionError je System; Unterprozesse starten auf allen Systemen mit spawn; Links und Dateien oeffnen mit
verstaendlichem Fehler. Alles ohne Fenster: einzelinstanz, meldung und webview sind nachgebildet."""
import concurrent.futures
import sys
import tempfile
from types import SimpleNamespace

import pytest

import aktualisierung
import pdf2md
import plattform
import ui_app


@pytest.fixture
def start(monkeypatch, tmp_path):
    """main() ohne Fenster: Ablage in tmp_path, kein Start-Test, vorbereiten() ohne Wirkung, meldung() sammelt."""
    monkeypatch.setenv("PDF2MD_ABLAGE", str(tmp_path / "ablage"))
    monkeypatch.delenv("PDF2MD_STARTTEST", raising=False)
    monkeypatch.setattr(plattform, "vorbereiten", lambda: None)
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace())     # das Fenster darf nie aufgehen
    meldungen = []
    monkeypatch.setattr(ui_app, "meldung", meldungen.append)
    return SimpleNamespace(ablage=tmp_path / "ablage", meldungen=meldungen)


def wirft(fehler):
    def ersatz(*args, **kwargs):
        raise fehler
    return ersatz


# ---------------------------------------------------------------- ui_app.main()
def test_verweigerter_zugriff_auf_die_ablage_wird_gemeldet(start, monkeypatch):
    """macOS: Hat der Nutzer den Zugriff auf Dokumente abgelehnt, scheitert die Sperrdatei mit PermissionError; die App
    verschwand bisher ohne jede Meldung."""
    monkeypatch.setattr(ui_app, "einzelinstanz", wirft(PermissionError(1, "Operation not permitted")))
    monkeypatch.setattr(plattform, "SYSTEM", "darwin")
    assert ui_app.main() == 1
    (text,) = start.meldungen
    assert str(start.ablage) in text and "Operation not permitted" in text
    assert "Systemeinstellungen unter Datenschutz & Sicherheit > Dateien und Ordner" in text
    assert not (start.ablage / ui_app.FEHLERDATEI).exists()          # erwarteter Fall, kein Programmfehler


def test_verweigerter_zugriff_unter_linux(start, monkeypatch):
    monkeypatch.setattr(ui_app, "einzelinstanz", wirft(PermissionError(13, "Permission denied")))
    monkeypatch.setattr(plattform, "SYSTEM", "linux")
    assert ui_app.main() == 1
    assert "Lese- und Schreibrechte prüfen, dann pdf2md neu starten" in start.meldungen[0]


def test_laeuft_schon(start, monkeypatch):
    monkeypatch.setattr(ui_app, "einzelinstanz", lambda basis: False)
    assert ui_app.main() == 1
    assert start.meldungen == [f"pdf2md läuft für diesen Ordner schon:\n{start.ablage}"]


def test_unbehandelte_ausnahme_landet_in_einer_datei(start, monkeypatch):
    monkeypatch.setattr(ui_app, "einzelinstanz", wirft(RuntimeError("kaputt beim Start")))
    assert ui_app.main() == 1
    datei = start.ablage / ui_app.FEHLERDATEI
    inhalt = datei.read_text(encoding="utf-8")
    assert "Traceback" in inhalt and "RuntimeError: kaputt beim Start" in inhalt
    assert inhalt.startswith(f"pdf2md {aktualisierung.VERSION} ")
    (text,) = start.meldungen
    assert "RuntimeError: kaputt beim Start" in text and str(datei) in text


def test_ohne_zugriff_auf_die_ablage_in_den_temp_ordner(start, monkeypatch, tmp_path):
    start.ablage.write_text("eine Datei statt des Ordners", encoding="utf-8")    # Ablage laesst sich nicht anlegen
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temp))
    monkeypatch.setattr(ui_app, "einzelinstanz", wirft(RuntimeError("kaputt")))
    assert ui_app.main() == 1
    assert (temp / ui_app.FEHLERDATEI).is_file()
    assert str(temp / ui_app.FEHLERDATEI) in start.meldungen[0]


def test_berechtigung_fehlt_spaeter_mit_hinweis(start, monkeypatch):
    """PermissionError nach der Sperrdatei (z.B. beim Lesen der Einstellungen) geht durch main() und bekommt denselben
    Hinweis wie der Zugriff auf die Ablage."""
    monkeypatch.setattr(ui_app, "einzelinstanz", lambda basis: True)
    monkeypatch.setattr(ui_app, "Api", wirft(PermissionError(1, "Operation not permitted")))
    monkeypatch.setattr(plattform, "SYSTEM", "darwin")
    assert ui_app.main() == 1
    (text,) = start.meldungen
    assert "PermissionError" in text and "Datenschutz & Sicherheit" in text
    assert str(start.ablage / ui_app.FEHLERDATEI) in text


def test_im_start_test_kein_dialog(start, monkeypatch, capsys, tmp_path):
    """Beim Bauen (PDF2MD_STARTTEST) wartete ein Dialog bis zum Zeitlimit; der Text geht auf die Konsole."""
    monkeypatch.setenv("PDF2MD_STARTTEST", str(tmp_path / "ergebnis.json"))
    monkeypatch.setattr(ui_app, "einzelinstanz", lambda basis: False)
    assert ui_app.main() == 1
    assert start.meldungen == [] and "läuft für diesen Ordner schon" in capsys.readouterr().err


# ---------------------------------------------------------------- pdf2md.fehlertext()
@pytest.mark.parametrize("system, erwartet", [("win32", "geöffnet"), ("darwin", "Datenschutz & Sicherheit"),
                                              ("linux", "Lese- und Schreibrechte prüfen")])
def test_permissionerror_je_system(monkeypatch, tmp_path, system, erwartet):
    """Unter macOS/Linux sperren Programme keine geoeffneten Dateien: "schließen und erneut starten" waere dort
    falsch, gemeint ist eine fehlende Berechtigung."""
    monkeypatch.setattr(plattform, "SYSTEM", system)
    text = pdf2md.fehlertext(PermissionError(13, "Permission denied"), tmp_path / "Buch.pdf")
    assert erwartet in text
    assert ("gesperrt" in text) == (system == "win32")
    assert text.startswith("keine Berechtigung") == (system != "win32")


def test_windows_sperre_bleibt_sperre(monkeypatch, tmp_path):
    monkeypatch.setattr(plattform, "SYSTEM", "linux")
    text = pdf2md.fehlertext(OSError("[WinError 32] Der Prozess kann nicht auf die Datei zugreifen"),
                             tmp_path / "a.pdf")
    assert "gesperrt" in text


# ---------------------------------------------------------------- Unterprozesse
@pytest.fixture
def pool(monkeypatch):
    """Nachgebildeter ProcessPoolExecutor: rechnet im eigenen Prozess und merkt sich den Startkontext."""
    kontexte = []

    class Pool:
        def __init__(self, max_workers=None, mp_context=None, **optionen):
            kontexte.append(mp_context)

        def __enter__(self):
            return self

        def __exit__(self, *fehler):
            return False

        def map(self, funktion, *folgen, chunksize=1):
            return map(funktion, *folgen)

        def submit(self, funktion, *argumente):
            aufgabe = concurrent.futures.Future()
            aufgabe.set_result(funktion(*argumente))
            return aufgabe
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", Pool)
    return kontexte


def test_kennzahlen_in_unterprozessen_mit_spawn(pool, monkeypatch, tmp_path):
    """Linux naehme sonst fork: ein Fork aus dem Fenster-Prozess mit Qt-/Chromium-Threads kann haengen bleiben."""
    (tmp_path / "Fertig").mkdir()
    for i in range(3):
        (tmp_path / "Fertig" / f"Buch {i}.md").write_text(
            pdf2md.kopf_schreiben({"titel": f"Beispielbuch {i}", "seiten": 5}) + "Text", encoding="utf-8")
    monkeypatch.setattr(ui_app, "PARALLEL_AB_BUECHERN", 1)
    api = ui_app.Api(tmp_path)
    api._parallel_rechnen()
    assert len(api._zwischenspeicher) == 3
    assert [k.get_start_method() for k in pool] == ["spawn"]


def test_markitdown_pakete_in_unterprozessen_mit_spawn(pool, monkeypatch, tmp_path):
    monkeypatch.setattr(pdf2md, "PARALLEL_AB_SEITEN", 10)
    monkeypatch.setattr(pdf2md, "SEITEN_PRO_PAKET", 5)
    monkeypatch.setattr(pdf2md, "_paket_umwandeln", lambda pfad, anfang, ende: f"Seiten {anfang}-{ende}")
    text = pdf2md._markitdown_umwandeln(tmp_path / "gross.pdf", 12, None)
    assert text == "Seiten 0-5\n\nSeiten 5-10\n\nSeiten 10-12"
    assert [k.get_start_method() for k in pool] == ["spawn"]


# ---------------------------------------------------------------- Oeffnen aus dem Fenster
def test_link_ueber_plattform(monkeypatch):
    geoeffnet = []
    monkeypatch.setattr(plattform, "adresse_oeffnen", geoeffnet.append)
    assert ui_app.link_oeffnen("https://example.org/") is True and geoeffnet == ["https://example.org/"]


def test_link_fehler_nur_auf_der_konsole(monkeypatch, capsys):
    """Wie bisher bei webbrowser: kein Fehler im Fenster, der Grund steht auf der Konsole."""
    monkeypatch.setattr(plattform, "adresse_oeffnen", wirft(OSError("xdg-open fehlt, Paket xdg-utils installieren")))
    assert ui_app.link_oeffnen("https://example.org/") is False
    assert "xdg-utils" in capsys.readouterr().err


def test_datei_oeffnen_zeigt_den_fehler_von_xdg_open(monkeypatch, tmp_path):
    """Frueher meldete das Fenster unter macOS/Linux immer "geöffnet"; jetzt kommt der Grund wie unter Windows."""
    monkeypatch.setattr(plattform.subprocess, "Popen", lambda befehl, **optionen: SimpleNamespace(
        wait=lambda timeout=None: 4))
    monkeypatch.setattr(plattform, "SYSTEM", "linux")
    (tmp_path / "Eingang").mkdir()
    (tmp_path / "Eingang" / "Buch.pdf").write_bytes(b"%PDF-1.4\n")
    api = ui_app.Api(tmp_path)
    assert api.datei_oeffnen("eingang", "Buch.pdf") == {"ok": False, "grund": (
        "Buch.pdf lässt sich nicht öffnen (kein Standardprogramm für diesen Dateityp eingerichtet, xdg-open meldet "
        "Fehler 4)")}
    assert api.ordner_oeffnen("fertig")["ok"] is False
