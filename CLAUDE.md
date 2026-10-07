# pdf2md

Kleines Windows-Tool mit Fenster (pywebview): Bücher/Dokumente -> Markdown für die KI-Weiterverarbeitung. PDFs laufen über PDFium (eigene Textbereinigung + Formelreparatur), alle anderen Formate (DOCX, PPTX, XLSX, EPUB, HTML) über MarkItDown. Metadaten -> YAML-Kopfblock, Umbenennung nach `Titel - Autor - Jahr`.

## Befehle

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1        # baut dist\pdf2md.exe (~94 MB, Fenster-Anwendung)
%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe -m pytest   # Tests; -m "not langsam" überspringt die langsamen
%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe ui_app.py   # Fenster ohne Build; PDF2MD_ABLAGE=<ordner> = andere Ablage
%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe werkzeuge\ui_vorschau.py <ablage> 8765   # Oberfläche im Browser (Screenshots/Tastatur)
```

- Keine Kommandozeilen-Schalter mehr (Nutzerwunsch): Doppelklick öffnet das Fenster, alles wird dort bedient. Einstellungen stehen in `einstellungen.py`, Abweichungen in `Einstellungen.json` neben dem Programm.
- Pruefung an echten Daten: Skripte in `werkzeuge/` (README, Abschnitt Tests). Ausgaben enthalten Buch-/Normtext: nur in den Scratchpad, nie ins Repo.
- Die venv liegt unter `%LOCALAPPDATA%\pdf2md-venv`, nicht in OneDrive. Rechnerspezifisches (Pfade zu Testdaten) steht in `CLAUDE.local.md`, die nicht ins Repo gehört. Das Repo ist öffentlich: keine persönlichen Daten, Pfade mit Benutzernamen, Kunden-/Abonummern oder Buch-/Normtext einchecken (Prüfung siehe Abschnitt Veröffentlichung).
- Python 3.13 liegt unter `%LOCALAPPDATA%\Programs\Python\Python313\`; `py` funktioniert in neuen Terminals, `python` nicht.
- Git: `C:\Program Files\Git\cmd\git.exe` (der PATH in alten Shells ist veraltet).
- Eingaben nicht per PowerShell-Pipe in Python-Skripte füttern (BOM verfälscht die Antwort), sondern `subprocess` mit `input=` verwenden.

## Aufbau

- `pdf2md.py` (gesamter Ablauf), `formeln.py` (Formelreparatur), `lesefolge.py` (Lesereihenfolge zweispaltiger Seiten), `zeichen.py` (Zeichenkorrektur je Schrift), `normen.py` (Normen erkennen), `tabellen.py` (Gitter-Tabellen als Markdown), `formelsatz.py` (Indizes, Brueche, Wurzeln, Operatoren als LaTeX), `seitenzahlen.py` (gedruckte Seitenzahlen), `zitierdaten.py` (IEEE-Quellenangabe ueber Crossref/DNB), `einstellungen.py` (alle einstellbaren Werte), `auswertung.py` (Kennzahlen, reine Funktionen), `ablage.py` (Listen der Ordner, Kopieren nach Eingang), `ui_app.py` (Fenster, Api, Lauf-Thread; Einstieg der .exe), `ui/web/` (HTML/CSS/JS, offline, im Build per `--add-data`), `schriften/` (STIX/DejaVu, im Build per `--add-data`), `tests/`, `werkzeuge/`, `docs/` (Plan, `einstellungen.md`), `build.ps1`.
- Testmaterial: 56 Normen in einem lokalen Ordner (Pfad in `CLAUDE.local.md`, für `werkzeuge/normen_lauf.py` per Umgebungsvariable `NORMEN`; nur lesen, nie verschieben: `verarbeiten()` verschiebt das Original! Zum Testen `umwandeln()`/`metadaten_lesen()` direkt aufrufen bzw. `werkzeuge/normen_lauf.py`). Doppelte/aeltere Ausgaben liegen auf Wunsch des Nutzers in `Normen\Duplikate\` (LIESMICH.txt); Entwuerfe und gueltige Ausgabe bleiben beide im Hauptordner, Berichtigungen bei ihrer Norm.
- Ordner neben der `.exe` bzw. dem Skript: `Eingang` -> `Fertig` oder `Prüfen`, dazu `Sicherung/`, `Protokoll.csv` und `Einstellungen.json`. Stati im Protokoll: OK, PRÜFEN, NACHGEBESSERT, UMBENANNT, RÜCKGÄNGIG, TEXT_ERNEUERT.

## Verbindliche Regeln (vom Nutzer)

- KEIN OCR/Scan-Support und KEINE Claude-Vision-Variante für Formeln.
- `dist\` (Fertig, Prüfen, Sicherung, Protokoll.csv, Eingang) enthält Nutzerdaten: nie verändern, nur lesend prüfen.
- Das große Handbuch-PDF (160 MB, Name in `CLAUDE.local.md`) bei Läufen und Tests ausnehmen.
- `.exe` nicht neu bauen, solange `pdf2md.exe`-Prozesse laufen.
- Nur lokal committen, der Nutzer pusht selbst. Trailer: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Antworten und Kommentare auf Deutsch.
- Bedienung nur über das Fenster; keine Kommandozeilen-Flags und kein Ziehen auf die .exe wieder einführen.
- Oberfläche (Nutzervorgaben gegen „AI-Slop“): keine Verläufe, kein Glas-Effekt, keine Emoji-Icons, kein Lila-Blau, keine Karten in Karten, keine Hero-Fläche, keine erfundenen Beispielzahlen (leere Zustände sagen „Noch keine Daten“). Segoe UI Variable, eine Akzentfarbe (Petrol), 4/8-px-Raster, 1-px-Linien, `tabular-nums`, kompakt. Kein CDN, kein npm.

## Bekannte Grenzen (nicht als Fähigkeit annehmen)

- Markdown-Tabellen nur bei gezeichneten Gitterlinien (Tabellen aus reinem Leerraum und reine Linien-Tabellen ohne senkrechte Striche bleiben Text); Formelstruktur nur teilweise (Indizes, Brueche, Wurzeln, Operatorgrenzen; keine Matrizen/grossen Klammern); rund 60.000 `�` bleiben.
- Bilder fehlen. Lesereihenfolge nur bei zwei Spalten korrigiert (siehe lesefolge.py); Fußnoten sind nicht geprüft.
- Überschriften nur aus Lesezeichen (2 von 58 Büchern haben keine). Das 160-MB-Handbuch wurde nie getestet.
- Die Heuristiken sind an 58 Büchern abgestimmt, die Tests sind synthetisch.

## Ablauf und Ablage

- Fehlt Titel, Autor oder Jahr, oder ist kaum Text vorhanden: Originalname behalten, Ablage in `Prüfen`; Grund steht im Kopfblock unter `pruefen:`.
- `nachbessern()`: Läuft bei jedem Klick auf „Starten“ (am Ende von `eingang_verarbeiten()`). Übernimmt Dateien aus `Prüfen`, sobald der Nutzer Titel/Autor/Jahr im Kopfblock der `.md` ergänzt hat. Scans ("kaum Text") bleiben, bis die Zeile `pruefen:` gelöscht ist.
- Werkzeug „Rückgängig“ (`rueckgaengig_plan()` / `rueckgaengig(plan)`) dreht den letzten Lauf anhand von `Protokoll.csv` zurück (verschiebt, löscht nie). Deshalb schreibt jede Aktion, die Dateien bewegt, eine Protokollzeile mit `von_pfad`, `nach_pfad`, `md_pfad`.
- Werkzeug „Namen reparieren“ (`namen_plan()` / `namen_reparieren(lauf, plan)`): benennt Dateien in `Fertig` nach dem Kopfblock der `.md` um. Immer erst Vorschau im Fenster, ausgeführt wird genau der gezeigte Plan (verschwundene Dateien werden übersprungen), Status `UMBENANNT`, mit Rückgängig umkehrbar. Läuft bewusst nicht automatisch, weil von Hand umbenannte Dateien sonst zurückbenannt würden.
- Werkzeug „Text erneuern“ (`text_plan()` / `text_erneuern(lauf, plan, abbrechen, datei_beginnt, datei_fertig)`): erneuert nur den Text bereits verarbeiteter PDFs in `Fertig`, Kopfblock bleibt, alte `.md` kommt nach `Sicherung/`. Nicht in Rückgängig eingebunden.
- `.md` immer mit LF schreiben (`md_schreiben`), Kopfblock beim Lesen tolerant (BOM, fehlende Anführungszeichen).
- Logging von `pdfminer`/`pdfplumber`/`pypdf` steht auf ERROR (Modulebene, damit es auch in den Unterprozessen gilt).

## Namen und Metadaten

- `neuer_name()` kürzt bei zu langen Namen nur den Titel, nie Autor und Jahr: erst Untertitel weglassen (Trenner " – "), sonst am Wortende mit "…". Der volle Titel bleibt im Kopfblock.
- Das Erstellungsdatum einer Datei gilt bewusst nicht als Erscheinungsjahr (`JAHR_AUS_ERSTELLDATUM = False`). Ausnahme: EPUB-Datum, das ist das Erscheinungsdatum.
- Jahr: ©-Vermerk im Textanfang (jüngstes Jahr). Fehlendes wird per ISBN/DOI bei Crossref nachgeschlagen (`ONLINE_ABGLEICH`).
- Springer-PDFs haben oft die ISBN als PDF-Titel; `ist_kennung()` verwirft das und nutzt sie zum Nachschlagen.

## PDF-Text

- Standard-Engine ist PDFium (`PDF_ENGINE="pdfium"`, über `pypdfium2`), NICHT MarkItDown. Grund (an 59 echten Büchern gemessen): MarkItDowns PDF-Weg klebt Wörter zusammen (pdfplumber-Standardabstand, sobald eine Seite "formularartig" aussieht) und macht aus Formeln/Fließtext Tabellen. Rückfall: Einstellung PDF-Engine = MarkItDown (mit gepatchtem pdfplumber, `x_tolerance_ratio=0.15`, und ohne `(cid:N)`).
- Bereinigung in `seiten_zu_text()`: Ligaturen, Silbentrennung (`_trennungen_verbinden`), Absätze (`_absaetze_bilden`, bewusst vorsichtig), Kopf-/Fußzeilen (`_kopf_fuss_entfernen`, ≥8 Seiten, ≥5 Zeichen, Strukturwörter wie "Aufgabe" ausgenommen), Seitenmarker (siehe Abschnitt Seitenzahlen). `nutztext()` entfernt die Marker (Scan-Erkennung, Jahr-Suche).
- Unlesbare Glyphen (Steuerzeichen 0x01-0x1F) werden zu `�`, weil das meist TeX-Formelsymbole sind; nicht stillschweigend löschen.
- Weiches Trennzeichen U+00AD mit folgendem (erzeugtem) Leerzeichen ist ein Zeilenende und wird wie `-\n` verbunden (`_trennungen_verbinden`); vorher löschte `STEUERZEICHEN` nur das U+00AD und es blieb „Bruch prüfung“.
- Tabulatoren werden zu Leerzeichen, der Text wird NFC-normalisiert (`_seite_bereinigen`).
- `kodierung_defekt()` erkennt PDFs mit fehlenden Umlauten (`fr`, `Lsung`) und setzt `warnung:` (blockiert Fertig nicht). `umlaute_ergaenzen()` macht `f�r` zu `für`, wenn dasselbe Wort im selben Buch intakt vorkommt (eindeutig, mind. 2-mal). Lesezeichen-Titel zählen doppelt (sie sind auch bei defekter Kodierung intakt); nötig, seit Überschriften doppelte Titelzeilen ersetzen und damit ein zweiter Beleg fehlte (Buch mit defekter Kodierung: „Zahnr�der“).
- Große PDFs (>=150 Seiten) werden beim MarkItDown-Weg in Paketen parallel umgewandelt, `MAX_PROZESSE = os.cpu_count() or 8` (keine feste Obergrenze mehr, war früher 8); `multiprocessing.freeze_support()` ist für die .exe Pflicht. PDFium braucht das nicht. Getestet in `tests/test_parallel.py` (war vorher ungetestet).
- Lesezeichen: `lesezeichen_lesen()` liest die PDF-Gliederung (PDFium `get_toc`), `_ueberschriften_einfuegen()` macht daraus `#`/`##`/... Steht der Titel als eigene Zeile im Seitentext, wird genau diese Zeile zur Überschrift, sonst kommt sie an den Seitenanfang. Seiten ohne Text bekommen nie eine Überschrift (sonst würde die Scan-Erkennung getäuscht). Im Kopfblock: `lesezeichen:`; `textquelle` endet auf "+ Lesezeichen", damit „Text erneuern“ ältere Bücher erkennt.

