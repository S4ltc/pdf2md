"""Bauen fuer Windows, macOS und Linux (werkzeuge/bauen.py) und der Start-Test des gebauten Programms
(ui_app._starttest). Gebaut wird hier nichts: geprueft werden die PyInstaller-Argumente je System, die Pakete und
der Start-Test mit einem nachgebildeten Fenster. Der echte Build mit Start-Test laeuft auf GitHub (bauen.yml)."""
import importlib.util
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

import aktualisierung
import plattform
import ui_app

WURZEL = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bauen", WURZEL / "werkzeuge" / "bauen.py")
bauen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bauen)


@pytest.fixture
def system(monkeypatch):
    def setzen(name):
        monkeypatch.setattr(bauen, "SYSTEM", name)
    return setzen


class TestArgumente:
    def args(self, tmp_path):
        return bauen.pyinstaller_argumente(tmp_path / "dist", tmp_path / "arbeit")

    def test_windows_eine_exe_mit_webview2(self, system, tmp_path):
        system("win32")
        a = self.args(tmp_path)
        assert "--onefile" in a and "webview.platforms.edgechromium" in a and "pythonnet" in a
        assert a[-1].endswith("ui_app.py") and "--windowed" in a and "--noconfirm" in a

    def test_macos_app_mit_webkit(self, system, tmp_path):
        system("darwin")
        a = self.args(tmp_path)
        assert "--onefile" not in a and "webview.platforms.cocoa" in a
        assert a[a.index("--osx-bundle-identifier") + 1] == "io.github.s4ltc.pdf2md"

    def test_linux_ordner_mit_qt(self, system, tmp_path):
        """Ordner statt einer Datei: die LGPL von Qt verlangt austauschbare Bibliotheken."""
        system("linux")
        a = self.args(tmp_path)
        assert "--onefile" not in a and "webview.platforms.qt" in a and "PySide6.QtWebEngineWidgets" in a

    def test_daten_mit_dem_trenner_des_systems(self, tmp_path):
        a = self.args(tmp_path)
        daten = [a[i + 1] for i, x in enumerate(a) if x == "--add-data"]
        assert [d.rsplit(os.pathsep, 1)[1] for d in daten] == ["schriften", "ui/web"]

    @pytest.mark.parametrize("name, teil", [("win32", "pdf2md.exe"), ("darwin", "pdf2md.app/Contents/MacOS/pdf2md"),
                                            ("linux", "pdf2md/pdf2md")])
    def test_programm(self, system, tmp_path, name, teil):
        system(name)
        assert bauen.programm(tmp_path) == tmp_path / teil


class TestPaket:
    @pytest.fixture
    def ohne_lizenzlauf(self, monkeypatch):
        monkeypatch.setattr(bauen, "drittlizenzen", lambda ziel: Path(ziel).write_text("Lizenzen", encoding="utf-8"))

    def test_windows_zip(self, system, tmp_path, ohne_lizenzlauf):
        system("win32")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "pdf2md.exe").write_bytes(b"exe")
        archiv = bauen.paket("windows", "v9.9.9", tmp_path / "dist", tmp_path)
        assert archiv == tmp_path / "pdf2md-v9.9.9-windows.zip"
        assert sorted(zipfile.ZipFile(archiv).namelist()) == ["DRITTLIZENZEN.txt", "LICENSE.txt", "LIESMICH.txt",
                                                               "pdf2md.exe"]

    def test_linux_tar_mit_programmordner(self, system, tmp_path, ohne_lizenzlauf):
        system("linux")
        ordner = tmp_path / "dist" / "pdf2md"
        (ordner / "_internal").mkdir(parents=True)
        (ordner / "pdf2md").write_bytes(b"elf")
        (ordner / "_internal" / "lib.so").write_bytes(b"so")
        archiv = bauen.paket("linux-x86_64", "v9.9.9", tmp_path / "dist", tmp_path)
        assert archiv.name == "pdf2md-v9.9.9-linux-x86_64.tar.xz"
        namen = set(tarfile.open(archiv).getnames())
        assert {"pdf2md/pdf2md", "pdf2md/_internal/lib.so", "LICENSE.txt", "LIESMICH.txt",
                "DRITTLIZENZEN.txt"} <= namen
        assert tarfile.open(archiv).getmember("pdf2md/pdf2md").mode & 0o111      # ausfuehrbar

    def test_macos_mit_ditto(self, system, tmp_path, ohne_lizenzlauf, monkeypatch):
        """ditto erhaelt Verknuepfungen und Rechte im App-Paket (zipfile kann das nicht)."""
        system("darwin")
        (tmp_path / "dist" / "pdf2md.app" / "Contents" / "MacOS").mkdir(parents=True)
        aufrufe = []
        monkeypatch.setattr(bauen.subprocess, "run", lambda befehl, **kw: aufrufe.append(befehl))
        archiv = bauen.paket("macos-arm64", "v9.9.9", tmp_path / "dist", tmp_path)
        assert archiv.name == "pdf2md-v9.9.9-macos-arm64.zip"
        assert aufrufe[-1][:4] == ["ditto", "-c", "-k", "--keepParent"] and aufrufe[-1][-1] == str(archiv)


