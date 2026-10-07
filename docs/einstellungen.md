# Einstellungen

Erzeugt aus `einstellungen.py` mit `python werkzeuge/einstellungen_liste.py`. Im Fenster stehen die Texte als Tooltip, gespeichert werden Abweichungen in `Einstellungen.json` neben dem Programm.

93 Einstellungen, davon 17 normal und 76 für Experten (an 58 Büchern gemessen).

## Normal

### Umwandlung

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| PDF-Engine | `pdf2md.PDF_ENGINE` | PDFium | PDFium / MarkItDown | Womit der Text aus PDFs gelesen wird. MarkItDown nur wählen, wenn PDFium eine Datei nicht lesen kann; es klebt Wörter zusammen und macht aus Formeln Tabellen. |
| Parallele Prozesse | `pdf2md.MAX_PROZESSE` | Anzahl der Prozessorkerne | 1 bis doppelte Kernzahl (Schritt 1) | So viele Prozessorkerne nutzt der MarkItDown-Weg für große PDFs gleichzeitig. Verringern, wenn der Rechner während eines Laufs zu träge wird. |

### Text und Seiten

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Überschriften aus Lesezeichen | `pdf2md.UEBERSCHRIFTEN_AUS_LESEZEICHEN` | an | an/aus | Macht aus den Lesezeichen des PDFs Markdown-Überschriften. Ausschalten, wenn die Lesezeichen eines PDFs unbrauchbar sind. |
| Überschriften aus der Schriftgröße | `pdf2md.UEBERSCHRIFTEN_AUS_SCHRIFT` | an | an/aus | Hat ein PDF keine Lesezeichen, werden deutlich größere Zeilen und fette Abschnittsnummern („2.4 …“) zu Überschriften. Ausschalten, wenn dabei zu viele falsche Überschriften entstehen. |
| Fett und kursiv übernehmen | `pdf2md.HERVORHEBUNGEN` | an | an/aus | Übernimmt fette und kursive Wortgruppen als **fett** und *kursiv*, kursive Formelzeichen ausgenommen. Ausschalten, wenn reiner Text ohne Markdown-Betonung gebraucht wird. |
| Spaltenreihenfolge korrigieren | `pdf2md.SPALTENREIHENFOLGE` | an | an/aus | Bringt zweispaltige Seiten in Lesereihenfolge, wenn das PDF die rechte Spalte vor der linken liefert. Nur zur Fehlersuche ausschalten. |
| Zeichenfehler korrigieren | `pdf2md.ZEICHEN_KORRIGIEREN` | an | an/aus | Korrigiert getrennte Umlaute wie „fü r“, Symbol- und Wingdings-Zeichen sowie Texte in falscher Kodierung. Nur zur Fehlersuche ausschalten. |

### Seitenzahlen und Zitieren

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Seitenmarker | `pdf2md.SEITENMARKER` | an | an/aus | Setzt vor jede Seite einen Marker mit gedruckter und PDF-Seitenzahl, damit eine KI mit Seitenangabe zitieren kann. Nur ausschalten, wenn keine Seitenangaben gebraucht werden. |
| Gedruckte Seitenzahlen | `pdf2md.GEDRUCKTE_SEITENZAHLEN` | an | an/aus | Ermittelt die gedruckte Seitenzahl aus dem Seitenlabel oder der Kopf- und Fußzeile. Ausgeschaltet nennen die Marker nur die Position im PDF. |

### Formeln

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Formelzeichen reparieren | `pdf2md.FORMELN_REPARIEREN` | an | an/aus | Repariert unlesbare oder vertauschte Zeichen in Formelschriften über Glyphnamen und Formvergleich. Nur ausschalten, wenn ein Buch damit sehr langsam wird oder Fehler auftreten. |
| Formelsatz als LaTeX | `pdf2md.FORMELSATZ` | an | an/aus | Setzt Indizes, Exponenten, Brüche, Wurzeln und Summen als LaTeX und markiert unsichere Formeln. Ausschalten, wenn reiner Text ohne LaTeX gebraucht wird. |

### Tabellen

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Tabellen erkennen | `pdf2md.TABELLEN_ERKENNEN` | an | an/aus | Setzt Tabellen mit gezeichneten Linien als Markdown-Tabellen. Ausschalten, wenn die Tabellen als Fließtext besser lesbar sind. |

