"""Bibliografische Angaben fuer korrekte Quellenangaben: IEEE (Standard, deutsche Variante: "Aufl.", "Hrsg.", "S.",
"und"), APA 7 und DIN ISO 690 (Name-Jahr), dazu BibTeX fuer Citavi, Zotero und LaTeX.

Quellen ueber DOI/ISBN: Crossref (DOI, Kapitel von Sammelwerken) und die Deutsche Nationalbibliothek (ISBN; liefert
Verlag/Imprint, Ort und Auflage deutscher Buecher zuverlaessiger als Crossref).
Datenschutz: Gesendet wird ausschliesslich die DOI bzw. ISBN in der Adresse, mit einem allgemeinen User-Agent ohne
Namen, E-Mail oder Rechnerdaten. Keine Cookies, keine Titel, keine Dateinamen, kein Text aus dem Dokument.

IEEE-Formen (Titel kursiv als Markdown *...*):
  Buch:        A. Muster, *Titel: Untertitel*. Ort: Verlag, Jahr, doi: ...
  Auflage:     ..., *Titel*, 3. Aufl. Ort: Verlag, Jahr.
  Sammelwerk:  A. Muster et al., Hrsg., *Handbuch*, 12. Aufl. Ort: Verlag, Jahr.
  Kapitel:     A. Autor und B. Autor, „Kapitel“, in *Buch*, 12. Aufl., A. Muster et al., Hrsg. Ort: Verlag, Jahr, S. 1–20.
  Norm:        *Sachgebiet – ... – Titelteil*, DIN EN ISO 12345:2023-07, 2023."""
from __future__ import annotations

import concurrent.futures
import json
import re
import unicodedata
import urllib.parse
import urllib.request

USER_AGENT = "pdf2md/1.0"          # bewusst ohne Kontaktangabe (Datenschutz)
TIMEOUT = 10
MAX_KAPITEL = 400                  # hoechstens so viele Kapitel-DOIs je Buch nachschlagen
KAPITEL_STAPEL = 8                 # so viele Kapitel je Stapel; ein Stapel ganz ohne Antwort beendet das Nachschlagen
DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>()]+")
KAPITEL_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>()]+?_\d+(?![\d])")
MARC = "{http://www.loc.gov/MARC21/slim}"

_zwischenspeicher: dict[str, object] = {}


def _abrufen(url: str) -> bytes | None:
    """Laedt eine Adresse (nur DOI/ISBN darin). None bei jedem Fehler (offline, Zeitueberschreitung, 404)."""
    if url in _zwischenspeicher:
        return _zwischenspeicher[url]
    try:
        anfrage = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
            daten = antwort.read()
    except Exception:
        daten = None
    _zwischenspeicher[url] = daten
    return daten


def crossref(doi: str) -> dict | None:
    roh = _abrufen("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/:;()._-"))
    try:
        return json.loads(roh)["message"] if roh else None
    except Exception:
        return None


def _personen(eintraege: list | None) -> list[tuple[str, str]]:
    return [(p.get("given", "").strip(), p.get("family", "").strip()) for p in (eintraege or [])
            if p.get("family")]


def _ohne_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


# Zusaetze, die Kataloge als Untertitel fuehren, die aber nicht zum Titel gehoeren
KEIN_UNTERTITEL = re.compile(r"(?:Fachlicher Träger|Herausgegeben|Hrsg\.|Mit \d+ Abbildungen|With \d+ figures)", re.I)


def _titel(titel: str | None, untertitel: str | None) -> str | None:
    if titel and untertitel and untertitel.lower() not in titel.lower() and not KEIN_UNTERTITEL.match(untertitel):
        return f"{titel}: {untertitel}"
    return titel or None


def _ort(ort: str | None) -> str | None:
    """Erster Verlagsort ohne Landesangabe ("Berlin ; Heidelberg" -> "Berlin", "Wiesbaden, Germany" -> "Wiesbaden")."""
    if not ort:
        return None
    ort = re.sub(r"[\[\]]", "", re.split(r"\s*[;/]\s*", ort)[0]).strip(" :")
    return re.sub(r",\s*(?:Germany|Deutschland|Germany\.)$", "", ort) or None


def _jahr(eintrag: dict) -> str | None:
    for feld in ("published-print", "issued", "published-online"):
        teile = ((eintrag.get(feld) or {}).get("date-parts") or [[None]])[0]
        if teile and teile[0]:
            return str(teile[0])
    return None