## Lesereihenfolge (`lesefolge.py`)

- Zweispaltige Seiten, bei denen PDFium die rechte Spalte vor der linken liefert (z. B. Springer/InDesign), werden in Lesereihenfolge gebracht. Schalter `SPALTENREIHENFOLGE` (Einstellungen), Kopfblock `spalten:`, `textquelle` endet auf "+ Spaltenreihenfolge".
- Ablauf: `laeufe_lesen()` zerlegt den Zeichenstrom in Zeilenstücke, `analysiere()` sucht genau eine Spaltenlücke und greift NUR ein, wenn im Strom eine rechte Textzeile vor einer linken desselben Bandes steht; `bereiche()` prüft zusätzlich mit `satzbrueche()` am Text, dass die neue Reihenfolge nicht schlechter ist. Sonst kommt None, und alles bleibt wie PDFium es liefert (unveränderte Seiten sind Zeichen für Zeichen gleich).
- Zwei Stellen bauen Seitentext auf und müssen dieselbe Reihenfolge nutzen: `pdf2md._pdfium_seiten` (über `lesefolge.seitentext`) und `formeln.Reparatur.reparieren` (Wiederaufbau aus den Zeichen über `sz.folge`). Ein Test (`test_spalten.py`) prüft, dass beide übereinstimmen.
- Gemessen: die Kontrolle "Zeilenübergang" (Satzende, dann klein) taugt nur als Sicherung gegen Verschlechterung, nicht als Qualitätsmaß (zu unempfindlich). Eine rein geometrische Umsortierung ohne die Bedingung "nachweislich falsch" verschlechterte viele Seiten mit Tabellen, Bildern und Kästen. Nicht lockern ohne neue Messung.
- `_kopf_fuss_entfernen()` (pdf2md.py) prüft deshalb nicht nur die exakt erste/letzte Zeile, sondern bis zu `KOPF_FUSS_RAND=3` Zeilen vom Rand (erkannt wird eine Kopf-/Fusszeile aber weiterhin nur anhand ihres Vorkommens an der echten Kante, sonst zählten sich wiederholende Fliesstext-Anfänge falsch mit). Gemessen an 26 betroffenen Büchern: Kantenlecks von 2217 auf 375 gesenkt (−83 %).
- **Absatzbruch an Spalten-/Bandgrenzen erzwingen:** `_ordnung_mit_bruechen()` (intern hinter `analysiere()`) merkt sich zusätzlich, vor welchen Läufen ein Sprung im Original-Strom liegt (Spalten-/Bandwechsel). `bereiche()` gibt das als 4. Tupel-Feld `hart` zurück; `seitentext()` fügt dort `SPALTENBRUCH` (ein Zeichen aus dem privaten Unicodebereich, ``) statt eines normalen Umbruchs ein. `pdf2md._seite_bereinigen()` wandelt ihn in eine echte Leerzeile um, BEVOR `_absaetze_bilden()` läuft (das überbrückt eine Leerzeile schon von sich aus nie). Grund für den Marker statt direkt einer Leerzeile: `zeilen_je_seite` (pdf2md.py) filtert leere Zeilen weg, der Marker (kein Whitespace) übersteht das.
  **Falle (zweimal genau so aufgetreten):** Jeder Lauf trägt praktisch immer seinen eigenen `\r\n` schon am Ende (PDFium schliesst den Zeilenumbruch in den Zeichenbereich mit ein). Die Wächterbedingung `if teile and not teile[-1].endswith(("\n","\r",...))` ist deshalb fast immer False — ein `hart`-Einschub HINTER dieser Bedingung feuert praktisch nie. Der Marker muss unabhängig von ihr eingefügt werden (in `lesefolge.seitentext()` UND in `formeln.py`s Wiederaufbau-Schleife, die dieselbe Reihenfolge separat nachbaut — beide müssen konsistent bleiben). Mit echten Büchern verifizieren, nicht nur mit Kurzbeispielen; synthetische Test-PDFs (fpdf2) laufen bei zu langem Text über die feste Zellenbreite über, was die Spaltenerkennung selbst verfälscht (Testzeilen kurz halten, vgl. `spaltenzeilen()` in conftest.py).
  Gemessen an allen 58 Büchern: über 3000 Spalten-/Bandgrenzen markiert, nur 2 blieben verklebt (zusammengehörige Formelzeilen I/II/III, vermutlich sogar korrekt).
