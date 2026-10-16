# Testplan macOS und Linux

Die Mac- und Linux-Pakete werden bei jedem Build auf GitHub automatisch gestartet. Dabei wandeln sie eine erfundene PDF und DOCX um, und das Linux-Paket wird zusätzlich in Containern mit Ubuntu 24.04, Debian 12 und Fedora 41 gestartet (Ergebnis je Lauf am Build). Nicht automatisch prüfbar ist, was nur auf einem echten Gerät passiert:
- erster Start mit Gatekeeper,
- die Abfrage nach dem Ordner Dokumente,
- Ziehen aus Finder bzw. Dateimanager,
- die Dateidialoge,
- echte Grafikkarten und Wayland,
- Darstellung und Tastatur.

Dieser Plan beschreibt den Handtest dafür. Ein Durchgang dauert etwa 45 Minuten.

## Datenschutz beim Testen

- Für Rückmeldungen nur die erfundenen Beispieldateien oder eigene unkritische Dokumente verwenden. Keine Bücher, Normen oder Auszüge daraus weitergeben, auch keine Kopfblöcke solcher Dateien.
- Terminalausgaben, `Protokoll.csv` und `pdf2md-fehler.txt` enthalten Pfade mit dem Benutzernamen (`/Users/NAME`, `/home/NAME`). Vor dem Weitergeben schwärzen.
- Bildschirmfotos nur mit Beispieldateien.

## Vorbereitung

1. Paket aus dem Release laden: `pdf2md-…-macos-arm64.zip` (Apple Silicon), `…-macos-intel.zip` oder `…-linux-x86_64.tar.xz`.
2. Prüfsumme vergleichen:
   - macOS: `shasum -a 256 <datei>`, mit der Zeile in `SHA256SUMS.txt` vergleichen.
   - Linux: `sha256sum -c SHA256SUMS.txt --ignore-missing`.
3. System, Version und Chip bzw. Distribution, Desktop (GNOME, KDE, …), Wayland oder X11 und Grafikkarte notieren.

## macOS: erster Start

Voraussetzung ist macOS 14 (Sonoma) oder neuer für Apple Silicon und macOS 15 (Sequoia) oder neuer für Intel. Das Paket meldet beim Bauen die gemessene Mindestversion (`macos_minos`; Intel: die mitgelieferte OpenSSL-Bibliothek verlangt 15.0).

1. Mit Safari laden, damit macOS die Datei wie bei Nutzern als „aus dem Internet“ kennzeichnet. Entpacken und `pdf2md.app` nach „Programme“ ziehen.
2. Doppelklicken. Erwartet: Hinweis, dass die App nicht geprüft werden kann. Dann Systemeinstellungen → Datenschutz & Sicherheit → bei pdf2md „Dennoch öffnen“, das braucht das Admin-Passwort.
   - Meldet macOS stattdessen „ist beschädigt“: im Terminal `xattr -dr com.apple.quarantine /Applications/pdf2md.app` ausführen und notieren, dass das nötig war.
3. Abfrage „pdf2md möchte auf Dateien im Ordner Dokumente zugreifen“ → Erlauben. Erwartet: Das Fenster zeigt oben die Versionsnummer, und im Finder entsteht `Dokumente/pdf2md` mit Eingang, Fertig und Prüfen.
4. Gegenprobe Zugriff verweigern:
   - `tccutil reset SystemPolicyDocumentsFolder io.github.s4ltc.pdf2md` ausführen, App neu starten, bei der Abfrage „Nicht erlauben“ wählen.
   - Erwartet: eine Meldung mit dem Hinweis auf Datenschutz & Sicherheit, kein stummes Verschwinden.
   - Danach den Zugriff wieder erlauben (Systemeinstellungen → Datenschutz & Sicherheit → Dateien und Ordner).
5. Nur wenn ein älterer Mac (macOS 13 oder älter) da ist: starten. Erwartet: macOS meldet, dass die App diese Version nicht unterstützt.

## Linux: erster Start