def aus_crossref(m: dict) -> dict:
    titel = _titel(_ohne_html((m.get("title") or [""])[0]), _ohne_html((m.get("subtitle") or [""])[0]))
    isbn = next((i["value"] for i in m.get("isbn-type") or [] if i.get("type") == "print"), None) \
        or next(iter(m.get("ISBN") or []), None)
    return {"titel": titel, "autoren": _personen(m.get("author")), "herausgeber": _personen(m.get("editor")),
            "verlag": m.get("publisher"), "ort": _ort(m.get("publisher-location")),
            "auflage": str(m["edition-number"]) if m.get("edition-number") else None, "jahr": _jahr(m),
            "isbn": isbn, "doi": m.get("DOI"), "typ": m.get("type"), "seiten": m.get("page"),
            "buchtitel": _ohne_html((m.get("container-title") or [""])[0]) or None}


def dnb(isbn: str) -> dict | None:
    """Titeldaten der Deutschen Nationalbibliothek (SRU-Schnittstelle, MARC21) zu einer ISBN."""
    from defusedxml import ElementTree as ET
    ziffern = re.sub(r"[^\dXx]", "", isbn)
    roh = _abrufen("https://services.dnb.de/sru/dnb?version=1.1&operation=searchRetrieve&recordSchema=MARC21-xml"
                   f"&maximumRecords=1&query=num%3D{ziffern}")
    if not roh:
        return None
    try:
        wurzel = ET.fromstring(roh)
    except Exception:
        return None
    satz = wurzel.find(f".//{MARC}record")
    if satz is None:
        return None

    def felder(tag: str):
        return satz.findall(f"{MARC}datafield[@tag='{tag}']")

    def unter(feld, code: str) -> str | None:
        e = feld.find(f"{MARC}subfield[@code='{code}']") if feld is not None else None
        return e.text.strip() if e is not None and e.text else None

    def person(feld) -> tuple[str, str] | None:
        name = unter(feld, "a")
        if not name:
            return None
        nach, _, vor = name.partition(",")
        return vor.strip(), nach.strip()

    autoren, herausgeber = [], []
    for feld in felder("100") + felder("700"):
        rollen = {(e.text or "").strip() for e in feld.findall(f"{MARC}subfield[@code='4']")}
        rollen |= {(e.text or "").strip().lower() for e in feld.findall(f"{MARC}subfield[@code='e']")}
        p = person(feld)
        if not p:
            continue
        if rollen & {"edt", "herausgeber", "hrsg."}:
            herausgeber.append(p)
        elif not rollen or rollen & {"aut", "verfasser"}:
            autoren.append(p)
    erscheinung = next((f for f in felder("264") if f.get("ind2") == "1"), None)
    if erscheinung is None:
        erscheinung = next(iter(felder("260")), None)
    ort = unter(erscheinung, "a")
    titel = unter(next(iter(felder("245")), None), "a")
    untertitel = unter(next(iter(felder("245")), None), "b")
    return {"titel": _titel(titel, untertitel),
            "autoren": autoren, "herausgeber": herausgeber,
            "verlag": unter(erscheinung, "b"),
            "ort": _ort(ort),
            "auflage": unter(next(iter(felder("250")), None), "a"),
            "jahr": (re.search(r"\d{4}", unter(erscheinung, "c") or "") or [None])[0],
            "isbn": ziffern}


def nachschlagen(kennungen: list[str]) -> dict | None:
    """Fuehrt Crossref (DOI) und DNB (ISBN) zusammen. Verlag, Ort und Auflage kommen bevorzugt von der DNB (dort steht
    das Imprint wie im Buch, "Springer Vieweg" statt "Springer Fachmedien Wiesbaden"), Personen und DOI von Crossref."""
    cr = None
    for k in kennungen:
        if k.startswith("10.") and not KAPITEL_DOI.fullmatch(k):
            m = crossref(k)
            if m and not str(m.get("type", "")).startswith(("book-chapter", "book-part", "reference-entry")):
                cr = aus_crossref(m)
                break
    isbns = [re.sub(r"[^\dXx]", "", k) for k in kennungen if not k.startswith("10.")]
    if cr and cr.get("isbn"):
        isbns.insert(0, cr["isbn"])
    nb = None
    for isbn in dict.fromkeys(isbns):
        nb = dnb(isbn)
        if nb:
            break
    if not cr and not nb:
        return None
    daten = dict(cr or {})
    quellen = (["Crossref"] if cr else []) + (["DNB"] if nb else [])
    for feld, wert in (nb or {}).items():
        if wert and (feld in ("verlag", "ort", "auflage") or not daten.get(feld)):
            daten[feld] = wert
    daten["quelle"] = " + ".join(quellen)
    return daten


