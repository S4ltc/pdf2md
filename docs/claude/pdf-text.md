# PDF-Text (`pdf2md.py`)

Aus CLAUDE.md ausgelagert. Vor einer Änderung an diesem Teil lesen; neue Messungen und Fallen hier eintragen (Zahlen mit Anzahl Bücher/Normen, Beispiele neutral, echte Titel nur in `CLAUDE.local.md`).

## PDF-Text

- Standard-Engine ist PDFium (`PDF_ENGINE="pdfium"`, über `pypdfium2`), NICHT MarkItDown. Grund (an 59 echten Büchern gemessen): MarkItDowns PDF-Weg klebt Wörter zusammen (pdfplumber-Standardabstand, sobald eine Seite "formularartig" aussieht) und macht aus Formeln/Fließtext Tabellen. Rückfall: Einstellung PDF-Engine = MarkItDown (mit gepatchtem pdfplumber, `x_tolerance_ratio=0.15`, und ohne `(cid:N)`).
- Bereinigung in `seiten_zu_text()`: Ligaturen, Silbentrennung (`_trennungen_verbinden`), Absätze (`_absaetze_bilden`, bewusst vorsichtig), Kopf-/Fußzeilen (`_kopf_fuss_entfernen`, ≥8 Seiten, ≥5 Zeichen, Strukturwörter wie "Aufgabe" ausgenommen), Seitenmarker (siehe `seitenzahlen-zitieren.md`). `nutztext()` entfernt die Marker (Scan-Erkennung, Jahr-Suche).
- Unlesbare Glyphen (Steuerzeichen 0x01-0x1F) werden zu `�`, weil das meist TeX-Formelsymbole sind; nicht stillschweigend löschen.
- Weiches Trennzeichen U+00AD mit folgendem (erzeugtem) Leerzeichen ist ein Zeilenende und wird wie `-\n` verbunden (`_trennungen_verbinden`); vorher löschte `STEUERZEICHEN` nur das U+00AD und es blieb „Bruch prüfung“.
- Tabulatoren werden zu Leerzeichen, der Text wird NFC-normalisiert (`_seite_bereinigen`).
- `kodierung_defekt()` erkennt PDFs mit fehlenden Umlauten (`fr`, `Lsung`) und setzt `warnung:` (blockiert Fertig nicht). `umlaute_ergaenzen()` macht `f�r` zu `für`, wenn dasselbe Wort im selben Buch intakt vorkommt (eindeutig, mind. 2-mal). Lesezeichen-Titel zählen doppelt (sie sind auch bei defekter Kodierung intakt); nötig, seit Überschriften doppelte Titelzeilen ersetzen und damit ein zweiter Beleg fehlte (Buch mit defekter Kodierung: „Zahnr�der“).
- Große PDFs (>=150 Seiten) werden beim MarkItDown-Weg in Paketen parallel umgewandelt, `MAX_PROZESSE = os.cpu_count() or 8` (keine feste Obergrenze mehr, war früher 8); `multiprocessing.freeze_support()` ist für die .exe Pflicht. PDFium braucht das nicht. Getestet in `tests/test_parallel.py` (war vorher ungetestet).
- Lesezeichen: `lesezeichen_lesen()` liest die PDF-Gliederung (PDFium `get_toc`), `_ueberschriften_einfuegen()` macht daraus `#`/`##`/... Steht der Titel als eigene Zeile im Seitentext, wird genau diese Zeile zur Überschrift, sonst kommt sie an den Seitenanfang. Seiten ohne Text bekommen nie eine Überschrift (sonst würde die Scan-Erkennung getäuscht). Im Kopfblock: `lesezeichen:`; `textquelle` endet auf "+ Lesezeichen", damit „Text erneuern“ ältere Bücher erkennt.

## Zweiter Durchgang in `_pdfium_seiten` (Zeichenkorrektur und Tabellen)

- Durchgang 1 liest jede Seite wie bisher (`get_text_range`/`lesefolge`), merkt sich verdächtige Seiten (`zeichen.verdaechtig`, `Korrektur.lernen` sammelt Hinweise je Schrift) und Gitter (`tabellen.gitter`). Durchgang 2 liest nur diese Seiten Zeichen für Zeichen neu (`zeichen.zeichen_lesen`, mit `lesefolge.seitentext(..., lesen=...)` bei umgestellten Seiten).
- Gemeinsames Format: `{Zeichenindex: Ersatz}` je Seite; `""` = Zeichen entfällt. Tabellen nutzen dasselbe: das erste Zeichen einer Tabelle wird zur ganzen Markdown-Tabelle (mit `SPALTENBRUCH`-Markern davor/danach = Leerzeilen), die übrigen Zeichen der Tabelle werden `""`.
- `formeln.Reparatur.reparieren(..., korrekturen=)` bekommt diese Dicts und setzt sie beim Neuaufbau einer Seite wieder ein, sonst gingen sie auf Formelseiten verloren.
- `zeichen_lesen` muss exakt `get_text_range` entsprechen (geprüft an 170 Buchseiten: 0 Abweichungen): Zeichen mit `FPDFText_GetTextIndexFromCharIndex == -1` auslassen (so verschwinden z.B. `\x03`), `\x02` wird `￾`.

## Kopf-/Fußzeilen (Ergänzungen)

- `KOPF_FUSS_MAX_LAENGE = 300` (vorher fest 100, wegen des langen Wasserzeichens). Dadurch trafen plötzlich Kapitel-Inhaltsverzeichnis-Zeilen mit Punktführern („Literatur . . . . 15“, >100 Zeichen); sie sind jetzt ausdrücklich ausgenommen (`PUNKTFUEHRER`).
- Gestapelte Kopfzeilen (Normen: „DIN EN ISO 12345:2023-07“, darunter „EN ISO 12345:2023 (D)“): weitere Runden nach dem Entfernen der erkannten Kante, aber nur Zeichen für Zeichen gleiche Zeilen und getrennt nach oben/unten (sonst verschwindet erster Fließtext jeder Seite, siehe Tests in `TestKopfFuss`).
- Kurze Dokumente: Schwelle `min(8, max(3, 60 % der Seiten))`.
