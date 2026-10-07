"""Ablage fuer das Fenster: was in Eingang, Prüfen und Fertig liegt (nur lesen), Signatur der Ordner fuer die
automatische Aktualisierung und Kopieren neuer Dateien nach Eingang.

Kopieren ist keine Dateibewegung im Sinne des Protokolls: das Original bleibt, wo es ist, deshalb gibt es keine
Protokollzeile und Rueckgaengig loescht keine Kopien."""

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import pdf2md


def _brauchbar(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in pdf2md.UNTERSTUETZT and not p.name.startswith(("~$", "."))


def _format(p: Path) -> str:
    return p.suffix.lstrip(".").upper() or "?"


def kennzahlen_lesen(pfad: str, aktuelle_textquelle: str) -> dict:
    """Kennzahlen einer .md (auswertung.buchkennzahlen) samt Name und Originaldatei. Laeuft auch in Unterprozessen,
    wenn das Fenster viele Buecher auf einmal auswertet (ui_app.Api._vorwaermen)."""
    import auswertung
    md = Path(pfad)
    werte, text = kopf_lesen_datei(md, voll=True)
    kennzahlen = auswertung.buchkennzahlen(werte or {}, text, aktuelle_textquelle)
    kennzahlen.update(name=md.stem, original=str((werte or {}).get("originaldatei") or ""))
    return kennzahlen


def kopf_lesen_datei(md: Path, voll: bool = False) -> tuple[dict | None, str]:
    """Kopfblock und Text einer .md (voll=False: nur der Anfang, reicht fuer den Kopfblock)."""
    try:
        with open(md, encoding="utf-8-sig", errors="replace") as f:
            return pdf2md.kopf_lesen(f.read() if voll else f.read(8000))
    except OSError:
        return None, ""


def eingang_liste(eingang: Path) -> list[dict]:
    if not eingang.is_dir():
        return []
    return [{"name": p.name, "format": _format(p), "groesse": p.stat().st_size}
            for p in sorted(eingang.iterdir(), key=lambda p: p.name.lower()) if _brauchbar(p)]


def pruefen_liste(pruefen: Path) -> list[dict]:
    """Je .md in Prüfen: Originalname, Grund aus `pruefen:` und ob sie beim naechsten Start uebernommen wird."""
    if not pruefen.is_dir():
        return []
    liste = []
    for md in sorted(pruefen.glob("*.md"), key=lambda p: p.name.lower()):
        werte, _ = kopf_lesen_datei(md)
        original = pdf2md.original_zu_md(md)
        hindernis = pdf2md.uebernahme_pruefen(werte, md)
        liste.append({"name": original.name if original else md.name, "md": md.name,
                      "format": _format(original) if original else "?",
                      "grund": str((werte or {}).get("pruefen") or ""), "bereit": hindernis is None,
                      "hinweis": "bereit zur Übernahme" if hindernis is None else hindernis})
    return liste


def fertig_liste(fertig: Path) -> list[dict]:
    """Je Buch (Paar aus Original und .md) eine Zeile, zuletzt geaenderte oben. Der Ordner wird nur einmal gelesen
    (frueher je .md bis zu sieben Abfragen nach dem Original: bei 640 Buechern spuerbar langsam, Haertetest)."""
    if not fertig.is_dir():
        return []
    eintraege = {p.name.lower(): p for p in fertig.iterdir()}
    liste = []
    for md in (p for p in eintraege.values() if p.suffix.lower() == ".md"):
        original = next((eintraege[n] for n in (md.stem.lower() + e for e in pdf2md.UNTERSTUETZT) if n in eintraege),
                        None)
        try:
            stand = md.stat().st_mtime
        except OSError:
            continue
        liste.append({"name": md.stem, "md": md.name, "format": _format(original) if original else "?",
                      "datum": datetime.fromtimestamp(stand).strftime("%Y-%m-%d"), "_stand": stand})
    liste.sort(key=lambda e: (-e["_stand"], e["name"].lower()))
    for e in liste:
        del e["_stand"]
    return liste


def signatur(*pfade: Path) -> str:
    """Kurzer Fingerabdruck von Ordnern (Namen, Groessen, Aenderungszeiten) und Dateien: aendert er sich, laedt das
    Fenster die Listen neu."""
    h = hashlib.sha1()
    for pfad in pfade:
        h.update(str(pfad).encode("utf-8", "replace"))
        try:
            if pfad.is_dir():
                for p in sorted(pfad.iterdir(), key=lambda p: p.name):
                    st = p.stat()
                    h.update(f"{p.name}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8", "replace"))
            elif pfad.is_file():
                st = pfad.stat()
                h.update(f"{st.st_size}|{st.st_mtime_ns}".encode())
        except OSError:
            h.update(b"?")
    return h.hexdigest()[:16]


def kopieren(quellen: list, eingang: Path) -> dict:
    """Kopiert Dateien (Ordner: ihre Dateien, nicht rekursiv) nach Eingang. Gleichnamige bekommen " (2)" usw."""
    eingang = Path(eingang)
    eingang.mkdir(parents=True, exist_ok=True)
    kopiert: list[str] = []
    abgelehnt: list[tuple[str, str]] = []
    for quelle in map(Path, quellen):
        dateien = sorted(p for p in quelle.iterdir() if p.is_file()) if quelle.is_dir() else [quelle]
        for datei in dateien:
            if not datei.is_file():
                abgelehnt.append((datei.name, "nicht gefunden"))
            elif not _brauchbar(datei):
                abgelehnt.append((datei.name, "Format nicht unterstützt"))
            elif datei.resolve().parent == eingang.resolve():
                abgelehnt.append((datei.name, "liegt schon im Eingang"))
            else:
                stem = pdf2md.freier_name(eingang, datei.stem, datei.suffix)
                ziel = eingang / f"{stem}{datei.suffix}"
                shutil.copy2(datei, ziel)
                kopiert.append(ziel.name)
    return {"kopiert": kopiert, "abgelehnt": abgelehnt}
