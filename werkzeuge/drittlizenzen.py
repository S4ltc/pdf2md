"""Schreibt die Lizenzen aller Bestandteile, die in pdf2md.exe stecken, in eine Textdatei (fuer das Release-Paket).

Ermittelt aus requirements.txt alle installierten Pakete samt Abhaengigkeiten (mit Extras und Umgebungsmarkern),
dazu Python selbst und die mitgelieferten Schriften. Je Paket: Name, Version, Lizenzangabe und die mitgelieferten
Lizenztexte (LICENSE/COPYING/NOTICE/AUTHORS aus den Paketmetadaten). Muss mit derselben Umgebung laufen, mit der
gebaut wird, sonst stimmen die Versionen nicht.

Aufruf:  python werkzeuge/drittlizenzen.py <zieldatei>"""
import re
import sys
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

WURZEL = Path(__file__).resolve().parent.parent
LIZENZDATEI = re.compile(r"(?:^|/)(?:LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$|\.dist-info/licenses/.+",
                         re.IGNORECASE)
MIT = """Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""
BSD2 = """Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
   disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
   disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""
APACHE = ('Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance '
          "with the License. Den vollständigen Lizenztext enthält der Abschnitt pypdfium2 (LICENSES/Apache-2.0.txt) "
          "weiter unten; online: https://www.apache.org/licenses/LICENSE-2.0")
# Gehoert zum Bauen, steckt aber nicht in der .exe (PyInstaller-Bootloader: GPL mit Ausnahme, siehe unten)
NUR_BAU = {"pyinstaller", "pyinstaller-hooks-contrib", "pip", "setuptools", "wheel", "altgraph", "pefile",
           "pywin32-ctypes", "packaging"}


def name_normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def abhaengigkeiten() -> list[metadata.Distribution]:
    umgebung = default_environment()
    offen = []
    for zeile in (WURZEL / "requirements.txt").read_text(encoding="utf-8").splitlines():
        zeile = zeile.split("#", 1)[0].strip()
        if zeile and not zeile.startswith("-"):
            offen.append(Requirement(zeile))
    gefunden: dict[str, metadata.Distribution] = {}
    while offen:
        anforderung = offen.pop()
        schluessel = name_normal(anforderung.name)
        try:
            dist = metadata.distribution(anforderung.name)
        except metadata.PackageNotFoundError:
            continue
        neu = schluessel not in gefunden
        gefunden[schluessel] = dist
        extras = set(anforderung.extras)
        for roh in dist.requires or []:
            unter = Requirement(roh)
            if unter.marker is None:
                gilt = True
            else:
                gilt = any(unter.marker.evaluate({**umgebung, "extra": e}) for e in (extras or {""}))
            if gilt and (neu or unter.extras):
                offen.append(unter)
    return sorted((d for k, d in gefunden.items() if k not in NUR_BAU), key=lambda d: name_normal(d.metadata["Name"]))


def lizenzangabe(dist: metadata.Distribution) -> str:
    m = dist.metadata
    angabe = m.get("License-Expression") or ""
    if not angabe:
        lizenz = (m.get("License") or "").strip()
        angabe = lizenz if lizenz and "\n" not in lizenz and len(lizenz) < 100 else ""
    if not angabe:
        klassen = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License ::")]
        angabe = ", ".join(klassen)
    return angabe or "siehe Lizenztext"


def lizenztexte(dist: metadata.Distribution) -> list[tuple[str, str]]:
    texte = []
    for datei in dist.files or []:
        if LIZENZDATEI.search(str(datei).replace("\\", "/")):
            try:
                texte.append((str(datei), Path(dist.locate_file(datei)).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    lizenz = dist.metadata.get("License") or ""
    if not texte and "\n" in lizenz:              # manche Pakete haben den ganzen Text nur in den Metadaten
        texte.append(("METADATA: License", lizenz))
    if not texte:                                 # kein Text im Paket: Standardtext der angegebenen Lizenz
        inhaber = re.sub(r"\s*<[^>]*>", "", dist.metadata.get("Author") or dist.metadata.get("Author-email")
                         or dist.metadata.get("Maintainer") or "den Autoren des Pakets").strip()
        angabe = lizenzangabe(dist)
        vorlage = MIT if "MIT" in angabe else BSD2 if "BSD" in angabe else APACHE if "Apache" in angabe else None
        if vorlage:
            kopf = "" if vorlage is APACHE else f"Copyright (c) {inhaber}\n\n"
            texte.append((f"Standardtext {angabe} (im Paket nicht enthalten)", kopf + vorlage))
    return texte


def main() -> None:
    ziel = Path(sys.argv[1])
    trenner = "=" * 79
    teile = [
        "pdf2md – Lizenzen der mitgelieferten Bestandteile",
        "",
        "pdf2md selbst steht unter der MIT-Lizenz (Datei LICENSE). Die Programmdatei pdf2md.exe enthält außerdem die",
        "folgenden Bestandteile Dritter. Ihre Lizenztexte stehen unten vollständig.",
        "",
        "Nicht enthalten, sondern vom System genutzt: Microsoft Edge WebView2 (Teil von Windows 10/11).",
        "Die .exe wurde mit PyInstaller gebaut; dessen Bootloader steht unter der GPL 2.0 mit einer Ausnahme, die",
        "ausdrücklich erlaubt, damit gebaute Programme unter eigener Lizenz zu verbreiten.",
        "",
    ]
    pakete = abhaengigkeiten()
    teile.append(f"Python {sys.version.split()[0]} – Python Software Foundation License")
    for dist in pakete:
        teile.append(f"{dist.metadata['Name']} {dist.version} – {lizenzangabe(dist)}")
    teile += ["STIX Two/STIXGeneral (Schrift) – SIL Open Font License 1.1", "DejaVu Sans (Schrift) – Bitstream Vera / "
              "DejaVu-Lizenz (frei)", ""]
    python_lizenz = Path(sys.base_prefix) / "LICENSE.txt"
    if python_lizenz.is_file():
        teile += [trenner, f"Python {sys.version.split()[0]}", trenner, python_lizenz.read_text(encoding="utf-8",
                                                                                                 errors="replace")]
    for dist in pakete:
        texte = lizenztexte(dist)
        teile += [trenner, f"{dist.metadata['Name']} {dist.version} – {lizenzangabe(dist)}", trenner]
        if not texte:
            teile.append("(kein Lizenztext im Paket; Lizenzangabe siehe oben, Quelle: "
                         f"{dist.metadata.get('Home-page') or dist.metadata.get('Project-URL') or 'PyPI'})")
        for name, text in texte:
            teile += [f"--- {name}", text.strip(), ""]
    for datei, titel in (("LICENSE_STIX", "STIX-Schriften"), ("LICENSE_DEJAVU", "DejaVu-Schriften")):
        teile += [trenner, titel, trenner, (WURZEL / "schriften" / datei).read_text(encoding="utf-8", errors="replace")]
    ziel.write_text("\n".join(teile) + "\n", encoding="utf-8", newline="\r\n")
    print(f"{ziel}: {len(pakete)} Pakete, {ziel.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
