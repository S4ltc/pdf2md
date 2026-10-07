"""Einstellungen von pdf2md: jede einstellbare Konstante der Module genau einmal beschrieben.

Ein Eintrag nennt Modul, Attribut, Typ, Bereich, Standard, Gruppe, Stufe (normal/experte) und den Tooltip. Gespeichert
werden nur die vom Standard abweichenden Werte in Einstellungen.json neben dem Programm; so greifen neue Standardwerte
einer spaeteren Version automatisch. anwenden() setzt die Werte als Modulattribute (die Module lesen ihre Konstanten
zur Laufzeit) und berechnet abgeleitete Werte neu (tabellen.MIN_UEBERSTAND = 3 * TOLERANZ).

Bewusst keine Einstellung: USER_AGENT (Datenschutz, eigener Test), DIAGNOSE (nur fuer Tests), Regex-Muster, Pfade,
Zeichensaetze, Zuordnungstabellen, Marker und Textvorlagen. Die Standardwerte der Expertenstufe sind an 58 Buechern
und 56 Normen gemessen (siehe CLAUDE.md); ein Test prueft, dass sie mit dem Code uebereinstimmen."""

import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DATEINAME = "Einstellungen.json"
CPU = os.cpu_count() or 8
GRUPPEN = ("Umwandlung", "Text und Seiten", "Seitenzahlen und Zitieren", "Formeln", "Tabellen", "Zeichen", "Spalten",
           "Normen", "Metadaten und Online", "Ablage")
AN = ("1", "true", "an", "ja", "ein", "on", "yes")
AUS = ("0", "false", "aus", "nein", "off", "no", "")


@dataclass(frozen=True)
class Einstellung:
    schluessel: str                                 # "tabellen.TOLERANZ"
    typ: str                                        # "bool" | "int" | "float" | "wahl"
    standard: Any
    gruppe: str
    stufe: str                                      # "normal" | "experte"
    titel: str                                      # Beschriftung im Fenster
    hilfe: str                                      # Tooltip: was es bewirkt, wann man es aendert (ohne Standard)
    bereich: tuple[float, float] | None = None
    schritt: float | None = None
    einheit: str = ""
    optionen: tuple[tuple[str, str], ...] = ()      # (Wert, Anzeige) fuer typ "wahl"

    @property
    def modul(self) -> str:
        return self.schluessel.split(".", 1)[0]

    @property
    def name(self) -> str:
        return self.schluessel.split(".", 1)[1]


def _schalter(name, gruppe, titel, hilfe, standard=True):
    return Einstellung(f"pdf2md.{name}", "bool", standard, gruppe, "normal", titel, hilfe)


def _zahl(schluessel, standard, von, bis, schritt, gruppe, titel, hilfe, einheit="", stufe="experte"):
    typ = "int" if isinstance(standard, int) and isinstance(schritt, int) else "float"
    return Einstellung(schluessel, typ, standard, gruppe, stufe, titel, hilfe, (von, bis), schritt, einheit)


