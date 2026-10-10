"""Was je Betriebssystem anders ist (plattform.py). Die Zweige fuer macOS und Linux laufen hier mit umgesetzter
Systemkennung und nachgebildeten Programmen; die Sperrdatei nur dort, wo es fcntl gibt (GitHub: macOS, Linux)."""
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

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
    prozess = Prozess()                                   # nachgebildetes Popen, siehe unten
    monkeypatch.setattr(P.subprocess, "Popen", prozess)
    system(name)
    P.oeffnen(tmp_path)
    assert prozess.befehle == [[befehl, str(tmp_path)]]


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


def test_meldung_ohne_windows_auf_stderr(system, monkeypatch, capsys):
    monkeypatch.setattr(P.shutil, "which", lambda name: None)     # kein Dialogprogramm: nichts geht auf
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


# ---------------------------------------------------------------- Programme des Systems (macOS/Linux)
class Prozess:
    """Nachgebildetes subprocess.Popen fuer open/xdg-open: code ist der Rueckgabewert; laeuft=True haelt laenger an
    als OEFFNEN_WARTEN (so verhaelt sich xdg-open ohne Desktopumgebung: es wartet auf das gestartete Programm)."""

    def __init__(self, code=0, laeuft=False):
        self.code, self.laeuft = code, laeuft
        self.befehle, self.optionen, self.gewartet = [], [], []
        self.abgeholt = threading.Event()

    def __call__(self, befehl, **optionen):
        self.befehle.append(befehl)
        self.optionen.append(optionen)
        return self

    def wait(self, timeout=None):
        self.gewartet.append(timeout)
        if self.laeuft and timeout is not None:
            raise subprocess.TimeoutExpired(self.befehle[-1], timeout)
        self.abgeholt.set()
        return self.code


@pytest.fixture
def eigene(monkeypatch):
    """Frischer Merker fuer die Variablen aus vorbereiten(); die Umgebung kommt nach dem Test zurueck."""
    monkeypatch.setattr(P, "_EIGENE", {})
    for name in ("QTWEBENGINE_DISABLE_SANDBOX", "SSL_CERT_FILE", "LD_LIBRARY_PATH", "LD_LIBRARY_PATH_ORIG",
                 "QT_PLUGIN_PATH"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def paket(monkeypatch, tmp_path):
    """Als gebaute App: PyInstaller setzt sys.frozen und sys._MEIPASS (der Ordner _internal des Pakets)."""
    ordner = tmp_path / "pdf2md" / "_internal"
    ordner.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(ordner), raising=False)
    return ordner


@pytest.mark.parametrize("name, code, erwartet", [
    ("linux", 4, "kein Standardprogramm für diesen Dateityp eingerichtet, xdg-open meldet Fehler 4"),
    ("linux", 3, "ein Hilfsprogramm zum Öffnen fehlt, xdg-open meldet Fehler 3"),
    ("linux", 2, "Datei nicht gefunden, xdg-open meldet Fehler 2"),
    ("darwin", 1, "kein Programm für diesen Dateityp gefunden, open meldet Fehler 1")])
def test_oeffnen_meldet_fehlschlag(system, monkeypatch, tmp_path, name, code, erwartet):
    """Frueher galt unter macOS/Linux jeder Aufruf als Erfolg; jetzt kommt OSError, das Fenster zeigt den Grund."""
    monkeypatch.setattr(P.subprocess, "Popen", Prozess(code))
    system(name)
    with pytest.raises(OSError) as fehler:
        P.oeffnen(tmp_path / "Buch.pdf")
    assert str(fehler.value) == erwartet


def test_oeffnen_ohne_xdg_open(system, monkeypatch, tmp_path):
    def fehlt(befehl, **optionen):
        raise FileNotFoundError(2, "No such file or directory", befehl[0])
    monkeypatch.setattr(P.subprocess, "Popen", fehlt)
    system("linux")
    with pytest.raises(OSError, match="^xdg-open fehlt, Paket xdg-utils installieren$"):
        P.oeffnen(tmp_path)


