"""Durchsucht eine mit PyInstaller gebaute pdf2md.exe nach Zeichenketten, die nicht veroeffentlicht werden sollen
(etwa der eigene Windows-Benutzername in eingebetteten Quellpfaden). Entpackt dazu das Archiv der .exe im Speicher,
auch die komprimierten Python-Module (PYZ). Nur lesend.

Aufruf:  python werkzeuge/exe_pruefen.py <pdf2md.exe> <suchwort> [<suchwort> ...]
         python werkzeuge/exe_pruefen.py dist/pdf2md.exe --benutzer      (sucht den aktuellen Benutzernamen)
Ausgabe: je Suchwort die Zahl der Fundstellen und bis zu fuenf Eintraege; Rueckgabewert 1, wenn etwas gefunden wurde."""
import getpass
import os
import sys
import zlib


def eintraege(pfad: str):
    """(Name, Bytes) aller Eintraege, Python-Module aus dem PYZ-Archiv einzeln und entpackt."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    archiv = CArchiveReader(pfad)
    for name in archiv.toc:
        try:
            daten = archiv.extract(name)
        except Exception:
            continue
        if daten is None:
            continue
        if name.endswith(".pyz") or name == "PYZ-00.pyz":
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pyz") as f:
                f.write(daten)
            try:
                pyz = ZlibArchiveReader(f.name)
                for modul in pyz.toc:
                    try:
                        yield f"{name}:{modul}", pyz.extract(modul, raw=True) or b""
                    except Exception:
                        continue
            finally:
                os.unlink(f.name)
        elif daten[:2] == b"PK":                         # base_library.zip u.ae.: jedes Mitglied einzeln
            import io
            import zipfile
            try:
                with zipfile.ZipFile(io.BytesIO(daten)) as z:
                    for mitglied in z.namelist():
                        yield f"{name}:{mitglied}", z.read(mitglied)
            except zipfile.BadZipFile:
                yield name, daten
        else:
            yield name, daten


def main() -> int:
    pfad = sys.argv[1]
    woerter = [w for w in sys.argv[2:] if w != "--benutzer"]
    if "--benutzer" in sys.argv[2:]:
        woerter.append(getpass.getuser())
    funde = {w: [] for w in woerter}
    for name, daten in eintraege(pfad):
        varianten = [daten]
        try:
            varianten.append(zlib.decompress(daten))
        except Exception:
            pass
        for w in woerter:
            kodiert = [w.encode("utf-8"), w.encode("utf-16-le")]
            if any(k.lower() in v.lower() for v in varianten for k in kodiert):
                funde[w].append(name)
    for w, orte in funde.items():
        print(f"{w!r}: {len(orte)} Fundstellen" + "".join(f"\n    {o}" for o in orte[:5]))
    return 1 if any(funde.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
