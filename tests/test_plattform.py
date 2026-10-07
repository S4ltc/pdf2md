"""Was je Betriebssystem anders ist (plattform.py). Die Zweige fuer macOS und Linux laufen hier mit umgesetzter
Systemkennung und nachgebildeten Programmen; die Sperrdatei nur dort, wo es fcntl gibt (GitHub: macOS, Linux)."""
import subprocess
import sys

import pytest

import plattform as P


@pytest.fixture
def system(monkeypatch):
    def setzen(name):
        monkeypatch.setattr(P, "SYSTEM", name)
    return setzen


@pytest.mark.parametrize("name, erwartet", [("win32", "edgechromium"), ("darwin", "cocoa")])
def test_anzeige_engine(system, name, erwartet):
    system(name)
    assert P.gui() == erwartet


def test_anzeige_engine_linux_qt_sonst_gtk(system, monkeypatch):
    system("linux")
    monkeypatch.setattr(P, "_vorhanden", lambda modul: modul == "PySide6")
    assert P.gui() == "qt"
    monkeypatch.setattr(P, "_vorhanden", lambda modul: False)
    assert P.gui() == "gtk"


@pytest.mark.parametrize("name, befehl", [("darwin", "open"), ("linux", "xdg-open")])
def test_oeffnen_mac_und_linux(system, monkeypatch, tmp_path, name, befehl):
    aufrufe = []
    monkeypatch.setattr(P.subprocess, "Popen", lambda args, **kw: aufrufe.append(args))
    system(name)
    P.oeffnen(tmp_path)
    assert aufrufe == [[befehl, str(tmp_path)]]


def test_oeffnen_windows(system, monkeypatch, tmp_path):
    geoeffnet = []
    monkeypatch.setattr(P.os, "startfile", geoeffnet.append, raising=False)
    system("win32")
    P.oeffnen(tmp_path)
    assert geoeffnet == [str(tmp_path)]


@pytest.mark.parametrize("name, ausgabe, erwartet", [("darwin", "Dark\n", True), ("darwin", "", False),
                                                     ("linux", "'prefer-dark'\n", True), ("linux", "'default'\n", False)])
def test_dunkles_thema(system, monkeypatch, name, ausgabe, erwartet):
    monkeypatch.setattr(P.subprocess, "run",
                        lambda befehl, **kw: subprocess.CompletedProcess(befehl, 0, stdout=ausgabe, stderr=""))
    system(name)
    assert P.dunkel() is erwartet


def test_dunkles_thema_ohne_programm(system, monkeypatch):
    def fehlt(*a, **kw):
        raise FileNotFoundError("gsettings")
    monkeypatch.setattr(P.subprocess, "run", fehlt)
    system("linux")
    assert P.dunkel() is False


def test_meldung_ohne_windows_auf_stderr(system, capsys):
    system("linux")
    P.meldung("pdf2md läuft schon")
    assert "pdf2md läuft schon" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="Windows: benannter Mutex, siehe test_ui_app")
def test_ein_fenster_je_ordner_mit_sperrdatei(tmp_path):
    assert P.einzelinstanz(tmp_path / "eins")
    assert not P.einzelinstanz(tmp_path / "eins")
    assert P.einzelinstanz(tmp_path / "zwei")


class TestAblage:
    @pytest.fixture
    def app(self, monkeypatch, tmp_path):
        """Als gebautes Programm (PyInstaller setzt sys.frozen); Heimatordner im tmp_path."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "pdf2md.app" / "Contents" / "MacOS" / "pdf2md"))
        monkeypatch.setattr(P, "_heim", lambda: tmp_path)

        def ohne_xdg(*a, **kw):
            raise FileNotFoundError("xdg-user-dir")
        monkeypatch.setattr(P.subprocess, "run", ohne_xdg)
        return tmp_path

    def test_aus_dem_quellcode_neben_dem_skript(self, system, monkeypatch, tmp_path):
        monkeypatch.delattr(sys, "frozen", raising=False)
        for name in ("win32", "darwin", "linux"):
            system(name)
            assert P.ablage_basis(tmp_path / "pdf2md.py") == tmp_path.resolve()

    def test_windows_neben_der_exe(self, system, app, monkeypatch):
        monkeypatch.setattr(sys, "executable", str(app / "pdf2md.exe"))
        system("win32")
        assert P.ablage_basis(app / "x.py") == app.resolve()

    @pytest.mark.parametrize("name", ["darwin", "linux"])
    def test_app_im_dokumente_ordner(self, system, app, name):
        """Neben der App waere schlecht: das App-Paket (macOS) bzw. /usr, /opt (Linux) ist schreibgeschuetzt."""
        (app / "Documents").mkdir()
        system(name)
        assert P.ablage_basis(app / "x.py") == app / "Documents" / "pdf2md"

    def test_linux_dokumente_nach_xdg(self, system, app, monkeypatch):
        (app / "Dokumente").mkdir()
        monkeypatch.setattr(P.subprocess, "run", lambda befehl, **kw: subprocess.CompletedProcess(
            befehl, 0, stdout=str(app / "Dokumente") + "\n", stderr=""))
        system("linux")
        assert P.ablage_basis(app / "x.py") == app / "Dokumente" / "pdf2md"

    def test_ohne_dokumente_ordner_im_heimatordner(self, system, app):
        system("linux")
        assert P.ablage_basis(app / "x.py") == app / "pdf2md"
