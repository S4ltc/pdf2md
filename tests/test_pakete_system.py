"""Was die Pakete vom System verlangen und wie sie ankommen (werkzeuge/bauen.py): gemessene Mindestversion (macOS:
minos aller Mach-O-Dateien, Linux: hoechste GLIBC-Symbolversion aller ELF-Dateien), Nachbearbeitung der macOS-App
(Info.plist, neue Signatur) und das Linux-Archiv mit einem Oberordner. otool, objdump, readelf und codesign sind
nachgebildet; nur die Tests am Ende laufen mit dem echten Werkzeug, wenn das System es hat (macOS bzw. Linux in
tests.yml auf GitHub)."""
import ast
import importlib.util
import io
import json
import plistlib
import re
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

    def codesign_nachbau(self, monkeypatch, app, signieren_ok=True):
        aufrufe = []

        def laufen(befehl, **kw):
            aufrufe.append(befehl)
            if befehl[:2] == ["codesign", "--force"]:      # signiert wird erst nach der Aenderung der Info.plist
                assert "NSDocumentsFolderUsageDescription" in self.info(app)
                return subprocess.CompletedProcess(befehl, 0 if signieren_ok else 1, "", "" if signieren_ok else
                                                   "pdf2md.app: code object is not signed at all")
            if befehl[:2] == ["codesign", "--verify"]:
                return subprocess.CompletedProcess(befehl, 0 if signieren_ok else 1, "",
                                                   "pdf2md.app: valid on disk" if signieren_ok else "invalid")
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
                           ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)]]
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
