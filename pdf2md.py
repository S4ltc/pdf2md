"""pdf2md - wandelt Buecher und Dokumente (PDF, DOCX, PPTX, XLSX, EPUB, HTML) in Markdown um, liest Metadaten und
benennt Original und .md nach dem Schema "Titel - Autor - Jahr" um.

Bedienung nur ueber das Fenster (ui_app.py, pdf2md.exe per Doppelklick): Dateien hinzufuegen (Dialog oder ins Fenster
ziehen, sie werden nach Eingang kopiert), "Starten" verarbeitet Eingang und uebernimmt fertig ausgefuellte Dateien aus
Prüfen. Werkzeuge (Rueckgaengig, Namen reparieren, Text erneuern) zeigen erst eine Vorschau. Einstellungen siehe
einstellungen.py (gespeichert in Einstellungen.json).

Ergebnis (neben dem Programm):
  Fertig/         Titel, Autor und Jahr gefunden -> Original + .md tragen den neuen Namen
  Prüfen/         etwas fehlt -> Originalname bleibt. Kopfblock der .md ausfuellen und erneut "Starten":
                  vollstaendige Dateien wandern dann nach Fertig.
  Protokoll.csv   Liste aller Aktionen (Grundlage fuer Rueckgaengig und die Auswertung)
"""

import concurrent.futures
import contextlib
import csv
import html
import io
import json
import logging
import multiprocessing
import os
import re
import shutil
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from defusedxml import ElementTree as ET
from markitdown import MarkItDown, StreamInfo
from pypdf import PdfReader, PdfWriter

try:
    import formeln          # Reparatur unlesbarer Formelzeichen (Glyphnamen und Formvergleich)
except Exception:           # pragma: no cover - fehlt eine Abhaengigkeit, laeuft das Tool ohne Formelreparatur
    formeln = None
try:
    import lesefolge        # Lesereihenfolge zweispaltiger Seiten
except Exception:           # pragma: no cover
    lesefolge = None
try:
    import zeichen          # Zeichenkorrektur (Umlaut-Leerzeichen, Symbol-Schriften, falsche Kodierung)
except Exception:           # pragma: no cover
    zeichen = None
try:
    import normen           # Normen (DIN, EN, ISO ...) erkennen: Nummer, Ausgabe, Titel
except Exception:           # pragma: no cover
    normen = None
try:
    import tabellen         # Tabellen mit Gitterlinien als Markdown-Tabellen
except Exception:           # pragma: no cover
    tabellen = None
try:
    import formelsatz       # Hoch-/Tiefstellung, Brueche, Wurzeln, Operatoren als LaTeX
except Exception:           # pragma: no cover
    formelsatz = None
try:
    import seitenzahlen     # gedruckte Seitenzahlen (Seitenlabel, Kopf-/Fusszeile) fuer korrekte Quellenangaben
except Exception:           # pragma: no cover
    seitenzahlen = None
try:
    import zitierdaten      # Quellenangabe im IEEE-Stil (Crossref/DNB ueber DOI/ISBN), Kapitel von Sammelwerken
except Exception:           # pragma: no cover
    zitierdaten = None
import plattform  # noqa: E402  Ablage, Anzeige und Oeffnen je Betriebssystem
try:
    import schriftbild      # Schriftgroesse und Fett/Kursiv: Ueberschriften ohne Lesezeichen, Hervorhebungen
except Exception:           # pragma: no cover
    schriftbild = None
try:
    import einstellungen    # alle einstellbaren Werte (Fenster, Einstellungen.json, Unterprozesse, Kopfblock)
except Exception:           # pragma: no cover
    einstellungen = None
SPALTENBRUCH = getattr(lesefolge, "SPALTENBRUCH", "")   # Marker fuer eine erzwungene Absatzgrenze, siehe lesefolge.py

# ---------------------------------------------------------------- Einstellungen
# Die Werte hier sind die Standardwerte. Das Fenster aendert sie ueber einstellungen.py (dort steht jede einstellbare
# Konstante mit Bereich und Tooltip; neue Konstanten dort eintragen, sonst prueft der Test sie nicht).
BASE_DIR = plattform.ablage_basis(Path(__file__))   # Windows: neben der .exe; App auf macOS/Linux: Dokumente
EINGANG = BASE_DIR / "Eingang"
FERTIG = BASE_DIR / "Fertig"
PRUEFEN = BASE_DIR / "Prüfen"
PROTOKOLL = BASE_DIR / "Protokoll.csv"
SICHERUNG = BASE_DIR / "Sicherung"

UNTERSTUETZT = {".pdf", ".docx", ".pptx", ".xlsx", ".epub", ".html", ".htm"}

MAX_NAME_LEN = 120          # Zeichen fuer den Dateinamen ohne Endung
MIN_TEXT_ZEICHEN = 200      # weniger Text => vermutlich Scan ohne Texterkennung
MIN_TEXT_DOKUMENT = 20      # DOCX/PPTX/XLSX/EPUB/HTML haben keine Scans: nur fast leere Dateien nach Prüfen
JAHR_SUCHTEXT = 15000       # so viele Zeichen vom Anfang nach dem Copyright-Jahr durchsuchen
# Das Erstellungsdatum einer Datei ist meist NICHT das Erscheinungsjahr. Nur auf True
# setzen, wenn du diesen unsicheren Wert trotzdem als Jahr akzeptieren willst.
JAHR_AUS_ERSTELLDATUM = False

# Fehlende Angaben ueber die ISBN/DOI bei Crossref (kostenlos, ohne Anmeldung) nachschlagen.
# Gesendet wird nur die ISBN bzw. DOI, kein Dateiinhalt. Auf False setzen = komplett offline.
ONLINE_ABGLEICH = True
# Stil der Quellenangabe im Kopfblock: "ieee", "apa" (APA 7) oder "din" (DIN ISO 690), siehe zitierdaten.py
ZITIERSTIL = "ieee"
BIBTEX = True               # zusaetzlich ein BibTeX-Eintrag im Kopfblock (Citavi, Zotero, LaTeX)
ONLINE_TIMEOUT = 10

# Womit der Text aus PDFs gelesen wird:
#   "pdfium"      (Standard) sauberer Text, echte Sonderzeichen, sehr schnell, aber keine Markdown-Tabellen
#   "markitdown"  der PDF-Weg von MarkItDown (macht aus Formeln und Fliesstext oft Tabellen-Muell)
PDF_ENGINE = "pdfium"
PDF_ENGINE_NAMEN = {"pdfium": "PDFium", "markitdown": "MarkItDown"}   # so steht es im Kopfblock (textquelle)
# Unlesbare oder vertauschte Zeichen in Formelschriften reparieren (nur beim PDFium-Weg). Details in formeln.py.
FORMELN_REPARIEREN = True
# Kapitelstruktur aus den PDF-Lesezeichen als Markdown-Ueberschriften (#, ##, ...) einfuegen (nur PDFium-Weg).
UEBERSCHRIFTEN_AUS_LESEZEICHEN = True
# Hat die PDF keine Lesezeichen: Ueberschriften aus der Schriftgroesse erkennen (schriftbild.py, nur PDFium-Weg).
UEBERSCHRIFTEN_AUS_SCHRIFT = True
# Fette und kursive Wortgruppen als **fett** / *kursiv* uebernehmen (schriftbild.py, nur PDFium-Weg).
HERVORHEBUNGEN = True
# Zweispaltige Seiten, deren Text im PDF in falscher Reihenfolge steht (rechte Spalte vor der linken), in
# Lesereihenfolge bringen (nur PDFium-Weg). Details in lesefolge.py.
SPALTENREIHENFOLGE = True
MAX_UEBERSCHRIFT = 200      # laengere Lesezeichen-Titel werden abgeschnitten
SEITENMARKER = True        # vor jede PDF-Seite <!-- Seite 197 (PDF 206) --> bzw. <!-- PDF-Seite 3 -->, fuer Quellenangaben
# Gedruckte Seitenzahl im Marker (aus Seitenlabel oder Kopf-/Fusszeile, seitenzahlen.py). Aus: nur die PDF-Seite.
GEDRUCKTE_SEITENZAHLEN = True
# Steht im Kopfblock jeder PDF-.md, damit eine KI die Marker richtig deutet
ZITIERHINWEIS = ("Seitenmarker <!-- Seite S (PDF N) -->: S ist die gedruckte Seitenzahl, die zitiert wird; N ist die "
                 "Position in der PDF-Datei. <!-- PDF-Seite N --> hat keine gedruckte Seitenzahl, dort nicht 'S. N' "
                 "zitieren. Ein Marker mitten im Satz zeigt den Seitenwechsel innerhalb des Satzes. Literaturangabe: "
                 "Feld quellenangabe ({stil}), im Text {im_text}; bei Sammelwerken gilt die Kapitelquelle davor. "
                 "Mit ⚠[Formel unsicher] markierte Formeln im PDF prüfen.")
IM_TEXT = {"ieee": "[Nr., S. S]", "apa": "(Autor, Jahr, S. S)", "din": "(AUTOR Jahr, S. S)"}   # Zitat im Text je Stil


def zitierstil() -> str:
    return ZITIERSTIL if ZITIERSTIL in IM_TEXT else "ieee"


def zitierhinweis() -> str:
    stil = zitierstil()
    name = zitierdaten.STILE[stil] if zitierdaten is not None else "IEEE"
    return ZITIERHINWEIS.format(stil=name, im_text=IM_TEXT[stil])
KOPF_FUSS_MIN_SEITEN = 8    # so oft muss eine Kopf-/Fusszeile vorkommen, um entfernt zu werden
KOPF_FUSS_MAX_LAENGE = 300  # laengere Zeilen gelten nie als Kopf-/Fusszeile (Wasserzeichen sind oft 150 Zeichen lang)
# Zeichenfehler auf Zeichenebene korrigieren (nur PDFium-Weg, Details in zeichen.py): "fü r" -> "für",
# Symbol-/Wingdings-Zeichen, Texte in falscher Kodierung ("f¸r" -> "für")
ZEICHEN_KORRIGIEREN = True
# Normen (DIN, EN, ISO ...) erkennen und Titel/Herausgeber/Ausgabe von der Norm selbst nehmen (Details in normen.py)
NORMEN_ERKENNEN = True
# Tabellen mit gezeichneten Gitterlinien als Markdown-Tabellen (nur PDFium-Weg, Details in tabellen.py).
TABELLEN_ERKENNEN = True
# Hoch-/Tiefstellungen, Brueche, Wurzeln, Summen als LaTeX ($R_{p0,2}$, $\frac{a}{b}$), unsichere Formeln markiert
# (formelsatz.py).
FORMELSATZ = True
# Lizenz-/Download-Vermerke, die auf jeder Seite einer gekauften Norm stehen (mit Firmen- und Benutzername).
# Sie sind kein Inhalt, verfaelschen das Jahr ("Datum / Uhrzeit des Ausdrucks: 2020-01-01") und werden entfernt.
LIZENZVERMERK = re.compile(r"(?:Datum / Uhrzeit des Ausdrucks:(?:.*?Printed copies are uncontrolled|.*$)"
                           r"|Firmenname:.*?Benutzername:\s*\S+(?:\s*Printed copies are uncontrolled)?"
                           r"|Benutzername:\s*\S+\s*Printed copies are uncontrolled"
                           r"|^\s*Printed copies are uncontrolled\s*$"
                           r"|Normen-Download-(?:Beuth|DIN ?Media)-\S*(?:.*$)?"
                           # Kennung des Lizenznehmers als Hex-Zeichenkette (Beuth-Downloads, eigene Zeile je Seite)
                           r"|^\s*[0-9A-F]{40,}\s*$"
                           # Abo-Vermerk mit Kunden- und Abonummer ("Normen-Ticker - Firma - Kd.-Nr.1234567 - Abo-Nr. ...")
                           r"|^.*\b(?:Kd\.?-Nr\.|Abo-Nr\.)\s*\d.*$|^.*\bNormen-?(?:Ticker|abonnement)\b.*$)",
                           re.IGNORECASE)
# Vermerk auf absichtlich leeren Seiten (Normen): die Seite gilt dann als leer und bekommt keinen Seitenmarker
LEERSEITE = re.compile(r"[–—-]?\s*Leerseite\s*[–—-]?|This page is intentionally (?:left )?blank\.?", re.IGNORECASE)

# Grosse PDFs werden in Seitenpakete geteilt und auf mehreren Prozessorkernen umgewandelt
# (nur beim MarkItDown-Weg noetig, PDFium ist ohne Teilung schnell genug).
PARALLEL_AB_SEITEN = 150
SEITEN_PRO_PAKET = 40
MAX_PROZESSE = os.cpu_count() or 8   # keine feste Obergrenze mehr: so viele Kerne, wie die Maschine hat

KENNUNG_MUSTER = re.compile(r"(?:isbn[\s:]*)?[\d\-\sxX]{10,}|10\.\d{4,9}/\S+", re.IGNORECASE)
# Platzhalter, die Programme als Titel eintragen ("Microsoft Word - Dokument1", "Präsentation1", "Mappe1", "Layout 1",
# "bericht.docx"). Nur der ganze Titel zaehlt: "Sehr langes Dokument" oder "Layout von Leiterplatten" sind echte Titel
# (die erste, nicht verankerte Fassung verwarf sie, gefunden im Haertetest).
UNBRAUCHBARE_TITEL = re.compile(
    r"^\s*(?:microsoft (?:word|powerpoint|excel)\b.*|(?:untitled|unbenannt)(?:[\s_-]*\d+)?"
    r"|(?:dokument|document|präsentation|presentation|mappe|book|arbeitsmappe|layout|folie|slide)[\s_-]*\d*)\s*$"
    r"|\.(?:indd|docx?|pptx?|xlsx?|qxd|pdf|tex|pages|rtf|txt)\s*$",
    re.IGNORECASE,
)
# Vorgaben von Programmen und Bibliotheken statt einer Person (python-docx/openpyxl schreiben sich selbst ein)
UNBRAUCHBARE_AUTOREN = {"admin", "administrator", "user", "owner", "unknown", "unbekannt", "windows user",
                        "windows-benutzer", "benutzer", "author", "autor", "microsoft office user",
                        "microsoft office-benutzer", "microsoft office benutzer", "python-docx", "python-pptx",
                        "openpyxl", "apache poi", "default", ""}
NORMTITEL = re.compile(r"(?:E )?(?:DIN|EN|ISO|IEC|VDI|VDE|DVS)\b\D{0,20}\d")   # Titel beginnt mit einer Normnummer
JAHR = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")
DOI_MUSTER = re.compile(r"10\.\d{4,9}/[^\s\"<>()]+")
ISBN_MUSTER = re.compile(r"(?<![\d-])97[89](?:[\- ]?\d){10}(?!\d)")
XLSX_LEER = re.compile(r"(?<=\|) NaN(?= \|)")
KEIN_BUCH = ("book-chapter", "book-part", "book-section", "reference-entry")

PROTOKOLL_SPALTEN = ["lauf", "zeit", "status", "original_name", "neuer_name", "ordner", "von_pfad",
                     "nach_pfad", "md_pfad", "titel", "autor", "jahr", "titel_quelle", "autor_quelle",
                     "jahr_quelle", "kennung", "hinweis"]
ZURUECKDREHBAR = ("OK", "PRÜFEN", "NACHGEBESSERT", "UMBENANNT")