### Normen

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Normen erkennen | `pdf2md.NORMEN_ERKENNEN` | an | an/aus | Erkennt DIN-, EN- und ISO-Normen und übernimmt Nummer, Ausgabe, Titel und Herausgeber von der Norm selbst. Ausschalten, wenn ein Buch fälschlich als Norm erkannt wird. |

### Metadaten und Online

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Online-Abgleich | `pdf2md.ONLINE_ABGLEICH` | an | an/aus | Schlägt fehlende Angaben und die Quellenangabe bei Crossref und der DNB nach; gesendet wird nur DOI oder ISBN. Ausschalten für Läufe ganz ohne Internet. |
| Wartezeit online | `pdf2md.ONLINE_TIMEOUT` | 10 s | 2 bis 60 s (Schritt 1) | So lange wird auf eine Antwort von Crossref oder der DNB gewartet. Erhöhen bei langsamer Verbindung. |
| Jahr aus Erstellungsdatum | `pdf2md.JAHR_AUS_ERSTELLDATUM` | aus | an/aus | Nimmt das Erstellungsdatum der Datei als Erscheinungsjahr, wenn sonst keins gefunden wird. Das ist meist falsch, deshalb nur für eigene Dokumente einschalten. |

### Ablage

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Länge des Dateinamens | `pdf2md.MAX_NAME_LEN` | 120 Zeichen | 60 bis 200 Zeichen (Schritt 5) | Höchstlänge des neuen Dateinamens ohne Endung; gekürzt wird nur der Titel. Verringern, wenn Pfade zu lang werden. |

## Experte

### Umwandlung

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Parallel ab | `pdf2md.PARALLEL_AB_SEITEN` | 150 Seiten | 20 bis 1000 Seiten (Schritt 10) | Ab dieser Seitenzahl teilt der MarkItDown-Weg ein PDF in Pakete und wandelt sie parallel um. Beim PDFium-Weg ohne Wirkung. |
| Seiten je Paket | `pdf2md.SEITEN_PRO_PAKET` | 40 Seiten | 10 bis 200 Seiten (Schritt 5) | Seiten je Paket beim parallelen MarkItDown-Weg. Größere Pakete brauchen mehr Speicher je Prozess. |

### Text und Seiten

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Länge der Überschrift | `pdf2md.MAX_UEBERSCHRIFT` | 200 Zeichen | 50 bis 500 Zeichen (Schritt 10) | Längere Lesezeichen-Titel werden abgeschnitten. Erhöhen, wenn lange Kapiteltitel gekürzt erscheinen. |
| Kopf- und Fußzeilen: Mindestanzahl | `pdf2md.KOPF_FUSS_MIN_SEITEN` | 8 Seiten | 3 bis 30 Seiten (Schritt 1) | So oft muss eine Zeile am Seitenrand vorkommen, damit sie als Kopf- oder Fußzeile entfernt wird. Erhöhen, wenn echter Text fehlt, senken, wenn Kopfzeilen stehen bleiben. |
| Kopf- und Fußzeilen: Höchstlänge | `pdf2md.KOPF_FUSS_MAX_LAENGE` | 300 Zeichen | 50 bis 600 Zeichen (Schritt 10) | Längere Zeilen gelten nie als Kopf- oder Fußzeile. Nur für sehr lange Wasserzeichen erhöhen. |
| Kopf- und Fußzeilen: Randzeilen | `pdf2md.KOPF_FUSS_RAND` | 3 Zeilen | 1 bis 6 Zeilen (Schritt 1) | So viele Zeilen am Seitenanfang und -ende werden auf Kopf- und Fußzeilen geprüft. Erhöhen, wenn Kopfzeilen hinter Spalten- oder Bildtext stehen bleiben. |
| Überschrift: Zeilen im Text | `pdf2md.TITEL_MAX_ZEILEN` | 5 Zeilen | 1 bis 10 Zeilen (Schritt 1) | So viele Zeilen darf ein im Text umbrochener Lesezeichen-Titel umfassen. Erhöhen, wenn lange Titel doppelt erscheinen. |
| Überschrift: Schriftgröße | `schriftbild.GROESSER` | 1,15 × | 1,05 bis 1,6 × (Schritt 0,05) | So viel größer als der Fließtext muss eine Zeile sein, um ohne Lesezeichen als Überschrift zu gelten (1,15 = 15 % größer). Erhöhen, wenn große Bildbeschriftungen zu Überschriften werden. |
| Hervorhebung: Mindestlänge | `schriftbild.MIN_BUCHSTABEN` | 4 Buchstaben | 2 bis 10 Buchstaben (Schritt 1) | So viele Buchstaben braucht ein einzelnes fettes oder kursives Wort, um übernommen zu werden; kürzere sind meist Formelzeichen. Erhöhen, wenn Variablen wie *Fmax* betont erscheinen. |