- Werkzeug-Falle: In Bash-Heredocs Escape-Sequenzen wie `\n` oder `￾` nicht in Python-Code einbauen, das ergibt kaputte Dateien; Dateien mit Write/Edit ändern.

## Zweiter Durchgang in `_pdfium_seiten` (Zeichenkorrektur und Tabellen)

- Durchgang 1 liest jede Seite wie bisher (`get_text_range`/`lesefolge`), merkt sich verdächtige Seiten (`zeichen.verdaechtig`, `Korrektur.lernen` sammelt Hinweise je Schrift) und Gitter (`tabellen.gitter`). Durchgang 2 liest nur diese Seiten Zeichen für Zeichen neu (`zeichen.zeichen_lesen`, mit `lesefolge.seitentext(..., lesen=...)` bei umgestellten Seiten).
- Gemeinsames Format: `{Zeichenindex: Ersatz}` je Seite; `""` = Zeichen entfällt. Tabellen nutzen dasselbe: das erste Zeichen einer Tabelle wird zur ganzen Markdown-Tabelle (mit `SPALTENBRUCH`-Markern davor/danach = Leerzeilen), die übrigen Zeichen der Tabelle werden `""`.
- `formeln.Reparatur.reparieren(..., korrekturen=)` bekommt diese Dicts und setzt sie beim Neuaufbau einer Seite wieder ein, sonst gingen sie auf Formelseiten verloren.
- `zeichen_lesen` muss exakt `get_text_range` entsprechen (geprüft an 170 Buchseiten: 0 Abweichungen): Zeichen mit `FPDFText_GetTextIndexFromCharIndex == -1` auslassen (so verschwinden z.B. `\x03`), `\x02` wird `￾`.

