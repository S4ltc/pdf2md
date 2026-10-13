"""Was je Betriebssystem anders ist: Anzeige-Engine, Dateien oeffnen, ein Fenster je Ordner, helles oder dunkles
Thema, Meldung ohne Fenster, der Ort der Ablage und die Umgebung fuer Programme des Systems.

Windows ist das Zielsystem der .exe und von Hand geprueft. macOS und Linux sind vorbereitet: die Tests laufen dort
bei jedem Push auf GitHub (.github/workflows/tests.yml), das Fenster selbst ist auf diesen Systemen nicht von Hand
geprueft. Anzeige: Windows WebView2 (edgechromium), macOS WebKit (cocoa), Linux QtWebEngine (qt, mit PySide6) oder
WebKitGTK (gtk, Systempaket). SYSTEM ist austauschbar, damit sich alle Zweige auch unter Windows testen lassen."""
from __future__ import annotations

import errno
import hashlib
import html
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

SYSTEM = sys.platform           # "win32", "darwin" (macOS), "linux"
_GRIFFE: list = []              # Mutex (Windows) bzw. offene Sperrdateien: halten, solange das Programm laeuft
SPERRDATEI = ".pdf2md.lock"     # in der Ablage (macOS/Linux, einzelinstanz); steht in .gitignore
_EIGENE: dict = {}              # Variablen aus vorbereiten(): nicht an Programme des Systems weitergeben
OEFFNEN_WARTEN = 2.0            # Sekunden Warten auf open/xdg-open; laeuft es laenger, gilt es als geoeffnet


def windows() -> bool:
    return SYSTEM == "win32"


def mac() -> bool:
    return SYSTEM == "darwin"


def _vorhanden(modul: str) -> bool:
    try:
        return importlib.util.find_spec(modul) is not None
    except (ImportError, ValueError):
        return False


def gui() -> str:
    """Anzeige-Engine fuer pywebview.start(gui=...)."""
    if windows():
        return "edgechromium"
    if mac():
        return "cocoa"
    return "qt" if _vorhanden("PySide6") else "gtk"


def vorbereiten() -> None:
    """Vor dem Start des Fensters. Linux: Ubuntu sperrt ab 23.10 die Sandbox von QtWebEngine (Chromium) fuer Programme
    ohne AppArmor-Profil, das Fenster bliebe leer oder startete nicht. Es laedt nur die eigenen lokalen Dateien der
    Oberflaeche, nie Seiten aus dem Netz; deshalb wird die Sandbox abgeschaltet (eine eigene Einstellung bleibt).

    Gebaute App unter macOS/Linux: urllib (Crossref, DNB, Update-Suche) nimmt das mitgelieferte OpenSSL, und das sucht
    die Wurzelzertifikate dort, wo sie auf dem Build-Rechner lagen (python.org-Python bzw. Ubuntu 22.04). Auf einem
    normalen Mac und unter Fedora oder Arch liegen dort keine; jede HTTPS-Anfrage scheiterte still am Zertifikat (das
    Programm macht dann ohne Online-Daten und ohne Update-Hinweis weiter). SSL_CERT_FILE zeigt deshalb auf die
    Zertifikate von certifi, die im Paket liegen. Das Zertifikatsverzeichnis des Systems gilt zusaetzlich weiter
    (OpenSSL liest Datei und Verzeichnis), eine eigene Einstellung des Nutzers bleibt."""
    if not windows() and not mac():
        _setzen("QTWEBENGINE_DISABLE_SANDBOX", "1")
    if getattr(sys, "frozen", False) and not windows():
        zertifikate = _zertifikate()
        if zertifikate:
            _setzen("SSL_CERT_FILE", zertifikate)


def _setzen(name: str, wert: str) -> None:
    """Wie os.environ.setdefault, merkt sich aber, was gesetzt wurde: fremde_umgebung() nimmt es wieder heraus."""
    if name not in os.environ:
        os.environ[name] = wert
        _EIGENE[name] = wert


def _zertifikate() -> str | None:
    """Datei mit den Wurzelzertifikaten von certifi, falls certifi da ist und die Datei mit ins Paket kam."""
    try:
        import certifi
        datei = certifi.where()
    except Exception:
        return None
    return datei if datei and os.path.isfile(datei) else None