### Seitenzahlen und Zitieren

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Kolumnentitel: Randzeilen | `pdf2md.KOLUMNENTITEL_RAND` | 2 Zeilen | 1 bis 5 Zeilen (Schritt 1) | So viele Zeilen oben und unten können einen Kolumnentitel mit Seitenzahl enthalten. Erhöhen, wenn Kolumnentitel im Text stehen bleiben. |
| Kolumnentitel: Anteil der Seiten | `pdf2md.KOLUMNENTITEL_ANTEIL` | 0,3 | 0,05 bis 0,9 (Schritt 0,05) | Kolumnentitel werden nur entfernt, wenn mindestens dieser Anteil der Seiten einen hat. Senken, wenn sie in kurzen Dokumenten stehen bleiben. |
| Suchzeilen am Rand | `seitenzahlen.RAND` | 4 Zeilen | 1 bis 10 Zeilen (Schritt 1) | So viele Zeilen am Seitenanfang und -ende werden nach der gedruckten Seitenzahl durchsucht. Erhöhen, wenn Seitenzahlen unter Fußnoten stehen. |
| Belege je Abschnitt | `seitenzahlen.MIN_BELEGE` | 3 Seiten | 1 bis 10 Seiten (Schritt 1) | So viele Seiten müssen denselben Versatz zwischen gedruckter und PDF-Seite zeigen, damit ein Abschnitt gilt. Senken für Dokumente mit wenigen Seitenzahlen. |
| Dichte der Belege | `seitenzahlen.MIN_DICHTE` | 0,4 | 0,05 bis 1 (Schritt 0,05) | Mindestanteil der Seiten eines Abschnitts mit lesbarer Seitenzahl. Senken für bildreiche Bücher. |
| Lücke ohne Zahl | `seitenzahlen.MAX_LUECKE` | 8 Seiten | 1 bis 30 Seiten (Schritt 1) | So viele Seiten ohne lesbare Zahl darf ein Abschnitt überbrücken. Erhöhen für Bücher mit langen Bildstrecken. |
| Verlängerung | `seitenzahlen.VERLAENGERUNG` | 2 Seiten | 0 bis 10 Seiten (Schritt 1) | So viele Seiten vor und nach einem Abschnitt bekommen ebenfalls eine berechnete Zahl. Senken, wenn Kapitelanfänge falsche Zahlen bekommen. |
| Label: Übereinstimmung | `seitenzahlen.MIN_UEBEREINSTIMMUNG` | 0,8 | 0,3 bis 1 (Schritt 0,05) | So oft müssen Seitenlabel des PDFs und gedruckte Zahlen übereinstimmen, damit das Label gilt. Senken, wenn brauchbare Labels verworfen werden. |
| Normen: Vorseiten | `seitenzahlen.VORSEITEN` | 6 Seiten | 0 bis 20 Seiten (Schritt 1) | Nationale Vorseiten von Normen bis zu dieser Länge dürfen schon mit einem Beleg nummeriert werden. Senken, wenn Normdeckblätter falsche Zahlen bekommen. |