EINSTELLUNGEN: tuple[Einstellung, ...] = (
    # ------------------------------------------------------------ normal
    Einstellung("pdf2md.PDF_ENGINE", "wahl", "pdfium", "Umwandlung", "normal", "PDF-Engine",
                "Womit der Text aus PDFs gelesen wird. MarkItDown nur wählen, wenn PDFium eine Datei nicht lesen kann; "
                "es klebt Wörter zusammen und macht aus Formeln Tabellen.",
                optionen=(("pdfium", "PDFium"), ("markitdown", "MarkItDown"))),
    _zahl("pdf2md.MAX_PROZESSE", CPU, 1, 2 * CPU, 1, "Umwandlung", "Parallele Prozesse",
          "So viele Prozessorkerne nutzt der MarkItDown-Weg für große PDFs gleichzeitig. Verringern, wenn der Rechner "
          "während eines Laufs zu träge wird.", stufe="normal"),
    _schalter("FORMELN_REPARIEREN", "Formeln", "Formelzeichen reparieren",
              "Repariert unlesbare oder vertauschte Zeichen in Formelschriften über Glyphnamen und Formvergleich. "
              "Nur ausschalten, wenn ein Buch damit sehr langsam wird oder Fehler auftreten."),
    _schalter("FORMELSATZ", "Formeln", "Formelsatz als LaTeX",
              "Setzt Indizes, Exponenten, Brüche, Wurzeln und Summen als LaTeX und markiert unsichere Formeln. "
              "Ausschalten, wenn reiner Text ohne LaTeX gebraucht wird."),
    _schalter("UEBERSCHRIFTEN_AUS_LESEZEICHEN", "Text und Seiten", "Überschriften aus Lesezeichen",
              "Macht aus den Lesezeichen des PDFs Markdown-Überschriften. Ausschalten, wenn die Lesezeichen eines PDFs "
              "unbrauchbar sind."),
    _schalter("SPALTENREIHENFOLGE", "Text und Seiten", "Spaltenreihenfolge korrigieren",
              "Bringt zweispaltige Seiten in Lesereihenfolge, wenn das PDF die rechte Spalte vor der linken liefert. "
              "Nur zur Fehlersuche ausschalten."),
    _schalter("ZEICHEN_KORRIGIEREN", "Text und Seiten", "Zeichenfehler korrigieren",
              "Korrigiert getrennte Umlaute wie „fü r“, Symbol- und Wingdings-Zeichen sowie Texte in falscher "
              "Kodierung. Nur zur Fehlersuche ausschalten."),
    _schalter("TABELLEN_ERKENNEN", "Tabellen", "Tabellen erkennen",
              "Setzt Tabellen mit gezeichneten Linien als Markdown-Tabellen. Ausschalten, wenn die Tabellen als "
              "Fließtext besser lesbar sind."),
    _schalter("NORMEN_ERKENNEN", "Normen", "Normen erkennen",
              "Erkennt DIN-, EN- und ISO-Normen und übernimmt Nummer, Ausgabe, Titel und Herausgeber von der Norm "
              "selbst. Ausschalten, wenn ein Buch fälschlich als Norm erkannt wird."),
    _schalter("SEITENMARKER", "Seitenzahlen und Zitieren", "Seitenmarker",
              "Setzt vor jede Seite einen Marker mit gedruckter und PDF-Seitenzahl, damit eine KI mit Seitenangabe "
              "zitieren kann. Nur ausschalten, wenn keine Seitenangaben gebraucht werden."),
    _schalter("GEDRUCKTE_SEITENZAHLEN", "Seitenzahlen und Zitieren", "Gedruckte Seitenzahlen",
              "Ermittelt die gedruckte Seitenzahl aus dem Seitenlabel oder der Kopf- und Fußzeile. Ausgeschaltet nennen "
              "die Marker nur die Position im PDF."),
    _schalter("ONLINE_ABGLEICH", "Metadaten und Online", "Online-Abgleich",
              "Schlägt fehlende Angaben und die Quellenangabe bei Crossref und der DNB nach; gesendet wird nur DOI "
              "oder ISBN. Ausschalten für Läufe ganz ohne Internet."),
    _zahl("pdf2md.ONLINE_TIMEOUT", 10, 2, 60, 1, "Metadaten und Online", "Wartezeit online",
          "So lange wird auf eine Antwort von Crossref oder der DNB gewartet. Erhöhen bei langsamer Verbindung.",
          einheit="s", stufe="normal"),
    _schalter("JAHR_AUS_ERSTELLDATUM", "Metadaten und Online", "Jahr aus Erstellungsdatum",
              "Nimmt das Erstellungsdatum der Datei als Erscheinungsjahr, wenn sonst keins gefunden wird. Das ist "
              "meist falsch, deshalb nur für eigene Dokumente einschalten.", standard=False),
    _zahl("pdf2md.MAX_NAME_LEN", 120, 60, 200, 5, "Ablage", "Länge des Dateinamens",
          "Höchstlänge des neuen Dateinamens ohne Endung; gekürzt wird nur der Titel. Verringern, wenn Pfade zu lang "
          "werden.", einheit="Zeichen", stufe="normal"),
    # ------------------------------------------------------------ pdf2md, Experte
    _zahl("pdf2md.MIN_TEXT_ZEICHEN", 200, 0, 2000, 50, "Ablage", "Mindesttext",
          "Mit weniger Text gilt eine Datei als Scan ohne Texterkennung und kommt nach Prüfen. Senken für sehr kurze "
          "Dokumente.", einheit="Zeichen"),
    _zahl("pdf2md.MIN_TEXT_DOKUMENT", 20, 0, 500, 10, "Ablage", "Mindesttext bei Office, EPUB und HTML",
          "Mit weniger Text gilt eine DOCX-, PPTX-, XLSX-, EPUB- oder HTML-Datei als fast leer und kommt nach Prüfen. "
          "Erhöhen, wenn leere Vorlagen in Fertig landen.", einheit="Zeichen"),
    _zahl("pdf2md.JAHR_SUCHTEXT", 15000, 2000, 100000, 1000, "Metadaten und Online", "Suchbereich für das Jahr",
          "So viele Zeichen vom Anfang werden nach dem Copyright-Jahr durchsucht. Erhöhen, wenn das Impressum weit "
          "hinten steht.", einheit="Zeichen"),
    _zahl("pdf2md.MAX_UEBERSCHRIFT", 200, 50, 500, 10, "Text und Seiten", "Länge der Überschrift",
          "Längere Lesezeichen-Titel werden abgeschnitten. Erhöhen, wenn lange Kapiteltitel gekürzt erscheinen.",
          einheit="Zeichen"),
    _zahl("pdf2md.KOPF_FUSS_MIN_SEITEN", 8, 3, 30, 1, "Text und Seiten", "Kopf- und Fußzeilen: Mindestanzahl",
          "So oft muss eine Zeile am Seitenrand vorkommen, damit sie als Kopf- oder Fußzeile entfernt wird. Erhöhen, "
          "wenn echter Text fehlt, senken, wenn Kopfzeilen stehen bleiben.", einheit="Seiten"),
    _zahl("pdf2md.KOPF_FUSS_MAX_LAENGE", 300, 50, 600, 10, "Text und Seiten", "Kopf- und Fußzeilen: Höchstlänge",
          "Längere Zeilen gelten nie als Kopf- oder Fußzeile. Nur für sehr lange Wasserzeichen erhöhen.",
          einheit="Zeichen"),
    _zahl("pdf2md.KOPF_FUSS_RAND", 3, 1, 6, 1, "Text und Seiten", "Kopf- und Fußzeilen: Randzeilen",
          "So viele Zeilen am Seitenanfang und -ende werden auf Kopf- und Fußzeilen geprüft. Erhöhen, wenn Kopfzeilen "
          "hinter Spalten- oder Bildtext stehen bleiben.", einheit="Zeilen"),
    _zahl("pdf2md.TITEL_MAX_ZEILEN", 5, 1, 10, 1, "Text und Seiten", "Überschrift: Zeilen im Text",
          "So viele Zeilen darf ein im Text umbrochener Lesezeichen-Titel umfassen. Erhöhen, wenn lange Titel doppelt "
          "erscheinen.", einheit="Zeilen"),
    _zahl("pdf2md.KOLUMNENTITEL_RAND", 2, 1, 5, 1, "Seitenzahlen und Zitieren", "Kolumnentitel: Randzeilen",
          "So viele Zeilen oben und unten können einen Kolumnentitel mit Seitenzahl enthalten. Erhöhen, wenn "
          "Kolumnentitel im Text stehen bleiben.", einheit="Zeilen"),
    _zahl("pdf2md.KOLUMNENTITEL_ANTEIL", 0.3, 0.05, 0.9, 0.05, "Seitenzahlen und Zitieren",
          "Kolumnentitel: Anteil der Seiten",
          "Kolumnentitel werden nur entfernt, wenn mindestens dieser Anteil der Seiten einen hat. Senken, wenn sie in "
          "kurzen Dokumenten stehen bleiben."),
    _zahl("pdf2md.PARALLEL_AB_SEITEN", 150, 20, 1000, 10, "Umwandlung", "Parallel ab",
          "Ab dieser Seitenzahl teilt der MarkItDown-Weg ein PDF in Pakete und wandelt sie parallel um. Beim "
          "PDFium-Weg ohne Wirkung.", einheit="Seiten"),
    _zahl("pdf2md.SEITEN_PRO_PAKET", 40, 10, 200, 5, "Umwandlung", "Seiten je Paket",
          "Seiten je Paket beim parallelen MarkItDown-Weg. Größere Pakete brauchen mehr Speicher je Prozess.",
          einheit="Seiten"),
    # ------------------------------------------------------------ formeln (Formelreparatur)
    _zahl("formeln.MAX_PROBEN", 8, 2, 30, 1, "Formeln", "Formvergleich: Proben je Zeichen",
          "So viele Vorkommen je unlesbarem Zeichen werden gerendert und verglichen. Mehr Proben sind sicherer, aber "
          "langsamer."),
    _zahl("formeln.RENDER_SKALA", 4, 2, 8, 1, "Formeln", "Formvergleich: Renderskala",
          "Vergrößerung beim Rendern der Seiten für den Formvergleich, 4 entspricht etwa 290 dpi. Höher erkennt kleine "
          "Zeichen besser, kostet aber deutlich Zeit.", einheit="×"),
    _zahl("formeln.GEO_GEWICHT", 0.5, 0.0, 2.0, 0.05, "Formeln", "Formvergleich: Gewicht der Lage",
          "Wie stark Höhe und Lage eines Zeichens gegenüber seiner Form zählen. An zwei Datensätzen gemessen, nur mit "
          "neuer Messung ändern."),
    _zahl("formeln.GEO_RELIEF", 0.2, 0.0, 1.0, 0.05, "Formeln", "Formvergleich: Lage bei Akzenten",
          "Gewicht der Lage für Zeichen, deren Höhe je nach Schrift stark schwankt, etwa Striche, Akzente und Wurzel. "
          "Nur mit neuer Messung ändern."),
    _zahl("formeln.MIN_ABSTAND", 0.12, 0.0, 0.5, 0.01, "Formeln", "Formvergleich: Vorsprung vor dem Original",
          "So viel besser als das Originalzeichen muss ein Ersatz in verdächtigen Schriften passen. Erhöhen, wenn "
          "richtige Zeichen ersetzt werden."),
    _zahl("formeln.MIN_WERT", 0.6, 0.3, 0.95, 0.01, "Formeln", "Formvergleich: Mindestwert",
          "Mindestpunktzahl eines Ersatzzeichens aus Ähnlichkeit minus Lagestrafe. An zwei Datensätzen gemessen, "
          "Senken erzeugt Fehlersetzungen."),
    _zahl("formeln.MIN_MARGE", 0.06, 0.0, 0.3, 0.01, "Formeln", "Formvergleich: Abstand zum Zweitbesten",
          "So viel besser als das zweitbeste Zeichen muss der Sieger sein. An zwei Datensätzen gemessen, Senken "
          "erzeugt Fehlersetzungen."),
    _zahl("formeln.GLYPH_GROESSE", 160, 64, 320, 16, "Formeln", "Formvergleich: Größe der Vergleichszeichen",
          "Größe, in der die Vergleichszeichen aus STIX und DejaVu gerendert werden. Größer ist genauer, aber "
          "langsamer.", einheit="px"),
    _zahl("formeln.RASTER", 28, 12, 64, 2, "Formeln", "Formvergleich: Profilraster",
          "Auflösung der Formprofile, mit denen Zeichen verglichen werden. Nur mit neuer Messung ändern."),
    # ------------------------------------------------------------ lesefolge (Spalten)
    _zahl("lesefolge.LUECKE", 3.0, 1.0, 10.0, 0.5, "Spalten", "Lücke in der Zeile",
          "Ab dieser Lücke innerhalb einer Zeile beginnt ein neues Zeilenstück. Senken, wenn eng stehende Spalten "
          "nicht getrennt werden.", einheit="Zeichenhöhen"),
    _zahl("lesefolge.MIN_LAEUFE", 12, 4, 40, 1, "Spalten", "Mindestzahl Zeilenstücke",
          "Seiten mit weniger Zeilenstücken bleiben unverändert. Senken für kurze zweispaltige Seiten."),
    _zahl("lesefolge.MIN_BREITE", 100.0, 20.0, 400.0, 10.0, "Spalten", "Mindestbreite des Textes",
          "Schmalerer Seitentext wird nie umsortiert. Senken für kleine Seitenformate.", einheit="pt"),
    _zahl("lesefolge.MIN_SPALTENZEILEN", 5, 2, 20, 1, "Spalten", "Zeilen je Spalte",
          "So viele fast volle Zeilen braucht jede Spalte. Senken, wenn kurze Spalten nicht erkannt werden.",
          einheit="Zeilen"),
    _zahl("lesefolge.LANG", 0.3, 0.1, 0.6, 0.05, "Spalten", "Textzeile ab Breite",
          "Ab diesem Anteil der Textbreite gilt ein Zeilenstück als eigene Textzeile, sonst hängt es am vorigen. Nur "
          "mit neuer Messung ändern."),
    _zahl("lesefolge.BREIT", 0.6, 0.4, 0.95, 0.05, "Spalten", "Breite Zeile ab",
          "Ab diesem Anteil der Textbreite reicht ein Zeilenstück über beide Spalten. Senken, wenn Überschriften über "
          "beiden Spalten falsch einsortiert werden."),
    _zahl("lesefolge.STEG_MIN", 5.0, 1.0, 30.0, 0.5, "Spalten", "Mindestbreite der Spaltenlücke",
          "So breit muss die Lücke zwischen zwei Spalten mindestens sein. Erhöhen, wenn Tabellen fälschlich als "
          "Spalten gelten.", einheit="pt"),
    _zahl("lesefolge.TOLERANZ", 6.0, 1.0, 30.0, 0.5, "Spalten", "Versatz der Spalten",
          "So weit darf eine Spalte über oder unter der anderen beginnen oder enden. Erhöhen bei versetzten Spalten.",
          einheit="pt"),
    _zahl("lesefolge.DURCHLAESSIG", 0.25, 0.0, 0.6, 0.05, "Spalten", "Zeilen über der Lücke",
          "Anteil der Zeilen, die die Spaltenlücke überqueren dürfen, etwa breite Formeln oder Tabellen. Erhöhen, wenn "
          "Seiten mit vielen Formeln nicht umsortiert werden."),
    # ------------------------------------------------------------ zeichen
    _zahl("zeichen.MIN_DOPPELTE_ZEILEN", 3, 1, 20, 1, "Zeichen", "Doppeldruck: Mindestzeilen",
          "So viele längere Zeilen müssen doppelt vorkommen, bevor eine Seite auf doppelt gedruckten Text geprüft "
          "wird. Senken, wenn Doppeldrucke stehen bleiben.", einheit="Zeilen"),
    _zahl("zeichen.MIN_ANTEIL_DOPPELT", 0.9, 0.5, 1.0, 0.01, "Zeichen", "Doppeldruck: Übereinstimmung",
          "So viel einer Zeile muss an derselben Stelle schon stehen, damit sie als Kopie wegfällt. Senken erhöht das "
          "Risiko, echten Text zu verlieren."),
    _zahl("zeichen.MIN_BEWEIS", 5, 1, 30, 1, "Zeichen", "Mac-Roman: Belege",
          "So oft müssen Mac-Roman-Zeichen mitten im Wort stehen, bevor eine Schrift umkodiert wird. Erhöhen, wenn "
          "Sonderzeichen fälschlich zu Umlauten werden."),
    _zahl("zeichen.MIN_WOERTER", 3, 1, 20, 1, "Zeichen", "Mac-Roman: Wörter",
          "In so vielen verschiedenen Wörtern müssen diese Belege vorkommen. Erhöhen, wenn Sonderzeichen fälschlich zu "
          "Umlauten werden."),
    # ------------------------------------------------------------ normen
    _zahl("normen.SCHRIFTGROESSE_TOLERANZ", 0.6, 0.1, 3.0, 0.1, "Normen", "Titel: Schriftgröße",
          "So weit darf die Schriftgröße einer Titelzeile von der ersten abweichen. Erhöhen, wenn Normtitel "
          "unvollständig sind.", einheit="pt"),
    _zahl("normen.DECKBLATT_SEITEN", 4, 1, 10, 1, "Normen", "Seiten bis zur Titelseite",
          "So viele Seiten vom Anfang werden nach der Titelseite der Norm durchsucht. Erhöhen, wenn ein Normtitel "
          "fehlt.", einheit="Seiten"),
    # ------------------------------------------------------------ tabellen
    _zahl("tabellen.MAX_DICKE", 2.5, 0.5, 6.0, 0.1, "Tabellen", "Linie: Höchstdicke",
          "Dickere Striche sind Flächen, keine Tabellenlinien. Erhöhen für Tabellen mit sehr dicken Linien.",
          einheit="pt"),
    _zahl("tabellen.MIN_LAENGE", 4.0, 1.0, 20.0, 0.5, "Tabellen", "Linie: Mindestlänge",
          "Kürzere Strecken gelten als Punkte oder Ecken. Senken für sehr kleine Tabellen.", einheit="pt"),
    _zahl("tabellen.TOLERANZ", 2.0, 0.5, 8.0, 0.5, "Tabellen", "Linien: Toleranz",
          "So nah müssen Linienenden und Kreuzungen beieinander liegen. Erhöhen, wenn Gitter mit ungenau gezeichneten "
          "Linien zerfallen.", einheit="pt"),
    _zahl("tabellen.MIN_ZEILEN", 2, 1, 6, 1, "Tabellen", "Mindestzeilen",
          "So viele Zeilen braucht ein Gitter, um als Tabelle zu gelten. Erhöhen, wenn kleine Rahmen als Tabelle "
          "erscheinen."),
    _zahl("tabellen.MIN_SPALTEN", 2, 1, 6, 1, "Tabellen", "Mindestspalten",
          "So viele Spalten braucht ein Gitter, um als Tabelle zu gelten. Erhöhen, wenn Kästen als Tabelle "
          "erscheinen."),
    _zahl("tabellen.MIN_BELEGT", 0.25, 0.0, 1.0, 0.05, "Tabellen", "Belegte Zellen",
          "Mindestanteil der Zellen mit Text. Erhöhen, wenn Zeichnungen als Tabelle erscheinen."),
    _zahl("tabellen.MIN_GEFUELLT", 3, 1, 20, 1, "Tabellen", "Gefüllte Zellen",
          "So viele Zellen mit Text braucht eine Tabelle, verteilt auf mindestens zwei Zeilen und Spalten. Erhöhen, "
          "wenn leere Formblätter als Tabelle erscheinen."),
    _zahl("tabellen.MAX_SCHNITTE", 1, 0, 10, 1, "Tabellen", "Wortschnitte",
          "So oft darf eine Gitterlinie ein Wort zerschneiden, bevor das Gitter als Zeichnung gilt. Erhöhen, wenn "
          "echte Tabellen wegfallen."),
    _zahl("tabellen.DUENN", 0.5, 0.0, 1.0, 0.05, "Tabellen", "Dünn gefüllt unter",
          "Gitter mit weniger gefüllten Zellen gelten als dünn und brauchen ein regelmäßiges Raster. Senken, wenn "
          "lückenhafte Tabellen wegfallen."),
    _zahl("tabellen.MIN_REGELMAESSIG", 0.6, 0.0, 1.0, 0.05, "Tabellen", "Regelmäßigkeit",
          "So regelmäßig muss ein dünn gefülltes Gitter sein, gemessen in Zellen je Rasterfeld. Erhöhen, wenn "
          "Schaltbilder als Tabelle erscheinen."),
    _zahl("tabellen.KLEIN", 16, 4, 64, 1, "Tabellen", "Kleiner Rahmen bis",
          "Dünn gefüllte Gitter bis zu dieser Zellenzahl gelten als Rahmen um eine Abbildung. Senken, wenn kleine "
          "echte Tabellen wegfallen.", einheit="Zellen"),
    _zahl("tabellen.MIN_TEXTLAENGE", 15, 1, 60, 1, "Tabellen", "Text je Zelle in Rahmen",
          "Kleine, dünn gefüllte Gitter mit kürzerem Text je Zelle gelten als beschriftete Abbildung. Senken, wenn "
          "kleine Zahlentabellen wegfallen.", einheit="Zeichen"),
    _zahl("tabellen.MAX_ZELLEN", 5000, 500, 20000, 500, "Tabellen", "Höchstzahl Zellen",
          "Größere Raster wie Millimeterpapier werden nicht als Tabelle gelesen. Nur für sehr große Tabellen "
          "erhöhen.", einheit="Zellen"),
    _zahl("tabellen.MAX_FREIES_ENDE", 0.5, 0.0, 1.0, 0.05, "Tabellen", "Freies Linienende",
          "Frei hängende Linienenden bis zu diesem Anteil der Länge werden gekürzt, längere Linien fallen weg. Senken, "
          "wenn Zeichnungslinien in Tabellen geraten."),
    _zahl("tabellen.LINIEN_MIN_BREITE", 0.25, 0.05, 0.9, 0.05, "Tabellen", "Linientabelle: Linienbreite",
          "Tabellen nur aus waagerechten Linien brauchen Linien über mindestens diesen Anteil der Seitenbreite. "
          "Erhöhen, wenn Unterstreichungen als Tabelle erscheinen."),
    _zahl("tabellen.LINIEN_GLEICH", 3.0, 0.5, 10.0, 0.5, "Tabellen", "Linientabelle: gleiche Linien",
          "So genau müssen Anfang und Ende der Linien einer Linientabelle übereinstimmen. Erhöhen bei ungenau "
          "gezeichneten Tabellen.", einheit="pt"),
    _zahl("tabellen.LINIEN_MAX_ABSTAND", 0.7, 0.2, 1.0, 0.05, "Tabellen", "Linientabelle: Höhe",
          "Anteil der Seitenhöhe, über den eine Linientabelle höchstens reicht. Erhöhen für ganzseitige Tabellen."),
    _zahl("tabellen.MIN_DATENZEILEN", 3, 1, 10, 1, "Tabellen", "Linientabelle: Datenzeilen",
          "So viele Zeilen braucht der Rumpf einer Linientabelle. Erhöhen, wenn Textkästen als Tabelle erscheinen.",
          einheit="Zeilen"),
    _zahl("tabellen.MIN_SPALTENLUECKE", 0.55, 0.1, 2.0, 0.05, "Tabellen", "Linientabelle: Spaltenlücke",
          "So breit muss der Leerraum zwischen zwei Spalten in jeder Zeile sein, gemessen in Schriftgrößen. Senken, "
          "wenn eng gesetzte Spalten verschmelzen.", einheit="× Schrift"),
    _zahl("tabellen.MAX_ZELLTEXT", 40, 10, 200, 5, "Tabellen", "Linientabelle: Text je Zelle",
          "Mittlere Zeichenzahl je Zelle, ab der eine Linientabelle als Fließtext gilt. Erhöhen für Tabellen mit "
          "langen Texten.", einheit="Zeichen"),
    # ------------------------------------------------------------ formelsatz
    _zahl("formelsatz.KLEINER", 0.85, 0.5, 0.98, 0.01, "Formeln", "Index: Größenverhältnis",
          "So viel kleiner als die Zeilenschrift muss ein Zeichen sein, um als Index oder Exponent zu gelten. Senken, "
          "wenn normaler Text hoch- oder tiefgestellt wird."),
    _zahl("formelsatz.HOCH", 0.15, 0.02, 0.5, 0.01, "Formeln", "Exponent: Höhe",
          "So weit über der Grundlinie beginnt ein Exponent, gemessen in Schriftgrößen. Erhöhen, wenn "
          "Fußnotenzeichen als Exponent erscheinen.", einheit="× Schrift"),
    _zahl("formelsatz.TIEF", 0.08, 0.01, 0.4, 0.01, "Formeln", "Index: Tiefe",
          "So weit unter der Grundlinie beginnt ein Index, gemessen in Schriftgrößen. Erhöhen, wenn tief stehende "
          "Buchstaben als Index erscheinen.", einheit="× Schrift"),
    _zahl("formelsatz.MAX_BALKEN_DICKE", 1.6, 0.2, 5.0, 0.1, "Formeln", "Bruchstrich: Höchstdicke",
          "Dickere Striche gelten nicht als Bruchstrich. Erhöhen, wenn fette Bruchstriche nicht erkannt werden.",
          einheit="pt"),
    _zahl("formelsatz.MIN_BALKEN", 2.0, 0.5, 20.0, 0.5, "Formeln", "Bruchstrich: Mindestlänge",
          "Kürzere Striche gelten nicht als Bruchstrich. Nur für sehr kleine Brüche senken.", einheit="pt"),
    _zahl("formelsatz.MAX_BALKEN", 360.0, 50.0, 800.0, 10.0, "Formeln", "Bruchstrich: Höchstlänge",
          "Längere Striche gelten als Trennlinie, nicht als Bruchstrich. Nur für sehr breite Formeln erhöhen.",
          einheit="pt"),
    _zahl("formelsatz.SUCHWEITE", 12, 1, 40, 1, "Formeln", "Index: Suchweite",
          "So viele Zeichen links und rechts wird das Bezugszeichen eines Index gesucht. Erhöhen, wenn Indizes an "
          "langen Ausdrücken verloren gehen.", einheit="Zeichen"),
    _zahl("formelsatz.ANGEHAENGT", 0.2, 0.0, 1.0, 0.05, "Formeln", "Index: Abstand zum Zeichen",
          "So dicht muss ein Index am Zeichen davor stehen, damit ein erzeugtes Leerzeichen ignoriert wird. Senken, "
          "wenn Wörter an Indizes kleben.", einheit="× Schrift"),
    _zahl("formelsatz.MAX_ZEILEN_BRUCH", 2, 1, 6, 1, "Formeln", "Bruch: Zeilen je Teil",
          "Zähler oder Nenner mit mehr Zeilen gelten als Tabelle mit Linie, nicht als Bruch. Nur für mehrzeilige "
          "Brüche erhöhen.", einheit="Zeilen"),
    _zahl("formelsatz.MAX_LUECKE_BRUCH", 1.5, 0.5, 5.0, 0.1, "Formeln", "Bruch: Lücke im Teil",
          "Größere Lücken in Zähler oder Nenner deuten auf Tabellenspalten statt auf einen Bruch. Erhöhen, wenn breite "
          "Brüche nicht erkannt werden.", einheit="× Schrift"),
    # ------------------------------------------------------------ seitenzahlen
    _zahl("seitenzahlen.RAND", 4, 1, 10, 1, "Seitenzahlen und Zitieren", "Suchzeilen am Rand",
          "So viele Zeilen am Seitenanfang und -ende werden nach der gedruckten Seitenzahl durchsucht. Erhöhen, wenn "
          "Seitenzahlen unter Fußnoten stehen.", einheit="Zeilen"),
    _zahl("seitenzahlen.MIN_BELEGE", 3, 1, 10, 1, "Seitenzahlen und Zitieren", "Belege je Abschnitt",
          "So viele Seiten müssen denselben Versatz zwischen gedruckter und PDF-Seite zeigen, damit ein Abschnitt "
          "gilt. Senken für Dokumente mit wenigen Seitenzahlen.", einheit="Seiten"),
    _zahl("seitenzahlen.MIN_DICHTE", 0.4, 0.05, 1.0, 0.05, "Seitenzahlen und Zitieren", "Dichte der Belege",
          "Mindestanteil der Seiten eines Abschnitts mit lesbarer Seitenzahl. Senken für bildreiche Bücher."),
    _zahl("seitenzahlen.MAX_LUECKE", 8, 1, 30, 1, "Seitenzahlen und Zitieren", "Lücke ohne Zahl",
          "So viele Seiten ohne lesbare Zahl darf ein Abschnitt überbrücken. Erhöhen für Bücher mit langen "
          "Bildstrecken.", einheit="Seiten"),
    _zahl("seitenzahlen.VERLAENGERUNG", 2, 0, 10, 1, "Seitenzahlen und Zitieren", "Verlängerung",
          "So viele Seiten vor und nach einem Abschnitt bekommen ebenfalls eine berechnete Zahl. Senken, wenn "
          "Kapitelanfänge falsche Zahlen bekommen.", einheit="Seiten"),
    _zahl("seitenzahlen.MIN_UEBEREINSTIMMUNG", 0.8, 0.3, 1.0, 0.05, "Seitenzahlen und Zitieren",
          "Label: Übereinstimmung",
          "So oft müssen Seitenlabel des PDFs und gedruckte Zahlen übereinstimmen, damit das Label gilt. Senken, wenn "
          "brauchbare Labels verworfen werden."),
    _zahl("seitenzahlen.VORSEITEN", 6, 0, 20, 1, "Seitenzahlen und Zitieren", "Normen: Vorseiten",
          "Nationale Vorseiten von Normen bis zu dieser Länge dürfen schon mit einem Beleg nummeriert werden. Senken, "
          "wenn Normdeckblätter falsche Zahlen bekommen.", einheit="Seiten"),
    # ------------------------------------------------------------ zitierdaten
    _zahl("zitierdaten.MAX_KAPITEL", 400, 0, 2000, 50, "Metadaten und Online", "Kapitel je Sammelwerk",
          "Höchstzahl der Kapitel-DOIs, die je Sammelwerk nachgeschlagen werden. Senken, wenn große Sammelwerke zu "
          "lange dauern."),
)
NACH_SCHLUESSEL: dict[str, Einstellung] = {e.schluessel: e for e in EINSTELLUNGEN}

