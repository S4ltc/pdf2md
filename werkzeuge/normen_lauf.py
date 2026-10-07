"""Wandelt alle Normen-PDFs um, OHNE Originale zu verschieben (nur lesend). Schreibt je Norm eine .md und
zusammenfassung.json in den Ausgabeordner. Die Ausgaben enthalten Normtext: nie ins Repo legen (DIN-Lizenz).

Aufruf:  python werkzeuge/normen_lauf.py <ausgabeordner> [muster]
Umgebung: NORMEN (Ordner mit den PDFs), CODE_DIR (anderer Code-Stand, z.B. per `git archive` ausgepackt)."""
import concurrent.futures as cf
import json
import os
import sys
import time
from pathlib import Path

CODE_DIR = os.environ.get("CODE_DIR", str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, CODE_DIR)
NORMEN = Path(os.environ["NORMEN"]) if os.environ.get("NORMEN") else None   # Ordner mit den Norm-PDFs


def eine(pfad: str, out: str) -> dict:
    import pdf2md
    pdf2md.ONLINE_ABGLEICH = False
    p = Path(pfad)
    t0 = time.time()
    info = pdf2md.metadaten_lesen(p)
    text, quelle, extra = pdf2md.umwandeln(p, info["seiten"], None)
    if extra and extra.get("norm"):
        pdf2md.norm_uebernehmen(info, extra["norm"])
    if not info["jahr"]:
        info["jahr"] = pdf2md.jahr_finden(text)
    erg = {k: info.get(k) for k in ("titel", "autor", "jahr", "titel_quelle", "autor_quelle", "jahr_quelle", "seiten",
                                    "norm")}
    erg["neuer_name"] = (pdf2md.neuer_name(info["titel"], info["autor"], info["jahr"])
                         if info["titel"] and info["autor"] and info["jahr"] else None)
    erg.update(textquelle=quelle, name=p.name, sek=round(time.time() - t0, 1), zeichen=len(text),
               fffd=text.count("\ufffd"), kennungen=pdf2md.kennungen_sammeln(info, text))
    erg["extra"] = {k: v for k, v in (extra or {}).items() if k != "korrekturen"}
    (Path(out) / (p.stem + ".md")).write_text(text, encoding="utf-8")
    return erg


def main():
    if NORMEN is None or not NORMEN.is_dir():
        sys.exit("Bitte die Umgebungsvariable NORMEN auf den Ordner mit den Norm-PDFs setzen.")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    muster = sys.argv[2] if len(sys.argv) > 2 else "*.pdf"
    dateien = sorted(NORMEN.glob(muster), key=lambda f: -f.stat().st_size)
    ergebnisse = []
    t0 = time.time()
    with cf.ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 4)) as pool:
        auftraege = {pool.submit(eine, str(f), str(out)): f.name for f in dateien}
        for a in cf.as_completed(auftraege):
            try:
                e = a.result()
                print(f"{e['sek']:6.1f}s  {e['name']}", flush=True)
            except Exception as ex:
                print(f"FEHLER {auftraege[a]}: {ex!r}", flush=True)
                e = {"name": auftraege[a], "fehler": repr(ex)}
            ergebnisse.append(e)
    ergebnisse.sort(key=lambda e: e["name"])
    (out / "zusammenfassung.json").write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1, default=str),
                                              encoding="utf-8")
    print(f"gesamt {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
