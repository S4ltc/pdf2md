"""Normen erkennen (DIN, EN, ISO, IEC, VDI ...): Nummer, Ausgabe, Titel, Herausgeber.

Die PDF-Metadaten von Normen sind fast immer leer oder unbrauchbar (Titel "CEN/TC 121" mit Autor "klar irene", Titel
"Datum:2009 April"). Auch der ©-Vermerk taugt nicht fuer das Jahr: auf der Titelseite folgt "Ersatz fuer ...:2014-06",
und das Wasserzeichen des Downloads nennt das Druckdatum. Normen tragen ihre Angaben aber sehr einheitlich:

- Kopfzeile fast jeder Seite: "DIN EN ISO 12345:2023-07" (Nummer und Ausgabe; Entwurf: "E DIN ...")
- erstes Lesezeichen: dasselbe, manchmal mit "_" statt Leerzeichen ("DIN_EN_34567-2:2019-10")
- Dateiname des DIN-Media-/Beuth-Downloads: "DIN EN ISO 12345_2023-07-00_DE_1234567.pdf"
- Titelseite: die Nummer in grosser Schrift, direkt darunter der deutsche Titel in derselben Schrift, danach
  englisch und franzoesisch in kleinerer Schrift. Aeltere Titelseiten (bis etwa 2004) haben den Titel ohne
  Nummernzeile unter "DEUTSCHE NORM".
"""

import re
from collections import Counter
from pathlib import Path

import pypdfium2.raw as raw

_GREMIUM = r"(?:DIN|EN|ISO|IEC|VDI|VDE|DVS|CEN|CLC|ASTM|SEW|VDMA|DKE|IEEE|ANSI|BS|NF|ÖNORM|OENORM|SN)"
_ZUSATZ = r"(?:SPEC|TS|TR|PAS|ISO|IEC|EN|VDE|CEN|CLC|V|IS|DIS|FDIS)"
_NUMMER = (rf"{_GREMIUM}(?:[ _/]+{_ZUSATZ})*[ _]+\d+(?:[.-]\d+)*(?:[ _]*/[ _]*A\d+)?"
           rf"(?:[ _]+(?:Beiblatt|Berichtigung|Blatt|Teil)[ _]+\d+)?")
# "E DIN EN ISO 12345:2023-07", "DIN_EN_34567-2:2019-10", "DIN EN 4567-1-8/A1:2026-05"
KOPFZEILE = re.compile(rf"\s*(?P<entwurf>E[ _]+)?(?P<nummer>{_NUMMER})[ _]*:[ _]*(?P<jahr>(?:19|20)\d\d)-(?P<monat>[01]\d)\s*")
# Dateiname des DIN-Media-/Beuth-Downloads: "DIN EN ISO 12345_2023-07-00_DE_1234567(_Draft).pdf"
DATEINAME = re.compile(rf"(?P<nummer>{_NUMMER})_(?P<jahr>(?:19|20)\d\d)-(?P<monat>[01]\d)-\d\d_[A-Z]{{2}}_\d+.*")
REF_NR = re.compile(rf"Ref\.?[ -]?Nr\.?\s*(?P<entwurf>E[ _]+)?(?P<nummer>{_NUMMER})[ _]*:[ _]*"
                    rf"(?P<jahr>(?:19|20)\d\d)-(?P<monat>[01]\d)\b")
NUMMER_ALLEIN = re.compile(rf"(?P<nummer>{_NUMMER})(?:\s+[A-Z])?\s*")   # Nummernzeile der Titelseite ("DIN EN 5678-1 D")
DEUTSCHE_NORM = re.compile(r".*DEUTSCHE NORM\b.*")
# Andere Dateinamen ("DIN_EN_ISO_12345_Berichtigung_1__2013-08.pdf", "DIN_EN_ISO_23456-1_2012_01.pdf"): nur als Notbehelf,
# denn solche Namen sind von Hand vergeben und stimmen nicht immer (gemessen: 2 von 20 mit falscher Ausgabe)
DATEINAME_FREI = re.compile(rf"(?P<nummer>{_NUMMER})_+(?P<jahr>(?:19|20)\d\d)[-_](?P<monat>[01]\d)(?:[-_].*)?")
MONATE = ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november",
          "dezember")
