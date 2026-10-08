"""Baut pdf2md mit PyInstaller fuer das laufende System, startet das Ergebnis einmal zur Probe und schnuert das Paket.

Aufruf (Werkzeug fuer den Build, nicht fuers Programm selbst):
  python werkzeuge/bauen.py [ausgabe]                     bauen (Standard: dist)
  python werkzeuge/bauen.py starttest [ausgabe]           gebautes Programm starten, Oberflaeche pruefen, schliessen
  python werkzeuge/bauen.py paket NAME TAG [ausgabe]      Paket pdf2md-TAG-NAME.zip bzw. .tar.xz im Projektordner
  python werkzeuge/bauen.py hinweise NAME                 Ergebnisse als GitHub-Hinweise ausgeben (bauen.yml)

Windows: eine pdf2md.exe (WebView2). macOS: pdf2md.app (WebKit; PyInstaller signiert ad hoc, nicht notarisiert).
Linux: Ordner pdf2md/ mit QtWebEngine ueber PySide6 (LGPL: Ordner statt einer Datei, damit die Qt-Bibliotheken
austauschbar bleiben). Der Start-Test setzt PDF2MD_STARTTEST (ui_app._starttest) und eine Ablage im Temp-Ordner;
unter Linux ohne Bildschirm laeuft er in xvfb-run. Gebaut wird fuer Releases nur auf GitHub (bauen.yml)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SYSTEM = sys.platform           # Tests setzen es um
STARTTEST_ZEIT = 240            # Sekunden; so lange darf der Start-Test hoechstens dauern


def windows() -> bool:
    return SYSTEM == "win32"


def mac() -> bool:
    return SYSTEM == "darwin"


def pyinstaller_argumente(ausgabe: Path, arbeit: Path) -> list[str]:
    def daten(quelle: Path, ziel: str) -> list[str]:
        return ["--add-data", f"{quelle}{os.pathsep}{ziel}"]
    args = ["--noconfirm", "--windowed", "--name", "pdf2md",
            "--collect-all", "markitdown", "--collect-all", "magika",
            "--collect-all", "pypdfium2", "--collect-all", "pypdfium2_raw",
            *daten(WURZEL / "schriften", "schriften"), *daten(WURZEL / "ui" / "web", "ui/web"),
            "--distpath", str(ausgabe), "--workpath", str(arbeit), "--specpath", str(arbeit)]
    if windows():
        # pywebview laedt die Plattform-Module und pythonnet erst zur Laufzeit: ausdruecklich mitnehmen
        args += ["--onefile", "--collect-all", "pythonnet", "--collect-all", "clr_loader",
                 "--hidden-import", "webview.platforms.edgechromium", "--hidden-import", "webview.platforms.winforms"]
    elif mac():
        args += ["--hidden-import", "webview.platforms.cocoa", "--osx-bundle-identifier", "io.github.s4ltc.pdf2md"]
    else:
        # nur die Qt-Module, die pywebview braucht (alle qtpy-Untermodule zogen 3D, Multimedia usw. mit: 346 statt 323 MB)
        args += ["--hidden-import", "webview.platforms.qt"]
        for modul in ("QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtWebChannel", "QtWebEngineCore",
                      "QtWebEngineWidgets"):
            args += ["--hidden-import", f"qtpy.{modul}", "--hidden-import", f"PySide6.{modul}"]
        # libQt6WebEngineCore braucht Qt Quick und QML als Bibliotheken (die kommen ueber die Abhaengigkeiten mit),
        # das Fenster aber keine QML-Module. Ueber die Python-Module QtQml/QtQuick zog PyInstaller alle QML-Module
        # samt ihrer Bibliotheken mit (Quick 3D, Controls-Stile, Graphs, Qt 3D, ...).
        for modul in ("QtQml", "QtQuick", "QtQuickWidgets"):
            args += ["--exclude-module", f"PySide6.{modul}"]
    return args + [str(WURZEL / "ui_app.py")]


def programm(ausgabe: Path) -> Path:
    if windows():
        return ausgabe / "pdf2md.exe"
    if mac():
        return ausgabe / "pdf2md.app" / "Contents" / "MacOS" / "pdf2md"
    return ausgabe / "pdf2md" / "pdf2md"


def bauen(ausgabe: Path) -> int:
    arbeit = Path(tempfile.gettempdir()) / "pdf2md-build"
    code = subprocess.run([sys.executable, "-m", "PyInstaller", *pyinstaller_argumente(ausgabe, arbeit)]).returncode
    if code == 0 and not windows() and not mac():
        gespart, entfernt = aufraeumen(ausgabe)
        bericht = {"gespart_mb": round(gespart / 1e6, 1), "entfernt": entfernt}
        (WURZEL / "aufgeraeumt.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(bericht, ensure_ascii=False, indent=1))
    return code


# Sprachen, die im Linux-Paket bleiben: Chromium faellt ohne passende Sprachdatei auf en-US zurueck, Qt laedt seine
# Uebersetzungen nur auf Anfrage (pdf2md fragt nie danach)
SPRACHEN = ("de", "en", "en-US")
# Qt-Plugins, die das Fenster nicht braucht und die Bibliotheken des Build-Systems mitziehen. Das GTK-Thema bringt
# GTK, Pango, Cairo usw. von Ubuntu 22.04 mit; auf einem anderen System liefen die gegen dessen GTK-, GIO- und
# Thema-Module. Ohne das Plugin nimmt Qt sein eigenes Aussehen (betrifft nur den Dateidialog, das Fenster ist HTML).
UNNOETIGE_PLUGINS = ("platformthemes/libqgtk3.so",)
ELF_NEEDED = re.compile(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]")


def benoetigt(datei: Path) -> list[str] | None:
    """Bibliotheken, die eine ELF-Datei beim Laden braucht (DT_NEEDED, ueber readelf); None, wenn keine ELF-Datei."""
    with open(datei, "rb") as f:
        if f.read(4) != b"\x7fELF":
            return None
    lauf = subprocess.run(["readelf", "-d", str(datei)], capture_output=True, text=True, errors="replace")
    return ELF_NEEDED.findall(lauf.stdout)


def nur_ueber(ordner: Path, weg: list[Path], abhaengigkeiten=None) -> list[Path]:
    """Bibliotheken im Ordner, die nur die Dateien in `weg` brauchen (auch ueber Zwischenstufen) und damit mit ihnen
    entfallen koennen. Was irgendeine andere Datei im Ordner braucht, bleibt; ebenso alles, was nur zur Laufzeit
    nachgeladen wird (dlopen), denn das steht in keiner Abhaengigkeit von `weg`."""
    abhaengigkeiten = abhaengigkeiten or benoetigt
    elf = {}
    for datei in ordner.rglob("*"):
        if datei.is_file() and not datei.is_symlink():
            namen = abhaengigkeiten(datei)
            if namen is not None:
                elf[datei.resolve()] = namen
    nach_name: dict[str, set[Path]] = {}
    for eintrag in ordner.rglob("*"):                  # auch Verknuepfungen (PyInstaller legt sie unter Linux an)
        if eintrag.resolve() in elf:
            nach_name.setdefault(eintrag.name, set()).add(eintrag.resolve())

    def huelle(start: set[Path]) -> set[Path]:
        gesehen, offen = set(), list(start)
        while offen:
            datei = offen.pop()
            if datei not in gesehen:
                gesehen.add(datei)
                for name in elf.get(datei, []):
                    offen.extend(nach_name.get(name, ()))
        return gesehen
    weg_menge = {p.resolve() for p in weg}
    kandidaten = huelle(weg_menge) - weg_menge
    return sorted(kandidaten - huelle(set(elf) - weg_menge - kandidaten))


def aufraeumen(ausgabe: Path) -> tuple[int, list[str]]:
    """Entfernt aus dem Linux-Programmordner, was das Fenster nicht braucht. Ergebnis: gesparte Bytes und die Namen
    entfernter Plugins und Bibliotheken. Gemessen (Paketbericht): 45 MB Sprachdateien von Chromium, 10 MB
    Qt-Uebersetzungen, libpython mit 31 MB Debug-Informationen, GTK des Build-Systems. Die Entwicklerwerkzeuge
    (qtwebengine_devtools_resources.pak) bleiben: ob Qt WebEngine ohne sie startet, ist nicht belegt."""
    intern = ausgabe / "pdf2md" / "_internal"
    qt = intern / "PySide6" / "Qt"
    weg = [p for p in (qt / "translations" / "qtwebengine_locales").glob("*.pak") if p.stem not in SPRACHEN]
    weg += [p for p in (qt / "translations").glob("*.qm") if p.stem.rpartition("_")[2] not in SPRACHEN]
    plugins = [qt / "plugins" / p for p in UNNOETIGE_PLUGINS if (qt / "plugins" / p).is_file()]
    bibliotheken = nur_ueber(intern, plugins) if plugins and shutil.which("readelf") else []
    verweise = [p for p in intern.rglob("*") if p.is_symlink() and p.resolve() in set(bibliotheken)]
    gespart = sum(p.stat().st_size for p in weg + plugins + bibliotheken)
    for datei in weg + plugins + bibliotheken + verweise:
        datei.unlink()
    for bibliothek in intern.glob("libpython3*.so*"):
        # nur die Debug-Informationen: die Symbole braucht der Starter von PyInstaller (dlopen/dlsym)
        if shutil.which("strip") and bibliothek.is_file() and not bibliothek.is_symlink():
            groesse = bibliothek.stat().st_size
            if subprocess.run(["strip", "--strip-debug", str(bibliothek)]).returncode == 0:
                gespart += groesse - bibliothek.stat().st_size
    return gespart, sorted(p.name for p in plugins + bibliotheken)


def starttest(ausgabe: Path, bericht: Path) -> int:
    """Startet das gebaute Programm mit PDF2MD_STARTTEST und wertet das Ergebnis aus. 0 = Oberflaeche hat sich
    gemeldet (Engine, Seite und Python-Schnittstelle laufen)."""
    with tempfile.TemporaryDirectory() as tmp:
        ergebnis = Path(tmp) / "ergebnis.json"
        env = {**os.environ, "PDF2MD_ABLAGE": str(Path(tmp) / "ablage"), "PDF2MD_STARTTEST": str(ergebnis)}
        befehl = [str(programm(ausgabe))]
        if not windows() and not mac() and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
            befehl = ["xvfb-run", "-a", "-s", "-screen 0 1280x1024x24"] + befehl
        try:
            lauf = subprocess.run(befehl, env=env, capture_output=True, text=True, errors="replace",
                                  timeout=STARTTEST_ZEIT)
            ausgabe_text, code = (lauf.stdout or "") + (lauf.stderr or ""), lauf.returncode
        except subprocess.TimeoutExpired:
            ausgabe_text, code = f"Zeitlimit {STARTTEST_ZEIT} s ueberschritten", None
        except OSError as e:
            ausgabe_text, code = f"Start nicht moeglich: {e}", None
        daten = (json.loads(ergebnis.read_text(encoding="utf-8")) if ergebnis.exists()
                 else {"ok": False, "fehler": "kein Ergebnis vom Programm"})
    daten.update(rueckgabe=code, ausgabe=ausgabe_text[-3000:])
    bericht.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(daten, ensure_ascii=False, indent=1))
    return 0 if daten.get("ok") else 1


def drittlizenzen(ziel: Path) -> None:
    subprocess.run([sys.executable, str(WURZEL / "werkzeuge" / "drittlizenzen.py"), str(ziel)], check=True)


TRENNER = re.compile(r"^={79}$", re.MULTILINE)      # wie in drittlizenzen.py
LGPL3 = re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3", re.IGNORECASE)


def lizenzbericht(ordner: Path) -> dict:
    """Bericht ueber DRITTLIZENZEN.txt, damit sich ein Paket ohne Download pruefen laesst (Hinweis am Lauf): Eintraege
    der Uebersicht, Pakete ohne eigenen Lizenztext, ob der volle Text der LGPL 3 dabei ist (Qt unter Linux) und wie
    lang die Texte der Qt-Pakete sind. Ein blosses Vorkommen von "LGPL" reicht nicht: die Python-Lizenz nennt sie
    schon (xz)."""
    text = (ordner / "DRITTLIZENZEN.txt").read_text(encoding="utf-8", errors="replace")
    teile = TRENNER.split(text)                        # Uebersicht, Kopf 1, Inhalt 1, Kopf 2, Inhalt 2, ...
    abschnitte = {teile[i].strip(): teile[i + 1] for i in range(1, len(teile) - 1, 2)}
    return {"eintraege": sum(1 for z in teile[0].splitlines() if " – " in z),
            "ohne_lizenztext": [k for k, inhalt in abschnitte.items() if "(kein Lizenztext im Paket" in inhalt],
            "nur_standardtext": [k for k, inhalt in abschnitte.items() if "--- Standardtext" in inhalt],
            "lgpl3_volltext": bool(LGPL3.search(text)),
            "qt_lizenztext_zeichen": {k: len(inhalt.strip()) for k, inhalt in abschnitte.items()
                                      if k.lower().startswith(("pyside6", "shiboken6"))}}


def groessenbericht(ordner: Path, anzahl: int = 50) -> dict:
    """Wo die Groesse eines Pakets steckt: entpackt gesamt, groesste Dateien und Ordner (je direkter Ordner)."""
    dateien = [(p.relative_to(ordner).as_posix(), p.stat().st_size) for p in ordner.rglob("*")
               if p.is_file() and not p.is_symlink()]
    je_ordner: dict[str, int] = {}
    for name, groesse in dateien:
        oberordner = name.rpartition("/")[0] or "."
        je_ordner[oberordner] = je_ordner.get(oberordner, 0) + groesse
    def mb(paare, n):                                  # eine Zeile je Eintrag, damit der Hinweis lesbar bleibt
        return [f"{groesse / 1e6:6.1f} MB  {name}" for name, groesse in sorted(paare, key=lambda x: -x[1])[:n]]
    return {"entpackt_mb": round(sum(g for _, g in dateien) / 1e6, 1), "dateien": len(dateien),
            "groesste_dateien": mb(dateien, anzahl), "groesste_ordner": mb(je_ordner.items(), 15)}


def paket(name: str, tag: str, ausgabe: Path, ziel_ordner: Path = WURZEL) -> Path:
    """pdf2md-TAG-NAME.zip (Windows, macOS) bzw. .tar.xz (Linux) mit Programm, Lizenz, Fremdlizenzen und LIESMICH."""
    ordner = Path(tempfile.mkdtemp()) / "pdf2md"        # macOS: oberster Ordner im ZIP (ditto --keepParent)
    ordner.mkdir()
    if windows():
        shutil.copy2(programm(ausgabe), ordner / "pdf2md.exe")
    elif mac():
        shutil.copytree(ausgabe / "pdf2md.app", ordner / "pdf2md.app", symlinks=True)
    else:
        shutil.copytree(ausgabe / "pdf2md", ordner / "pdf2md", symlinks=True)
    shutil.copy2(WURZEL / "LICENSE", ordner / "LICENSE.txt")
    shutil.copy2(WURZEL / "docs" / "LIESMICH.txt", ordner / "LIESMICH.txt")
    drittlizenzen(ordner / "DRITTLIZENZEN.txt")
    lizenzen, groessen = lizenzbericht(ordner), groessenbericht(ordner)
    archiv = _packen(ordner, ziel_ordner / f"pdf2md-{tag}-{name}")
    bericht = {"archiv": archiv.name, "groesse_mb": round(archiv.stat().st_size / 1e6, 1) if archiv.exists() else None,
               **lizenzen, **groessen}                 # das Wichtigste zuerst, falls ein Hinweis gekuerzt wird
    (ziel_ordner / "paket.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
    return archiv


def _packen(ordner: Path, stamm: Path) -> Path:
    if windows():
        return Path(shutil.make_archive(str(stamm), "zip", ordner))
    if mac():
        archiv = Path(f"{stamm}.zip")                  # nicht with_suffix: die Versionsnummer enthaelt Punkte
        # ditto statt zipfile: erhaelt Verknuepfungen und Rechte im App-Paket
        subprocess.run(["ditto", "-c", "-k", "--keepParent", "--sequesterRsrc", str(ordner), str(archiv)], check=True)
        return archiv
    archiv = Path(f"{stamm}.tar.xz")             # xz statt gzip: Qt WebEngine packt sich damit deutlich kleiner
    def ausfuehrbar(info: tarfile.TarInfo) -> tarfile.TarInfo:
        if info.name == "pdf2md/pdf2md":                  # auch wenn das Paket nicht unter Linux entsteht
            info.mode |= 0o755
        return info
    with tarfile.open(archiv, "w:xz") as tar:
        for eintrag in sorted(ordner.iterdir()):
            tar.add(eintrag, arcname=eintrag.name, filter=ausfuehrbar)
    return archiv


HINWEIS_LAENGE = 3000      # GitHub kuerzt einen Hinweis nach rund 4000 Zeichen (gemessen: 4062), laengere werden geteilt


def hinweise(name: str, wurzel: Path = WURZEL) -> list[str]:
    """Ergebnis von Start-Test und Paket als GitHub-Hinweise (::notice), ohne Anmeldung ueber die API lesbar."""
    test = wurzel / "starttest.json"
    if test.exists():
        d = json.loads(test.read_text(encoding="utf-8"))
        kurz = {k: d.get(k) for k in ("gui", "angezeigt", "fehler", "rueckgabe")}
        meldungen = [(f"Start-Test {name}", ("OK " if d.get("ok") else "FEHLER ") + json.dumps(kurz, ensure_ascii=False)
                      + "\n" + (d.get("ausgabe") or "")[-2500:])]
    else:
        meldungen = [(f"Start-Test {name}", "nicht gelaufen (Build fehlgeschlagen?)")]
    for datei, titel in (("aufgeraeumt.json", "Aufgeraeumt"), ("paket.json", "Paket")):
        if (wurzel / datei).exists():
            text = (wurzel / datei).read_text(encoding="utf-8")
            teile = [text[i:i + HINWEIS_LAENGE] for i in range(0, len(text), HINWEIS_LAENGE)]
            meldungen += [(f"{titel} {name}" + (f" ({n}/{len(teile)})" if len(teile) > 1 else ""), teil)
                          for n, teil in enumerate(teile, 1)]
    def maskiert(text: str) -> str:
        return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return [f"::notice title={maskiert(titel)}::{maskiert(text)}" for titel, text in meldungen]


def main(argumente: list[str]) -> int:
    if argumente[:1] == ["hinweise"]:
        sys.stdout.reconfigure(encoding="utf-8")       # Windows-Runner: sonst cp1252 und kein „–“
        print("\n".join(hinweise(argumente[1])))
        return 0
    if argumente[:1] == ["starttest"]:
        ausgabe = Path(argumente[1]) if len(argumente) > 1 else WURZEL / "dist"
        return starttest(ausgabe, WURZEL / "starttest.json")
    if argumente[:1] == ["paket"]:
        ausgabe = Path(argumente[3]) if len(argumente) > 3 else WURZEL / "dist"
        print(paket(argumente[1], argumente[2], ausgabe))
        return 0
    ausgabe = Path(argumente[0]) if argumente else WURZEL / "dist"
    return bauen(ausgabe)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
