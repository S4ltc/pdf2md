# Baut pdf2md.exe (PyInstaller, Fenster-Anwendung). Aufruf:  powershell -ExecutionPolicy Bypass -File build.ps1
# Die virtuelle Umgebung liegt bewusst ausserhalb von OneDrive (viele kleine Dateien).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

# Eine laufende pdf2md.exe wuerde ueberschrieben bzw. die Datei ist gesperrt: dann nicht bauen.
if (Get-Process -Name pdf2md -ErrorAction SilentlyContinue) {
    Write-Host "pdf2md.exe laeuft noch. Bitte erst schliessen, dann erneut bauen."
    exit 1
}

$venv = Join-Path $env:LOCALAPPDATA "pdf2md-venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
    $basePython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
    if (-not (Test-Path $basePython)) { $basePython = "python" }
    & $basePython -m venv $venv
}
& $python -m pip install --quiet -r (Join-Path $here "requirements.txt") pyinstaller
if ($LASTEXITCODE -ne 0) { Write-Host "Installation der Abhaengigkeiten fehlgeschlagen."; exit 1 }

$work = Join-Path $env:TEMP "pdf2md-build"
# Einstieg ist das Fenster (ui_app.py); pdf2md.py und die anderen Module kommen ueber die Importe mit.
# schriften\ enthaelt die freien Referenzschriften (STIX, DejaVu) fuer die Formelreparatur, ui\web die Oberflaeche.
# --windowed: kein Konsolenfenster. pywebview bringt einen eigenen PyInstaller-Hook mit; die Plattform-Module
# (EdgeChromium/WinForms) und pythonnet werden dynamisch geladen und deshalb ausdruecklich mitgenommen.
& $python -m PyInstaller --onefile --windowed --name pdf2md `
    --collect-all markitdown --collect-all magika --collect-all pypdfium2 --collect-all pypdfium2_raw `
    --collect-all pythonnet --collect-all clr_loader `
    --hidden-import webview.platforms.edgechromium --hidden-import webview.platforms.winforms `
    --add-data ("{0};schriften" -f (Join-Path $here "schriften")) `
    --add-data ("{0};ui/web" -f (Join-Path $here "ui\web")) `
    --distpath (Join-Path $here "dist") --workpath $work --specpath $work `
    (Join-Path $here "ui_app.py")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $here "dist\pdf2md.exe"))) {
    Write-Host "Build fehlgeschlagen."
    exit 1
}

Write-Host "`nFertig: $(Join-Path $here 'dist\pdf2md.exe')"
