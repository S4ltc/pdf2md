"""Schutz-Hook fuer Claude Code (PreToolUse): setzt zwei verbindliche Regeln aus CLAUDE.md technisch durch.

1. dist/ enthaelt Nutzerdaten (Eingang, Fertig, Pruefen, Sicherung, Protokoll.csv, Einstellungen.json): Edit/Write
   dort sind gesperrt, ebenso Shell-Befehle, die diese Daten loeschen, verschieben oder ueberschreiben. Lesen und
   Kopieren AUS dist bleibt erlaubt (Kopie der Ablage im Scratchpad), ebenso der Build (dist/pdf2md.exe).
2. git push macht der Nutzer selbst.

Claude Code uebergibt den Werkzeugaufruf als JSON auf stdin; bei einem Verstoss antwortet das Skript mit
permissionDecision "deny" samt Begruendung, sonst ohne Ausgabe. Die Shell-Pruefung ist eine Heuristik: sie soll
Versehen verhindern, keine Absicht. Bei eigenen Fehlern laesst das Skript den Aufruf durch (Exitcode immer 0),
damit ein Fehler im Hook nicht jede Arbeit blockiert. Eingetragen ist der Hook in .claude/settings.local.json
(lokal, weil er per `py` startet); getestet in tests/test_schutz_hook.py."""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]
DIST = PROJEKT / "dist"

DIST_GRUND = ("dist\\ enthält Nutzerdaten (Eingang, Fertig, Prüfen, Sicherung, Protokoll.csv, Einstellungen.json) "
              "und wird nie verändert (CLAUDE.md, Verbindliche Regeln). Für Versuche eine Kopie der Ablage im "
              "Scratchpad anlegen; muss in dist\\ wirklich etwas geändert werden, macht das der Nutzer selbst.")
PUSH_GRUND = ("git push macht der Nutzer selbst (CLAUDE.md: nur lokal committen). Den Commit lokal lassen und dem "
              "Nutzer Bescheid geben; vor einem Push den Skill veroeffentlichen durchgehen.")

# Alle Muster laufen auf dem normalisierten Befehl: NFC, "\" -> "/", kleingeschrieben
_DATEN = r"dist/+(?:eingang|fertig|prüfen|pruefen|sicherung|protokoll\.csv|einstellungen\.json|literatur\.bib)(?![\w.])"
NUTZERDATEN = re.compile(_DATEN)
ABLAGE = re.compile(r"(?:^|[\s\"'=/])dist/*(?=$|[\s\"';|&)])")          # der Ordner dist selbst
UMLEITUNG = re.compile(r">{1,2}\s*[\"']?[^\s\"'|;&]*" + _DATEN)
GIT_PUSH = re.compile(r"\bgit(?:\.exe)?[\"']?(?:\s+(?:-c\s+\S+|--?[a-z][\w-]*(?:=\S+)?))*\s+push\b")
PY_SCHREIBEND = re.compile(r"shutil\.|os\.(?:remove|unlink|rename|replace|rmdir|removedirs)\b|\.unlink\(|"
                           r"\.rename\(|\.replace\(|\.rmdir\(|write_text|write_bytes|rmtree|"
                           r"open\([^)]*,\s*(?:mode\s*=\s*)?[\"'][^\"']*[wax]")
ZITAT = re.compile(r"\"[^\"]*\"|'[^']*'")
GIT_PFAD = re.compile(r"[\"'](?:[^\"']*/)?git(?:\.exe)?[\"']")
TEILBEFEHL = re.compile(r"&&|\|\||[;|\n]")
WORT = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
ROBOCOPY_OPTION = re.compile(r"/[a-z]+(?::\S*)?")

ZERSTOEREND = {"rm", "rmdir", "rd", "del", "erase", "mv", "move", "ren", "rename", "unlink", "shred", "truncate",
               "touch", "tee", "remove-item", "ri", "move-item", "mi", "rename-item", "rni", "set-content", "sc",
               "add-content", "ac", "clear-content", "clc", "out-file", "new-item", "ni"}
