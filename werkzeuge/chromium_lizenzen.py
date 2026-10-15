"""Schreibt CHROMIUM-LIZENZEN.txt fuer das Linux-Paket: die Lizenztexte von Chromium (steckt ueber PySide6 in Qt
WebEngine) und der Bestandteile Dritter, die Qt selbst mitbringt, vollstaendig und versionsgenau.

Aufruf:  python werkzeuge/chromium_lizenzen.py <zieldatei>     erzeugen (bauen.yml, nur Linux, vor dem Paket)
         python werkzeuge/chromium_lizenzen.py --versionen    Versionen als key=wert (Cache-Schluessel in bauen.yml)

Laeuft in der Umgebung, mit der gebaut wird: die Versionen meldet das installierte PySide6 selbst (qVersion(),
qWebEngineVersion(), qWebEngineChromiumVersion(), qWebEngineChromiumSecurityPatchVersion(), ICU aus Qt/lib).

Quelle (Recherche 2026-10-10 an PySide6 6.12.0, PySide6_WebEngine 6.12.0.140 = Qt WebEngine 6.140.0):
- (a) Wheels: PySide6_WebEngine und PySide6_Essentials enthalten keine Lizenz- oder Attributionsdatei (nur METADATA
  mit der LGPL-Angabe), qtwebengine_resources.pak keine chrome://credits-Seite. Scheidet aus.
- (b) Qt-Doku "Qt WebEngine Licensing" (eine Seite je Bestandteil): von Qt mit licenses.py und GN erzeugt, also genau
  die gebauten Teile, aber nur HTML, und fuer Qt WebEngine 6.140 nur als wandernder Snapshot (doc.qt.io leitet auf
  doc-snapshots.qt.io um); versionierte Doku gibt es nur bis Qt 6.11. Nicht versionsgenau.
- (c) Quellarchiv qtwebengine-everywhere-src-<ver>.tar.xz (rund 550 MB, nur bei leerem Cache): offizielle Quelle mit
  allen README.chromium, Lizenzdateien und CHROMIUM_VERSION. Seit Qt 6.12 ist Qt WebEngine ein eigenes Produkt
  (6.140 = Chromium 140) und liegt nicht mehr unter qt/<X.Y>/<X.Y.Z>/submodules; am 2026-10-10 gab es nur
  6.140.0-rc unter development_releases (auch das wird geprueft). Deshalb als Ersatz der GitHub-Spiegel:
  qt/qtwebengine (Tag v<ver>, Zweig <ver>, Verlauf von CHROMIUM_VERSION) nennt den Submodul-Stand von
  qt/qtwebengine-chromium, das Archiv dazu liefert codeload.github.com (gleicher Inhalt wie src/3rdparty im
  Quellarchiv; am 2026-10-11 geprueft: liefert den Baum sofort als Datenstrom).
- (d) Chromiums tools/licenses/licenses.py braucht GN und einen konfigurierten Build. Seine Regeln (welche
  Verzeichnisse, SPECIAL_CASES fuer Blink, V8, PDFium, ANGLE, PRUNE_PATHS, Shipped) liest dieses Werkzeug aber aus
  genau der verwendeten Quelle und wendet sie an.
Gewaehlt: (c), ersatzweise GitHub. Versionsgenau heisst: CHROMIUM_VERSION der Quelle (Chromium-Basis und Stand der
Sicherheitskorrekturen) stimmt mit dem ueberein, was die mitgelieferte Bibliothek meldet. Gibt es das nicht (am
2026-10-11: Bibliothek Chromium 140.0.7339.225, alle Quellen 140.0.7339.264 beim gleichen Sicherheitsstand),
genuegt nach Entscheidung des Nutzers (2026-10-15) eine Quelle mit gleichem Sicherheitsstand, deren Chromium nur in
der Patch-Nummer abweicht; die Datei nennt die Abweichung. Sonst Abbruch. Ohne GN ist
die Liste eine Obermenge (alle Bestandteile mit Shipped: yes, auch solche, die nur unter Windows, macOS oder Android
gebaut werden). Bei Lizenzhinweisen ist das unschaedlich, fehlen darf dagegen nichts.

Qt selbst: dieselbe Ablage (download.qt.io, qt/<X.Y>/<X.Y.Z>/submodules, genau qVersion(); Ersatz: GitHub-Tag)
liefert die Quellarchive der Qt-Module mit einer qt_attribution.json je Drittbestandteil (zlib, HarfBuzz, FreeType,
libpng, PCRE2, libjpeg, libtiff, libwebp, ...). ICU liegt als libicu*.so.<NN> bei Qt, steht in keinem Qt-Archiv und
kommt aus unicode-org/icu (Tag der Version, die die Bibliothek meldet).

Gelesen wird im Streaming-Modus (tarfile "r|" hinter einem eigenen Entpacker), auf die Platte kommt nichts: nur
README.chromium & Co., licenses.py, qt_attribution.json und Dateien mit Lizenznamen bleiben im Speicher. Verweist
ein Bestandteil auf eine anders benannte Datei, kommt sie im selben Durchgang mit, wenn sie im Archiv hinter dem
Verweis steht, sonst in einem weiteren Durchgang nur fuer diese Dateien. Endet ein Archiv vorzeitig (abgebrochene
Verbindung), wird es neu gelesen statt mit unvollstaendigem Baum weiterzumachen. Fehler beenden mit Rueckgabewert 1.

Geprueft am 2026-10-11 an der echten licenses.py von Chromium 140 (qtwebengine-chromium, Zweig 6.140.0):
regeln_lesen liest 22 SPECIAL_CASES, 45 PRUNE_PATHS und 12 ADDITIONAL_PATHS. Die Auswahl der Verzeichnisse folgt
FindThirdPartyDirs/ParseDir dort; abweichend nimmt dieses Werkzeug auch Bestandteile auf, deren Lizenzdatei fehlt
oder deren Pflichtangaben unvollstaendig sind (licenses.py liesse sie still weg), und vermerkt das."""
import ast
import ctypes
import http.client
import json
import lzma
import os
import posixpath
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

KENNUNG = "pdf2md/1.0"
DOWNLOAD = "https://download.qt.io"
GITHUB_API = "https://api.github.com"
GITHUB_ROH = "https://raw.githubusercontent.com"
CODELOAD = "https://codeload.github.com"
ZEITLIMIT = 120                 # Sekunden je Anfrage (ohne Gesamtdauer eines Archivs)
WARTEN = (5, 20)                # Sekunden vor dem zweiten und dritten Versuch
DURCHGAENGE = 3                 # hoechstens so oft wird ein Archiv gelesen (erster Durchgang + Nachlesen)
VORSCHAU_EINTRAEGE = 5000       # so weit wird ein Archiv nach CHROMIUM_VERSION durchsucht (steht ganz vorn)
VERLAUF = 15                    # so viele Stände von CHROMIUM_VERSION je Zweig werden verglichen
GROESSTE_DATEI = 4_000_000      # groessere Dateien mit Lizenznamen sind keine Lizenztexte
TRENNER = "=" * 79              # wie in DRITTLIZENZEN.txt

# Qt-Module, deren Bibliotheken oder Plugins im Linux-Paket stecken (koennen) und die Drittbestandteile mitbringen;
# qtshadertools (glslang, SPIRV-Cross) vorsorglich, falls PyInstaller libQt6ShaderTools mitnimmt. qtsvg,
# qtwebchannel und qtlottie haben keine qt_attribution.json (Stand Qt 6.12.0); Qt PDF (Plugin imageformats/libqpdf)
# stammt aus Qt WebEngine und ist mit dem Chromium-Baum (PDFium) abgedeckt.
QT_MODULE = ("qtbase", "qtdeclarative", "qtimageformats", "qtwayland", "qtpositioning", "qtvirtualkeyboard",
             "qtshadertools")
