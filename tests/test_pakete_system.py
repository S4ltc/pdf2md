"""Was die Pakete vom System verlangen und wie sie ankommen (werkzeuge/bauen.py): gemessene Mindestversion (macOS:
minos aller Mach-O-Dateien, Linux: hoechste GLIBC-Symbolversion aller ELF-Dateien), Nachbearbeitung der macOS-App
(Info.plist, neue Signatur) und das Linux-Archiv mit einem Oberordner, dazu der Job distributionen in bauen.yml (in
bash nachgestellt, braucht PyYAML). otool, objdump, readelf, codesign, apt-get, dnf und ldd sind nachgebildet; nur
die Tests am Ende laufen mit dem echten Werkzeug, wenn das System es hat (macOS bzw. Linux in tests.yml auf
GitHub)."""
import ast
import importlib.util
import io
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tokenize
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bauen", WURZEL / "werkzeuge" / "bauen.py")
bauen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bauen)


@pytest.fixture
def system(monkeypatch):
    def setzen(name):
        monkeypatch.setattr(bauen, "SYSTEM", name)
    return setzen


def hoechste(versionen):
    return max(versionen, key=bauen._versionsschluessel)


# Nachgebildete Ausgaben der Werkzeuge (Aufbau wie binutils 2.38 bzw. otool aus Xcode; Namen erfunden)
OBJDUMP_T = """
/tmp/beispiel/libbeispiel.so.1:     file format elf64-x86-64

DYNAMIC SYMBOL TABLE:
0000000000000000      DF *UND*\t0000000000000000 (GLIBC_2.3)  __ctype_toupper_loc
0000000000000000      DF *UND*\t0000000000000000  GLIBC_2.2.5 getenv
0000000000000000      DF *UND*\t0000000000000000  GLIBC_2.17  clock_gettime
0000000000000000      DF *UND*\t0000000000000000  GLIBC_PRIVATE _dl_beispiel
0000000000000000      DF *UND*\t0000000000000000  GLIBCXX_3.4.30 _ZSt28__throw_bad_array_new_lengthv
0000000000000000  w   D  *UND*\t0000000000000000  Base        __gmon_start__
0000000000012340 g    DF .text\t0000000000000042  Base        beispiel_funktion
0000000000012400 g    DF .text\t0000000000000010  GLIBC_2.38  beispiel_kompat
"""

READELF_V = """
Version symbols section '.gnu.version' contains 5 entries:
 Addr: 0x0000000000000500  Offset: 0x000500  Link: 5 (.dynsym)
  000:   0 (*local*)       2 (GLIBC_2.2.5)   3 (GLIBC_2.34)    1 (*global*)
  004:   4 (GLIBC_2.99)

Version definition section '.gnu.version_d' contains 2 entries:
  Addr: 0x0000000000000520  Offset: 0x000520  Link: 6 (.dynstr)
  000000: Rev: 1  Flags: BASE  Index: 1  Cnt: 1  Name: libbeispiel.so.1
  0x001c: Rev: 1  Flags: none  Index: 2  Cnt: 1  Name: GLIBC_2.99

Version needs section '.gnu.version_r' contains 1 entry:
 Addr: 0x0000000000000558  Offset: 0x000558  Link: 6 (.dynstr)
  000000: Version: 1  File: libc.so.6  Cnt: 2
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 3
  0x0020:   Name: GLIBC_2.2.5  Flags: none  Version: 2
"""

READELF_DYNSYMS = """
Symbol table '.dynsym' contains 5 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
     0: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  UND
     1: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND free@GLIBC_2.2.5 (2)
     2: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND pthread_create@GLIBC_2.34 (3)
     3: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND _ZNSt8ios_base4InitC1Ev@GLIBCXX_3.4 (4)
     4: 0000000000001234    16 FUNC    GLOBAL DEFAULT   12 beispiel_kompat@@GLIBC_2.38
"""

OTOOL_NEU = """/tmp/beispiel/pdf2md.app/Contents/Frameworks/libbeispiel.dylib:
Load command 0
      cmd LC_SEGMENT_64
  cmdsize 552
  segname __TEXT
   vmaddr 0x0000000000000000
Load command 8
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos 11.0
      sdk 14.2
   ntools 1
     tool 3
  version 1022.1
Load command 9
          cmd LC_LOAD_DYLIB
      cmdsize 56
         name /usr/lib/libSystem.B.dylib (offset 24)
   time stamp 2 Thu Jan  1 00:00:02 1970
      current version 1336.0.0
compatibility version 1.0.0
"""

OTOOL_ALT = """/tmp/beispiel/libalt.so:
Load command 7
      cmd LC_VERSION_MIN_MACOSX
  cmdsize 16
  version 10.9
      sdk 10.14
"""

OTOOL_UNIVERSAL = """/tmp/beispiel/libuniversal.dylib (architecture x86_64):
Load command 0
      cmd LC_VERSION_MIN_MACOSX
  cmdsize 16
  version 10.9
      sdk 10.14
/tmp/beispiel/libuniversal.dylib (architecture arm64):
Load command 0
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos 11.0
      sdk 13.1
   ntools 1
     tool 3
  version 820.1
"""

OTOOL_CATALYST = """/tmp/beispiel/libzippered.dylib:
Load command 10
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 6
    minos 14.0
      sdk 17.0
   ntools 0
Load command 11
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform MACOS
    minos 10.15
      sdk 14.0
   ntools 0
"""


class TestVersionenLesen:
    def test_reihenfolge(self):
        """Zahlen statt Text vergleichen: 2.2.5 < 2.17 < 2.34; 11.0 und 11 sind gleich."""
        assert sorted(["2.34", "2.17", "2.2.5", "2.3"], key=bauen._versionsschluessel) == ["2.2.5", "2.3", "2.17",
                                                                                           "2.34"]
        assert bauen._versionsschluessel("11.0") == bauen._versionsschluessel("11")
        assert hoechste(["10.13", "11.0", "10.9"]) == "11.0" and hoechste(["13.3", "13.10"]) == "13.10"

    def test_objdump(self):
        """GLIBC_PRIVATE und die Versionen der libstdc++ (GLIBCXX_) zaehlen nicht, ebenso wenig eine Version, die die
        Datei selbst anbietet (definiertes Symbol, wie GLIBC_2.2.5 in libcrypt aus libxcrypt; hier 2.38)."""
        assert sorted(bauen.glibc_versionen(OBJDUMP_T)) == ["2.17", "2.2.5", "2.3"]
        assert hoechste(bauen.glibc_versionen(OBJDUMP_T)) == "2.17"

    def test_readelf_v_ohne_eigene_definitionen(self):
        """Es zaehlt nur "Version needs": was eine Datei selbst anbietet (Version definition), verlangt sie nicht, und
        "Version symbols" mischt Angebotenes und Verlangtes."""
        assert "2.99" not in bauen.glibc_versionen(READELF_V)
        assert hoechste(bauen.glibc_versionen(READELF_V)) == "2.34"

    def test_readelf_dyn_syms(self):
        assert sorted(bauen.glibc_versionen(READELF_DYNSYMS)) == ["2.2.5", "2.34"]

    def test_ohne_glibc(self):
        assert bauen.glibc_versionen("") == [] and bauen.glibc_versionen("DYNAMIC SYMBOL TABLE:\n") == []

    def test_otool_build_version(self):
        """minos zaehlt, nicht die Version des Linkers ("version 1022.1") und nicht die der Bibliotheken."""
        assert bauen.macos_versionen(OTOOL_NEU) == ["11.0"]

    def test_otool_alte_angabe(self):
        """LC_VERSION_MIN_MACOSX: version, nicht sdk."""
        assert bauen.macos_versionen(OTOOL_ALT) == ["10.9"]

    def test_otool_nur_macos_nicht_catalyst(self):
        assert bauen.macos_versionen(OTOOL_CATALYST) == ["10.15"]

    def test_otool_universal_nur_eigene_architektur(self):
        """Ein x86_64-Teil mit 10.9 sagt nichts ueber den arm64-Teil (und umgekehrt)."""
        assert bauen.macos_versionen(OTOOL_UNIVERSAL, "arm64") == ["11.0"]
        assert bauen.macos_versionen(OTOOL_UNIVERSAL, "x86_64") == ["10.9"]
        assert sorted(bauen.macos_versionen(OTOOL_UNIVERSAL)) == ["10.9", "11.0"]