class TestAufraeumen:
    def test_nur_deutsch_und_englisch(self, tmp_path, monkeypatch):
        """Chromium-Sprachdateien und Qt-Uebersetzungen ausser de/en entfallen; was das Fenster braucht, bleibt."""
        monkeypatch.setattr(bauen.shutil, "which", lambda name: None)       # kein strip unter Windows
        qt = tmp_path / "pdf2md" / "_internal" / "PySide6" / "Qt"
        (qt / "translations" / "qtwebengine_locales").mkdir(parents=True)
        (qt / "resources").mkdir()
        for name in ("de.pak", "en-US.pak", "fr.pak", "pt-BR.pak"):
            (qt / "translations" / "qtwebengine_locales" / name).write_bytes(b"x" * 100)
        for name in ("qtbase_de.qm", "qt_en.qm", "qt_help_de.qm", "qtbase_fr.qm", "qt_pt_BR.qm"):
            (qt / "translations" / name).write_bytes(b"x" * 10)
        (qt / "resources" / "qtwebengine_devtools_resources.pak").write_bytes(b"x")
        (qt / "resources" / "qtwebengine_resources.pak").write_bytes(b"x")
        assert bauen.aufraeumen(tmp_path) == 220
        assert sorted(p.name for p in qt.rglob("*") if p.is_file()) == [
            "de.pak", "en-US.pak", "qt_en.qm", "qt_help_de.qm", "qtbase_de.qm", "qtwebengine_devtools_resources.pak",
            "qtwebengine_resources.pak"]

    def test_nur_unter_linux(self, system, tmp_path, monkeypatch):
        aufrufe = []
        monkeypatch.setattr(bauen.subprocess, "run", lambda befehl, **kw: subprocess.CompletedProcess(befehl, 0))
        monkeypatch.setattr(bauen, "aufraeumen", lambda ausgabe: aufrufe.append(ausgabe) or 0)
        for name in ("win32", "darwin", "linux"):
            system(name)
            assert bauen.bauen(tmp_path) == 0
        assert aufrufe == [tmp_path]


class FensterNachbau:
    """Wie ein pywebview-Fenster: die Versionsnummer erscheint erst nach ein paar Abfragen."""
    def __init__(self, nach=3, text=aktualisierung.VERSION):
        self.abfragen, self.nach, self.text, self.geschlossen = 0, nach, text, False

    def evaluate_js(self, code):
        self.abfragen += 1
        return self.text if self.abfragen > self.nach else ""

    def destroy(self):
        self.geschlossen = True


