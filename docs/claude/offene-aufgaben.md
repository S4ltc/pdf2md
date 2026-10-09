# Offene Aufgaben: Grundlagen und Pläne

Zu den Einträgen unter „Offene Aufgaben“ in CLAUDE.md (außer Chromium-Lizenzen, die steht dort vollständig). Stand 2026-10-10: nur gelesen und geplant, nichts umgesetzt. Zeilennummern können inzwischen gewandert sein.

Beim Umsetzen gilt:
- Entscheidungen des Nutzers sind verbindlich.
- Alles unter „Empfehlung“ oder „Plan“ stammt von Claude und ist vor Beginn mit dem Nutzer zu bestätigen.
- Erledigte Aufgaben hier und in CLAUDE.md streichen. Bleibendes Wissen kommt in die passende Datei unter `docs/claude/`.

## Ordner für Eingang und Fertig frei wählen

**Entscheidungen des Nutzers (2026-10-10):**
- Für Eingang wie für Fertig lässt sich ein beliebiger Ordner wählen, der als aktueller Eingang bzw. Fertig dient.
- Die Standardordner neben der exe bleiben bestehen. Man wechselt jederzeit nahtlos zurück auf den Standardordner.

**Empfehlung (vor Beginn bestätigen):**
- Ein gewählter Eingang verhält sich wie der heutige: Starten verschiebt nach Fertig bzw. Prüfen. So verstanden aus „dient als aktueller Eingang“; der Nutzer hat es nicht ausdrücklich gesagt. Enthält ein neu gewählter Eingang schon Dateien, fragt das Fenster mit deren Anzahl nach.
- Der gewählte Pfad bleibt gemerkt, auch während der Standardordner aktiv ist. So schaltet man ohne neuen Dialog wieder auf ihn um.
- Prüfen, Sicherung, `Protokoll.csv` und `Einstellungen.json` bleiben in der Programm-Ablage (`basis`). So enthält Fertig nur fertige Paare, und die KI-Weiterverarbeitung liest keine Entwürfe oder Sicherungen mit.
- Beim Wechsel von Fertig bleiben die vorhandenen Bücher am alten Ort; die Rückfrage nennt ihn. Ein Werkzeug zum Mitnehmen lässt sich später ergänzen.
- Gewählte Ordner werden nie selbst angelegt. Fehlt einer (Laufwerk getrennt, anderer USB-Stick unter demselben Buchstaben), sperrt das Fenster Starten und die Werkzeuge mit klarer Meldung.

