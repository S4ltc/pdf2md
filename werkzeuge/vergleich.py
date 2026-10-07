"""Vergleicht zwei Ausgabeordner (alt/neu) Datei fuer Datei: Zeilendiff mit Beispielen.
Aufruf: python werkzeuge/vergleich.py <alt> <neu> [beispiele_je_datei]"""
import difflib
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

alt_dir, neu_dir = Path(sys.argv[1]), Path(sys.argv[2])
zeige = int(sys.argv[3]) if len(sys.argv) > 3 else 4


def norm(z: str) -> str:
    """Was die erwarteten Aenderungen (NFC, Tabulatoren) ausgleicht."""
    z = unicodedata.normalize("NFC", z).replace("\t", " ")
    return re.sub(r"[ ]{3,}", "  ", z).rstrip()


gesamt = Counter()
for a in sorted(alt_dir.glob("*.md")):
    b = neu_dir / a.name
    if not b.exists():
        continue
    za = a.read_text(encoding="utf-8").split("\n")
    zb = b.read_text(encoding="utf-8").split("\n")
    na, nb = [norm(z) for z in za], [norm(z) for z in zb]
    sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
    arten = Counter()
    beispiele = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        weg, dazu = na[i1:i2], nb[j1:j2]
        arten[op] += 1
        if len(beispiele) < zeige:
            beispiele.append((op, weg[:3], dazu[:3]))
    roh_gleich = sum(1 for x, y in zip(za, zb) if x != y)
    gesamt.update(arten)
    if arten:
        print(f"== {a.name[:70]}  {dict(arten)}")
        for op, weg, dazu in beispiele:
            for z in weg:
                print(f"   - {z[:160]!r}")
            for z in dazu:
                print(f"   + {z[:160]!r}")
            print("   ---")
print("GESAMT", dict(gesamt))