ELF = b"\x7fELF" + b"\x00" * 60
MACH_O = bytes.fromhex("cffaedfe") + b"\x00" * 60
UNIVERSAL = bytes.fromhex("cafebabe") + b"\x00" * 60


def anlegen(ordner: Path, dateien: dict) -> None:
    for name, inhalt in dateien.items():
        (ordner / name).parent.mkdir(parents=True, exist_ok=True)
        (ordner / name).write_bytes(inhalt)


class TestMindestversionen:
    def nachbau(self, ausgaben):
        """Statt des Werkzeugs: Ausgabe je Dateiname; merkt sich, welche Dateien gefragt wurden."""
        gefragt = []

        def ausgabe_von(datei):
            gefragt.append(datei.name)
            return ausgaben.get(datei.name, "")
        return ausgabe_von, gefragt

    def test_linux_hoechste_glibc_und_wer_sie_setzt(self, system, tmp_path):
        system("linux")
        anlegen(tmp_path, {"pdf2md/pdf2md": ELF, "pdf2md/_internal/libalt.so.1": ELF,
                           "pdf2md/_internal/libneu.so.2": ELF, "pdf2md/_internal/libohne.so": ELF,
                           "pdf2md/_internal/daten.bin": b"keine ELF-Datei", "LICENSE.txt": b"Lizenz"})
        alt = "0000000000000000      DF *UND*\t0000000000000000  GLIBC_2.2.5 free\n"
        ausgabe_von, gefragt = self.nachbau({"pdf2md": OBJDUMP_T, "libalt.so.1": alt, "libneu.so.2": READELF_V})
        bericht = bauen.mindestversionen(tmp_path, ausgabe_von)
        assert bericht == {"glibc_max": "2.34", "glibc_max_dateien": ["pdf2md/_internal/libneu.so.2"]}
        assert sorted(gefragt) == ["libalt.so.1", "libneu.so.2", "libohne.so", "pdf2md"]   # nur ELF-Dateien

    def test_macos_hoechstes_minos(self, system, tmp_path):
        system("darwin")
        anlegen(tmp_path, {"pdf2md.app/Contents/MacOS/pdf2md": MACH_O,
                           "pdf2md.app/Contents/Frameworks/libalt.so": MACH_O,
                           "pdf2md.app/Contents/Frameworks/libuniversal.dylib": UNIVERSAL,
                           "pdf2md.app/Contents/Info.plist": b"<?xml version", "LICENSE.txt": b"Lizenz"})
        ausgabe_von, gefragt = self.nachbau({"pdf2md": OTOOL_NEU, "libalt.so": OTOOL_ALT,
                                             "libuniversal.dylib": OTOOL_UNIVERSAL})
        assert bauen.mindestversionen(tmp_path, ausgabe_von, arch="x86_64") == {
            "macos_minos": "11.0", "macos_minos_dateien": ["pdf2md.app/Contents/MacOS/pdf2md"]}
        assert bauen.mindestversionen(tmp_path, ausgabe_von, arch="arm64")["macos_minos_dateien"] == [
            "pdf2md.app/Contents/Frameworks/libuniversal.dylib", "pdf2md.app/Contents/MacOS/pdf2md"]
        assert "Info.plist" not in gefragt and "LICENSE.txt" not in gefragt

    def test_windows_nichts(self, system, tmp_path):
        system("win32")
        anlegen(tmp_path, {"pdf2md.exe": b"MZ", "x.so": ELF})
        ausgabe_von, gefragt = self.nachbau({})
        assert bauen.mindestversionen(tmp_path, ausgabe_von) == {} and gefragt == []

    def test_ohne_binaerdateien(self, system, tmp_path):
        system("linux")
        anlegen(tmp_path, {"LICENSE.txt": b"Lizenz"})
        assert bauen.mindestversionen(tmp_path, self.nachbau({})[0]) == {"glibc_max": None, "glibc_max_dateien": []}

    def test_werkzeug_fehlt(self, system, tmp_path):
        """Ohne Werkzeug keine geschaetzte Zahl, sondern ein klarer Vermerk im Bericht."""
        system("linux")
        anlegen(tmp_path, {"lib.so": ELF})

        def fehlt(datei):
            raise FileNotFoundError("objdump")
        bericht = bauen.mindestversionen(tmp_path, fehlt)
        assert bericht["glibc_max"] is None and "nicht messbar" in bericht["glibc_max_fehler"]

    @pytest.mark.parametrize("name, vorhanden, befehl", [("darwin", {"otool"}, ["otool", "-l"]),
                                                         ("linux", {"objdump", "readelf"}, ["objdump", "-T"]),
                                                         ("linux", {"readelf"}, ["readelf", "-V", "-W"])])
    def test_welches_werkzeug(self, system, tmp_path, monkeypatch, name, vorhanden, befehl):
        system(name)
        aufrufe = []
        monkeypatch.setattr(bauen.shutil, "which", lambda w: f"/usr/bin/{w}" if w in vorhanden else None)
        monkeypatch.setattr(bauen.subprocess, "run",
                            lambda b, **kw: aufrufe.append(b) or subprocess.CompletedProcess(b, 0, "GLIBC_2.17", ""))
        assert bauen._versionsausgabe(tmp_path / "lib.so") == "GLIBC_2.17"
        assert aufrufe == [befehl + [str(tmp_path / "lib.so")]]

    def test_im_paketbericht(self, system, tmp_path, monkeypatch):
        """groessenbericht (und damit paket.json) traegt das gemessene Minimum ein."""
        system("linux")
        monkeypatch.setattr(bauen, "drittlizenzen", lambda ziel: Path(ziel).write_text("Lizenzen", encoding="utf-8"))
        monkeypatch.setattr(bauen, "_versionsausgabe", lambda datei: OBJDUMP_T if datei.name == "pdf2md" else "")
        anlegen(tmp_path / "dist", {"pdf2md/pdf2md": ELF, "pdf2md/_internal/lib.so": ELF})
        bauen.paket("linux-x86_64", "v9.9.9", tmp_path / "dist", tmp_path)
        bericht = json.loads((tmp_path / "paket.json").read_text(encoding="utf-8"))
        assert bericht["glibc_max"] == "2.17" and bericht["glibc_max_dateien"] == ["pdf2md/pdf2md"]