# Beispiele, Tests, Werkzeuge und Build-Skripte stecken nicht im Programm
QT_AUSGENOMMEN = re.compile(r"^(?:examples|tests|util|cmake|coin)/|/(?:testlib|testinternal)/")

# wie in Chromiums tools/licenses/licenses.py (Standard, falls die Quelle sie nicht selbst festlegt)
METADATEN = ("README.chromium", "README.crashpad", "README.v8", "README.pdfium", "README.angle")
LICENSES_PY = ("tools/licenses/licenses.py", "tools/licenses.py")
ZUSATZPFADE = "additional_readme_paths.json"
FELDER = ("Name", "URL", "License", "License File", "Shipped")
ALIAS = {"Shipped in Chromium": "Shipped"}
NICHT_AUSGELIEFERT = "NOT_SHIPPED"
ABHAENGIGKEITEN_TRENNER = re.compile(r"^-{20} DEPENDENCY DIVIDER -{20}$")

# Dateinamen, die schon im ersten Durchgang mitkommen; "credits": ffmpeg nennt CREDITS.chromium als Lizenzdatei, und
# die steht im Archiv vor dem README.chromium (sonst ein weiterer Durchgang durch rund 550 MB)
LIZENZNAME = re.compile(r"licen[cs]e|copying|copyright|notice|patents|credits", re.IGNORECASE)
BINAER = re.compile(r"\.(?:png|jpe?g|gif|ico|webp|bmp|pyc|so|a|o|jar|zip|gz|xz|bz2|tgz|pak|bin|dat|wasm|ttf|otf"
                    r"|woff2?)$", re.IGNORECASE)
CHROMIUM_PFAD = re.compile(r"^(?:\./)?[^/]+/(?:src/3rdparty/)?chromium/(.+)$")
CHROMIUM_VERSION = re.compile(r"^(?:\./)?[^/]+/CHROMIUM_VERSION$")


class Abbruch(Exception):
    """Fehler mit Meldung fuer den Build-Lauf (Rueckgabewert 1)."""


# ---------------------------------------------------------------------------------------------------------------
# Netz


