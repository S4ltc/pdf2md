# Seitenzahlen und Quellenangabe (`seitenzahlen.py`, `zitierdaten.py`)

Aus CLAUDE.md ausgelagert. Vor einer Änderung an diesem Teil lesen; neue Messungen und Fallen hier eintragen (Zahlen mit Anzahl Bücher/Normen, Beispiele neutral, echte Titel nur in `CLAUDE.local.md`).

## Seitenzahlen und Zitieren (`seitenzahlen.py`, `pdf2md.seiten_zu_text`)

- Marker: `<!-- Seite S (PDF N) -->` (S = gedruckte Zahl, auch roemisch), ohne gedruckte Zahl `<!-- PDF-Seite N -->`; altes `<!-- Seite N -->` wird beim Lesen noch erkannt (`SEITENMARKER_MUSTER`). Kopfblock: `seitenzahlen:`, `zitierhinweis:`.
- Quelle 1: Seitenlabel (`FPDF_GetPageLabel`), nur wenn es nicht bloss die Position wiederholt (eine Norm: Labels 1..n, gedruckt ab PDF 10) und den Randzahlen nicht widerspricht. Quelle 2: Randzahlen-Folge mit gleichem Versatz (>=3 Belege, Luecken <=8, Dichte >=0,4; Versatz-0-Vorseiten von Normen auch mit 1 Beleg); 2 Seiten Verlaengerung; EN-Deckblatt zwischen zwei Abschnitten bekommt die 1 des folgenden.
- Gemessen (`werkzeuge/seitenpruefung.py`, Inhaltsverzeichnis gegen Lesezeichen): 8954 gleich, 25 anders, alle 25 = Lesezeichen eine Seite zu frueh. Deshalb `_lesezeichen_nachschieben()`: Titel nicht auf seiner Seite, aber auf der naechsten -> dorthin.
- `_kolumnentitel_entfernen()`: Randzeile, die mit der gedruckten Zahl beginnt/endet, nur wenn >=30 % der Seiten so eine haben (45.000 Woerter Kolumnentitel in 58 Buechern).
- `_ueber_seitenwechsel()`: Trennung "Reg-" + "ler" -> Wort an die vorige Seite; Satz laeuft weiter (vorige Zeile >=30 Zeichen ohne Satzende, kein Abb./Tabelle-Anfang, neue Seite beginnt klein) -> Marker mitten im Satz. Weiche Trennung am Seitenende wird zu "-" (`_seite_bereinigen`), PDFium haengt die Seitenzahl manchmal direkt an ("Anfor￾16", `_seitenzahl_abtrennen`).
- Pruefung: `werkzeuge/zitierpruefung.py` sucht Saetze auf der Marker-Seite (Bezug: korrigierter Seitentext, nicht Rohtext, sonst scheitert es an "Schweiflen"). Normen: 98,7 % gefunden, 0 auf falscher Seite.

## Quellenangabe (`zitierdaten.py`)

- IEEE deutsch ("Aufl.", "Hrsg.", "und", >6 Personen "et al."), Kopfblock `quellenangabe`, `verlag`, `ort`, `auflage`, `herausgeber`, `isbn`, `doi`, `zitierdaten_quelle`. Normen: `*Titel*, NUMMER:AUSGABE, JAHR.` (ohne Online).
- Verlag/Ort/Auflage bevorzugt DNB (SRU, MARC21: 264/250/700 mit `$4 edt`), Personen/DOI Crossref; Untertitel "Fachlicher Träger ..." verworfen, Ort ohne ", Germany".
- Sammelwerke (Crossref `edited-book`/`reference-book` oder nur Herausgeber): Kapitel-DOIs im Text -> `<!-- Kapitelquelle (IEEE): ... -->` hinter dem Seitenmarker der Kapitelseite.
- Datenschutz (Nutzerwunsch): nur DOI/ISBN in der URL, User-Agent `pdf2md/1.0` ohne Kontaktangabe. Test `test_user_agent_ohne_persoenliche_angaben`. Nie E-Mail o.ae. ergaenzen ("polite pool").
- „Text erneuern“ ergaenzt fehlende Felder; nur eine reine Offline-Angabe ("nur Titel, Autor und Jahr") wird ersetzt.
- Zitierstil (`ZITIERSTIL`: ieee/apa/din, `zitierdaten.STILE` = Name im Kopfblock `zitierstil:`): `zitierdaten.buch/kapitel/norm(…, stil)`; APA 7 mit "&", "(Hrsg.)", "(16. Aufl.)", DOI als https://doi.org/…, ohne Ort; DIN ISO 690 in der Name-Jahr-Form mit Nachnamen in Versalien, mehr als drei Personen "et al.". `zitierhinweis()` nennt Stil und Zitatform im Text ([Nr., S. S] / (Autor, Jahr, S. S) / (AUTOR Jahr, S. S)), Kapitelquellen tragen den Stilnamen. Stil gewechselt: `text_plan()` nimmt auch PDFs mit anderem `zitierstil` (aeltere ohne Feld = IEEE), `text_erneuern` setzt dann `quellenangabe`/`zitierstil` neu.
- BibTeX (`BIBTEX`): Feld `bibtex:` (eine Zeile), `@book` bzw. `@standard` (biblatex), Titel in doppelten Klammern (Grossschreibung), Sonderzeichen maskiert, Schluessel "muster2016beispielkunde" (Umlaute umschrieben, Fuellwoerter wie "mit" uebersprungen). Werkzeug „Literaturliste exportieren“ (`literatur_plan()`/`literatur_schreiben()`): `Literatur.bib` neben Fertig, Eintrag aus `bibtex:` oder aus den Kopfblock-Feldern (`_bibtex_aus_kopf`, Normen ueber `norm:`), doppelte Schluessel bekommen b, c, ….
