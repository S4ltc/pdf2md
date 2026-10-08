# Baut pdf2md.exe fuer Windows (PyInstaller, Fenster-Anwendung). Aufruf:  powershell -ExecutionPolicy Bypass -File build.ps1
# Die PyInstaller-Einstellungen stehen in werkzeuge\bauen.py (gemeinsam mit den Builds fuer macOS und Linux auf GitHub).
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

& $python (Join-Path $here "werkzeuge\bauen.py") (Join-Path $here "dist")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $here "dist\pdf2md.exe"))) {
    Write-Host "Build fehlgeschlagen."
    exit 1
}

Write-Host "`nFertig: $(Join-Path $here 'dist\pdf2md.exe')"