class TestStarttest:
    def test_oberflaeche_meldet_sich(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ui_app, "STARTTEST_TAKT", 0.01)
        fenster = FensterNachbau()
        ui_app._starttest(fenster, tmp_path / "ergebnis.json")
        ergebnis = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))
        assert ergebnis["ok"] and ergebnis["version"] == aktualisierung.VERSION and ergebnis["gui"] == plattform.gui()
        assert fenster.geschlossen

    def test_ohne_antwort_nicht_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ui_app, "STARTTEST_TAKT", 0.01)
        monkeypatch.setattr(ui_app, "STARTTEST_WARTEN", 0.1)
        fenster = FensterNachbau(nach=10 ** 6)
        ui_app._starttest(fenster, tmp_path / "ergebnis.json")
        assert not json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))["ok"] and fenster.geschlossen


class TestStarttestAuswerten:
    def test_ergebnis_und_fehler(self, tmp_path, monkeypatch, system):
        system("win32")
        (tmp_path / "pdf2md.exe").write_bytes(b"exe")

        def laufen(befehl, env, **kw):
            Path(env["PDF2MD_STARTTEST"]).write_text(json.dumps({"ok": True, "gui": "edgechromium"}), encoding="utf-8")
            assert env["PDF2MD_ABLAGE"] and Path(befehl[-1]).name == "pdf2md.exe"
            return subprocess.CompletedProcess(befehl, 0, "", "")
        monkeypatch.setattr(bauen.subprocess, "run", laufen)
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 0
        assert json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))["ok"]

        monkeypatch.setattr(bauen.subprocess, "run",
                            lambda befehl, env, **kw: subprocess.CompletedProcess(befehl, 1, "", "Absturz"))
        assert bauen.starttest(tmp_path, tmp_path / "starttest.json") == 1
        assert "Absturz" in json.loads((tmp_path / "starttest.json").read_text(encoding="utf-8"))["ausgabe"]


def test_linux_ohne_chromium_sandbox(monkeypatch):
    """Ubuntu ab 23.10 sperrt die Sandbox von QtWebEngine fuer Programme ohne AppArmor-Profil; das Fenster laedt nur
    die eigenen lokalen Dateien, deshalb wird sie abgeschaltet (vorhandene Einstellung bleibt)."""
    monkeypatch.delenv("QTWEBENGINE_DISABLE_SANDBOX", raising=False)
    monkeypatch.setattr(plattform, "SYSTEM", "linux")
    plattform.vorbereiten()
    assert os.environ["QTWEBENGINE_DISABLE_SANDBOX"] == "1"
    monkeypatch.setenv("QTWEBENGINE_DISABLE_SANDBOX", "0")
    plattform.vorbereiten()
    assert os.environ["QTWEBENGINE_DISABLE_SANDBOX"] == "0"
    monkeypatch.delenv("QTWEBENGINE_DISABLE_SANDBOX")
    monkeypatch.setattr(plattform, "SYSTEM", "win32")
    plattform.vorbereiten()
    assert "QTWEBENGINE_DISABLE_SANDBOX" not in os.environ