## Zeichenkorrektur (`zeichen.py`)

- Umlaut-Leerzeichen: nur Trema (U+0308) auf a/o/u bzw. `ǆ`/`Ƶ` nach Vokal, nur erzeugte Leerzeichen (`FPDFText_IsGenerated`), nur vor Kleinbuchstaben. **Nicht** auf andere Akzente ausweiten: in Physik-/Thermodynamik-Büchern ist das Leerzeichen nach `Q̇`, `ū`, `c̄` echt (gemessen, sonst „Q̇Wärmestrom“), französisch „à l'arc“ ebenso. NFC fügt dann „u“+Trema zu „ü“ zusammen (`_seite_bereinigen`).
- Mac-Roman: je Schrift, nur mit ≥5 Hinweisen (‰ ¸ ˆ mitten im Wort, Kleinbuchstabe danach) in ≥3 verschiedenen Wörtern, 0 intakten ä/ö/ü, und nie in Formelschriften (`FORMELSCHRIFT`). Grund: in TeX-/MathTime-Schriften ist „ˆ“ das Dach über Variablen (`xˆ`, `Gˆw`), die erste, lockerere Regel traf dort 20 Bücher falsch. Das Mac-Roman-„ﬂ“ (= ß) zerlegt PDFium in f+l mit identischem Zeichenrahmen, ein echtes „fl“ hat zwei Rahmen (`_eine_glyphe`).
- Symbol/Wingdings: Zuordnung nur nach Schriftname (`symbol`/`wingding`), die Codes U+F0xx bedeuten je Schrift etwas anderes (0x6F: Symbol ο, Wingdings □).
- Doppelt gedruckter Text (doppelte Inhaltsebene, gemessen an drei Büchern: 291.000 Zeichen auf 392 Seiten, 261.000 und 65.000): Verdacht per `doppelt_verdacht()` (≥3 längere Zeilen doppelt oder verdoppelte Formelzeichen „𝑁𝑁“). Entfernt werden **ganze Zeilen** des Zeichenstroms, deren sichtbare Zeichen zu ≥90 % mit gleichem Code an derselben Position (auf 0,1 pt) schon früher stehen, dazu das zweite von zwei gleichen aufeinanderfolgenden Formelzeichen (U+1D400ff.) am selben Ort. Die erste Fassung arbeitete Zeichen für Zeichen und war falsch: aufgelöste Ligaturen (f, f, i mit gleichem Rahmen) verloren ein f, und zwei verschiedene übereinander gedruckte Texte (korrigierte Fassung in einem Lehrbuch) wurden zu Buchstabensalat. `tabellen.einsetzen` entdoppelt Zellen zusätzlich selbst. Verbleibende „𝐶𝐶𝐶 = 𝐶 + 𝑀𝑀“ (CEV-Formel in einer Stahlnorm) sind keine Doppeldrucke, sondern kaputte Zeichenzuordnung im PDF.

## Normen (`normen.py`)

- Quellen in dieser Reihenfolge: Kopfzeile `NUMMER:JJJJ-MM` (≥2 Seiten und entweder ≥25 % der Seiten oder schon auf den ersten 4 Seiten; bei DIN-EN-Normen steht die DIN-Kopfzeile nur auf den nationalen Vorseiten), „Ref. Nr.“ der Titelseite, erstes Lesezeichen, Dateiname `NUMMER_JJJJ-MM-TT_DE_1234567.pdf`.
- Titel: Nummernzeile auf der Titelseite (≥11 pt), danach die Zeilen in derselben Schriftgröße (±0,6 pt; Größe = FontSize × Textmatrix) bis „Deutsche Fassung“/andere Größe. Alte Titelseiten (bis ~2004): Zeilen unter „DEUTSCHE NORM“ bis „Deutsche Fassung“/ICS. Teile ohne Strich werden mit „ – “ verbunden, außer die Zeile endet auf ein Füllwort („und“, „für“, …).
- `norm_uebernehmen()` überschreibt Metadaten-Titel/-Autor und Jahr immer (Norm-Metadaten sind Müll, Jahr aus © wäre Druckdatum oder ersetzte Ausgabe). `neuer_name()` kürzt Normtitel anders als Buchtitel (Nummer + letzter Teil bleiben, `NORMTITEL`).
- Wasserzeichen `LIZENZVERMERK` („Datum / Uhrzeit des Ausdrucks: … Printed copies are uncontrolled“) wird vor der Kopf-/Fußzeilen-Erkennung aus jeder Zeile entfernt, auch wenn es an Text klebt oder über bis zu drei Zeilen umbrochen ist; es enthält Firmen- und Benutzernamen. `LEERSEITE`-Zeilen („— Leerseite —“, „This page is intentionally blank.“) fallen ebenfalls weg.
- Nicht lösbar (Scan): einzelne Deckblatt-/Anhangseiten alter Normen sind Bilder mit unsichtbarer Texterkennungs-Ebene (Schrift z.B. `CALS_InvisibleTTFont`): gesperrter Text („Pr üf u n g“), Tabellenlinien nur als Pixel. Kein OCR/Scan-Support (Nutzerregel). Eine solche Norm liegt inzwischen als Textfassung vor (Scan in `Duplikate`).
- Weitere Lizenzvermerke (`LIZENZVERMERK`): Hex-Kennung als eigene Zeile, "Normen-Ticker"/"Normenabonnement" mit `Kd.-Nr.`/`Abo-Nr.` (persoenliche Daten, Test `test_kunden_und_abovermerke`). Strichcode vor der 7-stelligen Dokumentnummer: `_strichcode_entfernen`.
- Erkennung ohne Kopfzeile: Lesezeichen nur mit Nummer + Monat/Jahr vom Deckblatt; frei benannte Dateien (`DATEINAME_FREI`) nur als letzter Ausweg (2 von 20 neuen Dateinamen nannten eine falsche Ausgabe). Titel notfalls aus dem Berichtigungsvermerk (`_titel_nach_ausgabe`).

## Tabellen (`tabellen.py`)

