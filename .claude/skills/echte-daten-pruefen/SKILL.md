---
name: echte-daten-pruefen
description: "Änderungen am Textverfahren an echten Büchern und Normen messen (Regression alt gegen neu). Nach Änderungen am Textweg in pdf2md.py, an lesefolge, zeichen, tabellen, formelsatz, formeln, schriftbild, seitenzahlen oder normen; bevor eine gemessene Schwelle geändert wird; wenn der Nutzer „an echten Daten prüfen“ sagt."
---

# Echte Daten prüfen

Synthetische Tests zeigen, dass der Code tut, was gemeint ist. Ob es den Büchern hilft, zeigt erst der Vergleich alt gegen neu an echten Dateien. Die Heuristiken sind an 58 Büchern und 56 Normen abgestimmt; jede Änderung daran braucht eine neue Messung.

## Regeln für jeden Schritt

- Testmaterial nur lesen: `umwandeln()`/`metadaten_lesen()` oder die Lauf-Skripte nutzen. `verarbeiten()` und „Starten“ verschieben das Original.
- Pfade zu Büchern und Normen stehen in `CLAUDE.local.md`; das große Handbuch-PDF (Name ebenda) bleibt draußen.
- Alle Ausgaben in den Scratchpad. Sie enthalten Buch- und Normtext: nicht ins Repo, nicht in Commit-Nachrichten, nicht nach `docs/`.
- Skripte mit der venv-Python (`%LOCALAPPDATA%\pdf2md-venv\Scripts\python.exe`) und `PYTHONIOENCODING=utf-8` starten.

## Ablauf

1. **Alter Stand**: den Code vor der Änderung auspacken, z. B. `git archive HEAD | tar -x -C <scratchpad>/alt` (Git Bash).
2. **Zwei Läufe** über dieselbe Auswahl (`muster`), lange Läufe im Hintergrund:
   - Bücher: `BUECHER=<Pfad> CODE_DIR=<scratchpad>/alt python werkzeuge/buecher_lauf.py <scratchpad>/buecher-alt [muster]`, dann ohne `CODE_DIR` nach `<scratchpad>/buecher-neu`.
   - Normen: dasselbe mit `NORMEN=<Pfad>` und `werkzeuge/normen_lauf.py`.
3. **Vergleichen**: `python werkzeuge/vergleich.py <alt> <neu> [beispiele_je_datei]`. Jede geänderte Datei einordnen: gewollt besser, gleichwertig oder schlechter.
4. **Gezielt nachmessen**, je nach Thema auf beiden Ordnern:
   - `werkzeuge/schwaechen.py <ordner>`: verbliebene `�`, verdoppelte Formelzeichen, Tabellen über Seitengrenzen, Kopfzeilenreste, gesperrter Text.
   - `werkzeuge/seitenpruefung.py <ordner mit PDFs>`: gedruckte Seitenzahlen gegen das Inhaltsverzeichnis.
   - `werkzeuge/zitierpruefung.py <ausgabeordner> <ordner mit PDFs>`: Sätze stehen auf der Seite ihres Markers.
5. **Festhalten**: Zahlen vorher/nachher mit der Anzahl Bücher bzw. Normen im passenden `docs/claude/<thema>.md` eintragen. Beispiele neutral beschreiben; welches Buch dahintersteht, gehört nach `CLAUDE.local.md`.

Fertig, wenn jede geänderte Datei eingeordnet ist, keine ungewollte Verschlechterung bleibt (oder sie mit dem Nutzer besprochen ist) und die Zahlen eingetragen sind.

## Fallen

- Die `.md` in `dist\Fertig` taugen nicht als Referenz: älterer Stand, dort liegen seit Oktober 2026 auch nur noch Normen. Verglichen wird immer alt gegen neu aus zwei frischen Läufen.
- Gemessene Schwellen (`formeln.MIN_WERT`/`MIN_MARGE`, die Eingriffsbedingungen in `lesefolge.py`, `tabellen.echt()`) nur mit neuer Messung an beiden Beständen ändern.
- Eine Kontrolle, die nur Verschlechterungen verhindert, ist kein Qualitätsmaß (Beispiel „Zeilenübergang“ in `docs/claude/lesefolge.md`).