DATUM_DECKBLATT = re.compile(rf"(?:^|\s)(?P<monat>{'|'.join(MONATE)})\s+(?P<jahr>(?:19|20)\d\d)\b", re.IGNORECASE)
# Zeilen auf alten Titelseiten, die nie zum Titel gehoeren (Rechtevermerk, Vertrieb)
KEIN_TITEL = re.compile(r".*(?:Deutsches Institut für Normung|Vervielfältigung|Alleinverkauf|Preisgr|Vertr\.).*")
# Hier endet der deutsche Titel auf der Titelseite
TITEL_ENDE = re.compile(r"(?:Deutsche(?: und Englische)? Fassung|Englische Fassung|Identisch mit|ICS\b|Ersatz f|"
                        r"Vorgesehen als|Einspr|Mit DIN|Anwendungswarnvermerk|German version|Welding\b)")
ISO_KLAMMER = re.compile(r"\s*\((?:ISO|IEC|EN)[^()]*:\d{4}[^()]*\)\s*")   # "(ISO 12345:2023)" am Titelende
FUELLWORT_ENDE = re.compile(r"(?:\b(?:und|oder|für|von|der|die|des|den|dem|mit|zum|zur|im|in|an|auf|bei|nach|ohne|"
                            r"sowie|bzw|aus|über|unter|zu)|[,(/-])$")
SCHRIFTGROESSE_TOLERANZ = 0.6
DECKBLATT_SEITEN = 4        # so viele Seiten vom Anfang werden nach der Titelseite durchsucht


def _nummer_normieren(nummer: str) -> str:
    nummer = re.sub(r"[ _]+", " ", nummer).strip()
    return re.sub(r"\s*/\s*", "/", nummer)


def herausgeber(nummer: str) -> str:
    """Wer die Norm herausgibt (steht als 'Autor' im Namen): das erste Kuerzel, "DIN EN ISO 12345" -> "DIN"."""
    return re.match(r"[A-ZÖ]+", nummer).group(0) if re.match(r"[A-ZÖ]+", nummer) else nummer.split()[0]


def _schluessel(m: re.Match) -> tuple[bool, str, str, str]:
    return bool(m.group("entwurf")), _nummer_normieren(m.group("nummer")), m.group("jahr"), m.group("monat")


def _kopfzeilen(seiten: list[str]) -> tuple[Counter, dict]:
    """Zaehlt "Nummer:JJJJ-MM" in den ersten/letzten drei Zeilen jeder Seite. Dazu je Treffer die erste Seite."""
    zaehler: Counter = Counter()
    erste: dict = {}
    for nr, text in enumerate(seiten):
        zeilen = [z for z in text.replace("\r", "\n").split("\n") if z.strip()]
        gesehen = set()
        for z in zeilen[:3] + zeilen[-3:]:
            m = KOPFZEILE.fullmatch(z)
            if m and _schluessel(m) not in gesehen:
                gesehen.add(_schluessel(m))
                zaehler[_schluessel(m)] += 1
                erste.setdefault(_schluessel(m), nr)
    return zaehler, erste