class TestLinuxArchiv:
    @pytest.fixture
    def archiv(self, system, tmp_path, monkeypatch):
        system("linux")
        monkeypatch.setattr(bauen, "drittlizenzen", lambda ziel: Path(ziel).write_text("Lizenzen", encoding="utf-8"))
        monkeypatch.setattr(bauen, "_versionsausgabe", lambda datei: "")
        original = tarfile.TarFile.gettarinfo

        def wie_auf_github(selbst, *args, **kwargs):        # Windows kennt keine uid: das Build-Konto nachbilden
            info = original(selbst, *args, **kwargs)
            info.uid, info.gid, info.uname, info.gname = 1001, 118, "runner", "docker"
            return info
        monkeypatch.setattr(tarfile.TarFile, "gettarinfo", wie_auf_github)
        anlegen(tmp_path / "dist", {"pdf2md/pdf2md": ELF, "pdf2md/_internal/lib.so": ELF})
        return bauen.paket("linux-x86_64", "v9.9.9", tmp_path / "dist", tmp_path)

    def test_ein_oberordner(self, archiv, tmp_path):
        """tar -xf im Download-Ordner legt genau einen Ordner an (frueher lagen LICENSE.txt usw. lose daneben)."""
        ziel = tmp_path / "entpackt"
        with tarfile.open(archiv) as tar:
            oben = tar.getmember("pdf2md-v9.9.9-linux-x86_64")
            assert oben.isdir() and (oben.mode & 0o777) == 0o755
            # root als Eigentuemer, nicht das Build-Konto (entpackt root nach /opt, gehoerte es sonst irgendwem)
            assert {(m.uid, m.gid, m.uname, m.gname) for m in tar.getmembers()} == {(0, 0, "", "")}
            tar.extractall(ziel, filter="data")
        assert [p.name for p in ziel.iterdir()] == ["pdf2md-v9.9.9-linux-x86_64"]
        assert sorted(p.name for p in (ziel / "pdf2md-v9.9.9-linux-x86_64").iterdir()) == [
            "DRITTLIZENZEN.txt", "LICENSE.txt", "LIESMICH.txt", "pdf2md"]

    def test_starttest_im_oberordner(self, archiv, tmp_path, monkeypatch):
        """bauen.yml (Distributionen) startet das entpackte Paket mit dem Oberordner als Ausgabeordner."""
        ziel = tmp_path / "entpackt"
        with tarfile.open(archiv) as tar:
            tar.extractall(ziel, filter="data")
        ordner = ziel / "pdf2md-v9.9.9-linux-x86_64"
        gestartet = []

        def laufen(befehl, env, **kw):
            gestartet.append(befehl)
            Path(env["PDF2MD_STARTTEST"]).write_text(json.dumps({"ok": True, "gui": "qt"}), encoding="utf-8")
            return subprocess.CompletedProcess(befehl, 0, "", "")
        monkeypatch.setattr(bauen.subprocess, "run", laufen)
        monkeypatch.setenv("DISPLAY", ":0")                 # kein xvfb-run noetig
        assert bauen.starttest(ordner, tmp_path / "starttest.json") == 0
        assert gestartet == [[str(ordner / "pdf2md" / "pdf2md")]] and Path(gestartet[0][0]).is_file()


