"""Lizenztexte von Chromium und der Drittbestandteile von Qt fuer das Linux-Paket (werkzeuge/chromium_lizenzen.py)
und ihr Weg ins Paket (bauen.paket, bauen.lizenzbericht, drittlizenzen.einleitung).

Alles mit erfundenen Mini-Quellen: ein kleines tar.xz/tar.gz im tmp-Ordner nach dem Aufbau des Qt-Quellarchivs bzw.
des GitHub-Archivs, ein nachgebildetes Netz statt urllib. Der echte Lauf (rund 550 MB Quellarchiv) passiert nur auf
GitHub (bauen.yml, Linux)."""
import gzip
import http.client
import importlib.util
import io
import itertools
import json
import lzma
import re
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


def laden(name):
    spec = importlib.util.spec_from_file_location(name, WURZEL / "werkzeuge" / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


cl = laden("chromium_lizenzen")
bauen = laden("bauen")

WE = "6.140.0"
STAND = ("140.0.1234.56", "150.0.2345.67")
VERSIONEN = cl.Versionen(qt="6.12.0", webengine=WE, chromium=STAND[0], sicherheit=STAND[1], icu="73.2")
QT_ARCHIV = (f"https://download.qt.io/official_releases/qtwebengine/6.140/{WE}/"
             f"qtwebengine-everywhere-src-{WE}.tar.xz")
QTBASE = "https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz"
ICU = "https://raw.githubusercontent.com/unicode-org/icu/release-73-2/icu4c/LICENSE"
CHROMIUM_TEXT = "// Copyright 2015 The Chromium Authors\n//\n// Redistribution erlaubt (erfundener Probetext).\n"
ALPHA_TEXT = "Copyright 2020 Erika Muster\n\nPermission is hereby granted (Probetext Alpha)."

MINI_LICENSES_PY = '''
import os
_REPOSITORY_ROOT = os.path.abspath(os.path.dirname(__file__))
METADATA_FILE_NAMES = frozenset({"README.chromium"})
PRUNE_PATHS = set([
    os.path.join('third_party', 'llvm'),
])
VCS_METADATA_DIRS = ('.svn', '.git')
PRUNE_DIRS = VCS_METADATA_DIRS + ('layout_tests', )
ADDITIONAL_PATHS = (
    os.path.join('v8'),
    os.path.join('native_client'),
)
SPECIAL_CASES = {
    os.path.join('third_party', 'blink'): {
        "Name": "WebKit",
        "URL": "https://webkit.example.org/",
        "Shipped": "yes",
        "License": "BSD and LGPL v2",
        "License File": ["//third_party/blink/LICENSE_FOR_ABOUT_CREDITS"],
    },
    os.path.join('native_client'): {
        "Name": "native client",
        "URL": "https://nacl.example.org",
        "Shipped": "yes",
        "License": "BSD",
        "License File": ["//native_client/LICENSE"],
    },
}
PATTERN_DEPENDENCY_DIVIDER = re.compile(r"^-{20} DEPENDENCY DIVIDER -{20}$")
PRUNE_PATHS.update([
    os.path.join('third_party', 'entfernt'),
])
'''


def readme(name, lizenzdatei=None, shipped="yes", extra=""):
    zeilen = [f"Name: {name}", f"URL: https://{name.lower()}.example.org", "License: MIT"]
    if lizenzdatei:
        zeilen.append(f"License File: {lizenzdatei}")
    if shipped:
        zeilen.append(f"Shipped: {shipped}")
    return "\n".join(zeilen) + "\n" + extra + "\nDescription:\nErfundener Bestandteil fuer Tests.\n"


def chromium_dateien() -> dict[str, str]:
    """Erfundener Chromium-Baum (Pfade relativ zu src/3rdparty/chromium)."""
    teiler = "-" * 20 + " DEPENDENCY DIVIDER " + "-" * 20
    return {
        "LICENSE": CHROMIUM_TEXT,
        "tools/licenses/licenses.py": MINI_LICENSES_PY,
        "third_party/alpha/README.chromium": readme("Alpha", "LICENSE"),
        "third_party/alpha/LICENSE": ALPHA_TEXT,
        "third_party/beta/README.chromium": readme("Beta", "LICENSE", shipped="no"),
        "third_party/beta/LICENSE": "Beta-Text, wird nicht ausgeliefert",
        # gleicher Text wie Alpha, nur mit Windows-Zeilenenden und Leerraum am Zeilenende: einmal ausgeben
        "third_party/gamma/README.chromium": readme("Gamma", "LICENSE"),
        "third_party/gamma/LICENSE": ALPHA_TEXT.replace("\n", "  \r\n") + "\r\n",
        # Lizenzdatei ohne Lizenznamen: erst im zweiten Durchgang geholt
        "third_party/delta/README.chromium": readme("Delta", "src/nutzungsbedingungen.txt"),
        "third_party/delta/src/nutzungsbedingungen.txt": "Delta-Bedingungen (Probetext)",
        "third_party/epsilon/README.chromium": readme("Epsilon", "LICENSE"),        # Datei fehlt in der Quelle
        "third_party/zeta/README.chromium": (readme("Zeta-Eins", "LICENSE-A") + teiler + "\n"
                                             + readme("Zeta-Zwei", "NOT_SHIPPED", shipped="")),
        "third_party/zeta/LICENSE-A": "Zeta-A-Text (Probetext)",
        "third_party/eta/README.chromium": readme("Eta", "//third_party/alpha/LICENSE"),
        "third_party/theta/README.chromium": readme("Theta", "LICENSE"),            # nur COPYING vorhanden
        "third_party/theta/COPYING": "Theta-COPYING (Probetext)",
        "third_party/iota/README.chromium": readme("Iota", "LICENSE"),              # LICENSE ist eine Verknuepfung
        "third_party/iota/docs/rechte.txt": "Iota-Rechte (Probetext)",
        "third_party/kappa/README.chromium": readme("Kappa", shipped="", extra="shipped in chromium: no\n"),
        "third_party/kappa/LICENSE": "Kappa-Text, wird nicht ausgeliefert",
        "third_party/blink/LICENSE_FOR_ABOUT_CREDITS": "WebKit-Text (Probetext)",
        "third_party/llvm/README.chromium": readme("LLVM", "LICENSE"),              # PRUNE_PATHS
        "third_party/llvm/LICENSE": "LLVM-Text",
        "third_party/entfernt/README.chromium": readme("Entfernt", "LICENSE"),      # PRUNE_PATHS.update
        "third_party/entfernt/LICENSE": "Entfernt-Text",
        "v8/README.chromium": readme("V8-Probe", "LICENSE.v8"),                    # ADDITIONAL_PATHS
        "v8/LICENSE.v8": "V8-Text (Probetext)",
        "v8/third_party/lambda/README.chromium": readme("Lambda", "LICENSE"),      # unter ADDITIONAL: nicht gesucht
        "v8/third_party/lambda/LICENSE": "Lambda-Text",
        "chrome/third_party/my/README.chromium": readme("My", "LICENSE"),          # third_party tiefer im Baum
        "chrome/third_party/my/LICENSE": "My-Text (Probetext)",
        "base/README.chromium": readme("Kein-Drittteil", "LICENSE"),               # kein third_party-Verzeichnis
        "base/LICENSE": "Base-Text",
    }


def tar_bauen(datei: Path, inhalte: dict[str, str | bytes], verweise: dict[str, str] | None = None,
              art: str = "xz") -> bytes:
    with tarfile.open(datei, f"w:{art}") as tar:
        for name, inhalt in inhalte.items():
            daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
            info = tarfile.TarInfo(name)
            info.size = len(daten)
            tar.addfile(info, io.BytesIO(daten))
        for name, ziel in (verweise or {}).items():
            info = tarfile.TarInfo(name)
            info.type, info.linkname = tarfile.SYMTYPE, ziel
            tar.addfile(info)
    return datei.read_bytes()


def qt_quellarchiv(tmp_path, chromium_version=STAND) -> bytes:
    """Wie qtwebengine-everywhere-src-<ver>.tar.xz: CHROMIUM_VERSION vorn, Chromium unter src/3rdparty/chromium."""
    oben = f"qtwebengine-everywhere-src-{WE}"
    inhalte = {f"{oben}/CHROMIUM_VERSION":
               f"Based on Chromium version:                        {chromium_version[0]}\n"
               f"Patched with security patches up to Chromium version: {chromium_version[1]}\n",
               f"{oben}/src/core/LICENSE": "Qt-eigener Text, gehoert nicht zu Chromium"}
    inhalte |= {f"{oben}/src/3rdparty/chromium/{p}": t for p, t in chromium_dateien().items()}
    verweise = {f"{oben}/src/3rdparty/chromium/third_party/iota/LICENSE": "docs/rechte.txt"}
    return tar_bauen(tmp_path / "qtwebengine.tar.xz", inhalte, verweise)


def qtbase_archiv(tmp_path) -> bytes:
    oben = "qtbase-everywhere-src-6.12.0"
    return tar_bauen(tmp_path / "qtbase.tar.xz", {
        f"{oben}/LICENSES/Zlib.txt": "Zlib-Lizenztext (Probetext)",
        f"{oben}/LICENSES/MIT.txt": "MIT-Lizenztext (Probetext)",
        # Qt erlaubt Zeilenumbrueche in Texten (kein strenges JSON)
        f"{oben}/src/3rdparty/beispiel/qt_attribution.json": json.dumps({
            "Id": "beispiel", "Name": "Beispielbibliothek", "Homepage": "https://beispiel.example.org",
            "License": "zlib License", "LicenseId": "Zlib", "LicenseFile": "LICENSE",
            "Copyright": "Copyright (C) 2001 Erika Muster"}).replace("Beispielbibliothek", "Beispiel\nbibliothek"),
        f"{oben}/src/3rdparty/beispiel/LICENSE": "Copyright (C) 2001 Erika Muster\nBeispiel-Lizenz (Probetext)",
        f"{oben}/src/gui/text/qt_attribution.json": json.dumps([
            {"Id": "daten", "Name": "Beispieldaten", "License": "MIT License", "LicenseId": "MIT",
             "Copyright": ["Copyright (C) 2002 Max Muster", "Copyright (C) 2003 Erika Muster"]},
            {"Id": "rechte", "Name": "Rechte aus Datei", "License": "Eigene", "LicenseFile": "BEDINGUNGEN.txt",
             "CopyrightFile": "RECHTE.txt"}]),
        f"{oben}/src/gui/text/BEDINGUNGEN.txt": "Bedingungen (Probetext)",
        f"{oben}/src/gui/text/RECHTE.txt": "Copyright (C) 2004 Max Muster",
        f"{oben}/src/3rdparty/ohne/qt_attribution.json": json.dumps({"Id": "ohne", "Name": "Ohne Text",
                                                                      "License": "Unbekannt"}),
        f"{oben}/examples/demo/qt_attribution.json": json.dumps({"Id": "demo", "Name": "Nur Beispiel",
                                                                  "LicenseFile": "LICENSE"}),
        f"{oben}/examples/demo/LICENSE": "Demo",
        f"{oben}/tests/auto/qt_attribution.json": json.dumps({"Id": "test", "Name": "Nur Test"}),
    })


class Antwort(io.BytesIO):
    def __init__(self, daten: bytes, url: str):
        super().__init__(daten)
        self.status, self.url = 200, url

    def geturl(self):
        return self.url


class AbbruchBeimLesen(Antwort):
    """Antwort, deren Verbindung beim Lesen abbricht (Kopf kam an, Inhalt nicht)."""

    def __init__(self):
        super().__init__(b"", "")

    def read(self, *argumente):
        raise http.client.IncompleteRead(b"teil")


class NetzNachbau:
    """Statt urllib: Adresse -> Inhalt (bytes/str), Ausnahme (wird geworfen), AbbruchBeimLesen oder Liste (je Abruf
    das naechste)."""

    def __init__(self, seiten):
        self.seiten, self.anfragen = dict(seiten), []

    def open(self, anfrage, timeout=None):
        url, methode = anfrage.full_url, anfrage.get_method()
        self.anfragen.append((methode, url, dict(anfrage.header_items())))
        inhalt = self.seiten.get(url)
        if isinstance(inhalt, list):
            inhalt = inhalt.pop(0) if len(inhalt) > 1 else inhalt[0]
        if inhalt is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if isinstance(inhalt, Exception):
            raise inhalt
        if isinstance(inhalt, AbbruchBeimLesen):
            return AbbruchBeimLesen()                       # je Abruf eine neue (die alte ist geschlossen)
        daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
        return Antwort(b"" if methode == "HEAD" else daten, url)

    def abrufe(self, url, methode="GET"):
        return sum(1 for m, u, _ in self.anfragen if u == url and m == methode)


@pytest.fixture
def netz(monkeypatch):
    def setzen(seiten):
        nachbau = NetzNachbau(seiten)
        monkeypatch.setattr(cl, "OEFFNER", nachbau)
        return nachbau
    monkeypatch.setattr(cl, "WARTEN", (0, 0))
    monkeypatch.setattr(cl, "QT_MODULE", ("qtbase",))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return setzen


def standard_seiten(tmp_path):
    return {QT_ARCHIV: qt_quellarchiv(tmp_path), QTBASE: qtbase_archiv(tmp_path),
            ICU: "UNICODE LICENSE V3 (Probetext ICU)"}


class TestRegeln:
    def test_aus_licenses_py_ohne_ausfuehren(self):
        """SPECIAL_CASES, PRUNE_PATHS (samt .update), ADDITIONAL_PATHS und PRUNE_DIRS kommen aus der Quelle selbst;
        alles andere (os.path.abspath, re.compile) wird uebergangen."""
        regeln = cl.regeln_lesen(MINI_LICENSES_PY)
        assert regeln.sonderfaelle["third_party/blink"]["License File"] == ["//third_party/blink/LICENSE_FOR_ABOUT_CREDITS"]
        assert regeln.ausgelassen == {"third_party/llvm", "third_party/entfernt"}
        assert regeln.zusaetzlich == {"v8", "native_client"}
        assert regeln.metadaten == ("README.chromium",)
        assert regeln.ohne_abstieg == (".svn", ".git", "layout_tests")

    def test_unlesbar_bricht_ab(self):
        with pytest.raises(cl.Abbruch, match="SPECIAL_CASES"):
            cl.regeln_lesen("PRUNE_PATHS = set()\nADDITIONAL_PATHS = ()\n")
        with pytest.raises(cl.Abbruch, match="nicht lesbar"):
            cl.regeln_lesen("def (:\n")

    def test_metadaten_wie_licenses_py(self):
        teiler = "-" * 20 + " DEPENDENCY DIVIDER " + "-" * 20
        text = ("name: Eins\nURL: https://eins.example.org\nLicense File: LICENSE, src/COPYING\nShipped: yes\n"
                "Name: Doppelt\nDescription:\nName:ohne Leerzeichen\n" + teiler + "\nName: Zwei\n"
                "Shipped in Chromium: no\n")
        assert cl.metadaten_lesen(text) == [
            {"Name": "Eins", "URL": "https://eins.example.org", "License File": ["LICENSE", "src/COPYING"],
             "Shipped": "yes"},
            {"Name": "Zwei", "Shipped in Chromium": "no"}]


class TestChromiumBaum:
    def baum(self, tmp_path):
        baum = cl.Baum()
        cl.durchgehen(io.BytesIO(qt_quellarchiv(tmp_path)), cl.chromium_pfad, lambda p, g: True, baum)
        return baum

    def test_nur_ausgelieferte_bestandteile(self, tmp_path):
        liste, _ = cl.chromium_auswerten(self.baum(tmp_path))
        namen = [b.name for b in liste]
        assert namen[0] == "The Chromium Project" and "The Chromium Authors" in liste[0].text
        assert {"Alpha", "Gamma", "Delta", "Epsilon", "Zeta-Eins", "Eta", "Theta", "Iota", "WebKit", "V8-Probe",
                "My"} == set(namen[1:])
        # Shipped: no, NOT_SHIPPED, Alias "Shipped in Chromium", PRUNE_PATHS, unter ADDITIONAL_PATHS, ohne
        # third_party, Sonderfall ohne Lizenzdatei (native_client gibt es nicht)
        for weg in ("Beta", "Zeta-Zwei", "Kappa", "LLVM", "Entfernt", "Lambda", "Kein-Drittteil", "native client"):
            assert weg not in namen

    def test_lizenzdateien_wie_licenses_py(self, tmp_path):
        liste, noetig = cl.chromium_auswerten(self.baum(tmp_path))
        je_name = {b.name: b for b in liste}
        assert je_name["Eta"].text == ALPHA_TEXT                         # //pfad: relativ zur Wurzel
        assert je_name["Theta"].text == "Theta-COPYING (Probetext)"      # COPYING, wenn LICENSE fehlt
        assert je_name["Iota"].text == "Iota-Rechte (Probetext)"         # Verknuepfung aufgeloest
        assert je_name["Epsilon"].text is None and je_name["Epsilon"].erwartet == ["third_party/epsilon/LICENSE"]
        assert je_name["WebKit"].fundorte == ["chromium/third_party/blink"]
        assert "third_party/delta/src/nutzungsbedingungen.txt" in noetig

    def test_lizenzdateien_im_ersten_durchgang(self):
        """Echtes Beispiel (Chromium 140): ffmpeg nennt CREDITS.chromium als Lizenzdatei, und die steht im Archiv vor
        dem README.chromium; ohne "credits" im Namensmuster kostete das einen weiteren Durchgang."""
        assert cl.chromium_behalten("third_party/ffmpeg/CREDITS.chromium", 3000)
        assert cl.chromium_behalten("third_party/x/LICENSE.txt", 3000)
        assert cl.chromium_behalten("tools/licenses/licenses.py", 60000)
        assert not cl.chromium_behalten("third_party/x/LICENSE.png", 3000)
        assert not cl.chromium_behalten("third_party/x/LICENSE", cl.GROESSTE_DATEI + 1)
        assert not cl.chromium_behalten("third_party/x/quelle.c", 3000)

    def test_pfade_aus_beiden_archivformen(self):
        assert cl.chromium_pfad("qtwebengine-everywhere-src-6.140.0/src/3rdparty/chromium/third_party/a/LICENSE") \
            == "third_party/a/LICENSE"
        assert cl.chromium_pfad("qtwebengine-chromium-0123abc/chromium/third_party/a/LICENSE") == "third_party/a/LICENSE"
        assert cl.chromium_pfad("qtwebengine-everywhere-src-6.140.0/src/core/LICENSE") is None
        assert cl.chromium_pfad("qtwebengine-chromium-0123abc/gn/LICENSE") is None


class TestErzeugen:
    def test_ganzer_lauf(self, tmp_path, netz):
        seiten = netz(standard_seiten(tmp_path))
        ziel = tmp_path / "CHROMIUM-LIZENZEN.txt"
        text = cl.erzeugen(ziel, VERSIONEN)
        assert ziel.read_bytes().decode("utf-8") == text and b"\r\n" not in ziel.read_bytes()
        kopf = text.split("\n\nÜbersicht", 1)[0]
        assert "Qt WebEngine: 6.140.0" in kopf and f"Chromium: {STAND[0]}, Sicherheitskorrekturen bis Chromium " \
            f"{STAND[1]}" in kopf and "ICU (von Qt): 73.2" in kopf
        assert f"Quelle Chromium: {QT_ARCHIV}; CHROMIUM_VERSION stimmt mit der Bibliothek überein" in kopf
        assert f"Quelle Qt (qtbase): {QTBASE}" in kopf and f"Quelle ICU: {ICU}" in kopf
        # 12 Chromium (mit dem Projekt selbst), 4 Qt, 1 ICU; ohne Text: Epsilon und Qts "Ohne Text"
        assert "Bestandteile: 17 (Chromium 12, Qt 4, ICU 1)" in kopf and "Ohne Lizenztext: 2" in kopf
        # gleicher Text (Alpha, Gamma mit CRLF, Eta ueber //-Pfad) genau einmal, mit allen drei Bestandteilen
        assert text.count("Permission is hereby granted (Probetext Alpha)") == 1
        gruppe = text.split("Permission is hereby granted (Probetext Alpha)")[0].rsplit("gilt für:", 1)[1]
        assert all(f"Chromium: {n} – " in gruppe for n in ("Alpha", "Gamma", "Eta"))
        for weg in ("Beta-Text", "Kappa-Text", "LLVM-Text", "Lambda-Text", "Demo", "Nur Test", "Zeta-Zwei"):
            assert weg not in text
        assert "Delta-Bedingungen" in text and "Iota-Rechte" in text and "Theta-COPYING" in text
        ohne = text.split("Ohne Lizenztext in der Quelle", 1)[1]
        assert "Epsilon" in ohne and "gesucht: third_party/epsilon/LICENSE" in ohne
        assert "Ohne Text" in ohne and "(keine Lizenzdatei angegeben)" in ohne
        # Delta (src/nutzungsbedingungen.txt steht hinter dem README) kommt im ersten Durchgang mit; einen zweiten
        # braucht nur das Ziel von Iota, das im Archiv vor der Verknuepfung steht
        assert seiten.abrufe(QT_ARCHIV) == 3                # Vorschau (CHROMIUM_VERSION) + 2 Durchgaenge
        # Bedingungen/Rechte ohne Lizenznamen stehen hinter ihrer qt_attribution.json: ein Durchgang reicht
        assert seiten.abrufe(QTBASE) == 1

    def test_qt_attribution(self, tmp_path, netz):
        netz({QTBASE: qtbase_archiv(tmp_path)})
        url, liste = cl.qt_lesen("qtbase", "6.12.0")
        je_name = {b.name: b for b in liste}
        assert url == QTBASE and set(je_name) == {"Beispiel\nbibliothek", "Beispieldaten", "Rechte aus Datei",
                                                  "Ohne Text"}
        # Copyright steht schon im Text: nicht doppelt
        assert je_name["Beispiel\nbibliothek"].text == "Copyright (C) 2001 Erika Muster\nBeispiel-Lizenz (Probetext)"
        # ohne LicenseFile: Text zu LicenseId aus LICENSES/, Copyright aus der JSON-Datei davor
        assert je_name["Beispieldaten"].text == ("Copyright (C) 2002 Max Muster\nCopyright (C) 2003 Erika Muster"
                                                 "\n\nMIT-Lizenztext (Probetext)")
        assert je_name["Rechte aus Datei"].text == "Copyright (C) 2004 Max Muster\n\nBedingungen (Probetext)"
        assert je_name["Beispieldaten"].fundorte == ["qtbase/src/gui/text"]

    def test_qt_ersatz_github(self, tmp_path, netz):
        """Fehlt das Archiv auf download.qt.io, kommt das Modul vom GitHub-Tag genau dieser Version."""
        url = "https://codeload.github.com/qt/qtbase/tar.gz/refs/tags/v6.12.0"
        netz({url: qtbase_archiv(tmp_path)})
        assert cl.qt_lesen("qtbase", "6.12.0")[0] == url

    def test_qt_fehlt_bricht_ab(self, netz):
        netz({})
        with pytest.raises(cl.Abbruch, match="kein Quellarchiv von qtbase 6.12.0"):
            cl.qt_lesen("qtbase", "6.12.0")

    def test_icu_tag_der_version(self, netz):
        netz({ICU: "ICU-Text", "https://raw.githubusercontent.com/unicode-org/icu/release-74-1/icu4c/LICENSE": "74"})
        assert cl.icu_lesen("73.2")[0] == ICU
        assert cl.icu_lesen("74")[0].endswith("/release-74-1/icu4c/LICENSE")       # nur Hauptversion bekannt
        with pytest.raises(cl.Abbruch, match="ICU 75"):
            cl.icu_lesen("75.1")

    def test_icu_version_aus_dateiname(self, tmp_path):
        """Laesst sich die Bibliothek nicht laden, bleibt die Hauptversion aus dem Dateinamen."""
        assert cl.icu_version(tmp_path) is None
        (tmp_path / "libicuuc.so.73").write_bytes(b"keine Bibliothek")
        assert cl.icu_version(tmp_path) == "73"


class TestQuelle:
    def github(self, tmp_path, ref, stand, sha="0123abcd"):
        archiv = tar_bauen(tmp_path / "gh.tar.gz", {f"qtwebengine-chromium-{sha}/chromium/{p}": t
                                                    for p, t in chromium_dateien().items()}, art="gz")
        return {f"https://raw.githubusercontent.com/qt/qtwebengine/{ref}/CHROMIUM_VERSION":
                f"Based on Chromium version: {stand[0]}\nPatched with security patches up to Chromium version: "
                f"{stand[1]}\n",
                f"https://api.github.com/repos/qt/qtwebengine/contents/src/3rdparty?ref={ref}":
                json.dumps({"type": "submodule", "sha": sha}),
                f"https://codeload.github.com/qt/qtwebengine-chromium/tar.gz/{sha}": archiv}

    def test_nur_genau_passender_stand(self, tmp_path, netz):
        """Das Quellarchiv hat einen anderen Sicherheitsstand als die Bibliothek: dann zaehlt der Zweig auf GitHub,
        dessen CHROMIUM_VERSION genau passt, nicht das naechstbeste Archiv."""
        seiten = {QT_ARCHIV: qt_quellarchiv(tmp_path, (STAND[0], "149.0.1.1")), QTBASE: qtbase_archiv(tmp_path),
                  ICU: "ICU"}
        seiten |= self.github(tmp_path, f"v{WE}", (STAND[0], "149.0.1.1"), sha="aaaa")
        seiten |= self.github(tmp_path, WE, STAND, sha="bbbb")
        netz(seiten)
        beschreibung, archiv = cl.chromium_quelle(VERSIONEN)
        assert beschreibung == f"github.com/qt/qtwebengine {WE}"
        assert archiv == "https://codeload.github.com/qt/qtwebengine-chromium/tar.gz/bbbb"
        text = cl.erzeugen(tmp_path / "aus.txt", VERSIONEN)
        assert f"Quelle Chromium: github.com/qt/qtwebengine {WE} ({archiv})" in text
        assert "Bestandteile: 17 (Chromium 12" in text

    def test_frueherer_stand_aus_dem_verlauf(self, tmp_path, netz):
        commits = f"https://api.github.com/repos/qt/qtwebengine/commits?sha={WE}&path=CHROMIUM_VERSION&per_page=15"
        seiten = {commits: json.dumps([{"sha": "c2"}, {"sha": "c1"}])}
        seiten |= self.github(tmp_path, WE, (STAND[0], "151.0.0.1"))
        seiten |= self.github(tmp_path, "c2", (STAND[0], "151.0.0.1"))
        seiten |= self.github(tmp_path, "c1", STAND, sha="cccc")
        netz(seiten)
        assert cl.chromium_quelle(VERSIONEN) == ("github.com/qt/qtwebengine c1",
                                                 "https://codeload.github.com/qt/qtwebengine-chromium/tar.gz/cccc")

    def test_reihenfolge_der_quellen(self):
        """Offizielles Quellarchiv zuerst (Ablage der fertigen Fassung 6.140.0 noch unbekannt: mit und ohne X.Y, bis
        Qt 6.11 unter qt/.../submodules), dann der Tag, der Release-Kandidat, der Zweig; der Verlauf (Netz) danach."""
        namen = [k.beschreibung for k in itertools.islice(cl.chromium_kandidaten(VERSIONEN), 9)]
        q = "https://download.qt.io"
        datei = f"qtwebengine-everywhere-src-{WE}.tar.xz"
        assert namen == [f"{q}/official_releases/qtwebengine/6.140/{WE}/{datei}",
                         f"{q}/official_releases/qtwebengine/{WE}/{datei}",
                         f"{q}/archive/qtwebengine/6.140/{WE}/{datei}", f"{q}/archive/qtwebengine/{WE}/{datei}",
                         f"{q}/official_releases/qt/6.140/{WE}/submodules/{datei}",
                         f"{q}/archive/qt/6.140/{WE}/submodules/{datei}",
                         f"github.com/qt/qtwebengine v{WE}",
                         f"{q}/development_releases/qtwebengine/{WE}-rc/qtwebengine-everywhere-src-{WE}-rc.tar.xz",
                         f"github.com/qt/qtwebengine {WE}"]

    def test_release_kandidat_wenn_die_fassung_fehlt(self, tmp_path, netz):
        """Am 2026-10-10 gab es Qt WebEngine 6.140.0 auf download.qt.io nur als Release-Kandidat: passt dessen
        CHROMIUM_VERSION genau, ist er die Quelle (offizielles Archiv statt GitHub-Spiegel)."""
        rc = (f"https://download.qt.io/development_releases/qtwebengine/{WE}-rc/"
              f"qtwebengine-everywhere-src-{WE}-rc.tar.xz")
        seiten = netz({rc: qt_quellarchiv(tmp_path)} | self.github(tmp_path, WE, STAND))
        assert cl.chromium_quelle(VERSIONEN) == (rc, rc)
        assert seiten.abrufe(f"https://raw.githubusercontent.com/qt/qtwebengine/{WE}/CHROMIUM_VERSION") == 0

    def test_keine_passende_quelle(self, tmp_path, netz, monkeypatch, capsys):
        seiten = netz({QT_ARCHIV: qt_quellarchiv(tmp_path, ("139.0.0.1", "149.0.0.1")),
                       "https://api.github.com/repos/qt/qtwebengine/commits?sha=6.140&path=CHROMIUM_VERSION"
                       "&per_page=15": urllib.error.URLError("Netz weg")})
        monkeypatch.setattr(cl, "versionen", lambda: VERSIONEN)
        assert cl.main([str(tmp_path / "aus.txt")]) == 1
        fehler = capsys.readouterr().err
        assert "keine Quelle mit genau dem Chromium-Stand" in fehler
        assert f"{QT_ARCHIV}: Chromium 139.0.0.1, Sicherheitsstand 149.0.0.1" in fehler
        assert f"github.com/qt/qtwebengine v{WE}: gibt es nicht" in fehler
        assert "weitere Quellen nicht ermittelbar" in fehler and "Netz weg" in fehler
        assert not (tmp_path / "aus.txt").exists()
        assert seiten.abrufe(QT_ARCHIV) == 1                # nur die Vorschau, kein ganzer Durchgang


class TestNetz:
    def test_token_nur_fuer_die_github_api(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "geheim-123")
        assert cl.anfrage("https://api.github.com/repos/qt/qtwebengine").get_header("Authorization") == \
            "Bearer geheim-123"
        for url in (QT_ARCHIV, "https://raw.githubusercontent.com/qt/qtwebengine/x/CHROMIUM_VERSION",
                    "https://codeload.github.com/qt/qtwebengine-chromium/tar.gz/x",
                    "https://api.github.com.example.org/x"):
            assert cl.anfrage(url).get_header("Authorization") is None

    def test_umleitung_verliert_das_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "geheim-123")
        alt = cl.anfrage("https://api.github.com/repos/qt/qtwebengine/contents/x")
        umleitung = cl._Umleitung()
        neu = umleitung.redirect_request(alt, None, 302, "Found", {}, "https://anderswo.example.org/x")
        assert neu.get_header("Authorization") is None and neu.get_header("User-agent") == "pdf2md/1.0"
        bleibt = umleitung.redirect_request(alt, None, 301, "Moved", {}, "https://api.github.com/repositories/1")
        assert bleibt.get_header("Authorization") == "Bearer geheim-123"

    def test_wiederholung_und_404(self, netz):
        url = "https://download.qt.io/probe.txt"
        seiten = netz({url: [urllib.error.URLError("kurz weg"), "da"]})
        assert cl.text_holen(url) == "da" and seiten.abrufe(url) == 2
        assert cl.text_holen("https://download.qt.io/gibt-es-nicht") is None
        assert seiten.abrufe("https://download.qt.io/gibt-es-nicht") == 1        # 404 wird nicht wiederholt
        netz({url: urllib.error.HTTPError(url, 503, "weg", {}, None)})
        with pytest.raises(cl.Abbruch, match="503"):
            cl.text_holen(url)

    def test_abbruch_beim_lesen_wird_wiederholt(self, netz):
        """Regression: brach die Verbindung erst beim Lesen ab (IncompleteRead), endete das Werkzeug mit einem
        Python-Fehler statt einem neuen Versuch bzw. einer klaren Meldung."""
        url = "https://raw.githubusercontent.com/qt/qtwebengine/x/CHROMIUM_VERSION"
        seiten = netz({url: [AbbruchBeimLesen(), "Based on Chromium version: 1.2.3.4"]})
        assert cl.text_holen(url) == "Based on Chromium version: 1.2.3.4" and seiten.abrufe(url) == 2
        netz({url: AbbruchBeimLesen()})
        with pytest.raises(cl.Abbruch, match="IncompleteRead"):
            cl.text_holen(url)

    def test_abgebrochenes_archiv_wird_neu_gelesen(self, tmp_path, netz):
        """Regression: tarfile "r|*" nahm ein halbes Archiv still als ganzes (abrufe blieb 1, Lizenztexte fehlten)."""
        ganz = qtbase_archiv(tmp_path)
        seiten = netz({QTBASE: [ganz[: len(ganz) // 2], ganz]})
        baum = cl.Baum()
        cl.archiv_lesen(QTBASE, cl.modulpfad, cl.qt_behalten, baum)
        assert seiten.abrufe(QTBASE) == 2 and "src/3rdparty/beispiel/LICENSE" in baum.dateien

    def test_immer_abgebrochen_bricht_ab(self, tmp_path, netz):
        ganz = qtbase_archiv(tmp_path)
        seiten = netz({QTBASE: ganz[:-8]})
        with pytest.raises(cl.Abbruch, match="Archiv nicht lesbar.*vorzeitig"):
            cl.archiv_lesen(QTBASE, cl.modulpfad, cl.qt_behalten, cl.Baum())
        assert seiten.abrufe(QTBASE) == 3


def alles(pfad, groesse):
    return True


class TestEntpacken:
    INHALT = {"oben/LICENSE": "Lizenz (Probetext)\n" * 300, "oben/README.chromium": "Name: Beispiel\n"}

    @pytest.mark.parametrize("art", ["xz", "gz"])
    def test_fehlendes_ende_ist_ein_fehler(self, tmp_path, art):
        """Bricht die Verbindung an einer Grenze zwischen zwei Dateien oder hinter dem tar-Teil ab, hoerte tarfile
        "r|*" still auf. Jetzt gilt nur ein Archiv, dessen Datenstrom bis zur Pruefsumme ankam."""
        ganz = tar_bauen(tmp_path / f"a.tar.{art}", self.INHALT, art=art)
        baum = cl.Baum()
        cl.durchgehen(io.BytesIO(ganz), cl.modulpfad, alles, baum)
        assert set(baum.dateien) == {"LICENSE", "README.chromium"}
        for ende in (len(ganz) - 8, len(ganz) // 2):
            with pytest.raises(EOFError, match="vorzeitig"):
                cl.durchgehen(io.BytesIO(ganz[:ende]), cl.modulpfad, alles, cl.Baum())

    def test_mehrere_datenstroeme_und_fuellnullen(self, tmp_path):
        roh = tar_bauen(tmp_path / "a.tar", self.INHALT, art="")
        for daten in (lzma.compress(roh[:1000]) + lzma.compress(roh[1000:]) + b"\0" * 4,
                      gzip.compress(roh[:700]) + gzip.compress(roh[700:])):
            baum = cl.Baum()
            cl.durchgehen(io.BytesIO(daten), cl.modulpfad, alles, baum)
            assert baum.dateien["LICENSE"] == self.INHALT["oben/LICENSE"].encode()

    def test_kein_archiv(self):
        """Etwa eine Fehlerseite mit Status 200: Fehler (und damit ein neuer Versuch), kein leerer Baum."""
        with pytest.raises(tarfile.ReadError, match="weder xz noch gzip"):
            cl.durchgehen(io.BytesIO(b"<html>Wartung</html>"), cl.modulpfad, alles, cl.Baum())
        with pytest.raises(EOFError, match="leere Antwort"):
            cl.durchgehen(io.BytesIO(b""), cl.modulpfad, alles, cl.Baum())

    def test_verweis_dahinter_kommt_im_selben_durchgang_mit(self, tmp_path, netz):
        """README.chromium verweist auf Dateien ohne Lizenznamen. Steht eine im Archiv hinter ihm (src/...), kommt
        sie im selben Durchgang mit; nur eine davor braucht einen weiteren Durchgang (Quellarchiv: rund 550 MB)."""
        url = "https://download.qt.io/probe.tar.xz"
        x = "oben/src/3rdparty/chromium/third_party/x"
        inhalte = {f"{x}/AAA_bedingungen.txt": "vorn (Probetext)",
                   f"{x}/README.chromium": readme("X", "AAA_bedingungen.txt, src/hinten.txt"),
                   f"{x}/src/hinten.txt": "hinten (Probetext)", f"{x}/src/anderes.c": "kein Lizenztext"}
        seiten = netz({url: tar_bauen(tmp_path / "p.tar.xz", inhalte)})
        baum = cl.Baum()
        cl.durchgehen(io.BytesIO(seiten.seiten[url]), cl.chromium_pfad, cl.chromium_behalten, baum,
                      cl.chromium_nachsehen)
        assert set(baum.dateien) == {"third_party/x/README.chromium", "third_party/x/src/hinten.txt"}

        def noetig(b):                                  # wie chromium_auswerten(b)[1] fuer dieses README
            return {"third_party/x/AAA_bedingungen.txt", "third_party/x/src/hinten.txt"}
        baum = cl.baum_lesen(url, cl.chromium_pfad, cl.chromium_behalten, noetig, cl.chromium_nachsehen)
        assert seiten.abrufe(url) == 2 and baum.text("third_party/x/AAA_bedingungen.txt") == "vorn (Probetext)"


class TestAufruf:
    def test_versionen_fuer_den_cache(self, monkeypatch, capsys):
        monkeypatch.setattr(cl, "versionen", lambda: VERSIONEN)
        assert cl.main(["--versionen"]) == 0
        assert capsys.readouterr().out.splitlines() == [
            "qt=6.12.0", "webengine=6.140.0", f"chromium={STAND[0]}", f"sicherheit={STAND[1]}", "icu=73.2"]

    def test_ohne_ziel(self, capsys):
        assert cl.main([]) == 2 and "Aufruf" in capsys.readouterr().err

    def test_ohne_pyside6(self, monkeypatch, capsys):
        """Unter Windows (und ohne PySide6) meldet das Werkzeug klar, wo es laufen muss."""
        monkeypatch.setitem(__import__("sys").modules, "PySide6", None)
        assert cl.main(["--versionen"]) == 1
        assert "PySide6 mit Qt WebEngine nicht importierbar" in capsys.readouterr().err

    def test_workflow_erzeugt_vor_dem_paket(self):
        """bauen.yml (Job bauen): Versionen, Cache, Erzeugen bei leerem Cache, Speichern, alles nur unter Linux und
        vor dem Paket; der Cache-Schluessel nutzt genau die Ausgaben von --versionen und den Stand des Werkzeugs."""
        text = (WURZEL / ".github" / "workflows" / "bauen.yml").read_text(encoding="utf-8")
        job = re.split(r"^  [a-z]+:\s*$", text.split("\njobs:\n", 1)[1], flags=re.MULTILINE)[1]   # Job bauen
        schritte = re.split(r"^      - ", job, flags=re.MULTILINE)
        namen = [re.match(r"(?:name: )?(.*)", s).group(1).strip() for s in schritte]
        reihe = ["Versionen für die Chromium-Lizenzen", "Chromium-Lizenzen aus dem Cache", "Chromium-Lizenzen erzeugen",
                 "Chromium-Lizenzen in den Cache", "Paket"]
        stellen = [namen.index(n) for n in reihe]
        assert stellen == sorted(stellen)
        for n in reihe[:-1]:
            assert "if: runner.os == 'Linux'" in schritte[namen.index(n)]
        erzeugen = schritte[namen.index("Chromium-Lizenzen erzeugen")]
        assert "cache-hit != 'true'" in erzeugen and "python werkzeuge/chromium_lizenzen.py CHROMIUM-LIZENZEN.txt" \
            in erzeugen
        schluessel = schritte[namen.index("Chromium-Lizenzen aus dem Cache")]
        felder = [z.split("=", 1)[0] for z in cl.versionsschluessel(VERSIONEN).splitlines()]
        assert set(re.findall(r"steps\.qt\.outputs\.(\w+)", schluessel)) == set(felder)
        assert "hashFiles('werkzeuge/chromium_lizenzen.py')" in schluessel
        assert "path: CHROMIUM-LIZENZEN.txt" in schluessel and bauen.CHROMIUM_LIZENZEN.name == "CHROMIUM-LIZENZEN.txt"


class TestPaket:
    """Weg ins Linux-Paket (werkzeuge/bauen.py) und Verweis in DRITTLIZENZEN.txt (werkzeuge/drittlizenzen.py)."""

    @pytest.fixture
    def linux(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bauen, "SYSTEM", "linux")
        monkeypatch.setattr(bauen, "drittlizenzen", lambda ziel: Path(ziel).write_text("Lizenzen", encoding="utf-8"))
        monkeypatch.setattr(bauen, "CHROMIUM_LIZENZEN", tmp_path / "projekt" / "CHROMIUM-LIZENZEN.txt")
        lib = tmp_path / "dist" / "pdf2md" / "_internal" / "PySide6" / "Qt" / "lib"
        lib.mkdir(parents=True)
        (lib / "libQt6WebEngineCore.so.6").write_bytes(b"elf")
        (tmp_path / "dist" / "pdf2md" / "pdf2md").write_bytes(b"elf")
        (tmp_path / "projekt").mkdir()
        return tmp_path

    def test_linux_paket_mit_chromium_lizenzen(self, linux):
        (linux / "projekt" / "CHROMIUM-LIZENZEN.txt").write_text(
            "Kopf\nBestandteile: 3 (Chromium 3)\nOhne Lizenztext: 0\n\n" + CHROMIUM_TEXT, encoding="utf-8")
        archiv = bauen.paket("linux-x86_64", "v9.9.9", linux / "dist", linux)
        with tarfile.open(archiv) as tar:
            namen = tar.getnames()
        assert any(n.endswith("CHROMIUM-LIZENZEN.txt") for n in namen)
        bericht = json.loads((linux / "paket.json").read_text(encoding="utf-8"))
        assert bericht["chromium_volltext"] and bericht["chromium_bestandteile"] == 3

    def test_linux_paket_ohne_chromium_lizenzen_bricht_ab(self, linux):
        with pytest.raises(SystemExit, match="CHROMIUM-LIZENZEN.txt fehlt: Qt WebEngine enthält Chromium"):
            bauen.paket("linux-x86_64", "v9.9.9", linux / "dist", linux)
        assert not list(linux.glob("pdf2md-*.tar.xz"))

    def test_ohne_qt_webengine_keine_pflicht(self, linux):
        """Ohne Qt WebEngine im Programmordner (also ohne Chromium) braucht das Paket die Datei nicht."""
        next((linux / "dist").rglob("libQt6WebEngineCore.so.6")).unlink()
        archiv = bauen.paket("linux-x86_64", "v9.9.9", linux / "dist", linux)
        with tarfile.open(archiv) as tar:
            assert not any(n.endswith("CHROMIUM-LIZENZEN.txt") for n in tar.getnames())

    def test_lizenzbericht_aus_beiden_dateien(self, tmp_path):
        (tmp_path / "DRITTLIZENZEN.txt").write_text("Kopf\n\nPySide6 6.12 – LGPL\n", encoding="utf-8")
        bericht = bauen.lizenzbericht(tmp_path)
        assert not bericht["chromium_volltext"] and bericht["chromium_bestandteile"] == 0
        assert bericht["chromium_quelle"] is None
        (tmp_path / "CHROMIUM-LIZENZEN.txt").write_text(
            "Kopf\nQuelle Chromium: github.com/qt/qtwebengine 6.140.0 (https://codeload.example.org/x)\n"
            "Bestandteile: 412 (Chromium 380, Qt 31, ICU 1)\nVerschiedene Lizenztexte: 250\nOhne Lizenztext: 2\n\n"
            + "=" * 79 + "\n[1] gilt für:\n" + "=" * 79 + "\n" + CHROMIUM_TEXT, encoding="utf-8")
        bericht = bauen.lizenzbericht(tmp_path)
        assert bericht["chromium_volltext"] and bericht["chromium_bestandteile"] == 412
        assert bericht["chromium_ohne_lizenztext"] == 2
        assert bericht["chromium_quelle"] == "github.com/qt/qtwebengine 6.140.0 (https://codeload.example.org/x)"
        assert bericht["eintraege"] == 1                    # die Uebersicht von DRITTLIZENZEN.txt bleibt fuer sich

    def test_release_warnt_nicht_mehr_mit_volltext(self, tmp_path):
        """hinweise() bleibt unveraendert: die Warnung CHROMIUM_AUFGABE verschwindet von selbst, sobald der
        Paketbericht aus DRITTLIZENZEN.txt und CHROMIUM-LIZENZEN.txt den Volltext meldet."""
        trenner = "=" * 79
        (tmp_path / "DRITTLIZENZEN.txt").write_text(f"Kopf\n\nPySide6 6.12 – LGPL\n\n{trenner}\nPySide6 6.12 – LGPL\n"
                                                    f"{trenner}\nLGPL-Text (Probetext)\n", encoding="utf-8")

        def chromium_warnung():
            (tmp_path / "paket.json").write_text(json.dumps(bauen.lizenzbericht(tmp_path)), encoding="utf-8")
            return [z for z in bauen.hinweise("linux-x86_64", tmp_path, tag="v1.2.0") if "Chromium-Lizenzen" in z]
        assert chromium_warnung()                           # Gegenprobe: ohne die Datei warnt ein Release
        (tmp_path / "CHROMIUM-LIZENZEN.txt").write_text("Kopf\nBestandteile: 1 (Chromium 1)\n\n" + CHROMIUM_TEXT,
                                                        encoding="utf-8")
        assert not chromium_warnung()

    def test_einleitung_verweist_auf_die_datei(self):
        drittlizenzen = laden("drittlizenzen")
        linux = "\n".join(drittlizenzen.einleitung("linux"))
        assert "CHROMIUM-LIZENZEN.txt" in linux and "doc.qt.io" not in linux
        assert "CHROMIUM-LIZENZEN.txt" not in "\n".join(drittlizenzen.einleitung("win32"))