# ---------------------------------------------------------------- IEEE
def initialen(vorname: str) -> str:
    """"Hans-Jürgen" -> "H.-J.", "Alfred Herbert" -> "A. H.", "Yuri A.W." -> "Y. A. W."."""
    teile = []
    for wort in vorname.split():
        for stueck in (s for s in wort.split(".") if s):
            teile.append("-".join(h[0] + "." for h in stueck.split("-") if h))
    return " ".join(teile)


def personen_ieee(personen: list[tuple[str, str]]) -> str:
    namen = [f"{initialen(v)} {n}".strip() for v, n in personen]
    if len(namen) > 6:
        return f"{namen[0]} et al."
    if len(namen) <= 2:
        return " und ".join(namen)
    return ", ".join(namen[:-1]) + " und " + namen[-1]


def personen_aus_text(autor: str | None) -> list[tuple[str, str]]:
    """"Peter Beispiel, Anna Muster" -> [("Peter", "Beispiel"), ...]: Notbehelf ohne Online-Daten."""
    ergebnis = []
    for name in re.split(r",\s*|\s+und\s+|\s*;\s*", autor or ""):
        name = re.sub(r"\bet al\.?", "", name).strip()
        if name:
            vor, _, nach = name.rpartition(" ")
            ergebnis.append((vor, nach))
    return ergebnis


def auflage_ieee(auflage: str | None) -> str | None:
    """"3., überarbeitete Auflage" / "3" -> "3. Aufl."; die erste Auflage wird nicht genannt."""
    m = re.match(r"\s*(\d+)", auflage or "")
    return f"{m.group(1)}. Aufl." if m and int(m.group(1)) > 1 else None


def _erscheinung(d: dict) -> str:
    ort, verlag = d.get("ort"), d.get("verlag")
    return f"{ort}: {verlag}" if ort and verlag else (verlag or ort or "")


def ieee_buch(d: dict) -> str:
    titel = f"*{d['titel']}*"
    auflage = auflage_ieee(d.get("auflage"))
    if d.get("autoren"):
        kopf = personen_ieee(d["autoren"]) + ", "
    elif d.get("herausgeber"):
        kopf = personen_ieee(d["herausgeber"]) + ", Hrsg., "
    else:
        kopf = ""
    teil = kopf + titel + (f", {auflage}" if auflage else ".")          # "3. Aufl." endet schon mit Punkt
    hinten = ", ".join(x for x in (_erscheinung(d), d.get("jahr") or "") if x)
    if d.get("doi"):
        hinten += f", doi: {d['doi']}"
    return f"{teil} {hinten}." if hinten else teil


def ieee_kapitel(k: dict, buch: dict) -> str:
    auflage = auflage_ieee(buch.get("auflage"))
    teile = [f"{personen_ieee(k['autoren'])}, „{k['titel']}“, in *{buch['titel']}*"]
    if auflage:
        teile.append(auflage)
    if buch.get("herausgeber"):
        teile.append(personen_ieee(buch["herausgeber"]) + ", Hrsg")
    text = ", ".join(teile) + ". " + ", ".join(x for x in (_erscheinung(buch), buch.get("jahr") or "") if x)
    if k.get("seiten"):
        text += ", S. " + k["seiten"].replace("-", "–")
    if k.get("doi"):
        text += f", doi: {k['doi']}"
    return text + "."


def ieee_norm(norm: dict) -> str:
    nummer = f"{norm['bezeichnung']}:{norm['ausgabe']}"
    if norm.get("entwurf"):
        nummer += " (Entwurf)"
    titel = norm.get("titel")
    return (f"*{titel}*, {nummer}, {norm['jahr']}." if titel else f"{nummer}, {norm['jahr']}.")


# ---------------------------------------------------------------- APA 7 und DIN ISO 690 (Name-Jahr), Auswahl
STILE = {"ieee": "IEEE", "apa": "APA 7", "din": "DIN ISO 690"}      # Einstellung pdf2md.ZITIERSTIL -> Name im Kopfblock


