"""Wandelt die Buecher in dist/Fertig neu um (nur lesend, ohne Dateien ueber 150 MB) und vergleicht
grob mit der vorhandenen .md. Die neuen Texte landen im Ausgabeordner (enthalten Buchtext: nie ins Repo legen).
Fuer einen Vorher/Nachher-Vergleich zwei Laeufe machen (alter Stand per `git archive` und CODE_DIR) und die beiden
Ordner mit vergleich.py gegenueberstellen.

Aufruf:  python werkzeuge/buecher_lauf.py <ausgabeordner> [muster]
Umgebung: BUECHER (Ordner mit PDF + .md), CODE_DIR (anderer Code-Stand)."""
import concurrent.futures as cf
import json
import os
import sys
import time
from pathlib import Path

CODE_DIR = os.environ.get("CODE_DIR", str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, CODE_DIR)
BUECHER = Path(os.environ.get("BUECHER", str(Path(__file__).resolve().parent.parent / "dist" / "Fertig")))
MAX_GROESSE = 150_000_000      # das 160-MB-Handbuch bleibt aussen vor


def eins(pfad: str, out: str) -> dict:
    import pdf2md
    pdf2md.ONLINE_ABGLEICH = False
    p = Path(pfad)
    md = p.with_suffix(".md")
    werte, alt = pdf2md.kopf_lesen(md.read_text(encoding="utf-8-sig")) if md.exists() else (None, "")
    t0 = time.time()
    neu, quelle, extra = pdf2md.umwandeln(p, (werte or {}).get("seiten"), None)
    sek = time.time() - t0
    (Path(out) / (p.stem[:80] + ".md")).write_text(neu, encoding="utf-8")
    a, b = alt.split("\n"), neu.split("\n")
    sa, sb = set(a), set(b)
    return {"name": p.name, "sek": round(sek, 1), "alt_quelle": (werte or {}).get("textquelle"),
            "zeilen_alt": len(a), "zeilen_neu": len(b), "weg": sum(z not in sb for z in a),
            "dazu": sum(z not in sa for z in b), "zeichen_alt": len(alt), "zeichen_neu": len(neu),
            "extra": {k: v for k, v in (extra or {}).items() if k != "korrekturen"}}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    muster = sys.argv[2] if len(sys.argv) > 2 else "*.pdf"
    dateien = sorted((f for f in BUECHER.glob(muster)
                      if f.stat().st_size <= MAX_GROESSE),
                     key=lambda f: -f.stat().st_size)
    ergebnisse = []
    t0 = time.time()
    with cf.ProcessPoolExecutor(max_workers=min(10, os.cpu_count() or 4)) as pool:
        auftraege = {pool.submit(eins, str(f), str(out)): f.name for f in dateien}
        for a in cf.as_completed(auftraege):
            try:
                e = a.result()
            except Exception as ex:
                e = {"name": auftraege[a], "fehler": repr(ex)}
            ergebnisse.append(e)
            print(f"{e.get('sek', 0):6.1f}s weg={e.get('weg')} dazu={e.get('dazu')} {e['name'][:70]}", flush=True)
    ergebnisse.sort(key=lambda e: e["name"])
    (out / "lauf.json").write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"gesamt {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