def test_oeffnen_laeuft_laenger_gilt_als_erfolg_ohne_zombie(system, monkeypatch, tmp_path):
    prozess = Prozess(laeuft=True)
    monkeypatch.setattr(P.subprocess, "Popen", prozess)
    system("linux")
    P.oeffnen(tmp_path)                                           # kein Fehler
    assert prozess.gewartet[0] == P.OEFFNEN_WARTEN
    assert prozess.abgeholt.wait(5) and None in prozess.gewartet   # ein Thread holt den Prozess ab: kein Zombie


def test_oeffnen_ohne_eigene_variablen_in_eigener_sitzung(system, monkeypatch, tmp_path, eigene):
    system("linux")
    P.vorbereiten()                                               # Sandbox aus, aber nur fuer das eigene Fenster
    prozess = Prozess()
    monkeypatch.setattr(P.subprocess, "Popen", prozess)
    P.oeffnen(tmp_path)
    optionen = prozess.optionen[0]
    assert os.environ["QTWEBENGINE_DISABLE_SANDBOX"] == "1" and "QTWEBENGINE_DISABLE_SANDBOX" not in optionen["env"]
    assert optionen["start_new_session"] and not optionen.get("shell")
    assert optionen["stdin"] == optionen["stdout"] == optionen["stderr"] == subprocess.DEVNULL