# Warnungen der PDF-Bibliotheken (z.B. "Cannot set non-stroke color ...") betreffen Farben und
# Layout-Kleinigkeiten, nicht den Text. Sie wuerden nur die Ausgabe fluten. Diese Zeilen stehen
# auf Modulebene, damit sie auch in den Unterprozessen der parallelen Umwandlung gelten.
for _name in ("pdfminer", "pdfplumber", "pypdf"):
    logging.getLogger(_name).setLevel(logging.ERROR)

# MarkItDown ruft pdfplumber mit dessen Standard-Abstandswert auf. Der klebt bei vielen Buechern die Woerter
# zusammen ("Wiefindeichheraus"). Ein relativer Abstand (Bruchteil der Schriftgroesse) behebt das.
try:
    import pdfplumber.page as _plumber_seite
    _extract_text_original = _plumber_seite.Page.extract_text

    def _extract_text_mit_abstand(self, *args, **kwargs):
        kwargs.setdefault("x_tolerance_ratio", 0.15)
        return _extract_text_original(self, *args, **kwargs)

    _plumber_seite.Page.extract_text = _extract_text_mit_abstand
except Exception:  # pragma: no cover - dann bleibt es beim Standardverhalten
    pass


# ---------------------------------------------------------------- Rueckmeldung an das Fenster
# Meldungen und Fortschritt gehen an die Funktionen, die das Fenster (ui_app.py) mit rueckmeldung() setzt; ohne Fenster
# (Tests, Werkzeuge) landen Meldungen auf der Konsole und der Fortschritt entfaellt. Es laeuft immer nur ein Lauf.
_rueckmeldung: dict = {"melder": None, "fortschritt": None}


def melden(text: str) -> None:
    melder = _rueckmeldung["melder"]
    if melder is None:
        try:
            print(text)
        except UnicodeEncodeError:              # alte Konsole (cp1252) kennt z.B. "⚠" nicht: ersetzen statt abbrechen
            kodierung = getattr(sys.stdout, "encoding", None) or "ascii"
            print(text.encode(kodierung, "replace").decode(kodierung))
    else:
        melder(text)


def fortschritt_melden(phase: str, erledigt: int = 0, gesamt: int = 0) -> None:
    """Fortschritt der aktuellen Datei: Phase und erledigt/gesamt (gesamt 0 = Dauer unbekannt)."""
    ziel = _rueckmeldung["fortschritt"]
    if ziel is not None:
        ziel(phase, erledigt, gesamt)


@contextlib.contextmanager
def rueckmeldung(melder=None, fortschritt=None):
    """Leitet melden()/fortschritt_melden() fuer die Dauer des with-Blocks um (None: bisheriges Ziel bleibt)."""
    vorher = dict(_rueckmeldung)
    if melder is not None:
        _rueckmeldung["melder"] = melder
    if fortschritt is not None:
        _rueckmeldung["fortschritt"] = fortschritt
    try:
        yield
    finally:
        _rueckmeldung.update(vorher)


# ---------------------------------------------------------------- Namen
def bereinigen(text: str) -> str:
    """Entfernt Zeichen, die in Windows-Dateinamen verboten sind."""
    text = re.sub(r"\s*:\s+", " – ", text)  # "Titel: Untertitel" -> "Titel – Untertitel"
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text


def kurzer_autor(autor: str) -> str:
    """Bei drei oder mehr Personen nur die erste nennen ('Muster et al.')."""
    personen = [p.strip() for p in re.split(r";|,| und | and | & ", autor) if p.strip()]
    return f"{personen[0]} et al." if len(personen) >= 3 else autor


def name_laenge(ordner: Path, endung: str) -> int:
    """Hoechstlaenge des Namens ohne Endung, damit der ganze Pfad unter der Windows-Grenze von 260 Zeichen bleibt
    (ohne die Freigabe langer Pfade scheitert sonst das Verschieben in tiefen Ordnern). Platz fuer " (2)" bleibt."""
    frei = 259 - len(str(Path(ordner).resolve())) - 1 - len(endung) - len(" (99)")
    return max(40, min(MAX_NAME_LEN, frei))