Voraussetzung ist x86_64 mit glibc ab 2.35, also Ubuntu 22.04 oder neuer, Debian 12 oder neuer, Fedora 40 oder neuer, Linux Mint 21 oder neuer. Das Paket meldet beim Bauen die gemessene glibc-Version.

1. Entpacken: `tar -xJf pdf2md-…-linux-x86_64.tar.xz`. Erwartet: ein Ordner `pdf2md-…-linux-x86_64` mit `pdf2md/`, Lizenzen und LIESMICH; nichts wird lose in den aktuellen Ordner gelegt.
2. Einmal im Terminal starten: `./pdf2md-…-linux-x86_64/pdf2md/pdf2md`. Erwartet: Fenster mit Titelleiste, Schließen-Knopf und Versionsnummer; `~/Dokumente/pdf2md` bzw. der Dokumente-Ordner der Sprache entsteht. Die Terminalausgabe sichern.
3. Einmal per Doppelklick im Dateimanager starten. Notieren, ob das geht.
4. Fenster leer, schwarz oder ohne Titelleiste: nacheinander probieren und notieren, was hilft.
   - `QT_QPA_PLATFORM=xcb ./…/pdf2md`
   - `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu ./…/pdf2md`
5. Startet nichts: Terminalausgabe sichern; fehlende Bibliotheken zeigt `ldd ./…/pdf2md/pdf2md | grep "not found"`. LIESMICH nennt die häufigsten Pakete (`libxcb-cursor0` und `libwayland-server0` bzw. `xcb-util-cursor` und `libwayland-server`). Unter WSL2 fehlen beide in der Regel, also vor dem ersten Start `sudo apt install libxcb-cursor0 libwayland-server0`. Gibt es eine Datei `pdf2md-fehler.txt` im Dokumente-Ordner, ihren Inhalt (geschwärzt) mitschicken.

## Prüfliste für beide Systeme

| Nr. | Prüfung | Erwartet |
|---|---|---|
| 1 | „Hinzufügen …“ und Strg+O (Mac: ⌘O) | Dateidialog öffnet sich; Mehrfachauswahl geht; `BERICHT.PDF` (Großbuchstaben) erscheint unter „Unterstützte Dateien“; Abbrechen ohne Fehlermeldung |
| 2 | Ziehen ins Fenster: eine Datei mit Umlaut und Gedankenstrich im Namen, `BERICHT.PDF`, ein Ordner mit drei PDFs, mehrere Dateien zugleich | Alle landen in Eingang, die Statuszeile meldet die Anzahl. Bleibt es bei „werden kopiert …“, Dateinamen notieren |
| 3 | Starten mit 3 bis 5 Dateien, darunter eine PDF mit über 300 Seiten | Fortschritt läuft, Dateien landen in Fertig bzw. Prüfen; Kopfblock wie unter Windows (gleiche Datei vergleichen) |
| 4 | Online-Abgleich: eine PDF ohne Jahr in den Metadaten, aber mit ISBN oder DOI im Text | Kopfblock enthält eine Quellenangabe bzw. das Jahr aus Crossref. Landet sie in Prüfen oder fehlt die Quellenangabe, deutet das auf ein Zertifikatsproblem |
| 5 | Öffnen: in jeder Spalte „Ordner“, in Fertig den Namen (öffnet die .md) und das Formatkürzel (öffnet das Original); Werkzeuge → Literaturliste exportieren | Finder bzw. Dateimanager, Editor und PDF-Betrachter öffnen sich; `Literatur.bib` liegt neben dem Ordner Fertig. Lässt sich etwas nicht öffnen, zeigt das Fenster einen Fehler statt Erfolg |
| 6 | Update-Hinweis (falls eine neuere Version erscheint): anklicken | Der Browser öffnet die Release-Seite; sonst zeigt das Fenster einen Hinweis |
| 7 | Schließen während eines Laufs: Schließen-Knopf; Mac zusätzlich ⌘Q und Dock → Beenden; Linux zusätzlich Alt+F4 | Rückfrage „Ein Lauf ist noch aktiv“; „Weiterlaufen lassen“ setzt fort; „Beenden und schließen“ schließt nach der aktuellen Datei. Nach dem Neustart keine halbe .md und nichts doppelt |
| 8 | Zweiter Start bei offenem Fenster (Linux: Doppelklick; Mac: `open -n /Applications/pdf2md.app`) | Kein zweites Fenster, sondern eine sichtbare Meldung „läuft schon“ |
| 9 | Viele Bücher: mindestens 45 kleine Dateien (kurze DOCX oder HTML) umwandeln, Programm neu starten | Auswertung zeigt nach einigen Sekunden die Kennzahlen; danach keine übrigen pdf2md-Prozesse (Aktivitätsanzeige bzw. `ps aux | grep pdf2md`) |
| 10 | Darstellung: System auf Dunkel stellen, starten, während eines Laufs auf Hell umschalten; Fenster auf Mindestgröße ziehen; lange Listen | Seite und Fensterrand passen zusammen; nichts abgeschnitten; erkennbar, dass Listen scrollen. Bildschirmfotos hell und dunkel |
| 11 | Tastatur: Mac ⌘O, ⌘↩, ⌘1 bis ⌘3, Tab durch die Oberfläche (einmal mit eingeschalteter Tastaturnavigation in den Systemeinstellungen); Linux Strg+O, Strg+Enter, Strg+1 bis Strg+3 | Kürzel wirken und die Tooltips nennen sie richtig; Tab erreicht Knöpfe und Listen |
| 12 | Update: eine neuere Version über die alte legen (Mac: in „Programme“ ersetzen; Linux: Ordner ersetzen) | Ablage und Einstellungen bleiben; Mac: notieren, ob die Abfrage zum Ordner Dokumente und die Gatekeeper-Rückfrage erneut kommen |
| 13 | Nur Mac, optional: einen langen Lauf starten, Fenster minimieren, 5 Minuten anderes tun | Dauer mit einem gleichen Lauf bei sichtbarem Fenster vergleichen (Auswertung → Dauer je Seite); deutlich langsamer heißt, App Nap bremst |