@pytest.mark.skipif(sys.platform == "win32", reason="echtes xdg-open als Shell-Skript nur unter macOS/Linux")
@pytest.mark.parametrize("skript, fehler", [("exit 4", "Fehler 4"), ("exit 0", None), ("sleep 3", None)])
def test_oeffnen_mit_echtem_prozess(system, monkeypatch, tmp_path, skript, fehler):
    """Nachgebautes xdg-open im PATH: der Rueckgabewert zaehlt, ein lang laufendes gilt nach OEFFNEN_WARTEN als
    geoeffnet."""
    ordner = tmp_path / "bin"
    ordner.mkdir()
    programm = ordner / "xdg-open"
    programm.write_text(f"#!/bin/sh\n{skript}\n", encoding="utf-8")
    programm.chmod(0o755)
    monkeypatch.setenv("PATH", str(ordner) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(P, "OEFFNEN_WARTEN", 0.5)
    system("linux")
    beginn = time.monotonic()
    if fehler:
        with pytest.raises(OSError, match=fehler):
            P.oeffnen(tmp_path)
    else:
        P.oeffnen(tmp_path)
    assert time.monotonic() - beginn < 2.5


def test_adresse_mac_und_linux_ueber_open(system, monkeypatch):
    prozess = Prozess()
    monkeypatch.setattr(P.subprocess, "Popen", prozess)
    for name in ("darwin", "linux"):
        system(name)
        P.adresse_oeffnen("https://example.org/")
    assert prozess.befehle == [["open", "https://example.org/"], ["xdg-open", "https://example.org/"]]
    assert all("env" in o for o in prozess.optionen)


def test_adresse_windows_wie_bisher_ueber_webbrowser(system, monkeypatch):
    import webbrowser
    geoeffnet = []
    monkeypatch.setattr(webbrowser, "open", geoeffnet.append)

    def nicht_erwartet(*a, **kw):
        raise AssertionError("unter Windows kein Unterprozess")
    monkeypatch.setattr(P.subprocess, "Popen", nicht_erwartet)
    system("win32")
    P.adresse_oeffnen("https://example.org/")
    assert geoeffnet == ["https://example.org/"]


def test_fremde_umgebung_ohne_eigene_variablen(system, monkeypatch, eigene):
    """Aus dem Quellcode: eine Kopie von os.environ, nur ohne das, was vorbereiten() gesetzt hat."""
    system("linux")
    P.vorbereiten()
    monkeypatch.setenv("PDF2MD_TEST", "bleibt")
    umgebung = P.fremde_umgebung()
    assert umgebung["PDF2MD_TEST"] == "bleibt" and "QTWEBENGINE_DISABLE_SANDBOX" not in umgebung
    umgebung["PDF2MD_TEST"] = "anders"
    assert os.environ["PDF2MD_TEST"] == "bleibt"                     # Kopie, das Programm behaelt seine Umgebung


def test_fremde_umgebung_behaelt_einstellung_des_nutzers(system, monkeypatch, eigene):
    monkeypatch.setenv("QTWEBENGINE_DISABLE_SANDBOX", "0")
    system("linux")
    P.vorbereiten()
    assert P.fremde_umgebung()["QTWEBENGINE_DISABLE_SANDBOX"] == "0"


def test_fremde_umgebung_linux_app_ohne_bibliotheken_aus_dem_paket(system, monkeypatch, eigene, paket, tmp_path):
    """PyInstaller setzt LD_LIBRARY_PATH auf das Paket (Original in LD_LIBRARY_PATH_ORIG) und fuer Qt
    QT_PLUGIN_PATH; xdg-open, Dateimanager und Browser luden sonst die Bibliotheken der App."""
    system("linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(paket))
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/opt/eigene/lib")
    monkeypatch.setenv("QT_PLUGIN_PATH", str(paket / "PySide6" / "Qt" / "plugins"))
    monkeypatch.setenv("PDF2MD_PFADE", os.pathsep.join([str(paket / "bin"), str(tmp_path / "andere")]))
    umgebung = P.fremde_umgebung()
    assert umgebung["LD_LIBRARY_PATH"] == "/opt/eigene/lib" and "LD_LIBRARY_PATH_ORIG" not in umgebung
    assert "QT_PLUGIN_PATH" not in umgebung and umgebung["PDF2MD_PFADE"] == str(tmp_path / "andere")
    assert os.environ["LD_LIBRARY_PATH"] == str(paket)


def test_fremde_umgebung_linux_app_ohne_original(system, monkeypatch, eigene, paket):
    """Ohne LD_LIBRARY_PATH_ORIG war vorher keins gesetzt: dann ganz entfernen (PyInstaller-Doku)."""
    system("linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(paket))
    assert "LD_LIBRARY_PATH" not in P.fremde_umgebung()


def test_fremde_umgebung_windows_unveraendert(system, monkeypatch, eigene, paket):
    system("win32")
    monkeypatch.setenv("QT_PLUGIN_PATH", str(paket / "plugins"))
    assert P.fremde_umgebung()["QT_PLUGIN_PATH"] == str(paket / "plugins")


def test_systemprogramme_bekommen_die_fremde_umgebung(system, monkeypatch, eigene, paket):
    """gsettings, defaults und xdg-user-dir (dunkel, dokumente) laufen ebenfalls ohne die Bibliotheken der App."""
    system("linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(paket))
    umgebungen = []

    def run(befehl, **optionen):
        umgebungen.append(optionen["env"])
        return subprocess.CompletedProcess(befehl, 0, stdout="'prefer-dark'\n", stderr="")
    monkeypatch.setattr(P.subprocess, "run", run)
    assert P.dunkel()
    assert umgebungen and "LD_LIBRARY_PATH" not in umgebungen[0]


@pytest.fixture
def certifi_nachbau(monkeypatch, tmp_path):
    datei = tmp_path / "cacert.pem"
    datei.write_text("-----BEGIN CERTIFICATE-----\n", encoding="ascii")
    monkeypatch.setitem(sys.modules, "certifi", SimpleNamespace(where=lambda: str(datei)))
    return datei


@pytest.mark.parametrize("name", ["darwin", "linux"])
def test_app_nimmt_die_zertifikate_von_certifi(system, eigene, paket, certifi_nachbau, name):
    """Das mitgelieferte OpenSSL findet auf Nutzer-Macs und unter Fedora/Arch keine Wurzelzertifikate: Crossref, DNB
    und die Update-Suche scheiterten still."""
    system(name)
    P.vorbereiten()
    assert os.environ["SSL_CERT_FILE"] == str(certifi_nachbau)
    assert "SSL_CERT_FILE" not in P.fremde_umgebung()               # nicht an Programme des Systems weitergeben


def test_eigene_zertifikatsdatei_bleibt(system, monkeypatch, eigene, paket, certifi_nachbau, tmp_path):
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "firma.pem"))
    system("darwin")
    P.vorbereiten()
    assert os.environ["SSL_CERT_FILE"] == str(tmp_path / "firma.pem")
    assert P.fremde_umgebung()["SSL_CERT_FILE"] == str(tmp_path / "firma.pem")


def test_zertifikate_nur_in_der_app_ausserhalb_von_windows(system, monkeypatch, eigene, certifi_nachbau):
    monkeypatch.delattr(sys, "frozen", raising=False)
    system("darwin")
    P.vorbereiten()                                  # aus dem Quellcode: Python des Systems, nichts aendern
    assert "SSL_CERT_FILE" not in os.environ
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    system("win32")
    P.vorbereiten()                                  # Windows: Zertifikatsspeicher des Systems
    assert "SSL_CERT_FILE" not in os.environ


def test_ohne_certifi_oder_ohne_datei_keine_aenderung(system, monkeypatch, eigene, paket, tmp_path):
    system("linux")
    monkeypatch.setitem(sys.modules, "certifi", None)                # import certifi -> ImportError
    P.vorbereiten()
    assert "SSL_CERT_FILE" not in os.environ
    monkeypatch.setitem(sys.modules, "certifi", SimpleNamespace(where=lambda: str(tmp_path / "fehlt.pem")))
    P.vorbereiten()
    assert "SSL_CERT_FILE" not in os.environ


def test_certifi_liefert_eine_datei():
    """certifi steht in requirements.txt und kommt damit ins Paket."""
    datei = P._zertifikate()
    assert datei and os.path.isfile(datei)


def test_meldung_mac_ueber_osascript_text_als_argument(system, monkeypatch, capsys):
    """Anfuehrungszeichen, Backslash und AppleScript im Text: kommt unveraendert als eigenes Argument an, nie im
    Skript und nie ueber eine Shell."""
    aufrufe = []
    monkeypatch.setattr(P.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(P.subprocess, "run", lambda befehl, **optionen: aufrufe.append((befehl, optionen)))
    system("darwin")
    text = 'Ordner "Bücher\\neu" fehlt" & do shell script "x'
    P.meldung(text)
    ((befehl, optionen),) = aufrufe
    assert befehl[0] == "osascript" and befehl[-2:] == ["pdf2md", text]
    assert not any(text in teil for teil in befehl[:-1])
    assert not optionen.get("shell") and "env" in optionen
    assert text in capsys.readouterr().err


@pytest.mark.parametrize("vorhanden, programm", [({"zenity", "kdialog", "notify-send"}, "zenity"),
                                                ({"kdialog", "notify-send"}, "kdialog"),
                                                ({"notify-send"}, "notify-send")])
def test_meldung_linux_dialog_sonst_benachrichtigung(system, monkeypatch, vorhanden, programm):
    aufrufe = []
    monkeypatch.setattr(P.shutil, "which", lambda name: "/usr/bin/" + name if name in vorhanden else None)
    monkeypatch.setattr(P.subprocess, "run", lambda befehl, **optionen: aufrufe.append((befehl, optionen)))
    system("linux")
    P.meldung("Ordner <A & B> fehlt")
    ((befehl, optionen),) = aufrufe
    assert befehl[0] == programm and not optionen.get("shell") and "env" in optionen
    letzter = {"zenity": "--text=Ordner <A & B> fehlt", "kdialog": "Ordner <A & B> fehlt",
               "notify-send": "Ordner &lt;A &amp; B&gt; fehlt"}[programm]
    assert befehl[-1] == letzter
    assert programm != "zenity" or "--no-markup" in befehl


def test_meldung_linux_naechstes_programm_wenn_eins_nicht_startet(system, monkeypatch):
    aufrufe = []

    def run(befehl, **optionen):
        aufrufe.append(befehl[0])
        if befehl[0] == "zenity":
            raise PermissionError(13, "Permission denied", "zenity")
    monkeypatch.setattr(P.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(P.subprocess, "run", run)
    system("linux")
    P.meldung("Hinweis")
    assert aufrufe == ["zenity", "kdialog"]


def test_zugriff_hinweis_je_system(system):
    system("darwin")
    assert "Datenschutz & Sicherheit > Dateien und Ordner" in P.zugriff_hinweis()
    system("linux")
    assert P.zugriff_hinweis() == "Lese- und Schreibrechte prüfen"
