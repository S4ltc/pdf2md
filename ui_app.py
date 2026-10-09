"""Fenster von pdf2md (pywebview, Oberflaeche in ui/web) und die Python-Schnittstelle dafuer.

Die Oberflaeche ruft nur oeffentliche Methoden von Api auf (im Fenster ueber window.pywebview.api, im
Entwicklungsserver werkzeuge/ui_vorschau.py per HTTP). Ein Lauf (Starten oder ein Werkzeug) laeuft in einem eigenen
Thread; die Oberflaeche holt Fortschritt und Meldungen mit ereignisse(nach) ab. Abbrechen greift nach der aktuellen
Datei. Es laeuft immer hoechstens ein Lauf, und je Ordner nur ein Fenster (benannter Mutex).

pywebview ruft jede Api-Methode in einem eigenen Thread auf: gemeinsamer Zustand nur unter self._sperre. Attribute
der Api sind privat (Unterstrich), sonst versucht pywebview, sie fuer JavaScript freizugeben."""

import copy
import json
import multiprocessing
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import ablage
import aktualisierung
import auswertung
import einstellungen
import pdf2md
import plattform

WERKZEUGE = {
    "rueckgaengig": "Letzten Lauf rückgängig machen",
    "namen": "Namen reparieren",
    "text": "Text erneuern",
    "literatur": "Literaturliste exportieren",
}
DATEITYPEN = ("Unterstützte Dateien (*.pdf;*.docx;*.pptx;*.xlsx;*.epub;*.html;*.htm)", "Alle Dateien (*.*)")
BEREICHE = ("eingang", "pruefen", "fertig")
MAX_EREIGNISSE = 3000
PARALLEL_AB_BUECHERN = 40     # so viele fehlende Kennzahlen rechnen Unterprozesse statt eines Threads
FORTSCHRITT_ABSTAND = 0.2      # Sekunden: haeufiger meldet die Oberflaeche keinen Fortschritt (Seiten sind schnell)
STARTTEST_WARTEN = 90          # Start-Test (werkzeuge/bauen.py): so lange darf sich die Oberflaeche Zeit lassen
STARTTEST_TAKT = 0.5