### Formeln

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Formvergleich: Proben je Zeichen | `formeln.MAX_PROBEN` | 8 | 2 bis 30 (Schritt 1) | So viele Vorkommen je unlesbarem Zeichen werden gerendert und verglichen. Mehr Proben sind sicherer, aber langsamer. |
| Formvergleich: Renderskala | `formeln.RENDER_SKALA` | 4 × | 2 bis 8 × (Schritt 1) | Vergrößerung beim Rendern der Seiten für den Formvergleich, 4 entspricht etwa 290 dpi. Höher erkennt kleine Zeichen besser, kostet aber deutlich Zeit. |
| Formvergleich: Gewicht der Lage | `formeln.GEO_GEWICHT` | 0,5 | 0 bis 2 (Schritt 0,05) | Wie stark Höhe und Lage eines Zeichens gegenüber seiner Form zählen. An zwei Datensätzen gemessen, nur mit neuer Messung ändern. |
| Formvergleich: Lage bei Akzenten | `formeln.GEO_RELIEF` | 0,2 | 0 bis 1 (Schritt 0,05) | Gewicht der Lage für Zeichen, deren Höhe je nach Schrift stark schwankt, etwa Striche, Akzente und Wurzel. Nur mit neuer Messung ändern. |
| Formvergleich: Vorsprung vor dem Original | `formeln.MIN_ABSTAND` | 0,12 | 0 bis 0,5 (Schritt 0,01) | So viel besser als das Originalzeichen muss ein Ersatz in verdächtigen Schriften passen. Erhöhen, wenn richtige Zeichen ersetzt werden. |
| Formvergleich: Mindestwert | `formeln.MIN_WERT` | 0,6 | 0,3 bis 0,95 (Schritt 0,01) | Mindestpunktzahl eines Ersatzzeichens aus Ähnlichkeit minus Lagestrafe. An zwei Datensätzen gemessen, Senken erzeugt Fehlersetzungen. |
| Formvergleich: Abstand zum Zweitbesten | `formeln.MIN_MARGE` | 0,06 | 0 bis 0,3 (Schritt 0,01) | So viel besser als das zweitbeste Zeichen muss der Sieger sein. An zwei Datensätzen gemessen, Senken erzeugt Fehlersetzungen. |
| Formvergleich: Größe der Vergleichszeichen | `formeln.GLYPH_GROESSE` | 160 px | 64 bis 320 px (Schritt 16) | Größe, in der die Vergleichszeichen aus STIX und DejaVu gerendert werden. Größer ist genauer, aber langsamer. |
| Formvergleich: Profilraster | `formeln.RASTER` | 28 | 12 bis 64 (Schritt 2) | Auflösung der Formprofile, mit denen Zeichen verglichen werden. Nur mit neuer Messung ändern. |
| Index: Größenverhältnis | `formelsatz.KLEINER` | 0,85 | 0,5 bis 0,98 (Schritt 0,01) | So viel kleiner als die Zeilenschrift muss ein Zeichen sein, um als Index oder Exponent zu gelten. Senken, wenn normaler Text hoch- oder tiefgestellt wird. |
| Exponent: Höhe | `formelsatz.HOCH` | 0,15 × Schrift | 0,02 bis 0,5 × Schrift (Schritt 0,01) | So weit über der Grundlinie beginnt ein Exponent, gemessen in Schriftgrößen. Erhöhen, wenn Fußnotenzeichen als Exponent erscheinen. |
| Index: Tiefe | `formelsatz.TIEF` | 0,08 × Schrift | 0,01 bis 0,4 × Schrift (Schritt 0,01) | So weit unter der Grundlinie beginnt ein Index, gemessen in Schriftgrößen. Erhöhen, wenn tief stehende Buchstaben als Index erscheinen. |
| Bruchstrich: Höchstdicke | `formelsatz.MAX_BALKEN_DICKE` | 1,6 pt | 0,2 bis 5 pt (Schritt 0,1) | Dickere Striche gelten nicht als Bruchstrich. Erhöhen, wenn fette Bruchstriche nicht erkannt werden. |
| Bruchstrich: Mindestlänge | `formelsatz.MIN_BALKEN` | 2 pt | 0,5 bis 20 pt (Schritt 0,5) | Kürzere Striche gelten nicht als Bruchstrich. Nur für sehr kleine Brüche senken. |
| Bruchstrich: Höchstlänge | `formelsatz.MAX_BALKEN` | 360 pt | 50 bis 800 pt (Schritt 10) | Längere Striche gelten als Trennlinie, nicht als Bruchstrich. Nur für sehr breite Formeln erhöhen. |
| Index: Suchweite | `formelsatz.SUCHWEITE` | 12 Zeichen | 1 bis 40 Zeichen (Schritt 1) | So viele Zeichen links und rechts wird das Bezugszeichen eines Index gesucht. Erhöhen, wenn Indizes an langen Ausdrücken verloren gehen. |
| Index: Abstand zum Zeichen | `formelsatz.ANGEHAENGT` | 0,2 × Schrift | 0 bis 1 × Schrift (Schritt 0,05) | So dicht muss ein Index am Zeichen davor stehen, damit ein erzeugtes Leerzeichen ignoriert wird. Senken, wenn Wörter an Indizes kleben. |
| Bruch: Zeilen je Teil | `formelsatz.MAX_ZEILEN_BRUCH` | 2 Zeilen | 1 bis 6 Zeilen (Schritt 1) | Zähler oder Nenner mit mehr Zeilen gelten als Tabelle mit Linie, nicht als Bruch. Nur für mehrzeilige Brüche erhöhen. |
| Bruch: Lücke im Teil | `formelsatz.MAX_LUECKE_BRUCH` | 1,5 × Schrift | 0,5 bis 5 × Schrift (Schritt 0,1) | Größere Lücken in Zähler oder Nenner deuten auf Tabellenspalten statt auf einen Bruch. Erhöhen, wenn breite Brüche nicht erkannt werden. |