def fremde_umgebung() -> dict:
    """Umgebung fuer Programme des Systems (open, xdg-open, gsettings, xdg-user-dir, Dialoge und was diese starten):
    eine Kopie von os.environ ohne die Variablen aus vorbereiten() (ein Qt-Programm des Nutzers liefe sonst ohne
    Sandbox). In der gebauten App unter Linux setzt der Starter von PyInstaller LD_LIBRARY_PATH auf den Programmordner
    (das Original steht in LD_LIBRARY_PATH_ORIG) und der Qt-Teil QT_PLUGIN_PATH und QML2_IMPORT_PATH auf das Qt im
    Paket. So geerbt luden xdg-open, Dateimanager oder Browser die alten Bibliotheken aus Ubuntu 22.04 statt der
    eigenen. Deshalb kommt LD_LIBRARY_PATH zurueck auf das Original (ohne Original: entfernt, wie in der
    PyInstaller-Doku "Run-time Information" empfohlen), und Eintraege, die ins Paket zeigen, fallen weg."""
    umgebung = dict(os.environ)
    for name, wert in _EIGENE.items():
        if umgebung.get(name) == wert:
            del umgebung[name]
    if not getattr(sys, "frozen", False) or windows():
        return umgebung
    if not mac():
        original = umgebung.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            umgebung["LD_LIBRARY_PATH"] = original
        else:
            umgebung.pop("LD_LIBRARY_PATH", None)
    paket = getattr(sys, "_MEIPASS", None)
    if paket:
        paket = os.path.realpath(paket)
        for name, wert in list(umgebung.items()):
            teile = wert.split(os.pathsep)
            rest = [t for t in teile if not _im_ordner(t, paket)]
            if len(rest) < len(teile):
                if any(rest):
                    umgebung[name] = os.pathsep.join(rest)
                else:
                    del umgebung[name]
    return umgebung


def _im_ordner(eintrag: str, ordner: str) -> bool:
    if not eintrag or not os.path.isabs(eintrag):
        return False
    pfad = os.path.realpath(eintrag)
    return pfad == ordner or pfad.startswith(ordner.rstrip(os.sep) + os.sep)


def oeffnen(pfad: Path) -> None:
    """Datei oder Ordner mit dem Standardprogramm oeffnen (PDF-Leser, Editor, Explorer/Finder/Dateimanager). Geht das
    nicht, kommt OSError mit verstaendlichem Text; das Fenster zeigt ihn an."""
    if windows():
        os.startfile(str(pfad))
    else:
        _starten(str(pfad))


def adresse_oeffnen(adresse: str) -> None:
    """Internetseite im Standardbrowser oeffnen; geht das nicht, kommt OSError mit dem Grund. macOS/Linux ueber open
    bzw. xdg-open mit fremde_umgebung(): das Modul webbrowser gaebe dem Browser die Umgebung der App mit (Linux:
    Bibliotheken aus dem Paket). Fehlt xdg-open (Linux ohne xdg-utils), sucht webbrowser selbst einen Browser (gio,
    x-www-browser, firefox, ...); der erbt dann zwar die Umgebung der App, aber das ist besser als gar keine Seite.
    Windows wie bisher ueber webbrowser; findet es keinen Browser, kommt jetzt ebenfalls OSError."""
    if windows():
        _browser(adresse, OSError("kein Browser gefunden"))
        return
    try:
        _starten(adresse)
    except FileNotFoundError as fehlt:
        _browser(adresse, fehlt)


def _browser(adresse: str, fehler: OSError) -> None:
    """Seite ueber das Modul webbrowser; findet es keinen Browser (Rueckgabe False), kommt fehler."""
    import webbrowser
    try:
        geoeffnet = webbrowser.open(adresse)
    except webbrowser.Error:
        geoeffnet = False
    if not geoeffnet:
        raise fehler


