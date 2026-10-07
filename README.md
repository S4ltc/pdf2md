# pdf2md

Wandelt Bücher, Normen und Dokumente in Markdown um (PDFs über PDFium mit eigener Text-, Formel- und
Tabellenaufbereitung, DOCX/PPTX/XLSX/EPUB/HTML über [MarkItDown](https://github.com/microsoft/markitdown)),
schreibt die Metadaten als Kopfblock in die `.md` und benennt Original und `.md` nach dem Schema
**`Titel - Autor - Jahr`** um. Gedacht für die Weiterverarbeitung der Texte in einer KI.

Unterstützte Formate: **PDF, DOCX, PPTX, XLSX, EPUB, HTML**.

## Download

1. Auf der Seite [Releases](https://github.com/S4ltc/pdf2md/releases/latest) die Datei `pdf2md-…-windows.zip`
   herunterladen.
2. In einen eigenen Ordner entpacken, zum Beispiel `Dokumente\pdf2md` (nicht unter „Programme“: neben der `.exe`
   entstehen die Arbeitsordner).
3. `pdf2md.exe` doppelklicken.

Voraussetzung ist Windows 10 oder 11 (64 Bit); Python wird nicht gebraucht. Die Anzeige nutzt Microsoft Edge
WebView2, das unter Windows 10/11 vorhanden ist. Beim ersten Start warnt Windows SmartScreen, weil die Datei nicht
digital signiert ist: „Weitere Informationen“ → „Trotzdem ausführen“. Wer sichergehen will, vergleicht die
Prüfsumme mit `SHA256SUMS.txt` aus dem Release (`Get-FileHash pdf2md-…-windows.zip` in PowerShell). Die `.exe`
entsteht automatisch auf einem Windows-Rechner von GitHub aus genau diesem Quellcode (`.github/workflows/release.yml`).

**Updates:** Oben im Fenster steht die Versionsnummer. Gibt es auf GitHub eine neuere Version, erscheint daneben
„Version … verfügbar“; ein Klick öffnet die Release-Seite. Zum Aktualisieren das neue ZIP herunterladen und nur
`pdf2md.exe` ersetzen. Die Ordner (`Eingang`, `Fertig`, `Prüfen`, `Sicherung`), `Protokoll.csv` und
`Einstellungen.json` bleiben, wie sie sind; neue Standardwerte greifen von selbst, weil nur Abweichungen gespeichert
werden. Danach unter Werkzeuge → „Text erneuern“ die vorhandenen Bücher mit dem neuen Verfahren umwandeln lassen.

## Datenschutz

- Alles läuft auf dem eigenen Rechner; es gibt keine Telemetrie und keine Anmeldung.
- Online geht nur eine Anfrage, wenn Angaben fehlen bzw. für die Quellenangabe: gesendet wird ausschließlich die
  DOI oder ISBN an Crossref und die Deutsche Nationalbibliothek, mit dem allgemeinen Kennzeichen `pdf2md/1.0`, ohne
  Dateiinhalt, Dateinamen, Namen oder E-Mail. Abschalten: Einstellungen → Online-Abgleich.
- Beim Start fragt das Fenster GitHub einmal nach der neuesten Version (öffentliche Release-Liste, Kennzeichen
  `pdf2md/1.0`; GitHub sieht dabei wie bei jedem Seitenaufruf die IP-Adresse). Heruntergeladen wird nichts.
  Abschalten: Einstellungen → Nach Updates suchen.
- Lizenzvermerke gekaufter Normen (Firmen- und Benutzername, Kunden- und Abonummern, Lizenzkennung) werden aus dem
  Text entfernt, damit sie nicht in die `.md` und von dort in eine KI gelangen.

## Benutzen (`pdf2md.exe`)

`pdf2md.exe` doppelklicken: es öffnet sich ein Fenster (hell oder dunkel wie Windows), in dem alles bedient wird.

1. **Hinzufügen …** (Strg+O) oder Dateien bzw. einen Ordner **ins Fenster ziehen**: die Dateien werden nach `Eingang`
   kopiert (das Original bleibt, wo es ist; bei gleichem Namen kommt ` (2)` dazu). Dateien direkt in den Ordner
   `Eingang` neben der `.exe` zu legen, geht weiterhin.
2. **Starten** (Strg+Enter): verarbeitet alles in `Eingang` und übernimmt fertig ausgefüllte Dateien aus `Prüfen`.
   Je Datei zeigt die Spalte Eingang Phase und Fortschritt (Seite x von y), unten steht das Laufprotokoll.
   **Abbrechen** greift nach der aktuellen Datei. Schließt man das Fenster während eines Laufs, fragt es nach.

| Bereich | Inhalt |
|---|---|
| **Übersicht** | Drei Spalten: Eingang (Name, Format, Größe), Prüfen (Grund, „bereit zur Übernahme“, sobald der Kopfblock vollständig ist), Fertig (neuer Name, Neueste oben, Filterfeld). Ein Klick auf den Namen öffnet die Datei mit dem Standardprogramm (in Prüfen und Fertig die `.md`, zum Beispiel um den Kopfblock zu ergänzen), das Formatkürzel daneben („PDF“) das Original; „Ordner“ im Spaltenkopf öffnet den Ordner im Explorer. Während eines Laufs steht die aktuelle Datei abgesetzt oben, darunter die Warteschlange. Darunter vier Kennzahlen und zwei kleine Diagramme. Die Listen aktualisieren sich selbst, wenn sich die Ordner ändern. |
| **Auswertung** | Bestand und Durchsatz (Dateien je Bereich, Formate, Seiten pro Minute je Lauf, Dauer gegen Seitenzahl), Metadaten-Qualität (Herkunft von Titel/Autor/Jahr, häufigste Prüfgründe, Anteil mit vollständiger IEEE-Quellenangabe), Text-Qualität (je Punkt Wert und höchstmögliche Anzahl, etwa „1.237 / 10.083 Formelzeilen“ unsicher markiert, gezählt über die Bücher, bei denen das Verfahren lief, dazu die Bücher mit den meisten offenen Stellen). |
| **Einstellungen** | Alle Schalter und Schwellen (siehe unten), mit Tooltip nach kurzem Verweilen. |
| **Werkzeuge** | Letzten Lauf rückgängig machen, Namen reparieren, Text erneuern, Literaturliste exportieren (BibTeX, siehe [Quellenangabe](#quellenangabe-ieee-apa-7-din-iso-690-bibtex)) (je mit Tooltip): jeweils erst eine vollständige Vorschau, ausgeführt wird erst nach Bestätigung. |

Ergebnis, neben der `.exe`:

| Ordner / Datei | Inhalt |
|---|---|
| `Fertig` | Titel, Autor und Jahr gefunden. Original und `.md` tragen den neuen Namen. |
| `Prüfen` | Mindestens eins davon fehlt, oder es ist ein Scan ohne Text. Der Originalname bleibt. |
| `Protokoll.csv` | Jede Aktion mit altem und neuem Namen, Ort und Quelle der Angaben (öffnet in Excel, Grundlage für Rückgängig und Auswertung). |
| `Einstellungen.json` | Nur die vom Standard abweichenden Einstellungen. Löschen setzt alles zurück. |

Das Original wird **verschoben und umbenannt** (nicht kopiert). Bei gleichem Namen wird ` (2)` angehängt.
Bei sehr langen Namen (über 120 Zeichen) wird nur der Titel gekürzt, Autor und Jahr bleiben immer im Namen:
zuerst fällt der Untertitel weg (`Titel – Untertitel` wird zu `Titel`), reicht das nicht, wird am Wortende mit `…` gekürzt.
Der volle Titel steht im Kopfblock der `.md`.

## Mit einer KI recherchieren und zitieren

Jede `.md` aus einer PDF bringt mit, was eine KI zum korrekten Zitieren braucht:

- **Literaturangabe:** `quellenangabe:` im Kopfblock (IEEE, APA 7 oder DIN ISO 690, Einstellung „Zitierstil“), dazu `bibtex:`; bei Sammelwerken je Kapitel `<!-- Kapitelquelle (IEEE): … -->`.
- **Seite:** jeder Seitenmarker nennt die gedruckte Seite, `<!-- Seite 197 (PDF 206) -->` heißt „S. 197“. Steht nur
  `<!-- PDF-Seite 3 -->`, gibt es keine gedruckte Seitenzahl.
- **Abschnitt:** Überschriften mit Nummer (`## 5.2 Anforderungen`), bei Normen die übliche Zitierform.
- **Warnungen:** `⚠[Formel unsicher]` vor Formeln, die im PDF geprüft werden müssen.

Eine Anweisung an die KI kann so lauten: *„Antworte nur mit Stellen aus den angehängten Dateien. Gib zu jeder Aussage
das wörtliche Zitat, die Quelle aus `quellenangabe` und die Seite aus dem Seitenmarker davor an (Format [Nr., S. x]).“*
Bei APA lautet das Format (Autor, Jahr, S. x), bei DIN ISO 690 (AUTOR Jahr, S. x); `zitierhinweis:` im Kopfblock
nennt es der KI ebenfalls.
Das wörtliche Zitat lässt sich im PDF mit Strg+F sofort finden und prüfen.

## Dateien in `Prüfen` nachbessern

1. Die `.md` in `Prüfen` mit einem Texteditor öffnen. Oben steht der Kopfblock. Zeile `pruefen:` nennt, was fehlt.
2. `titel`, `autor` und `jahr` ausfüllen (Anführungszeichen sind nicht nötig, das Jahr muss vierstellig sein).
3. Im Fenster **Starten** drücken (mit leerem Eingang wird nur `Prüfen` abgearbeitet). Die Spalte Prüfen zeigt
   vorher schon „bereit zur Übernahme“, sobald die Angaben vollständig sind.

Vollständige Dateien wandern dann nach `Fertig` und werden umbenannt. Bei Scans ohne Text (`kaum Text`) muss
zusätzlich die Zeile `pruefen:` gelöscht werden, damit die Datei übernommen wird.

## Textqualität (für die Weiterverarbeitung in einer KI)

PDFs werden standardmäßig mit **PDFium** gelesen (der PDF-Engine von Chrome), alle anderen Formate mit MarkItDown.
Gründe, gemessen an 59 echten Fachbüchern:

- MarkItDowns PDF-Weg klebte bei etwa der Hälfte der Bücher Wörter zusammen (`Wiefindeichheraus`) und machte aus
  Formeln und sogar Fließtext Tabellen-Müll (jede fünfte Zeile begann mit `|`). PDFium liefert sauberen Text.
- PDFium erkennt mathematische Symbole (`ω`, `∞`, `π`) und ist etwa 25-mal schneller: Ein Buch mit 2000 Seiten und 147 MB
  braucht rund 5 Sekunden statt Minuten.

Der Text wird zusätzlich bereinigt:

| Schritt | Beispiel |
|---|---|
| Silbentrennung am Zeilenende zusammenführen | `Kon-` / `struktion` wird `Konstruktion`; `Ein-` / `und Ausgabe` bleibt `Ein- und Ausgabe`; `Maschinenbau-` / `Techniker` bleibt `Maschinenbau-Techniker` |
| Umbrochene Zeilen zu Absätzen verbinden | Fließtext wird zusammenhängend, Listen, Formeln und Inhaltsverzeichnis bleiben zeilenweise |
| Kopf-/Fußzeilen und Seitenzahlen entfernen | laufende Kapiteltitel, `34`, `iv`, auch wechselnde wie `12.3 Getriebe 197` |
| Punkte im Inhaltsverzeichnis kürzen | `Einleitung ........ 12` wird `Einleitung … 12` |
| Ligaturen auflösen | `ﬁ`, `ﬂ` werden `fi`, `fl` |
| Seitenmarker mit **gedruckter** Seitenzahl | `<!-- Seite 197 (PDF 206) -->` vor jeder Seite, siehe [Seitenzahlen und Zitieren](#seitenzahlen-und-zitieren) |
| Wörter und Sätze über den Seitenwechsel verbinden | `Reg-` / `ler` wird `Regler`; ein Satz behält den Marker mitten im Satz |
| Indizes, Exponenten, Brüche als LaTeX | `p1` wird `p$_{1}$`, `V / T0` wird `$\frac{V}{T_{0}}$`, siehe [Formelsatz](#formelsatz-latex) |
| Tabellen mit Gitterlinien als Markdown-Tabelle | siehe [Tabellen](#tabellen) |
| Fett und kursiv als Markdown | `**Kennwert**`, `*Zugfestigkeit*`; kursive Formelzeichen wie `F` bleiben ohne Sternchen, siehe [Ohne Lesezeichen, fett und kursiv](#überschriften-ohne-lesezeichen-fett-und-kursiv) |
| Zeichenfehler der PDF-Schriften beheben | `fü r` wird `für`, `f¸r` wird `für`, Symbol-Schrift `U+F061` wird `α` (siehe [Zeichenkorrektur](#zeichenkorrektur)) |
| Lizenz-Wasserzeichen gekaufter Normen entfernen | `Datum / Uhrzeit des Ausdrucks: … Firmenname: … Benutzername: …` |
| Leerseiten-Vermerke entfernen | `— Leerseite —`, `This page is intentionally blank.` |
| Tabulatoren zwischen Wörtern, zerlegte Umlaute (`u` + `¨`) vereinheitlichen | damit eine Suche nach „für“ jede Stelle findet |

**Was nicht geht (Grenzen):**

- **Tabellen ohne Gitterlinien** (nur durch Leerraum ausgerichtet) bleiben Textzeilen. Bei DOCX, XLSX und HTML bleiben
  Tabellen immer erhalten.
- **Formelzeichen** werden weitgehend repariert (siehe unten), aber nicht vollständig. Unsichere Zeichen bleiben
  als `�` stehen. Die **Struktur** von Formeln wird teilweise zurückgewonnen (Indizes, Exponenten, Brüche, Wurzeln,
  Summen- und Integralgrenzen, siehe [Formelsatz](#formelsatz-latex)); Matrizen, große Klammern und mehrzeilige
  Formeln bleiben Text. Formeln mit unlesbarem Zeichen sind mit `⚠[Formel unsicher]` markiert.
- **Defekte Schriftkodierung (Umlaute):** Manche PDFs haben Umlaute, die nirgends zugeordnet sind (`fr` statt `für`).
  Sie werden zum großen Teil zurückgewonnen (siehe unten), was nicht sicher erkannt wird, bleibt als `f�r` markiert.
  Wenn viele Wörter betroffen bleiben, steht eine `warnung:` im Kopfblock, in der Meldung und im Protokoll.
- Bei PDFs, die zwei Buchseiten auf eine PDF-Seite legen, kann eine Kopfzeile mitten im Text stehen bleiben.

Zurück zum MarkItDown-Weg für PDFs: Einstellungen → PDF-Engine (`PDF_ENGINE`).
Dort ist der Abstands-Fehler von `pdfplumber` behoben und die `(cid:N)`-Platzhalter sind entfernt, die Tabellen bleiben.

### Überschriften aus den PDF-Lesezeichen

Die meisten Fachbücher haben Lesezeichen (die Gliederung im PDF-Leser). Das Tool macht daraus Markdown-Überschriften:
Ebene 0 wird `#`, Ebene 1 `##` und so weiter (höchstens sechs). Das hilft einer KI, ein Buch nach Kapiteln zu gliedern
und zu zerlegen. Steht der Titel auf der Zielseite als eigene Zeile, wird genau diese Zeile zur Überschrift (so bleibt
die Reihenfolge im Text richtig, auch bei Titeln, die über zwei oder drei Zeilen umbrochen sind). Sonst steht die
Überschrift am Seitenanfang. Im Test an 58 Büchern hatten 56 Lesezeichen (30 bis 1700 Einträge), im Schnitt wurden
etwa 90 % der Titel direkt im Text gefunden. Hat ein PDF keine Lesezeichen, kommen die Überschriften aus der
Schriftgröße (nächster Abschnitt).

Seiten ohne Text bekommen keine Überschrift, damit ein gescanntes Buch mit Lesezeichen nicht wie ein Textbuch aussieht.
Abschalten im Fenster unter Einstellungen (`UEBERSCHRIFTEN_AUS_LESEZEICHEN`).
Im Kopfblock steht unter `lesezeichen:`, wie viele Überschriften eingefügt wurden.

Zeigt ein Lesezeichen eine Seite zu früh (kommt vor, gemessen am Inhaltsverzeichnis) und steht der Titel erst auf der
nächsten Seite, kommt die Überschrift dorthin, damit auch die Seitenangabe des Abschnitts stimmt.

### Überschriften ohne Lesezeichen, fett und kursiv

Das Tool liest je Zeile Schriftgröße und Schriftschnitt (Code in `schriftbild.py`).

- **Überschriften aus der Schriftgröße**, nur wenn ein PDF keine Lesezeichen hat: Zeilen, die deutlich größer als der
  Fließtext sind, und nummerierte Abschnittstitel (`3.5 …`, auch nur etwas größer oder fett in Textgröße). Die Ebene
  folgt der Nummer (`3.1.1` wird `###`), ohne Nummer der Schriftgröße. Keine Überschrift werden Kolumnentitel, Bild-
  und Tabellenunterschriften, Zeilen des Inhaltsverzeichnisses, Sätze, Formeln und Diagrammbeschriftungen.
  Gemessen an 57 Büchern und 56 Normen, deren Lesezeichen dafür als Vergleich dienten: gefunden wurden 73 % der
  Lesezeichen-Titel der Bücher (Normen 82 %), und 62 % der erkannten Überschriften stehen auch in den Lesezeichen
  (Normen 72 %; die übrigen sind oft echte Unterabschnitte, die kein Lesezeichen haben). Lesezeichen bleiben deshalb
  die erste Wahl. Im Kopfblock steht dann `ueberschriften:` statt `lesezeichen:`.
- **Fett und kursiv** werden `**fett**`, `*kursiv*` bzw. `***beides***`. Kursive Formelzeichen zählen nicht
  (Formelschriften und einzelne kurze Wörter). Ist fast der ganze Text eines PDFs als fett gekennzeichnet, gilt das
  als Grundschrift. Eingesetzt wird nur, wo die Stelle auf ihrer Seite eindeutig wiederzufinden ist; Überschriften,
  Tabellen und Formeln bleiben unberührt. Im Kopfblock: `hervorhebungen:`.
- Kosten: etwa 13 % mehr Laufzeit. Abschalten im Fenster unter Einstellungen („Überschriften aus der Schriftgröße“,
  „Fett und kursiv übernehmen“).

### Seitenzahlen und Zitieren

Die Position einer Seite in der PDF-Datei ist fast nie die gedruckte Seite: Bücher haben einen Vorspann mit römischen
Zahlen (gemessen: in allen 54 Büchern mit Seitenbezeichnung, meist 4 bis 24 Seiten Versatz), Normen ein nationales
Deckblatt und Vorwort (2 bis 6 Seiten). Zitiert wird aber die gedruckte Seite. Deshalb nennt jeder Seitenmarker beides:

```
<!-- Seite 197 (PDF 206) -->      gedruckte Seite 197, in der PDF-Datei die 206. Seite
<!-- Seite xii (PDF 12) -->       Vorspann mit römischer Zählung
<!-- PDF-Seite 3 -->              keine gedruckte Seitenzahl bekannt: nicht als „S. 3“ zitieren
```

Die gedruckte Zahl kommt aus der **Seitenbezeichnung der PDF** (Verlage hinterlegen sie dort, auch römisch), sonst aus
der **Zahlenfolge in Kopf- oder Fußzeile** (Normen: eine Folge über mehrere Seiten, eine einzelne Zahl zählt nie; Seiten
ohne eigene Zahl innerhalb der Folge, z. B. Kapitelanfänge, bekommen die Zahl aus der Folge). Bei DIN-EN-Normen beginnt
die Zählung auf dem EN-Deckblatt neu, das Tool folgt dem. Wo nichts Sicheres zu finden ist, steht nur die PDF-Seite.
Code in `seitenzahlen.py`.

**Geprüft:** unabhängig über das Inhaltsverzeichnis (Kapitel-Seitenzahl dort gegen die zugeordnete Zahl der Seite, auf
die das Lesezeichen zeigt), an 55 Büchern und 56 Normen: 8.954 Einträge gleich, 25 abweichend, und die 25 lagen alle an
Lesezeichen, die eine Seite zu früh zeigen (behoben, siehe oben). 33.184 von 33.225 Seiten haben eine gedruckte Zahl.
Zusätzlich wurden zufällige Sätze aus jeder `.md` im PDF auf der angegebenen Seite gesucht
(`werkzeuge/zitierpruefung.py`, 3.000 Sätze aus 55 Büchern und 56 Normen): **kein einziger auf einer falschen Seite**;
98 % direkt gefunden, der Rest scheitert nur am Textvergleich (z. B. Überschrift aus dem Lesezeichen im Satz).

**Seitenwechsel:** Ein am Seitenende getrenntes Wort wird verbunden (`Reg-` / `ler` wird `Regler`, rund 1.200 Fälle in
den Büchern), es zählt zur Seite, auf der es beginnt. Läuft ein Satz über die Seite, steht der Marker mitten im Satz:
`… wird der <!-- Seite 12 (PDF 14) --> Wert …`. So bleibt der Absatz für eine KI zusammen, und die Seite stimmt trotzdem.

Im Kopfblock jeder PDF-`.md` steht unter `seitenzahlen:`, woher die Zahlen kommen, und unter `zitierhinweis:` eine
kurze Erklärung der Marker für die KI. Abschalten: `GEDRUCKTE_SEITENZAHLEN = False` (dann nur `<!-- PDF-Seite N -->`).

**Lebende Kolumnentitel** (Kopfzeilen, die mit dem Abschnitt wechseln: `1.3 Grundbegriffe 13`,
`584 10 Schwingungen`) fallen ebenfalls weg: Mit bekannter Seitenzahl sind sie sicher zu erkennen
(kurze Randzeile, die mit genau dieser Zahl beginnt oder endet; nur wenn das Buch das auf mindestens 30 % der Seiten tut).

### Lesereihenfolge zweispaltiger Seiten

PDFium liefert den Text in der Reihenfolge, in der das PDF ihn zeichnet. Bei manchen Verlagen (z. B. InDesign-Vorlagen)
steht dort die rechte Spalte vor der linken und eine Tabelle am Seitenende. Das Tool erkennt das: Es zerlegt die Seite
in Zeilenstücke, sucht die Spaltenlücke und stellt die Seite nur dann um, wenn im Text nachweislich eine rechte
Textzeile **vor** einer linken steht. Dann gilt: Kopf und breite Zeilen, linke Spalte, rechte Spalte, breite Zeile,
und so weiter. Es wird nur umsortiert, nie etwas hinzugefügt oder weggelassen (im Test an ganzen Büchern blieb der
Zeichenbestand des Rohtexts auf allen umsortierten Seiten identisch). Zusätzlich prüft das Tool am Text: Würde die neue
Reihenfolge mehr Satzbrüche erzeugen (Satzende, dann klein weiter), bleibt es bei der alten.

Gemessen an den 58 Büchern: Nur wenige Bücher sind betroffen, diese dafür stark. Im stärksten Fall sind 444 Seiten
umgestellt worden, in anderen Büchern 120 bzw. 84 von 1452, in einem weiteren keine (dort bleibt der Text Zeichen für
Zeichen gleich). Das kostet etwa 5 bis 15 ms je Seite.

Grenzen: Nur zwei Spalten (drei oder mehr, Tabellen und einspaltige Seiten bleiben, wie sie sind). Seiten mit Bildern,
Kästen und Formeln zwischen den Spalten sind schwieriger; wo unsicher, bleibt die PDF-Reihenfolge. Die Kopf-/Fußzeilen-
Entfernung erkennt eine laufende Kopfzeile auch dann noch, wenn ihr auf einer umgestellten Seite eine kurze Randnotiz
vorausgeht (sie prüft die ersten/letzten drei Zeilen, nicht nur die äußerste). An jeder Spalten-/Bandgrenze wird ein
Absatzbruch erzwungen, damit die Textzeile vor der Grenze nie mit der danach zu einem (inhaltlich falschen) Absatz
verschmilzt (geprüft an über 3000 Grenzen in 58 Büchern: nur 2 Ausnahmen, beides zusammengehörige Formelzeilen).

Abschalten im Fenster unter Einstellungen (`SPALTENREIHENFOLGE`). Im Kopfblock steht
unter `spalten:`, wie viele Seiten umgestellt wurden; `textquelle` endet auf „+ Spaltenreihenfolge“, damit
„Text erneuern“ ältere Bücher erkennt.

### Normen (DIN, EN, ISO …)

Bei Normen sind die PDF-Metadaten fast immer unbrauchbar (Titel „CEN/TC 121“ mit Autor „klar irene“, Titel
„Datum:2009 April“), und das Jahr im Text führt in die Irre: das Download-Wasserzeichen nennt das Druckdatum, die
Titelseite die ersetzte Ausgabe. Das Tool erkennt Normen deshalb selbst (Code in `normen.py`):

- **Nummer und Ausgabe** aus der Kopfzeile der Seiten (`DIN EN ISO 12345:2023-07`), sonst aus der „Ref. Nr.“ der
  Titelseite, dem ersten Lesezeichen (auch nur mit Nummer, dann mit dem Datum vom Deckblatt, z. B. „Berichtigung 1“,
  „August 2013“) oder dem Dateinamen des DIN-Media-/Beuth-Downloads (`DIN EN ISO 12345_2023-07-00_DE_1234567.pdf`), zuletzt
  aus einem frei vergebenen Dateinamen (`DIN_EN_ISO_12345_2011-09.pdf`). Entwürfe bekommen ein „E “ davor (`E DIN 9876`).
  Vorrang hat immer, was in der Norm selbst steht: zwei der neuen Dateien waren anders benannt als ihr Inhalt
  (eine Datei mit „2009-07“ im Namen ist die Ausgabe 2002-09).
- **Titel** von der Titelseite: der deutsche Titel steht dort in derselben Schrift wie die Nummer, die englische und
  französische Übersetzung darunter kleiner. Fehlt er dort als Text, kommt er aus einem Berichtigungsvermerk davor.
- **Autor** ist der Herausgeber (`DIN`), **Jahr** das Jahr der Ausgabe.
- **Quellenangabe** im Kopfblock (IEEE): `*Klebtechnik – … – Einstufung von Fehlstellen*, DIN EN ISO
  12345:2023-07, 2023.` Normen zitiert man meist nach Abschnitt oder Tabelle; beides steht als Überschrift im Text.
- Lizenzvermerke werden entfernt, auch Kunden-/Abonummern (`Kd.-Nr.`, `Abo-Nr.`, „Normen-Ticker“) und die
  Lizenzkennung als Hex-Zeile; ebenso der Strichcode der Dokumentnummer auf dem Deckblatt.

Der Dateiname lautet dann zum Beispiel `DIN EN ISO 12345 – Klebtechnik – Einstufung von Fehlstellen - DIN - 2023` (Nummer und Titel erfunden).
Ist der Name zu lang, bleiben Nummer und letzter Titelteil (der genaueste, oft „Teil 3: …“) stehen, die mittleren Teile
fallen weg. Im Kopfblock steht zusätzlich `norm: "DIN EN ISO 12345:2023-07"`. Getestet an 56 Normen (1991 bis 2026):
alle mit richtiger Nummer, Ausgabe und Titel erkannt. Abschalten: `NORMEN_ERKENNEN = False` in `pdf2md.py`.
Doppelte und ältere Ausgaben liegen im Normen-Ordner unter `Duplikate\` (mit `LIESMICH.txt`, warum).

### Tabellen

Tabellen, deren Zellen durch **gezeichnete Linien** getrennt sind (in Normen fast alle, in Fachbüchern viele), werden
als Markdown-Tabelle an ihrer Stelle in den Text gesetzt (Code in `tabellen.py`):

```
| Nennmaß mm |  | G |  |  |
|---|---|---|---|---|
| über | bis einschl. | 5 | 6 | 7 |
| 3 | 6 | +9 +4 | +12 +4 | +16 +4 |
```

Verbundene Zellen stehen in ihrer ersten Zelle, die übrigen bleiben leer (Markdown kennt keine verbundenen Zellen).
Seitlich offene Tabellen (Randspalten ohne senkrechte Randlinie) und senkrecht gesetzte Spaltenköpfe werden erkannt.
Stehen in einer Zelle zwei Werte übereinander (oberes und unteres Abmaß), stehen sie nebeneinander. Damit aus Zeichnungen
und Diagrammen mit Gitternetz keine Tabellen werden, gilt ein Gitter nur dann als Tabelle, wenn mindestens drei Zellen
in zwei Zeilen und zwei Spalten Text enthalten und keine Linie mitten durch ein Wort läuft. Gemessen: 1.058 Tabellen in
56 Normen, 2.579 in 55 Büchern (davon 133 nur mit waagerechten Linien, siehe unten).

**Tabellen nur mit waagerechten Linien** (eine Linie oben, eine unter dem Kopf, eine unten; so setzen Springer und viele
TeX-Bücher): Die Spalten ergeben sich aus dem Leerraum, der in allen Zeilen frei bleibt. Umbrochene Zelltexte
(Fortsetzungszeile mit leerer erster Spalte) gehören zur Zeile davor, ein Spaltenkopf über mehrere Spalten verbindet die
Kopfzellen, zwei Tabellen untereinander werden an ihrer Überschrift („Tab. 1.6 …“) getrennt. Weil hier keine Linien die
Spalten vorgeben, sind die Regeln strenger (dicht gefüllt, kurze Zellen); Fließtext zwischen Linien bleibt Text.
Tabellen ganz ohne Linien bleiben weiterhin Text.
Abschalten im Fenster unter Einstellungen (`TABELLEN_ERKENNEN`).

### Zeichenkorrektur

Manche Fehler liegen in den Schriften der PDF und sind im fertigen Text nicht mehr sicher zu erkennen. Das Tool liest
dafür betroffene Seiten Zeichen für Zeichen (Code in `zeichen.py`):

| Fehler | Beispiel | Wo gefunden |
|---|---|---|
| Umlaut als „u“ + Trema, PDFium setzt ein Leerzeichen dahinter | `fü r`, `Prü fung` → `für`, `Prüfung` | DIN-Normen ab 2024 (500 bis 1000 Mal je Norm) |
| falsches Zeichen für Großbuchstaben-Akzente | `Aǆ nderungen` → `Änderungen` | DIN-Normen ab 2024 |
| Symbol-/Wingdings-Schrift im privaten Unicodebereich | `U+F061` → `α`, `U+F0B7` → `•`, Wingdings `U+F06F` → `□` | Word-PDFs, Normen, einige Bücher |
| Text in Mac-Roman statt Windows-1252 gelesen | `f¸r Europ‰ische St‰hle` → `für Europäische Stähle` | DIN-Normen um 2004/2005 |
| Text doppelt an derselben Stelle gedruckt (erschien zweimal im Markdown) | ganze Tabellen und Absätze doppelt | drei Bücher (Tabellen, Formeln) |

Die Mac-Roman-Korrektur greift nur je Schrift und nur, wenn die Schrift mehrere solche Wörter und kein einziges intaktes
„ä/ö/ü“ enthält; Formelschriften (TeX, MathTime) sind ausgenommen, dort ist `ˆ` ein echter Akzent. Das Leerzeichen nach
einem Umlaut fällt nur weg, wenn PDFium es selbst erzeugt hat und ein Kleinbuchstabe folgt („Q̇ Wärmestrom“ bleibt).
Im Kopfblock steht unter `zeichenkorrektur:`, was korrigiert wurde.

### Formelzeichen reparieren

Viele Fachbücher (TeX, Springer-MathTime) haben Formelschriften ohne brauchbare Zeichenzuordnung. Ohne Reparatur steht
dort `FGK D 150 N` für `F_GK = 150 N`, `x3 D l=2` für `x3 = l/2` oder `52:400` für `52.400`. Das Tool repariert das
zeichenweise, je Schrift und Zeichen (nicht je Vorkommen), in zwei Stufen (Code in `formeln.py`):

| Weg | Wie | Wann |
|---|---|---|
| **A: Glyphnamen** | liest den Namen des Zeichens aus dem eingebetteten Schriftprogramm (`beta` wird `β`) | LaTeX/Computer-Modern-Schriften, exakt |
| **B: Formvergleich** | rendert das Zeichen und vergleicht es mit Referenzzeichen aus freien Schriften (STIX, DejaVu). Mehrere Vorkommen stimmen ab. | Schriften mit kaputten Namen, z. B. MathTime |

B ersetzt nur, wenn das gefundene Zeichen **deutlich** besser passt (Mindestpunktzahl und Abstand zum zweitbesten).
Ein nachweislich falsches Zeichen, das nicht sicher ersetzt werden kann, wird zu `�`, statt falsch stehen zu bleiben.
Außerdem ergänzt das Tool `f�r` zu `für`, wenn dasselbe Wort an anderer Stelle des Buchs intakt vorkommt
(kein Wörterbuch nötig, das Buch liefert sein eigenes).

**Gemessene Qualität** (an deinen eigenen Büchern, mit der Zeichentabelle aus den gezeichneten Glyphen als Prüfstein):

- MathTime-Zeichen: 37 von 43 bekannten Zeichen richtig, 0 falsch, 6 bleiben offen (z. B. `±`, das dem `⊥` zu ähnlich sieht).
- Große Operatoren und Wurzeln (unabhängig gegen Weg A geprüft): 271 angenommene Entscheidungen, 0 falsch.
- Umlaute in einem Buch mit defekter Kodierung: von etwa 7 % auf 90 % der geprüften Wörter korrekt.
- Über alle 58 getesteten Bücher: `�` von 126.500 auf 60.300 (−52 %), dazu rund 442.000 korrigierte Zeichen
  (meist Stellen, die vorher falsch statt erkennbar unlesbar waren, z. B. `D` für `=`). Kein Buch ist abgestürzt.

Nicht gelöst: rund 60.000 `�` bleiben, vor allem in Büchern mit vielen seltenen Formelzeichen (z. B. große
Nachschlagewerke) und bei den weiterhin unsicheren Umlauten des Buchs mit defekter Kodierung.

Die Reparatur kostet Zeit: im Schnitt etwa 11 Sekunden pro Buch, bei sehr großen Büchern (1500 bis 2000 Seiten) bis zu
einer Minute zusätzlich.
Abschalten im Fenster unter Einstellungen (`FORMELN_REPARIEREN`).
Im Kopfblock steht unter `formelreparatur:`, was passiert ist.

### Formelsatz (LaTeX)

PDFium liefert Formeln als flachen Text: `p1 V1 = p2 V2`, `10−3` (liest sich wie „10 minus 3“), ein Bruch zerfällt in
Zeilen (`V` / `T0 + t = V0` / `T0`). Das Tool setzt die Struktur aus der Lage der Zeichen wieder zusammen (keine
Bilderkennung, Code in `formelsatz.py`):

| Was | Erkennung | Ergebnis |
|---|---|---|
| Index, Exponent, Fußnotenzeichen | kleineres Zeichen über/unter der Grundlinie des Nachbarzeichens | `p$_{1}$`, `10$^{−3}$`, `Probenrichtung$^{a}$`, `$\dot{S}_{irr,12}^{R}$` |
| Bruch | kurzer Strich, darüber und darunter je eine dichte Zeile, die nicht über den Strich hinausragt | `$\frac{V}{T_{0} + t} = \frac{V_{0}}{T_{0}}$` |
| Wurzel | `√` mit Strich über dem Radikanden | `$d = \sqrt{\frac{4A}{π}}$` |
| Summe, Produkt, Integral, lim | großes Zeichen mit kleinen Grenzen darüber/darunter (Integral: rechts) | `$\int_{1}^{2}\frac{dq}{T}$`, `$\lim_{∆t→0}$` |
| Akzent über Formelzeichen | frei stehender Punkt/Strich über dem Buchstaben | `Q̇`, in Formeln `\dot{Q}` |

Eine Zeile mit Bruch, Wurzel oder Operator wird ganz neu gesetzt: Wörter bleiben Text, alles dazwischen kommt als
Formel in `$…$`, abgesetzte Formeln stehen als eigener Absatz. Tabellenlinien gelten nie als Bruchstrich (sie enden an
senkrechten Linien, sind zu lang für ihren Text oder stehen zu mehreren gleich lang übereinander).
**Unsichere Formeln** (ein unlesbares Zeichen `�` in der Formel oder ein Zähler/Nenner über mehrere Zeilen) bekommen
davor die Markierung `⚠[Formel unsicher]`, damit sie beim Lesen und Zitieren auffallen: im PDF nachsehen.
Die Formelreparatur (siehe oben) und der Formelsatz arbeiten zusammen: die reparierten Zeichen stehen auch in den neu
gesetzten Formeln.

Gemessen an 55 Büchern: 309.000 Hoch-/Tiefstellungen, 72.700 Formelteile (Brüche, Wurzeln, Operatoren), 5.457 Zeilen
als unsicher markiert; in 56 Normen 6.559 Hoch-/Tiefstellungen, 140 Formelteile, 7 unsichere Zeilen. Geprüft wurden
Stichproben von Hand; Tabellenkopf über Linie, Dampftafeln und Unterstreichungen ergeben keine Brüche mehr.
Kosten: etwa 20 ms je Seite mit Formeln (Seiten mit nur einer Schriftgröße und ohne Striche werden übersprungen).
Abschalten im Fenster unter Einstellungen (`FORMELSATZ`). Im Kopfblock steht unter
`formelsatz:`, was gesetzt wurde.

### Text bereits verarbeiteter Bücher erneuern

Werkzeuge → **Text erneuern …**: wandelt den Text der PDFs in `Fertig` mit dem aktuellen Verfahren neu um. **Namen,
Ordner und Kopfblock bleiben** (auch von Hand ergänzte Angaben). Die alten `.md`-Dateien werden vorher in den Ordner
`Sicherung` kopiert. Die Vorschau listet alle betroffenen Bücher; erst „Neu umwandeln“ startet. Fortschritt und
Abbrechen wie bei „Starten“. Dateien, die schon mit dem aktuellen Verfahren erzeugt wurden, erscheinen nicht. Das Zurückdrehen geht von Hand: die Datei aus `Sicherung` zurückkopieren.
Fehlt im Kopfblock die Quellenangabe (ältere `.md`), wird sie dabei ergänzt; von Hand eingetragene Angaben bleiben.

## Namen in `Fertig` reparieren

Werkzeuge → **Namen reparieren …**: bildet die Namen in `Fertig` neu aus `titel`, `autor` und `jahr` im Kopfblock der
`.md` und benennt Dateien um, deren Name nicht passt. Das hilft zum Beispiel bei Namen, die eine ältere Version auf 120
Zeichen abgeschnitten hat (Autor und Jahr fehlten dann). Die **Vorschau** zeigt je Datei alt → neu; erst „Umbenennen“
führt sie aus.

Achtung: Auch von Hand umbenannte Dateien in `Fertig` gelten als abweichend und werden in der Vorschau aufgelistet.
Wenn du einen Namen behalten willst, brich ab und ändere stattdessen `titel`/`autor`/`jahr` im Kopfblock. Das
Umbenennen lässt sich mit „Letzten Lauf rückgängig machen“ zurückdrehen.

## Rückgängig machen

Werkzeuge → **Letzten Lauf rückgängig machen …**: dreht den **letzten** Lauf zurück (Umwandlung, Übernahme aus Prüfen
oder Umbenennen), mehrfach hintereinander möglich. Die Vorschau nennt jede Datei und ihren alten Ort. Die Originale gehen an ihren
alten Ort mit dem alten Namen zurück. Die `.md` wird daneben abgelegt, es wird nichts gelöscht.

## Woher die Metadaten kommen

1. **Titel, Autor:** Datei-Metadaten (PDF-Info, Dokument-Eigenschaften bei Office, Dublin-Core bei EPUB, `<title>`
   bei HTML). Platzhalter wie "Microsoft Word - Dokument1", Autor "admin" oder ein Titel, der nur eine ISBN/DOI
   ist (Springer-PDFs), werden verworfen.
2. **Jahr:**
   - EPUB: das Datum aus den Metadaten (bei EPUB ist es das Erscheinungsdatum).
   - Sonst: Copyright-/Erscheinungsvermerk im Textanfang (hinter "©", sonst bei "Auflage"/"Erstausgabe").
     Bei mehreren Jahren gilt das jüngste.
   - Das Erstellungsdatum einer Datei wird absichtlich nicht genutzt, weil es meist nicht das Erscheinungsjahr ist
     (Schalter `JAHR_AUS_ERSTELLDATUM`).
3. **Was dann noch fehlt:** Abgleich bei [Crossref](https://www.crossref.org/) über DOI/ISBN aus dem Textanfang.
   Es wird nur die ISBN/DOI gesendet. Abschalten: Einstellungen → Online-Abgleich.

Bei drei oder mehr Autoren steht im Dateinamen nur der erste ("Muster et al."), im Kopfblock alle.
Im Kopfblock der `.md` steht zu jedem Wert die Quelle (`titel_quelle`, `autor_quelle`, `jahr_quelle`).

### Quellenangabe (IEEE, APA 7, DIN ISO 690, BibTeX)

Für das Literaturverzeichnis schlägt das Tool über die DOI bei Crossref und über die ISBN bei der Deutschen
Nationalbibliothek nach und schreibt in den Kopfblock (Code in `zitierdaten.py`):

```
quellenangabe: "H. D. Muster und S. Beispiel, *Beispielkunde*, 16. Aufl. Berlin: Springer Vieweg, 2016, doi: 10.1007/…"
verlag: "Springer Vieweg"   ort: "Berlin"   auflage: "16., aktualisierte Auflage"   isbn: "..."   doi: "..."
```

IEEE in der deutschen Variante („Aufl.“, „Hrsg.“, „und“, „S.“), Titel kursiv als Markdown (`*…*`). Ab sieben Personen
steht nur die erste mit „et al.“. Verlag (wie im Buch, z. B. „Springer Vieweg“), Ort und Auflage kommen bevorzugt von
der DNB, Personen und DOI von Crossref. Im Text zitiert man mit Seite: `[1, S. 197]` (Seite aus dem Marker).

**Andere Zitierstile** (Einstellungen → Zitierstil); der Kopfblock nennt den Stil unter `zitierstil:`:

| Stil | Buch | Im Text |
|---|---|---|
| IEEE (Standard) | `H. D. Muster und S. Beispiel, *Beispielkunde*, 16. Aufl. Berlin: Springer Vieweg, 2016, doi: …` | `[1, S. 197]` |
| APA 7 | `Muster, H. D., & Beispiel, S. (2016). *Beispielkunde* (16. Aufl.). Springer Vieweg. https://doi.org/…` | `(Muster & Beispiel, 2016, S. 197)` |
| DIN ISO 690 | `MUSTER, Hans Dieter und Stefan BEISPIEL, 2016. *Beispielkunde*. 16. Aufl. Berlin: Springer Vieweg. ISBN …. DOI: …` | `(MUSTER und BEISPIEL 2016, S. 197)` |

Normen: IEEE `*Titel*, DIN EN ISO 12345:2023-07, 2023.`, APA `DIN. (2023). *Titel* (DIN EN ISO 12345:2023-07).`,
DIN ISO 690 `DIN EN ISO 12345:2023-07, 2023. *Titel*.` Nach einem Wechsel des Stils setzt Werkzeuge → „Text
erneuern“ die Angaben der vorhandenen PDFs im neuen Stil.

**BibTeX:** Zusätzlich steht ein BibTeX-Eintrag im Kopfblock (`bibtex:`, abschaltbar), zum Beispiel
`@book{muster2016beispielkunde, author = {Muster, Hans Dieter and Beispiel, Stefan}, title = {{Beispielkunde}}, …}`,
bei Normen `@standard{…}`. Werkzeuge → **Literaturliste exportieren** schreibt alle Bücher und Normen aus `Fertig` in
eine Datei `Literatur.bib` neben dem Programm (eine vorhandene wird ersetzt), zum Import in Citavi, Zotero oder
LaTeX; ältere `.md` ohne BibTeX-Feld werden dafür aus dem Kopfblock zusammengesetzt. Die Vorschau zeigt den
Zitierschlüssel jeder Datei, gleiche Schlüssel bekommen `b`, `c` … angehängt.

**Sammelwerke** (Handbücher, Atlanten): Jedes Kapitel hat eigene Autoren und wird einzeln zitiert. Steht die
Kapitel-DOI im Text (Springer druckt sie auf die erste Kapitelseite), kommt dort die Quellenangabe des Kapitels hin:
`<!-- Kapitelquelle (IEEE): A. Autor und B. Autor, „Kapiteltitel“, in *Handbuch*, 12. Aufl., C. Muster et al.,
Hrsg. Berlin: Springer Vieweg, 2019, S. 33–48, doi: … -->`.

**Datenschutz:** Gesendet wird ausschließlich die DOI bzw. ISBN in der Adresse, mit dem allgemeinen Kennzeichen
`pdf2md/1.0` (ohne Name, E-Mail oder Rechnerdaten), keine Titel, keine Dateinamen, kein Text. Ohne Netz entsteht die
Angabe aus Titel, Autor und Jahr (`zitierdaten_quelle: "nur Titel, Autor und Jahr …"`). Abschalten: Einstellungen →
Online-Abgleich (`ONLINE_ABGLEICH`).

**HTML:** Gelesen werden auch die Angaben für Literaturverwaltungen (`citation_title`, `citation_author`,
`citation_publication_date`, `citation_doi` wie bei Fachzeitschriften, Dublin Core `dc.title`/`dc.creator` wie bei
Project Gutenberg). Ohne Zeichensatz-Angabe gilt UTF-8, sonst Windows-1252. Platzhalter wie „Präsentation1“, „Mappe1“
oder ein Autor „python-docx“ werden verworfen.

**Hinweis für Office-Dateien:** Word, PowerPoint und Excel enthalten selten ein Erscheinungsjahr. Solche Dateien
landen daher oft in `Prüfen`, bis du das Jahr nachträgst.

## Geschwindigkeit

Das betrifft nur den MarkItDown-Weg (Einstellung PDF-Engine, oder wenn PDFium eine Datei nicht lesen kann): PDFs ab
150 Seiten werden dort in Pakete zu 40 Seiten geteilt und parallel umgewandelt, auf so vielen Kernen, wie die Maschine
hat (Test mit 1030 Seiten auf 8 Kernen: 50 s auf 13 s). Ohne diese Teilung liest MarkItDown jede Seite mehrfach.
Die Standard-Engine PDFium braucht keine Teilung, sie ist auch ohne Parallelisierung schnell genug.

## Auf einem anderen PC

**Nur benutzen:** den Download oben nehmen oder `pdf2md.exe` kopieren. Python wird dort nicht gebraucht. Das Fenster
nutzt die WebView2-Laufzeit von Microsoft Edge, die unter Windows 10/11 vorhanden ist; es läuft ohne Internet. Je
Ordner kann nur ein Fenster offen sein (ein zweiter Start wird mit Hinweis abgewiesen).

**Auch weiterentwickeln (zweiter PC mit eigenem Klon):**

1. Python 3.13 installieren und das Repository klonen (`git clone https://github.com/S4ltc/pdf2md.git`).
2. Im Projektordner `powershell -ExecutionPolicy Bypass -File build.ps1` ausführen. Das legt die Umgebung unter
   `%LOCALAPPDATA%\pdf2md-venv` an und baut `dist\pdf2md.exe`.
3. Für die Tests einmalig `%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.

Was **nicht** im Repository liegt (steht in `.gitignore`): `dist\` samt `pdf2md.exe`, `Eingang`, `Fertig`, `Prüfen`,
`Sicherung`, `Protokoll.csv` und `Einstellungen.json`. Die exe ist ein Build-Ergebnis (rund 94 MB, GitHub lehnt Dateien über 100 MB ab),
die Bücher gehören nicht ins Repository. Jeder PC hat deshalb seine eigenen Daten.

**Achtung bei gemeinsam genutzten Ordnern (z. B. OneDrive):** `Protokoll.csv` speichert absolute Pfade. Rückgängig
funktioniert nur, wenn die Ordner auf dem PC genauso heißen wie beim Lauf. Sonst Rückgängig nur an dem PC benutzen,
der den Lauf gemacht hat.

**Ablauf beim Wechsel:** am ersten PC committen und pushen, am zweiten PC in GitHub Desktop `Fetch`/`Pull`, nach der
Arbeit wieder pushen. Chats von Claude Code werden nicht zwischen PCs synchronisiert; das gemeinsame Gedächtnis ist
`CLAUDE.md` im Repository, Rechnerspezifisches (Pfade zu eigenen Testdaten) gehört in `CLAUDE.local.md` (nicht im Repo).

## Tests

Das Projekt hat eine automatische Testsuite (pytest, rund 505 Tests). Sie braucht keine echten Bücher: PDFs, DOCX und
EPUB werden von den Tests selbst erzeugt, alles läuft in einem temporären Ordner, nichts wird online abgefragt
(Crossref und DNB werden nachgebildet).

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

In dieser Umgebung heißt der Python-Aufruf `%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe -m pytest`.
Die Tests mit gerenderten Seiten (Formelreparatur) sind mit `langsam` markiert und lassen sich mit
`python -m pytest -m "not langsam"` überspringen.

Abgedeckt sind Namensbildung, Metadaten und Jahr-Erkennung (PDF, DOCX, EPUB, HTML), Textbereinigung, Kopfblock,
Lesezeichen, Formelreparatur (u. a. Schutzregeln), Zeichenkorrektur, Normen-Erkennung, Tabellen (auch: Zeichnungen
dürfen keine Tabellen werden) sowie der gesamte Ablauf mit Fertig/Prüfen, Nachbessern, Rückgängig, Namen reparieren,
Text erneuern und Protokoll, außerdem Einstellungen (Verzeichnis, Speichern, Anwenden auch in Unterprozessen),
Auswertung, Ablage-Listen und die Schnittstelle des Fensters (Lauf im Hintergrund, Abbrechen, Sperren, Werkzeug-Vorschau)
ohne echtes Fenster. Die Suite wurde mit absichtlich eingebauten Fehlern gegengeprüft
(10 von 10 wurden erkannt). Zu jedem behobenen Fehler gehört ein Regressionstest.

**Prüfung an echten Daten** (`werkzeuge/`, nur lesend, die Ausgaben enthalten Buch- und Normtext und gehören nie ins
Repository):

| Skript | Zweck |
|---|---|
| `normen_lauf.py <ausgabe>` | alle Normen umwandeln, ohne sie zu verschieben, mit `zusammenfassung.json` |
| `buecher_lauf.py <ausgabe>` | alle Bücher in `dist\Fertig` neu umwandeln (ohne Dateien über 150 MB) |
| `vergleich.py <alt> <neu>` | zwei Ausgabeordner zeilenweise vergleichen (alter Stand per `git archive` und `CODE_DIR`) |
| `seitenpruefung.py <pdf-ordner>` | gedruckte Seitenzahlen gegen das Inhaltsverzeichnis prüfen |
| `zitierpruefung.py <ausgabe> <pdf-ordner>` | zufällige Sätze der `.md` auf der angegebenen PDF-Seite suchen |
| `schwaechen.py <ausgabe>` | verbleibende Schwächen zählen (`�`, Zahlenzeilen ohne Tabelle, …) |
| `ui_vorschau.py <ablage> [port]` | die Oberfläche im Browser auf einer Ablage (Kopie, nie `dist`), für Screenshots und Tastaturtests |
| `einstellungen_liste.py` | schreibt `docs/einstellungen.md` (alle Einstellungen mit Bereich und Tooltip) |
| `haertetest.py <ziel>` | erzeugt Grenzfälle aller Formate und lässt sie wie im Fenster durchlaufen |
| `drittlizenzen.py <datei>` | schreibt die Lizenzen aller in der `.exe` enthaltenen Bestandteile |
| `exe_pruefen.py <exe> --benutzer [wort ...]` | sucht in einer gebauten `.exe` nach persönlichen Zeichenketten |

## Selbst bauen / weiterentwickeln

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Das Skript legt die virtuelle Umgebung unter `%LOCALAPPDATA%\pdf2md-venv` an (bewusst außerhalb von OneDrive)
und erzeugt `dist\pdf2md.exe` (Fenster-Anwendung, Einstieg `ui_app.py`, ohne Konsole). Läuft `pdf2md.exe` noch, bricht
es ab. Ohne Build: `python ui_app.py` (mit `PDF2MD_ABLAGE=<ordner>` auf eine andere Ablage, zum Beispiel eine Kopie).

### macOS und Linux (vorbereitet)

Fertige Downloads gibt es nur für Windows. Der Code ist für macOS und Linux vorbereitet: alles, was je System
anders ist, steht in `plattform.py` (Anzeige: WebKit auf dem Mac, QtWebEngine über PySide6 oder WebKitGTK unter
Linux; Dateien öffnen, ein Fenster je Ordner, helles/dunkles Thema, Ort der Ablage). Die Tests laufen bei jedem Push
auf Windows, macOS und Linux. Das Fenster selbst ist auf macOS und Linux noch nicht von Hand geprüft. Aus dem
Quellcode starten: Python 3.13, `pip install -r requirements.txt`, `python ui_app.py`. Die Ablage liegt dann neben dem
Skript, in einer gebauten App später im Dokumente-Ordner (`~/Documents/pdf2md`).

### Einstellungen

Jede einstellbare Konstante steht genau einmal in `einstellungen.py` (Modul, Name, Typ, Bereich, Standard, Gruppe,
Stufe, Tooltip), zusammen 89: 15 normale und 74 Experten-Werte (im Fenster eingeklappt, an 58 Büchern gemessen). Die
Liste mit allen Tooltips steht in [`docs/einstellungen.md`](docs/einstellungen.md). Gespeichert werden nur Abweichungen
in `Einstellungen.json`; sie gelten auch in den Unterprozessen der parallelen Umwandlung. Wurde eine Datei mit
abweichenden Werten erzeugt, steht das im Kopfblock (`einstellungen: "abweichend: …"`). Keine Einstellung sind
`USER_AGENT` (Datenschutz), `DIAGNOSE` (nur Tests) und die Regex-Muster.

### Veröffentlichen

- **Tests:** laufen bei jedem Push auf `main` automatisch auf GitHub (`.github/workflows/tests.yml`).
- **Release:** zuerst `VERSION` in `aktualisierung.py` erhöhen und committen, dann einen passenden Versions-Tag
  pushen, z. B. `git tag v1.1.0` und `git push origin v1.1.0` (passen Tag und `VERSION` nicht, bricht der Ablauf ab,
  sonst würde die Update-Suche falsch melden). Dann baut GitHub die
  `.exe`, lässt alle Tests in derselben Umgebung laufen, schreibt die Fremdlizenzen (`werkzeuge/drittlizenzen.py`)
  und legt das Release mit `pdf2md-v1.0.0-windows.zip` (exe, `LICENSE.txt`, `DRITTLIZENZEN.txt`, `LIESMICH.txt`)
  und `SHA256SUMS.txt` an.
- **Nichts Persönliches veröffentlichen:** Releases nur von GitHub bauen lassen, nicht die eigene `.exe` hochladen.
  Vor jedem Push prüfen: keine Pfade mit dem eigenen Benutzernamen, keine Kunden-/Abonummern aus Normen, kein
  Buch- oder Normtext und keine Titel der eigenen Bücher und Normen (Beispiele in Tests und Doku sind erfunden),
  Commits mit der GitHub-noreply-Adresse (Einstellungen → Emails). `werkzeuge/exe_pruefen.py`
  durchsucht eine gebaute `.exe` nach solchen Zeichenketten.

## Bekannte Grenzen

- Gescannte Bücher ohne Texterkennung liefern keinen Text und landen in `Prüfen`. OCR ist nicht eingebaut.
- Fehlen Metadaten und ISBN/DOI, wird nichts erraten. Der Titel muss dann von Hand nachgetragen werden.
- Zitate immer im PDF gegenprüfen (Strg+F mit einem Satz aus der `.md` findet die Stelle), besonders Zahlen aus
  Tabellen und Formeln. Seitenangaben nur aus Markern mit gedruckter Zahl (`<!-- Seite S (PDF N) -->`) übernehmen.
- Tabellen ohne Gitterlinien bleiben Text. Formeln mit Matrizen oder mehrzeiligen Klammern bleiben flach.
- Überschriften aus der Schriftgröße (PDFs ohne Lesezeichen) sind deutlich ungenauer als Lesezeichen. Fett und
  kursiv fehlen dort, wo eine Stelle nicht eindeutig wiederzufinden ist.
- Ältere Office-Formate (`.doc`, `.ppt`, `.xls`) sowie `.odt` und `.txt` werden nicht unterstützt und beim Hinzufügen abgelehnt.
- Passwortgeschützte PDFs (Öffnen-Passwort) und beschädigte Dateien bleiben mit verständlicher Meldung im Eingang; ein
  nur gegen Bearbeiten geschütztes PDF wird normal gelesen.
- Ist eine Datei in einem anderen Programm geöffnet und dadurch gesperrt, bleibt sie im Eingang bzw. in Prüfen; nach dem
  Schließen einfach erneut „Starten“.
- DOCX, PPTX, XLSX, EPUB und HTML haben keine Seiten: keine Seitenmarker, also nicht seitengenau zitierbar. Bei EPUB ist
  das Jahr das der E-Book-Ausgabe (Gutenberg-„Faust“: 2000). XLSX-Zahlen erscheinen teils als `400.0` (pandas).
- Stark fehlerhaftes HTML (etwa ein nicht geschlossenes `<title>`) kann Tags als Text liefern.
- Härtetest (`werkzeuge/haertetest.py`, Oktober 2026): 41 erzeugte Dateien aller Formate inklusive Grenzfällen ohne
  Absturz; 2000 PDF-Seiten in rund 11 s, 60.000 Tabellenzeilen in rund 20 s. 165 Einstellungsvarianten (Minimum,
  Maximum, Schalter) an zwei echten PDFs ohne Fehler.

## Lizenz

pdf2md steht unter der [MIT-Lizenz](LICENSE). Die `.exe` enthält Bibliotheken und Schriften Dritter (unter anderem
MarkItDown, PDFium/pypdfium2, pywebview, pypdf, NumPy, STIX- und DejaVu-Schriften), alle unter freizügigen Lizenzen;
ihre Lizenztexte liegen dem Download als `DRITTLIZENZEN.txt` bei (erzeugt mit `werkzeuge/drittlizenzen.py`).