- Linien = dünne Pfadobjekte (≤2,5 pt) und Kanten umrandeter (nicht gefüllter) Rechtecke; zusammenfassen, freie Enden iterativ behandeln (Zeichnungslinien hängen frei): kurze freie Endstücke (≤50 % der Länge) werden abgeschnitten, Linien mit langen freien Enden oder <2 Kreuzungen entfallen. Früher entfiel jede Linie mit freiem Ende; dabei verschwanden Trennlinien, die in einer verbundenen Kopfzelle enden (Normtabellen: „µm | mm“, „Kurzname | Werkstoffnummer“), und Spalten verschmolzen („60 0,1“). Mit Kürzen: 816 statt 784 Tabellen in den Normen, 86 Normtabellen besser gegliedert; Tabelle nur mit ≥2 durchgehenden waagerechten Linien (≥90 % Breite). Verbundene Zellen per Union-Find (fehlende Trennlinie über ≥50 % der Kante).
- Seitlich offene Tabellen (`_offene_seiten`): ragen ≥2 waagerechte Linien (Originallänge vor dem Kürzen, `Strecke.roh()`) über die äußerste senkrechte Linie hinaus, bekommt die Tabelle dort eine Randspalte. Sonst fehlten die Randspalten, und Wörter wurden am Rand zerschnitten (Buch mit Normtabelle: „Zeile“ und „Spalte 7“ fehlten, „Nennmaße|n in m“). Das Problem trat erst nach der Entdoppelung auf, vorher scheiterte die Tabelle am doppelt gedruckten Text.
- Gegen Diagramme/Zeichnungen (`echt()`): ≥3 gefüllte Zellen in ≥2 Zeilen und ≥2 Spalten, Füllgrad ≥25 %, höchstens 1 „Wortschnitt“ (zwei Zeichen ohne Leerraum, gleiche Zeile, Abstand <0,25 Schriftgröße, in verschiedenen Zellen). Vorher ohne diese Filter: viele 2×2-Fehltreffer aus Abbildungen in Büchern; leere Formblätter (nur Kopfzeile gefüllt) fallen jetzt ebenfalls raus, ihr Text bleibt normaler Text.
- Zelltext: Leerzeichen liefert PDFium; ein Zeilenwechsel in der Zelle zählt, wenn sich zwei Zeichen quer zur Schreibrichtung nicht überlappen (sonst „+6+4“ statt „+6 +4“). Eigene Lücken-Leerzeichen nach Zeichenrahmen waren falsch („Alu miniu m“, schmale Glyphen). Schreibrichtung per `FPDFText_GetCharAngle`: senkrechte Spaltenköpfe (90°) sonst „B r u c h p r ü f u n g“. Kombinierende Akzente hängen immer direkt am Buchstaben davor (das Trema sitzt höher und galt sonst als neue Zeile: „Fla ̈ che“); von `zeichen.py` gestrichene Leerzeichen trennen nicht.
- Dünn gefüllte Gitter (<50 %): nur mit regelmäßigem Raster (≥0,6 Zellen je Elementarzelle) und nicht als kleiner Rahmen (≤16 Zellen oder ≤2 Spalten) mit kurzen Beschriftungen (<15 Zeichen je Zelle). Kalibriert an 57 Büchern (Schaltbilder, Blockschaltbilder) und 46 Normen (GPS-Matrizen und Formblätter bleiben).
- `_absaetze_bilden` verbindet nie Zeilen, die mit „|“ beginnen.
- Tabellen nur mit waagerechten Linien (Springer/booktabs: oben, unter dem Kopf, unten): `linien_kandidaten()` (>=3 gleich lange Linien >=25 % Seitenbreite, keine senkrechte Linie dazwischen, nicht in einem Gitter), `linientabellen()` mit den Zeichen aus `formelsatz.zeichen`: Spalten = x-Bereiche, die in keiner Rumpfzeile bedeckt sind (>=0,8 Schriftgroessen), Zeilen = sichtbare Zeilen; Fortsetzungszeile (erste Spalte leer, hoechstens die Haelfte der Spalten belegt) gehoert zur Zeile davor; Kopfwort ueber mehrere Spalten verbindet die Zellen; zwei Tabellen mit gleich langen Linien werden an "Tab. N" getrennt. `echt()` strenger (Fuellgrad >=50 %, <=40 Zeichen je Zelle, jede Spalte in >=50 % der Zeilen belegt). Gemessen vor dem Bau: rund 300 Buchseiten mit solchen Tabellen.

## Seitenzahlen und Zitieren (`seitenzahlen.py`, `pdf2md.seiten_zu_text`)

- Marker: `<!-- Seite S (PDF N) -->` (S = gedruckte Zahl, auch roemisch), ohne gedruckte Zahl `<!-- PDF-Seite N -->`; altes `<!-- Seite N -->` wird beim Lesen noch erkannt (`SEITENMARKER_MUSTER`). Kopfblock: `seitenzahlen:`, `zitierhinweis:`.
- Quelle 1: Seitenlabel (`FPDF_GetPageLabel`), nur wenn es nicht bloss die Position wiederholt (eine Norm: Labels 1..n, gedruckt ab PDF 10) und den Randzahlen nicht widerspricht. Quelle 2: Randzahlen-Folge mit gleichem Versatz (>=3 Belege, Luecken <=8, Dichte >=0,4; Versatz-0-Vorseiten von Normen auch mit 1 Beleg); 2 Seiten Verlaengerung; EN-Deckblatt zwischen zwei Abschnitten bekommt die 1 des folgenden.
- Gemessen (`werkzeuge/seitenpruefung.py`, Inhaltsverzeichnis gegen Lesezeichen): 8954 gleich, 25 anders, alle 25 = Lesezeichen eine Seite zu frueh. Deshalb `_lesezeichen_nachschieben()`: Titel nicht auf seiner Seite, aber auf der naechsten -> dorthin.
- `_kolumnentitel_entfernen()`: Randzeile, die mit der gedruckten Zahl beginnt/endet, nur wenn >=30 % der Seiten so eine haben (45.000 Woerter Kolumnentitel in 58 Buechern).
- `_ueber_seitenwechsel()`: Trennung "Reg-" + "ler" -> Wort an die vorige Seite; Satz laeuft weiter (vorige Zeile >=30 Zeichen ohne Satzende, kein Abb./Tabelle-Anfang, neue Seite beginnt klein) -> Marker mitten im Satz. Weiche Trennung am Seitenende wird zu "-" (`_seite_bereinigen`), PDFium haengt die Seitenzahl manchmal direkt an ("Anfor￾16", `_seitenzahl_abtrennen`).
- Pruefung: `werkzeuge/zitierpruefung.py` sucht Saetze auf der Marker-Seite (Bezug: korrigierter Seitentext, nicht Rohtext, sonst scheitert es an "Schweiflen"). Normen: 98,7 % gefunden, 0 auf falscher Seite.

