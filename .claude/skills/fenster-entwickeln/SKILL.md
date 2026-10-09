---
name: fenster-entwickeln
description: "Oberfläche und Api ändern: ui_app.py, ui/web/, einstellungen.py, auswertung.py, ablage.py, plattform.py, aktualisierung.py. Mit Ablage-Kopie statt dist, Vorschau-Server, Screenshots hell/dunkel und den bekannten Fallen (Threads, Einstellungen in Unterprozessen, schnelle Regler)."
---

# Fenster entwickeln

## Ablauf

1. **Ablage-Kopie** im Scratchpad anlegen: Ordner und `Protokoll.csv` aus `dist` kopieren (lesen ist erlaubt) und in der Kopie die Pfade in `Protokoll.csv` auf die Kopie umschreiben, sonst verschiebt „Rückgängig“ in `dist`. Originale dürfen Platzhalter sein.
2. **Starten** gegen die Kopie: Fenster mit `PDF2MD_ABLAGE=<kopie> python ui_app.py`, im Browser mit `python werkzeuge/ui_vorschau.py <kopie> 8765`. Die lokale `.claude/launch.json` hat dafür den Eintrag `ui-vorschau`; ihren Pfad auf die aktuelle Kopie setzen. Mit `dist` als Ablage sperrt der Schutz-Hook beide Aufrufe.
3. **Änderung mit Test**: Api in `tests/test_ui_app.py` (ohne Fenster, `extern_oeffnen`/`link_oeffnen` ersetzt), Kennzahlen in `tests/test_auswertung.py`, Listen in `tests/test_ablage.py`, Einstellungen in `tests/test_einstellungen.py`, Systemzweige in `tests/test_plattform.py`.
4. **Sichtprüfung** über den Vorschau-Server mit `?thema=hell|dunkel&seite=uebersicht|auswertung|einstellungen&experte=offen`: hell und dunkel, 1280, 960 und 720 px breit (720 = Mindestbreite des Fensters), dazu Tastaturbedienung. Screenshots per Edge headless oder im eingebauten Browser. Kontrastmodus und reduzierte Bewegung: Rendering-Tool der Edge-DevTools (Emulation von `forced-colors`, `prefers-reduced-motion`).
5. **Neue Einstellung**: in `einstellungen.EINSTELLUNGEN` eintragen, dann `python werkzeuge/einstellungen_liste.py` (schreibt `docs/einstellungen.md` neu).

Fertig, wenn die Tests grün sind, jede geänderte Stelle den Prüfmaßstab unten erfüllt, die Screenshots hell und dunkel in allen drei Breiten ohne Überlauf aussehen und `dist` unverändert ist.

## Prüfmaßstab

Die Gestaltungsregeln in CLAUDE.md (Verbindliche Regeln) gelten zuerst. Für alles, was sie offenlassen:

**Windows 11** (das Fenster soll wie ein Windows-Werkzeug wirken, nicht wie eine Webseite):
- Schriftstufen: 12/16 Beschriftung, 14/20 Text (halbfett für Betonung), 18/24 Abschnitte und Dialogtitel, 20/28 Seitentitel und große Zahlen, 28/36 einzelne Kennzahl. Keine Zwischengrößen.
- Mindestens 12 px Schrift, halbfett erst ab 14 px, halbfett (600) statt fett. Satzschreibung, keine Versal-Labels.
- Zeilen höchstens etwa 60 Zeichen (`max-width: 60ch` für Fließtext).
- Rundung 4 px für Steuerelemente, Flächen auf der Seite und Tooltips, 8 px für Menüs und Dialoge.

**Texte:**
- Eine Aktion heißt überall gleich: Menüeintrag, Dialogknopf und Schlussmeldung nutzen dasselbe Verb („Namen reparieren …“ → „Namen reparieren (12)“ → „Namen repariert: 12 umbenannt“).
- Knöpfe sagen, was passiert. Fehlermeldungen sagen, was passiert ist und was man tun kann; keine pauschale Meldung für verschiedene Ursachen.
- Leere Zustände sagen, wie man weiterkommt. Mehrzahl richtig bilden („1 Datei“, „3 Dateien“), nie „Datei(en)“.
- Eine Beschriftung beschreibt genau, was darunter steht; überflüssige Beschriftungen weglassen.
- Die Statuszeile antwortet auf eine Aktion des Nutzers (Datei geöffnet, Einstellung gespeichert, Fehler); Laufereignisse (Beginn, Ende, Ergebnis) stehen im Laufprotokoll und werden für Screenreader über `#ansage` vorgelesen, nicht zusätzlich in der Statuszeile.

**Bedienbarkeit:**
- Jedes bedienbare Element hat einen sichtbaren Fokus über `outline`; `box-shadow` allein verschwindet im Windows-Kontrastmodus. Für `forced-colors: active` prüfen.
- Text unter 18 px braucht mindestens 4,5:1 Kontrast auf jeder Fläche, auf der er steht, hell und dunkel nachgerechnet.
- Die Live-Region `#status` bleibt in jeder Breite im Dokument; nie per `display: none` verstecken.
- Nichts nur per Maus: Werte in Diagrammen sind auch per Tastatur und Screenreader erreichbar.
- Regelmäßige Aktualisierungen (Takt 0,4 s im Lauf) bauen nur neu, was sich geändert hat, und erhalten Fokus und Scrollstand.
- Bewegung nur als Antwort auf eine Aktion oder als Fortschritt, mit `prefers-reduced-motion`.
- Keine Fläche mit eigenem Rahmen in einer gerahmten Fläche (Karte in Karte).

## Hintergrund (aus CLAUDE.md)

- Neuaufbau nur bei Änderung (app.js): `listeErneuern()` für die drei Listen (Kennung aus den Daten; Fokus über `data-ziel` ohne Scrollsprung wiederhergestellt, sonst Element an derselben Stelle bzw. Spaltenüberschrift), Kennungen in `zeigeKennzahlen()` und `zeigeDiagrammeUebersicht()`, `neuZeichnen()` je Diagramm der Auswertung. Im Takt baut `verarbeiteEreignisse()` nur den Eingang; Prüfen, Fertig und Kennzahlen folgen der Signatur. Gemessen im echten Lauf: Fertig 0 Neuaufbauten statt einem je Takt, Fokus bleibt.
- Diagramme (diagramme.js): `zugang()` macht jedes Diagramm zu einem Tabstopp mit Pfeiltasten, Live-Ansage und unsichtbarer Werteliste; das SVG ist `aria-hidden`. Der gewählte Wert überlebt ein Neuzeichnen (`diagrammAuswahl`).
- Testumgebung: Im ausgeblendeten eingebauten Browser feuert das `close`-Ereignis von `<dialog>` nicht (Chromium zeichnet nicht). Dialogabläufe dort über die Api (`POST /api/werkzeug_starten`) prüfen oder den Browser einblenden.

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
- Version und Updates (`aktualisierung.py`): `VERSION` steht im Kopf des Fensters. `Api.update_pruefen_starten()` fragt einmal je Start (nur aus `main()`, nie in Tests) `releases/latest` bei GitHub ab (User-Agent `pdf2md/1.0`, abschaltbar `aktualisierung.SUCHEN`, Standard an); eine neuere Version erhoeht `_warm` (Signatur), das Fenster zeigt „Version … verfügbar“. `update_oeffnen()` oeffnet nur die feste Release-Seite (`link_oeffnen`, in Tests ersetzt). Ersetzt oder geladen wird nichts.