def erkennen(pfad: Path, seiten: list[str], lesezeichen: dict | None = None) -> dict | None:
    """Erkennt eine Norm an Kopfzeilen, erstem Lesezeichen oder Dateinamen. Gibt None zurueck, wenn es keine ist, sonst
    {"nummer", "entwurf", "jahr", "monat", "ausgabe", "bezeichnung", "herausgeber", "titel", "quelle"}."""
    mit_text = sum(1 for s in seiten if s.strip())
    treffer, quelle = None, None
    kopf, erste = _kopfzeilen(seiten)
    if kopf:
        schluessel, anzahl = kopf.most_common(1)[0]
        # Bei DIN-EN-Normen steht die DIN-Kopfzeile nur auf den nationalen Vorseiten (ab Seite 2), danach die EN-Kopfzeile
        if anzahl >= max(2, 0.25 * mit_text) or (anzahl >= 2 and erste[schluessel] < DECKBLATT_SEITEN):
            treffer, quelle = schluessel, "Kopfzeile der Norm"
    if treffer is None:
        for text in seiten[:DECKBLATT_SEITEN]:          # aeltere Titelseiten: "Ref. Nr. DIN EN 5678-4:2001-02"
            m = REF_NR.search(text)
            if m:
                treffer, quelle = _schluessel(m), "Ref.-Nr. auf der Titelseite"
                break
    erstes = next(iter(sorted((lesezeichen or {}).items())), (None, []))[1]
    if treffer is None and erstes:
        m = KOPFZEILE.fullmatch(erstes[0][1])
        if m:
            treffer, quelle = _schluessel(m), "Lesezeichen der Norm"
    if treffer is None and erstes:
        # Lesezeichen nur mit Nummer ("DIN EN ISO 12345 Berichtigung 1"), die Ausgabe steht auf dem Deckblatt
        m = NUMMER_ALLEIN.fullmatch(erstes[0][1])
        datum = next((d for s in seiten[:2] for d in [DATUM_DECKBLATT.search(s)] if d), None)
        if m and datum:
            monat = f"{MONATE.index(datum.group('monat').lower()) + 1:02d}"
            treffer = (False, _nummer_normieren(m.group("nummer")), datum.group("jahr"), monat)
            quelle = "Lesezeichen und Datum auf dem Deckblatt"
    if treffer is None:
        m = DATEINAME.fullmatch(pfad.stem)
        if m:
            treffer = (False, _nummer_normieren(m.group("nummer")), m.group("jahr"), m.group("monat"))
            quelle = "Dateiname (Normen-Download)"
    if treffer is None:
        m = DATEINAME_FREI.fullmatch(pfad.stem)
        if m:
            treffer = (False, _nummer_normieren(m.group("nummer")), m.group("jahr"), m.group("monat"))
            quelle = "Dateiname"
    if treffer is None:
        return None
    entwurf, nummer, jahr, monat = treffer
    bezeichnung = ("E " if entwurf else "") + nummer
    try:
        titel = titel_lesen(pfad, nummer)
    except Exception:
        titel = None
    return {"nummer": nummer, "entwurf": entwurf, "jahr": jahr, "monat": monat, "ausgabe": f"{jahr}-{monat}",
            "bezeichnung": bezeichnung, "herausgeber": herausgeber(nummer), "titel": titel, "quelle": quelle}


def vollstaendiger_titel(norm: dict) -> str:
    """"DIN EN ISO 12345 – Klebtechnik – ..." (ohne Sachtitel nur die Nummer). Entwuerfe beginnen mit "E "."""
    return f"{norm['bezeichnung']} – {norm['titel']}" if norm.get("titel") else norm["bezeichnung"]


# ---------------------------------------------------------------- Titelseite
def _zeilen_mit_groesse(tp) -> list[tuple[str, float]]:
    """(Zeilentext, Schriftgroesse des ersten sichtbaren Zeichens) einer Seite. Die Groesse ist die wirksame Groesse
    (Schriftgroesse mal Textmatrix; manche PDFs setzen die Schrift auf 1 und skalieren ueber die Matrix)."""
    n = tp.count_chars()
    zeilen: list[tuple[str, float]] = []
    teile: list[str] = []
    groesse = None
    matrix = raw.FS_MATRIX()
    for k in range(n):
        code = raw.FPDFText_GetUnicode(tp, k)
        if code in (10, 13):
            if teile:
                zeilen.append(("".join(teile), groesse or 0.0))
            teile, groesse = [], None
            continue
        if groesse is None and code not in (32, 9, 0xA0) and raw.FPDFText_GetMatrix(tp, k, matrix):
            skala = abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5
            groesse = round(raw.FPDFText_GetFontSize(tp, k) * skala, 1)
        if 0xD800 <= code <= 0xDFFF or code < 32 and code != 9:
            continue
        teile.append(chr(code))
    if teile:
        zeilen.append(("".join(teile), groesse or 0.0))
    return [(re.sub(r"\s+", " ", t).strip(), g) for t, g in zeilen if t.strip()]


def _zusammensetzen(zeilen: list[str]) -> str:
    """Titelzeilen zu einem Titel: Zeilen mit Gedankenstrich am Ende sind Teile ("Klebtechnik –"), sonst umbrochene
    Zeilen. Aeltere Titelseiten setzen jeden Teil ohne Strich auf eine eigene Zeile, dann kommt " – " dazwischen."""
    mit_strich = any(z.rstrip().endswith(("–", "—")) for z in zeilen)
    titel = ""
    for z in zeilen:
        z = z.strip()
        if not titel:
            titel = z
        elif mit_strich or FUELLWORT_ENDE.search(titel) or z[:1].islower():
            titel += " " + z
        else:
            titel += " – " + z
    titel = titel.replace("—", "–")
    titel = ISO_KLAMMER.sub(" ", titel)
    titel = re.sub(r"\s+", " ", titel).strip(" ;,.")
    titel = re.sub(r"(?:\s*–)+$", "", titel).strip()
    return re.sub(r"(?:\s*–\s*){2,}", " – ", titel)