def neuer_name(titel: str, autor: str, jahr: str, max_len: int | None = None) -> str:
    """'Titel - Autor - Jahr'. Ist der Name zu lang, wird nur der Titel gekuerzt (am Wortende,
    mit '…'), damit Autor und Jahr immer erhalten bleiben. Der volle Titel steht im Kopfblock der .md."""
    autor = kurzer_autor(autor)
    if len(autor) > 50:
        autor = autor[:49].rstrip() + "…"
    ende = bereinigen(f"{autor} - {jahr}")   # erst hier bereinigen, sonst geht der Punkt in 'et al.' verloren
    titel = bereinigen(titel)
    laenge = MAX_NAME_LEN if max_len is None else max_len
    if len(ende) > laenge // 2:                       # sehr enger Platz: Autor kuerzen, Jahr bleibt
        autor = autor[:max(8, laenge // 2 - len(str(jahr)) - 4)].rstrip() + "…"
        ende = bereinigen(f"{autor} - {jahr}")
    erlaubt = laenge - len(ende) - 3                  # 3 = das ' - ' zwischen Titel und Rest
    if len(titel) > erlaubt:
        teile = titel.split(" – ")
        if len(teile) > 2 and NORMTITEL.match(teile[0]):
            # Norm ("DIN EN ISO 12345 – Klebtechnik – Klebverbindungen ... – Einstufung von Fehlstellen"): Nummer und
            # letzten Teil behalten, der ist am genauesten; die mittleren Teile fallen weg, die laengsten zuerst.
            # "Teil 3: Technische ..." (nach bereinigen() "Teil 3 – Technische ...") bleibt zusammen.
            for i in range(len(teile) - 2, 0, -1):
                if re.fullmatch(r"(?:Teil|Part|Blatt) [\d-]+", teile[i]):
                    teile[i:i + 2] = [f"{teile[i]} – {teile[i + 1]}"]
            while len(teile) > 2 and len(" – ".join(teile)) > erlaubt:
                del teile[max(range(1, len(teile) - 1), key=lambda i: len(teile[i]))]
        else:
            # Buch: erst versuchen, den Untertitel wegzulassen ("Titel – Untertitel" -> "Titel") ...
            while len(teile) > 1 and len(" – ".join(teile)) > erlaubt:
                teile.pop()
        rest = " – ".join(teile)
        if len(rest) <= erlaubt:
            titel = rest
        else:                                        # ... sonst am Wortende kuerzen
            gekuerzt = rest[:erlaubt - 1]
            wortende = max(gekuerzt.rfind(" "), gekuerzt.rfind(","))
            if wortende > erlaubt // 2:              # nur am Wortende kuerzen, wenn nicht zu viel wegfaellt
                gekuerzt = gekuerzt[:wortende]
            titel = gekuerzt.rstrip(" ,.;:–-") + "…"
    return f"{titel} - {ende}"


def freier_name(ordner: Path, stem: str, endung: str) -> str:
    """Haengt bei Namenskollisionen (2), (3) ... an. Prueft Original und .md."""
    kandidat, n = stem, 2
    while (ordner / f"{kandidat}{endung}").exists() or (ordner / f"{kandidat}.md").exists():
        kandidat = f"{stem} ({n})"
        n += 1
    return kandidat


# ---------------------------------------------------------------- Metadaten
def ist_kennung(text: str) -> bool:
    """True bei Titeln, die nur eine ISBN oder DOI sind (Springer-PDFs machen das oft)."""
    return bool(KENNUNG_MUSTER.fullmatch(text.strip()))


def titel_brauchbar(titel: str | None) -> bool:
    """Ein Titel muss nach dem Bereinigen fuer Dateinamen noch Buchstaben oder Ziffern haben ('???:*' ergaebe sonst
    den Dateinamen ' - Autor - Jahr')."""
    return bool(titel) and bool(re.search(r"[^\W_]", bereinigen(titel)))


def _titel_setzen(info: dict, titel: str, quelle: str) -> None:
    titel = (titel or "").strip()
    if ist_kennung(titel):
        info["kennungen"].append(titel)   # nur eine ISBN/DOI -> zum Nachschlagen aufheben
    elif len(titel) >= 3 and not UNBRAUCHBARE_TITEL.search(titel) and titel_brauchbar(titel):
        info["titel"], info["titel_quelle"] = titel, quelle


def _autor_setzen(info: dict, autor: str, quelle: str) -> None:
    autor = (autor or "").strip()
    if autor.lower() not in UNBRAUCHBARE_AUTOREN:
        info["autor"], info["autor_quelle"] = autor, quelle


def _jahr_setzen(info: dict, text: str, quelle: str) -> None:
    treffer = JAHR.search(str(text or ""))
    if treffer:
        info["jahr"], info["jahr_quelle"] = treffer.group(1), quelle


def _pdf_metadaten(pfad: Path, info: dict) -> None:
    reader = PdfReader(str(pfad))
    if reader.is_encrypted:
        reader.decrypt("")
    info["seiten"] = len(reader.pages)
    meta = reader.metadata or {}
    _titel_setzen(info, meta.get("/Title"), "PDF-Metadaten")
    _autor_setzen(info, meta.get("/Author"), "PDF-Metadaten")
    if JAHR_AUS_ERSTELLDATUM:
        _jahr_setzen(info, str(meta.get("/CreationDate") or "").replace("D:", ""),
                     "PDF-Erstellungsdatum (unsicher)")


def _ooxml_metadaten(pfad: Path, info: dict) -> None:
    """docx, pptx und xlsx: Eigenschaften stehen in docProps/core.xml."""
    with zipfile.ZipFile(pfad) as z:
        wurzel = ET.fromstring(z.read("docProps/core.xml"))
    werte = {el.tag.rsplit("}", 1)[-1]: (el.text or "") for el in wurzel.iter()}
    _titel_setzen(info, werte.get("title"), "Dokument-Eigenschaften")
    _autor_setzen(info, werte.get("creator"), "Dokument-Eigenschaften")
    if JAHR_AUS_ERSTELLDATUM:
        _jahr_setzen(info, werte.get("created"), "Erstellungsdatum (unsicher)")


def _epub_metadaten(pfad: Path, info: dict) -> None:
    """EPUB: Dublin-Core-Angaben in der OPF-Datei. Das Datum ist hier das Erscheinungsdatum."""
    with zipfile.ZipFile(pfad) as z:
        container = ET.fromstring(z.read("META-INF/container.xml"))
        opf_pfad = next(el.get("full-path") for el in container.iter() if el.tag.endswith("rootfile"))
        opf = ET.fromstring(z.read(opf_pfad))
    dc = "{http://purl.org/dc/elements/1.1/}"

    def felder(name: str) -> list[str]:
        return [el.text.strip() for el in opf.iter(dc + name) if el.text and el.text.strip()]

    if felder("title"):
        _titel_setzen(info, felder("title")[0], "EPUB-Metadaten")
    if felder("creator"):
        _autor_setzen(info, ", ".join(felder("creator")), "EPUB-Metadaten")
    if felder("date"):
        _jahr_setzen(info, felder("date")[0], "EPUB-Metadaten")
    info["kennungen"] += felder("identifier")


HTML_ZEICHENSATZ = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?([\w.:-]+)""", re.IGNORECASE)
META_TAG = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
META_ATTRIBUT = re.compile(r"""(\w[\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def html_dekodieren(roh: bytes) -> str:
    """HTML-Bytes als Text: UTF-8 (auch mit BOM), sonst der im Dokument angegebene Zeichensatz, sonst Windows-1252
    (alte deutsche Seiten ohne Angabe). MarkItDown raet sonst falsch ("lðngerer Absatz ■ber", Haertetest)."""
    try:
        return roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    angabe = HTML_ZEICHENSATZ.search(roh[:4096])
    if angabe:
        try:
            return roh.decode(angabe.group(1).decode("ascii"), errors="replace")
        except LookupError:
            pass
    return roh.decode("cp1252", errors="replace")


def _person_umstellen(name: str) -> str:
    """'Kafka, Franz, 1883-1924' / 'Muster, Max' -> 'Franz Kafka' / 'Max Muster' (Dublin Core, citation_author)."""
    m = re.fullmatch(r"\s*([^,]+?),\s*([^,\d]+?)(?:,\s*[\d?\-–. ]+)?\s*", name)
    return f"{m.group(2)} {m.group(1)}" if m else name.strip()


def _html_metadaten(pfad: Path, info: dict) -> None:
    """<title> und <meta name="author">, bevorzugt aber die Angaben fuer Literaturverwaltungen: citation_* (Google
    Scholar, Fachzeitschriften) und Dublin Core (dc.*, z.B. Project Gutenberg). dcterms.created/modified sind
    Datumsangaben der Datei, nicht das Erscheinungsjahr, und bleiben deshalb aussen vor."""
    kopf = html_dekodieren(pfad.read_bytes()[:400_000])
    meta: dict[str, list[str]] = {}
    for tag in META_TAG.findall(kopf):
        attr = {k.lower(): html.unescape(a or b) for k, a, b in META_ATTRIBUT.findall(tag)}
        name = attr.get("name") or attr.get("property")
        if name and attr.get("content", "").strip():
            meta.setdefault(name.lower(), []).append(re.sub(r"\s+", " ", attr["content"]).strip())

    def erstes(*namen: str) -> list[str]:
        return next((meta[n] for n in namen if n in meta), [])

    titel = erstes("citation_title", "dc.title", "dcterms.title", "og:title")
    if titel:
        _titel_setzen(info, titel[0], "HTML-Metadaten")
    if not info["titel"]:
        t = re.search(r"<title[^>]*>(.*?)</title>", kopf, re.IGNORECASE | re.DOTALL)
        if t:
            _titel_setzen(info, html.unescape(re.sub(r"\s+", " ", t.group(1))).strip(), "HTML-Titel")
    personen = erstes("citation_author", "dc.creator", "dcterms.creator", "author")
    if personen:
        _autor_setzen(info, ", ".join(_person_umstellen(n) for n in personen), "HTML-Metadaten")
    datum = erstes("citation_publication_date", "citation_date", "dc.date", "dcterms.issued", "article:published_time")
    if datum:
        _jahr_setzen(info, datum[0], "HTML-Metadaten")
    for kennung in erstes("citation_doi") + erstes("citation_isbn") + erstes("dc.identifier"):
        if ist_kennung(kennung) or DOI_MUSTER.search(kennung):
            info["kennungen"].append(kennung)


def metadaten_lesen(pfad: Path) -> dict:
    """Liest Titel, Autor (und bei EPUB das Jahr) aus den Datei-Metadaten. Fehlendes bleibt None."""
    info = {"titel": None, "autor": None, "jahr": None, "seiten": None,
            "titel_quelle": None, "autor_quelle": None, "jahr_quelle": None, "kennungen": []}
    endung = pfad.suffix.lower()
    if endung == ".pdf":
        _pdf_metadaten(pfad, info)
        return info
    leser = {".docx": _ooxml_metadaten, ".pptx": _ooxml_metadaten, ".xlsx": _ooxml_metadaten,
             ".epub": _epub_metadaten, ".html": _html_metadaten, ".htm": _html_metadaten}[endung]
    try:
        leser(pfad, info)
    except Exception:
        pass  # kaputte oder fehlende Metadaten duerfen die Umwandlung nicht verhindern
    return info


def jahr_finden(text: str) -> str | None:
    """Sucht das Erscheinungsjahr im Textanfang: erst hinter '©'/'Copyright', dann bei
    'Auflage'/'Erstausgabe' usw. Bei mehreren Jahren (Auflagen, Uebersetzungen) gilt das juengste."""
    kopf = nutztext(text[:JAHR_SUCHTEXT])
    grenze = date.today().year + 1

    def jahre_nach(muster: str, fenster: int) -> list[int]:
        gefunden = []
        for m in re.finditer(muster, kopf, re.IGNORECASE):
            gefunden += [int(j) for j in JAHR.findall(kopf[m.end():m.end() + fenster])]
        return [j for j in gefunden if j <= grenze]

    jahre = jahre_nach(r"©|\(c\)|copyright", 250)
    if not jahre:
        jahre = jahre_nach(r"erschienen|erstausgabe|first published|published|auflage|edition", 80)
    return str(max(jahre)) if jahre else None


def kennungen_sammeln(info: dict, text: str) -> list[str]:
    """DOIs vor ISBNs (DOIs sind eindeutiger), zuerst aus den Metadaten, dann aus dem Textanfang."""
    kopf = text[:JAHR_SUCHTEXT]
    vorab = " ".join(info["kennungen"])
    dois = [d.rstrip(".,;") for d in DOI_MUSTER.findall(vorab + " " + kopf)]
    isbns = ISBN_MUSTER.findall(vorab + " " + kopf)
    rein = []
    for k in dois + isbns:
        k = k.strip()
        if k not in rein and not re.search(r"_\d+$", k):  # Kapitel-DOIs (..._5) auslassen
            rein.append(k)
    return rein[:4]


# ---------------------------------------------------------------- Online-Abgleich (Crossref)
def _crossref(url: str) -> dict | None:
    try:
        anfrage = urllib.request.Request(url, headers={"User-Agent": "pdf2md/1.0"})
        with urllib.request.urlopen(anfrage, timeout=ONLINE_TIMEOUT) as antwort:
            return json.load(antwort)["message"]
    except Exception:
        return None


def _als_treffer(eintrag: dict | None) -> dict | None:
    if not eintrag or str(eintrag.get("type", "")).startswith(KEIN_BUCH) or not eintrag.get("title"):
        return None
    ohne_html = lambda s: re.sub(r"<[^>]+>", "", s).strip()
    titel = ohne_html(eintrag["title"][0])
    untertitel = ohne_html(eintrag["subtitle"][0]) if eintrag.get("subtitle") else ""
    if untertitel and untertitel.lower() not in titel.lower():
        titel = f"{titel}: {untertitel}"
    personen = eintrag.get("author") or eintrag.get("editor") or []
    autor = ", ".join(f"{p.get('given', '')} {p.get('family', '')}".strip() for p in personen) or None
    teile = ((eintrag.get("issued") or {}).get("date-parts") or [[None]])[0]
    return {"titel": titel, "autor": autor, "jahr": str(teile[0]) if teile and teile[0] else None}


def online_nachschlagen(kennungen: list[str]) -> dict | None:
    for k in kennungen:
        if k.startswith("10."):
            treffer = _als_treffer(_crossref(f"https://api.crossref.org/works/{k}"))
        else:
            isbn = k.replace(" ", "")
            # Springer-Buecher haben die DOI 10.1007/<ISBN mit Bindestrichen>
            treffer = _als_treffer(_crossref(f"https://api.crossref.org/works/10.1007/{isbn}"))
            if not treffer:
                antwort = _crossref(
                    "https://api.crossref.org/works?rows=5&filter=isbn:" + re.sub(r"\D", "", isbn)
                ) or {}
                treffer = next((t for t in map(_als_treffer, antwort.get("items", [])) if t), None)
        if treffer:
            treffer["kennung"] = k
            return treffer
    return None


# ---------------------------------------------------------------- Textbereinigung (PDF)
_BUCHSTABE = r"[^\W\d_]"
LIGATUREN = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
STEUERZEICHEN = re.compile(r"[\x00\x0b\x0c￾￿­​]")     # unsichtbar: einfach entfernen
FEHLZEICHEN = re.compile(r"[\x01-\x08\x0e-\x1f]")   # PDFs mit defekter Schriftkodierung: Glyphe nicht lesbar -> "�"
# Woerter, denen ein Umlaut fehlt ("fr" statt "für"): Zeichen dafuer, dass die Schriftkodierung der PDF defekt ist
_UML = "[�]?"      # der fehlende Umlaut kann auch schon als Platzhalter markiert sein ('f�r')
FEHLENDE_UMLAUTE = re.compile(
    rf"\b(?:f{_UML}r|k{_UML}nnen|m{_UML}ssen|m{_UML}glich|zun{_UML}chst|w{_UML}hrend|L{_UML}sung|L{_UML}sungen|"
    rf"{_UML}hnlich|w{_UML}rde|n{_UML}tig)\b")
SEITENZAHL = re.compile(r"(?:\d{1,4}|[ivxlcdmIVXLCDM]{1,7})")
KOORDINATION = {"und", "oder", "bzw", "sowie", "u", "bis", "and", "or"}     # "Ein- und Ausgabe"
STRUKTURWORT = re.compile(r"(?:aufgabe|beispiel|übung|abb|abbildung|tab|tabelle|lösung|figure|example|"
                          r"exercise|problem|gleichung)\b", re.IGNORECASE)
LISTENANFANG = re.compile(r"(?:[•●▪◦\-–—*]|\(?\d{1,3}[.)]|\(?[a-zA-Z][.)])\s")
SATZENDE = ".!?:;"
# Abkuerzungen am Zeilenende ("(s.", "z. B.", "vgl.", "Abb.") sind kein Satzende
ABKUERZUNG_ENDE = re.compile(r"(?:^|[\s(])(?:[^\W\d_]{1,3}|vgl|Abb|Tab|bzw|usw|etc|Nr|Bd|Kap|Gl|Fig|Eq|Prof|Dr)\.$")


def _satzende(zeile: str) -> bool:
    return zeile[-1:] in SATZENDE and not ABKUERZUNG_ENDE.search(zeile)
# Marker am Zeilenanfang ("<!-- Seite 197 (PDF 206) -->\n") oder mitten im Satz ("der <!-- Seite 12 (PDF 14) --> Wert");
# "<!-- Seite N -->" ist das Format aelterer .md-Dateien
SEITENMARKER_MUSTER = re.compile(r"(?: (?=<!--))?<!-- (?:Seite \S+ \(PDF \d+\)|PDF-Seite \d+|Seite \d+) -->\n?")


def seitenmarker(pdf_nr: int, gedruckt: str | None) -> str:
    return f"<!-- Seite {gedruckt} (PDF {pdf_nr}) -->" if gedruckt else f"<!-- PDF-Seite {pdf_nr} -->"


def nutztext(text: str) -> str:
    """Der Text ohne die eingefuegten Seitenmarker, z.B. fuer die Scan-Erkennung."""
    return SEITENMARKER_MUSTER.sub("", text)


def umlaute_ergaenzen(text: str, verlaesslich: str = "") -> tuple[str, int]:
    """Ersetzt in Woertern genau einen Platzhalter ('L�sung') durch den Umlaut, der dasselbe Wort an anderer
    Stelle des Buchs intakt schreibt ('Loesung' mit oe). Kein Woerterbuch noetig, das Buch liefert sein
    eigenes. Gibt (Text, Anzahl ersetzter Woerter) zurueck. Nur eindeutige Faelle werden ersetzt.
    verlaesslich: Text mit sicher richtigen Umlauten (die Lesezeichen-Titel, sie sind auch bei defekter Schrift-
    kodierung intakt); jedes Vorkommen dort zaehlt doppelt."""
    if "�" not in text:
        return text, 0
    umlautwort = r"[^\W\d_]*[äöüÄÖÜß][^\W\d_]*"
    bekannt = Counter(re.findall(umlautwort, text))
    for wort in re.findall(umlautwort, verlaesslich):
        bekannt[wort] += 2
    ersetzung: dict[str, str] = {}
    for wort in set(re.findall(r"[^\W\d_]*�[^\W\d_]*", text)):
        if wort.count("�") != 1 or len(wort) < 3:
            continue
        treffer = {c: bekannt[wort.replace("�", c)] for c in "äöüÄÖÜß" if bekannt[wort.replace("�", c)]}
        if not treffer:
            continue
        beste = max(treffer, key=treffer.get)
        andere = sorted((n for c, n in treffer.items() if c != beste), reverse=True)
        if treffer[beste] >= 2 and (not andere or andere[0] * 3 <= treffer[beste]):
            ersetzung[wort] = wort.replace("�", beste)
    if not ersetzung:
        return text, 0
    zaehler = 0

    def ersatz(m: re.Match) -> str:
        nonlocal zaehler
        neu = ersetzung.get(m.group(0))
        if neu is None:
            return m.group(0)
        zaehler += 1
        return neu

    return re.sub(r"[^\W\d_]*�[^\W\d_]*", ersatz, text), zaehler


def kodierung_defekt(text: str) -> bool:
    """True, wenn auffaellig viele deutsche Woerter ohne Umlaut vorkommen ('fr', 'Lsung', 'knnen').
    Dann ist die Schriftkodierung der PDF kaputt, kein Extraktor kann das richtig lesen (nur OCR)."""
    treffer = len(FEHLENDE_UMLAUTE.findall(text))
    return treffer >= 30 and treffer / max(len(text) / 6, 1) > 0.002   # ~Woerter = Zeichen / 6


def _trennungen_verbinden(text: str) -> str:
    """Fuegt am Zeilenende getrennte Woerter wieder zusammen ('Kon-' + 'struktion')."""
    def strich(m: re.Match) -> str:
        buchstabe, wort = m.group(1), m.group(3)
        if wort.lower().rstrip(".,;:") in KOORDINATION:      # "Ein- und Ausgabe": Strich und Leerzeichen bleiben
            return f"{buchstabe}- {wort}"
        if wort[0].islower():                                # "Kon-\nstruktion" -> "Konstruktion"
            return f"{buchstabe}{wort}"
        return f"{buchstabe}-{wort}"                         # "Maschinenbau-\nTechniker": Silben gehen klein weiter,
        #                                                      vor Grossbuchstaben ist es ein echter Bindestrich

    # PDFium markiert weiche Trennstellen am Zeilenende mit einem eigenen Zeichen (statt "-"): verbinden. Ein weiches
    # Trennzeichen (U+00AD) mit folgendem Leerzeichen ist ebenfalls ein Zeilenende ("Bruch\xad prüfung", z.B. in
    # senkrecht gesetzten Tabellenkoepfen); ohne diese Regel entstand "Bruch prüfung".
    text = re.sub("\u00ad[ \t]+", "\u00ad\n", text)
    return re.sub(rf"({_BUCHSTABE})(-|[\x02\ufffe\u00ad])\n[ \t]*(\S+)", strich, text)


def _absaetze_bilden(text: str) -> str:
    """Verbindet umbrochene Zeilen zu Absaetzen. Vorsichtig: nur, wenn die Zeile fast die volle Breite hat
    und nicht mit einem Satzzeichen endet. Formeln, Listen und Inhaltsverzeichnisse bleiben zeilenweise."""
    zeilen = text.split("\n")
    laengen = sorted(len(z) for z in zeilen if len(z) >= 25)
    if len(laengen) < 8:
        return text
    grenze = 0.88 * laengen[int(len(laengen) * 0.9)]
    ergebnis: list[str] = []
    letzte = 0                                               # Laenge der letzten *physischen* Zeile
    for z in zeilen:
        if ergebnis and z.strip():
            vor = ergebnis[-1]
            if (letzte >= grenze and not _satzende(vor) and " … " not in vor and " … " not in z
                    and not LISTENANFANG.match(z.lstrip())
                    and not vor.startswith("|") and not z.startswith("|")):      # Tabellenzeilen nie verbinden
                ergebnis[-1] = vor + " " + z.lstrip()
                letzte = len(z)
                continue
            if letzte < grenze and _satzende(vor) and vor[-1:] in ".!?" and z[:1].isupper():
                ergebnis.append("")                          # kurze Schlusszeile: neuer Absatz
        ergebnis.append(z)
        letzte = len(z)
    return "\n".join(ergebnis)


FORMELSTUECK = re.compile(r"\$[^$\n]+\$")


def _unsichere_formeln_markieren(text: str) -> str:
    """Eine LaTeX-Formel ($...$, formelsatz.py) mit unlesbarem Zeichen ist unsicher: Markierung vor die Zeile, damit
    sie beim Lesen und Zitieren auffaellt (formelsatz.UNSICHER)."""
    if "$" not in text or "�" not in text or formelsatz is None:
        return text
    zeilen = text.split("\n")
    for i, z in enumerate(zeilen):
        if not z.startswith(formelsatz.UNSICHER) and any("�" in m.group(0) for m in FORMELSTUECK.finditer(z)):
            zeilen[i] = formelsatz.UNSICHER + z
    return "\n".join(zeilen)


def _seite_bereinigen(text: str) -> str:
    # NFC: "u" + kombinierendes Trema (so setzen neuere DIN-PDFs jeden Umlaut) wird zu "ü", sonst findet eine Suche
    # nach "für" das Wort nicht
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\t", " ")          # manche PDFs trennen Woerter mit Tabulatoren statt Leerzeichen
    text = text.translate(LIGATUREN)
    text = _trennungen_verbinden(text)
    # Weiche Trennstelle ganz am Seitenende ("Reg\x02", weiter auf der naechsten Seite): als "-" behalten, damit
    # seiten_zu_text() das Wort ueber den Seitenwechsel verbinden kann (sonst blieb "empfehlens" / "wert")
    text = re.sub(rf"({_BUCHSTABE})[\x02\ufffe\u00ad]\s*$", r"\1-", text)
    text = STEUERZEICHEN.sub("", text)
    text = FEHLZEICHEN.sub("�", text)
    text = re.sub("[\ud800-\udfff]", "�", text)    # einzelne UTF-16-Haelften waeren beim Speichern ein Fehler
    text = _unsichere_formeln_markieren(text)
    text = re.sub(r"(?:[ \t]*\.){4,}[ \t]*", " … ", text)   # Inhaltsverzeichnis-Punkte ".........."
    text = "\n".join(re.sub(r"[ \t]{3,}", "  ", z).rstrip() for z in text.split("\n"))
    text = text.replace(SPALTENBRUCH, "")   # erzwungene Absatzgrenze (Spaltenwechsel) -> echte Leerzeile fuer
    text = _absaetze_bilden(text)           # _absaetze_bilden(), die eine Leerzeile nie ueberbrueckt
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


KOPF_FUSS_RAND = 3    # so viele Zeilen am Seitenanfang/-ende werden auf Kopf-/Fusszeilen geprueft (siehe unten)
PUNKTFUEHRER = re.compile(r"(?:[ \t]*\.){4,}|…")


def _kopf_fuss_entfernen(seiten: list[list[str]]) -> list[list[str]]:
    """Entfernt Seitenzahlen sowie laufende Kopf-/Fusszeilen. Eine Zeile gilt als Kopf-/Fusszeile, wenn sie (ohne
    Ziffern) auf mindestens KOPF_FUSS_MIN_SEITEN Seiten als (dort) erste oder letzte Zeile vorkommt; erkannt wird sie
    dann bis zu KOPF_FUSS_RAND Zeilen vom Seitenrand entfernt. Der Rand ist noetig, weil eine Kopfzeile bei
    zweispaltigen Seiten nach dem Umstellen der Lesereihenfolge (lesefolge.py) nicht immer die exakt erste/letzte
    Zeile ist, z.B. wenn ihr eine kurze Randnotiz vorausgeht. Die Erkennung selbst bleibt an der echten Kante (sonst
    wuerden sich auf kurzen Seiten wiederholende Fliesstext-Anfaenge faelschlich als Kopfzeile zaehlen)."""
    def norm(z: str) -> str:
        return re.sub(r"\d+", "#", z.strip())

    # Kurze Dokumente (z.B. eine Norm mit 5 Seiten) haben keine 8 Seiten: dort reichen 60 % der Seiten, mindestens 3
    mit_text = sum(1 for zeilen in seiten if zeilen)
    schwelle = min(KOPF_FUSS_MIN_SEITEN, max(3, -(-6 * mit_text // 10)))
    laufend: set[str] = set()       # an der echten Kante erkannt (Ziffern gleichgesetzt)
    exakt = {"oben": set(), "unten": set()}    # tiefer liegend erkannt (nur Zeichen fuer Zeichen gleiche Zeilen)

    def zu_entfernen(z: str, seite: str | None = None) -> bool:
        if SEITENZAHL.fullmatch(z.strip()) or norm(z) in laufend:
            return True
        return z.strip() in exakt[seite] if seite else False

    def taugt(n: str, anzahl: int) -> bool:
        # Inhaltsverzeichnis-Zeilen mit Punktfuehrern ("Literatur . . . . 15") sind nie Kopf-/Fusszeilen, auch wenn
        # sie am Ende vieler Kapitelanfangsseiten (Kapitel-Inhaltsverzeichnis) stehen
        return (anzahl >= schwelle and 5 <= len(n) <= KOPF_FUSS_MAX_LAENGE and not STRUKTURWORT.match(n)
                and not PUNKTFUEHRER.search(n))

    def kanten(zeilen: list[str]) -> tuple[str, str] | None:
        """Erste und letzte Zeile, nachdem schon erkannte Kopf-/Fusszeilen und Seitenzahlen am Rand weg sind."""
        a, e = 0, len(zeilen)
        while a < min(e, KOPF_FUSS_RAND) and zu_entfernen(zeilen[a], "oben"):
            a += 1
        while e > a and len(zeilen) - e < KOPF_FUSS_RAND and zu_entfernen(zeilen[e - 1], "unten"):
            e -= 1
        return (zeilen[a], zeilen[e - 1]) if e > a else None

    zaehler = Counter()
    for zeilen in seiten:
        if zeilen:
            zaehler.update({norm(zeilen[0]), norm(zeilen[-1])})
    laufend = {n for n, c in zaehler.items() if taugt(n, c)}
    # Gestapelte Kopfzeilen (Normen: "DIN EN ISO 13579:2023-07" und darunter "EN ISO 13579:2023 (D)"): die Zeile, die
    # nach dem Entfernen der erkannten Kopf-/Fusszeilen am Rand steht, zaehlt nur, wenn sie auf genug Seiten Zeichen fuer
    # Zeichen gleich ist. Sonst wuerde der erste Fliesstext jeder Seite ("Seite 12 ...", Ziffern gleichgesetzt) als
    # Kopfzeile gelten.
    for _ in range(KOPF_FUSS_RAND - 1):
        oben, unten = Counter(), Counter()
        for zeilen in seiten:
            rand = kanten(zeilen) if zeilen else None
            if rand:
                oben[rand[0].strip()] += 1
                unten[rand[1].strip()] += 1
        neu_oben = {z for z, c in oben.items() if taugt(z, c)} - exakt["oben"]
        neu_unten = {z for z, c in unten.items() if taugt(z, c)} - exakt["unten"]
        if not (neu_oben or neu_unten):
            break
        exakt["oben"] |= neu_oben
        exakt["unten"] |= neu_unten

    def rand_kuerzen(zeilen: list[str], seite: str) -> list[str]:
        """Sucht innerhalb der ersten KOPF_FUSS_RAND Zeilen die am weitesten innen liegende Kopf-/Fusszeile und
        entfernt sie samt allem, was davor steht (z.B. eine kurze Randnotiz, siehe Docstring oben)."""
        grenze = min(KOPF_FUSS_RAND, len(zeilen) - 1)
        treffer = [i for i in range(grenze) if zu_entfernen(zeilen[i], seite)]
        return zeilen[treffer[-1] + 1:] if treffer else zeilen

    saubere = []
    for zeilen in seiten:
        vorne_weg = rand_kuerzen(list(zeilen), "oben")                            # Kopfzeile(n) am Anfang
        fertig = list(reversed(rand_kuerzen(list(reversed(vorne_weg)), "unten")))  # Fusszeile(n) am Ende
        saubere.append(fertig)
    return saubere


def _norm_titel(s: str) -> str:
    """Vergleichsform eines Titels: ohne jeden Leerraum, denn Lesezeichen lassen ihn oft weg, wo der Text einen
    Zeilenumbruch hat ("Nationaler Anhang NA (informativ)Literaturhinweise")."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s)).casefold()


TITEL_MAX_ZEILEN = 5    # so viele Zeilen darf ein im Text umbrochener Lesezeichen-Titel umfassen


def lesezeichen_lesen(pfad: Path) -> dict[int, list[tuple[int, str]]]:
    """Kapitelstruktur aus den PDF-Lesezeichen: {Seitenindex: [(Ebene, Titel), ...]} in Lesezeichen-Reihenfolge.
    Leer, wenn die PDF keine Lesezeichen hat oder sie sich nicht lesen lassen."""
    import pypdfium2 as pdfium
    ergebnis: dict[int, list[tuple[int, str]]] = {}
    try:
        dokument = pdfium.PdfDocument(str(pfad))
    except Exception:
        return ergebnis
    try:
        gesehen = set()
        for eintrag in dokument.get_toc():
            try:
                titel = re.sub(r"\s+", " ", STEUERZEICHEN.sub("", eintrag.get_title() or "")).strip()
                ziel = eintrag.get_dest()
                seite = None if ziel is None else ziel.get_index()
                ebene = eintrag.level
            except Exception:
                continue
            titel = re.sub("[\ud800-\udfff]", "", titel)[:MAX_UEBERSCHRIFT]
            if "_" in titel and NORMTITEL.match(titel.replace("_", " ")):
                titel = titel.replace("_", " ")          # Lesezeichen "DIN_EN_34567-2:2019-10" -> "DIN EN 34567-2:2019-10"
            if len(titel) < 2 or seite is None or not 0 <= seite < len(dokument) or (seite, ebene, titel) in gesehen:
                continue
            gesehen.add((seite, ebene, titel))
            ergebnis.setdefault(seite, []).append((ebene, titel))
    except Exception:
        return {}
    finally:
        dokument.close()
    return ergebnis


def _ueberschriften_einfuegen(text: str, eintraege: list[tuple[int, str]], statistik: dict | None = None,
                              nur_vorhandene: bool = False) -> str:
    """Macht aus den Lesezeichen einer Seite Markdown-Ueberschriften. Steht der Titel als eigene Zeile im Seitentext
    (auch auf bis zu drei Zeilen umbrochen), wird genau diese Zeile zur Ueberschrift. Sonst kommt die Ueberschrift an
    den Seitenanfang, ausser bei nur_vorhandene (Ueberschriften aus der Schriftgroesse: deren Titel stammt aus den
    rohen Zeichen, steht die Zeile so nicht im korrigierten Text, waere er eine Dublette mit Zeichenfehler).
    Ebene 0 wird '#', Ebene 1 '##' usw. (hoechstens sechs)."""
    zeilen: list[str | None] = text.split("\n")
    ueberschrift = set()
    oben = []
    for ebene, titel in eintraege:
        marke = "#" * min(ebene + 1, 6) + " "
        ziel = _norm_titel(titel)
        treffer = None
        for i, z in enumerate(zeilen):
            if z is None or i in ueberschrift or not z.strip() or z.startswith("#"):
                continue
            n = _norm_titel(z)
            if n == ziel:
                treffer = (i, i)
                break
            if len(n) >= 4 and ziel.startswith(n):                   # langer Titel, im Text umbrochen
                for j in range(i + 1, min(i + TITEL_MAX_ZEILEN, len(zeilen))):
                    if zeilen[j] is None:
                        break
                    n = _norm_titel(n + " " + zeilen[j])
                    if n == ziel:
                        treffer = (i, j)
                        break
                if treffer:
                    break
        if treffer:
            i, j = treffer
            zeilen[i] = marke + " ".join(zeilen[k].strip() for k in range(i, j + 1))
            for k in range(i + 1, j + 1):
                zeilen[k] = None
            ueberschrift.add(i)
        elif not nur_vorhandene:
            oben.append(marke + titel)
        if statistik is not None:
            statistik["gesamt"] = statistik.get("gesamt", 0) + 1
            statistik["im_text"] = statistik.get("im_text", 0) + (1 if treffer else 0)
    ergebnis: list[str] = []
    for i, z in enumerate(zeilen):
        if z is None:
            continue
        if i in ueberschrift and ergebnis and ergebnis[-1] != "":
            ergebnis.append("")                                       # Leerzeile vor der Ueberschrift
        ergebnis.append(z)
        if i in ueberschrift:
            ergebnis.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(ergebnis)).strip("\n")
    return ("\n\n".join(oben) + "\n\n" + text) if oben else text


KOLUMNENTITEL_RAND = 2      # so viele Zeilen oben/unten koennen ein lebender Kolumnentitel sein
KOLUMNENTITEL_ANTEIL = 0.3  # so viele Seiten muessen einen haben, damit die Regel greift


def _kolumnentitel_entfernen(zeilen_je_seite: list[list[str]], gedruckt: list[str | None]) -> list[list[str]]:
    """Lebende Kolumnentitel ("1.3 Grundbegriffe 13", "584 10 Schwingungen")
    wechseln mit dem Abschnitt und fallen deshalb durch die Kopf-/Fusszeilen-Erkennung (die gleiche Zeilen sucht).
    Mit bekannter gedruckter Seitenzahl sind sie sicher zu erkennen: eine kurze Randzeile, die mit genau dieser Zahl
    beginnt oder endet. Nur, wenn das Buch das auf vielen Seiten so macht (sonst koennte es Zufall sein)."""
    treffer: dict[int, list[int]] = {}
    for i, (zeilen, zahl) in enumerate(zip(zeilen_je_seite, gedruckt)):
        if not zahl or not zeilen:
            continue
        rand = sorted(set(range(min(KOLUMNENTITEL_RAND, len(zeilen))))
                      | set(range(max(0, len(zeilen) - KOLUMNENTITEL_RAND), len(zeilen))))
        for k in rand:
            z = zeilen[k].strip()
            if 4 < len(z) <= 120 and (z.startswith(zahl + " ") or z.endswith(" " + zahl)) and not z.startswith("|"):
                treffer.setdefault(i, []).append(k)
    mit_zahl = sum(1 for g in gedruckt if g)
    if not mit_zahl or len(treffer) < max(3, KOLUMNENTITEL_ANTEIL * mit_zahl):
        return zeilen_je_seite
    return [[z for k, z in enumerate(zeilen) if k not in treffer.get(i, ())]
            for i, zeilen in enumerate(zeilen_je_seite)]


STRICHCODE = re.compile(r"[^\w\s]{2,}\w?[^\w\s]*|[!-/:-@\[-`{-~]{1,3}\w{1,3}[!-/:-@\[-`{-~]{1,4}")
DOKUMENTNUMMER = re.compile(r"\d{7}")


def _strichcode_entfernen(zeilen_je_seite: list[list[str]]) -> list[list[str]]:
    """Normen-Deckblatt: der Strichcode der Dokumentnummer kommt als Zeichensalat ("!&&Y8"", "|ϕCQϕ�") direkt vor der
    siebenstelligen Nummer. Nur auf den ersten Seiten und nur in genau dieser Folge."""
    for zeilen in zeilen_je_seite[:3]:
        for i in range(len(zeilen) - 1):
            kurz = zeilen[i].strip()
            if 2 <= len(kurz) <= 12 and DOKUMENTNUMMER.fullmatch(zeilen[i + 1].strip()) and \
                    (STRICHCODE.fullmatch(kurz) or any(c in "!\"#%&'()*+|�" for c in kurz)) and not kurz.isalpha():
                zeilen[i] = ""
    return [[z for z in zeilen if z] for zeilen in zeilen_je_seite]


TRENNUNG_MIT_SEITENZAHL = re.compile(rf"(.*{_BUCHSTABE}[\x02\ufffe\u00ad])(\d{{1,4}})")


def _seitenzahl_abtrennen(zeilen: list[str]) -> list[str]:
    """PDFium haengt die Seitenzahl manchmal ohne Umbruch an eine weiche Trennung am Seitenende ("Anfor\ufffe16"); ohne
    Trennung entstand "Anfor16" mitten im Text und der Seite fehlte ihre Zahl. Nur am Seitenende."""
    if zeilen:
        m = TRENNUNG_MIT_SEITENZAHL.fullmatch(zeilen[-1])
        if m:
            return zeilen[:-1] + [m.group(1), m.group(2)]
    return zeilen


def _titel_im_text(text: str, titel: str) -> bool:
    statistik: dict = {}
    _ueberschriften_einfuegen(text, [(0, titel)], statistik)
    return statistik.get("im_text", 0) == 1


def _lesezeichen_nachschieben(ueberschriften: dict[int, list[tuple[int, str]]],
                              texte: list[str]) -> dict[int, list[tuple[int, str]]]:
    """Manche Lesezeichen zeigen eine Seite zu frueh (gemessen am Inhaltsverzeichnis: ein Lehrbuch und eine
    Norm mit "Europaeisches Vorwort"). Steht der Titel nicht auf seiner Seite, aber auf der naechsten, gehoert die
    Ueberschrift dorthin, sonst stuende sie (und damit die Seitenangabe des Abschnitts) auf der falschen Seite."""
    neu: dict[int, list[tuple[int, str]]] = {}
    for seite in sorted(ueberschriften):
        for ebene, titel in ueberschriften[seite]:
            ziel = seite
            if (seite + 1 < len(texte) and not _titel_im_text(texte[seite], titel)
                    and _titel_im_text(texte[seite + 1], titel)):
                ziel = seite + 1
            neu.setdefault(ziel, []).append((ebene, titel))
    return neu


KEIN_FLIESSTEXT = ("|", "#", "<!--")        # Tabellenzeilen, Ueberschriften, Marker: nie ueber den Seitenwechsel verbinden


def _ueber_seitenwechsel(vorher: str, text: str, marker: str) -> tuple[str, str]:
    """Verbindet, was ueber einen Seitenwechsel hinweg zusammengehoert, und setzt den Marker der neuen Seite.
    - Getrenntes Wort ("Reg-" | "ler"): der Wortrest kommt an das Ende der vorigen Seite ("Regler"), denn eine Suche
      soll das Wort finden. Zitiert wird ein Wort auf der Seite, auf der es beginnt.
    - Satz, der weiterlaeuft (vorige Seite endet ohne Satzzeichen, neue beginnt klein): der Marker kommt mitten in den
      Satz ("... wird der <!-- Seite 12 (PDF 14) --> Wert ..."), der Absatz bleibt ganz und die Seite trotzdem exakt.
    Gibt (vorige Seite, neue Seite samt Marker) zurueck."""
    letzte = vorher.rsplit("\n", 1)[-1]
    erste, _, rest = text.partition("\n")
    if (not letzte or not erste or letzte.startswith(KEIN_FLIESSTEXT) or erste.startswith(KEIN_FLIESSTEXT)
            or LISTENANFANG.match(erste)):
        return vorher, f"{marker}\n{text}"
    m = re.search(rf"{_BUCHSTABE}-$", letzte)
    w = re.match(r"([a-zäöüß]\S*)[ \t]*", erste)
    if m and w and w.group(1).lower().rstrip(".,;:") not in KOORDINATION:
        vorher, letzte = vorher[:-1] + w.group(1), letzte[:-1] + w.group(1)
        erste = erste[w.end():]
        if not erste:                                   # die Zeile bestand nur aus dem Wortrest
            return vorher, f"{marker}\n{rest}" if rest else marker
    weiter = (re.match(r"[a-zäöüß(]", erste) and not _satzende(letzte) and len(letzte) >= 30
              and not STRUKTURWORT.match(letzte))
    if weiter:                                          # die ganze neue Seite haengt am Satz der vorigen
        return vorher + f" {marker} " + erste + (f"\n{rest}" if rest else ""), ""
    return vorher, f"{marker}\n{erste}" + (f"\n{rest}" if rest else "")


def seiten_zu_text(seiten: list[str], ueberschriften: dict[int, list[tuple[int, str]]] | None = None,
                   statistik: dict | None = None, labels: list[str | None] | None = None,
                   nur_vorhandene: bool = False) -> str:
    """Rohtext je PDF-Seite -> bereinigter Gesamttext mit Seitenmarkern und, wenn angegeben, Ueberschriften aus den
    Lesezeichen (nur auf Seiten mit Text, damit die Scan-Erkennung nicht getaeuscht wird). Der Marker nennt die
    gedruckte Seitenzahl (labels: Seitenlabel der PDF, sonst aus Kopf-/Fusszeilen), siehe seitenzahlen.py.
    statistik bekommt "seitenzahlen" (Anzahl Seiten mit gedruckter Zahl) und "seitenzahlen_quelle"."""
    zeilen_je_seite = [_seitenzahl_abtrennen([z.rstrip() for z in (LIZENZVERMERK.sub("", z) for z in
                                              s.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
                                              if z.strip() and not LEERSEITE.fullmatch(z.strip())])
                       for s in seiten]
    zeilen_je_seite = _strichcode_entfernen(zeilen_je_seite)
    gedruckt: list[str | None] = [None] * len(seiten)
    if SEITENMARKER and GEDRUCKTE_SEITENZAHLEN and seitenzahlen is not None:
        gedruckt, quelle = seitenzahlen.zuordnen(labels, [seitenzahlen.kandidaten(z) for z in zeilen_je_seite])
        if statistik is not None and quelle:
            statistik["seitenzahlen"] = sum(1 for g in gedruckt if g)
            statistik["seitenzahlen_quelle"] = quelle
        zeilen_je_seite = _kolumnentitel_entfernen(zeilen_je_seite, gedruckt)
    zeilen_je_seite = _kopf_fuss_entfernen(zeilen_je_seite)
    texte = [_seite_bereinigen("\n".join(zeilen)) for zeilen in zeilen_je_seite]
    if ueberschriften:
        ueberschriften = _lesezeichen_nachschieben(ueberschriften, texte)
    teile: list[str] = []
    for nr, text in enumerate(texte, 1):
        if text.strip():
            if ueberschriften and (nr - 1) in ueberschriften:
                text = _ueberschriften_einfuegen(text, ueberschriften[nr - 1], statistik, nur_vorhandene)
            if not SEITENMARKER:
                teile.append(text)
                continue
            marker = seitenmarker(nr, gedruckt[nr - 1])
            if teile:
                teile[-1], text = _ueber_seitenwechsel(teile[-1], text, marker)
            else:
                text = f"{marker}\n{text}"
            if text:
                teile.append(text)
    return "\n\n".join(teile)


def spalten_aktiv() -> bool:
    return bool(SPALTENREIHENFOLGE and lesefolge is not None)


def zeichen_aktiv() -> bool:
    return bool(ZEICHEN_KORRIGIEREN and zeichen is not None)


def tabellen_aktiv() -> bool:
    return bool(TABELLEN_ERKENNEN and tabellen is not None and zeichen is not None)


def formelsatz_aktiv() -> bool:
    return bool(FORMELSATZ and formelsatz is not None and zeichen is not None)


def schriftbild_aktiv() -> bool:
    return bool((HERVORHEBUNGEN or UEBERSCHRIFTEN_AUS_SCHRIFT) and schriftbild is not None)


def _phrase_normieren(text: str) -> str:
    """Zeichen einer Hervorhebung so bereinigen wie den Seitentext (_seite_bereinigen), damit sie sich wiederfindet."""
    return STEUERZEICHEN.sub("", unicodedata.normalize("NFC", text).replace("\t", " ").translate(LIGATUREN))


def _pdfium_seiten(pfad: Path, statistik: dict | None = None, reparatur=None,
                   schrift: list | None = None) -> list[str]:
    """Rohtext jeder PDF-Seite ueber PDFium (Chrome-PDF-Engine). Bei zweispaltigen Seiten mit falscher Reihenfolge
    im PDF wird der Text in Lesereihenfolge geliefert (statistik["spalten"] zaehlt diese Seiten).
    Seiten mit verdaechtigen Zeichen (zeichen.py) oder Gitter-Tabellen (tabellen.py) werden in einem zweiten Durchgang
    Zeichen fuer Zeichen neu gelesen; erst dann stehen die Entscheidungen je Schrift fest, und der Zelltext der Tabellen
    bekommt dieselben Korrekturen. statistik["zeichen"] zaehlt die Zeichenkorrekturen, statistik["tabellen"] die
    Tabellen, statistik["korrekturen"] ({Seite: {Zeichenindex: Ersatz}}) braucht die Formelreparatur beim Neuaufbau
    einer Seite. schrift: bekommt je Seite die Zeilen mit Schriftgroesse und Fett/Kursiv (schriftbild.py)."""
    import pypdfium2 as pdfium
    spalten = spalten_aktiv()
    korrektur = zeichen.Korrektur() if zeichen_aktiv() else None
    mit_tabellen = tabellen_aktiv()
    mit_formelsatz = formelsatz_aktiv()
    zweiter_durchgang: dict[int, tuple] = {}     # Seite -> (Lesereihenfolge, verdaechtig?, Gitter-Tabellen, Formelsatz?)
    dokument = pdfium.PdfDocument(str(pfad))
    try:
        if statistik is not None and seitenzahlen is not None and GEDRUCKTE_SEITENZAHLEN:
            labels = seitenzahlen.label_lesen(dokument)
            if any(labels):
                statistik["labels"] = labels
        seiten = []
        anzahl = len(dokument)
        for i in range(anzahl):
            fortschritt_melden("Text lesen", i + 1, anzahl)
            seite = dokument[i]
            if schrift is not None:
                schrift.append([])
            try:
                textseite = seite.get_textpage()
                try:
                    if schrift is not None:
                        try:
                            schrift[-1] = schriftbild.zeilen_lesen(textseite, i)
                        except Exception:
                            pass        # ohne Schriftbild nur keine Hervorhebungen auf dieser Seite
                    folge = lesefolge.bereiche(textseite) if spalten else None
                    if folge and statistik is not None:
                        statistik["spalten"] = statistik.get("spalten", 0) + 1
                    seiten.append(lesefolge.seitentext(textseite, folge) if folge else textseite.get_text_range())
                    verdacht = korrektur is not None and zeichen.verdaechtig(seiten[-1])
                    if verdacht:
                        korrektur.lernen(textseite)
                    gitter = tabellen.gitter(seite) if mit_tabellen and seiten[-1].strip() else []
                    # Tabellen nur mit waagerechten Linien brauchen die Zeichen (Formelsatz liest sie)
                    linien = (tabellen.linien_kandidaten(seite, gitter)
                              if mit_tabellen and formelsatz is not None and seiten[-1].strip() else [])
                    formel = mit_formelsatz and bool(seiten[-1].strip())
                    if verdacht or gitter or linien or formel:
                        zweiter_durchgang[i] = (folge, verdacht, gitter, linien, formel)
                finally:
                    textseite.close()
            except Exception:
                seiten.append("")      # eine kaputte Seite soll das Buch nicht verhindern
            finally:
                seite.close()
        if reparatur is not None:
            # Die Formelreparatur (formeln.py) entscheidet je Schrift und Zeichen; der Formelsatz braucht ihre Zuordnung,
            # sonst stuende in neu gesetzten Formeln weiter "D" statt "=" (MathTime)
            try:
                fortschritt_melden("Formelzeichen prüfen")
                reparatur.analysieren(seiten, alle_seiten=kodierung_defekt("\n".join(seiten)))
            except Exception as e:
                if statistik is not None:
                    statistik["reparatur_fehler"] = str(e)
                reparatur = None
        korrekturen: dict[int, dict[int, str]] = {}
        anzahl_tabellen = 0
        formelstatistik: Counter = Counter()
        for j, (i, (folge, verdacht, gitter, linien, formel)) in enumerate(zweiter_durchgang.items(), 1):
            fortschritt_melden("Formeln und Tabellen", j, len(zweiter_durchgang))
            seite = dokument[i]
            try:
                textseite = seite.get_textpage()
                try:
                    ersatz = korrektur.korrektur(textseite) if verdacht else {}
                    if formel:
                        try:
                            formelersatz, st = formelsatz.ersatz(
                                seite, textseite, ersatz,
                                zuordnung=reparatur.zuordnung_fuer(i) if reparatur is not None else None)
                            ersatz = {**ersatz, **formelersatz}
                            formelstatistik.update(st)
                        except Exception:
                            pass               # der Formelsatz darf eine Seite nie verhindern
                    if linien:
                        gitter = gitter + tabellen.linientabellen(linien, formelsatz.zeichen(textseite, ersatz))
                    if gitter:
                        tabellenersatz, anzahl = tabellen.einsetzen(gitter, textseite, ersatz)
                        ersatz = {**ersatz, **tabellenersatz}
                        anzahl_tabellen += anzahl
                    if ersatz and folge:
                        seiten[i] = lesefolge.seitentext(
                            textseite, folge, lesen=lambda a, e: zeichen.zeichen_lesen(textseite, a, e, ersatz))
                    elif ersatz:
                        seiten[i] = zeichen.zeichen_lesen(textseite, 0, textseite.count_chars(), ersatz)
                    if ersatz:
                        korrekturen[i] = ersatz
                finally:
                    textseite.close()
            except Exception:
                pass                   # dann bleibt der Text dieser Seite, wie PDFium ihn liefert
            finally:
                seite.close()
        if statistik is not None and korrekturen:
            if korrektur is not None and korrektur.statistik():
                statistik["zeichen"] = korrektur.statistik()
            if anzahl_tabellen:
                statistik["tabellen"] = anzahl_tabellen
            if +formelstatistik:
                statistik["formelsatz"] = dict(+formelstatistik)
            statistik["korrekturen"] = korrekturen
        return seiten
    finally:
        dokument.close()


# ---------------------------------------------------------------- Umwandlung
_worker = {"markitdown": None, "pfad": None, "reader": None}


def _paket_umwandeln(pfad: str, start: int, ende: int) -> str:
    """Laeuft in einem eigenen Prozess: wandelt die PDF-Seiten start..ende um."""
    if _worker["markitdown"] is None:
        _worker["markitdown"] = MarkItDown(enable_plugins=False)
    if _worker["pfad"] != pfad:
        reader = PdfReader(pfad)
        if reader.is_encrypted:
            reader.decrypt("")
        _worker["pfad"], _worker["reader"] = pfad, reader
    writer = PdfWriter()
    for seite in _worker["reader"].pages[start:ende]:
        writer.add_page(seite)
    puffer = io.BytesIO()
    writer.write(puffer)
    puffer.seek(0)
    return _worker["markitdown"].convert_stream(puffer, file_extension=".pdf").text_content or ""


def formeln_aktiv() -> bool:
    return bool(FORMELN_REPARIEREN and formeln is not None)


def erwartete_textquelle() -> str:
    """So heisst die Textquelle im Kopfblock, wenn das aktuelle Verfahren angewendet wurde."""
    name = PDF_ENGINE_NAMEN[PDF_ENGINE]
    if PDF_ENGINE == "pdfium":
        if formeln_aktiv():
            name += " + Formelreparatur"
        if UEBERSCHRIFTEN_AUS_LESEZEICHEN:
            name += " + Lesezeichen"
        if spalten_aktiv():
            name += " + Spaltenreihenfolge"
        if zeichen_aktiv():
            name += " + Zeichenkorrektur"
        if tabellen_aktiv():
            name += " + Tabellen"
        if formelsatz_aktiv():
            name += " + Formelsatz"
        if seitenzahlen_aktiv():
            name += " + Seitenzahlen"
        if UEBERSCHRIFTEN_AUS_SCHRIFT and schriftbild is not None:
            name += " + Schriftgrößen-Überschriften"
        if HERVORHEBUNGEN and schriftbild is not None:
            name += " + Hervorhebungen"
    return name


def seitenzahlen_aktiv() -> bool:
    return bool(SEITENMARKER and GEDRUCKTE_SEITENZAHLEN and seitenzahlen is not None)


def normen_aktiv() -> bool:
    return bool(NORMEN_ERKENNEN and normen is not None)


def _pdfium_text(pfad: Path, spalten: dict | None = None,
                schrift: list | None = None) -> tuple[list[str], dict | None]:
    """Rohtext je Seite (PDFium), danach ggf. mit repariertem Formelzeichen. Statistik oder None.
    spalten: bekommt die Zahl der in Lesereihenfolge gebrachten Seiten."""
    def platzhalter_weg(texte: list[str]) -> list[str]:
        # was die Formelreparatur nicht kennt, wird wieder das Steuerzeichen (spaeter "�", siehe formelsatz.py)
        return [formelsatz.aufloesen(t)[0] for t in texte] if formelsatz is not None else texte

    rep = None
    if formeln_aktiv():
        try:
            rep = formeln.Reparatur(pfad, spalten=spalten_aktiv())
        except Exception as e:                                   # eine Reparatur darf nie die Umwandlung verhindern
            melden(f"   Formelreparatur übersprungen ({e})")
    eigene = spalten if spalten is not None else {}
    try:
        # die Zuordnung der Formelreparatur entsteht zwischen den beiden Durchgaengen (siehe _pdfium_seiten)
        seiten = _pdfium_seiten(pfad, eigene, rep, schrift)
        korrekturen = eigene.pop("korrekturen", None)
        if rep is None:
            return platzhalter_weg(seiten), None
        fehler = eigene.pop("reparatur_fehler", None)
        if fehler:
            melden(f"   Formelreparatur übersprungen ({fehler})")
            return platzhalter_weg(seiten), None
        try:
            fortschritt_melden("Formelzeichen einsetzen")
            neu = rep.aufbauen(seiten, korrekturen=korrekturen)
            return platzhalter_weg(neu), rep.statistik()
        except Exception as e:
            melden(f"   Formelreparatur übersprungen ({e})")
            return platzhalter_weg(seiten), None
    finally:
        if rep is not None:
            rep.schliessen()


def umwandeln(pfad: Path, seiten: int | None, konverter: MarkItDown) -> tuple[str, str, dict | None]:
    """Wandelt eine Datei in Markdown um und gibt (Text, Textquelle, Formelstatistik) zurueck.
    PDFs: PDFium (Standard) oder MarkItDown. Andere Formate: MarkItDown."""
    if pfad.suffix.lower() == ".pdf" and PDF_ENGINE == "pdfium":
        try:
            spaltenstat: dict = {}
            schrift: list | None = [] if schriftbild_aktiv() else None
            roh, formelstatistik = _pdfium_text(pfad, spaltenstat, schrift)
            if formelstatistik and formelstatistik["ersetzt"]:
                melden(f"   Formelzeichen repariert: {formelstatistik['a'] + formelstatistik['b']} Zeichenarten "
                      f"({formelstatistik['ersetzt']} Zeichen), {formelstatistik['offen']} unsicher")
            # Bei fehlgeschlagener Formelreparatur bleibt die Textquelle schlicht "PDFium", so wird es spaeter erneut versucht
            fehlgeschlagen = formeln_aktiv() and formelstatistik is None
            quelle = PDF_ENGINE_NAMEN["pdfium"] if fehlgeschlagen else erwartete_textquelle()
            extra = dict(formelstatistik) if formelstatistik else {"a": 0, "b": 0, "offen": 0, "ersetzt": 0}
            if spaltenstat.get("spalten"):
                extra["spalten"] = spaltenstat["spalten"]
                melden(f"   Zweispaltige Seiten in Lesereihenfolge gebracht: {spaltenstat['spalten']}")
            if spaltenstat.get("zeichen") and zeichen.statistik_text(spaltenstat["zeichen"]):
                extra["zeichen"] = spaltenstat["zeichen"]
                melden(f"   Zeichen korrigiert: {zeichen.statistik_text(spaltenstat['zeichen'])}")
            if spaltenstat.get("tabellen"):
                extra["tabellen"] = spaltenstat["tabellen"]
                melden(f"   Tabellen als Markdown übernommen: {spaltenstat['tabellen']}")
            if spaltenstat.get("formelsatz"):
                extra["formelsatz"] = spaltenstat["formelsatz"]
                melden(f"   Formelsatz: {_formelsatztext(spaltenstat['formelsatz'])}")
            fortschritt_melden("Text aufbereiten")
            lesezeichen = lesezeichen_lesen(pfad) if UEBERSCHRIFTEN_AUS_LESEZEICHEN else None
            if normen_aktiv():
                try:
                    norm = normen.erkennen(pfad, roh, lesezeichen)
                except Exception:                               # die Normerkennung darf nie die Umwandlung verhindern
                    norm = None
                if norm:
                    extra["norm"] = norm
                    melden(f"   Norm erkannt: {norm['bezeichnung']}:{norm['ausgabe']}"
                          + (f" – {norm['titel']}" if norm.get("titel") else " (Titel nicht gefunden)"))
            ueberschriften = lesezeichen
            if not lesezeichen and UEBERSCHRIFTEN_AUS_SCHRIFT and schrift:
                try:
                    ueberschriften = schriftbild.ueberschriften(schrift)
                except Exception:                               # dann eben ohne Ueberschriften, wie bisher
                    ueberschriften = None
            lz: dict = {}
            text = seiten_zu_text(roh, ueberschriften, lz, spaltenstat.pop("labels", None),
                                  nur_vorhandene=ueberschriften is not lesezeichen)
            if lz.get("seitenzahlen"):
                extra["seitenzahlen"], extra["seitenzahlen_quelle"] = lz["seitenzahlen"], lz["seitenzahlen_quelle"]
                melden(f"   Gedruckte Seitenzahlen: {lz['seitenzahlen']} von {len(roh)} Seiten ({lz['seitenzahlen_quelle']})")
            if lz.get("im_text") and ueberschriften is not lesezeichen:      # nur tatsaechlich gesetzte zaehlen
                extra["ueberschriften_schrift"] = lz["im_text"]
                melden(f"   Überschriften aus der Schriftgröße (PDF ohne Lesezeichen): {lz['im_text']}")
            elif lz.get("gesamt") and ueberschriften is lesezeichen:
                extra["ueberschriften"], extra["ueberschriften_im_text"] = lz["gesamt"], lz.get("im_text", 0)
                melden(f"   Überschriften aus Lesezeichen: {lz['gesamt']} ({lz.get('im_text', 0)} direkt im Text gefunden)")
            if formeln_aktiv() and formelstatistik is not None:
                titel = " ".join(t for eintraege in (lesezeichen or {}).values() for _, t in eintraege)
                text, extra["umlaute"] = umlaute_ergaenzen(text, titel)
                if extra["umlaute"]:
                    melden(f"   Umlaute aus dem Buch ergänzt: {extra['umlaute']} Wörter")
            if HERVORHEBUNGEN and schrift:
                try:                                            # ganz am Ende: der Text steht dann fest
                    text, anzahl = schriftbild.einsetzen(text, schriftbild.hervorhebungen(schrift), _phrase_normieren)
                except Exception:
                    anzahl = 0
                if anzahl:
                    extra["hervorhebungen"] = anzahl
                    melden(f"   Fett/kursiv übernommen: {anzahl} Stellen")
            return text, quelle, extra
        except Exception as e:
            melden(f"   PDFium hat die Datei nicht gelesen ({e}), verwende MarkItDown ...")
    text = _markitdown_umwandeln(pfad, seiten, konverter)
    if pfad.suffix.lower() == ".pdf":
        text = re.sub(r"\(cid:\d+\)", "", text)              # nicht zuordenbare Zeichen, nur Rauschen
    if pfad.suffix.lower() == ".xlsx":
        text = XLSX_LEER.sub(" ", text)                       # leere Zellen: pandas schreibt "NaN"
    return text, PDF_ENGINE_NAMEN["markitdown"], None


def _markitdown_umwandeln(pfad: Path, seiten: int | None, konverter: MarkItDown) -> str:
    """Kleine Dateien am Stueck, grosse PDFs in Paketen parallel. Bei Problemen: am Stueck."""
    if pfad.suffix.lower() == ".pdf" and seiten and seiten >= PARALLEL_AB_SEITEN:
        pakete = [(a, min(a + SEITEN_PRO_PAKET, seiten)) for a in range(0, seiten, SEITEN_PRO_PAKET)]
        prozesse = max(1, min(MAX_PROZESSE, os.cpu_count() or 1, len(pakete)))
        try:
            ergebnis = [""] * len(pakete)
            fertig = 0
            # die Unterprozesse importieren die Module frisch (Standardwerte): Einstellungen dort erneut anwenden
            start = ({"initializer": einstellungen.anwenden, "initargs": (einstellungen.aktuell(),)}
                     if einstellungen is not None else {})
            with concurrent.futures.ProcessPoolExecutor(max_workers=prozesse, **start) as pool:
                aufgaben = {pool.submit(_paket_umwandeln, str(pfad), a, e): i
                            for i, (a, e) in enumerate(pakete)}
                fortschritt_melden("Seiten umwandeln", 0, seiten)
                for aufgabe in concurrent.futures.as_completed(aufgaben):
                    ergebnis[aufgaben[aufgabe]] = aufgabe.result()
                    fertig += 1
                    fortschritt_melden("Seiten umwandeln", min(fertig * SEITEN_PRO_PAKET, seiten), seiten)
            return "\n\n".join(ergebnis)
        except Exception as e:
            melden(f"   Parallele Umwandlung fehlgeschlagen ({e}), versuche es am Stueck ...")
    fortschritt_melden("Text lesen")
    if pfad.suffix.lower() in (".html", ".htm"):                # Zeichensatz selbst bestimmen (html_dekodieren)
        roh = html_dekodieren(pfad.read_bytes()).encode("utf-8")
        info = StreamInfo(extension=".html", mimetype="text/html", charset="utf-8")
        return konverter.convert_stream(io.BytesIO(roh), stream_info=info).text_content or ""
    return konverter.convert(str(pfad)).text_content or ""


# ---------------------------------------------------------------- Kopfblock der .md
def kopf_schreiben(werte: dict) -> str:
    """YAML-Kopfblock; json.dumps sorgt fuer gueltig maskierte Zeichenketten."""
    zeilen = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in werte.items()]
    return "\n".join(zeilen + ["---", "", ""])


def kopf_lesen(text: str) -> tuple[dict | None, str]:
    """Trennt Kopfblock und Text. Verzeiht fehlende Anfuehrungszeichen (jahr: 2019, titel: Mein Buch)."""
    if not text.startswith("---\n"):
        return None, text
    ende = text.find("\n---\n", 3)
    if ende == -1:
        return None, text
    werte = {}
    for zeile in text[4:ende].split("\n"):
        m = re.fullmatch(r"([A-Za-z_]+):[ \t]*(.*)", zeile.rstrip())
        if m:
            try:
                werte[m.group(1)] = json.loads(m.group(2))
            except ValueError:
                werte[m.group(1)] = m.group(2).strip()
    rest = text[ende + 5:]
    return werte, rest[1:] if rest.startswith("\n") else rest


def _text(wert) -> str | None:
    return None if wert is None else (str(wert).strip() or None)


def md_schreiben(pfad: Path, inhalt: str) -> None:
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:  # immer LF, auch unter Windows
        f.write(inhalt)


# ---------------------------------------------------------------- Protokoll
def protokollieren(lauf: str, status: str, **felder) -> None:
    zeile = {"lauf": lauf, "zeit": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": status}
    zeile.update({k: ("" if v is None else v) for k, v in felder.items()})
    try:
        neu = not PROTOKOLL.exists()
        # BOM nur beim Anlegen, damit Excel die Umlaute richtig anzeigt
        with open(PROTOKOLL, "a", encoding="utf-8-sig" if neu else "utf-8", newline="") as f:
            schreiber = csv.DictWriter(f, PROTOKOLL_SPALTEN, delimiter=";", extrasaction="ignore",
                                       restval="")
            if neu:
                schreiber.writeheader()
            schreiber.writerow(zeile)
    except OSError as e:  # z.B. Protokoll.csv ist in Excel geoeffnet
        melden(f"   Hinweis: Protokoll.csv konnte nicht geschrieben werden ({e})")


def _protokoll_felder(info: dict) -> dict:
    return {"titel": info["titel"], "autor": info["autor"], "jahr": info["jahr"],
            "titel_quelle": info["titel_quelle"], "autor_quelle": info["autor_quelle"],
            "jahr_quelle": info["jahr_quelle"], "kennung": info.get("kennung")}


# ---------------------------------------------------------------- Hauptablauf
def _spaltentext(s: dict) -> str:
    return f"{s['spalten']} zweispaltige Seiten in Lesereihenfolge gebracht (im PDF steht der Text in anderer Reihenfolge)"


def _lesezeichentext(s: dict) -> str:
    return f"{s['ueberschriften']} Überschriften ({s['ueberschriften_im_text']} direkt im Text gefunden, den Rest am Seitenanfang eingefügt)"


def _formeltext(s: dict) -> str:
    text = (f"{s['a']} Zeichenarten per Glyphname, {s['b']} per Formvergleich, {s['offen']} unsicher "
            f"({s['ersetzt']} Zeichen ersetzt)")
    if s.get("umlaute"):
        text += f"; {s['umlaute']} Wörter mit Umlaut aus dem Buch ergänzt"
    return text


VERFAHRENSFELDER = ("formelreparatur", "lesezeichen", "ueberschriften", "spalten", "zeichenkorrektur",   # die Umwandlung
                     "tabellen", "formelsatz", "hervorhebungen", "seitenzahlen", "zitierhinweis", "einstellungen")


def _formelsatztext(s: dict) -> str:
    teile = [f"{s.get('hochtief', 0)} Hoch-/Tiefstellungen", f"{s.get('formeln', 0)} Formelteile (Brüche, Wurzeln, "
             f"Summen) als LaTeX"]
    if s.get("akzente"):
        teile.append(f"{s['akzente']} Akzente über Formelzeichen")
    if s.get("unsicher"):
        teile.append(f"{s['unsicher']} unsichere Formeln markiert ({formelsatz.UNSICHER.strip()})")
    return ", ".join(teile)


def _verfahrensfelder(kopf: dict, s: dict | None) -> None:
    """Traegt ein, was die Umwandlung gemacht hat (Formelreparatur, Lesezeichen, Spalten, Zeichenkorrektur ...)."""
    for feld in VERFAHRENSFELDER:
        kopf.pop(feld, None)
    # Mit abweichenden Einstellungen erzeugte Texte bleiben nachvollziehbar (Fenster: Einstellungen)
    abweichend = einstellungen.abweichungstext(einstellungen.aktuell()) if einstellungen is not None else None
    if abweichend:
        kopf["einstellungen"] = abweichend
    if not s:
        return
    if SEITENMARKER:
        kopf["seitenzahlen"] = (f"gedruckte Seitenzahl für {s['seitenzahlen']} von {kopf.get('seiten') or '?'} "
                                f"PDF-Seiten ({s['seitenzahlen_quelle']})" if s.get("seitenzahlen")
                                else "keine gedruckten Seitenzahlen gefunden, Marker nennen nur die PDF-Seite")
        kopf["zitierhinweis"] = zitierhinweis()
    if s["a"] + s["b"] + s["offen"]:
        kopf["formelreparatur"] = _formeltext(s)
    if s.get("ueberschriften"):
        kopf["lesezeichen"] = _lesezeichentext(s)
    if s.get("ueberschriften_schrift"):
        kopf["ueberschriften"] = f"{s['ueberschriften_schrift']} Überschriften aus der Schriftgröße (PDF ohne Lesezeichen)"
    if s.get("hervorhebungen"):
        kopf["hervorhebungen"] = f"{s['hervorhebungen']} fette/kursive Stellen als **fett** bzw. *kursiv* übernommen"
    if s.get("spalten"):
        kopf["spalten"] = _spaltentext(s)
    if s.get("zeichen") and zeichen.statistik_text(s["zeichen"]):     # nur gezaehlte, aber leere Arten: nichts
        kopf["zeichenkorrektur"] = zeichen.statistik_text(s["zeichen"])
    if s.get("tabellen"):
        kopf["tabellen"] = f"{s['tabellen']} Tabellen mit Gitterlinien als Markdown-Tabellen übernommen"
    if s.get("formelsatz"):
        kopf["formelsatz"] = _formelsatztext(s["formelsatz"])


ZITIERFELDER = ("quellenangabe", "zitierstil", "bibtex", "verlag", "ort", "auflage", "herausgeber", "isbn", "doi", "zitierdaten_quelle",
                "kapitelquellen")


def zitierangaben(info: dict, text: str, norm: dict | None = None) -> tuple[dict, str]:
    """Kopfblock-Felder fuer die Quellenangabe (Stil ZITIERSTIL, dazu BibTeX) und der Text, bei Sammelwerken mit der
    Quellenangabe jedes Kapitels (zitierdaten.py). Online wird nur DOI/ISBN abgefragt (ONLINE_ABGLEICH); ohne Netz entsteht die Angabe aus
    Titel, Autor und Jahr. info braucht titel, autor, jahr (und kennungen fuer kennungen_sammeln)."""
    if zitierdaten is None:
        return {}, text
    stil = zitierstil()
    if norm:
        felder = {"quellenangabe": zitierdaten.norm(norm, stil), "zitierstil": zitierdaten.STILE[stil]}
        if BIBTEX:
            felder["bibtex"] = zitierdaten.bibtex_norm(norm)
        return felder, text
    daten = None
    if ONLINE_ABGLEICH:
        kennungen = kennungen_sammeln(info, text)
        if info.get("kennung") and info["kennung"] not in kennungen:
            kennungen.insert(0, info["kennung"])
        daten = zitierdaten.nachschlagen(kennungen) if kennungen else None
    d = dict(daten or {})
    d["titel"] = d.get("titel") or info.get("titel")
    d["jahr"] = info.get("jahr") or d.get("jahr")
    if not d.get("autoren") and not d.get("herausgeber"):
        d["autoren"] = zitierdaten.personen_aus_text(info.get("autor"))
    if not d["titel"]:
        return {}, text
    felder = {"quellenangabe": zitierdaten.buch(d, stil), "zitierstil": zitierdaten.STILE[stil]}
    if BIBTEX:
        felder["bibtex"] = zitierdaten.bibtex_buch(d)
    for feld in ("verlag", "ort", "auflage", "isbn", "doi"):
        if d.get(feld):
            felder[feld] = d[feld]
    if d.get("herausgeber"):
        felder["herausgeber"] = ", ".join(f"{v} {n}".strip() for v, n in d["herausgeber"])
    felder["zitierdaten_quelle"] = (f"{daten['quelle']} (über DOI/ISBN)" if daten
                                    else "nur Titel, Autor und Jahr (ohne Online-Abgleich, Verlag und Ort fehlen)")
    if daten:
        text, anzahl = zitierdaten.kapitel_einfuegen(text, d, stil)
        if anzahl:
            felder["kapitelquellen"] = (f"{anzahl} Kapitel mit eigenen Autoren: Quellenangabe je Kapitel als "
                                        f"<!-- Kapitelquelle ({zitierdaten.STILE[stil]}): ... --> am Kapitelanfang")
            melden(f"   Sammelwerk: Quellenangabe für {anzahl} Kapitel eingefügt")
    return felder, text


def norm_uebernehmen(info: dict, norm: dict) -> None:
    """Bei Normen sind Titel und Autor aus den PDF-Metadaten fast immer falsch ("CEN/TC 121", "klar irene"), das Jahr
    aus dem Text ebenso (Druckdatum, ersetzte Ausgabe). Die Angaben der Norm selbst gehen deshalb immer vor."""
    info["titel"], info["titel_quelle"] = normen.vollstaendiger_titel(norm), (
        "Titelseite der Norm" if norm.get("titel") else f"Normnummer ({norm['quelle']})")
    info["autor"], info["autor_quelle"] = norm["herausgeber"], "Herausgeber der Norm"
    info["jahr"], info["jahr_quelle"] = norm["jahr"], f"Ausgabe {norm['ausgabe']} ({norm['quelle']})"
    info["norm"] = f"{norm['bezeichnung']}:{norm['ausgabe']}"


def verarbeiten(datei: Path, konverter: MarkItDown, lauf: str, melder=None, fortschritt=None) -> str:
    """Verarbeitet eine Datei und gibt eine einzeilige Statusmeldung zurueck. melder(text) bekommt die Meldungen,
    fortschritt(phase, erledigt, gesamt) den Fortschritt (Fenster); ohne beide gehen Meldungen auf die Konsole."""
    with rueckmeldung(melder, fortschritt):
        return _verarbeiten(datei, konverter, lauf)


def _verarbeiten(datei: Path, konverter: MarkItDown, lauf: str) -> str:
    endung = datei.suffix.lower()
    fortschritt_melden("Metadaten lesen")
    info = metadaten_lesen(datei)
    text, textquelle, formelstatistik = umwandeln(datei, info["seiten"], konverter)
    if formelstatistik and formelstatistik.get("norm"):
        norm_uebernehmen(info, formelstatistik["norm"])
    fortschritt_melden("Metadaten und Quellenangabe")

    if not info["jahr"]:
        info["jahr"] = jahr_finden(text)
        if info["jahr"]:
            info["jahr_quelle"] = "Copyright-/Erscheinungsvermerk im Text"

    fehlt = [f for f in ("titel", "autor", "jahr") if not info[f]]
    if fehlt and ONLINE_ABGLEICH:
        kennungen = kennungen_sammeln(info, text)
        treffer = online_nachschlagen(kennungen) if kennungen else None
        if treffer:
            info["kennung"] = treffer["kennung"]
            for feld in fehlt:
                if treffer[feld]:
                    info[feld], info[f"{feld}_quelle"] = treffer[feld], "Crossref (über ISBN/DOI)"
        elif kennungen:
            info["kennung"] = kennungen[0]
    zitat, text = zitierangaben(info, text, (formelstatistik or {}).get("norm"))

    probleme = []
    if len(nutztext(text).strip()) < (MIN_TEXT_ZEICHEN if endung == ".pdf" else MIN_TEXT_DOKUMENT):
        probleme.append("kaum Text (vermutlich Scan ohne Texterkennung)" if endung == ".pdf"
                        else "kaum Text (Dokument ist fast leer)")
    probleme += [f"{name} fehlt" for feld, name in (("titel", "Titel"), ("autor", "Autor"), ("jahr", "Jahr"))
                 if not info[feld]]
    # Warnungen blockieren die Ablage in Fertig nicht, stehen aber im Kopfblock, im Protokoll und in der Meldung
    warnungen = []
    if kodierung_defekt(text):
        warnungen.append("Umlaute fehlen teilweise (defekte Schriftkodierung im PDF, nur per Texterkennung behebbar)")

    if probleme:
        ziel = PRUEFEN
        stem = bereinigen(datei.stem)[:name_laenge(ziel, endung)].rstrip(" .") or "Datei"
    else:
        ziel = FERTIG
        stem = neuer_name(info["titel"], info["autor"], info["jahr"], max_len=name_laenge(ziel, endung))
    ziel.mkdir(parents=True, exist_ok=True)
    stem = freier_name(ziel, stem, endung)

    kopf = {"titel": info["titel"], "titel_quelle": info["titel_quelle"],
            "autor": info["autor"], "autor_quelle": info["autor_quelle"],
            "jahr": info["jahr"], "jahr_quelle": info["jahr_quelle"],
            "kennung": info.get("kennung"), **zitat, "seiten": info["seiten"], "textquelle": textquelle,
            "originaldatei": datei.name, "umgewandelt_am": date.today().isoformat()}
    if info.get("norm"):
        kopf["norm"] = info["norm"]
    _verfahrensfelder(kopf, formelstatistik)
    if probleme:
        kopf["pruefen"] = "; ".join(probleme)
    if warnungen:
        kopf["warnung"] = "; ".join(warnungen)

    # Erst .md schreiben, dann Original verschieben: bei einem Fehler geht nichts verloren.
    fortschritt_melden("Kopfblock")
    md_pfad, ziel_datei = ziel / f"{stem}.md", ziel / f"{stem}{endung}"
    md_schreiben(md_pfad, kopf_schreiben(kopf) + text)
    von = datei.resolve()
    try:
        shutil.move(str(datei), str(ziel_datei))
    except OSError:
        md_pfad.unlink(missing_ok=True)    # Original gesperrt (z.B. im PDF-Leser offen): keine verwaiste .md lassen
        raise

    protokollieren(lauf, "PRÜFEN" if probleme else "OK", original_name=datei.name, neuer_name=stem,
                   ordner=ziel.name, von_pfad=von, nach_pfad=ziel_datei, md_pfad=md_pfad,
                   hinweis="; ".join(probleme + [f"WARNUNG: {w}" for w in warnungen]), **_protokoll_felder(info))
    zusatz = "".join(f"\n   WARNUNG {w}" for w in warnungen)
    if probleme:
        return f"PRÜFEN  {datei.name}  ({'; '.join(probleme)}){zusatz}"
    return f"OK      {datei.name}  ->  {stem}{zusatz}"


def original_zu_md(md: Path) -> Path | None:
    """Findet die zur .md gehoerende Originaldatei im selben Ordner."""
    for endung in UNTERSTUETZT:
        kandidat = md.with_suffix(endung)
        if kandidat.is_file():
            return kandidat
    return None


def uebernahme_pruefen(werte: dict | None, md: Path) -> str | None:
    """Darf die Datei aus Prüfen nach Fertig? None = ja, sonst der Grund (fuer nachbessern() und das Fenster).
    Scans ('kaum Text') bleiben, bis die Zeile `pruefen:` im Kopfblock geloescht ist."""
    if werte is None:
        return "kein Kopfblock"
    titel, autor, jahr = (_text(werte.get(k)) for k in ("titel", "autor", "jahr"))
    if not titel_brauchbar(titel):
        titel = None
    fehlt = [name for wert, name in ((titel, "Titel"), (autor, "Autor"), (jahr, "Jahr")) if not wert]
    if fehlt:
        return "; ".join(f"{name} fehlt" for name in fehlt)
    if "kaum Text" in str(werte.get("pruefen") or ""):
        return "kaum Text: Zeile pruefen: im Kopfblock löschen"
    if not re.fullmatch(r"(?:1[5-9]|20)\d{2}", jahr):
        return "Jahr muss vierstellig sein"
    if ist_kennung(titel):
        return "Titel ist eine ISBN"
    if original_zu_md(md) is None:
        return "Originaldatei fehlt"
    return None


def nachbessern(lauf: str) -> int:
    """Verschiebt Dateien aus Prüfen nach Fertig, sobald Titel, Autor und Jahr im Kopfblock
    der .md eingetragen sind (Bedingungen: uebernahme_pruefen)."""
    if not PRUEFEN.is_dir():
        return 0
    erledigt = wartend = 0
    for md in sorted(PRUEFEN.glob("*.md")):
        with open(md, encoding="utf-8-sig") as f:
            werte, _ = kopf_lesen(f.read(8000))
        if werte is None:
            continue
        grund = uebernahme_pruefen(werte, md)
        if grund is not None:
            wartend += 1
            if grund in ("Jahr muss vierstellig sein", "Titel ist eine ISBN", "Originaldatei fehlt"):
                melden(f"   Nicht übernommen: {md.name}  ({grund})")
            continue
        titel, autor, jahr = (_text(werte.get(k)) for k in ("titel", "autor", "jahr"))
        original = original_zu_md(md)

        with open(md, encoding="utf-8-sig") as f:
            werte, text = kopf_lesen(f.read())
        werte.update({"titel": titel, "autor": autor, "jahr": jahr})
        for feld in ("titel", "autor", "jahr"):
            if not werte.get(f"{feld}_quelle"):
                werte[f"{feld}_quelle"] = "manuell nachgetragen"
        werte.pop("pruefen", None)
        werte["nachgebessert_am"] = date.today().isoformat()

        FERTIG.mkdir(parents=True, exist_ok=True)
        soll = neuer_name(titel, autor, jahr, max_len=name_laenge(FERTIG, original.suffix))
        stem = freier_name(FERTIG, soll, original.suffix)
        md_neu, datei_neu = FERTIG / f"{stem}.md", FERTIG / f"{stem}{original.suffix}"
        md_schreiben(md_neu, kopf_schreiben(werte) + text)
        von = original.resolve()
        try:
            shutil.move(str(original), str(datei_neu))
        except OSError as e:               # Original gesperrt: alles bleibt in Prüfen, naechster Start versucht es erneut
            md_neu.unlink(missing_ok=True)
            melden(f"   Nicht übernommen: {original.name}  ({fehlertext(e, original)})")
            wartend += 1
            continue
        try:
            md.unlink()   # die bearbeitete Fassung liegt jetzt in Fertig
        except OSError:
            melden(f"   Hinweis: {md.name} in Prüfen ist noch geöffnet und kann gelöscht werden (Inhalt liegt in Fertig)")

        protokollieren(lauf, "NACHGEBESSERT", original_name=original.name, neuer_name=stem,
                       ordner=FERTIG.name, von_pfad=von, nach_pfad=datei_neu, md_pfad=md_neu,
                       titel=titel, autor=autor, jahr=jahr, titel_quelle=werte["titel_quelle"],
                       autor_quelle=werte["autor_quelle"], jahr_quelle=werte["jahr_quelle"],
                       kennung=werte.get("kennung"))
        melden(f"   NACHGEBESSERT  {original.name}  ->  {stem}")
        erledigt += 1
    if wartend:
        melden(f"   {wartend} Datei(en) in Prüfen warten noch auf vollständige Angaben.")
    return erledigt


# ---------------------------------------------------------------- Werkzeuge (im Fenster: Vorschau, dann Ausfuehren)
def namen_plan() -> list[dict]:
    """Paare in Fertig, deren Name nicht zu Titel, Autor und Jahr im Kopfblock passt (z.B. weil aeltere Versionen zu
    lange Namen abgeschnitten haben oder von Hand umbenannt wurde). Aendert nichts."""
    if not FERTIG.is_dir():
        return []
    plan = []
    for md in sorted(FERTIG.glob("*.md")):
        with open(md, encoding="utf-8-sig") as f:
            werte, _ = kopf_lesen(f.read(8000))
        if werte is None:
            continue
        titel, autor, jahr = (_text(werte.get(k)) for k in ("titel", "autor", "jahr"))
        original = original_zu_md(md)
        if not (titel and autor and jahr) or original is None:
            continue
        soll = neuer_name(titel, autor, jahr, max_len=name_laenge(FERTIG, original.suffix))
        # NFC auf beiden Seiten: macOS liefert Dateinamen oft zerlegt ("u" + Trema), der Kopfblock ist zusammengesetzt
        if re.fullmatch(re.escape(unicodedata.normalize("NFC", soll)) + r"(?: \(\d+\))?",
                        unicodedata.normalize("NFC", md.stem), re.IGNORECASE):
            continue  # Name stimmt (ein angehaengtes " (2)" bei Namensgleichheit ist in Ordnung)
        plan.append({"md": md, "original": original, "alt": md.stem, "neu": soll, "werte": werte})
    return plan


def namen_reparieren(lauf: str, plan: list[dict] | None = None, abbrechen=None) -> int:
    """Benennt die Paare aus namen_plan() um (Status UMBENANNT, mit Rueckgaengig umkehrbar). Laeuft nie automatisch,
    weil von Hand umbenannte Dateien sonst zurueckbenannt wuerden: das Fenster zeigt erst die Vorschau."""
    plan = namen_plan() if plan is None else plan
    erledigt = 0
    for eintrag in plan:
        if abbrechen is not None and abbrechen():
            break
        md, original, werte = eintrag["md"], eintrag["original"], eintrag["werte"]
        if not (md.is_file() and original.is_file()):
            melden(f"   Übersprungen: {md.stem}  (Datei nicht mehr da)")
            continue
        stem = freier_name(FERTIG, eintrag["neu"], original.suffix)
        md_neu, datei_neu = FERTIG / f"{stem}.md", FERTIG / f"{stem}{original.suffix}"
        von = original.resolve()
        try:
            original.rename(datei_neu)
            try:
                md.rename(md_neu)
            except OSError:
                datei_neu.rename(von)   # halbe Umbenennung zurueckdrehen, Paar bleibt zusammen
                raise
        except OSError as e:
            melden(f"   FEHLER  {md.stem}: {e}  (nichts geändert)")
            continue
        protokollieren(lauf, "UMBENANNT", original_name=original.name, neuer_name=stem,
                       ordner=FERTIG.name, von_pfad=von, nach_pfad=datei_neu, md_pfad=md_neu,
                       titel=werte.get("titel"), autor=werte.get("autor"), jahr=werte.get("jahr"),
                       titel_quelle=werte.get("titel_quelle"), autor_quelle=werte.get("autor_quelle"),
                       jahr_quelle=werte.get("jahr_quelle"), kennung=werte.get("kennung"))
        melden(f"   UMBENANNT  {md.stem}  ->  {stem}")
        erledigt += 1
    melden(f"{erledigt} von {len(plan)} Datei(en) umbenannt.")
    return erledigt


LITERATURLISTE = "Literatur.bib"     # neben dem Programm, Werkzeug "Literaturliste exportieren"


def _bibtex_aus_kopf(werte: dict) -> str | None:
    """BibTeX-Eintrag aus den Kopfblock-Feldern, fuer .md ohne Feld bibtex (aeltere oder BIBTEX ausgeschaltet)."""
    titel = _text(werte.get("titel"))
    if zitierdaten is None or not titel:
        return None
    jahr, norm = _text(werte.get("jahr")), _text(werte.get("norm"))
    if norm and ":" in norm:
        bezeichnung, _, ausgabe = norm.rpartition(":")
        rest = titel.split(" – ", 1)[1] if titel.startswith(bezeichnung + " – ") else None
        return zitierdaten.bibtex_norm({"bezeichnung": bezeichnung, "ausgabe": ausgabe, "jahr": jahr or ausgabe[:4],
                                        "titel": rest, "herausgeber": _text(werte.get("autor")),
                                        "entwurf": bezeichnung.startswith("E ")})
    autoren = zitierdaten.personen_aus_text(_text(werte.get("autor")))
    herausgeber = zitierdaten.personen_aus_text(_text(werte.get("herausgeber")))
    if herausgeber and {n for _, n in autoren} <= {n for _, n in herausgeber}:
        autoren = []                                   # Sammelwerk: als "Autor" steht ein Herausgeber
    d = {"titel": titel, "autoren": autoren, "herausgeber": herausgeber, "jahr": jahr}
    for feld in ("verlag", "ort", "auflage", "isbn", "doi"):
        d[feld] = _text(werte.get(feld))
    return zitierdaten.bibtex_buch(d)


def literatur_plan() -> list[dict]:
    """Ein BibTeX-Eintrag je .md in Fertig (Feld bibtex, sonst aus dem Kopfblock), Schluessel eindeutig gemacht
    ("muster2016beispielkunde", "...b", "...c")."""
    if not FERTIG.is_dir():
        return []
    plan, vergeben = [], set()
    for md in sorted(FERTIG.glob("*.md")):
        try:
            with open(md, encoding="utf-8-sig") as f:
                werte, _ = kopf_lesen(f.read(50000))
        except OSError:
            continue
        eintrag = (_text(werte.get("bibtex")) or _bibtex_aus_kopf(werte)) if werte else None
        m = re.match(r"@\w+\{([^,\s]+),", eintrag or "")
        if not m:
            continue
        schluessel, n = m.group(1), 1
        while schluessel in vergeben:
            n += 1
            schluessel = m.group(1) + "abcdefghijklmnopqrstuvwxyz"[min(n, 26) - 1] + ("" if n <= 26 else str(n))
        vergeben.add(schluessel)
        plan.append({"name": md.stem, "schluessel": schluessel,
                     "eintrag": eintrag[:m.start(1)] + schluessel + eintrag[m.end(1):]})
    return plan


def literatur_schreiben(plan: list[dict], ziel: Path | None = None) -> Path:
    """Schreibt die Eintraege als BibTeX-Datei (Standard: Literatur.bib neben Fertig); eine vorhandene wird ersetzt."""
    ziel = ziel or FERTIG.parent / LITERATURLISTE
    kopf = f"% Literaturliste aus pdf2md ({date.today().isoformat()}): {len(plan)} Einträge aus {FERTIG.name}\n\n"
    with open(ziel, "w", encoding="utf-8", newline="\n") as f:
        f.write(kopf + "\n\n".join(e["eintrag"] for e in plan) + "\n")
    return ziel


def _anderer_zitierstil(werte: dict) -> bool:
    """Steht die Quellenangabe in einem anderen als dem eingestellten Stil? Aeltere .md ohne Feld: IEEE."""
    return (bool(werte.get("quellenangabe")) and zitierdaten is not None
            and werte.get("zitierstil", "IEEE") != zitierdaten.STILE[zitierstil()])


def text_plan() -> list[dict]:
    """PDFs in Fertig, deren Text nicht mit dem aktuellen Verfahren erzeugt wurde (textquelle im Kopfblock) oder deren
    Quellenangabe einen anderen Zitierstil hat."""
    if not FERTIG.is_dir():
        return []
    plan = []
    for md in sorted(FERTIG.glob("*.md")):
        original = original_zu_md(md)
        if original is None or original.suffix.lower() != ".pdf":
            continue
        with open(md, encoding="utf-8-sig") as f:
            werte, _ = kopf_lesen(f.read(8000))
        if werte is None or (werte.get("textquelle") == erwartete_textquelle() and not _anderer_zitierstil(werte)):
            continue                                          # schon mit diesem Verfahren (und Zitierstil) erzeugt
        plan.append({"md": md, "original": original, "name": md.stem})
    return plan


def text_erneuern(lauf: str, plan: list[dict] | None = None, abbrechen=None, datei_beginnt=None,
                  datei_fertig=None) -> int:
    """Wandelt den Text der PDFs aus text_plan() mit dem aktuellen Verfahren neu um. Namen, Ordner und Kopfblock (auch
    von Hand ergaenzte Angaben) bleiben, nur der Text darunter wird ersetzt; die alte .md kommt vorher nach Sicherung.
    abbrechen() wird vor jedem Buch gefragt; datei_beginnt(name, i, n) / datei_fertig(name, status) fuer das Fenster."""
    plan = text_plan() if plan is None else plan
    if not plan:
        return 0
    SICHERUNG.mkdir(exist_ok=True)
    konverter = MarkItDown(enable_plugins=False)
    erledigt = 0
    for i, eintrag in enumerate(plan, 1):
        if abbrechen is not None and abbrechen():
            break
        md, original = eintrag["md"], eintrag["original"]
        if datei_beginnt is not None:
            datei_beginnt(md.stem, i, len(plan))
        melden(f"[{i}/{len(plan)}] {md.stem}")
        status = "TEXT_ERNEUERT"
        try:
            with open(md, encoding="utf-8-sig") as f:
                werte, _ = kopf_lesen(f.read())
            text, quelle, formelstatistik = umwandeln(original, werte.get("seiten"), konverter)
            if len(nutztext(text).strip()) < MIN_TEXT_ZEICHEN:
                status = "ÜBERSPRUNGEN  kaum Text erkannt, alte .md bleibt unverändert"
                melden("   " + status)
                continue
            sicherung = SICHERUNG / md.name
            n = 2
            while sicherung.exists():
                sicherung = SICHERUNG / f"{md.stem} ({n}).md"
                n += 1
            shutil.copy2(md, sicherung)
            werte["textquelle"] = quelle
            werte.pop("warnung", None)
            _verfahrensfelder(werte, formelstatistik)
            # Quellenangabe ergaenzen; von Hand eingetragene Angaben bleiben, nur eine reine Offline-Angabe wird ersetzt
            info = {"titel": _text(werte.get("titel")), "autor": _text(werte.get("autor")),
                    "jahr": _text(werte.get("jahr")), "kennung": _text(werte.get("kennung")),
                    "kennungen": [werte["kennung"]] if werte.get("kennung") else []}
            zitat, text = zitierangaben(info, text, (formelstatistik or {}).get("norm"))
            ersetzen = (str(werte.get("zitierdaten_quelle", "")).startswith("nur ")
                        and not str(zitat.get("zitierdaten_quelle", "nur ")).startswith("nur "))
            neuer_stil = _anderer_zitierstil(werte)              # anderer Zitierstil eingestellt: Angabe neu setzen
            for feld, wert in zitat.items():
                if (feld not in werte or ersetzen or feld == "kapitelquellen"
                        or (neuer_stil and feld in ("quellenangabe", "zitierstil"))):
                    werte[feld] = wert
            if kodierung_defekt(text):
                werte["warnung"] = ("Umlaute fehlen teilweise (defekte Schriftkodierung im PDF, "
                                    "nur per Texterkennung behebbar)")
                melden("   WARNUNG Umlaute fehlen teilweise (defekte Schriftkodierung im PDF)")
            werte["text_erneuert_am"] = date.today().isoformat()
            md_schreiben(md, kopf_schreiben(werte) + text)
            protokollieren(lauf, "TEXT_ERNEUERT", original_name=original.name, neuer_name=md.stem,
                           ordner=FERTIG.name, von_pfad=sicherung, nach_pfad=md, md_pfad=md,
                           titel=werte.get("titel"), autor=werte.get("autor"), jahr=werte.get("jahr"),
                           hinweis=werte.get("warnung", ""))
            erledigt += 1
        except Exception as e:
            status = f"FEHLER  {fehlertext(e, original)}  (alte .md bleibt unverändert)"
            melden("   " + status)
        finally:
            if datei_fertig is not None:
                datei_fertig(md.stem, status)
    melden(f"{erledigt} von {len(plan)} Text(e) erneuert. Die alten Fassungen liegen in {SICHERUNG}")
    return erledigt


def rueckgaengig_plan() -> dict | None:
    """Der letzte noch nicht zurueckgedrehte Lauf mit seinen Zeilen in Ruecklaufreihenfolge, oder None."""
    if not PROTOKOLL.exists():
        return None
    try:
        with open(PROTOKOLL, encoding="utf-8-sig", newline="") as f:
            zeilen = list(csv.DictReader(f, delimiter=";"))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None
    # nur vollstaendige Zeilen: ein von Hand (z.B. in Excel mit Komma) veraendertes Protokoll darf nichts verschieben
    zeilen = [z for z in zeilen if all(z.get(k) for k in ("lauf", "status", "von_pfad", "nach_pfad"))]
    schon_zurueck = {z["lauf"] for z in zeilen if z["status"] == "RÜCKGÄNGIG"}
    laeufe = [z["lauf"] for z in zeilen if z["status"] in ZURUECKDREHBAR and z["lauf"] not in schon_zurueck]
    if not laeufe:
        return None
    lauf = laeufe[-1]
    return {"lauf": lauf,
            "zeilen": list(reversed([z for z in zeilen if z["lauf"] == lauf and z["status"] in ZURUECKDREHBAR]))}


def rueckgaengig(plan: dict | None = None) -> int:
    """Dreht den Lauf aus rueckgaengig_plan() zurueck: Originale gehen an ihren alten Ort mit altem Namen, die .md wird
    daneben abgelegt (nichts wird geloescht)."""
    plan = rueckgaengig_plan() if plan is None else plan
    if plan is None:
        melden("Kein Lauf vorhanden, der noch rückgängig gemacht werden kann.")
        return 0
    lauf = plan["lauf"]
    melden(f"Lauf vom {lauf} wird zurückgedreht ...")
    erledigt = 0
    for z in plan["zeilen"]:
        von, nach = Path(z["von_pfad"]), Path(z["nach_pfad"])
        md = Path(z["md_pfad"]) if z.get("md_pfad") else None      # Path("") waere der aktuelle Ordner
        if von.exists() or not nach.exists():
            melden(f"   Übersprungen: {nach.name}  (Ziel belegt oder Datei nicht mehr da)")
            continue
        md_ziel = von.with_suffix(".md")
        try:
            von.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(nach), str(von))
        except OSError as e:               # gesperrt: diese Datei auslassen, die uebrigen trotzdem zurueckdrehen
            melden(f"   Übersprungen: {nach.name}  ({fehlertext(e, nach)})")
            continue
        if md is not None and md.is_file() and not md_ziel.exists():
            try:
                shutil.move(str(md), str(md_ziel))
            except OSError as e:
                melden(f"   Hinweis: {md.name} blieb liegen ({fehlertext(e, md)})")
        melden(f"   Zurück: {nach.name}  ->  {von}")
        protokollieren(lauf, "RÜCKGÄNGIG", original_name=z["original_name"], neuer_name=z["neuer_name"],
                       ordner=von.parent.name, von_pfad=nach, nach_pfad=von, md_pfad=md_ziel)
        erledigt += 1
    return erledigt


def dateien_sammeln(pfade: list[Path]) -> list[Path]:
    def brauchbar(p: Path) -> bool:
        return p.is_file() and p.suffix.lower() in UNTERSTUETZT and not p.name.startswith(("~$", "."))

    gefunden = []
    for p in pfade:
        if p.is_dir():
            gefunden += sorted(x for x in p.iterdir() if brauchbar(x))
        elif brauchbar(p):
            gefunden.append(p)
        else:
            melden(f"ÜBERSPRUNGEN  {p}  (Format nicht unterstützt)")
    return gefunden


def fehlertext(e: BaseException, datei: Path) -> str:
    """Verstaendliche Fehlermeldung fuer das Fenster und das Protokoll statt der Ausnahme der Bibliothek
    ("File conversion failed after 2 attempts: - DocxConverter threw BadZipFile ...")."""
    roh = f"{type(e).__name__}: {e}"
    format_ = datei.suffix.lstrip(".").upper() or "Datei"
    try:
        leer = datei.is_file() and datei.stat().st_size == 0
    except OSError:
        leer = False
    if leer or "empty file" in roh:
        return "leere Datei (0 Byte)"
    if isinstance(e, PermissionError) or "WinError 32" in roh or "being used by another process" in roh:
        return "Datei ist gesperrt, vermutlich in einem anderen Programm geöffnet: schließen und erneut starten"
    if re.search(r"decrypt|password|encrypt", roh, re.IGNORECASE):
        return "passwortgeschützt: ohne Passwort neu speichern (z. B. „Als PDF drucken“) und erneut hinzufügen"
    if re.search(r"BadZipFile|not a zip file|KeyError.*(?:archive|item named)|container\.xml", roh, re.IGNORECASE):
        return f"beschädigt oder kein gültiges {format_} (Dateistruktur fehlerhaft)"
    if datei.suffix.lower() == ".pdf" and re.search(
            r"Stream has ended|EOF marker|startxref|PdfReadError|PdfiumError|Failed to load|not a PDF|invalid pdf",
            roh, re.IGNORECASE):
        return "beschädigtes oder unvollständiges PDF (oder kein echtes PDF)"
    erste = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return erste[:200]


def eingang_verarbeiten(lauf: str, melder=None, fortschritt=None, abbrechen=None, datei_beginnt=None,
                        datei_fertig=None) -> dict:
    """Der Lauf hinter "Starten": alle Dateien aus Eingang, danach nachbessern() fuer Prüfen (wie frueher bei jedem
    Programmstart). abbrechen() wird vor jeder Datei gefragt, eine angefangene Datei wird immer fertig. Eine Datei mit
    Fehler bleibt unveraendert im Eingang. datei_beginnt(name, i, n) / datei_fertig(name, status) fuer das Fenster."""
    ergebnis = {"ok": 0, "pruefen": 0, "fehler": 0, "nachgebessert": 0, "abgebrochen": False}
    with rueckmeldung(melder, fortschritt):
        EINGANG.mkdir(parents=True, exist_ok=True)
        dateien = dateien_sammeln([EINGANG])
        konverter = MarkItDown(enable_plugins=False) if dateien else None
        for i, datei in enumerate(dateien, 1):
            if abbrechen is not None and abbrechen():
                ergebnis["abgebrochen"] = True
                break
            if datei_beginnt is not None:
                datei_beginnt(datei.name, i, len(dateien))
            melden(f"[{i}/{len(dateien)}] {datei.name}")
            try:
                status = verarbeiten(datei, konverter, lauf)
                ergebnis["pruefen" if status.startswith("PRÜFEN") else "ok"] += 1
            except Exception as e:  # eine kaputte Datei soll den Rest nicht stoppen
                ergebnis["fehler"] += 1
                grund = fehlertext(e, datei)
                status = f"FEHLER  {datei.name}: {grund}  (Original blieb unverändert)"
                protokollieren(lauf, "FEHLER", original_name=datei.name, von_pfad=datei.resolve(),
                               hinweis=f"{grund} [{type(e).__name__}: {str(e)[:300]}]")
            melden("   " + status)
            if datei_fertig is not None:
                datei_fertig(datei.name, status)
        if not ergebnis["abgebrochen"]:
            ergebnis["nachgebessert"] = nachbessern(lauf)
    return ergebnis


def main() -> int:
    """Startet das Fenster (ui_app.py). Kommandozeilen-Schalter gibt es nicht mehr, alles laeuft ueber die Oberflaeche."""
    import ui_app
    return ui_app.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # noetig, damit die Unterprozesse in der .exe starten
    sys.exit(main())
