---
name: veroeffentlichen
description: "Push oder Release vorbereiten und prüfen: Datenschutz (persönliche Daten, echte Titel), Commit-Autoren, gebaute exe, Version und Tag, CI-Ergebnis auf GitHub. Wenn der Nutzer pushen, veröffentlichen oder ein Release machen will."
---

# Veröffentlichen

Das Repo ist öffentlich (MIT). Claude prüft und bereitet vor; pushen und taggen macht der Nutzer selbst (der Schutz-Hook sperrt `git push`).

## Ablauf

1. **Umfang**: `git fetch origin`, dann `git log --oneline origin/main..HEAD` zeigt, was hinausgeht.
2. **Datenschutz** über den ganzen Baum mit `git grep -n -i`, nicht nur im Diff:
   - Windows-Benutzername (`$env:USERNAME`), die eigene E-Mail-Adresse, `OneDrive`, `Kd.-Nr`, `Abo-Nr`, Lizenzkennungen und Ausdruckszeitpunkte aus Normen.
   - Die echten Titel, Autoren und Normnummern aus `CLAUDE.local.md` (Abschnitt „Echte Titel …“), dazu ISBN/DOI der eigenen Bücher.

   Die Suchbegriffe nur auf der Kommandozeile verwenden, nie in eine Datei im Repo schreiben. Jeden Treffer erklären oder ersetzen (erfundene Werte wie Normnummer 12345, „Beispielelemente“, Erika Muster).
3. **Autoren**: `git log --format='%an <%ae>' origin/main..HEAD | sort -u` zeigt nur die GitHub-noreply-Adresse.
4. **Zweige**: nur `main` geht nach `origin`. `main-privat` und der Remote `privat` enthalten die alte Historie mit privater E-Mail-Adresse (Regeln in `CLAUDE.local.md`).
5. **Bei einem Release** zusätzlich:
   - `VERSION` in `aktualisierung.py` erhöhen; der Tag `v<VERSION>` muss genau passen, sonst bricht `release.yml` ab.
   - Offene Aufgaben in CLAUDE.md prüfen:
     - Chromium-Lizenzen: Ohne `CHROMIUM-LIZENZEN.txt` bricht das Linux-Paket im Release ab (Push-Builds warnen nur). Vor dem Tag den letzten Push-Lauf lesen (Schritt 7): Paketbericht „Paket linux-x86_64“ mit `chromium_volltext: true` und `chromium_quelle`, keine Warnung „Chromium-Lizenzen …“.
     - Mac und Linux bleiben „Vorschau“, bis die Handtests nach `docs/testplan-mac-linux.md` (Schritt 3) gemacht sind. Erst danach „Vorschau“ in README, `docs/LIESMICH.txt` und `.github/release-notes.md` streichen. Die nächste Version 1.2.0 ist das erste Release mit Mac- und Linux-Paketen, noch als Vorschau.
   - Eine lokal gebaute exe prüfen: `python werkzeuge/exe_pruefen.py dist/pdf2md.exe --benutzer`; Treffer „runneradmin“ stammen aus vorgebauten Paketen. Bauen: Skill `pakete-bauen`.
6. **Übergabe**: dem Nutzer das Prüfergebnis und die Befehle zum Selbst-Ausführen nennen (Push von `main`, bei einem Release Tag anlegen und pushen).
7. **CI lesen** (nach dem Push, wenn gewünscht): `tests.yml` (windows/macos/ubuntu) und `bauen.yml` schreiben Ergebnisse als Annotation (Titel der Hinweise: Skill `pakete-bauen`, Abschnitt macOS und Linux). Öffentlich lesbar ohne Anmeldung: `https://api.github.com/repos/S4ltc/pdf2md/commits/<sha>/check-runs`, dann je Lauf `annotations_url`. Job-Logs brauchen eine Anmeldung.

Fertig, wenn jeder Treffer aus Schritt 2 erklärt oder ersetzt ist, nur noreply-Autoren dabei sind und der Nutzer die Übergabe aus Schritt 6 hat.

## Hintergrund (aus CLAUDE.md)

- Lizenz `LICENSE` (MIT, Inhaber „S4ltc“ = GitHub-Name, kein Klarname). Fremdlizenzen erzeugt `werkzeuge/drittlizenzen.py` aus requirements.txt samt Abhängigkeiten (Texte aus `.dist-info`, auch `licenses/`; fehlt ein Text, der Standardtext der angegebenen Lizenz), dazu Python und die Schriften.
- Releases baut nur GitHub (`.github/workflows/release.yml`, Tag `v*`; vorher `VERSION` in `aktualisierung.py` erhoehen, der Ablauf bricht ab, wenn Tag und VERSION nicht passen): Build, alle Tests in derselben Umgebung, Pakete `pdf2md-<tag>-windows.zip`, `-macos-arm64.zip`, `-macos-intel.zip` und `-linux-x86_64.tar.xz` (je Programm, LICENSE.txt, DRITTLIZENZEN.txt, LIESMICH.txt; Linux zusätzlich CHROMIUM-LIZENZEN.txt und ein Oberordner mit dem Namen des Archivs), SHA256SUMS.txt und Text aus `.github/release-notes.md`. Der Job `distributionen` (Linux-Paket auf weiteren Distributionen) hält das Release nicht auf. Tests bei jedem Push: `tests.yml`.