### Tabellen

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Linie: Höchstdicke | `tabellen.MAX_DICKE` | 2,5 pt | 0,5 bis 6 pt (Schritt 0,1) | Dickere Striche sind Flächen, keine Tabellenlinien. Erhöhen für Tabellen mit sehr dicken Linien. |
| Linie: Mindestlänge | `tabellen.MIN_LAENGE` | 4 pt | 1 bis 20 pt (Schritt 0,5) | Kürzere Strecken gelten als Punkte oder Ecken. Senken für sehr kleine Tabellen. |
| Linien: Toleranz | `tabellen.TOLERANZ` | 2 pt | 0,5 bis 8 pt (Schritt 0,5) | So nah müssen Linienenden und Kreuzungen beieinander liegen. Erhöhen, wenn Gitter mit ungenau gezeichneten Linien zerfallen. |
| Mindestzeilen | `tabellen.MIN_ZEILEN` | 2 | 1 bis 6 (Schritt 1) | So viele Zeilen braucht ein Gitter, um als Tabelle zu gelten. Erhöhen, wenn kleine Rahmen als Tabelle erscheinen. |
| Mindestspalten | `tabellen.MIN_SPALTEN` | 2 | 1 bis 6 (Schritt 1) | So viele Spalten braucht ein Gitter, um als Tabelle zu gelten. Erhöhen, wenn Kästen als Tabelle erscheinen. |
| Belegte Zellen | `tabellen.MIN_BELEGT` | 0,25 | 0 bis 1 (Schritt 0,05) | Mindestanteil der Zellen mit Text. Erhöhen, wenn Zeichnungen als Tabelle erscheinen. |
| Gefüllte Zellen | `tabellen.MIN_GEFUELLT` | 3 | 1 bis 20 (Schritt 1) | So viele Zellen mit Text braucht eine Tabelle, verteilt auf mindestens zwei Zeilen und Spalten. Erhöhen, wenn leere Formblätter als Tabelle erscheinen. |
| Wortschnitte | `tabellen.MAX_SCHNITTE` | 1 | 0 bis 10 (Schritt 1) | So oft darf eine Gitterlinie ein Wort zerschneiden, bevor das Gitter als Zeichnung gilt. Erhöhen, wenn echte Tabellen wegfallen. |
| Dünn gefüllt unter | `tabellen.DUENN` | 0,5 | 0 bis 1 (Schritt 0,05) | Gitter mit weniger gefüllten Zellen gelten als dünn und brauchen ein regelmäßiges Raster. Senken, wenn lückenhafte Tabellen wegfallen. |
| Regelmäßigkeit | `tabellen.MIN_REGELMAESSIG` | 0,6 | 0 bis 1 (Schritt 0,05) | So regelmäßig muss ein dünn gefülltes Gitter sein, gemessen in Zellen je Rasterfeld. Erhöhen, wenn Schaltbilder als Tabelle erscheinen. |
| Kleiner Rahmen bis | `tabellen.KLEIN` | 16 Zellen | 4 bis 64 Zellen (Schritt 1) | Dünn gefüllte Gitter bis zu dieser Zellenzahl gelten als Rahmen um eine Abbildung. Senken, wenn kleine echte Tabellen wegfallen. |
| Text je Zelle in Rahmen | `tabellen.MIN_TEXTLAENGE` | 15 Zeichen | 1 bis 60 Zeichen (Schritt 1) | Kleine, dünn gefüllte Gitter mit kürzerem Text je Zelle gelten als beschriftete Abbildung. Senken, wenn kleine Zahlentabellen wegfallen. |
| Höchstzahl Zellen | `tabellen.MAX_ZELLEN` | 5000 Zellen | 500 bis 20000 Zellen (Schritt 500) | Größere Raster wie Millimeterpapier werden nicht als Tabelle gelesen. Nur für sehr große Tabellen erhöhen. |
| Freies Linienende | `tabellen.MAX_FREIES_ENDE` | 0,5 | 0 bis 1 (Schritt 0,05) | Frei hängende Linienenden bis zu diesem Anteil der Länge werden gekürzt, längere Linien fallen weg. Senken, wenn Zeichnungslinien in Tabellen geraten. |
| Linientabelle: Linienbreite | `tabellen.LINIEN_MIN_BREITE` | 0,25 | 0,05 bis 0,9 (Schritt 0,05) | Tabellen nur aus waagerechten Linien brauchen Linien über mindestens diesen Anteil der Seitenbreite. Erhöhen, wenn Unterstreichungen als Tabelle erscheinen. |
| Linientabelle: gleiche Linien | `tabellen.LINIEN_GLEICH` | 3 pt | 0,5 bis 10 pt (Schritt 0,5) | So genau müssen Anfang und Ende der Linien einer Linientabelle übereinstimmen. Erhöhen bei ungenau gezeichneten Tabellen. |
| Linientabelle: Höhe | `tabellen.LINIEN_MAX_ABSTAND` | 0,7 | 0,2 bis 1 (Schritt 0,05) | Anteil der Seitenhöhe, über den eine Linientabelle höchstens reicht. Erhöhen für ganzseitige Tabellen. |
| Linientabelle: Datenzeilen | `tabellen.MIN_DATENZEILEN` | 3 Zeilen | 1 bis 10 Zeilen (Schritt 1) | So viele Zeilen braucht der Rumpf einer Linientabelle. Erhöhen, wenn Textkästen als Tabelle erscheinen. |
| Linientabelle: Spaltenlücke | `tabellen.MIN_SPALTENLUECKE` | 0,55 × Schrift | 0,1 bis 2 × Schrift (Schritt 0,05) | So breit muss der Leerraum zwischen zwei Spalten in jeder Zeile sein, gemessen in Schriftgrößen. Senken, wenn eng gesetzte Spalten verschmelzen. |
| Linientabelle: Text je Zelle | `tabellen.MAX_ZELLTEXT` | 40 Zeichen | 10 bis 200 Zeichen (Schritt 5) | Mittlere Zeichenzahl je Zelle, ab der eine Linientabelle als Fließtext gilt. Erhöhen für Tabellen mit langen Texten. |