class _Umleitung(urllib.request.HTTPRedirectHandler):
    """Folgt Umleitungen (download.qt.io verteilt auf Spiegel), gibt ein GitHub-Token aber nie an andere Server."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        neu = super().redirect_request(req, fp, code, msg, headers, newurl)
        if neu is not None and urllib.parse.urlsplit(newurl).hostname != "api.github.com":
            neu.remove_header("Authorization")
        return neu


OEFFNER = urllib.request.build_opener(_Umleitung)


def anfrage(url: str, methode: str = "GET") -> urllib.request.Request:
    """Anfrage mit eigener Kennung; das Token aus GITHUB_TOKEN (bauen.yml, gegen die Abruf-Grenze der API ohne
    Anmeldung) nur fuer api.github.com."""
    kopf = {"User-Agent": KENNUNG}
    token = os.environ.get("GITHUB_TOKEN")
    if token and urllib.parse.urlsplit(url).hostname == "api.github.com":
        kopf["Authorization"] = f"Bearer {token}"
        kopf["Accept"] = "application/vnd.github+json"
    return urllib.request.Request(url, headers=kopf, method=methode)


def oeffnen(url: str, methode: str = "GET"):
    """Antwort (offen, mit read()) oder None, wenn es die Adresse nicht gibt (404/410). Andere Fehler werden bis zu
    zweimal wiederholt, dann Abbruch."""
    fehler: Exception | None = None
    for versuch in range(len(WARTEN) + 1):
        if versuch:
            time.sleep(WARTEN[versuch - 1])
        try:
            return OEFFNER.open(anfrage(url, methode), timeout=ZEITLIMIT)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            fehler = e
        except (OSError, http.client.HTTPException) as e:       # URLError ist ein OSError
            fehler = e
    raise Abbruch(f"{url}: {fehler}")


def text_holen(url: str) -> str | None:
    """Inhalt als Text oder None (404/410); bricht die Verbindung beim Lesen ab, wird neu angefragt."""
    fehler: Exception | None = None
    for versuch in range(len(WARTEN) + 1):
        if versuch:
            time.sleep(WARTEN[versuch - 1])
        antwort = oeffnen(url)
        if antwort is None:
            return None
        try:
            with antwort:
                return antwort.read().decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException) as e:
            fehler = e
    raise Abbruch(f"{url}: {fehler}")


def json_holen(url: str):
    text = text_holen(url)
    try:
        return None if text is None else json.loads(text)
    except ValueError as e:
        raise Abbruch(f"{url}: keine JSON-Antwort ({e})") from None


def vorhanden(url: str) -> bool:
    antwort = oeffnen(url, "HEAD")
    if antwort is not None:
        antwort.close()
    return antwort is not None


# ---------------------------------------------------------------------------------------------------------------
# Archive im Streaming-Modus


@dataclass
class Baum:
    """Ausgewaehlte Dateien eines Quellarchivs; Pfade relativ zur Wurzel (Chromium: src/3rdparty/chromium)."""
    dateien: dict[str, bytes] = field(default_factory=dict)
    verweise: dict[str, str] = field(default_factory=dict)       # Verknuepfung -> Ziel, relativ zur Wurzel

    def aufloesen(self, pfad: str) -> str:
        for _ in range(20):                                       # Ketten von Verknuepfungen, ohne Endlosschleife
            if pfad not in self.verweise:
                break
            pfad = self.verweise[pfad]
        return pfad

    def hat(self, pfad: str) -> bool:
        return self.aufloesen(pfad) in self.dateien

    def text(self, pfad: str) -> str | None:
        return als_text(self.dateien.get(self.aufloesen(pfad)))


def als_text(daten: bytes | None) -> str | None:
    """Inhalt als Text (UTF-8, sonst Latin-1); None fuer fehlende oder binaere Dateien."""
    if daten is None or b"\0" in daten[:8192]:
        return None
    try:
        return daten.decode("utf-8")
    except UnicodeDecodeError:
        return daten.decode("latin-1")


XZ_KOPF, GZIP_KOPF = b"\xfd7zXZ\x00", b"\x1f\x8b"
LESEMENGE = 1 << 16             # Bytes je Lesevorgang aus der Antwort


class Entpacken:
    """Entpackt eine xz- oder gzip-Antwort beim Lesen (fuer tarfile "r|"). Anders als tarfile "r|*" meldet es ein
    vorzeitiges Ende als EOFError: bricht die Verbindung an einer Grenze zwischen zwei Dateien ab, haette tarfile
    still aufgehoert, und der Baum waere unvollstaendig, ohne dass es jemand merkt. Mehrere hintereinander gehaengte
    Datenstroeme (xz, gzip) werden nacheinander entpackt, Fuellnullen dahinter uebergangen."""

    def __init__(self, antwort):
        self.antwort, self.puffer, self.rest = antwort, bytearray(), b""
        self.entpacker = None
        self.ende = False

    def _naechster_strom(self, daten: bytes):
        if daten.startswith(XZ_KOPF):
            return lzma.LZMADecompressor()
        if daten.startswith(GZIP_KOPF):
            return zlib.decompressobj(16 + zlib.MAX_WBITS)
        return None

    def _nachfuellen(self) -> None:
        daten = self.rest or self.antwort.read(LESEMENGE)
        self.rest = b""
        if self.entpacker is None or self.entpacker.eof:
            while daten and len(daten) < len(XZ_KOPF):  # Kopf des Datenstroms erst vollstaendig
                mehr = self.antwort.read(LESEMENGE)
                if not mehr:
                    break
                daten += mehr
            if not daten:
                if self.entpacker is None:
                    raise EOFError("leere Antwort statt eines Archivs")
                self.ende = True
                return
            neu = self._naechster_strom(daten)
            if neu is None:
                if self.entpacker is None:
                    raise tarfile.ReadError("weder xz noch gzip")
                self.ende = True                        # Fuellnullen oder Reste hinter dem letzten Datenstrom
                return
            self.entpacker = neu
        elif not daten:
            raise EOFError("Archiv vorzeitig zu Ende (Verbindung abgebrochen?)")
        self.puffer += self.entpacker.decompress(daten)
        if self.entpacker.eof:
            self.rest = self.entpacker.unused_data

    def zu_ende_lesen(self) -> None:
        """Liest den Rest hinter dem Ende des tar-Teils (Fuellbloecke, Index, Pruefsumme): erst damit steht fest,
        dass das Archiv vollstaendig angekommen ist."""
        while not self.ende:
            self._nachfuellen()
            self.puffer.clear()

    def read(self, anzahl: int = -1) -> bytes:
        while not self.ende and (anzahl < 0 or len(self.puffer) < anzahl):
            self._nachfuellen()
        if anzahl < 0 or anzahl >= len(self.puffer):
            ergebnis = bytes(self.puffer)
            self.puffer.clear()
        else:
            ergebnis = bytes(self.puffer[:anzahl])
            del self.puffer[:anzahl]                    # vorn loeschen ist bei bytearray billig (kein Umkopieren)
        return ergebnis


def tar_lesen(strom: Entpacken) -> tarfile.TarFile:
    return tarfile.open(fileobj=strom, mode="r|")


def durchgehen(antwort, pfad_von: Callable[[str], str | None], behalten: Callable[[str, int], bool],
               baum: Baum, nachsehen: Callable[[str, bytes], Iterable[str]] | None = None) -> None:
    """Liest ein tar-Archiv (xz oder gzip) von vorn nach hinten und legt die gewuenschten Dateien in `baum` ab.
    `nachsehen(pfad, inhalt)` nennt zu einer gerade gelesenen Datei weitere, die noch im selben Durchgang mitkommen
    sollen, falls sie im Archiv weiter hinten stehen (z.B. die Lizenzdatei, auf die ein README.chromium verweist);
    ebenso das Ziel einer Verknuepfung. Was davor stand, holt baum_lesen in einem weiteren Durchgang. Ein
    unvollstaendiges Archiv ergibt EOFError (siehe Entpacken), auch wenn nur das Ende hinter dem tar-Teil fehlt."""
    dazu: set[str] = set()
    strom = Entpacken(antwort)
    with tar_lesen(strom) as tar:
        for info in tar:
            pfad = pfad_von(info.name)
            if pfad is None or not (pfad in dazu or behalten(pfad, info.size if info.isfile() else 0)):
                continue
            if info.issym():
                ziel = posixpath.normpath(posixpath.join(posixpath.dirname(pfad), info.linkname))
                baum.verweise[pfad] = ziel
                dazu.add(ziel)
            elif info.islnk():
                ziel = pfad_von(info.linkname)
                if ziel is not None:
                    baum.verweise[pfad] = ziel
            elif info.isfile():
                datei = tar.extractfile(info)
                if datei is not None:
                    baum.dateien[pfad] = datei.read()
                    if nachsehen is not None:
                        dazu.update(nachsehen(pfad, baum.dateien[pfad]))
    strom.zu_ende_lesen()


ARCHIVFEHLER = (OSError, EOFError, tarfile.TarError, lzma.LZMAError, zlib.error, http.client.HTTPException)


def archiv_lesen(url: str, pfad_von: Callable[[str], str | None], behalten: Callable[[str, int], bool],
                 baum: Baum, nachsehen: Callable[[str, bytes], Iterable[str]] | None = None) -> None:
    """Ein Durchgang durch das Archiv; bricht die Verbindung ab (auch still, siehe Entpacken), wird der Durchgang
    wiederholt."""
    fehler: Exception | None = None
    for versuch in range(len(WARTEN) + 1):
        if versuch:
            time.sleep(WARTEN[versuch - 1])
        antwort = oeffnen(url)
        if antwort is None:
            raise Abbruch(f"{url}: nicht (mehr) vorhanden")
        teil = Baum()
        try:
            with antwort:
                durchgehen(antwort, pfad_von, behalten, teil, nachsehen)
        except ARCHIVFEHLER as e:
            fehler = e
            continue
        baum.dateien.update(teil.dateien)
        baum.verweise.update(teil.verweise)
        return
    raise Abbruch(f"{url}: Archiv nicht lesbar ({fehler})")


def baum_lesen(url: str, pfad_von: Callable[[str], str | None], behalten: Callable[[str, int], bool],
               noetig: Callable[[Baum], set[str]],
               nachsehen: Callable[[str, bytes], Iterable[str]] | None = None) -> Baum:
    """Erster Durchgang mit `behalten` (und `nachsehen`, siehe durchgehen); fehlen danach Dateien, die `noetig`
    verlangt (anders benannte Lizenzdateien, die im Archiv vor ihrem Verweis stehen, Ziele von Verknuepfungen), folgen
    Durchgaenge nur fuer diese. Was dann noch fehlt, gibt es in der Quelle nicht. Was `behalten` schon im ersten
    Durchgang genommen haette, wird nicht noch einmal gesucht."""
    baum = Baum()
    archiv_lesen(url, pfad_von, behalten, baum, nachsehen)
    gesucht: set[str] = set()
    for _ in range(DURCHGAENGE - 1):
        ziele = {baum.aufloesen(p) for p in noetig(baum) if not baum.hat(p)}
        fehlend = {p for p in ziele if not behalten(p, 0)} - gesucht
        if not fehlend:
            break
        gesucht |= fehlend
        print(f"  weiterer Durchgang fuer {len(fehlend)} Dateien", flush=True)
        archiv_lesen(url, pfad_von, lambda pfad, groesse: pfad in fehlend, baum)
    return baum


def lizenzname(pfad: str, groesse: int) -> bool:
    name = posixpath.basename(pfad)
    return groesse <= GROESSTE_DATEI and bool(LIZENZNAME.search(name)) and not BINAER.search(name)


def normtext(text: str) -> str:
    """Vergleichsform eines Lizenztextes: Zeilenenden, Leerraum am Zeilenende und am Rand vereinheitlicht."""
    return "\n".join(z.rstrip() for z in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()


# ---------------------------------------------------------------------------------------------------------------
# Bestandteile


@dataclass
class Bestandteil:
    teil: str                       # "Chromium", "Qt" oder "ICU"
    name: str
    url: str
    lizenz: str
    fundorte: list[str]             # Pfade in der Quelle
    text: str | None                # Volltext (mehrere Dateien hintereinander)
    erwartet: list[str] = field(default_factory=list)   # gesuchte, aber nicht vorhandene Lizenzdateien


@dataclass(frozen=True)
class Versionen:
    qt: str
    webengine: str
    chromium: str                   # Chromium-Basis, z.B. 140.0.7339.264
    sicherheit: str                 # Stand der Sicherheitskorrekturen, z.B. 154.0.8037.93
    icu: str | None                 # ICU, das Qt mitbringt (z.B. 73.2; nur die Hauptversion, wenn nicht ermittelbar)


def _zeichen(wert) -> str:
    return wert if isinstance(wert, str) else bytes(wert).decode("utf-8", errors="replace")


def icu_version(lib: Path) -> str | None:
    """Version der ICU-Bibliothek neben Qt: die Hauptversion steht im Dateinamen (libicuuc.so.73), die genaue meldet
    u_getVersion_73() der Bibliothek selbst. libicudata wird vorher geladen, falls libicuuc sie nicht ueber einen
    eigenen Suchpfad findet (meist hat QtCore beide schon geladen)."""
    for datei in sorted(lib.glob("libicuuc.so.*")):
        haupt = re.fullmatch(r"libicuuc\.so\.(\d+)(?:\.\d+)*", datei.name)
        if not haupt:
            continue
        try:
            daten = lib / f"libicudata.so.{haupt.group(1)}"
            if daten.is_file():
                ctypes.CDLL(str(daten), mode=ctypes.RTLD_GLOBAL)
            info = (ctypes.c_uint8 * 4)()
            getattr(ctypes.CDLL(str(datei)), f"u_getVersion_{haupt.group(1)}")(info)
            teile = list(info)
            while len(teile) > 2 and teile[-1] == 0:
                teile.pop()
            return ".".join(str(t) for t in teile)
        except (OSError, AttributeError):
            return haupt.group(1)
    return None


def versionen() -> Versionen:
    """Versionen aus dem installierten PySide6 (genau das, was ins Paket kommt)."""
    try:
        from PySide6 import QtCore, QtWebEngineCore
    except ImportError as e:
        raise Abbruch(f"PySide6 mit Qt WebEngine nicht importierbar ({e}); das Werkzeug laeuft in der "
                      "Build-Umgebung unter Linux") from None
    return Versionen(qt=_zeichen(QtCore.qVersion()), webengine=_zeichen(QtWebEngineCore.qWebEngineVersion()),
                     chromium=_zeichen(QtWebEngineCore.qWebEngineChromiumVersion()),
                     sicherheit=_zeichen(QtWebEngineCore.qWebEngineChromiumSecurityPatchVersion()),
                     icu=icu_version(Path(QtCore.__file__).resolve().parent / "Qt" / "lib"))


def versionsschluessel(v: Versionen) -> str:
    return "\n".join(f"{k}={w or ''}" for k, w in (("qt", v.qt), ("webengine", v.webengine), ("chromium", v.chromium),
                                                  ("sicherheit", v.sicherheit), ("icu", v.icu)))


# ---------------------------------------------------------------------------------------------------------------
# Chromium: Quelle finden


def chromium_stand(text: str) -> tuple[str, str] | None:
    """(Chromium-Basis, Stand der Sicherheitskorrekturen) aus Qts Datei CHROMIUM_VERSION."""
    basis = re.search(r"Based on Chromium version:\s*(\S+)", text)
    sicher = re.search(r"security patches up to Chromium version:\s*(\S+)", text)
    return (basis.group(1), sicher.group(1) if sicher else "") if basis else None


@dataclass
class Kandidat:
    beschreibung: str
    stand: Callable[[], tuple[str, str] | None]      # None: gibt es nicht
    archiv: Callable[[], str]                         # Adresse des Archivs mit dem Chromium-Baum


def archiv_stand(antwort) -> tuple[str, str]:
    """Liest nur den Anfang des Archivs bis zu CHROMIUM_VERSION (steht im Quellarchiv ganz vorn)."""
    with tar_lesen(Entpacken(antwort)) as tar:
        for nummer, info in enumerate(tar):
            if CHROMIUM_VERSION.match(info.name) and info.isfile():
                datei = tar.extractfile(info)
                stand = chromium_stand(datei.read().decode("utf-8", errors="replace")) if datei else None
                return stand or ("unbekannt", "")
            if nummer >= VORSCHAU_EINTRAEGE:
                break
    return ("ohne CHROMIUM_VERSION", "")


def archiv_kandidat(url: str) -> Kandidat:
    def stand():
        antwort = oeffnen(url)
        if antwort is None:
            return None
        try:
            with antwort:
                return archiv_stand(antwort)
        except ARCHIVFEHLER as e:
            return (f"nicht lesbar: {e}", "")
    return Kandidat(url, stand, lambda: url)


def github_kandidat(ref: str) -> Kandidat:
    """Stand von qt/qtwebengine (Tag, Zweig oder Commit); den Chromium-Baum enthaelt das Submodul src/3rdparty."""
    def stand():
        text = text_holen(f"{GITHUB_ROH}/qt/qtwebengine/{ref}/CHROMIUM_VERSION")
        return None if text is None else (chromium_stand(text) or ("unbekannt", ""))

    def archiv():
        info = json_holen(f"{GITHUB_API}/repos/qt/qtwebengine/contents/src/3rdparty?ref={urllib.parse.quote(ref)}")
        if not isinstance(info, dict) or info.get("type") != "submodule" or not info.get("sha"):
            raise Abbruch(f"qt/qtwebengine {ref}: Submodul src/3rdparty nicht gefunden")
        return f"{CODELOAD}/qt/qtwebengine-chromium/tar.gz/{info['sha']}"
    return Kandidat(f"github.com/qt/qtwebengine {ref}", stand, archiv)


def verlauf_kandidaten(zweig: str) -> Iterator[Kandidat]:
    """Fruehere Staende eines Zweigs, an denen sich CHROMIUM_VERSION geaendert hat (neueste zuerst)."""
    commits = json_holen(f"{GITHUB_API}/repos/qt/qtwebengine/commits?sha={urllib.parse.quote(zweig)}"
                         f"&path=CHROMIUM_VERSION&per_page={VERLAUF}")
    for commit in commits if isinstance(commits, list) else []:
        if isinstance(commit, dict) and commit.get("sha"):
            yield github_kandidat(commit["sha"])


def chromium_kandidaten(v: Versionen) -> Iterator[Kandidat]:
    """Moegliche Quellen fuer den Chromium-Baum von Qt WebEngine v.webengine, die genaueste zuerst: das offizielle
    Quellarchiv (eigenes Produkt ab 6.140, Ablage der fertigen Fassung noch unbekannt, deshalb mit und ohne X.Y;
    bis Qt 6.11 unter qt/<X.Y>/<X.Y.Z>/submodules), der Tag auf GitHub, das Quellarchiv des Release-Kandidaten, der
    Zweig der Fassung und zuletzt fruehere Staende der Zweige. Welche passt, entscheidet allein CHROMIUM_VERSION."""
    ver = v.webengine
    xy = ".".join(ver.split(".")[:2])
    datei = f"qtwebengine-everywhere-src-{ver}.tar.xz"
    for ordner in (f"official_releases/qtwebengine/{xy}/{ver}", f"official_releases/qtwebengine/{ver}",
                   f"archive/qtwebengine/{xy}/{ver}", f"archive/qtwebengine/{ver}",
                   f"official_releases/qt/{xy}/{ver}/submodules", f"archive/qt/{xy}/{ver}/submodules"):
        yield archiv_kandidat(f"{DOWNLOAD}/{ordner}/{datei}")
    yield github_kandidat(f"v{ver}")
    yield archiv_kandidat(f"{DOWNLOAD}/development_releases/qtwebengine/{ver}-rc/qtwebengine-everywhere-src-{ver}-rc"
                          ".tar.xz")
    yield github_kandidat(ver)
    for zweig in dict.fromkeys((ver, xy)):
        yield from verlauf_kandidaten(zweig)


def nur_patch_anders(stand: tuple[str, str], v: Versionen) -> bool:
    """Gleicher Sicherheitsstand, Chromium bis auf die Patch-Nummer gleich (140.0.7339.264 statt .225)."""
    basis, teile = stand[0].split("."), v.chromium.split(".")
    return (bool(stand[1]) and stand[1] == v.sicherheit and len(basis) == len(teile) == 4
            and basis[:3] == teile[:3] and basis[3] != teile[3])


def chromium_quelle(v: Versionen, kandidaten: Iterator[Kandidat] | None = None) -> tuple[str, str, str | None]:
    """(Beschreibung, Archiv, Abweichung) der Quelle fuer den Chromium-Baum. Zuerst zaehlt eine Quelle, deren
    CHROMIUM_VERSION genau zur Bibliothek passt. Gibt es keine, genuegt die erste mit gleichem Sicherheitsstand,
    deren Chromium nur in der Patch-Nummer abweicht (Nutzerentscheidung 2026-10-15; Abweichung = deren Chromium,
    sonst None). Eine Quelle, die nicht erreichbar ist, wird uebersprungen; passt keine, bricht das Werkzeug mit der
    Liste aller ab."""
    gesucht = (v.chromium, v.sicherheit)
    gesehen, ersatz = [], None
    folge = iter(chromium_kandidaten(v) if kandidaten is None else kandidaten)
    while True:
        try:
            kandidat = next(folge)
        except StopIteration:
            break
        except Abbruch as e:                        # z.B. Verlauf auf GitHub nicht abrufbar
            gesehen.append(f"  weitere Quellen nicht ermittelbar: {e}")
            break
        try:
            stand = kandidat.stand()
            if stand is None:
                gesehen.append(f"  {kandidat.beschreibung}: gibt es nicht")
                continue
            gesehen.append(f"  {kandidat.beschreibung}: Chromium {stand[0]}, Sicherheitsstand {stand[1] or '?'}")
            if stand == gesucht:
                return kandidat.beschreibung, kandidat.archiv(), None
            if ersatz is None and nur_patch_anders(stand, v):
                ersatz = (kandidat, stand[0])               # weiter nach einer genau passenden suchen
        except Abbruch as e:
            gesehen.append(f"  {kandidat.beschreibung}: nicht erreichbar ({e})")
    if ersatz:
        return ersatz[0].beschreibung, ersatz[0].archiv(), ersatz[1]
    raise Abbruch(f"keine passende Quelle für den Chromium-Stand der Bibliothek (Qt WebEngine {v.webengine}, Chromium "
                  f"{v.chromium}, Sicherheitsstand {v.sicherheit}; genau dieser Stand oder derselbe Sicherheitsstand "
                  "mit anderer Patch-Nummer) gefunden:\n" + "\n".join(gesehen))


# ---------------------------------------------------------------------------------------------------------------
# Chromium: Regeln aus licenses.py und README.chromium


@dataclass
class Regeln:
    sonderfaelle: dict[str, dict]               # SPECIAL_CASES: Verzeichnis -> Angaben (statt README.chromium)
    ausgelassen: set[str]                       # PRUNE_PATHS
    zusaetzlich: set[str]                       # ADDITIONAL_PATHS
    metadaten: tuple[str, ...] = METADATEN      # METADATA_FILE_NAMES
    ohne_abstieg: tuple[str, ...] = (".svn", ".git", "layout_tests")    # PRUNE_DIRS


def regeln_lesen(text: str) -> Regeln:
    """Liest SPECIAL_CASES, PRUNE_PATHS, ADDITIONAL_PATHS (und METADATA_FILE_NAMES, PRUNE_DIRS) aus Chromiums
    licenses.py, ohne es auszufuehren: nur Literale, os.path.join, set/frozenset/tuple/list, + und .update()."""
    werte: dict[str, object] = {}

    def wert(knoten):
        if not isinstance(knoten, ast.AST):         # z.B. **ausdruck in einem Woerterbuch
            raise ValueError("kein Literal")
        if isinstance(knoten, ast.Constant):
            return knoten.value
        if isinstance(knoten, (ast.List, ast.Tuple, ast.Set)):
            return [wert(e) for e in knoten.elts]
        if isinstance(knoten, ast.Dict):
            return {wert(k): wert(w) for k, w in zip(knoten.keys, knoten.values)}
        if isinstance(knoten, ast.Name) and knoten.id in werte:
            return werte[knoten.id]
        if isinstance(knoten, ast.BinOp) and isinstance(knoten.op, ast.Add):
            return list(wert(knoten.left)) + list(wert(knoten.right))
        if isinstance(knoten, ast.Call) and not knoten.keywords:
            name = ast.unparse(knoten.func)
            if name == "os.path.join":
                return "/".join(wert(a) for a in knoten.args)
            if name in ("set", "frozenset", "tuple", "list"):
                return list(wert(knoten.args[0])) if knoten.args else []
        raise ValueError(ast.unparse(knoten)[:80])

    try:
        programm = ast.parse(text)
    except (SyntaxError, ValueError) as e:
        raise Abbruch(f"licenses.py nicht lesbar: {e}") from None
    for knoten in programm.body:
        try:
            if (isinstance(knoten, ast.Assign) and len(knoten.targets) == 1
                    and isinstance(knoten.targets[0], ast.Name) and knoten.targets[0].id.isupper()):
                werte[knoten.targets[0].id] = wert(knoten.value)
            elif (isinstance(knoten, ast.Expr) and isinstance(knoten.value, ast.Call)
                  and ast.unparse(knoten.value.func) == "PRUNE_PATHS.update" and len(knoten.value.args) == 1):
                werte["PRUNE_PATHS"] = list(werte.get("PRUNE_PATHS", [])) + list(wert(knoten.value.args[0]))
        except ValueError:
            continue                                # andere Konstanten (z.B. mit Funktionsaufrufen) braucht es nicht
    fehlend = [n for n in ("SPECIAL_CASES", "PRUNE_PATHS", "ADDITIONAL_PATHS") if n not in werte]
    if fehlend or not isinstance(werte["SPECIAL_CASES"], dict):
        raise Abbruch(f"licenses.py: {', '.join(fehlend) or 'SPECIAL_CASES'} nicht lesbar")
    return Regeln(sonderfaelle={k: dict(w) for k, w in werte["SPECIAL_CASES"].items()},
                  ausgelassen=set(werte["PRUNE_PATHS"]), zusaetzlich=set(werte["ADDITIONAL_PATHS"]),
                  metadaten=tuple(werte.get("METADATA_FILE_NAMES") or METADATEN),
                  ohne_abstieg=tuple(werte.get("PRUNE_DIRS") or (".svn", ".git", "layout_tests")))


def metadaten_lesen(text: str) -> list[dict]:
    """Angaben aus README.chromium wie licenses.py: "Feld: Wert" je Zeile (bekannte Felder, Gross-/Kleinschreibung
    egal), mehrere Abhaengigkeiten durch DEPENDENCY DIVIDER getrennt, License File durch Kommas. Doppelte Felder:
    das erste gilt (licenses.py verwirft dann die ganze Datei; fuer Lizenzhinweise ist mehr besser als weniger)."""
    bekannt = {f.lower(): f for f in (*FELDER, *ALIAS)}
    liste, angaben = [], {}
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if ABHAENGIGKEITEN_TRENNER.match(zeile):
            if angaben:
                liste.append(angaben)
            angaben = {}
            continue
        teile = zeile.split(": ", 1)
        feld = bekannt.get(teile[0].lower()) if len(teile) == 2 else None
        if feld and feld not in angaben:
            angaben[feld] = ([w.strip() for w in teile[1].split(",") if w.strip()] if feld == "License File"
                             else teile[1].strip())
    if angaben:
        liste.append(angaben)
    return liste


def _vorfahren(pfad: str) -> list[str]:
    teile = pfad.split("/")
    return ["/".join(teile[:i]) for i in range(1, len(teile) + 1)]


def drittverzeichnisse(baum: Baum, regeln: Regeln) -> list[str]:
    """Verzeichnisse, die licenses.py als Drittbestandteile betrachtet: jedes direkte Unterverzeichnis eines Ordners
    third_party (nicht unterhalb von ADDITIONAL_PATHS, dorthin steigt licenses.py nicht ab), dazu ADDITIONAL_PATHS
    und die Eintraege von additional_readme_paths.json; ohne PRUNE_PATHS, PRUNE_DIRS und out*."""
    def ausgelassen(d):
        return (d.startswith("out") or any(t in regeln.ohne_abstieg for t in d.split("/"))
                or any(v in regeln.ausgelassen for v in _vorfahren(d)))

    def gefunden(d):
        teile = d.split("/")
        return (len(teile) >= 2 and teile[-2] == "third_party"
                and not any(v in regeln.zusaetzlich for v in _vorfahren(d)[:-1]))

    kandidaten = {posixpath.dirname(p) for p in baum.dateien if posixpath.basename(p) in regeln.metadaten}
    kandidaten |= set(regeln.sonderfaelle)
    gewaehlt = {d for d in kandidaten | regeln.zusaetzlich if not ausgelassen(d) and (gefunden(d) or
                                                                                         d in regeln.zusaetzlich)}
    for _ in range(5):                              # additional_readme_paths.json, auch verschachtelt
        neu = set()
        for pfad in baum.dateien:
            basis = posixpath.dirname(pfad)
            if posixpath.basename(pfad) == ZUSATZPFADE and basis in gewaehlt:
                try:
                    unter = json.loads(baum.text(pfad) or "[]")
                except ValueError:
                    continue
                neu |= {posixpath.normpath(posixpath.join(basis, u)) for u in unter if isinstance(u, str)}
        neu = {d for d in neu if not ausgelassen(d)} - gewaehlt
        if not neu:
            break
        gewaehlt |= neu
    return sorted(gewaehlt)


def _lizenzpfad(verzeichnis: str, datei: str) -> str:
    """Pfad aus "License File": mit / beginnend relativ zur Wurzel (//third_party/...), sonst zum Verzeichnis."""
    if datei.startswith("/"):
        return posixpath.normpath(datei.lstrip("/"))
    return posixpath.normpath(posixpath.join(verzeichnis, datei))


def abhaengigkeit(baum: Baum, verzeichnis: str, angaben: dict) -> tuple[Bestandteil | None, list[str]]:
    """Ein Bestandteil aus README.chromium-Angaben und die Lizenzdateien, die er verlangt. None, wenn er laut
    Angaben nicht ausgeliefert wird (Shipped: no oder License File: NOT_SHIPPED)."""
    angaben = dict(angaben)
    for alias, feld in ALIAS.items():
        if alias in angaben:
            angaben[feld] = angaben.pop(alias)
    dateien = angaben.get("License File") or ["LICENSE"]
    if isinstance(dateien, str):
        dateien = [d.strip() for d in dateien.split(",") if d.strip()]
    if str(angaben.get("Shipped") or "yes").strip().lower() == "no" or NICHT_AUSGELIEFERT in dateien:
        return None, []
    pfade = [_lizenzpfad(verzeichnis, d) for d in dateien]
    vorhanden_ = [p for p in pfade if baum.hat(p)]
    if not vorhanden_ and baum.hat(posixpath.join(verzeichnis, "COPYING")):     # wie licenses.py
        vorhanden_ = [posixpath.join(verzeichnis, "COPYING")]
    texte = [t for t in (baum.text(p) for p in vorhanden_) if t and t.strip()]
    return Bestandteil(teil="Chromium", name=str(angaben.get("Name") or posixpath.basename(verzeichnis)),
                       url=str(angaben.get("URL") or ""), lizenz=str(angaben.get("License") or ""),
                       fundorte=[f"chromium/{verzeichnis}".rstrip("/")], text="\n\n".join(texte) or None,
                       erwartet=[] if texte else pfade), pfade


def chromium_auswerten(baum: Baum) -> tuple[list[Bestandteil], set[str]]:
    """Alle ausgelieferten Chromium-Bestandteile (das Chromium-Projekt selbst zuerst, wie in licenses.py) und alle
    Lizenzdateien, auf die sie verweisen."""
    quelle = next((p for p in LICENSES_PY if baum.hat(p)), None)
    if quelle is None:
        raise Abbruch("tools/licenses/licenses.py fehlt im Chromium-Baum")
    regeln = regeln_lesen(baum.text(quelle) or "")
    je_verzeichnis: dict[str, list[str]] = {}
    for pfad in baum.dateien:
        if posixpath.basename(pfad) in regeln.metadaten:
            je_verzeichnis.setdefault(posixpath.dirname(pfad), []).append(pfad)
    projekt, pfade = abhaengigkeit(baum, "", {"Name": "The Chromium Project", "URL": "https://www.chromium.org",
                                              "License": 'BSD 3-clause "New" or "Revised" License',
                                              "License File": ["//LICENSE"], "Shipped": "yes"})
    liste, noetig = [projekt], set(pfade)
    for verzeichnis in drittverzeichnisse(baum, regeln):
        if verzeichnis in regeln.sonderfaelle:
            bestandteil, pfade = abhaengigkeit(baum, verzeichnis, regeln.sonderfaelle[verzeichnis])
            noetig |= set(pfade)
            # wie licenses.py: ein Sonderfall zaehlt nur, wenn es seine Lizenzdatei gibt (sonst fehlt das Verzeichnis)
            if bestandteil is not None and bestandteil.text:
                liste.append(bestandteil)
            continue
        for readme in sorted(je_verzeichnis.get(verzeichnis, [])):
            for angaben in metadaten_lesen(baum.text(readme) or ""):
                bestandteil, pfade = abhaengigkeit(baum, verzeichnis, angaben)
                noetig |= set(pfade)
                if bestandteil is not None:
                    liste.append(bestandteil)
    return liste, noetig


def chromium_pfad(name: str) -> str | None:
    treffer = CHROMIUM_PFAD.match(name)
    return treffer.group(1) if treffer else None


def chromium_behalten(pfad: str, groesse: int) -> bool:
    name = posixpath.basename(pfad)
    return name in METADATEN or name == ZUSATZPFADE or pfad in LICENSES_PY or lizenzname(pfad, groesse)


def chromium_nachsehen(pfad: str, daten: bytes) -> list[str]:
    """Waehrend des Lesens: die Lizenzdateien, auf die ein gerade gelesenes README.chromium verweist (auch anders
    benannte wie src/README), dazu COPYING wie in licenses.py. Sie kommen so im selben Durchgang mit, wenn sie im
    Archiv hinter dem README stehen (git sortiert Grossbuchstaben vor Kleinbuchstaben, src/ also dahinter)."""
    if posixpath.basename(pfad) not in METADATEN:
        return []
    verzeichnis = posixpath.dirname(pfad)
    pfade = [posixpath.join(verzeichnis, "COPYING")]
    for angaben in metadaten_lesen(als_text(daten) or ""):
        pfade += [_lizenzpfad(verzeichnis, d) for d in angaben.get("License File") or ["LICENSE"]
                  if d != NICHT_AUSGELIEFERT]
    return pfade


# ---------------------------------------------------------------------------------------------------------------
# Qt-Module (qt_attribution.json) und ICU


def qt_archive(modul: str, version: str) -> list[str]:
    xy = ".".join(version.split(".")[:2])
    datei = f"{modul}-everywhere-src-{version}.tar.xz"
    return [f"{DOWNLOAD}/official_releases/qt/{xy}/{version}/submodules/{datei}",
            f"{DOWNLOAD}/archive/qt/{xy}/{version}/submodules/{datei}",
            f"{CODELOAD}/qt/{modul}/tar.gz/refs/tags/v{version}"]


def modulpfad(name: str) -> str | None:
    name = name[2:] if name.startswith("./") else name
    return name.split("/", 1)[1] if "/" in name.strip("/") else None


def qt_behalten(pfad: str, groesse: int) -> bool:
    return (posixpath.basename(pfad) == "qt_attribution.json" or pfad.startswith("LICENSES/")
            or lizenzname(pfad, groesse))


def spdx_kennungen(ausdruck: str) -> list[str]:
    """Lizenzkennungen eines SPDX-Ausdrucks ("FTL OR GPL-2.0-only" -> ["FTL", "GPL-2.0-only"])."""
    return [k for k in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+\-]*", ausdruck) if k not in ("AND", "OR", "WITH")]


def qt_lizenzdateien(basis: str, eintrag: dict) -> list[str]:
    """LicenseFiles bzw. LicenseFile eines Eintrags, relativ zum Ordner der qt_attribution.json."""
    dateien = eintrag.get("LicenseFiles") or ([eintrag["LicenseFile"]] if eintrag.get("LicenseFile") else [])
    return [posixpath.normpath(posixpath.join(basis, d)) for d in dateien if isinstance(d, str)]


def qt_rechtedatei(basis: str, eintrag: dict) -> str | None:
    datei = eintrag.get("CopyrightFile")
    return posixpath.normpath(posixpath.join(basis, datei)) if isinstance(datei, str) and datei else None


def qt_nachsehen(pfad: str, daten: bytes) -> list[str]:
    """Wie chromium_nachsehen, fuer eine gerade gelesene qt_attribution.json: ihre Lizenz- und Copyright-Dateien."""
    if posixpath.basename(pfad) != "qt_attribution.json":
        return []
    try:
        eintraege = json.loads(als_text(daten) or "", strict=False)
    except ValueError:
        return []                                   # meldet qt_auswerten
    basis, pfade = posixpath.dirname(pfad), []
    for eintrag in eintraege if isinstance(eintraege, list) else [eintraege]:
        if isinstance(eintrag, dict):
            pfade += qt_lizenzdateien(basis, eintrag) + list(filter(None, [qt_rechtedatei(basis, eintrag)]))
    return pfade


def qt_auswerten(baum: Baum, modul: str) -> tuple[list[Bestandteil], set[str]]:
    """Drittbestandteile eines Qt-Moduls aus seinen qt_attribution.json (wie Qts qtattributionsscanner):
    LicenseFile(s) relativ zur JSON-Datei, sonst die Texte zu LicenseId unter LICENSES/; Copyright davor."""
    liste, noetig = [], set()
    for pfad in sorted(baum.dateien):
        if posixpath.basename(pfad) != "qt_attribution.json" or QT_AUSGENOMMEN.search(pfad):
            continue
        basis = posixpath.dirname(pfad)
        try:
            daten = json.loads(baum.text(pfad) or "", strict=False)      # Qt erlaubt Zeilenumbrueche in Texten
        except ValueError as e:
            liste.append(Bestandteil("Qt", f"{modul}/{pfad}", "", "", [f"{modul}/{basis}"], None,
                                     [f"{pfad} nicht lesbar: {e}"]))
            continue
        for eintrag in daten if isinstance(daten, list) else [daten]:
            if not isinstance(eintrag, dict):
                continue
            pfade = qt_lizenzdateien(basis, eintrag)
            noetig |= set(pfade)
            if not any(baum.hat(p) for p in pfade) and eintrag.get("LicenseId"):
                pfade += [f"LICENSES/{k}.txt" for k in spdx_kennungen(str(eintrag["LicenseId"]))]
            texte = [t for t in (baum.text(p) for p in pfade if baum.hat(p)) if t and t.strip()]
            rechte = eintrag.get("Copyright") or ""
            rechte = "\n".join(map(str, rechte)) if isinstance(rechte, list) else str(rechte)
            datei = qt_rechtedatei(basis, eintrag)
            if datei:
                noetig.add(datei)
                rechte = "\n".join(filter(None, [rechte, baum.text(datei) or ""]))
            ort = posixpath.join(basis, eintrag["Path"]) if isinstance(eintrag.get("Path"), str) else basis
            # BSD/MIT verlangen den Copyright-Vermerk; oft steht er nur in der JSON-Datei, sonst schon im Text
            zusatz = [z.strip() for z in rechte.splitlines() if z.strip() and z.strip() not in "\n".join(texte)]
            if texte and zusatz:
                texte.insert(0, "\n".join(zusatz))
            liste.append(Bestandteil(
                teil="Qt", name=str(eintrag.get("Name") or eintrag.get("Id") or basis),
                url=str(eintrag.get("Homepage") or eintrag.get("DownloadLocation") or ""),
                lizenz=str(eintrag.get("License") or eintrag.get("LicenseId") or ""), fundorte=[f"{modul}/{ort}"],
                text="\n\n".join(texte) or None,
                erwartet=[] if texte else [f"{modul}/{p}" for p in pfade] or ["(keine Lizenzdatei angegeben)"]))
    return liste, noetig


def qt_lesen(modul: str, version: str) -> tuple[str, list[Bestandteil]]:
    """Quellarchiv des Moduls in genau dieser Version (download.qt.io, sonst GitHub-Tag) und seine Bestandteile."""
    gesehen = []
    for url in qt_archive(modul, version):
        try:
            if not vorhanden(url):
                gesehen.append(f"{url}: gibt es nicht")
                continue
        except Abbruch as e:
            gesehen.append(f"nicht erreichbar ({e})")
            continue
        print(f"Qt: {url}", flush=True)
        baum = baum_lesen(url, modulpfad, qt_behalten, lambda b: qt_auswerten(b, modul)[1], qt_nachsehen)
        return url, qt_auswerten(baum, modul)[0]
    raise Abbruch(f"kein Quellarchiv von {modul} {version} gefunden:\n  " + "\n  ".join(gesehen))


def icu_lesen(version: str) -> tuple[str, Bestandteil]:
    """Lizenz der ICU, die Qt mitbringt, aus unicode-org/icu (Tag release-73-2; nur Hauptversion: release-73-1)."""
    tag = "release-" + (version.replace(".", "-") if "." in version else f"{version}-1")
    url = f"{GITHUB_ROH}/unicode-org/icu/{tag}/icu4c/LICENSE"
    text = text_holen(url)
    if not text or not text.strip():
        raise Abbruch(f"Lizenz von ICU {version} nicht gefunden: {url}")
    return url, Bestandteil(teil="ICU", name=f"ICU {version} (International Components for Unicode, von Qt)",
                            url="https://icu.unicode.org", lizenz="Unicode-3.0 und weitere (siehe Text)",
                            fundorte=[f"unicode-org/icu {tag}: icu4c/LICENSE"], text=text)


# ---------------------------------------------------------------------------------------------------------------
# Ausgabe


def zusammenfassen(bestandteile: list[Bestandteil]) -> list[Bestandteil]:
    """Gleicher Bestandteil (Name, Lizenz, Text) an mehreren Fundorten nur einmal."""
    gesehen: dict[tuple, Bestandteil] = {}
    for b in bestandteile:
        schluessel = (b.teil, b.name.lower(), b.url, b.lizenz, normtext(b.text) if b.text else tuple(b.erwartet))
        if schluessel in gesehen:
            gesehen[schluessel].fundorte += [f for f in b.fundorte if f not in gesehen[schluessel].fundorte]
        else:
            gesehen[schluessel] = Bestandteil(b.teil, b.name, b.url, b.lizenz, list(b.fundorte), b.text,
                                              list(b.erwartet))
    return list(gesehen.values())


def ausgabe(v: Versionen, quellen: list[str], bestandteile: list[Bestandteil], genau: bool = True) -> str:
    """Text der Datei: Kopf (Versionen, Quellen, Anzahlen fuer bauen.lizenzbericht), Uebersicht, dann jeder
    verschiedene Lizenztext einmal mit allen Bestandteilen, die ihn nutzen, zuletzt die Bestandteile ohne Text.
    genau=False: die Chromium-Quelle weicht in der Patch-Nummer ab (steht in der Zeile "Quelle Chromium")."""
    bestandteile = zusammenfassen(bestandteile)
    gruppen: dict[str, list[Bestandteil]] = {}
    for b in bestandteile:
        if b.text:
            gruppen.setdefault(normtext(b.text), []).append(b)
    nummer = {id(b): n for n, liste in enumerate(gruppen.values(), 1) for b in liste}
    ohne = [b for b in bestandteile if not b.text]
    je_teil = {t: sum(1 for b in bestandteile if b.teil == t) for t in ("Chromium", "Qt", "ICU")}

    def zeile(b: Bestandteil) -> str:
        return " – ".join(filter(None, [b.name, b.url, b.lizenz, ", ".join(b.fundorte)]))

    kopf = ["pdf2md – Lizenzen von Chromium (in Qt WebEngine) und der Bestandteile Dritter in Qt", "",
            "Das Linux-Paket enthält Qt for Python (PySide6) mit Qt WebEngine, und Qt WebEngine enthält Chromium. Hier",
            "stehen die Lizenztexte von Chromium und aller Bestandteile Dritter, die Chromium und Qt mitbringen,",
            "vollständig. Erzeugt mit werkzeuge/chromium_lizenzen.py aus den Quellen "
            + ("genau der mitgelieferten Fassungen." if genau else "der mitgelieferten Fassungen (Chromium: siehe unten)."),
            "Chromium nach den Regeln seiner tools/licenses/licenses.py (alle Bestandteile, die ausgeliefert werden",
            "können), Qt nach seinen qt_attribution.json. Die Liste ist eine Obermenge dessen, was unter Linux gebaut",
            "wird.", "",
            f"Qt: {v.qt}", f"Qt WebEngine: {v.webengine}",
            f"Chromium: {v.chromium}, Sicherheitskorrekturen bis Chromium {v.sicherheit}",
            *([f"ICU (von Qt): {v.icu}"] if v.icu else []), *quellen,
            f"Bestandteile: {len(bestandteile)} (" + ", ".join(f"{t} {n}" for t, n in je_teil.items() if n) + ")",
            f"Verschiedene Lizenztexte: {len(gruppen)}", f"Ohne Lizenztext: {len(ohne)}", "",
            "Übersicht (Bestandteil – Lizenzangabe – Nummer des Lizenztextes unten)"]
    kopf += [f"  {b.teil}: {b.name} – {b.lizenz or 'ohne Angabe'} – "
             + (f"[{nummer[id(b)]}]" if b.text else "Lizenztext fehlt") for b in bestandteile]
    teile = ["\n".join(kopf), ""]
    for n, (text, liste) in enumerate(gruppen.items(), 1):
        teile += [TRENNER, f"[{n}] gilt für:", *[f"  {b.teil}: {zeile(b)}" for b in liste], TRENNER, text, ""]
    teile += [TRENNER, "Ohne Lizenztext in der Quelle (gesuchte Dateien gibt es dort nicht)", TRENNER]
    teile += [f"  {b.teil}: {zeile(b)}; gesucht: {', '.join(b.erwartet)}" for b in ohne] or ["  (keine)"]
    return "\n".join(teile) + "\n"


def erzeugen(ziel: Path, v: Versionen | None = None) -> str:
    v = v or versionen()
    print(f"Qt {v.qt}, Qt WebEngine {v.webengine}, Chromium {v.chromium} (Sicherheitsstand {v.sicherheit}), "
          f"ICU {v.icu or '-'}", flush=True)
    beschreibung, archiv, abweichung = chromium_quelle(v)
    print(f"Chromium: {beschreibung} -> {archiv}" + (f" (Chromium {abweichung})" if abweichung else ""), flush=True)
    baum = baum_lesen(archiv, chromium_pfad, chromium_behalten, lambda b: chromium_auswerten(b)[1],
                      chromium_nachsehen)
    bestandteile = chromium_auswerten(baum)[0]
    if not bestandteile[0].text or "The Chromium Authors" not in bestandteile[0].text:
        raise Abbruch(f"{archiv}: Lizenz des Chromium-Projekts (chromium/LICENSE) fehlt")
    quellen = [f"Quelle Chromium: {beschreibung}" + (f" ({archiv})" if archiv != beschreibung else "")
               + ("; CHROMIUM_VERSION stimmt mit der Bibliothek überein" if not abweichung else
                  f"; CHROMIUM_VERSION der Quelle nennt Chromium {abweichung}, die Bibliothek {v.chromium}: gleicher "
                  f"Sicherheitsstand {v.sicherheit}, nur die Patch-Nummer weicht ab (eine Quelle mit genau diesem "
                  "Stand gibt es nicht)")]
    for modul in QT_MODULE:
        url, liste = qt_lesen(modul, v.qt)
        quellen.append(f"Quelle Qt ({modul}): {url}")
        bestandteile += liste
    if v.icu:
        url, icu = icu_lesen(v.icu)
        quellen.append(f"Quelle ICU: {url}")
        bestandteile.append(icu)
    text = ausgabe(v, quellen, bestandteile, genau=not abweichung)
    ziel.write_text(text, encoding="utf-8", newline="\n")
    kopf = text.split("\n\nÜbersicht", 1)[0]
    print(f"{ziel}: {ziel.stat().st_size // 1024} KB; "
          + "; ".join(z for z in kopf.splitlines() if z.startswith(("Bestandteile:", "Ohne Lizenztext:"))), flush=True)
    return text


def main(argumente: list[str]) -> int:
    try:
        if argumente == ["--versionen"]:
            print(versionsschluessel(versionen()))
            return 0
        if len(argumente) != 1 or argumente[0].startswith("-"):
            print("Aufruf: python werkzeuge/chromium_lizenzen.py <zieldatei> | --versionen", file=sys.stderr)
            return 2
        erzeugen(Path(argumente[0]))
        return 0
    except Abbruch as e:
        print(f"chromium_lizenzen: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