## Quellenangabe (`zitierdaten.py`)

- IEEE deutsch ("Aufl.", "Hrsg.", "und", >6 Personen "et al."), Kopfblock `quellenangabe`, `verlag`, `ort`, `auflage`, `herausgeber`, `isbn`, `doi`, `zitierdaten_quelle`. Normen: `*Titel*, NUMMER:AUSGABE, JAHR.` (ohne Online).
- Verlag/Ort/Auflage bevorzugt DNB (SRU, MARC21: 264/250/700 mit `$4 edt`), Personen/DOI Crossref; Untertitel "Fachlicher Träger ..." verworfen, Ort ohne ", Germany".
- Sammelwerke (Crossref `edited-book`/`reference-book` oder nur Herausgeber): Kapitel-DOIs im Text -> `<!-- Kapitelquelle (IEEE): ... -->` hinter dem Seitenmarker der Kapitelseite.
- Datenschutz (Nutzerwunsch): nur DOI/ISBN in der URL, User-Agent `pdf2md/1.0` ohne Kontaktangabe. Test `test_user_agent_ohne_persoenliche_angaben`. Nie E-Mail o.ae. ergaenzen ("polite pool").
- „Text erneuern“ ergaenzt fehlende Felder; nur eine reine Offline-Angabe ("nur Titel, Autor und Jahr") wird ersetzt.

## Formelsatz (`formelsatz.py`)

- Laeuft im zweiten Durchgang von `_pdfium_seiten` auf jeder Seite mit Text (nach zeichen.py, vor tabellen.py, damit Zellen "$^{a}$" bekommen). Seiten mit nur einer Schriftgroesse (Textobjekte) und ohne Striche werden uebersprungen. Kosten ~20 ms/Seite (Buecher insgesamt etwa doppelte Laufzeit).
- Hoch/tief: kleineres Zeichen (<=0,85) gegen den naechsten groesseren NACHBARN (nicht die Zeilenmitte: PDFium legt Nenner, "=" und Zaehler in eine Zeile, Fussnoten nebeneinander). PDFium erzeugt Leerzeichen zwischen Zeichen und Index; `_getrennt()` ignoriert sie bei schmaler Luecke. Index+Exponent am selben Zeichen stehen in x durcheinander -> erst alle tiefen, dann alle hohen (`s_{irr,12}^{R}`). Der Nachbar zaehlt nur, wenn er Buchstabe/Ziffer/Klammer ist (`_kann_basis`), der Index rechts davon steht (Fussnotenzeichen links) und senkrecht ueberlappt (Satzzeichen ausgenommen): sonst wurden die Ziffern der Dokumentnummer unter dem Strichcode des Norm-Deckblatts zu Indizes ("428$_{94}$7").
- Ausgabe ausserhalb von Formeln: die Index-Gruppe wird an ihr Bezugszeichen gehaengt (auch wenn PDFium sie in eine eigene Zeile setzt, "Ṡ R" / "irr,12"); `_zeilen()` haengt reine Klein-Zeilen (Exponent "2" von "m²") an die Nachbarzeile.
- Brueche: Striche sind Pfade ODER 0,5 pt hohe Bilder (TeX). Kein Bruch: Strich endet an/kreuzt senkrechte Linie, >=3 gleich lange Striche uebereinander (Tabellenzeilen), Strich laenger als Zaehler/Nenner + 2 Schriftgroessen, Spaltenluecken, mehr als 2 Zeilen, >=3 Woerter mit >=4 Buchstaben (Ueberschrift ueber Linie). Ohne diese Regeln wurden Dampftafeln zu `\frac{\frac{\frac{...`.
- CMEX-Schrift: "Z"/"R"/"P"/"X" (gross) sind ∫/∑ (`CMEX`-Tabelle, nur bei Schriftname CMEX). Integralgrenzen stehen rechts, nicht ueber/unter.
- Formelreparatur und Formelsatz: `formeln.Reparatur` ist geteilt in `analysieren()` (zwischen Durchgang 1 und 2) und `aufbauen()`; der Formelsatz holt reparierte Zeichen ueber `zuordnung_fuer(seite)`, sonst stuende in neu gesetzten Formeln "D" statt "=" (MathTime). Unlesbares ohne Zuordnung: Platzhalter `k:code`, aufgeloest in `formeln.aufbauen` bzw. `_pdfium_text`.
- `UNSICHER` ("⚠[Formel unsicher] ") vor Zeilen mit `$...$` die "�" enthalten (`_unsichere_formeln_markieren`) oder mit unsicherem Bruch.

## Kopf-/Fußzeilen (Ergänzungen)

- `KOPF_FUSS_MAX_LAENGE = 300` (vorher fest 100, wegen des langen Wasserzeichens). Dadurch trafen plötzlich Kapitel-Inhaltsverzeichnis-Zeilen mit Punktführern („Literatur . . . . 15“, >100 Zeichen); sie sind jetzt ausdrücklich ausgenommen (`PUNKTFUEHRER`).
- Gestapelte Kopfzeilen (Normen: „DIN EN ISO 12345:2023-07“, darunter „EN ISO 12345:2023 (D)“): weitere Runden nach dem Entfernen der erkannten Kante, aber nur Zeichen für Zeichen gleiche Zeilen und getrennt nach oben/unten (sonst verschwindet erster Fließtext jeder Seite, siehe Tests in `TestKopfFuss`).
- Kurze Dokumente: Schwelle `min(8, max(3, 60 % der Seiten))`.

## Formelreparatur (`formeln.py`)