class TestMacApp:
    @pytest.fixture
    def app(self, system, tmp_path, monkeypatch):
        """Eine nachgebaute pdf2md.app mit der Info.plist, wie PyInstaller sie anlegt (gekuerzt)."""
        system("darwin")
        app = tmp_path / "dist" / "pdf2md.app"
        anlegen(app, {"Contents/MacOS/pdf2md": MACH_O, "Contents/Frameworks/libalt.so": MACH_O})
        with open(app / "Contents" / "Info.plist", "wb") as f:
            plistlib.dump({"CFBundleIdentifier": "io.github.s4ltc.pdf2md", "CFBundleExecutable": "pdf2md"}, f)
        monkeypatch.setattr(bauen, "_versionsausgabe",
                            lambda datei: OTOOL_NEU.replace("11.0", "13.3") if datei.name == "pdf2md" else OTOOL_ALT)
        return app

    @staticmethod
    def info(app):
        with open(app / "Contents" / "Info.plist", "rb") as f:
            return plistlib.load(f)

    def codesign_nachbau(self, monkeypatch, app, signieren_ok=True, pruefen_ok=None):
        aufrufe = []
        pruefen_ok = signieren_ok if pruefen_ok is None else pruefen_ok

        def laufen(befehl, **kw):
            aufrufe.append(befehl)
            if befehl[:2] == ["codesign", "--force"]:      # signiert wird erst nach der Aenderung der Info.plist
                assert "NSDocumentsFolderUsageDescription" in self.info(app)
                return subprocess.CompletedProcess(befehl, 0 if signieren_ok else 1, "", "" if signieren_ok else
                                                   "pdf2md.app: code object is not signed at all")
            if befehl[:2] == ["codesign", "--verify"]:
                return subprocess.CompletedProcess(befehl, 0 if pruefen_ok else 1, "",
                                                   "pdf2md.app: valid on disk" if pruefen_ok else
                                                   "pdf2md.app: a sealed resource is missing or invalid")
            return subprocess.CompletedProcess(befehl, 0, "", "")   # PyInstaller
        monkeypatch.setattr(bauen.subprocess, "run", laufen)
        return aufrufe

    def test_info_plist_und_neue_signatur(self, app, monkeypatch):
        aufrufe = self.codesign_nachbau(monkeypatch, app)
        bericht = bauen.app_nachbearbeiten(app.parent)
        info = self.info(app)
        assert info["LSMinimumSystemVersion"] == "13.3"           # gemessen, nicht geschaetzt
        assert "Dokumente" in info["NSDocumentsFolderUsageDescription"]
        assert info["CFBundleIdentifier"] == "io.github.s4ltc.pdf2md" and info["CFBundleExecutable"] == "pdf2md"
        assert aufrufe == [["codesign", "--force", "--deep", "--sign", "-", str(app)],
                           ["codesign", "--verify", "--deep", "--strict", "--all-architectures", "--verbose=2",
                            str(app)]]
        assert bericht["macos_minos"] == "13.3" and bericht["macos_minos_dateien"] == ["Contents/MacOS/pdf2md"]
        assert bericht["signiert"] and bericht["signatur_gueltig"] and "valid on disk" in bericht["codesign"]
        assert bericht["info_plist"]["LSMinimumSystemVersion"] == "13.3"
        assert bericht["LSMinimumSystemVersion_vorher"] is None

    def test_ohne_messung_keine_mindestversion(self, app, monkeypatch):
        """Laesst sich minos nicht messen, bleibt LSMinimumSystemVersion weg (lieber keine Angabe als eine falsche)."""
        monkeypatch.setattr(bauen, "_versionsausgabe", lambda datei: "")
        self.codesign_nachbau(monkeypatch, app)
        bericht = bauen.app_nachbearbeiten(app.parent)
        assert "LSMinimumSystemVersion" not in self.info(app) and bericht["macos_minos"] is None
        assert "NSDocumentsFolderUsageDescription" in self.info(app)

    def test_bauen_schreibt_bericht(self, app, tmp_path, monkeypatch):
        monkeypatch.setattr(bauen, "WURZEL", tmp_path)
        self.codesign_nachbau(monkeypatch, app)
        assert bauen.bauen(app.parent) == 0
        bericht = json.loads((tmp_path / "aufgeraeumt.json").read_text(encoding="utf-8"))
        assert bericht["macos_minos"] == "13.3" and bericht["signiert"] and bericht["signatur_gueltig"]

    def test_signatur_misslingt_bauen_scheitert(self, app, tmp_path, monkeypatch):
        """Nach der Aenderung der Info.plist gilt die alte Signatur nicht mehr; ohne neue startet die App nicht."""
        monkeypatch.setattr(bauen, "WURZEL", tmp_path)
        self.codesign_nachbau(monkeypatch, app, signieren_ok=False)
        assert bauen.bauen(app.parent) == 1
        bericht = json.loads((tmp_path / "aufgeraeumt.json").read_text(encoding="utf-8"))
        assert not bericht["signiert"] and "not signed" in bericht["codesign"]

    def test_pruefung_misslingt_bauen_scheitert(self, app, tmp_path, monkeypatch, capsys):
        """Signieren gelingt, die strenge Pruefung (--verify --deep --strict --all-architectures) nicht: frueher nur
        eine Notiz in aufgeraeumt.json und Rueckgabe 0, das Paket waere trotz ungueltiger Signatur entstanden."""
        monkeypatch.setattr(bauen, "WURZEL", tmp_path)
        aufrufe = self.codesign_nachbau(monkeypatch, app, signieren_ok=True, pruefen_ok=False)
        assert bauen.bauen(app.parent) == 1
        assert "--all-architectures" in aufrufe[-1] and aufrufe[-1][:2] == ["codesign", "--verify"]
        bericht = json.loads((tmp_path / "aufgeraeumt.json").read_text(encoding="utf-8"))
        assert bericht["signiert"] and not bericht["signatur_gueltig"] and "sealed resource" in bericht["codesign"]
        assert "Pruefen" in capsys.readouterr().err

    def test_windows_ohne_nachbearbeitung(self, system, tmp_path, monkeypatch):
        system("win32")
        monkeypatch.setattr(bauen, "WURZEL", tmp_path)
        monkeypatch.setattr(bauen.subprocess, "run", lambda befehl, **kw: subprocess.CompletedProcess(befehl, 0))
        assert bauen.bauen(tmp_path) == 0 and not (tmp_path / "aufgeraeumt.json").exists()


# Wie im Container des Distributionstests: bauen.py ohne pip-Pakete (python -I -S, also ohne site-packages) laden,
# starttest mit nachgebildetem Programm und hinweise aufrufen, danach melden, welche Module ausserhalb der
# Standardbibliothek geladen wurden. Ein Teil des Start-Tests, der fpdf2 o.ae. braucht, muss dort still entfallen.
OHNE_PAKETE = '''
import importlib.util, json, subprocess, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("bauen", sys.argv[1])
bauen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bauen)
bauen.SYSTEM = "linux"
ordner = Path(sys.argv[2])
def laufen(befehl, *args, **kw):
    ziel = (kw.get("env") or {}).get("PDF2MD_STARTTEST")
    if ziel:
        Path(ziel).write_text(json.dumps({"ok": True, "gui": "qt"}), encoding="utf-8")
    return subprocess.CompletedProcess(befehl, 0, "", "")
subprocess.run = laufen
bauen.os.environ["DISPLAY"] = ":0"
code = bauen.starttest(ordner, ordner / "starttest.json")
hinweis = bauen.hinweise("linux test", ordner, tag="probe")[0]
fremd = sorted({m.split(".")[0] for m in sys.modules} - set(sys.stdlib_module_names) - {"__main__", "bauen"})
print(json.dumps({"code": code, "hinweis": hinweis, "fremd": fremd}))
'''


def ohne_pakete(bauen_py: Path, ordner: Path) -> dict:
    (ordner / "pdf2md").mkdir(parents=True, exist_ok=True)
    (ordner / "pdf2md" / "pdf2md").write_bytes(ELF)
    (ordner / "kind.py").write_text(OHNE_PAKETE, encoding="utf-8")
    lauf = subprocess.run([sys.executable, "-I", "-S", str(ordner / "kind.py"), str(bauen_py), str(ordner)],
                          capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 0, lauf.stderr[-2000:]
    return json.loads(lauf.stdout.strip().splitlines()[-1])


def fstring_neue_syntax(quelle: str) -> list[str]:
    """Zeichenketten in einem f-String mit denselben Anfuehrungszeichen wie aussen: erst ab Python 3.12 (PEP 701)."""
    def zeichen(token):
        rest = token.lstrip("rRbBuUfF")
        return rest[:3] if rest[:3] in ('"""', "'''") else rest[:1]
    aussen, funde = [], []
    for token in tokenize.generate_tokens(io.StringIO(quelle).readline):
        if token.type in (tokenize.FSTRING_START, tokenize.STRING) and aussen and zeichen(token.string) == aussen[-1]:
            funde.append(f"Zeile {token.start[0]}: {token.line.strip()}")
        if token.type == tokenize.FSTRING_START:
            aussen.append(zeichen(token.string))
        elif token.type == tokenize.FSTRING_END:
            aussen.pop()
    return funde


def test_bauen_laeuft_ohne_pakete(tmp_path):
    """Der Distributionstest (bauen.yml) startet bauen.py mit dem python3 des Containers, ohne pip: starttest und
    hinweise brauchen nur die Standardbibliothek."""
    ergebnis = ohne_pakete(WURZEL / "werkzeuge" / "bauen.py", tmp_path)
    assert ergebnis["code"] == 0 and ergebnis["fremd"] == []
    assert ergebnis["hinweis"].startswith("::notice title=Start-Test linux test::OK ")


def test_ohne_pakete_erkennt_fremden_import(tmp_path):
    """Die Nachstellung oben schlaegt an, wenn bauen.py beim Start-Test ein Paket braucht (hier: pytest)."""
    quelle = (WURZEL / "werkzeuge" / "bauen.py").read_text(encoding="utf-8")
    kaputt = tmp_path / "werkzeuge" / "bauen.py"
    kaputt.parent.mkdir()
    kaputt.write_text(re.sub(r"(?m)^(def starttest\(.*\).*:\n)", r"\1    import pytest\n", quelle, count=1),
                      encoding="utf-8")
    assert "    import pytest\n" in kaputt.read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="No module named 'pytest'"):
        ohne_pakete(kaputt, tmp_path / "lauf")


