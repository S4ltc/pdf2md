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
- Pruefung an echten Daten: Skill `echte-daten-pruefen` (Skripte in `werkzeuge/`, README Abschnitt Tests). Ausgaben enthalten Buch-/Normtext: nur in den Scratchpad, nie ins Repo.
- Die venv liegt unter `%LOCALAPPDATA%\pdf2md-venv`, nicht in OneDrive. Rechnerspezifisches (Pfade zu Testdaten) steht in `CLAUDE.local.md`, die nicht ins Repo gehört. Das Repo ist öffentlich: keine persönlichen Daten, Pfade mit Benutzernamen, Kunden-/Abonummern oder Buch-/Normtext einchecken (Regel unter Verbindliche Regeln, Prüfung vor dem Push: Skill `veroeffentlichen`).
- Python 3.13 liegt unter `%LOCALAPPDATA%\Programs\Python\Python313\`; `py` funktioniert in neuen Terminals, `python` nicht.
- Git: `C:\Program Files\Git\cmd\git.exe` (der PATH in alten Shells ist veraltet).
- Eingaben nicht per PowerShell-Pipe in Python-Skripte füttern (BOM verfälscht die Antwort), sondern `subprocess` mit `input=` verwenden.
- Werkzeug-Falle: In Bash-Heredocs Escape-Sequenzen wie `\n` oder `￾` nicht in Python-Code einbauen, das ergibt kaputte Dateien; Dateien mit Write/Edit ändern.

## Aufbau

- `pdf2md.py` (gesamter Ablauf), `formeln.py` (Formelreparatur), `lesefolge.py` (Lesereihenfolge zweispaltiger Seiten), `zeichen.py` (Zeichenkorrektur je Schrift), `normen.py` (Normen erkennen), `tabellen.py` (Gitter-Tabellen als Markdown), `formelsatz.py` (Indizes, Brueche, Wurzeln, Operatoren als LaTeX), `seitenzahlen.py` (gedruckte Seitenzahlen), `zitierdaten.py` (Quellenangabe IEEE/APA 7/DIN ISO 690 und BibTeX ueber Crossref/DNB), `aktualisierung.py` (Version und Update-Suche), `plattform.py` (alles je Betriebssystem: Anzeige-Engine, Oeffnen, ein Fenster je Ordner, Thema, Ablageort), `schriftbild.py` (Schriftgroesse und Fett/Kursiv je Zeile: Ueberschriften ohne Lesezeichen, Hervorhebungen), `einstellungen.py` (alle einstellbaren Werte), `auswertung.py` (Kennzahlen, reine Funktionen), `ablage.py` (Listen der Ordner, Kopieren nach Eingang), `ui_app.py` (Fenster, Api, Lauf-Thread; Einstieg der .exe), `ui/web/` (HTML/CSS/JS, offline, im Build per `--add-data`), `schriften/` (STIX/DejaVu, im Build per `--add-data`), `tests/`, `werkzeuge/`, `docs/` (Plan, `einstellungen.md`, `claude/` = Wissen je Modul), `.claude/` (Skills und Schutz-Hook im Repo, alles andere lokal), `build.ps1`.
- Testmaterial: 56 Normen in einem lokalen Ordner (Pfad in `CLAUDE.local.md`, für `werkzeuge/normen_lauf.py` per Umgebungsvariable `NORMEN`; nur lesen, nie verschieben: `verarbeiten()` verschiebt das Original! Zum Testen `umwandeln()`/`metadaten_lesen()` direkt aufrufen bzw. `werkzeuge/normen_lauf.py`). Doppelte/aeltere Ausgaben liegen auf Wunsch des Nutzers in `Normen\Duplikate\` (LIESMICH.txt); Entwuerfe und gueltige Ausgabe bleiben beide im Hauptordner, Berichtigungen bei ihrer Norm.
- Ordner neben der `.exe` bzw. dem Skript: `Eingang` -> `Fertig` oder `Prüfen`, dazu `Sicherung/`, `Protokoll.csv` und `Einstellungen.json`. Stati im Protokoll: OK, PRÜFEN, NACHGEBESSERT, UMBENANNT, RÜCKGÄNGIG, TEXT_ERNEUERT.

## Verbindliche Regeln (vom Nutzer)

- KEIN OCR/Scan-Support und KEINE Claude-Vision-Variante für Formeln.
- `dist\` (Fertig, Prüfen, Sicherung, Protokoll.csv, Eingang) enthält Nutzerdaten: nie verändern, nur lesend prüfen.
- Datenschutz (öffentliches Repo, essenziell): nichts Persönliches einchecken – keine Pfade mit Benutzernamen, keine echten Kunden-/Abonummern, Lizenzkennungen oder Ausdruckszeitpunkte aus Normen, kein Buch-/Normtext und keine Titel, Autoren, ISBN/DOI oder Normnummern der eigenen Bücher und Normen. Tests und Kommentare nutzen erfundene Werte (Nummern wie 12345, Titel wie „Beispielelemente“); was dahinter steht, nur in `CLAUDE.local.md`. Commits nur mit der GitHub-noreply-Adresse; die alte private Historie darf nie veröffentlicht werden.
- Das große Handbuch-PDF (160 MB, Name in `CLAUDE.local.md`) bei Läufen und Tests ausnehmen.
- `.exe` nicht neu bauen, solange `pdf2md.exe`-Prozesse laufen.
- Nur lokal committen, der Nutzer pusht selbst. Trailer: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Antworten und Kommentare auf Deutsch.
- Bedienung nur über das Fenster; keine Kommandozeilen-Flags und kein Ziehen auf die .exe wieder einführen.
- Oberfläche (Nutzervorgaben gegen „AI-Slop“): keine Verläufe, kein Glas-Effekt, keine Emoji-Icons, kein Lila-Blau, keine Karten in Karten, keine Hero-Fläche, keine erfundenen Beispielzahlen (leere Zustände sagen „Noch keine Daten“). Segoe UI Variable, eine Akzentfarbe (Petrol), 4/8-px-Raster, 1-px-Linien, `tabular-nums`, kompakt. Kein CDN, kein npm.

## Offene Aufgaben

- **Chromium-Lizenzen als Volltext (vor dem finalen Release, nach Schritt 3 = Test auf echten Geräten; Nutzerentscheidung 2026-10-08):** Im Linux-Paket steckt Chromium (Qt WebEngine). `DRITTLIZENZEN.txt` nennt dafür bisher nur die Qt-Seite (`drittlizenzen.einleitung()`); BSD/MIT/Apache verlangen bei Weitergabe als Programm aber den beiliegenden Text. Vorgehen: zuerst prüfen, ob die PySide6-Wheels die Texte doch mitbringen (`drittlizenzen.LIZENZDATEI` erkennt nur Dateinamen mit LICENSE/COPYING/NOTICE, keine Ordner wie `LICENSES/` oder Attributionsdateien); sonst im Release-Build aus den Qt-WebEngine-Quellen genau der verwendeten Version erzeugen (Chromiums `tools/licenses`). Erledigt, wenn der Paketbericht `chromium_volltext: true` zeigt; bis dahin warnt jeder Release-Lauf (`bauen.hinweise`, `CHROMIUM_AUFGABE`), README nennt es unter Release.

## Bekannte Grenzen (nicht als Fähigkeit annehmen)

- Markdown-Tabellen nur bei gezeichneten Gitterlinien (Tabellen aus reinem Leerraum und reine Linien-Tabellen ohne senkrechte Striche bleiben Text); Formelstruktur nur teilweise (Indizes, Brueche, Wurzeln, Operatorgrenzen; keine Matrizen/grossen Klammern); rund 60.000 `�` bleiben.
- Bilder fehlen. Lesereihenfolge nur bei zwei Spalten korrigiert (siehe lesefolge.py); Fußnoten sind nicht geprüft.
- Überschriften aus Lesezeichen; ohne Lesezeichen aus der Schriftgröße (ungenauer, siehe `docs/claude/schriftbild.md`). Das 160-MB-Handbuch wurde nie getestet.
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

## Wissen je Modul und Abläufe

Gemessene Werte, Entscheidungen und Fallen je Modul stehen in `docs/claude/`. Vor einer Änderung am Modul die passende Datei lesen; neue Messungen und Fallen dort eintragen, nicht hier.

| Modul | Datei |
|---|---|
| Textweg in `pdf2md.py`: Bereinigung, Kopf-/Fußzeilen, Lesezeichen, zweiter Durchgang | `docs/claude/pdf-text.md` |
| `lesefolge.py` | `docs/claude/lesefolge.md` |
| `zeichen.py` | `docs/claude/zeichen.md` |
| `normen.py` | `docs/claude/normen.md` |
| `tabellen.py` | `docs/claude/tabellen.md` |
| `seitenzahlen.py`, `zitierdaten.py` | `docs/claude/seitenzahlen-zitieren.md` |
| `formelsatz.py`, `formeln.py` | `docs/claude/formeln.md` |
| `schriftbild.py` | `docs/claude/schriftbild.md` |
| `werkzeuge/haertetest.py`, Grenzfälle der Eingabe | `docs/claude/haertetest.md` |

- Neue einstellbare Konstante (Zahl oder Schalter) in einem Modul: in `einstellungen.EINSTELLUNGEN` eintragen; ein Test prüft Standard = Code und dass keine Einstellung beim Import kopiert wird (keine Default-Argumente, kein `from x import`).
- Abläufe als Projekt-Skills in `.claude/skills/`: `echte-daten-pruefen` (Regression an echten Büchern und Normen), `fenster-entwickeln` (Oberfläche, Api, Einstellungen, Auswertung), `pakete-bauen` (exe, App, Linux-Ordner, Lizenzen, Workflows), `veroeffentlichen` (Datenschutzprüfung, Release, CI lesen).
- `.claude/hooks/schutz.py` sperrt Schreiben in `dist\` und `git push` (eingetragen in der lokalen `.claude/settings.local.json`, Tests in `tests/test_schutz_hook.py`).

## Tests

- `tests/` (pytest, rund 730 Tests, brauchen keine echten Bücher, alle Testdateien werden selbst erzeugt; `test_formelsatz.py` baut Zeichen als `formelsatz.Teil` nach, `test_zitierdaten.py` bildet Crossref/DNB nach). Abhängigkeiten: `requirements-dev.txt`. `test_zeichen.py` ersetzt PDFium durch eine nachgebaute Textseite (`RawNachbau`), so lassen sich erzeugte Leerzeichen, Schriften und Zeichenrahmen gezielt setzen.
- Regression an echten Daten: Skill `echte-daten-pruefen`.
- Die Fixture `arbeitsordner` (conftest.py) leitet EINGANG/FERTIG/PRUEFEN/PROTOKOLL/SICHERUNG in ein tmp-Verzeichnis um und schaltet Crossref und Formelreparatur aus (deshalb steht dort im Kopfblock `einstellungen: "abweichend: …"`). `tests/test_ui_app.py` prüft die Api ohne Fenster (eigene Fixture mit `Einstellungen.json`). Die autouse-Fixture `keine_echte_ablage` leitet die Pfade in jedem Test zuerst nach tmp um (früher lagen Testreste `Prüfen/quelle (2).pdf` und eine `Protokoll.csv` im Projektordner). Tests mit Formelreparatur sind mit `langsam` markiert.
- Bei jedem behobenen Fehler einen Regressionstest ergänzen (Beispiele: `ArialMT2` darf nicht als MathTime gelten, UTF-16-Hälften dürfen den Text nicht unspeicherbar machen).
- Ein Mutationstest (absichtlich eingebaute Fehler im Speicher) hat 10 von 10 Fehlern erkannt.