**Befunde:**
- **Ablagevariablen:** Die Ablage besteht aus fünf Modulvariablen (`pdf2md.EINGANG/FERTIG/PRUEFEN/SICHERUNG/PROTOKOLL`), die `ui_app.ablage_setzen(basis)` alle relativ zu `basis` setzt. Alle Leser fragen sie erst zur Laufzeit ab, das Umsetzen der Variablen reicht also technisch. `basis` ist `PDF2MD_ABLAGE` oder `plattform.ablage_basis()`; die Einzelinstanz-Sperre hängt an `basis`.
- **Speicherort der Wahl:** `einstellungen.speichern()` schreibt nur bekannte Abweichungen, ein fremder Schlüssel in `Einstellungen.json` ginge beim nächsten Speichern verloren. `abweichungstext()` schreibt jede Abweichung in den Kopfblock jeder neuen .md, ein Pfad mit Benutzernamen stünde dann in jeder Ausgabe. Die Wahl gehört deshalb nicht in `EINSTELLUNGEN`.
- **Rückgängig:** `Protokoll.csv` speichert absolute Pfade. Rückgängig bringt Dateien früherer Läufe auch nach einem Wechsel an die alten Orte zurück und legt einen fehlenden alten Eingang dabei neu an (`mkdir(parents=True)`).
- **Namen reparieren:** Der Plan enthält absolute Pfade, nimmt das Ziel aber aus dem aktuellen `FERTIG`. Ein Plan von vor einem Wechsel würde auf demselben Laufwerk vom alten in den neuen Fertig verschieben. Auf einem anderen Laufwerk scheitert `Path.rename` ohne Folgen.
- **Text erneuern:** schreibt die .md an ihrem alten Ort neu; nur die Spalte `ordner` im Protokoll nennt dann den neuen Fertig.
- **Verschieben über Laufwerke:** `shutil.move` steht in vier Aufrufen in drei Funktionen: `_verarbeiten`, `nachbessern` und zweimal `rueckgaengig` (Original und .md). Über Laufwerksgrenzen kopiert es und löscht dann das Original. Ist das Original gesperrt (im PDF-Leser offen), bleibt eine Kopie ohne .md in Fertig, und der nächste Lauf erzeugt ein Duplikat „(2)“. Dasselbe Symptom hatte der im Härtetest behobene Fehler, dort blieb aber eine verwaiste .md.
- **Literatur.bib:** wird nach `FERTIG.parent` geschrieben, der Hinweis sagt aber „neben das Programm“. Bei einem gewählten Fertig landet die Datei im übergeordneten Ordner, bei `D:\` in der Laufwerkswurzel.
- **Pfadlänge (`name_laenge`):** Ab etwa 129 Zeichen Ordnerpfad werden Namen gekürzt. Ab etwa 209 scheitert das Verschieben unter Windows ohne Freigabe langer Pfade.
- **Fehlende Ordner:** werden heute still angelegt (Eingang, Ziel, Ordner öffnen).
- **Signatur:** Sie kommt alle 1,5 s, während eines Laufs alle 0,4 s, und liest alle drei Ordner mit `iterdir` plus `stat` je Datei, dazu `Protokoll.csv`. Auf einem Netzlaufwerk ist das ein Netzaufruf pro Datei; mit `os.scandir` käme `stat` unter Windows aus der Verzeichnisliste.
- **Ordnerdialog:** pywebview 6.2 bietet `webview.FileDialog.FOLDER` auf allen drei Systemen (`FOLDER_DIALOG` ist veraltet). Rückgabe ist ein Tupel oder None. Das Aufrufmuster ist dasselbe wie bei `hinzufuegen_dialog`.
- **Vorschau-Server:** `werkzeuge/ui_vorschau.py` macht jede öffentliche Api-Methode per POST aufrufbar. `hinzufuegen(pfade)` nimmt schon heute Quellpfade an, die nach Eingang kopiert werden. Eine neue Methode, die einen Zielordner aus der Oberfläche annähme, wäre dort von jeder lokalen Seite aus aufrufbar. Deshalb läuft der Dialog nur in Python.

**Plan:**
1. Eigene `Ordner.json` in `basis` mit je Rolle Pfad und ob er aktiv ist. Pfade innerhalb von `basis` werden relativ gespeichert, damit der Ordner mit der exe verschiebbar bleibt. Schreiben wie `einstellungen.speichern` (Hilfsdatei, dann `os.replace`). In `.gitignore` und in `_DATEN` von `.claude/hooks/schutz.py` eintragen, mit Test.
2. Reine Funktionen in `ablage.py` (laden, speichern, prüfen). Geprüft wird: existiert, beschreib- und löschbar (Probedatei), nicht derselbe Ordner wie eine andere Rolle oder Prüfen/Sicherung, Pfadlänge.
3. `pdf2md.verschieben(quelle, ziel)` ersetzt die vier `shutil.move`. Zuerst `os.rename`. Bei anderem Laufwerk kopieren und dann löschen; scheitert eines davon, wird die Kopie entfernt und das Original bleibt. Dazu `SICHERUNG.mkdir(parents=True)` und eine neue Variable `pdf2md.ABLAGE` für `Literatur.bib` und `Ordner.json`.
4. Api `ordner_waehlen(bereich)` (Dialog nur in Python, nie ein Zielpfad aus JavaScript) und eine Methode zum Umschalten Standard/gewählt. Beide sind während eines Laufs gesperrt und verwerfen die Werkzeugpläne. `stand()` liefert je Rolle Pfad, ob Standard und ob erreichbar.
5. Oberfläche: Abschnitt „Ordner“ oben auf der Einstellungsseite mit Pfad, „Ordner ändern …“ und Umschalter je Rolle. Rückfragen siehe Empfehlung. In der Übersicht steht „Ordner nicht erreichbar“ statt eines leeren Zustands. Prüfmaßstab nach Skill `fenster-entwickeln`.
6. `ui_vorschau.py` und `PDF2MD_ABLAGE` ignorieren Ziele aus `Ordner.json` außerhalb der Ablage-Kopie. Sonst verschiebt eine aus `dist` kopierte Ablage echte Daten, ohne dass der Schutz-Hook es merkt, denn er erkennt `dist` nur am Pfadtext.
7. Tests:
   - getrennte „Laufwerke“ über nachgebildetes `os.rename` → `OSError(EXDEV)` und ein gesperrtes Original;
   - Rückgängig nach einem Wechsel; fehlender Ordner; verworfene Pläne;
   - die conftest-Fixtures (`keine_echte_ablage`, `arbeitsordner`) und `test_tests_nutzen_nie_die_echte_ablage` um die neue Variable ergänzen.

**Fallen:**
- OneDrive als Eingang: Verschieben entfernt die Datei auch aus der Cloud. Reine Online-Platzhalter werden beim Lesen geladen.
- OneDrive als Fertig: kurze Sperren durch die Synchronisation und Konfliktkopien zweier PCs.
- Fremde `.md` im gewählten Fertig zählen als Bücher.
- macOS fragt beim Zugriff auf Schreibtisch, Downloads oder externe Laufwerke nach (TCC). Bei einer unsignierten App womöglich nach jedem Update erneut; ungeprüft.
- Die Auswertung zeigt Läufe von vor einem Fertig-Wechsel ohne Seiten und Tempo.

**Aufwand:** etwa 1 bis 1,5 Tage, dazu ein Handtest des Dialogs unter Windows (macOS/Linux nur über CI).

## Modus Schnell / Gründlich

**Entscheidungen des Nutzers (2026-10-10):**
- „Gründlich“ ist der heutige Standard; es gibt zwei Stufen.
- „Schnell“ schaltet nur die teuren Schritte ab: Formelsatz, Formelreparatur und Fett/kursiv (Hervorhebungen).
- Lesereihenfolge, Zeichenkorrektur und Tabellen bleiben an.

**Befunde (gemessen, Quellen in README und `docs/claude/`):**
- Formelsatz: etwa 20 ms je Seite, Bücher insgesamt etwa doppelte Laufzeit.
- Formelreparatur: im Schnitt etwa 11 s je Buch, bei 1500 bis 2000 Seiten bis eine Minute. Nutzen über 58 Bücher: unlesbare Zeichen −52 %, rund 442.000 korrigierte Zeichen.
- Hervorhebungen und Überschriften aus der Schrift: zusammen etwa +13 %. Wie sich das aufteilt, ist nicht gemessen.
- Spaltenreihenfolge: 5 bis 15 ms je Seite. Tabellen und Zeichenkorrektur: Laufzeit nicht gemessen.
- Kein Modus macht DOCX, PPTX, XLSX, EPUB, HTML oder den MarkItDown-Weg schneller.
- Online-Abgleich: Die Entscheidung nennt ihn nicht. Empfehlung: an lassen. Er steht nicht in `textquelle`, ein Ausschalten ließe sich also später nicht über „Text erneuern“ nachholen.

**Plan:**
1. Wahl-Einstellung, etwa `pdf2md.TEMPO` (`gruendlich` = Standard, `schnell`), in `EINSTELLUNGEN`, Stufe normal. Nicht `MODUS` nennen, das ist in `ui/web/app.js` vergeben.
2. Schnell wirkt als Maske über `formeln_aktiv()`, `formelsatz_aktiv()` und eine neue `hervorhebungen_aktiv()`; die Einzelschalter behalten den Wert des Nutzers. Stellen, die `HERVORHEBUNGEN`/`UEBERSCHRIFTEN_AUS_SCHRIFT` direkt lesen, auf die Funktionen umstellen, mit Verhaltenstest. Im Kopfblock steht dann `einstellungen: "abweichend: TEMPO=schnell"`.
3. Schnell darf nur Verfahren abschalten, die in `textquelle` stehen, damit „Text erneuern“ schnell erzeugte Bücher später findet.
4. **Text erneuern (Vorschlag, vor Beginn bestätigen):**
   - Heute vergleicht `text_plan()` die `textquelle` auf Gleichheit. Im Modus Schnell würden damit alle gründlich erzeugten Bücher herabgestuft.
   - Vorschlag: Ein Buch gilt als aktuell, wenn es mindestens die Verfahren des eingestellten Modus enthält und höchstens die gründlichen; es wird also nie herabgestuft.
   - Gründlich nachholen: auf Gründlich schalten und „Text erneuern“ ausführen.
   - Dieselbe Regel gilt für `auswertung.buchkennzahlen()["aktuell"]` und den Schlüssel des Kennzahlen-Zwischenspeichers.
5. Schriftzeilen nur lesen, wenn Hervorhebungen aktiv sind oder das PDF keine Lesezeichen hat. Dafür die Lesezeichen vor dem ersten Durchgang lesen. Das nützt beiden Modi.
6. Oberfläche:
   - Auswahl „Schnell | Gründlich“ oben auf der Einstellungsseite.
   - Die maskierten Schalter sind deaktiviert und zeigen „im Modus Schnell aus“.
   - Solange Schnell gilt, steht ein Hinweis neben „Starten“.
7. Messen (Skill `echte-daten-pruefen`): Die Messskripte können den Arbeitsprozessen bisher keine Einstellungen mitgeben, das muss zuerst ergänzt werden. Sie laufen außerdem 10- bis 12-fach parallel, was die Zeiten je Buch verfälscht.

**Fallen:**
- **Umlautergänzung:** Ohne Formelreparatur fällt auch `umlaute_ergaenzen()` weg. Beim Buch mit defekter Kodierung hob sie den Anteil richtig geschriebener Umlautwörter (geprüfte Stichprobe) von etwa 7 % auf 90 %. Prüfen, ob die Kopplung nötig ist, sonst entkoppeln.
- **Schriftzeilen:** `HERVORHEBUNGEN` allein auszuschalten spart sie nicht, solange `UEBERSCHRIFTEN_AUS_SCHRIFT` an ist.
- **Durchsatzdiagramm:** Es mischt beide Modi.

**Aufwand:** etwa 3,5 bis 4 Tage samt Messung.

Nicht Teil dieser Aufgabe: mehrere Bücher gleichzeitig umwandeln. Das wäre der größte Zeitgewinn in beiden Modi, betrifft aber Protokoll und Namenskonflikte (etwa 2 bis 3 Tage).

## Qualitäts-Score je Buch in der Auswertung

**Wunsch des Nutzers (2026-10-09):** Jedes Buch bekommt in der Auswertung einen Score bis 100 nach der erreichten Qualität. Ein Hover schlüsselt die Punkte nach sinnvollen Kategorien auf.

**Empfehlung (vor Beginn bestätigen, danach an echten Daten kalibrieren):**

| Kategorie | Punkte | Grundlage |
|---|---|---|
| Zeichen lesbar | 30 | `�` außerhalb der als unsicher markierten Formelzeilen und verdoppelte Mathezeichen, je 10.000 Zeichen; bei defekter Kodierung höchstens 10 |
| Gliederung | 15 | Lesezeichen (Anteil direkt im Text); Überschriften aus der Schrift nur Teilpunkte (gemessene Genauigkeit 62–72 %) |
| Seitenzahlen | 15 | Anteil Seiten mit gedruckter Zahl (nur neue Marker) |
| Metadaten und Quellenangabe | 15 | Titel, Autor, Jahr je 3; vollständige Quellenangabe 6 |
| Formeln | 15 | Anteil sicherer Formelzeilen |
| Tabellen | 10 | Tabellen je Tabellentitel; im Hover die Grenze „Tabellen ohne Gitterlinien bleiben Text“ nennen |

- **Fehlende Kategorien:** Was es bei einem Buch nicht gibt (keine Formeln, keine Tabellen, Office-Formate ohne Seiten), zählt nicht. Score = erreichte durch mögliche Punkte × 100. Die Aufschlüsselung zeigt die umgerechneten Höchstpunkte, damit die Zeilen genau den Score ergeben (Rundung nach größten Resten).
- **Nicht erfasst:** Das Verfahren lief nicht, etwa bei älteren .md. Das gibt weder 0 noch volle Punkte, der Score heißt dann „vorläufig“.
- **Kein Score:** Scans und Bücher mit weniger als 50 bewertbaren Punkten bekommen „–“ mit Grund.
- **Korrekturen:** Sie geben keine Punkte, erscheinen aber als Zeilen: Spalten umsortiert, Doppeldruck entfernt, Zeichen korrigiert, Formelzeichen repariert, Umlaute ergänzt, Hervorhebungen.
- **Ebenfalls zu bestätigen:** ob Metadaten überhaupt zählen (Empfehlung ja), und ob die neue Tabelle „Qualität je Buch“ (alle Bücher, aufsteigend nach Score) die Top-10-Tabelle „Bücher mit den meisten offenen Stellen“ ersetzt (Empfehlung ja).

**Befunde:**
- **Kennzahlen:** Je Buch liegen viele schon vor (`auswertung.buchkennzahlen`). Es fehlen die Textlänge (für Dichten) und die Kopfblock-Felder `ueberschriften` (aus der Schrift), `hervorhebungen`, `zeichenkorrektur` und `warnung`.
- **Namenskollision:** Die Kennzahl `ueberschriften` stammt aus dem Kopfblock-Feld `lesezeichen`. Das Kopfblock-Feld `ueberschriften` meint dagegen die Überschriften aus der Schrift.
- **Unsichere Formeln:** `⚠[Formel unsicher]` entsteht durch `�` in Formelzeilen oder durch einen unsicheren Formelteil (Zähler, Nenner oder Radikand über mehrere Zeilen). Die Zeichen-Kategorie darf die `�` dieser Zeilen nicht noch einmal zählen.
- **Quellenangabe:** Ob ein Dokument eine ISBN oder DOI hat, steht nicht verlässlich im Kopfblock. „Online aus“, „keine Kennung“ und „Abfrage gescheitert“ sehen gleich aus. Bei Office-Formaten den Teil Quellenangabe weglassen, oder in `zitierdaten_quelle` künftig unterscheiden.
- **Tooltip:** Es übernimmt nur `textContent` (`app.js`), hat `pointer-events: none`, und jeder Klick verbirgt es. Auf Touch erscheint es praktisch nie, im Kontrastmodus fehlt ein Rand. Hover allein reicht deshalb nicht.
- **Neuaufbau:** Die Auswertung baut bei jeder Signaturänderung neu auf, ohne den Fokus zu erhalten. `listeErneuern()` hat als Ausweichziel `.spalte h2`, das es nur in der Übersicht gibt.
- **Vorhandener Fehler (nebenbei beheben):** `buchkennzahlen()["aktuell"]` vergleicht `textquelle` mit der PDF-Textquelle. DOCX, EPUB und andere Nicht-PDFs zählen deshalb im Hinweis der Auswertung als „mit einem älteren Verfahren erzeugt“, obwohl „Text erneuern“ sie gar nicht verarbeitet.

**Plan:**
1. `auswertung.py`: neue Felder in `buchkennzahlen`, die Konstante `WERTUNG` (fest, keine Einstellung, wie `QUALITAET`) und eine reine Funktion `buchwertung()`. Sie gibt Score, „vorläufig“, Kategorien und Korrekturen zurück. Die Kennzahlen bleiben picklebar, denn sie entstehen auch in Unterprozessen.
2. `Api.auswertung()` liefert `wertung` je .md in Fertig und Prüfen. Schlüssel ist Bereich plus Name, weil derselbe Name in beiden Ordnern vorkommen kann.
3. Oberfläche:
   - Tabelle „Qualität je Buch“ mit Filter und sortierbaren Spalten (`aria-sort`).
   - Score als `<button>` mit Zahl (`tabular-nums`) und schmaler Petrol-Spur, keine Ampelfarben.
   - Hover oder Fokus zeigt die Aufschlüsselung (Tooltip auf strukturierten Inhalt erweitern, kein `innerHTML` aus Daten).
   - Klick, Enter oder Leertaste klappen dieselbe Aufschlüsselung als Detailzeile auf, für Tastatur, Touch und Screenreader; Esc schließt beides.
   - Offene Detailzeilen und der Fokus überstehen den Neuaufbau.
4. Im Hinweis der Auswertung steht: Ein Score von 100 heißt nicht fehlerfrei. Bilder, Fußnoten und Tabellen aus Leerraum misst pdf2md nicht.
5. Kalibrieren an Büchern und Normen (Skill `echte-daten-pruefen`, Ausgaben nur im Scratchpad), Messwerte ohne Titel nach `docs/claude/`.
6. Prüfen: Sichtprüfung nach Skill `fenster-entwickeln`. Dazu ein Lasttest mit rund 640 erzeugten .md in Fertig (wie die Messung in `docs/claude/haertetest.md`; ein Skript dafür gibt es noch nicht, `werkzeuge/haertetest.py` erzeugt nur Grenzfälle). Geprüft werden Größe der Antwort und Neuaufbau.

**Aufwand:** etwa 1,5 bis 2 Tage.

## Issues und Pull Requests täglich vorprüfen

**Entscheidungen des Nutzers:**
- Umsetzen erst zum Projektende (2026-10-09). Auch Ausschlussliste und Issue-Vorlagen nicht vorziehen, außer der Nutzer wünscht es ausdrücklich.
- Ergebnis ist nur ein privater Bericht (2026-10-10). Der Nutzer entscheidet und postet selbst. Auf GitHub schreibt nichts automatisch: kein Kommentar, kein Label, kein Schließen, kein Push.
- Eine Ausschlussliste (was gegen die Grundsätze des Tools verstößt, z. B. OCR) und ein Schutz gegen Böswilligkeit wie Prompt-Injection gehören zur Aufgabe (2026-10-10). Wie beides aussieht, ist unten Empfehlung bzw. Entwurf.

**Empfohlener Ablauf (vor Beginn bestätigen):**
1. **Ort:**
   - Lokal als geplante Aufgabe in Claude Code Desktop, in einem eigenen Ordner außerhalb von Repo und OneDrive, etwa `%LOCALAPPDATA%\pdf2md-triage`. Der PC muss dafür laufen; verpasste Tage holt der nächste Lauf nach.
   - Nicht im Repo-Ordner: Dort lädt Claude Code `CLAUDE.local.md` (echte Titel, Pfade) und das Projektgedächtnis, und Remote und Zweig der privaten Historie sowie `dist\` liegen in Reichweite.
   - Eine Cloud-Routine nur, wenn der PC oft aus ist: Ihr GitHub-Zugang hat in der Regel Schreibrechte, und lokale Hooks fehlen dort.
   - Von einer GitHub Action abraten: Der Schlüssel läge als Secret neben fremden Texten, und die Logs eines öffentlichen Repos kann jeder angemeldete GitHub-Nutzer lesen.
2. **Abruf:** Ein deterministisches Skript `werkzeuge/triage_abruf.py`, ohne KI.
   - Es holt die seit dem letzten Stand neuen oder geänderten Issues und PRs samt Dateiliste, Diff und CI-Status.
   - Ausschließlich GET an `api.github.com` (urllib wie in `aktualisierung.py`); Weiterleitungen auf andere Hosts werden nicht verfolgt.
   - Der Token steht in einer eigenen Umgebungsvariable und gelangt nie in Claudes Kontext.
   - Es legt außerdem per `git archive main` einen Stand im Triage-Ordner ab, ohne `.git`, `CLAUDE.local.md` und `dist`.
   - Gibt es nichts Neues, endet der Lauf sofort.
3. **Bereinigung durch das Skript:**
   - Unsichtbare und steuernde Zeichen werden als `⟦U+XXXX⟧` sichtbar: Zero-Width, Bidi/Trojan Source, Tag-Zeichen, Variantenwähler, weiches Trennzeichen, BOM, Steuerzeichen, privater Bereich. Bekannte Zeichen im eigenen Code (`SPALTENBRUCH`, U+FFFE, U+00AD) sind als bekannt gekennzeichnet, nicht als Angriff.
   - HTML-Kommentare und `<details>` bleiben sichtbar. Links erscheinen als Text, Linktext und Ziel getrennt. Bilder und Anhänge erscheinen nur als Metadaten und werden nie geladen.
   - Längen sind begrenzt.
4. **Markierungen durch das Skript:**
   - Injection-Muster (deutsch und englisch) und Treffer auf die Ausschlussliste.
   - Heikle Pfade im Diff:
     - `CLAUDE.md`, `.claude/**` und `docs/claude/**`: Das sind Anweisungen an künftige Sitzungen, eine Änderung dort wäre also eine dauerhafte Injection.
     - `.github/**`, `requirements*.txt`, `build.ps1`, `werkzeuge/bauen.py` und `werkzeuge/drittlizenzen.py`: Lieferkette und Release.
     - `aktualisierung.py`: Update-Adresse.
     - `ui/web/**` und `plattform.py`: Die Sandbox unter Linux ist nur aus, weil nur lokale Dateien geladen werden.
     - `ui_app.py`, `tests/conftest.py`, `LICENSE` und Binärdateien.
5. **Auswertung durch Claude:** Ein Skill `issues-pruefen` liest nur den bereinigten Eingang und den vom Abrufskript abgelegten Stand. Je Eintrag schreibt er:
   - Einordnung (Fehler, Wunsch, Frage, Beitrag, Spam, verdächtig) und Abgleich mit der Ausschlussliste mit Kennung und Beleg.
   - Betroffene Module laut Tabelle in CLAUDE.md.
   - Lösungsansatz mit Tests, und ob eine Messung an echten Daten durch den Nutzer nötig ist.
   - Antwortentwurf auf Deutsch. Bei fremdsprachigen Einträgen zusätzlich in deren Sprache, falls der Nutzer das bestätigt (Regel „Antworten und Kommentare auf Deutsch“).

   Fremdtext steht nur als gekennzeichneter, gekürzter Codeblock im Bericht. Ganz oben stehen „Verdächtig“ und „Änderungen an heiklen Pfaden“, am Ende „Ausgeführt wurde nichts“.
6. **Absicherung unabhängig vom Modell:**
   - Eigene Settings im Triage-Ordner.
   - Ein Hook im Triage-Modus mit Matcher `*`, fail-closed. Anders als `schutz.py`, das bei eigenen Fehlern durchlässt und MCP-Werkzeuge nicht prüft.
   - Erlaubt sind nur Lesen im Triage-Ordner, Schreiben nach `berichte/` und genau der Aufruf des Abrufskripts.
   - Gesperrt sind WebFetch/WebSearch, alle MCP-Server (GitHub, Browser, Claude in Chrome mit angemeldeter GitHub-Sitzung, Terminal, Sitzungsverwaltung, Konnektoren) und alle anderen Shell-Befehle. Mit Tests.
7. **Token und Repo (macht der Nutzer):**
   - Feingranularer Token nur für das öffentliche Repo, nicht für das private, nur lesend.
   - Freigabe von Workflows externer Beitragender verlangen (`tests.yml` läuft bei `pull_request`).
   - Keine `pull_request_target`-Workflows und kein `${{ github.event.* }}`-Text in `run:`-Skripten.
8. **Tests mit erfundenen Angriffs-Issues:** Tag-Zeichen, Bidi-Dateiname, versteckter HTML-Kommentar, Link mit falschem Linktext, Anweisung an „Claude“. Ein nachgebildetes urllib prüft „nur GET, nur api.github.com“.

**Grenzen:**
- Prompt-Injection lässt sich nicht zuverlässig erkennen. Der eigentliche Schutz ist, dass nichts Missbrauchbares in Reichweite ist: keine Schreibrechte, kein Netz, keine Secrets, nichts Privates. Die Muster sind nur Hinweise.
- Schwellen-PRs kann nur der Nutzer prüfen, weil nur er die Bestände hat.
- Ein Merge im GitHub-Webinterface umgeht den Skill `veroeffentlichen`. Danach den lokalen `main` von `origin` nachziehen, nie aus dem privaten Remote.

**Ausschlussliste (Entwurf für `docs/ausschluss.md`):** Jeder Eintrag bekommt Kennung, Quelle und Antwortbaustein; ein Test prüft, dass die Quellen existieren.

- **A, Grundsatzverstoß (ablehnen mit Begründung):**
  - A1 OCR/Scan-Support, auch über Fremdwerkzeuge oder Texterkennungs- und Layoutmodelle. MinerU hat der Nutzer beim Vergleich mit anderen Konvertern ausgeschlossen („widerspricht meinem Grundsatz“); welcher Grundsatz gemeint ist, ist nicht festgehalten. Die Einordnung unter A1 ist vorläufig, beim Anlegen bestätigen.
  - A2 Claude-Vision oder andere Bilderkennung für Formeln.
  - A3 Cloud- oder Online-Umwandlung. Online gehen nur DOI/ISBN an Crossref/DNB und die Release-Abfrage.
  - A4 Telemetrie, Anmeldung, Absturzberichte.
  - A5 Kontaktangaben im User-Agent oder eine E-Mail für Crossref.
  - A6 Auto-Updater. Die Update-Suche zeigt nur einen Hinweis.
  - A7 Kommandozeilen-Schalter für das Programm, Ziehen auf die exe.
  - A8 Verstöße gegen die Oberflächenregeln.
  - A9 CDN, npm oder Inhalte aus dem Netz im Fenster.
  - A10 GPL/AGPL-Bestandteile; PyQt6 statt PySide6; ein Linux-Paket als eine Datei statt Ordner.
  - A11 Persönliche Daten, echte Titel oder Buch-/Normtext im Repo; echte PDFs als Testdaten.
  - A12 Lizenzvermerke gekaufter Normen behalten.
  - A13 Eigene Builds als Release.
  - A14 Erstellungsdatum standardmäßig als Erscheinungsjahr. Als Schalter „Jahr aus Erstellungsdatum“ (Standard aus) gibt es das bereits.
  - A15 „Namen reparieren“ automatisch; Rückgängig, das löscht; Dateibewegung ohne Protokollzeile.
  - A16 Ziel- oder Ablagepfade aus der Oberfläche. Quellen zum Kopieren nach Eingang über `hinzufuegen` bzw. Ablegen sind die bestehende Ausnahme.
  - A17 `pull_request_target` oder Automatik mit Schreibrechten.
- **B, Beitragsregel (annehmbar nach Nacharbeit):**
  - B1 Gemessene Schwellen nur mit neuer Messung an beiden Beständen.
  - B2 PDFium bleibt Standard.
  - B3 Neue Konstanten in `EINSTELLUNGEN`.
  - B4 Regressionstest je behobenem Fehler.
  - B5 Deutsch.
  - B6 Systemabhängiges nach `plattform.py`.
  - B7 .md mit LF.
- **C, bekannte Grenze (Wunsch zulässig, kein Ausschluss):** Tabellen ohne Gitterlinien, Matrizen und große Klammern, Bilder, mehr als zwei Spalten, Fußnoten, Überschriften ohne Lesezeichen, weitere Formate.

**Aufwand:** etwa 3 Tage, für den Nutzer 30 bis 60 Minuten (Token, Repo-Einstellung, Aufgabe bestätigen).