# Werte, die aus Einstellungen folgen und beim Anwenden neu berechnet werden
ABGELEITET: dict[str, Callable[[dict], Any]] = {
    "tabellen.MIN_UEBERSTAND": lambda w: 3 * w["tabellen.TOLERANZ"],
    "zitierdaten.TIMEOUT": lambda w: w["pdf2md.ONLINE_TIMEOUT"],
}
# Aendern sich diese Werte, muessen die Vergleichszeichen der Formelreparatur neu gerendert werden
FORMEL_REFERENZ = ("formeln.GLYPH_GROESSE", "formeln.RASTER")


def standardwerte() -> dict[str, Any]:
    return {e.schluessel: e.standard for e in EINSTELLUNGEN}


def pruefen(schluessel: str, wert: Any) -> Any:
    """Wandelt einen Wert in den Typ der Einstellung und klemmt Zahlen in den Bereich. KeyError: keine Einstellung,
    ValueError: unbrauchbarer Wert."""
    e = NACH_SCHLUESSEL[schluessel]
    if e.typ == "bool":
        if isinstance(wert, str):
            if wert.strip().lower() in AN:
                return True
            if wert.strip().lower() in AUS:
                return False
            raise ValueError(f"{schluessel}: '{wert}' ist kein Ein/Aus-Wert")
        return bool(wert)
    if e.typ == "wahl":
        if wert not in {w for w, _ in e.optionen}:
            raise ValueError(f"{schluessel}: '{wert}' ist nicht erlaubt")
        return wert
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        raise ValueError(f"{schluessel}: '{wert}' ist keine Zahl") from None
    if zahl != zahl:                                            # NaN
        raise ValueError(f"{schluessel}: keine Zahl")
    zahl = min(max(zahl, e.bereich[0]), e.bereich[1])
    return int(round(zahl)) if e.typ == "int" else round(zahl, 6)