## Ergebnis festhalten

Je Nummer festhalten: erfüllt, nicht erfüllt (mit Beobachtung) oder nicht geprüft. Dazu System und Version, Paketname und die Auffälligkeiten aus dem ersten Start. Terminalausgaben und Fehlerdateien geschwärzt beilegen.

## Testwege ohne eigenes Gerät

- **Linux mit WSL2 unter Windows 11:**
  - Schneller Rauchtest, etwa eine Stunde. Einrichten in einer PowerShell als Administrator mit `wsl --install -d Ubuntu-24.04`, danach neu starten.
  - Testdateien ins Linux-Heimverzeichnis kopieren, nicht direkt aus OneDrive unter `/mnt/c` öffnen.
  - Nicht prüfbar sind Ziehen aus dem Explorer, dunkles Thema und Dateimanager.
- **Linux in einer Ubuntu-24.04-VM (VirtualBox):** echter GNOME-Desktop mit Wayland, Nautilus und AppArmor wie bei Nutzern, damit sind fast alle Punkte prüfbar. Empfehlungen für die VM:
  - 4 bis 8 Kerne, 8 bis 16 GB Arbeitsspeicher, deutsche Sprache, Gastzusätze.
  - Gemeinsamer Ordner für das Paket.
  - Vorher einen Snapshot anlegen.
  - Unter Windows mit aktiver Speicherintegrität läuft VirtualBox langsamer.
- **macOS:**
  - Am besten mit Bekannten, die einen Mac haben, etwa in einem Videoanruf mit Bildschirmfreigabe.
  - Sonst ein gemieteter Mac mini M1, etwa bei Scaleway: Die Mindestmiete beträgt 24 Stunden, rund 2,64 € netto. Das automatische Löschen nach 24 Stunden einschalten. Zugriff per VNC; das Paket dort in Safari laden.
  - Eine macOS-VM auf einem Windows-PC erlaubt Apples Lizenz nicht. Intel-Macs prüft bisher nur der automatische Build.
