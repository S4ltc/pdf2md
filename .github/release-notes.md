**Download**

- **Windows 10/11:** `pdf2md-…-windows.zip` herunterladen, in einen eigenen Ordner entpacken (zum Beispiel `Dokumente\pdf2md`) und `pdf2md.exe` doppelklicken. Beim ersten Start warnt SmartScreen, weil die Datei nicht signiert ist: „Weitere Informationen“ → „Trotzdem ausführen“.
- **macOS 14 (Sonoma) oder neuer (Vorschau):** Apple Silicon `pdf2md-…-macos-arm64.zip`, Intel `pdf2md-…-macos-intel.zip`. Entpacken und `pdf2md.app` nach „Programme“ ziehen. Die App ist nicht notarisiert: nach dem ersten Öffnungsversuch Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“ (mit Administratorpasswort). Meldet macOS, die App sei „beschädigt“: im Terminal `xattr -dr com.apple.quarantine /Applications/pdf2md.app`. Den Zugriff auf den Ordner Dokumente erlauben, dort entstehen die Arbeitsordner (`Dokumente/pdf2md`).
- **Linux x86_64 (Vorschau, glibc ab 2.35: Ubuntu 22.04, Debian 12, Fedora 40, Linux Mint 21 oder neuer):** `tar -xJf pdf2md-…-linux-x86_64.tar.xz` ergibt den Ordner `pdf2md-…-linux-x86_64`, darin `pdf2md/pdf2md` starten. Die Arbeitsordner entstehen im Dokumente-Ordner unter `pdf2md`. Fehlt eine Bibliothek, meist `libxcb-cursor0` (Debian/Ubuntu) bzw. `xcb-util-cursor` (Fedora) installieren; bleibt das Fenster leer, `QT_QPA_PLATFORM=xcb` vor den Aufruf setzen und probieren (mehr dazu in der README).

„Vorschau“: Die Mac- und Linux-Fassungen werden bei jedem Build auf GitHub automatisch gestartet und geprüft, sind auf echten Geräten aber noch nicht von Hand getestet. Startet pdf2md nicht, nennt eine Meldung die Datei `pdf2md-fehler.txt` mit den Einzelheiten.

**Prüfsummen** stehen in `SHA256SUMS.txt`: Windows `Get-FileHash pdf2md-…-windows.zip` (PowerShell), macOS `shasum -a 256 pdf2md-…-macos-arm64.zip` (Wert mit der Zeile in `SHA256SUMS.txt` vergleichen), Linux `sha256sum -c SHA256SUMS.txt --ignore-missing` im Download-Ordner.

Anleitung, Datenschutz und bekannte Grenzen: siehe [README](https://github.com/S4ltc/pdf2md#readme). Lizenz: MIT, Lizenzen der enthaltenen Bibliotheken in `DRITTLIZENZEN.txt` im jeweiligen Paket, im Linux-Paket zusätzlich `CHROMIUM-LIZENZEN.txt` (Chromium und die Bestandteile Dritter von Qt).