- Weg A: Glyphnamen aus dem CFF-Schriftprogramm (nur ohne `/ToUnicode`, exakt).
- Weg B: Formvergleich (gerenderte Probe gegen STIX/DejaVu, Abstimmung je (Schrift, PDFium-Zeichen)).
- Schwellen `MIN_WERT=0.6`, `MIN_MARGE=0.06` sind an zwei unabhängigen Datensätzen gemessen; nicht lockern ohne neue Messung.
- Mathezeichen unter Steuercode werden nie stillschweigend gelöscht; Buchstaben und Ziffern werden nie durch andere Buchstaben oder `�` ersetzt.
- MathTime-Schriften erkennt `MT2(?=[A-Za-z])|MTEX|MTMI|MTSY|MathTime`; `TimesNewRomanPSMT2` und `ArialMT2` dürfen nicht treffen.
- PDFium-Fallen: `FPDFText_GetFontSize` ist bei TeX-PDFs oft 1 (echte Größe = FontSize × Textmatrix); Zeichen außerhalb der Basisebene kommen als UTF-16-Hälften (`chr()` einzeln ergibt ungültigen Text und bricht das Speichern ab); `get_text_range` versteckt `\x02` (Trennstrich/Umlaut) als `￾`.

## Fenster (`ui_app.py`, `ui/web/`)

- Aufbau: `ui_app.Api` ist die einzige Schnittstelle der Oberfläche (öffentliche Methoden; im Fenster über `window.pywebview.api`, im Entwicklungsserver `werkzeuge/ui_vorschau.py` per `POST /api/<methode>`, erkennbar am meta-Tag `pdf2md-modus`). Die Oberfläche fragt `signatur()` (alle 1,5 s, im Lauf 0,4 s) und `ereignisse(nach)` ab; Python schiebt nichts per `evaluate_js` (Ausnahme: Rückfrage beim Schließen).
- Lauf: ein Thread zur Zeit (`Api._starten`), `pdf2md.eingang_verarbeiten()` bzw. die Werkzeuge mit `abbrechen`/`datei_beginnt`/`datei_fertig`; Meldungen und Fortschritt kommen über `pdf2md.rueckmeldung(melder, fortschritt)` statt `print` (`melden()`, `fortschritt_melden()`; ohne Fenster bleibt `print`). Abbrechen greift vor der nächsten Datei. Fortschritt gedrosselt (0,2 s). Einstellungen sind während eines Laufs gesperrt.
- Falle: pywebview ruft jede Api-Methode in einem eigenen Thread auf -> gemeinsamer Zustand nur unter `self._sperre`, Laufzustand als tiefe Kopie herausgeben. Api-Attribute privat halten (Unterstrich), sonst versucht pywebview, sie für JavaScript freizugeben.
- Falle: Einstellungen in Unterprozessen. `ProcessPoolExecutor` startet frische Prozesse mit Standardwerten; `_markitdown_umwandeln` übergibt deshalb `initializer=einstellungen.anwenden`. Abgeleitete Werte (`tabellen.MIN_UEBERSTAND = 3*TOLERANZ`, `zitierdaten.TIMEOUT = ONLINE_TIMEOUT`) stehen in `einstellungen.ABGELEITET`; geänderte `formeln.GLYPH_GROESSE`/`RASTER` setzen `formeln._REFERENZ` zurück. Neue Konstanten in `einstellungen.EINSTELLUNGEN` eintragen; ein Test prüft Standard = Code und dass keine Einstellung beim Import kopiert wird (Default-Argumente, `from x import`).
- Falle: Einstellungen schnell hintereinander (Pfeiltasten am Regler) dürfen sich nicht überholen: `setzenPlanen()` sammelt 250 ms und speichert strikt nacheinander, die Zeile wird an Ort und Stelle aktualisiert (vorher: Anzeige 2,5, gespeichert 3,0).
- Schließen während eines Laufs: `closing`-Handler liefert False, Rückfrage im Fenster, dann `schliessen_anfragen()` (Abbruch nach der aktuellen Datei, danach `destroy`). Einzelinstanz je Ordner per benanntem Mutex. Ziehen ins Fenster: DOM-Handler auf `document` mit `pywebviewFullPath`, im Browser-Entwicklungsserver nicht möglich.
- Dateien und Ordner öffnen (Nutzerwunsch, Standardprogramm von Windows über `ui_app.extern_oeffnen`): `Api.datei_oeffnen(bereich, name, art)` nimmt nur einen Dateinamen aus Eingang/Prüfen/Fertig (kein Pfad aus der Oberfläche, `..` und andere Ordner abgelehnt), `art="original"` öffnet das Original zur `.md`; `Api.ordner_oeffnen(bereich)`. Tests ersetzen `extern_oeffnen`, damit beim Testen nichts aufgeht.
- Hinzufügen kopiert nach `Eingang` (`ablage.kopieren`, keine Protokollzeile, Rückgängig löscht keine Kopien). Fertig zeigt je Buch eine Zeile. Prüfen: „bereit zur Übernahme“ nach `pdf2md.uebernahme_pruefen()` (dieselbe Regel wie `nachbessern`).
- Text-Qualität (`auswertung.textqualitaet`): je Punkt Wert / höchstmögliche Anzahl (unlesbare Zeichen = repariert + verbliebene `�`, Formelzeilen mit `$…$`, Tabellentitel im Text, Überschriften aus Lesezeichen, Seiten, Seiten mit Marker, Bücher), gezählt nur über Bücher, deren `textquelle` das Verfahren nennt; sonst stünden ältere `.md` mit 0 im Zähler und vollem Nenner da.
- Auswertung: Dauer aus den `zeit`-Abständen je Lauf (erste Datei: Abstand zu `lauf` = Startzeit), Seiten aus dem Kopfblock (Name oder `originaldatei`), über 6 h = unbekannt; `Protokoll.csv` bleibt im alten Format. Kennzahlen je `.md` zwischengespeichert nach (mtime, Größe). Gedruckte Seitenzahlen nur aus neuen Markern; ältere `.md` (ohne neue Felder) zählen als „nicht erfasst“, die Oberfläche sagt das dazu.
- Entwickeln nie gegen `dist`: Kopie der Ablage im Scratchpad anlegen, `Protokoll.csv` dabei auf die Kopie umschreiben (sonst würde Rückgängig in `dist` verschieben), Originale dürfen Platzhalter sein. Screenshots: Edge headless gegen `ui_vorschau.py` mit `?thema=hell|dunkel&seite=uebersicht|auswertung|einstellungen&experte=offen`.
- Build: Einstieg `ui_app.py` (`--onefile --windowed --name pdf2md`), `ui/web` per `--add-data`, pywebview-Plattformmodule und pythonnet ausdrücklich mitnehmen; `freeze_support()` steht in `ui_app.main()`. Die exe braucht die WebView2-Laufzeit (Windows 10/11 hat sie).

## Härtetest (`werkzeuge/haertetest.py`, `tests/test_haertetest.py`)