def _starten(ziel: str) -> None:
    """open (macOS) bzw. xdg-open (Linux) mit ziel. Beide kehren sonst gleich zurueck, ein Rueckgabewert ungleich 0
    heisst: nichts geoeffnet. Ohne Desktopumgebung wartet xdg-open aber, bis das gestartete Programm endet: laeuft es
    laenger als OEFFNEN_WARTEN, gilt es als geoeffnet, und ein Hintergrund-Thread holt den Prozess ab, sobald er endet
    (sonst bliebe ein Zombie). Fehlt das Programm, kommt FileNotFoundError (adresse_oeffnen weicht dann aus); laesst
    es sich aus einem anderen Grund nicht starten (keine Ausfuehrungsrechte, zu wenig Speicher), OSError mit Grund."""
    programm = "open" if mac() else "xdg-open"
    try:
        prozess = subprocess.Popen([programm, ziel], env=fremde_umgebung(), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"{programm} fehlt" + ("" if mac() else ", Paket xdg-utils installieren")) from e
    except OSError as e:
        raise OSError(f"{programm} lässt sich nicht starten: {e.strerror or e}") from e
    try:
        code = prozess.wait(timeout=OEFFNEN_WARTEN)
    except subprocess.TimeoutExpired:
        threading.Thread(target=prozess.wait, daemon=True).start()
        return
    if code:
        raise OSError(_oeffnen_fehler(programm, code))


def _oeffnen_fehler(programm: str, code: int) -> str:
    """Text zum Rueckgabewert (man open; man xdg-open: 2 Datei fehlt, 3 Hilfsprogramm fehlt, 4 fehlgeschlagen). Ohne
    Klammern, das Fenster setzt den Text selbst in Klammern."""
    if programm == "open":
        grund = "kein Programm für diesen Dateityp gefunden"
    elif code == 2:
        grund = "Datei nicht gefunden"
    elif code == 3:
        grund = "ein Hilfsprogramm zum Öffnen fehlt"
    else:
        grund = "kein Standardprogramm für diesen Dateityp eingerichtet"
    return f"{grund}, {programm} meldet Fehler {code}"


def einzelinstanz(basis: Path) -> bool:
    """True, wenn fuer diesen Ordner noch kein Fenster offen ist. Windows: benannter Mutex; macOS/Linux: gesperrte
    Datei .pdf2md.lock in der Ablage (die Sperre endet mit dem Programm, auch nach einem Absturz). False nur, wenn
    die Sperre schon gehalten wird; laesst sich der Ordner nicht anlegen, die Datei nicht oeffnen oder gar nicht
    sperren, kommt OSError (PermissionError bei fehlendem Zugriff)."""
    if windows():
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        name = "Local\\pdf2md-" + hashlib.sha1(str(Path(basis).resolve()).lower().encode("utf-8")).hexdigest()[:12]
        griff = kernel32.CreateMutexW(None, False, name)
        if ctypes.get_last_error() == 183:                  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(ctypes.c_void_p(griff))
            return False
        _GRIFFE.append(griff)
        return True
    import fcntl
    Path(basis).mkdir(parents=True, exist_ok=True)
    datei = open(Path(basis) / SPERRDATEI, "a+")
    try:
        fcntl.flock(datei, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        datei.close()
        if _gesperrt(e):
            return False
        raise                   # z.B. Netz- oder FUSE-Laufwerk ohne Dateisperren: nicht "laeuft schon" melden
    _GRIFFE.append(datei)
    return True


def _gesperrt(fehler: OSError) -> bool:
    """Heisst der Fehler von flock(LOCK_NB): ein anderes Programm haelt die Sperre? Laut Python-Doku EAGAIN bzw.
    EWOULDBLOCK (BlockingIOError) oder je nach System EACCES. ENOLCK, EOPNOTSUPP oder EINVAL (Netz- und
    FUSE-Laufwerke ohne Sperren) bedeuten dagegen: hier laesst sich gar nicht sperren."""
    return isinstance(fehler, BlockingIOError) or fehler.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES)


def _ausgabe(befehl: list[str]) -> str:
    return subprocess.run(befehl, capture_output=True, text=True, timeout=3, env=fremde_umgebung()).stdout.strip()