def test_bauen_mit_python_311_lesbar():
    """Debian 12 hat Python 3.11: keine Syntax, die erst 3.12 kennt (f-Strings mit denselben Anfuehrungszeichen
    innen wie aussen, PEP 701)."""
    quelle = (WURZEL / "werkzeuge" / "bauen.py").read_text(encoding="utf-8")
    ast.parse(quelle, feature_version=(3, 11))
    assert fstring_neue_syntax(quelle) == []


def test_fstring_pruefung_erkennt():
    """Die Pruefung oben schlaegt an, wo sie soll (sonst bestuende der Test auch ohne Wirkung)."""
    assert fstring_neue_syntax("x = f\"{'a'}\"\n") == []
    assert fstring_neue_syntax("x = f'{\"a\"}'\n") == []
    assert fstring_neue_syntax("d = {}\nx = f\"{d[\"a\"]}\"\n") == ['Zeile 2: x = f"{d["a"]}"']


# Job "distributionen" in bauen.yml, in bash nachgestellt: die run-Skripte laufen wie auf GitHub (bash --noprofile
# --norc -eo pipefail, Umgebung aus env und GITHUB_ENV, Schritte nach einem Fehlschlag nur mit if: always(),
# continue-on-error). Nachgebildet sind nur apt-get, dnf, rpm, ldd und python3 starttest (hinweise laeuft echt); im
# PATH stehen ausser ihnen nur Verweise auf die Grundwerkzeuge (WERKZEUGE_ECHT), so laesst sich auch ein Container
# ohne ldd nachstellen. Der Nachbau von Qt verlangt libxcb-cursor.so.0 wie docs/LIESMICH.txt. Unter Windows Git Bash.
BAUEN_YML = WURZEL / ".github" / "workflows" / "bauen.yml"
WERKZEUGE_ECHT = ("bash", "cat", "grep", "mkdir", "rm", "sed", "sleep", "sort", "tail", "tar", "touch", "xz")
CURSOR_PAKETE = ("libxcb-cursor0", "xcb-util-cursor")   # liefern libxcb-cursor.so.0 (Debian/Ubuntu bzw. Fedora)
NACHBAU = {
    "apt-get": r'''#!/bin/sh
echo "apt-get $*" >> "$SIM/aufrufe.log"
[ "$1" = update ] && exit 0
for p in "$@"; do                    # wie apt-get: ein unbekannter Name, und gar nichts wird installiert
  case "$p" in -*|install) continue ;; esac
  if grep -qx -- "$p" "$SIM/unbekannt.txt"; then echo "E: Unable to locate package $p" >&2; exit 100; fi
done
for p in "$@"; do case "$p" in -*|install) ;; *) touch "$SIM/installiert/$p" ;; esac; done
''',
    "dnf": r'''#!/bin/sh
echo "dnf $*" >> "$SIM/aufrufe.log"
case " $* " in *" --skip-unavailable "*) ueberspringen=ja ;; *) ueberspringen=nein ;; esac
for p in "$@"; do
  case "$p" in -*|install) continue ;; esac
  if grep -qx -- "$p" "$SIM/unbekannt.txt"; then
    echo "No match for argument: $p" >&2
    [ "$ueberspringen" = ja ] || exit 1
  fi
done
for p in "$@"; do
  case "$p" in -*|install) continue ;; esac
  grep -qx -- "$p" "$SIM/unbekannt.txt" || touch "$SIM/installiert/$p"
done
''',
    "rpm": r'''#!/bin/sh
for p in "$@"; do name="$p"; done
[ -e "$SIM/installiert/$name" ] && exit 0
echo "no package provides $name"
exit 1
''',
    "ldd": r'''#!/bin/sh
case "$1" in
  *libqxcb.so) [ -e "$SIM/installiert/libxcb-cursor0" ] || [ -e "$SIM/installiert/xcb-util-cursor" ] ||
               printf '\tlibxcb-cursor.so.0 => not found\n' ;;
esac
printf '\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f0000000000)\n'
''',
    "python3": r'''#!/bin/sh
if [ "$2" = starttest ]; then
  echo "starttest $3${LIBGL_ALWAYS_SOFTWARE:+ LIBGL_ALWAYS_SOFTWARE=$LIBGL_ALWAYS_SOFTWARE}${QT_XCB_GL_INTEGRATION:+ QT_XCB_GL_INTEGRATION=$QT_XCB_GL_INTEGRATION}${QT_QUICK_BACKEND:+ QT_QUICK_BACKEND=$QT_QUICK_BACKEND}" >> "$SIM/aufrufe.log"
  ok=false
  if [ -e "$SIM/installiert/libxcb-cursor0" ] || [ -e "$SIM/installiert/xcb-util-cursor" ]; then ok=true; fi
  if [ -n "$LIBGL_ALWAYS_SOFTWARE" ]; then ok=true; fi    # erfunden: so zeigt der Test, dass die Variante ankommt
  printf '{"ok": %s, "gui": "qt"}' "$ok" > starttest.json
  [ "$ok" = true ]
  exit
fi
exec "$ECHTES_PYTHON" "$@"
''',
}


def bash_ab_4(bash: str) -> bool:
    lauf = subprocess.run([bash, "--noprofile", "--norc", "-c", 'echo "${BASH_VERSINFO[0]}"'],
                          capture_output=True, text=True)
    return lauf.stdout.strip().isdigit() and int(lauf.stdout) >= 4