def _auflage_nr(auflage: str | None) -> str | None:
    m = re.match(r"\s*(\d+)", auflage or "")
    return m.group(1) if m and int(m.group(1)) > 1 else None


def _seiten(seiten: str | None) -> str | None:
    return seiten.replace("-", "–") if seiten else None


def personen_apa(personen: list[tuple[str, str]]) -> str:
    """"Muster, H. D., & Beispiel, S."; ab 21 Personen die ersten 19, "…" und die letzte (APA 7)."""
    namen = [f"{n}, {initialen(v)}" if initialen(v) else n for v, n in personen]
    if len(namen) > 20:
        return ", ".join(namen[:19]) + ", … " + namen[-1]
    return namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + ", & " + namen[-1]


def _apa_vorn(personen: list[tuple[str, str]]) -> str:
    """Herausgeber im Kapitel: "P. Sommer & J. Winter", "A. A, B. B, & C. C"."""
    namen = [f"{initialen(v)} {n}".strip() for v, n in personen]
    if len(namen) <= 2:
        return " & ".join(namen)
    return ", ".join(namen[:-1]) + ", & " + namen[-1]


def _apa_titel(titel: str, auflage: str | None, seiten: str | None = None) -> str:
    zusatz = [f"{nr}. Aufl." for nr in [_auflage_nr(auflage)] if nr] + ([f"S. {_seiten(seiten)}"] if seiten else [])
    return f"*{titel}*" + (f" ({', '.join(zusatz)})" if zusatz else "")


def _apa_ende(verlag: str | None, doi: str | None) -> str:
    return (f" {verlag}." if verlag else "") + (f" https://doi.org/{doi}" if doi else "")


def apa_buch(d: dict) -> str:
    jahr = f"({d.get('jahr') or 'o. J.'})"
    titel = _apa_titel(d["titel"], d.get("auflage"))
    if d.get("autoren"):
        text = f"{personen_apa(d['autoren'])} {jahr}. {titel}."
    elif d.get("herausgeber"):
        text = f"{personen_apa(d['herausgeber'])} (Hrsg.). {jahr}. {titel}."
    else:
        text = f"{titel}. {jahr}."
    return text + _apa_ende(d.get("verlag"), d.get("doi"))


def apa_kapitel(k: dict, buch: dict) -> str:
    hrsg = f"{_apa_vorn(buch['herausgeber'])} (Hrsg.), " if buch.get("herausgeber") else ""
    text = (f"{personen_apa(k['autoren'])} ({buch.get('jahr') or 'o. J.'}). {k['titel']}. In {hrsg}"
            f"{_apa_titel(buch['titel'], buch.get('auflage'), k.get('seiten'))}.")
    return text + _apa_ende(buch.get("verlag"), k.get("doi"))


def _norm_herausgeber(norm: dict) -> str:
    return norm.get("herausgeber") or re.sub(r"^E\s+", "", norm["bezeichnung"]).split()[0]


def apa_norm(norm: dict) -> str:
    nummer = f"{norm['bezeichnung']}:{norm['ausgabe']}" + (", Entwurf" if norm.get("entwurf") else "")
    kopf = f"{_norm_herausgeber(norm)}. ({norm['jahr']})."
    return f"{kopf} *{norm['titel']}* ({nummer})." if norm.get("titel") else f"{kopf} *{nummer}*."


def personen_din(personen: list[tuple[str, str]]) -> str:
    """"MUSTER, Hans Dieter und Stefan BEISPIEL"; mehr als drei: die erste mit "et al." (DIN ISO 690)."""
    vor, nach = personen[0]
    erste = f"{nach.upper()}, {vor}" if vor else nach.upper()
    if len(personen) > 3:
        return erste + " et al."
    rest = [f"{v} {n.upper()}".strip() for v, n in personen[1:]]
    return erste if not rest else ", ".join([erste] + rest[:-1]) + " und " + rest[-1]


def _din_vorn(personen: list[tuple[str, str]]) -> str:
    namen = [f"{v} {n.upper()}".strip() for v, n in personen]
    if len(namen) > 3:
        return namen[0] + " et al."
    return namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " und " + namen[-1]