KOPIEREN = {"cp", "copy", "copy-item", "cpi", "xcopy", "robocopy"}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("\\", "/").casefold()


def _befehlsname(wort: str) -> str:
    name = wort.rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".exe") else name


def _in_dist(pfad: str, cwd: str | None) -> bool:
    p = Path(pfad)
    if not p.is_absolute():
        p = Path(cwd or PROJEKT) / p
    ziel, dist = _norm(os.path.normpath(str(p))), _norm(os.path.normpath(str(DIST)))
    return ziel == dist or ziel.startswith(dist + "/")


def _betrifft_dist(text: str) -> bool:
    return bool(NUTZERDATEN.search(text) or ABLAGE.search(text))


def _kopierziel(woerter: list[str], befehl: str) -> str | None:
    """Ziel eines Kopierbefehls: -Destination, bei robocopy/xcopy das zweite, sonst das letzte Pfad-Argument."""
    for i, w in enumerate(woerter[:-1]):
        if w in ("-destination", "-dest"):
            return woerter[i + 1]
    start = next(i for i, w in enumerate(woerter) if _befehlsname(w) == befehl) + 1
    pfade = [w for w in woerter[start:] if not w.startswith("-")
             and not (befehl in ("robocopy", "xcopy") and ROBOCOPY_OPTION.fullmatch(w))]
    if len(pfade) < 2:
        return None
    return pfade[1] if befehl in ("robocopy", "xcopy") else pfade[-1]


def _teilbefehl_veraendert_dist(teil: str) -> bool:
    if not _betrifft_dist(teil):
        return False
    woerter = [w.strip("\"'") for w in WORT.findall(teil)]
    namen = {_befehlsname(w) for w in woerter}
    if namen & ZERSTOEREND or ("sed" in namen and any(w.startswith("-i") for w in woerter)):
        return True
    for befehl in namen & KOPIEREN:
        ziel = _kopierziel(woerter, befehl)
        if ziel and _betrifft_dist(" " + ziel):
            return True
    # Der Vorschau-Server und das Fenster arbeiten wirklich auf der Ablage, die man ihnen gibt
    return bool(UMLEITUNG.search(teil)) or "ui_vorschau" in teil or "pdf2md_ablage" in teil


def _shell_pruefen(befehl: str) -> str | None:
    text = _norm(befehl)
    # Text in Anfuehrungszeichen (Commit-Nachricht, echo) ist kein Befehl, ausser es ist der Pfad zu git selbst
    ohne_zitate = ZITAT.sub(lambda m: m.group() if GIT_PFAD.fullmatch(m.group()) else '""', text)
    if GIT_PUSH.search(ohne_zitate):
        return PUSH_GRUND
    if _betrifft_dist(text) and PY_SCHREIBEND.search(text):          # Einzeiler: Pfad und Aufruf im selben Befehl
        return DIST_GRUND
    if any(_teilbefehl_veraendert_dist(t) for t in TEILBEFEHL.split(text)):
        return DIST_GRUND
    return None


def pruefen(eingabe: dict) -> str | None:
    """Begruendung, wenn der Werkzeugaufruf gesperrt ist, sonst None."""
    werkzeug = eingabe.get("tool_name") or ""
    daten = eingabe.get("tool_input") or {}
    if werkzeug in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        pfad = daten.get("file_path") or daten.get("notebook_path")
        return DIST_GRUND if pfad and _in_dist(pfad, eingabe.get("cwd")) else None
    if werkzeug in ("Bash", "PowerShell"):
        return _shell_pruefen(daten.get("command") or "")
    return None


def main() -> int:
    try:
        grund = pruefen(json.loads(sys.stdin.buffer.read().decode("utf-8-sig")))   # -sig: PowerShell-Pipe setzt BOM
    except Exception:
        return 0
    if grund:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                            "permissionDecision": "deny",
                                                            "permissionDecisionReason": grund}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