def git_bash() -> str | None:
    """bash fuer die Shell-Teile des Workflows, ab Version 4 wie in den Containern (globstar); macOS bringt nur 3.2
    mit, dann die von Homebrew. Unter Windows die von Git (System32\\bash.exe waere WSL)."""
    if sys.platform != "win32":
        kandidaten = [shutil.which("bash"), "/opt/homebrew/bin/bash", "/usr/local/bin/bash"]
        return next((k for k in kandidaten if k and Path(k).is_file() and bash_ab_4(k)), None)
    git = shutil.which("git")
    kandidaten = ([Path(git).resolve().parent.parent / "bin" / "bash.exe"] if git else []) + [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"]
    return next((str(k) for k in kandidaten if k.is_file()), None)


def bash_pfad(pfad: Path) -> str:
    """Pfad, wie bash ihn versteht (Git Bash: /c/...)."""
    pfad = Path(pfad).resolve()
    return "/" + pfad.drive[0].lower() + pfad.as_posix()[2:] if sys.platform == "win32" else str(pfad)


def skript(pfad: Path, text: str) -> None:
    pfad.write_text(text, encoding="utf-8", newline="\n")    # bash verschluckt sich an CRLF
    pfad.chmod(0o755)


def linux_paket(ziel: Path) -> None:
    """Das Linux-Archiv wie aus dem Build-Job (Inhalt erfunden): Starter, Qt-Plugin xcb, Qt WebEngine."""
    ziel.parent.mkdir(parents=True)
    with tarfile.open(ziel, "w:xz") as tar:
        for name in ("pdf2md", "_internal/PySide6/Qt/plugins/platforms/libqxcb.so",
                     "_internal/PySide6/Qt/lib/libQt6WebEngineCore.so.6"):
            info = tarfile.TarInfo(f"pdf2md-probe-linux-x86_64/pdf2md/{name}")
            info.size, info.mode = len(ELF), 0o755
            tar.addfile(info, io.BytesIO(ELF))


@pytest.fixture
def distributionen():
    yaml = pytest.importorskip("yaml", reason="braucht PyYAML")
    return yaml.safe_load(BAUEN_YML.read_text(encoding="utf-8"))["jobs"]["distributionen"]


def eintrag(job: dict, distro: str, **dazu) -> dict:
    """Matrix-Eintrag einer Distribution, dazu je Liste weitere (erfundene) Paketnamen."""
    gefunden = next(e for e in job["strategy"]["matrix"]["include"] if e["distro"] == distro)
    return {k: (f"{v} {dazu[k]}" if k in dazu else v) for k, v in gefunden.items()}


# Ueber BASH_ENV (liest jede nicht-interaktive bash), nicht per export -f: die Wrapper in sim/bin laufen mit /bin/sh,
# und dash (Ubuntu) verwirft exportierte bash-Funktionen (Variablenname BASH_FUNC_shopt%%) beim Weiterreichen.
OHNE_GLOBSTAR = r'''shopt() {   # wie bash 3.2 (macOS): globstar gibt es nicht, die uebrigen Schalter wirken trotzdem
  local a
  local weiter=()
  for a in "$@"; do
    if [ "$a" = globstar ]; then echo "bash: shopt: globstar: invalid shell option name" >&2; else weiter+=("$a"); fi
  done
  builtin shopt "${weiter[@]}"
  [ ${#weiter[@]} -eq $# ]
}
'''


def job_nachstellen(job: dict, matrix: dict, arbeit: Path, unbekannt=(), mit_ldd=True, ohne_globstar=False) -> dict:
    """Spielt die Schritte des Jobs fuer einen Matrix-Eintrag durch. unbekannt: Paketnamen, die apt-get/dnf nicht
    kennen; mit_ldd=False: Container ohne ldd; ohne_globstar=True: bash ohne globstar (wie 3.2)."""
    bash = git_bash()
    if not bash:
        pytest.skip("braucht bash ab 4 (unter Windows Git Bash, unter macOS die von Homebrew)")
    sim, ws = arbeit / "sim", arbeit / "ws"
    for ordner in (sim / "bin", sim / "installiert", ws):
        ordner.mkdir(parents=True)
    (sim / "unbekannt.txt").write_text("".join(f"{p}\n" for p in unbekannt), encoding="utf-8", newline="\n")
    (sim / "github_env").write_text("", encoding="utf-8")
    echt = subprocess.run([bash, "--noprofile", "--norc", "-c", "command -v " + " ".join(WERKZEUGE_ECHT)],
                          capture_output=True, text=True).stdout.split()
    if len(echt) != len(WERKZEUGE_ECHT):
        pytest.skip(f"Grundwerkzeuge fehlen in bash: {echt}")
    for name, ziel in zip(WERKZEUGE_ECHT, echt):
        skript(sim / "bin" / name, f'#!/bin/sh\nexec "{ziel}" "$@"\n')
    for name, text in NACHBAU.items():
        if name != "ldd" or mit_ldd:
            skript(sim / "bin" / name, text)
    umgebung = {"PATH": bash_pfad(sim / "bin"), "SIM": bash_pfad(sim), "GITHUB_ENV": bash_pfad(sim / "github_env"),
                "ECHTES_PYTHON": bash_pfad(Path(sys.executable))}
    if ohne_globstar:
        skript(sim / "ohne_globstar.sh", OHNE_GLOBSTAR)
        umgebung["BASH_ENV"] = bash_pfad(sim / "ohne_globstar.sh")
    for name, wert in job["env"].items():
        umgebung[name] = re.sub(r"\$\{\{\s*matrix\.(\w+)\s*\}\}", lambda m: matrix[m.group(1)], str(wert))
        assert "${{" not in umgebung[name], name
    assert job["defaults"]["run"]["shell"] == "bash"
    ausgabe, schritte, gescheitert = [], [], False
    for nummer, schritt in enumerate(job["steps"]):
        name = schritt.get("name") or schritt["uses"]
        if gescheitert and "always()" not in str(schritt.get("if", "")):
            schritte.append((name, "uebersprungen"))
            continue
        assert set(schritt.get("if", "always()").split()) == {"always()"}, schritt   # sonst hier nicht nachgestellt
        if schritt.get("uses", "").startswith("actions/checkout@"):
            (ws / "werkzeuge").mkdir()
            shutil.copy2(WURZEL / "werkzeuge" / "bauen.py", ws / "werkzeuge" / "bauen.py")
        elif schritt.get("uses", "").startswith("actions/download-artifact@"):
            linux_paket(ws / schritt["with"]["path"] / "pdf2md-probe-linux-x86_64.tar.xz")
        else:
            assert "${{" not in schritt["run"], name                  # Skripte lesen nur Umgebungsvariablen
            datei = sim / f"schritt{nummer}.sh"
            skript(datei, "".join(f"export {k}={shlex.quote(v)}\n" for k, v in umgebung.items())
                   + "unset DISPLAY\n" + schritt["run"])
            lauf = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", bash_pfad(datei)], cwd=ws,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            ausgabe.append(lauf.stdout + lauf.stderr)
            for zeile in (sim / "github_env").read_text(encoding="utf-8").splitlines():
                schluessel, _, wert = zeile.partition("=")
                umgebung[schluessel] = wert
            if lauf.returncode != 0 and not schritt.get("continue-on-error"):
                gescheitert = True
            schritte.append((name, lauf.returncode))
            continue
        schritte.append((name, 0))
    aufrufe = sim / "aufrufe.log"
    return {"ausgabe": "\n".join(ausgabe), "schritte": schritte, "gescheitert": gescheitert, "ws": ws,
            "installiert": {p.name for p in (sim / "installiert").iterdir()},
            "aufrufe": aufrufe.read_text(encoding="utf-8").splitlines() if aufrufe.exists() else []}


def stufen_ergebnisse(ausgabe: str, distro: str) -> list[tuple[str, str]]:
    return re.findall(rf"::notice title=Start-Test linux {re.escape(distro)} \(([^)]*)\)::(\S+)", ausgabe)


STUFEN = ["Grundstock", "Grundstock + Paket aus LIESMICH", "mit allen Qt-Paketen"]


class TestDistributionen:
    def test_aufbau(self, distributionen):
        """Werkzeuge im ersten Schritt ohne continue-on-error, Bibliotheken erst in den drei Stufen."""
        schritte = distributionen["steps"]
        assert schritte[0]["name"].startswith("Werkzeuge") and "continue-on-error" not in schritte[0]
        assert "$WERKZEUGE" in schritte[0]["run"] and "$GRUNDSTOCK" not in schritte[0]["run"]
        stufen = [s for s in schritte if s.get("name", "").startswith("Stufe ")]
        assert [s["run"] for s in stufen] == ["bash stufe.sh 1 $GRUNDSTOCK", "bash stufe.sh 2 $LIESMICH",
                                              "bash stufe.sh 3 $QT"]
        assert all(s.get("continue-on-error") for s in stufen)
        assert [distributionen["env"][f"STUFE_{n}"] for n in (1, 2, 3)] == STUFEN
        for e in distributionen["strategy"]["matrix"]["include"]:
            werkzeuge = e["werkzeuge"].split()
            assert {"python3", "tar", "util-linux"} <= set(werkzeuge), e["distro"]
            assert any("xvfb" in w.lower() for w in werkzeuge) and any("xauth" in w for w in werkzeuge)
            assert any(w.startswith("xz") for w in werkzeuge)
            assert not set(werkzeuge) & set((e["grundstock"] + " " + e["liesmich"] + " " + e["qt"]).split())

    def test_liesmich_pakete_wie_in_docs(self, distributionen):
        """Stufe 2 installiert genau die Pakete, die docs/LIESMICH.txt Nutzern nennt, und erst dort. Dazu gehoert
        libwayland-server: libQt6WebEngineCore braucht sie, PyInstaller liefert libwayland-* bewusst nicht mit, und
        Ubuntu 24.04 ohne Wayland-Desktop hat sie nicht (CI an 2635270: in allen drei Stufen "not found")."""
        liesmich = (WURZEL / "docs" / "LIESMICH.txt").read_text(encoding="utf-8")
        for e in distributionen["strategy"]["matrix"]["include"]:
            pakete = e["liesmich"].split()
            assert pakete == {"apt": ["libxcb-cursor0", "libwayland-server0"],
                              "dnf": ["xcb-util-cursor", "libwayland-server"]}[e["verwaltung"]], e["distro"]
            assert pakete[0] in CURSOR_PAKETE
            for paket in pakete:
                assert re.search(rf"(?<![\w-]){re.escape(paket)}(?![\w-])", liesmich), paket
                assert paket not in (e["werkzeuge"] + " " + e["grundstock"] + " " + e["qt"]).split()

    @pytest.mark.langsam                                 # je Nachbau einige Sekunden (viele kleine Prozesse)
    def test_unbekanntes_paket_kostet_nur_dieses(self, distributionen, tmp_path):
        """Frueher installierte apt-get die ganze Liste oder nichts: ein umbenanntes Paket (hier erfunden) verhinderte
        alles, auch python3 und xvfb, und der Job mass nichts. Jetzt fehlt nur dieses eine, mit Warnung."""
        matrix = eintrag(distributionen, "ubuntu-24.04", grundstock="libgibtsnicht0")
        lauf = job_nachstellen(distributionen, matrix, tmp_path, unbekannt=["libgibtsnicht0"])
        assert not lauf["gescheitert"], lauf["schritte"]
        assert ("::warning title=Paket fehlt linux ubuntu-24.04::libgibtsnicht0 (Grundstock): E: Unable to locate "
                "package libgibtsnicht0") in lauf["ausgabe"]
        alle = set((matrix["werkzeuge"] + " " + matrix["grundstock"] + " " + matrix["liesmich"] + " "
                    + matrix["qt"]).split())
        assert lauf["installiert"] == alle - {"libgibtsnicht0"}
        assert lauf["ausgabe"].count("::warning title=Paket fehlt") == 1

    @pytest.mark.langsam
    def test_drei_stufen_je_mit_ldd_und_start_test(self, distributionen, tmp_path):
        """Grundstock allein reicht nicht (libxcb-cursor fehlt), mit dem Paket aus LIESMICH startet das Programm."""
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "debian-12"), tmp_path)
        assert stufen_ergebnisse(lauf["ausgabe"], "debian-12") == [
            ("Grundstock", "FEHLER"), ("Grundstock + Paket aus LIESMICH", "OK"), ("mit allen Qt-Paketen", "OK")]
        ordner = "entpackt/pdf2md-probe-linux-x86_64"
        assert [a for a in lauf["aufrufe"] if a.startswith("starttest")] == [f"starttest {ordner}"] * 3
        assert ("::notice title=Fehlende Bibliotheken linux debian-12::Grundstock: %0Alibqxcb.so: libxcb-cursor.so.0 "
                "=> not found%0A%0AGrundstock + Paket aus LIESMICH: keine%0A%0Amit allen Qt-Paketen: keine"
                ) in lauf["ausgabe"]
        assert "Paket fehlt" not in lauf["ausgabe"] and "nicht gelaufen" not in lauf["ausgabe"]
        # jede Stufe installiert nur ihre Pakete, die Werkzeuge kamen vorher in einem Aufruf
        apt = [a for a in lauf["aufrufe"] if a.startswith("apt-get install")]
        assert apt[0].endswith(" " + eintrag(distributionen, "debian-12")["werkzeuge"])
        assert len(apt) == 1 + sum(len(eintrag(distributionen, "debian-12")[k].split())
                                   for k in ("grundstock", "liesmich", "qt"))

    @pytest.mark.langsam
    def test_fedora_mit_skip_unavailable(self, distributionen, tmp_path):
        """Fedora: Bibliotheken per dnf --skip-unavailable, was fehlt, meldet rpm; die Werkzeuge ohne den Schalter."""
        matrix = eintrag(distributionen, "fedora-41", qt="libgibtsnicht0")
        lauf = job_nachstellen(distributionen, matrix, tmp_path, unbekannt=["libgibtsnicht0"])
        dnf = [a for a in lauf["aufrufe"] if a.startswith("dnf ")]
        assert "--skip-unavailable" not in dnf[0] and dnf[0].endswith(" " + matrix["werkzeuge"])   # Werkzeuge
        assert len(dnf) == 4 and all("--skip-unavailable" in a for a in dnf[1:])
        assert ("::warning title=Paket fehlt linux fedora-41::libgibtsnicht0 (mit allen Qt-Paketen): nicht "
                "installiert") in lauf["ausgabe"]
        assert set(matrix["qt"].split()) - lauf["installiert"] == {"libgibtsnicht0"}
        assert stufen_ergebnisse(lauf["ausgabe"], "fedora-41") == [
            ("Grundstock", "FEHLER"), ("Grundstock + Paket aus LIESMICH", "OK"), ("mit allen Qt-Paketen", "OK")]

    def test_ohne_werkzeuge_scheitert_der_job(self, distributionen, tmp_path):
        """Fehlt ein Werkzeug (hier xvfb), scheitert der Job sichtbar; die Hinweise sagen, dass nichts lief."""
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "ubuntu-24.04"), tmp_path, unbekannt=["xvfb"])
        assert lauf["gescheitert"] and lauf["schritte"][0][1] != 0
        assert not [a for a in lauf["aufrufe"] if a.startswith("starttest")]
        assert stufen_ergebnisse(lauf["ausgabe"], "ubuntu-24.04") == [(s, "nicht") for s in STUFEN]   # gelaufen
        assert ("Fehlende Bibliotheken linux ubuntu-24.04::Grundstock: nicht geprüft%0A%0AGrundstock + Paket aus "
                "LIESMICH: nicht geprüft%0A%0Amit allen Qt-Paketen: nicht geprüft") in lauf["ausgabe"]

    @pytest.mark.langsam
    def test_ldd_fehlt_nicht_in_der_liste(self, distributionen, tmp_path):
        """Ohne ldd: eine Warnung am Lauf, die Liste sagt "nicht geprüft" (frueher stand "ldd fehlt im Container"
        als vermeintlich fehlende Bibliothek darin)."""
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "ubuntu-24.04"), tmp_path, mit_ldd=False)
        assert lauf["ausgabe"].count("::warning title=ldd fehlt linux ubuntu-24.04::") == 1
        assert not list(lauf["ws"].glob("fehlend-*.txt"))
        hinweis = next(z for z in lauf["ausgabe"].splitlines() if "title=Fehlende Bibliotheken" in z)
        assert hinweis.count("nicht geprüft") == 3 and "ldd" not in hinweis
        assert len(stufen_ergebnisse(lauf["ausgabe"], "ubuntu-24.04")) == 3

    @pytest.mark.langsam
    def test_varianten_nur_nach_fehlschlag(self, distributionen, tmp_path):
        """Ubuntu 24.04 und Fedora 41 brachen unter Xvfb mit "Could not initialize GLX" ab, Debian 12 nicht (CI an
        0f40f21). Scheitert Stufe 3, laeuft der Start-Test zur Diagnose noch mit Umgebungsvarianten, je mit eigenem
        Hinweis, dazu glxinfo. Der Job scheitert dadurch nicht."""
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "ubuntu-24.04"), tmp_path,
                               unbekannt=["libxcb-cursor0"])
        assert not lauf["gescheitert"], lauf["schritte"]
        ordner = "entpackt/pdf2md-probe-linux-x86_64"
        assert [a for a in lauf["aufrufe"] if a.startswith("starttest")] == [f"starttest {ordner}"] * 3 + [
            f"starttest {ordner} LIBGL_ALWAYS_SOFTWARE=1", f"starttest {ordner} QT_XCB_GL_INTEGRATION=xcb_egl",
            f"starttest {ordner} QT_XCB_GL_INTEGRATION=none", f"starttest {ordner} QT_QUICK_BACKEND=software"]
        varianten = re.findall(r"::notice title=Start-Test linux ubuntu-24\.04 \(Variante ([^)]*)\)::(\S+)",
                               lauf["ausgabe"])
        assert varianten == [("LIBGL_ALWAYS_SOFTWARE=1", "OK"), ("QT_XCB_GL_INTEGRATION=xcb_egl", "FEHLER"),
                             ("QT_XCB_GL_INTEGRATION=none", "FEHLER"),
                             ("QT_QUICK_BACKEND=software QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu", "FEHLER")]
        assert "::notice title=glxinfo linux ubuntu-24.04::glxinfo nicht verfügbar" in lauf["ausgabe"]
        assert [a for a in lauf["aufrufe"] if a.startswith("apt-get install") and a.endswith(" mesa-utils")]

    def test_keine_varianten_wenn_stufe_3_laeuft(self, distributionen, tmp_path):
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "debian-12"), tmp_path)
        assert "Variante" not in lauf["ausgabe"] and "glxinfo" not in lauf["ausgabe"]
        assert not [a for a in lauf["aufrufe"] if "mesa-utils" in a]

    @pytest.mark.langsam
    def test_ohne_globstar_nicht_geprueft(self, distributionen, tmp_path):
        """bash ohne globstar (macOS: 3.2) fand die Qt-Bibliotheken unter _internal/**/ nicht und meldete still
        "keine" fehlende Bibliothek (tests auf macos-latest, 7e25741). Jetzt: eine Warnung und "nicht geprüft"."""
        lauf = job_nachstellen(distributionen, eintrag(distributionen, "debian-12"), tmp_path, ohne_globstar=True)
        assert lauf["ausgabe"].count("::warning title=bash ohne globstar linux debian-12::") == 1
        hinweis = next(z for z in lauf["ausgabe"].splitlines() if "title=Fehlende Bibliotheken" in z)
        assert hinweis.count("nicht geprüft") == 3 and "keine" not in hinweis
        assert stufen_ergebnisse(lauf["ausgabe"], "debian-12") == [
            ("Grundstock", "FEHLER"), ("Grundstock + Paket aus LIESMICH", "OK"), ("mit allen Qt-Paketen", "OK")]