def din_buch(d: dict) -> str:
    jahr = d.get("jahr") or "o. J."
    if d.get("autoren"):
        teile = [f"{personen_din(d['autoren'])}, {jahr}.", f"*{d['titel']}*."]
    elif d.get("herausgeber"):
        teile = [f"{personen_din(d['herausgeber'])}, Hrsg., {jahr}.", f"*{d['titel']}*."]
    else:
        teile = [f"*{d['titel']}*, {jahr}."]
    nr = _auflage_nr(d.get("auflage"))
    teile += [f"{nr}. Aufl."] if nr else []
    teile += [_erscheinung(d) + "."] if _erscheinung(d) else []
    teile += [f"ISBN {d['isbn']}."] if d.get("isbn") else []
    teile += [f"DOI: {d['doi']}"] if d.get("doi") else []
    return " ".join(teile)


def din_kapitel(k: dict, buch: dict) -> str:
    hrsg = f"{_din_vorn(buch['herausgeber'])}, Hrsg. " if buch.get("herausgeber") else ""
    teile = [f"{personen_din(k['autoren'])}, {buch.get('jahr') or 'o. J.'}.", f"{k['titel']}.",
             f"In: {hrsg}*{buch['titel']}*."]
    nr = _auflage_nr(buch.get("auflage"))
    teile += [f"{nr}. Aufl."] if nr else []
    ort = ", ".join(x for x in (_erscheinung(buch), f"S. {_seiten(k['seiten'])}" if k.get("seiten") else "") if x)
    teile += [ort + "."] if ort else []
    teile += [f"DOI: {k['doi']}"] if k.get("doi") else []
    return " ".join(teile)


def din_norm(norm: dict) -> str:
    nummer = f"{norm['bezeichnung']}:{norm['ausgabe']}" + (" (Entwurf)" if norm.get("entwurf") else "")
    return f"{nummer}, {norm['jahr']}." + (f" *{norm['titel']}*." if norm.get("titel") else "")


def buch(d: dict, stil: str = "ieee") -> str:
    return {"apa": apa_buch, "din": din_buch}.get(stil, ieee_buch)(d)


def kapitel(k: dict, b: dict, stil: str = "ieee") -> str:
    return {"apa": apa_kapitel, "din": din_kapitel}.get(stil, ieee_kapitel)(k, b)


def norm(n: dict, stil: str = "ieee") -> str:
    return {"apa": apa_norm, "din": din_norm}.get(stil, ieee_norm)(n)


# ---------------------------------------------------------------- BibTeX (Citavi, Zotero, LaTeX)
BIB_MASKE = str.maketrans({"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"})
UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
FUELLWOERTER = {"der", "die", "das", "des", "dem", "den", "ein", "eine", "the", "and", "und", "von", "zur", "zum", "mit",
                "für", "auf", "aus", "bei", "for", "with"}


def _bib(text: str) -> str:
    return str(text).translate(BIB_MASKE)