### Zeichen

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Doppeldruck: Mindestzeilen | `zeichen.MIN_DOPPELTE_ZEILEN` | 3 Zeilen | 1 bis 20 Zeilen (Schritt 1) | So viele längere Zeilen müssen doppelt vorkommen, bevor eine Seite auf doppelt gedruckten Text geprüft wird. Senken, wenn Doppeldrucke stehen bleiben. |
| Doppeldruck: Übereinstimmung | `zeichen.MIN_ANTEIL_DOPPELT` | 0,9 | 0,5 bis 1 (Schritt 0,01) | So viel einer Zeile muss an derselben Stelle schon stehen, damit sie als Kopie wegfällt. Senken erhöht das Risiko, echten Text zu verlieren. |
| Mac-Roman: Belege | `zeichen.MIN_BEWEIS` | 5 | 1 bis 30 (Schritt 1) | So oft müssen Mac-Roman-Zeichen mitten im Wort stehen, bevor eine Schrift umkodiert wird. Erhöhen, wenn Sonderzeichen fälschlich zu Umlauten werden. |
| Mac-Roman: Wörter | `zeichen.MIN_WOERTER` | 3 | 1 bis 20 (Schritt 1) | In so vielen verschiedenen Wörtern müssen diese Belege vorkommen. Erhöhen, wenn Sonderzeichen fälschlich zu Umlauten werden. |

