"""Version von pdf2md und die Suche nach einer neueren Version (Releases auf GitHub).

Beim Start fragt das Fenster einmal die oeffentliche Release-Liste von GitHub ab (SUCHEN, im Fenster abschaltbar) und
zeigt einen Hinweis mit Link, wenn es eine neuere Version gibt. Heruntergeladen oder ersetzt wird nichts.
Datenschutz: Gesendet wird nur die Anfrage selbst mit dem allgemeinen User-Agent pdf2md/1.0 (wie zitierdaten.py);
GitHub sieht dabei, wie bei jedem Seitenaufruf, die IP-Adresse. Keine Kennung, kein Dateiname, kein Inhalt.

VERSION muss zum Tag des Releases passen (v1.1.0 -> "1.1.0"); .github/workflows/release.yml prueft das."""
from __future__ import annotations

import json
import re
import urllib.request

VERSION = "1.1.0"
SUCHEN = True
ADRESSE = "https://api.github.com/repos/S4ltc/pdf2md/releases/latest"
SEITE = "https://github.com/S4ltc/pdf2md/releases/latest"     # oeffnet der Hinweis im Browser
USER_AGENT = "pdf2md/1.0"
TIMEOUT = 5


def zahlen(version: str | None) -> tuple[int, int, int] | None:
    """"v1.2" -> (1, 2, 0); Vorabversionen ("1.2.0-beta") und Unlesbares -> None."""
    m = re.fullmatch(r"[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?", (version or "").strip())
    return tuple(int(x or 0) for x in m.groups()) if m else None


def _abrufen(adresse: str) -> bytes | None:
    try:
        anfrage = urllib.request.Request(adresse, headers={"User-Agent": USER_AGENT,
                                                           "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
            return antwort.read()
    except Exception:
        return None


def neuere_version() -> str | None:
    """Die Nummer des neuesten Releases, wenn sie hoeher ist als VERSION; sonst, ausgeschaltet oder offline None."""
    if not SUCHEN:
        return None
    roh = _abrufen(ADRESSE)
    try:
        tag = json.loads(roh)["tag_name"] if roh else None
    except Exception:
        return None
    neu, jetzt = zahlen(tag), zahlen(VERSION)
    return ".".join(map(str, neu)) if neu and jetzt and neu > jetzt else None