class TestLizenzen:
    @pytest.fixture
    def drittlizenzen(self):
        spec = importlib.util.spec_from_file_location("drittlizenzen", WURZEL / "werkzeuge" / "drittlizenzen.py")
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        return modul

    @pytest.mark.parametrize("name, programm, engine", [("win32", "pdf2md.exe", "WebView2"),
                                                        ("darwin", "pdf2md.app", "WebKit"),
                                                        ("linux", "Programmordner pdf2md", "LGPL")])
    def test_einleitung_je_system(self, drittlizenzen, name, programm, engine):
        text = "\n".join(drittlizenzen.einleitung(name))
        assert programm in text and engine in text
        assert ("WebView2" in text) == (name == "win32")

    @staticmethod
    def abschnitt(kopf, inhalt):
        return f"{'=' * 79}\n{kopf}\n{'=' * 79}\n{inhalt}\n"

    def test_bericht_ueber_die_lizenzen(self, tmp_path):
        (tmp_path / "DRITTLIZENZEN.txt").write_text(
            "Kopf\n\nPython 3.13 – PSF\nPySide6 6.10 – LGPL\nqtpy 2.4 – MIT\nleer 1.0 – MIT\n\n"
            + self.abschnitt("Python 3.13", "XZ\n======\n- COPYING.LGPLv2.1: GNU Lesser General Public License")
            + self.abschnitt("PySide6 6.10 – LGPL", "--- LICENSES/LGPL-3.0.txt\nGNU LESSER GENERAL PUBLIC LICENSE\n"
                                                    "                       Version 3, 29 June 2007")
            + self.abschnitt("qtpy 2.4 – MIT", "--- Standardtext MIT (im Paket nicht enthalten)\nPermission ...")
            + self.abschnitt("leer 1.0 – MIT", "(kein Lizenztext im Paket; Lizenzangabe siehe oben, Quelle: PyPI)"),
            encoding="utf-8")
        bericht = bauen.lizenzbericht(tmp_path)
        assert bericht["eintraege"] == 4 and bericht["lgpl3_volltext"]
        assert bericht["ohne_lizenztext"] == ["leer 1.0 – MIT"] and bericht["nur_standardtext"] == ["qtpy 2.4 – MIT"]
        assert list(bericht["qt_lizenztext_zeichen"]) == ["PySide6 6.10 – LGPL"]

    class Paket:
        def __init__(self, name):
            self.metadata = {"Name": name}

    def test_gnu_texte_nur_mit_qt(self, drittlizenzen, tmp_path):
        """PySide6 nennt die LGPL nur; ihr Text und der der GPL 3 (auf der sie aufbaut) kommen vom Build-System."""
        (tmp_path / "LGPL-3").write_text("GNU LESSER GENERAL PUBLIC LICENSE\n  Version 3", encoding="utf-8")
        (tmp_path / "GPL-3").write_text("GNU GENERAL PUBLIC LICENSE\n  Version 3", encoding="utf-8")
        assert drittlizenzen.gnu_texte([self.Paket("pypdfium2")], tmp_path) == []
        texte = drittlizenzen.gnu_texte([self.Paket("pypdfium2"), self.Paket("PySide6_Essentials")], tmp_path)
        assert [t.split()[:4] for _, t in texte] == [["GNU", "LESSER", "GENERAL", "PUBLIC"],
                                                     ["GNU", "GENERAL", "PUBLIC", "LICENSE"]]

    def test_gnu_texte_fehlen_bricht_ab(self, drittlizenzen, tmp_path):
        with pytest.raises(SystemExit, match="LGPL-3"):
            drittlizenzen.gnu_texte([self.Paket("shiboken6")], tmp_path)

    def test_lgpl_nur_erwaehnt_zaehlt_nicht(self, tmp_path):
        """Die Lizenz von Python nennt die LGPL 2.1 (xz); das ist nicht der Text der LGPL 3 fuer Qt."""
        (tmp_path / "DRITTLIZENZEN.txt").write_text(
            "Kopf\n\n" + self.abschnitt("Python 3.13", "- COPYING.LGPLv2.1: GNU Lesser General Public License"),
            encoding="utf-8")
        assert not bauen.lizenzbericht(tmp_path)["lgpl3_volltext"]

    def test_groessenbericht(self, tmp_path):
        (tmp_path / "pdf2md" / "_internal" / "Qt").mkdir(parents=True)
        (tmp_path / "pdf2md" / "_internal" / "Qt" / "gross.so").write_bytes(b"x" * 3_000_000)
        (tmp_path / "pdf2md" / "_internal" / "Qt" / "klein.so").write_bytes(b"x" * 1_000_000)
        (tmp_path / "LICENSE.txt").write_bytes(b"x" * 100_000)
        bericht = bauen.groessenbericht(tmp_path, anzahl=2)
        assert bericht["entpackt_mb"] == 4.1 and bericht["dateien"] == 3
        assert bericht["groesste_dateien"] == ["   3.0 MB  pdf2md/_internal/Qt/gross.so",
                                               "   1.0 MB  pdf2md/_internal/Qt/klein.so"]
        assert bericht["groesste_ordner"] == ["   4.0 MB  pdf2md/_internal/Qt", "   0.1 MB  ."]
