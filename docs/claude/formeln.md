# Formelsatz und Formelreparatur (`formelsatz.py`, `formeln.py`)

Aus CLAUDE.md ausgelagert. Vor einer Änderung an diesem Teil lesen; neue Messungen und Fallen hier eintragen (Zahlen mit Anzahl Bücher/Normen, Beispiele neutral, echte Titel nur in `CLAUDE.local.md`).

## Formelsatz (`formelsatz.py`)

- Laeuft im zweiten Durchgang von `_pdfium_seiten` auf jeder Seite mit Text (nach zeichen.py, vor tabellen.py, damit Zellen "$^{a}$" bekommen). Seiten mit nur einer Schriftgroesse (Textobjekte) und ohne Striche werden uebersprungen. Kosten ~20 ms/Seite (Buecher insgesamt etwa doppelte Laufzeit).
- Hoch/tief: kleineres Zeichen (<=0,85) gegen den naechsten groesseren NACHBARN (nicht die Zeilenmitte: PDFium legt Nenner, "=" und Zaehler in eine Zeile, Fussnoten nebeneinander). PDFium erzeugt Leerzeichen zwischen Zeichen und Index; `_getrennt()` ignoriert sie bei schmaler Luecke. Index+Exponent am selben Zeichen stehen in x durcheinander -> erst alle tiefen, dann alle hohen (`s_{irr,12}^{R}`). Der Nachbar zaehlt nur, wenn er Buchstabe/Ziffer/Klammer ist (`_kann_basis`), der Index rechts davon steht (Fussnotenzeichen links) und senkrecht ueberlappt (Satzzeichen ausgenommen): sonst wurden die Ziffern der Dokumentnummer unter dem Strichcode des Norm-Deckblatts zu Indizes ("428$_{94}$7").
- Ausgabe ausserhalb von Formeln: die Index-Gruppe wird an ihr Bezugszeichen gehaengt (auch wenn PDFium sie in eine eigene Zeile setzt, "Ṡ R" / "irr,12"); `_zeilen()` haengt reine Klein-Zeilen (Exponent "2" von "m²") an die Nachbarzeile.
- Brueche: Striche sind Pfade ODER 0,5 pt hohe Bilder (TeX). Kein Bruch: Strich endet an/kreuzt senkrechte Linie, >=3 gleich lange Striche uebereinander (Tabellenzeilen), Strich laenger als Zaehler/Nenner + 2 Schriftgroessen, Spaltenluecken, mehr als 2 Zeilen, >=3 Woerter mit >=4 Buchstaben (Ueberschrift ueber Linie). Ohne diese Regeln wurden Dampftafeln zu `\frac{\frac{\frac{...`.
- CMEX-Schrift: "Z"/"R"/"P"/"X" (gross) sind ∫/∑ (`CMEX`-Tabelle, nur bei Schriftname CMEX). Integralgrenzen stehen rechts, nicht ueber/unter.
- Formelreparatur und Formelsatz: `formeln.Reparatur` ist geteilt in `analysieren()` (zwischen Durchgang 1 und 2) und `aufbauen()`; der Formelsatz holt reparierte Zeichen ueber `zuordnung_fuer(seite)`, sonst stuende in neu gesetzten Formeln "D" statt "=" (MathTime). Unlesbares ohne Zuordnung: Platzhalter `k:code`, aufgeloest in `formeln.aufbauen` bzw. `_pdfium_text`.
- `UNSICHER` ("⚠[Formel unsicher] ") vor Zeilen mit `$...$` die "�" enthalten (`_unsichere_formeln_markieren`) oder mit unsicherem Bruch.

## Formelreparatur (`formeln.py`)

- Weg A: Glyphnamen aus dem CFF-Schriftprogramm (nur ohne `/ToUnicode`, exakt).
- Weg B: Formvergleich (gerenderte Probe gegen STIX/DejaVu, Abstimmung je (Schrift, PDFium-Zeichen)).
- Schwellen `MIN_WERT=0.6`, `MIN_MARGE=0.06` sind an zwei unabhängigen Datensätzen gemessen; nicht lockern ohne neue Messung.
- Mathezeichen unter Steuercode werden nie stillschweigend gelöscht; Buchstaben und Ziffern werden nie durch andere Buchstaben oder `�` ersetzt.
- MathTime-Schriften erkennt `MT2(?=[A-Za-z])|MTEX|MTMI|MTSY|MathTime`; `TimesNewRomanPSMT2` und `ArialMT2` dürfen nicht treffen.
- Code 2 ist zweierlei: ein echtes Zeichen der Schrift (MathTime: Malpunkt) ODER PDFiums Markierung einer Silbentrennung (`FPDFText_IsHyphen`, auch mitten in der Zeile, wenn PDFium Zeilen zusammenhaengt). `_zeichen_der_seite` speichert die Markierung als U+FFFE wie `get_text_range`; vorher fand der Formvergleich in TeX-Textschriften (SFRM/CMR gelten als `MATHESCHRIFT`) dafuer "-" und es blieb "zeit-lich" (gemessen: rund 10.000 zerteilte Woerter, fast alle in drei Buechern). Auch Platzhalter aus neu gesetzten Formelzeilen laufen ueber `_trennzeichen()`.
- PDFium-Fallen: `FPDFText_GetFontSize` ist bei TeX-PDFs oft 1 (echte Größe = FontSize × Textmatrix); Zeichen außerhalb der Basisebene kommen als UTF-16-Hälften (`chr()` einzeln ergibt ungültigen Text und bricht das Speichern ab); `get_text_range` versteckt `\x02` (Trennstrich/Umlaut) als `￾`.