def _titel_aus_seite(zeilen: list[tuple[str, float]], nummer: str) -> str | None:
    kern = re.sub(r"\s+", " ", nummer)
    # 1) Nummernzeile in grosser Schrift, der Titel folgt in derselben Schrift
    for i, (text, groesse) in enumerate(zeilen):
        m = NUMMER_ALLEIN.fullmatch(text)
        if not m or _nummer_normieren(m.group("nummer")) != kern or groesse < 11:
            continue
        titel: list[str] = []
        for text2, groesse2 in zeilen[i + 1:]:
            gleich = abs(groesse2 - groesse) <= SCHRIFTGROESSE_TOLERANZ
            if not titel:
                if gleich and not TITEL_ENDE.match(text2):
                    titel.append(text2)
                continue
            if not gleich or TITEL_ENDE.match(text2):
                break
            titel.append(text2)
        if titel:
            return _zusammensetzen(titel)
    # 2) Aeltere Titelseite: Titel direkt unter "DEUTSCHE NORM", bis "Deutsche Fassung" / "ICS" / Nummer
    for i, (text, _) in enumerate(zeilen):
        if not DEUTSCHE_NORM.fullmatch(text):
            continue
        titel = []
        for text2, _ in zeilen[i + 1:]:
            ende = TITEL_ENDE.search(text2)
            if ende:
                if ende.start() > 0:
                    titel.append(text2[:ende.start()])
                break
            if kern in re.sub(r"\s+", " ", text2) or re.fullmatch(r"(?:DIN|D|ICS.*|\d.*)", text2):
                break
            if NUMMER_ALLEIN.fullmatch(text2) or KEIN_TITEL.fullmatch(text2):
                continue                                     # "EN 5678-2", Rechtevermerk: gehoeren nicht zum Titel
            titel.append(text2)
            if len(titel) > 8:
                return None                                  # das ist kein Titel mehr
        if titel:
            return _zusammensetzen(titel)
    return None


def _titel_nach_ausgabe(zeilen: list[tuple[str, float]], nummer: str) -> str | None:
    """Notbehelf: Berichtigungsvermerke vor der Titelseite nennen "DIN EN 5678-2:2001-05" und darunter den Titel
    ("Klebtechnik – ... Bauteile; Deutsche Fassung"). Gebraucht, wenn die Titelseite den deutschen Titel nicht als Text hat."""
    kern = re.sub(r"\s+", " ", nummer)
    for i, (text, _) in enumerate(zeilen):
        m = KOPFZEILE.fullmatch(text)
        if not m or _nummer_normieren(m.group("nummer")) != kern:
            continue
        titel = []
        for text2, _ in zeilen[i + 1:i + 6]:
            if KOPFZEILE.fullmatch(text2):              # die Nummer steht oben und noch einmal direkt ueber dem Titel
                titel = []
                continue
            ende = TITEL_ENDE.search(text2)
            if ende:
                if ende.start() > 0:
                    titel.append(text2[:ende.start()])
                break
            titel.append(text2)
        if titel and len(" ".join(titel)) < 300:
            return _zusammensetzen(titel)
    return None


def titel_lesen(pfad: Path, nummer: str) -> str | None:
    """Deutscher Titel von der Titelseite (erste Seiten), oder None. Erst alle Deckblattseiten nach der ueblichen
    Titelseite absuchen, erst danach den Notbehelf (Berichtigungsvermerk) versuchen."""
    import pypdfium2 as pdfium
    dokument = pdfium.PdfDocument(str(pfad))
    try:
        seiten = []
        for nr in range(min(DECKBLATT_SEITEN, len(dokument))):
            seite = dokument[nr]
            tp = seite.get_textpage()
            try:
                seiten.append(_zeilen_mit_groesse(tp))
            finally:
                tp.close()
                seite.close()
    finally:
        dokument.close()
    for lesen in (_titel_aus_seite, _titel_nach_ausgabe):
        for zeilen in seiten:
            titel = lesen(zeilen, nummer)
            if titel and len(titel) >= 5:
                return titel
    return None