- Gefunden und behoben (je mit Regressionstest): `UNBRAUCHBARE_TITEL` war nicht verankert und verwarf echte Titel („Sehr langes Dokument“, „Layout von Leiterplatten“); Titel nur aus Sonderzeichen ergab den Namen „ - Autor - Jahr“ (`titel_brauchbar`); Autoren „python-docx“/„openpyxl“/„Microsoft Office User“; HTML ohne Zeichensatz wurde von MarkItDown falsch geraten (`html_dekodieren`, danach `convert_stream` mit UTF-8); XLSX „NaN“ in leeren Zellen; Office/EPUB/HTML mit wenig Text galten als Scan (`MIN_TEXT_DOKUMENT`); Fehlermeldungen der Bibliotheken unverständlich (`fehlertext`); gesperrtes Original hinterließ eine verwaiste `.md` und beim nächsten Lauf ein Duplikat „(2)“ (`.md` wird bei Fehlschlag gelöscht, Nachbessern/Rückgängig je Datei abgesichert); Rückgängig mit leerem `md_pfad` hätte `Path("")` = aktuellen Ordner verschoben; Kapitel-DOIs bei Netzausfall bis 400 × TIMEOUT (`KAPITEL_STAPEL`); tiefe Ordner > 260 Zeichen (`name_laenge`).
- Fenster bei vielen Büchern: Kennzahlen im Thread hielten den Interpreter (GIL) so lange, dass jede Abfrage Sekunden wartete (640 Bücher: 24 s leer). Jetzt liefert `stand()` die Listen sofort, Kennzahlen rechnet `_vorwaermen()` (ab `PARALLEL_AB_BUECHERN` in Unterprozessen über `ablage.kennzahlen_lesen`, auch in der .exe geprüft), die Signatur ändert sich danach. Ein Skript per stdin kann keine Unterprozesse starten (multiprocessing braucht eine Datei); `_vorwaermen` fällt dann auf den Thread zurück.
- Gemessen: 2000 PDF-Seiten 11 s, 60.000 XLSX-Zeilen 18–23 s (MarkItDown/pandas), 30.000 HTML-Absätze 2 s; 165 Einstellungsvarianten an zwei echten PDFs ohne Ausnahme.

## Veröffentlichung (öffentliches Repo, MIT)

- Lizenz `LICENSE` (MIT, Inhaber „S4ltc“ = GitHub-Name, kein Klarname). Fremdlizenzen erzeugt `werkzeuge/drittlizenzen.py` aus requirements.txt samt Abhängigkeiten (Texte aus `.dist-info`, auch `licenses/`; fehlt ein Text, der Standardtext der angegebenen Lizenz), dazu Python und die Schriften.
- Releases baut nur GitHub (`.github/workflows/release.yml`, Tag `v*`): Build, alle Tests in derselben Umgebung, Paket `pdf2md-<tag>-windows.zip` (exe, LICENSE.txt, DRITTLIZENZEN.txt, docs/LIESMICH.txt) und SHA256SUMS.txt. Tests bei jedem Push: `tests.yml`.
- Datenschutz (Nutzerwunsch, essenziell): nichts Persönliches einchecken – keine Pfade mit Benutzernamen (die stehen in `CLAUDE.local.md`), keine echten Kunden-/Abonummern, Lizenzkennungen oder Ausdruckszeitpunkte aus Normen (Tests nutzen erfundene Werte), kein Buch-/Normtext und keine Titel, Autoren, ISBN/DOI oder Normnummern der eigenen Bücher und Normen (Tests und Kommentare nutzen erfundene Nummern wie 12345 und Titel wie „Beispielelemente“; was dahinter steht, nur in `CLAUDE.local.md`). Commits nur mit der GitHub-noreply-Adresse; die alte private Historie (private E-Mail als Autor) darf nie veröffentlicht werden. Vor dem Push prüfen: `git grep` nach Benutzername, E-Mail, `OneDrive`, `Kd.-Nr.`; Autoren mit `git log --format='%an <%ae>'`. Eine gebaute `.exe` prüft `werkzeuge/exe_pruefen.py <exe> --benutzer` (die lokale enthielt den Benutzernamen nicht, PyInstaller kürzt die Pfade; Treffer „runneradmin“ stammen aus vorgebauten Paketen).

## Tests

- `tests/` (pytest, rund 505 Tests, brauchen keine echten Bücher, alle Testdateien werden selbst erzeugt; `test_formelsatz.py` baut Zeichen als `formelsatz.Teil` nach, `test_zitierdaten.py` bildet Crossref/DNB nach). Abhängigkeiten: `requirements-dev.txt`. `test_zeichen.py` ersetzt PDFium durch eine nachgebaute Textseite (`RawNachbau`), so lassen sich erzeugte Leerzeichen, Schriften und Zeichenrahmen gezielt setzen.
- Regression an echten Daten: alten Stand per `git archive HEAD` in einen Ordner auspacken, beide Stände per `umwandeln()` über die Bücher in `dist\Fertig` laufen lassen (ohne das 160-MB-Handbuch) und die Ausgaben zeilenweise vergleichen. Die `.md` in `Fertig` taugen nicht als Referenz (älterer Stand, dort noch ohne Spaltenreihenfolge).
- Die Fixture `arbeitsordner` (conftest.py) leitet EINGANG/FERTIG/PRUEFEN/PROTOKOLL/SICHERUNG in ein tmp-Verzeichnis um und schaltet Crossref und Formelreparatur aus (deshalb steht dort im Kopfblock `einstellungen: "abweichend: …"`). `tests/test_ui_app.py` prüft die Api ohne Fenster (eigene Fixture mit `Einstellungen.json`). Die autouse-Fixture `keine_echte_ablage` leitet die Pfade in jedem Test zuerst nach tmp um (früher lagen Testreste `Prüfen/quelle (2).pdf` und eine `Protokoll.csv` im Projektordner). Tests mit Formelreparatur sind mit `langsam` markiert.
- Bei jedem behobenen Fehler einen Regressionstest ergänzen (Beispiele: `ArialMT2` darf nicht als MathTime gelten, UTF-16-Hälften dürfen den Text nicht unspeicherbar machen).
- Ein Mutationstest (absichtlich eingebaute Fehler im Speicher) hat 10 von 10 Fehlern erkannt.