### Spalten

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Lücke in der Zeile | `lesefolge.LUECKE` | 3 Zeichenhöhen | 1 bis 10 Zeichenhöhen (Schritt 0,5) | Ab dieser Lücke innerhalb einer Zeile beginnt ein neues Zeilenstück. Senken, wenn eng stehende Spalten nicht getrennt werden. |
| Mindestzahl Zeilenstücke | `lesefolge.MIN_LAEUFE` | 12 | 4 bis 40 (Schritt 1) | Seiten mit weniger Zeilenstücken bleiben unverändert. Senken für kurze zweispaltige Seiten. |
| Mindestbreite des Textes | `lesefolge.MIN_BREITE` | 100 pt | 20 bis 400 pt (Schritt 10) | Schmalerer Seitentext wird nie umsortiert. Senken für kleine Seitenformate. |
| Zeilen je Spalte | `lesefolge.MIN_SPALTENZEILEN` | 5 Zeilen | 2 bis 20 Zeilen (Schritt 1) | So viele fast volle Zeilen braucht jede Spalte. Senken, wenn kurze Spalten nicht erkannt werden. |
| Textzeile ab Breite | `lesefolge.LANG` | 0,3 | 0,1 bis 0,6 (Schritt 0,05) | Ab diesem Anteil der Textbreite gilt ein Zeilenstück als eigene Textzeile, sonst hängt es am vorigen. Nur mit neuer Messung ändern. |
| Breite Zeile ab | `lesefolge.BREIT` | 0,6 | 0,4 bis 0,95 (Schritt 0,05) | Ab diesem Anteil der Textbreite reicht ein Zeilenstück über beide Spalten. Senken, wenn Überschriften über beiden Spalten falsch einsortiert werden. |
| Mindestbreite der Spaltenlücke | `lesefolge.STEG_MIN` | 5 pt | 1 bis 30 pt (Schritt 0,5) | So breit muss die Lücke zwischen zwei Spalten mindestens sein. Erhöhen, wenn Tabellen fälschlich als Spalten gelten. |
| Versatz der Spalten | `lesefolge.TOLERANZ` | 6 pt | 1 bis 30 pt (Schritt 0,5) | So weit darf eine Spalte über oder unter der anderen beginnen oder enden. Erhöhen bei versetzten Spalten. |
| Zeilen über der Lücke | `lesefolge.DURCHLAESSIG` | 0,25 | 0 bis 0,6 (Schritt 0,05) | Anteil der Zeilen, die die Spaltenlücke überqueren dürfen, etwa breite Formeln oder Tabellen. Erhöhen, wenn Seiten mit vielen Formeln nicht umsortiert werden. |

### Normen

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Titel: Schriftgröße | `normen.SCHRIFTGROESSE_TOLERANZ` | 0,6 pt | 0,1 bis 3 pt (Schritt 0,1) | So weit darf die Schriftgröße einer Titelzeile von der ersten abweichen. Erhöhen, wenn Normtitel unvollständig sind. |
| Seiten bis zur Titelseite | `normen.DECKBLATT_SEITEN` | 4 Seiten | 1 bis 10 Seiten (Schritt 1) | So viele Seiten vom Anfang werden nach der Titelseite der Norm durchsucht. Erhöhen, wenn ein Normtitel fehlt. |

### Metadaten und Online

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Suchbereich für das Jahr | `pdf2md.JAHR_SUCHTEXT` | 15000 Zeichen | 2000 bis 100000 Zeichen (Schritt 1000) | So viele Zeichen vom Anfang werden nach dem Copyright-Jahr durchsucht. Erhöhen, wenn das Impressum weit hinten steht. |
| Kapitel je Sammelwerk | `zitierdaten.MAX_KAPITEL` | 400 | 0 bis 2000 (Schritt 50) | Höchstzahl der Kapitel-DOIs, die je Sammelwerk nachgeschlagen werden. Senken, wenn große Sammelwerke zu lange dauern. |

### Ablage

| Einstellung | Schlüssel | Standard | Bereich | Tooltip |
|---|---|---|---|---|
| Mindesttext | `pdf2md.MIN_TEXT_ZEICHEN` | 200 Zeichen | 0 bis 2000 Zeichen (Schritt 50) | Mit weniger Text gilt eine Datei als Scan ohne Texterkennung und kommt nach Prüfen. Senken für sehr kurze Dokumente. |
| Mindesttext bei Office, EPUB und HTML | `pdf2md.MIN_TEXT_DOKUMENT` | 20 Zeichen | 0 bis 500 Zeichen (Schritt 10) | Mit weniger Text gilt eine DOCX-, PPTX-, XLSX-, EPUB- oder HTML-Datei als fast leer und kommt nach Prüfen. Erhöhen, wenn leere Vorlagen in Fertig landen. |
