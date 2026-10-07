"""Zaehlt verbleibende Schwaechen in einem Ausgabeordner (nur lesend): �, verdoppelte Formelzeichen, Tabellen ueber
Seitengrenzen, Zahlenzeilen ausserhalb von Tabellen, gesperrter Text, Kurzzeilen, Kopfzeilenreste.
Aufruf: python werkzeuge/schwaechen.py <ordner> [...]"""
import re, sys, collections
from pathlib import Path

SEITE = re.compile(r"<!-- Seite (\d+) -->")
MATHE_DOPPELT = re.compile(r"([\U0001D400-\U0001D7FF])\1")
GESPERRT = re.compile(r"(?:\b\w ){5,}\w\b")
ZAHLEN = re.compile(r"[-+±]?\d+(?:[.,]\d+)?")
KURZ = re.compile(r"^\S{1,2}$")

def analyse(ordner):
    s = collections.Counter()
    proben = collections.defaultdict(list)
    for f in sorted(Path(ordner).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        seiten = SEITE.split(text)
        # seiten: ['', '1', text1, '2', text2, ...]
        texte = seiten[2::2]
        s["dateien"] += 1
        s["seiten"] += len(texte)
        s["ersatz"] += text.count("�")
        if text.count("�") > 200:
            proben["ersatz"].append((f.name[:50], text.count("�")))
        s["mathe_doppelt"] += len(MATHE_DOPPELT.findall(text))
        s["leerseiten"] += sum(1 for t in texte if len(t.strip()) < 30)
        # Tabellen über Seitengrenzen: Seite endet mit Tabelle, nächste beginnt mit Tabelle gleicher Spaltenzahl
        for a, b in zip(texte, texte[1:]):
            za = [z for z in a.strip().splitlines() if z.strip()]
            zb = [z for z in b.strip().splitlines() if z.strip()]
            if not za or not zb:
                continue
            letzte_tab = next((z for z in reversed(za[-6:]) if z.startswith("|")), None)
            erste_tab = next((z for z in zb[:6] if z.startswith("|")), None)
            if letzte_tab and erste_tab and letzte_tab.count("|") == erste_tab.count("|"):
                s["tabelle_ueber_seite"] += 1
        tabellen = 0
        for t in texte:
            zeilen = t.splitlines()
            vorher = ""
            for z in zeilen:
                if z.startswith("|") and not vorher.startswith("|"):
                    tabellen += 1
                vorher = z
                if z.startswith("|"):
                    continue
                if len(ZAHLEN.findall(z)) >= 5 and len(re.sub(r"[\d\s.,+\-±]", "", z)) < len(z) * 0.4:
                    s["zahlenzeilen_ohne_tabelle"] += 1
                if GESPERRT.search(z):
                    s["gesperrt"] += 1
                if KURZ.match(z.strip()):
                    s["kurzzeilen"] += 1
                s["zeilen"] += 1
        s["tabellen"] += tabellen
        # Wiederholte Zeilen (mögliche Kopf-/Fußzeilenreste)
        z = collections.Counter(l.strip() for l in text.splitlines()
                                if 8 <= len(l.strip()) <= 80 and not l.startswith(("|", "#", "<!--")))
        rest = [(l, n) for l, n in z.items() if n >= max(5, len(texte) * 0.3)]
        s["kopf_reste"] += len(rest)
        if rest:
            proben["kopf_reste"].append((f.name[:40], rest[:2]))
    return s, proben

for ordner in sys.argv[1:]:
    s, p = analyse(ordner)
    print("==", ordner)
    for k, v in s.items():
        print(f"  {k}: {v}")
    for k, v in p.items():
        print(f"  Proben {k}:")
        for x in v[:8]:
            print("    ", x)