def _schluesselteil(text: str) -> str:
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFC", text).translate(UMSCHRIFT))
    return re.sub(r"[^a-z0-9-]", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def bibtex_schluessel(personen: list[tuple[str, str]], jahr: str | None, titel: str) -> str:
    """"muster2016beispielkunde": Nachname der ersten Person, Jahr, erstes Titelwort (ohne Artikel)."""
    wort = next((w for w in re.findall(r"[^\W\d_]+", titel or "") if len(w) >= 3 and w.lower() not in FUELLWOERTER), "")
    return (_schluesselteil(personen[0][1]) if personen else "") + (jahr or "") + _schluesselteil(wort) or "eintrag"


def _bib_personen(personen: list[tuple[str, str]]) -> str:
    return " and ".join(_bib(f"{n}, {v}" if v else n) for v, n in personen)


def _bib_eintrag(typ: str, schluessel: str, felder: list[tuple[str, str | None]]) -> str:
    return "@" + typ + "{" + schluessel + ", " + ", ".join(f"{k} = {{{v}}}" for k, v in felder if v) + "}"


def bibtex_buch(d: dict) -> str:
    personen = d.get("autoren") or d.get("herausgeber") or []
    return _bib_eintrag("book", bibtex_schluessel(personen, d.get("jahr"), d["titel"]), [
        ("author", _bib_personen(d["autoren"]) if d.get("autoren") else None),
        ("editor", _bib_personen(d["herausgeber"]) if d.get("herausgeber") else None),
        ("title", "{" + _bib(d["titel"]) + "}"),          # doppelte Klammern: Grossschreibung bleibt (deutsche Titel)
        ("edition", _auflage_nr(d.get("auflage"))),
        ("publisher", _bib(d["verlag"]) if d.get("verlag") else None),
        ("address", _bib(d["ort"]) if d.get("ort") else None),
        ("year", d.get("jahr")), ("isbn", d.get("isbn")), ("doi", d.get("doi"))])


def bibtex_norm(norm: dict) -> str:
    herausgeber = _norm_herausgeber(norm)
    nummer = (re.search(r"\d+(?:-\d+)*", norm["bezeichnung"]) or [""])[0]
    return _bib_eintrag("standard", f"{_schluesselteil(herausgeber)}{nummer}_{norm['jahr']}", [
        ("title", "{" + _bib(norm["titel"]) + "}" if norm.get("titel") else None),
        ("number", _bib(f"{norm['bezeichnung']}:{norm['ausgabe']}")), ("organization", _bib(herausgeber)),
        ("year", norm["jahr"]), ("note", "Entwurf" if norm.get("entwurf") else None)])


def ist_sammelwerk(d: dict | None) -> bool:
    return bool(d and (d.get("typ") in ("edited-book", "reference-book") or (d.get("herausgeber")
                                                                             and not d.get("autoren"))))


# ---------------------------------------------------------------- Kapitel von Sammelwerken im Text
MARKER = re.compile(r"<!-- (?:Seite \S+ \(PDF \d+\)|PDF-Seite \d+|Seite \d+) -->")


def kapitel_einfuegen(text: str, buch: dict, stil: str = "ieee") -> tuple[str, int]:
    """Bei Sammelwerken (Handbuecher, Atlanten) hat jedes Kapitel eigene Autoren und wird einzeln zitiert.
    Die Kapitel-DOI steht auf der ersten Kapitelseite; dort kommt die Quellenangabe des Kapitels als Kommentar hinter
    den Seitenmarker: <!-- Kapitelquelle (IEEE): ... --> (bzw. im gewaehlten Stil). Gibt (Text, Anzahl
    eingefuegter Kapitel) zurueck."""
    if not ist_sammelwerk(buch) or not buch.get("doi"):
        return text, 0
    praefix = buch["doi"] + "_"
    funde = []                                   # (Position im Text, DOI), je DOI nur die erste Stelle
    gesehen = set()
    for m in KAPITEL_DOI.finditer(text):
        doi = m.group(0).rstrip(".,;")
        if doi.lower().startswith(praefix.lower()) and doi not in gesehen:
            gesehen.add(doi)
            funde.append((m.start(), doi))
    funde = funde[:MAX_KAPITEL]
    if not funde:
        return text, 0
    # in Stapeln: bleibt ein ganzer Stapel ohne Antwort (Netz weg, Dienst gestoert), wird nicht weiter gefragt, sonst
    # warteten bis zu 400 Kapitel je TIMEOUT Sekunden und der Lauf liesse sich lange nicht abbrechen (Haertetest)
    daten: list = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(funde), KAPITEL_STAPEL):
            stapel = list(pool.map(lambda f: crossref(f[1]), funde[start:start + KAPITEL_STAPEL]))
            daten += stapel
            if not any(stapel):
                daten += [None] * (len(funde) - len(daten))
                break
    einfuegen = []                               # (Position, Zeile)
    for (pos, doi), m in zip(funde, daten):
        if not m or not m.get("author"):
            continue
        k = aus_crossref(m)
        k["doi"] = doi
        zeile = f"<!-- Kapitelquelle ({STILE.get(stil, 'IEEE')}): {kapitel(k, buch, stil)} -->"
        marker = None
        for marker in MARKER.finditer(text, 0, pos):
            pass
        if marker is None:
            continue
        ende = marker.end()
        if text[ende:ende + 1] == "\n":        # Marker am Zeilenanfang: Kommentar direkt darunter
            einfuegen.append((ende + 1, zeile + "\n"))
        else:                                   # Marker mitten im Satz: hinter die Zeile mit der DOI
            zeilenende = text.find("\n", pos)
            einfuegen.append((len(text) if zeilenende < 0 else zeilenende + 1, zeile + "\n"))
    for pos, zeile in sorted(einfuegen, reverse=True):
        text = text[:pos] + zeile + text[pos:]
    return text, len(einfuegen)