@pytest.mark.skipif(not sys.platform.startswith("linux") or not (shutil.which("objdump") and shutil.which("readelf")),
                    reason="braucht Linux mit binutils (tests.yml auf GitHub)")
def test_echtes_objdump_und_readelf(system, tmp_path):
    """Mit den echten Werkzeugen: objdump -T und readelf -V ergeben fuer dasselbe Programm dieselbe glibc."""
    programm = Path(sys.executable).resolve()
    objdump = subprocess.run(["objdump", "-T", str(programm)], capture_output=True, text=True).stdout
    readelf = subprocess.run(["readelf", "-V", "-W", str(programm)], capture_output=True, text=True).stdout
    glibc = hoechste(bauen.glibc_versionen(objdump))
    assert re.fullmatch(r"2\.\d+(\.\d+)?", glibc) and glibc == hoechste(bauen.glibc_versionen(readelf))
    system("linux")
    shutil.copy2(programm, tmp_path / "python")
    assert bauen.mindestversionen(tmp_path)["glibc_max"] == glibc


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("otool"),
                    reason="braucht macOS mit otool (tests.yml auf GitHub)")
def test_echtes_otool(system, tmp_path):
    """Mit dem echten otool: das laufende Python verlangt mindestens macOS 10.9 (eine plausible Zahl)."""
    system("darwin")
    shutil.copy2(Path(sys.executable).resolve(), tmp_path / "python")
    minos = bauen.mindestversionen(tmp_path)["macos_minos"]
    assert minos and bauen._versionsschluessel(minos) >= (10, 9), minos
