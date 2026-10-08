"""Was je Betriebssystem anders ist: Anzeige-Engine, Dateien oeffnen, ein Fenster je Ordner, helles oder dunkles
Thema, Meldung ohne Fenster und der Ort der Ablage.

Windows ist das Zielsystem der .exe und von Hand geprueft. macOS und Linux sind vorbereitet: die Tests laufen dort
bei jedem Push auf GitHub (.github/workflows/tests.yml), das Fenster selbst ist auf diesen Systemen nicht von Hand
geprueft. Anzeige: Windows WebView2 (edgechromium), macOS WebKit (cocoa), Linux QtWebEngine (qt, mit PySide6) oder
WebKitGTK (gtk, Systempaket). SYSTEM ist austauschbar, damit sich alle Zweige auch unter Windows testen lassen."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

SYSTEM = sys.platform           # "win32", "darwin" (macOS), "linux"
_GRIFFE: list = []              # Mutex (Windows) bzw. offene Sperrdateien: halten, solange das Programm laeuft


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
    Oberflaeche, nie Seiten aus dem Netz; deshalb wird die Sandbox abgeschaltet (eine eigene Einstellung bleibt)."""
    if not windows() and not mac():
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


def oeffnen(pfad: Path) -> None:
    """Datei oder Ordner mit dem Standardprogramm oeffnen (PDF-Leser, Editor, Explorer/Finder/Dateimanager)."""
    if windows():
        os.startfile(str(pfad))
    else:
        subprocess.Popen(["open" if mac() else "xdg-open", str(pfad)])


def einzelinstanz(basis: Path) -> bool:
    """True, wenn fuer diesen Ordner noch kein Fenster offen ist. Windows: benannter Mutex; macOS/Linux: gesperrte
    Datei .pdf2md.lock in der Ablage (die Sperre endet mit dem Programm, auch nach einem Absturz)."""
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
    datei = open(Path(basis) / ".pdf2md.lock", "a+")
    try:
        fcntl.flock(datei, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        datei.close()
        return False
    _GRIFFE.append(datei)
    return True


def _ausgabe(befehl: list[str]) -> str:
    return subprocess.run(befehl, capture_output=True, text=True, timeout=3).stdout.strip()


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
    """Meldung, bevor es ein Fenster gibt (z.B. "laeuft schon"). Ohne Windows: auf die Konsole."""
    if windows():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "pdf2md", 0x40)
    else:
        print(text, file=sys.stderr)


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
