# Normen (`normen.py`)

Aus CLAUDE.md ausgelagert. Vor einer Änderung an diesem Teil lesen; neue Messungen und Fallen hier eintragen (Zahlen mit Anzahl Bücher/Normen, Beispiele neutral, echte Titel nur in `CLAUDE.local.md`).

## Normen (`normen.py`)

- Quellen in dieser Reihenfolge: Kopfzeile `NUMMER:JJJJ-MM` (≥2 Seiten und entweder ≥25 % der Seiten oder schon auf den ersten 4 Seiten; bei DIN-EN-Normen steht die DIN-Kopfzeile nur auf den nationalen Vorseiten), „Ref. Nr.“ der Titelseite, erstes Lesezeichen, Dateiname `NUMMER_JJJJ-MM-TT_DE_1234567.pdf`.
- Titel: Nummernzeile auf der Titelseite (≥11 pt), danach die Zeilen in derselben Schriftgröße (±0,6 pt; Größe = FontSize × Textmatrix) bis „Deutsche Fassung“/andere Größe. Alte Titelseiten (bis ~2004): Zeilen unter „DEUTSCHE NORM“ bis „Deutsche Fassung“/ICS. Teile ohne Strich werden mit „ – “ verbunden, außer die Zeile endet auf ein Füllwort („und“, „für“, …).
- `norm_uebernehmen()` überschreibt Metadaten-Titel/-Autor und Jahr immer (Norm-Metadaten sind Müll, Jahr aus © wäre Druckdatum oder ersetzte Ausgabe). `neuer_name()` kürzt Normtitel anders als Buchtitel (Nummer + letzter Teil bleiben, `NORMTITEL`).
- Wasserzeichen `LIZENZVERMERK` („Datum / Uhrzeit des Ausdrucks: … Printed copies are uncontrolled“) wird vor der Kopf-/Fußzeilen-Erkennung aus jeder Zeile entfernt, auch wenn es an Text klebt oder über bis zu drei Zeilen umbrochen ist; es enthält Firmen- und Benutzernamen. `LEERSEITE`-Zeilen („— Leerseite —“, „This page is intentionally blank.“) fallen ebenfalls weg.
- Nicht lösbar (Scan): einzelne Deckblatt-/Anhangseiten alter Normen sind Bilder mit unsichtbarer Texterkennungs-Ebene (Schrift z.B. `CALS_InvisibleTTFont`): gesperrter Text („Pr üf u n g“), Tabellenlinien nur als Pixel. Kein OCR/Scan-Support (Nutzerregel). Eine solche Norm liegt inzwischen als Textfassung vor (Scan in `Duplikate`).
- Weitere Lizenzvermerke (`LIZENZVERMERK`): Hex-Kennung als eigene Zeile, "Normen-Ticker"/"Normenabonnement" mit `Kd.-Nr.`/`Abo-Nr.` (persoenliche Daten, Test `test_kunden_und_abovermerke`). Strichcode vor der 7-stelligen Dokumentnummer: `_strichcode_entfernen`.
- Erkennung ohne Kopfzeile: Lesezeichen nur mit Nummer + Monat/Jahr vom Deckblatt; frei benannte Dateien (`DATEINAME_FREI`) nur als letzter Ausweg (2 von 20 neuen Dateinamen nannten eine falsche Ausgabe). Titel notfalls aus dem Berichtigungsvermerk (`_titel_nach_ausgabe`).