def dunkel() -> bool:
    """Ist das System auf dunkles Thema gestellt? (Hintergrundfarbe vor dem ersten Zeichnen des Fensters)"""
    try:
        if windows():
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as schluessel:
                return winreg.QueryValueEx(schluessel, "AppsUseLightTheme")[0] == 0
        if mac():
            return _ausgabe(["defaults", "read", "-g", "AppleInterfaceStyle"]).lower() == "dark"
        return "dark" in _ausgabe(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]).lower()
    except Exception:
        return False


def meldung(text: str) -> None:
    """Meldung, bevor es ein Fenster gibt (z.B. "laeuft schon", Startfehler). Windows: MessageBox; macOS: osascript;
    Linux: zenity oder kdialog, sonst eine Benachrichtigung (notify-send). Dialoge warten wie die MessageBox, bis sie
    bestaetigt sind. Ausserhalb von Windows steht der Text immer auch auf stderr, falls kein Dialog erscheinen kann."""
    if windows():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "pdf2md", 0x40)
        return
    try:
        print(text, file=sys.stderr)
    except (OSError, ValueError):                       # Konsole geschlossen
        pass
    for befehl in _dialoge(text):
        if not shutil.which(befehl[0]):
            continue
        try:
            code = subprocess.run(befehl, env=fremde_umgebung(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).returncode
        except (OSError, ValueError, subprocess.SubprocessError):     # naechstes Programm versuchen
            continue
        if code in (0, 1):      # bestaetigt bzw. geschlossen; anderes (kein Display, GTK-Fehler): naechstes Programm
            return


def _dialoge(text: str) -> list[list[str]]:
    """Befehle fuer meldung(), in dieser Reihenfolge versucht; ohne Shell, der Text ist immer ein eigenes Argument.
    osascript bekommt ihn ueber argv statt im Skript: so muessen weder Anfuehrungszeichen noch Backslashes maskiert
    werden, und der Text kann kein AppleScript einschleusen. zenity ohne Pango-Markup, notify-send mit maskiertem
    Markup (sonst verschluckten beide Text mit < oder &)."""
    if mac():
        return [["osascript", "-e", "on run argv", "-e", "display alert (item 1 of argv) message (item 2 of argv)",
                 "-e", "end run", "pdf2md", text]]
    return [["zenity", "--info", "--title=pdf2md", "--no-markup", "--text=" + text],
            ["kdialog", "--title", "pdf2md", "--msgbox", text],
            ["notify-send", "--app-name=pdf2md", "--", "pdf2md", html.escape(text, quote=False)]]


def zugriff_hinweis() -> str:
    """Was zu tun ist, wenn das System den Zugriff verweigert (PermissionError ausserhalb von Windows). macOS fragt
    beim ersten Zugriff auf Dokumente, Schreibtisch, Downloads oder Wechselmedien; wer dort ablehnt, kann es nur in
    den Systemeinstellungen wieder erlauben."""
    if mac():
        return ("in den Systemeinstellungen unter Datenschutz & Sicherheit > Dateien und Ordner pdf2md den Zugriff "
                "erlauben")
    return "Lese- und Schreibrechte prüfen"


def _heim() -> Path:
    return Path.home()


def dokumente() -> Path:
    """Dokumente-Ordner: Linux nach XDG (xdg-user-dir), sonst ~/Documents bzw. ~/Dokumente, notfalls der Heimatordner."""
    heim = _heim()
    if not mac() and not windows():
        try:
            ordner = Path(_ausgabe(["xdg-user-dir", "DOCUMENTS"]))
            if ordner.is_dir() and ordner != heim:
                return ordner
        except Exception:
            pass
    for name in ("Documents", "Dokumente"):
        if (heim / name).is_dir():
            return heim / name
    return heim


def ablage_basis(skript: Path) -> Path:
    """Ordner fuer Eingang, Fertig, Prüfen, Protokoll und Einstellungen. Aus dem Quellcode und unter Windows neben dem
    Programm; als App unter macOS/Linux im Dokumente-Ordner (das App-Paket bzw. /usr, /opt ist schreibgeschuetzt)."""
    if not getattr(sys, "frozen", False):
        return Path(skript).resolve().parent
    if windows():
        return Path(sys.executable).resolve().parent
    return dokumente() / "pdf2md"