def web_ordner() -> Path:
    """ui/web, in der .exe aus dem entpackten Bundle (sys._MEIPASS)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "ui" / "web"


def extern_oeffnen(pfad: Path) -> None:
    """Datei oder Ordner mit dem Standardprogramm oeffnen (PDF-Leser, Editor, Explorer); Tests ersetzen das."""
    plattform.oeffnen(pfad)


def link_oeffnen(adresse: str) -> None:
    """Seite im Standardbrowser oeffnen (nur feste Adressen aus dem Code, nie aus der Oberflaeche)."""
    import webbrowser
    webbrowser.open(adresse)


def ordner_von(bereich: str) -> Path:
    return {"eingang": pdf2md.EINGANG, "pruefen": pdf2md.PRUEFEN, "fertig": pdf2md.FERTIG}[bereich]


def ablage_setzen(basis: Path) -> None:
    """Eingang, Fertig, Prüfen, Protokoll und Sicherung liegen neben dem Programm (oder in einer Kopie zum Testen)."""
    pdf2md.EINGANG = basis / "Eingang"
    pdf2md.FERTIG = basis / "Fertig"
    pdf2md.PRUEFEN = basis / "Prüfen"
    pdf2md.PROTOKOLL = basis / "Protokoll.csv"
    pdf2md.SICHERUNG = basis / "Sicherung"


class Api:
    def __init__(self, basis: Path):
        self._basis = Path(basis)
        ablage_setzen(self._basis)
        self._einstellungen_pfad = self._basis / einstellungen.DATEINAME
        self._werte = einstellungen.laden(self._einstellungen_pfad)
        einstellungen.anwenden(self._werte)
        self._fenster = None
        self._sperre = threading.RLock()
        self._ereignisliste: list[dict] = []
        self._nr = 0
        self._lauf: dict | None = None
        self._thread: threading.Thread | None = None
        self._abbruch = threading.Event()
        self._schliessen_nach_lauf = False
        self._schliessen_erlaubt = False
        self._plaene: dict[str, object] = {}
        self._zwischenspeicher: dict[str, tuple] = {}
        self._rechnen = threading.Lock()                 # Kennzahlen der Buecher: immer nur eine Berechnung
        self._vorwaermer: threading.Thread | None = None
        self._warm = 0                                   # zaehlt fertige Hintergrundberechnungen (Teil der Signatur)
        self._letzter_fortschritt = (0.0, "")
        self._update: str | None = None                  # neuere Version auf GitHub (aktualisierung.py)
        self._update_thread: threading.Thread | None = None

    # ------------------------------------------------------------ Zustand
    def signatur(self) -> str:
        # endet eine Hintergrundberechnung der Kennzahlen, aendert sich die Signatur und das Fenster laedt neu
        return ablage.signatur(pdf2md.EINGANG, pdf2md.PRUEFEN, pdf2md.FERTIG, pdf2md.PROTOKOLL) + f"-{self._warm}"

    def stand(self) -> dict:
        """Alles fuer die Uebersicht: drei Listen, vier Kennzahlen, zwei Mini-Diagramme, Laufzustand."""
        signatur = self.signatur()
        eingang = ablage.eingang_liste(pdf2md.EINGANG)
        pruefen = ablage.pruefen_liste(pdf2md.PRUEFEN)
        fertig = ablage.fertig_liste(pdf2md.FERTIG)
        # Kennzahlen nur aus dem Zwischenspeicher; fehlt etwas, rechnet ein Hintergrund-Thread (sonst bliebe das
        # Fenster beim ersten Start mit vielen Buechern lange leer: 640 Buecher = 24 s, Haertetest)
        if self._im_speicher(pdf2md.FERTIG) and self._im_speicher(pdf2md.PRUEFEN):
            buecher = self._buecher(pdf2md.FERTIG)
            alle = buecher + self._buecher(pdf2md.PRUEFEN)
            kennzahlen = auswertung.uebersicht(buecher, len(pruefen), sum(e["bereit"] for e in pruefen))
            herkunft = auswertung.herkunft(alle)
        else:
            self._vorwaermen()
            alle, kennzahlen, herkunft = [], None, None
        laeufe = [l for l in auswertung.laeufe(self._protokoll(), self._seiten_je_name(alle))
                  if l["art"] in ("Umwandlung", "Text erneuert")]
        return {"eingang": eingang, "pruefen": pruefen, "fertig": fertig, "kennzahlen": kennzahlen,
                "mini": {"laeufe": laeufe[-24:], "herkunft": herkunft},
                "lauf": self._laufzustand(), "signatur": signatur, "ordner": str(self._basis),
                "version": {"aktuell": aktualisierung.VERSION, "neu": self._update}}

    # ------------------------------------------------------------ Version
    def update_pruefen_starten(self) -> None:
        """Fragt im Hintergrund nach einer neueren Version (einmal beim Start, abschaltbar: aktualisierung.SUCHEN).
        Das Ergebnis aendert die Signatur, das Fenster laedt dann neu und zeigt den Hinweis."""
        def pruefen():
            neu = aktualisierung.neuere_version()
            if neu:
                with self._sperre:
                    self._update = neu
                    self._warm += 1
        self._update_thread = threading.Thread(target=pruefen, daemon=True)
        self._update_thread.start()

    def update_oeffnen(self) -> dict:
        link_oeffnen(aktualisierung.SEITE)
        return {"ok": True}

    def ereignisse(self, nach: int = 0) -> dict:
        with self._sperre:
            neu = [e for e in self._ereignisliste if e["nr"] > nach]
            return {"ereignisse": neu, "lauf": self._laufzustand(), "letzte": self._nr}

    # ------------------------------------------------------------ Dateien
    def hinzufuegen_dialog(self) -> dict:
        if self._fenster is None:
            return {"kopiert": [], "abgelehnt": [], "hinweis": "Den Dateidialog gibt es nur im Programmfenster."}
        import webview
        pfade = self._fenster.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=DATEITYPEN)
        return self.hinzufuegen(list(pfade or []))

    def hinzufuegen(self, pfade: list) -> dict:
        ergebnis = ablage.kopieren([p for p in pfade if p], pdf2md.EINGANG)
        if ergebnis["kopiert"] or ergebnis["abgelehnt"]:
            kopiert = pdf2md.anzahl(len(ergebnis["kopiert"]), "Datei", "Dateien")
            self._ereignis("meldung", text=f"{kopiert} nach Eingang kopiert"
                           + "".join(f"; abgelehnt: {n} ({g})" for n, g in ergebnis["abgelehnt"]))
        return {"kopiert": ergebnis["kopiert"], "abgelehnt": [list(a) for a in ergebnis["abgelehnt"]]}

    def datei_oeffnen(self, bereich: str, name: str, art: str = "md") -> dict:
        """Oeffnet eine Datei aus Eingang, Prüfen oder Fertig mit dem Standardprogramm. name ist der Dateiname in der
        Liste (Eingang: das Original, Prüfen/Fertig: die .md); art "original" oeffnet die Originaldatei zur .md. Nur
        Dateien direkt in diesen drei Ordnern, nie ein Pfad, den die Oberflaeche zusammensetzt."""
        if bereich not in BEREICHE or art not in ("md", "original"):
            return {"ok": False, "grund": "unbekannter Bereich"}
        ordner = ordner_von(bereich)
        if not name or Path(name).name != name:
            return {"ok": False, "grund": "ungültiger Dateiname"}
        pfad = ordner / name
        if bereich != "eingang" and art == "original":
            pfad = pdf2md.original_zu_md(pfad) if pfad.suffix.lower() == ".md" else None
        if pfad is None or not pfad.is_file() or pfad.resolve().parent != ordner.resolve():
            return {"ok": False, "grund": f"{name}: Datei nicht gefunden"}
        try:
            extern_oeffnen(pfad)
        except OSError as e:
            return {"ok": False, "grund": f"{pfad.name} lässt sich nicht öffnen ({e})"}
        return {"ok": True, "datei": pfad.name}

    def ordner_oeffnen(self, bereich: str) -> dict:
        """Oeffnet Eingang, Prüfen oder Fertig im Explorer (legt den Ordner bei Bedarf an)."""
        if bereich not in BEREICHE:
            return {"ok": False, "grund": "unbekannter Bereich"}
        ordner = ordner_von(bereich)
        try:
            ordner.mkdir(parents=True, exist_ok=True)
            extern_oeffnen(ordner)
        except OSError as e:
            return {"ok": False, "grund": f"{ordner.name} lässt sich nicht öffnen ({e})"}
        return {"ok": True, "ordner": str(ordner)}

    # ------------------------------------------------------------ Lauf
    def starten(self) -> dict:
        """Verarbeitet alle Dateien in Eingang und uebernimmt vollstaendige Dateien aus Prüfen."""
        def lauf(stempel: str):
            return pdf2md.eingang_verarbeiten(stempel, abbrechen=self._abbruch.is_set,
                                              datei_beginnt=self._datei_beginnt, datei_fertig=self._datei_fertig)
        return self._starten("Umwandlung", lauf)

    def abbrechen(self) -> None:
        with self._sperre:
            if self._lauf is not None and not self._abbruch.is_set():
                self._abbruch.set()
                self._lauf["abbrechen"] = True
                self._ereignis("meldung", text="Abbruch nach der aktuellen Datei angefordert")

    def werkzeug_vorschau(self, name: str) -> dict:
        """Was das Werkzeug tun wuerde, ohne etwas zu aendern. Ausgefuehrt wird spaeter genau diese Liste."""
        if name not in WERKZEUGE:
            return {"name": name, "fehler": "unbekanntes Werkzeug"}
        if name == "rueckgaengig":
            plan = pdf2md.rueckgaengig_plan()
            eintraege = [{"alt": Path(z["nach_pfad"]).name, "neu": str(Path(z["von_pfad"]))} for z in plan["zeilen"]] \
                if plan else []
            hinweis = (f"Lauf vom {plan['lauf']}: Originale gehen an ihren alten Ort mit altem Namen, die .md "
                       "daneben. Gelöscht wird nichts." if plan else "Kein Lauf, der noch rückgängig gemacht werden kann.")
        elif name == "namen":
            plan = pdf2md.namen_plan()
            eintraege = [{"alt": e["alt"], "neu": e["neu"]} for e in plan]
            hinweis = ("Original und .md bekommen den Namen aus Titel, Autor und Jahr im Kopfblock. Auch von Hand "
                       "umbenannte Dateien werden zurückbenannt." if plan
                       else "Alle Namen in Fertig stimmen mit dem Kopfblock überein.")
        elif name == "literatur":
            plan = pdf2md.literatur_plan()
            eintraege = [{"alt": e["name"], "neu": e["schluessel"]} for e in plan]
            hinweis = (f"Schreibt {pdf2md.LITERATURLISTE} neben das Programm (eine vorhandene Datei wird ersetzt), "
                       "zum Import in Citavi, Zotero oder LaTeX. Rechts steht der Schlüssel zum Zitieren." if plan
                       else "In Fertig gibt es noch keine Datei mit Titel im Kopfblock.")
        else:
            plan = pdf2md.text_plan()
            eintraege = [{"alt": e["name"], "neu": ""} for e in plan]
            hinweis = ("Der Text dieser PDFs wird mit dem aktuellen Verfahren neu umgewandelt. Name und Kopfblock "
                       "bleiben, die alte .md kommt nach Sicherung." if plan
                       else "Alle PDF-Texte in Fertig sind mit dem aktuellen Verfahren erzeugt.")
        with self._sperre:
            self._plaene[name] = plan
        return {"name": name, "titel": WERKZEUGE[name], "eintraege": eintraege, "hinweis": hinweis,
                "leer": not eintraege, "anzahl": len(eintraege)}

    def werkzeug_starten(self, name: str) -> dict:
        if name not in WERKZEUGE:
            return {"ok": False, "grund": "unbekanntes Werkzeug"}
        with self._sperre:
            plan = self._plaene.pop(name, None)
        if not plan:
            return {"ok": False, "grund": "Erst die Vorschau öffnen."}
        if name == "rueckgaengig":
            return self._starten(WERKZEUGE[name], lambda stempel: {"zurueck": pdf2md.rueckgaengig(plan)})
        if name == "literatur":
            return self._starten(WERKZEUGE[name], lambda stempel: self._literatur(plan))
        if name == "namen":
            return self._starten(WERKZEUGE[name], lambda stempel: {
                "umbenannt": pdf2md.namen_reparieren(stempel, plan, abbrechen=self._abbruch.is_set),
                "abgebrochen": self._abbruch.is_set()})
        return self._starten(WERKZEUGE[name], lambda stempel: {
            "erneuert": pdf2md.text_erneuern(stempel, plan, abbrechen=self._abbruch.is_set,
                                             datei_beginnt=self._datei_beginnt, datei_fertig=self._datei_fertig),
            "abgebrochen": self._abbruch.is_set()})

    @staticmethod
    def _literatur(plan: list[dict]) -> dict:
        ziel = pdf2md.literatur_schreiben(plan)
        pdf2md.melden(f"{pdf2md.anzahl(len(plan), 'Eintrag', 'Einträge')} nach {ziel} geschrieben")
        return {"eintraege": len(plan), "datei": str(ziel)}

    # ------------------------------------------------------------ Einstellungen
    def einstellungen(self) -> dict:
        return {"gesperrt": self._lauf is not None, "gruppen": list(einstellungen.GRUPPEN),
                "eintraege": einstellungen.fuer_ui(self._werte), "datei": str(self._einstellungen_pfad)}

    def einstellung_setzen(self, schluessel: str, wert) -> dict:
        with self._sperre:
            if self._lauf is not None:
                return {"ok": False, "grund": "Während eines Laufs gesperrt."}
            try:
                self._werte[schluessel] = einstellungen.pruefen(schluessel, wert)
            except (KeyError, ValueError) as e:
                return {"ok": False, "grund": str(e)}
            self._speichern()
            eintrag = next(e for e in einstellungen.fuer_ui(self._werte) if e["schluessel"] == schluessel)
            return {"ok": True, "eintrag": eintrag}

    def einstellungen_zuruecksetzen(self, schluessel: str | None = None) -> dict:
        with self._sperre:
            if self._lauf is not None:
                return {"ok": False, "grund": "Während eines Laufs gesperrt."} | self.einstellungen()
            standard = einstellungen.standardwerte()
            if schluessel is None:
                self._werte = standard
            elif schluessel in standard:
                self._werte[schluessel] = standard[schluessel]
            self._speichern()
            return {"ok": True} | self.einstellungen()

    # ------------------------------------------------------------ Auswertung
    def auswertung(self) -> dict:
        eingang = ablage.eingang_liste(pdf2md.EINGANG)
        pruefen = ablage.pruefen_liste(pdf2md.PRUEFEN)
        fertig = ablage.fertig_liste(pdf2md.FERTIG)
        buecher = self._buecher(pdf2md.FERTIG)
        alle = buecher + self._buecher(pdf2md.PRUEFEN)
        zeilen = self._protokoll()
        seiten = self._seiten_je_name(alle)
        return {
            "bestand": auswertung.bestand(eingang, pruefen, fertig),
            "laeufe": [l for l in auswertung.laeufe(zeilen, seiten) if l["art"] in ("Umwandlung", "Text erneuert")],
            "dauern": [d for d in auswertung.dauern(zeilen, seiten) if d["dauer_s"] is not None and d["seiten"]],
            "herkunft": auswertung.herkunft(alle),
            "pruefgruende": [list(g) for g in auswertung.pruefgruende(alle)],
            "ieee": list(auswertung.ieee_anteil(buecher)),
            "textsummen": auswertung.textsummen(buecher),
            "textqualitaet": auswertung.textqualitaet(buecher),
            "offene_stellen": auswertung.offene_stellen(buecher),
        }

    # ------------------------------------------------------------ Fenster
    def schliessen_anfragen(self) -> dict:
        """Vom Fenster nach der Rueckfrage: laeuft ein Lauf, endet er nach der aktuellen Datei und das Fenster schliesst
        danach; sonst schliesst es sofort."""
        with self._sperre:
            if self._lauf is not None:
                self._schliessen_nach_lauf = True
                self.abbrechen()
                return {"laeuft": True}
            self._schliessen_erlaubt = True
        if self._fenster is not None:
            threading.Thread(target=self._fenster.destroy, daemon=True).start()
        return {"laeuft": False}

    # ------------------------------------------------------------ intern
    def _fenster_setzen(self, fenster) -> None:
        self._fenster = fenster

    def _beim_schliessen(self) -> bool:
        """closing-Ereignis von pywebview: False haelt das Fenster offen (laufender Lauf, erst nachfragen)."""
        if self._lauf is None or self._schliessen_erlaubt:
            return True
        if self._fenster is not None:
            threading.Thread(target=lambda: self._fenster.evaluate_js("window.app && app.schliessenFragen()"),
                             daemon=True).start()
        return False

    def _beim_laden(self) -> None:
        """Dateien, die ins Fenster gezogen werden, liefert pywebview mit vollem Pfad (pywebviewFullPath)."""
        from webview.dom import DOMEventHandler

        def fallen_gelassen(ereignis):
            dateien = ereignis.get("dataTransfer", {}).get("files", [])
            pfade = [d.get("pywebviewFullPath") for d in dateien if d.get("pywebviewFullPath")]
            if pfade:
                self.hinzufuegen(pfade)

        self._fenster.dom.document.events.drop += DOMEventHandler(fallen_gelassen, True, True)

    def _speichern(self) -> None:
        einstellungen.speichern(self._einstellungen_pfad, self._werte)
        einstellungen.anwenden(self._werte)

    def _protokoll(self) -> list[dict]:
        try:
            return auswertung.protokoll_lesen(pdf2md.PROTOKOLL.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            return []

    def _schluessel(self, md: Path, aktuell: str):
        st = md.stat()
        return (st.st_mtime_ns, st.st_size, aktuell)

    def _im_speicher(self, ordner: Path) -> bool:
        """Liegen fuer alle .md des Ordners aktuelle Kennzahlen im Zwischenspeicher? (nur stat, kein Lesen)"""
        if not ordner.is_dir():
            return True
        aktuell = pdf2md.erwartete_textquelle()
        for md in ordner.glob("*.md"):
            gespeichert = self._zwischenspeicher.get(str(md))
            try:
                if not gespeichert or gespeichert[0] != self._schluessel(md, aktuell):
                    return False
            except OSError:
                continue
        return True

    def _vorwaermen(self) -> None:
        """Rechnet die fehlenden Kennzahlen in einem Hintergrund-Thread (hoechstens einer zur Zeit)."""
        with self._sperre:
            if self._vorwaermer is not None and self._vorwaermer.is_alive():
                return

            def rechnen():
                try:
                    self._parallel_rechnen()
                except Exception:
                    pass                                 # dann rechnet _buecher unten alles im Thread
                self._buecher(pdf2md.FERTIG)
                self._buecher(pdf2md.PRUEFEN)
                self._warm += 1
            self._vorwaermer = threading.Thread(target=rechnen, daemon=True)
            self._vorwaermer.start()

    def _parallel_rechnen(self) -> None:
        """Viele fehlende Kennzahlen in Unterprozessen rechnen: im Thread hielt die Berechnung bei 640 Buechern den
        Interpreter so lange fest, dass auch schnelle Abfragen des Fensters Sekunden warteten (Haertetest)."""
        aktuell = pdf2md.erwartete_textquelle()
        fehlend = []
        for ordner in (pdf2md.FERTIG, pdf2md.PRUEFEN):
            for md in (ordner.glob("*.md") if ordner.is_dir() else []):
                try:
                    schluessel = self._schluessel(md, aktuell)
                except OSError:
                    continue
                gespeichert = self._zwischenspeicher.get(str(md))
                if not gespeichert or gespeichert[0] != schluessel:
                    fehlend.append((md, schluessel))
        if len(fehlend) < PARALLEL_AB_BUECHERN:
            return
        import concurrent.futures
        prozesse = max(1, min(8, (os.cpu_count() or 2) // 2, len(fehlend) // 10))
        with concurrent.futures.ProcessPoolExecutor(max_workers=prozesse) as pool:
            ergebnisse = pool.map(ablage.kennzahlen_lesen, [str(m) for m, _ in fehlend], [aktuell] * len(fehlend),
                                  chunksize=8)
            for (md, schluessel), kennzahlen in zip(fehlend, ergebnisse):
                with self._rechnen:
                    self._zwischenspeicher[str(md)] = (schluessel, kennzahlen)

    def _buecher(self, ordner: Path) -> list[dict]:
        """Kennzahlen je .md, zwischengespeichert nach Aenderungszeit und Groesse (die Texte sind gross)."""
        with self._rechnen:
            return self._buecher_rechnen(ordner)

    def _buecher_rechnen(self, ordner: Path) -> list[dict]:
        if not ordner.is_dir():
            return []
        aktuell = pdf2md.erwartete_textquelle()
        buecher = []
        for md in sorted(ordner.glob("*.md")):
            try:
                schluessel = self._schluessel(md, aktuell)
            except OSError:
                continue
            gespeichert = self._zwischenspeicher.get(str(md))
            if gespeichert and gespeichert[0] == schluessel:
                buecher.append(gespeichert[1])
                continue
            kennzahlen = ablage.kennzahlen_lesen(str(md), aktuell)
            self._zwischenspeicher[str(md)] = (schluessel, kennzahlen)
            buecher.append(kennzahlen)
        return buecher

    @staticmethod
    def _seiten_je_name(buecher: list[dict]) -> dict[str, int]:
        seiten = {}
        for b in buecher:
            if b["seiten"]:
                seiten[b["name"]] = b["seiten"]
                if b.get("original"):
                    seiten.setdefault(b["original"], b["seiten"])
        return seiten

    def _ereignis(self, typ: str, **daten) -> None:
        with self._sperre:
            self._nr += 1
            self._ereignisliste.append({**daten, "nr": self._nr, "art": typ, "zeit": time.strftime("%H:%M:%S")})
            if len(self._ereignisliste) > MAX_EREIGNISSE:
                del self._ereignisliste[:len(self._ereignisliste) - MAX_EREIGNISSE]

    def _laufzustand(self) -> dict | None:
        with self._sperre:
            if self._lauf is None:
                return None
            zustand = copy.deepcopy({k: v for k, v in self._lauf.items() if k != "start_zeit"})
            return zustand | {"sekunden": int(time.time() - self._lauf["start_zeit"])}

    def _starten(self, art: str, ziel) -> dict:
        with self._sperre:
            if self._lauf is not None:
                return {"ok": False, "grund": "Es läuft bereits ein Lauf."}
            self._abbruch.clear()
            stempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._lauf = {"art": art, "lauf": stempel, "aktuell": None, "dateien": {}, "abbrechen": False,
                          "start_zeit": time.time()}
            self._thread = threading.Thread(target=self._ausfuehren, args=(art, ziel, stempel), daemon=True)
            self._ereignis("lauf_beginnt", lauf_art=art)
            self._thread.start()
        return {"ok": True}

    def _ausfuehren(self, art: str, ziel, stempel: str) -> None:
        ergebnis, fehler = None, None
        try:
            with pdf2md.rueckmeldung(self._melden, self._fortschritt):
                ergebnis = ziel(stempel)
        except Exception as e:                                   # der Lauf darf das Fenster nie mitreissen
            fehler = f"{type(e).__name__}: {e}"
        try:                                                     # Kennzahlen der neuen Dateien gleich mitrechnen,
            self._buecher(pdf2md.FERTIG)                         # damit die Uebersicht nach dem Lauf vollstaendig ist
            self._buecher(pdf2md.PRUEFEN)
        except Exception:
            pass
        with self._sperre:
            self._lauf = None
            self._ereignis("lauf_ende", lauf_art=art, ergebnis=ergebnis, fehler=fehler)
            schliessen = self._schliessen_nach_lauf
            if schliessen:
                self._schliessen_erlaubt = True
        self._zwischenspeicher_bereinigen()
        if schliessen and self._fenster is not None:
            self._fenster.destroy()

    def _zwischenspeicher_bereinigen(self) -> None:
        for pfad in [p for p in self._zwischenspeicher if not Path(p).exists()]:
            del self._zwischenspeicher[pfad]

    def _warten(self, sekunden: float) -> None:
        """Fuer Tests: wartet, bis der Lauf-Thread fertig ist."""
        thread = self._thread
        if thread is not None:
            thread.join(sekunden)

    def _melden(self, text: str) -> None:
        text = text.strip()
        if text:
            self._ereignis("meldung", text=text)

    def _fortschritt(self, phase: str, erledigt: int = 0, gesamt: int = 0) -> None:
        jetzt = time.time()
        zuletzt, letzte_phase = self._letzter_fortschritt
        if phase == letzte_phase and jetzt - zuletzt < FORTSCHRITT_ABSTAND and erledigt != gesamt:
            return
        self._letzter_fortschritt = (jetzt, phase)
        with self._sperre:
            if self._lauf is not None and self._lauf["aktuell"] is not None:
                self._lauf["aktuell"].update(phase=phase, erledigt=erledigt, gesamt=gesamt)
                name = self._lauf["aktuell"]["name"]
            else:
                name = None
            self._ereignis("fortschritt", name=name, phase=phase, erledigt=erledigt, gesamt=gesamt)

    def _datei_beginnt(self, name: str, nummer: int, anzahl: int) -> None:
        with self._sperre:
            if self._lauf is not None:
                self._lauf["aktuell"] = {"name": name, "nummer": nummer, "anzahl": anzahl, "phase": "",
                                         "erledigt": 0, "gesamt": 0}
                self._lauf["dateien"][name] = "läuft"
            self._ereignis("datei_beginnt", name=name, nummer=nummer, anzahl=anzahl)

    def _datei_fertig(self, name: str, status: str) -> None:
        with self._sperre:
            if self._lauf is not None:
                self._lauf["dateien"][name] = status
                self._lauf["aktuell"] = None
            self._ereignis("datei_fertig", name=name, status=status)


# ---------------------------------------------------------------- Programmstart
_MUTEX = None


def einzelinstanz(basis: Path) -> bool:
    """True, wenn fuer diesen Ordner noch kein Fenster offen ist (plattform.py: Mutex bzw. Sperrdatei)."""
    return plattform.einzelinstanz(basis)


def system_dunkel() -> bool:
    return plattform.dunkel()


def meldung(text: str) -> None:
    plattform.meldung(text)


def _starttest(fenster, ziel: Path) -> None:
    """Nur fuer den automatischen Start-Test beim Bauen (Umgebungsvariable PDF2MD_STARTTEST, kein Schalter fuer
    Nutzer): wartet, bis die Oberflaeche ihre Versionsnummer ueber die Python-Schnittstelle geholt und angezeigt hat
    (Engine, Seite und Schnittstelle laufen), schreibt das Ergebnis nach ziel und schliesst das Fenster."""
    ergebnis = {"ok": False, "version": aktualisierung.VERSION, "gui": plattform.gui(), "system": plattform.SYSTEM}
    ende = time.time() + STARTTEST_WARTEN
    while time.time() < ende:
        try:
            angezeigt = fenster.evaluate_js("(document.querySelector('#version') || {}).textContent || ''")
        except Exception as e:                                # die Seite laedt noch oder die Engine hakt
            angezeigt, ergebnis["fehler"] = None, repr(e)[:500]
        if angezeigt == aktualisierung.VERSION:
            ergebnis.update(ok=True, angezeigt=angezeigt)
            ergebnis.pop("fehler", None)
            break
        time.sleep(STARTTEST_TAKT)
    Path(ziel).write_text(json.dumps(ergebnis, ensure_ascii=False), encoding="utf-8")
    fenster.destroy()


def main() -> int:
    multiprocessing.freeze_support()                         # noetig, damit die Unterprozesse in der .exe starten
    plattform.vorbereiten()
    starttest = os.environ.get("PDF2MD_STARTTEST")             # nur beim Bauen gesetzt (werkzeuge/bauen.py)
    # Ablage neben dem Programm; PDF2MD_ABLAGE zeigt zum Entwickeln auf eine Kopie (nie auf dist)
    basis = Path(os.environ.get("PDF2MD_ABLAGE") or pdf2md.BASE_DIR)
    if not einzelinstanz(basis):
        meldung(f"pdf2md läuft für diesen Ordner schon:\n{basis}")
        return 1
    import webview
    api = Api(basis)
    if not starttest:
        api.update_pruefen_starten()
    fenster = webview.create_window("pdf2md", url=str(web_ordner() / "index.html"), js_api=api, width=1280,
                                    height=820, min_size=(720, 560), text_select=True,
                                    background_color="#1f1f1f" if system_dunkel() else "#fafafa")
    api._fenster_setzen(fenster)
    fenster.events.closing += api._beim_schliessen
    fenster.events.loaded += api._beim_laden
    if starttest:
        webview.start(_starttest, (fenster, Path(starttest)), gui=plattform.gui(), private_mode=True)
    else:
        webview.start(gui=plattform.gui(), private_mode=True)
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