def laden(pfad: Path) -> dict[str, Any]:
    """Standardwerte, ueberschrieben von den gueltigen Werten aus der Datei. Fehlende oder kaputte Datei, unbekannte
    Schluessel und unbrauchbare Werte werden still uebergangen (das Programm startet immer)."""
    werte = standardwerte()
    try:
        gespeichert = json.loads(Path(pfad).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return werte
    if not isinstance(gespeichert, dict):
        return werte
    for schluessel, wert in gespeichert.items():
        try:
            werte[schluessel] = pruefen(schluessel, wert)
        except (KeyError, ValueError):
            continue
    return werte


def abweichungen(werte: dict[str, Any]) -> dict[str, Any]:
    return {e.schluessel: werte[e.schluessel] for e in EINSTELLUNGEN
            if e.schluessel in werte and werte[e.schluessel] != e.standard}


def speichern(pfad: Path, werte: dict[str, Any]) -> None:
    """Schreibt nur die Abweichungen vom Standard (erst in eine Hilfsdatei, dann ersetzen: nie eine halbe Datei)."""
    pfad = Path(pfad)
    tmp = pfad.with_name(pfad.name + ".tmp")
    tmp.write_text(json.dumps(abweichungen(werte), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, pfad)


def aktuell() -> dict[str, Any]:
    """Die Werte, mit denen die Module gerade arbeiten."""
    return {e.schluessel: getattr(importlib.import_module(e.modul), e.name) for e in EINSTELLUNGEN}


def anwenden(werte: dict[str, Any]) -> None:
    """Setzt die Werte als Modulattribute, danach die abgeleiteten Werte. Laeuft auch als initializer in den
    Unterprozessen der parallelen Umwandlung (die importieren die Module frisch mit den Standardwerten)."""
    vorher = aktuell()
    for e in EINSTELLUNGEN:
        if e.schluessel in werte:
            setattr(importlib.import_module(e.modul), e.name, pruefen(e.schluessel, werte[e.schluessel]))
    jetzt = aktuell()
    for schluessel, formel in ABGELEITET.items():
        modul, name = schluessel.split(".", 1)
        setattr(importlib.import_module(modul), name, formel(jetzt))
    if any(vorher[s] != jetzt[s] for s in FORMEL_REFERENZ):
        importlib.import_module("formeln")._REFERENZ = None


def anzeige(e: Einstellung, wert: Any) -> str:
    """Wert so, wie er im Fenster und im Tooltip steht: an/aus, Anzeigename der Auswahl, Zahl mit Komma und Einheit."""
    if e.typ == "bool":
        return "an" if wert else "aus"
    if e.typ == "wahl":
        return dict(e.optionen).get(wert, str(wert))
    text = f"{wert:g}".replace(".", ",") if e.typ == "float" else str(wert)
    return f"{text} {e.einheit}".strip()


def tooltip(e: Einstellung) -> str:
    return f"{e.hilfe} Standard: {anzeige(e, e.standard)}."


def abweichungstext(werte: dict[str, Any]) -> str | None:
    """Fuer den Kopfblock: "abweichend: FORMELSATZ=aus, tabellen.TOLERANZ=3" (Modul nur bei mehrdeutigem Namen)."""
    teile = []
    namen = [e.name for e in EINSTELLUNGEN]
    for schluessel, wert in abweichungen(werte).items():
        e = NACH_SCHLUESSEL[schluessel]
        name = e.name if namen.count(e.name) == 1 else schluessel
        if e.typ == "bool":
            text = "an" if wert else "aus"
        elif e.typ == "float":
            text = f"{wert:g}"
        else:
            text = str(wert)
        teile.append(f"{name}={text}")
    return "abweichend: " + ", ".join(teile) if teile else None


def fuer_ui(werte: dict[str, Any]) -> list[dict]:
    """Alle Einstellungen mit aktuellem Wert, so wie das Fenster sie braucht (in der Reihenfolge der Gruppen)."""
    reihenfolge = {g: i for i, g in enumerate(GRUPPEN)}
    eintraege = []
    for i, e in enumerate(EINSTELLUNGEN):
        eintraege.append({
            "schluessel": e.schluessel, "name": e.name, "typ": e.typ, "wert": werte.get(e.schluessel, e.standard),
            "standard": e.standard, "gruppe": e.gruppe, "stufe": e.stufe, "titel": e.titel, "tooltip": tooltip(e),
            "min": e.bereich[0] if e.bereich else None, "max": e.bereich[1] if e.bereich else None,
            "schritt": e.schritt, "einheit": e.einheit, "optionen": [list(o) for o in e.optionen],
            "_ordnung": (reihenfolge[e.gruppe], i)})
    eintraege.sort(key=lambda x: x.pop("_ordnung"))
    return eintraege
